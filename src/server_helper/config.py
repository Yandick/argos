"""
Configuration Manager for ServerHelper
Loads settings from setting.json (current dir or ~/.server-helper/setting.json)
"""
import os
import json
import uuid

DEFAULT_CONFIG = {
    "servers": [],
    "agents": {
        "default": "claude",
        "claude": {
            "name": "Claude Code",
            "cmd": "claude",
            "type": "cli"
        },
        "agy": {
            "name": "Antigravity CLI",
            "cmd": "agy",
            "type": "cli"
        },
        "codex": {
            "name": "OpenAI / Codex API",
            "api_base": "https://api.deepseek.com/v1",
            "api_key": "",
            "model": "deepseek-chat",
            "type": "api"
        }
    },
    "settings": {
        "theme": "dark",
        "default_agent": "claude"
    }
}


class Config:
    def __init__(self, config_path=None):
        self.config_path = self._resolve_path(config_path)
        self.data = self._load()
        self._apply_proxy()

    def _resolve_path(self, custom_path=None):
        if custom_path and os.path.exists(custom_path):
            return os.path.abspath(custom_path)
        # Check current working directory for setting.json
        local_file = os.path.join(os.getcwd(), "setting.json")
        if os.path.isfile(local_file):
            return local_file
        # Fallback to home dir
        home_dir = os.path.expanduser(os.environ.get("SERVER_HELPER_HOME", "~/.server-helper"))
        os.makedirs(home_dir, exist_ok=True)
        return os.path.join(home_dir, "setting.json")

    def _load(self):
        if not os.path.exists(self.config_path):
            self._save(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            return DEFAULT_CONFIG

    def _save(self, data=None):
        if data is None:
            data = self.data
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] 保存配置失败: {e}")

    def _normalize_server(self, s):
        if not isinstance(s, dict):
            return s
        if "id" not in s:
            s["id"] = "srv-" + str(uuid.uuid4())[:8]
        if "auth_type" not in s and "auth" in s:
            s["auth_type"] = s["auth"]
        if "auth" not in s and "auth_type" in s:
            s["auth"] = s["auth_type"]
        if "key_path" not in s and "key" in s:
            s["key_path"] = s["key"]
        if "user" not in s and "username" in s:
            s["user"] = s["username"]
        if "username" not in s and "user" in s:
            s["username"] = s["user"]
        if "password" not in s and "pass" in s:
            s["password"] = s["pass"]
        if "pass" not in s and "password" in s:
            s["pass"] = s["password"]
        return s

    def get_servers(self):
        servers = self.data.get("servers", [])
        return [self._normalize_server(s) for s in servers]

    def get_server(self, name_or_id):
        for s in self.get_servers():
            if s.get("id") == name_or_id or s.get("name") == name_or_id:
                return s
        return None

    def add_or_update_server(self, name, host, port=22, user="root", auth_type="key", key_path=None, password=None, default_dir=None):
        servers = self.data.get("servers", [])
        existing = self.get_server(name)
        if existing:
            existing.update({
                "host": host,
                "port": int(port),
                "user": user,
                "auth_type": auth_type,
                "key_path": key_path,
                "password": password,
                "default_dir": default_dir
            })
            res = existing
        else:
            server_id = "srv-" + str(uuid.uuid4())[:8]
            res = {
                "id": server_id,
                "name": name,
                "host": host,
                "port": int(port),
                "user": user,
                "auth_type": auth_type,
                "key_path": key_path or os.path.expanduser("~/.ssh/id_rsa"),
                "password": password or "",
                "default_dir": default_dir or ""
            }
            servers.append(res)
        self.data["servers"] = servers
        self._save()
        return res

    def remove_server(self, name_or_id):
        servers = self.data.get("servers", [])
        new_servers = [s for s in servers if s.get("id") != name_or_id and s.get("name") != name_or_id]
        if len(new_servers) != len(servers):
            self.data["servers"] = new_servers
            self._save()
            return True
        return False

    def rename_server(self, old_name_or_id, new_name):
        new_name = (new_name or "").strip()
        if not new_name:
            return False, "新名称不能为空"
        servers = self.data.get("servers", [])
        target = None
        for s in servers:
            if s.get("id") == old_name_or_id or s.get("name") == old_name_or_id:
                target = s
                break
        if not target:
            return False, f"未找到服务器: {old_name_or_id}"
        target["name"] = new_name
        self._save()
        try:
            g_path = os.path.expanduser("~/.server-helper/setting.json")
            if os.path.isfile(g_path):
                with open(g_path, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return True, new_name

    def get_agents(self):
        return self.data.get("agents", {})

    def get_agent(self, name):
        agents = self.get_agents()
        return agents.get(name) or agents.get("claude")

    def get_settings(self):
        return self.data.get("settings", {})

    def update_settings(self, new_settings):
        self.data["settings"].update(new_settings)
        self._save()
        try:
            g_path = os.path.expanduser("~/.server-helper/setting.json")
            if os.path.isfile(g_path):
                with open(g_path, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return self.data["settings"]

    def get_model(self, agent_name=None):
        settings = self.get_settings()
        if agent_name:
            ag = self.get_agent(agent_name)
            if ag and ag.get("model"):
                return ag.get("model")
        return settings.get("default_model") or "gemini-2.5-pro"

    def set_model(self, model_name, agent_name=None):
        model_name = (model_name or "").strip()
        if agent_name:
            agents = self.get_agents()
            if agent_name in agents:
                agents[agent_name]["model"] = model_name
        self.update_settings({"default_model": model_name})
        return model_name

    def get_thinking_effort(self):
        settings = self.get_settings()
        return settings.get("thinking_effort") or "high"

    def set_thinking_effort(self, effort):
        effort = (effort or "").lower().strip()
        if effort not in ("low", "medium", "high", "off"):
            effort = "high"
        self.update_settings({"thinking_effort": effort})
        agents = self.get_agents()
        if "agy" in agents:
            agents["agy"]["thinking_effort"] = effort
        self._save()
        return effort

    def get_proxy(self):
        settings = self.get_settings()
        return settings.get("proxy") or os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""

    def set_proxy(self, proxy_url):
        proxy_url = (proxy_url or "").strip()
        if proxy_url.lower() in ("off", "none", "disable", "no", "0"):
            proxy_url = ""
        self.update_settings({"proxy": proxy_url})
        self._apply_proxy(proxy_url)
        return proxy_url

    def _apply_proxy(self, proxy_url=None):
        if proxy_url is None:
            proxy_url = self.get_proxy()
        if proxy_url:
            for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
                os.environ[k] = proxy_url
        else:
            for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
                os.environ.pop(k, None)

