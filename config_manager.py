"""
Configuration Manager for ServerHelper
Handles persistent storage of SSH servers, task presets, and application settings.
"""
import os
import json
import uuid

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "settings": {
        "port": 8765,
        "default_agent_cli": "claude",
        "api_key": "",
        "api_base": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "theme": "dark",
        "font_size": 13,
        "auto_reconnect": True
    },
    "servers": [],
    "task_presets": []
}


class ConfigManager:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        self.config = self._load()

    def _load(self):
        if not os.path.exists(CONFIG_FILE):
            self._save(DEFAULT_CONFIG)
            return DEFAULT_CONFIG
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in data:
                        data[k] = v
                # Clean up legacy sample servers/presets if present
                if "servers" in data:
                    data["servers"] = [s for s in data["servers"] if s.get("id") != "sample-server"]
                if "task_presets" in data:
                    data["task_presets"] = [p for p in data["task_presets"] if not p.get("id", "").startswith("preset-")]
                return data
        except Exception as e:
            print(f"[ConfigManager] Error reading config: {e}, using default.")
            return DEFAULT_CONFIG

    def _save(self, data=None):
        if data is None:
            data = self.config
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ConfigManager] Failed to save config: {e}")

    def get_all(self):
        return self.config

    def get_settings(self):
        return self.config.get("settings", {})

    def update_settings(self, settings):
        self.config["settings"].update(settings)
        self._save()
        return self.config["settings"]

    def get_servers(self):
        return self.config.get("servers", [])

    def get_server_by_id(self, server_id):
        for s in self.config.get("servers", []):
            if s.get("id") == server_id:
                return s
        return None

    def save_server(self, server_data):
        servers = self.config.get("servers", [])
        server_id = server_data.get("id")
        if not server_id:
            server_id = "srv-" + str(uuid.uuid4())[:8]
            server_data["id"] = server_id
            servers.append(server_data)
        else:
            updated = False
            for i, s in enumerate(servers):
                if s.get("id") == server_id:
                    servers[i] = server_data
                    updated = True
                    break
            if not updated:
                servers.append(server_data)
        self.config["servers"] = servers
        self._save()
        return server_data

    def delete_server(self, server_id):
        self.config["servers"] = [s for s in self.config.get("servers", []) if s.get("id") != server_id]
        self._save()
        return True

    def get_task_presets(self):
        return self.config.get("task_presets", [])

    def save_task_preset(self, preset_data):
        presets = self.config.get("task_presets", [])
        preset_id = preset_data.get("id")
        if not preset_id:
            preset_id = "task-" + str(uuid.uuid4())[:8]
            preset_data["id"] = preset_id
            presets.append(preset_data)
        else:
            updated = False
            for i, p in enumerate(presets):
                if p.get("id") == preset_id:
                    presets[i] = preset_data
                    updated = True
                    break
            if not updated:
                presets.append(preset_data)
        self.config["task_presets"] = presets
        self._save()
        return preset_data

    def delete_task_preset(self, preset_id):
        self.config["task_presets"] = [p for p in self.config.get("task_presets", []) if p.get("id") != preset_id]
        self._save()
        return True
