"""
Argos Dynamic Agent Model Loader
Inspects local configuration files of installed coding agents
(OpenCode, Claude Code, Codex, Antigravity, Aider) and dynamically
discovers their configured and available AI models.
"""
import os
import json
import re
import time

# get_agent_models() sits on keystroke-frequency hot paths (toolbar render,
# slash completion). The loaders read several JSON/TOML files from disk (and
# codex may attempt HTTP), so cache results per agent with a short TTL.
_MODELS_CACHE = {}
_MODELS_TTL = 10.0  # seconds

DEFAULT_AGY_MODELS = [
    {"cmd": "gemini-3.8-flash", "name": "Gemini 3.8 Flash", "desc": "Google latest flagship default model (fast & smart)", "badge": "default"},
    {"cmd": "gemini-3.1-pro",   "name": "Gemini 3.1 Pro",   "desc": "Google top-tier deep reasoning pro model", "badge": "official"},
    {"cmd": "gemini-2.5-pro",   "name": "Gemini 2.5 Pro",   "desc": "Complex reasoning & software architecture", "badge": "official"},
    {"cmd": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "desc": "Ultra fast lightweight model", "badge": "official"},
]

DEFAULT_CLAUDE_MODELS = [
    {"cmd": "claude-3-7-sonnet", "name": "Claude 3.7 Sonnet", "desc": "Anthropic latest hybrid reasoning & coding model", "badge": "default"},
    {"cmd": "claude-3-5-sonnet", "name": "Claude 3.5 Sonnet", "desc": "Industry standard programming benchmark model", "badge": "official"},
    {"cmd": "claude-3-5-haiku",  "name": "Claude 3.5 Haiku",  "desc": "Fast lightweight responsive model", "badge": "official"},
    {"cmd": "claude-3-opus",     "name": "Claude 3 Opus",     "desc": "Deep analytical reasoning model", "badge": "official"},
]

DEFAULT_OPENCODE_MODELS = [
    {"cmd": "qwen3.8-max",       "name": "Qwen 3.8 Max",      "desc": "Alibaba Cloud flagship reasoning model", "badge": "default"},
    {"cmd": "qwen3.8-flash",     "name": "Qwen 3.8 Flash",    "desc": "Fast high-throughput reasoning model", "badge": "popular"},
    {"cmd": "qwen3.7-max",       "name": "Qwen 3.7 Max",      "desc": "Deep thinking reasoning model", "badge": "popular"},
    {"cmd": "deepseek-chat",     "name": "DeepSeek V3",       "desc": "DeepSeek general coding model", "badge": "popular"},
    {"cmd": "deepseek-reasoner", "name": "DeepSeek R1",       "desc": "Open-weight deep reasoning model", "badge": "popular"},
]

DEFAULT_CODEX_MODELS = [
    {"cmd": "gpt-5.6-sol",       "name": "GPT-5.6 Sol",       "desc": "OpenAI / Codex custom model", "badge": "default"},
    {"cmd": "gpt-4o",            "name": "GPT-4o",            "desc": "OpenAI flagship multimodal model", "badge": "official"},
    {"cmd": "o3-mini",           "name": "o3-mini",           "desc": "OpenAI STEM & coding reasoning model", "badge": "official"},
    {"cmd": "o1",                "name": "o1",                "desc": "OpenAI full reasoning model", "badge": "official"},
]


def _get_home():
    return os.path.expanduser("~")


def load_opencode_models():
    """
    Reads OpenCode models from local config:
    ~/.config/opencode/opencode.json or ~/.opencode/opencode.json or ./opencode.json
    """
    home = _get_home()
    candidates = [
        os.path.join(home, ".config", "opencode", "opencode.json"),
        os.path.join(home, ".opencode", "opencode.json"),
        os.path.join(os.getcwd(), "opencode.json"),
    ]

    for p in candidates:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                models = []
                providers = data.get("provider", {})
                if isinstance(providers, dict):
                    for prov_id, prov in providers.items():
                        prov_name = prov.get("name") or prov_id
                        p_models = prov.get("models", {})
                        if isinstance(p_models, dict):
                            for m_id, m_info in p_models.items():
                                if not isinstance(m_info, dict):
                                    m_info = {}
                                name = m_info.get("name") or m_id
                                details = []
                                limit = m_info.get("limit", {})
                                if isinstance(limit, dict) and limit.get("context"):
                                    ctx = limit["context"]
                                    if ctx >= 1000000:
                                        details.append(f"{ctx // 1000000}M ctx")
                                    elif ctx >= 1000:
                                        details.append(f"{ctx // 1000}k ctx")
                                if m_info.get("reasoning"):
                                    details.append("reasoning")
                                det_str = f" ({', '.join(details)})" if details else ""
                                desc = f"{name}{det_str} · {prov_name}"
                                models.append({
                                    "cmd": m_id,
                                    "label": m_id,
                                    "name": name,
                                    "desc": desc,
                                    "badge": "local config",
                                    "source": p
                                })
                if models:
                    return models
            except Exception:
                pass

    return list(DEFAULT_OPENCODE_MODELS)


def load_claude_models():
    """
    Reads Claude Code models from ~/.claude/settings.json or ~/.claude.json.
    Merges user-configured models (e.g. qwen, custom endpoints) with official Claude models.
    """
    home = _get_home()
    candidates = [
        os.path.join(home, ".claude", "settings.json"),
        os.path.join(home, ".claude.json"),
        os.path.join(os.getcwd(), ".claude", "settings.json"),
    ]

    configured_models = []
    seen = set()

    for p in candidates:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                env = data.get("env", {}) if isinstance(data, dict) else {}
                model_keys = [
                    ("ANTHROPIC_MODEL", "Primary Default"),
                    ("ANTHROPIC_DEFAULT_SONNET_MODEL", "Sonnet Override"),
                    ("ANTHROPIC_DEFAULT_OPUS_MODEL", "Opus Override"),
                    ("ANTHROPIC_DEFAULT_HAIKU_MODEL", "Haiku Override"),
                    ("CLAUDE_CODE_SUBAGENT_MODEL", "Subagent Model"),
                ]
                for env_k, label in model_keys:
                    m = env.get(env_k)
                    if m and m not in seen:
                        seen.add(m)
                        configured_models.append({
                            "cmd": m,
                            "label": m,
                            "name": m,
                            "desc": f"Configured in ~/.claude/settings.json ({label})",
                            "badge": "configured",
                            "source": p
                        })
                top_m = data.get("model") if isinstance(data, dict) else None
                if top_m and top_m not in seen:
                    seen.add(top_m)
                    configured_models.append({
                        "cmd": top_m,
                        "label": top_m,
                        "name": top_m,
                        "desc": f"Configured active model ({top_m})",
                        "badge": "configured",
                        "source": p
                    })
            except Exception:
                pass

    for m in DEFAULT_CLAUDE_MODELS:
        if m["cmd"] not in seen:
            item = dict(m)
            item["label"] = item["cmd"]
            configured_models.append(item)

    return configured_models if configured_models else list(DEFAULT_CLAUDE_MODELS)


_CODEX_MODELS_CACHE = None


def load_codex_models():
    """
    Reads Codex models from ~/.codex/config.toml and ~/.codex/auth.json.
    If a custom model_provider is configured with a base_url, queries
    the provider's /models endpoint to discover live subscription models
    (such as gpt-6-astra, gpt-5.6-terra, gpt-5.6-sol, etc.) with caching.
    """
    global _CODEX_MODELS_CACHE
    home = _get_home()
    config_toml = os.path.join(home, ".codex", "config.toml")
    auth_json = os.path.join(home, ".codex", "auth.json")

    configured_model = None
    provider_name = "custom"
    base_url = None

    if os.path.isfile(config_toml):
        try:
            with open(config_toml, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            m_mod = re.search(r'model\s*=\s*"([^"]+)"', content)
            if m_mod:
                configured_model = m_mod.group(1).strip()
            m_prov = re.search(r'model_provider\s*=\s*"([^"]+)"', content)
            if m_prov:
                provider_name = m_prov.group(1).strip()
            m_url = re.search(r'base_url\s*=\s*"([^"]+)"', content)
            if m_url:
                base_url = m_url.group(1).strip()
        except Exception:
            pass

    api_key = None
    if os.path.isfile(auth_json):
        try:
            with open(auth_json, "r", encoding="utf-8", errors="replace") as f:
                auth_data = json.load(f)
                api_key = auth_data.get("OPENAI_API_KEY") or auth_data.get("api_key")
        except Exception:
            pass

    # Query live models from custom endpoint if base_url is available
    live_models = []
    if base_url:
        if _CODEX_MODELS_CACHE is not None:
            live_models = _CODEX_MODELS_CACHE
        else:
            try:
                import requests
                url = base_url.rstrip("/") + "/models"
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                resp = requests.get(url, headers=headers, timeout=2.0)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    for item in items:
                        mid = item.get("id") if isinstance(item, dict) else (item if isinstance(item, str) else None)
                        if mid and mid not in live_models:
                            live_models.append(mid)
            except Exception:
                pass
            _CODEX_MODELS_CACHE = list(live_models)
            live_models = list(_CODEX_MODELS_CACHE)

    models = []
    seen = set()

    # 1. Active configured model from config.toml
    if configured_model:
        seen.add(configured_model)
        models.append({
            "cmd": configured_model,
            "label": configured_model,
            "name": configured_model,
            "desc": f"Configured default in ~/.codex/config.toml ({provider_name})",
            "badge": "configured",
            "source": config_toml
        })

    # 2. Live models from provider subscription (e.g. gpt-6-astra, gpt-5.6-terra, gpt-5.6-luna)
    for m in live_models:
        if m not in seen:
            seen.add(m)
            models.append({
                "cmd": m,
                "label": m,
                "name": m,
                "desc": f"Custom subscription model ({provider_name})",
                "badge": "subscription",
                "source": base_url or "api"
            })

    # 3. Fallback standard models
    for m in DEFAULT_CODEX_MODELS:
        if m["cmd"] not in seen:
            item = dict(m)
            item["label"] = item["cmd"]
            models.append(item)

    return models if models else list(DEFAULT_CODEX_MODELS)


def load_agy_models():
    """
    Returns Antigravity (Google Gemini) supported models.
    """
    models = []
    for m in DEFAULT_AGY_MODELS:
        item = dict(m)
        item["label"] = item["cmd"]
        models.append(item)
    return models


def load_aider_models():
    """
    Returns Aider supported models.
    """
    return [
        {"cmd": "claude-3-7-sonnet", "label": "claude-3-7-sonnet", "name": "Claude 3.7 Sonnet", "desc": "Anthropic hybrid reasoning & coding model", "badge": "recommended"},
        {"cmd": "deepseek-chat",     "label": "deepseek-chat",     "name": "DeepSeek V3",       "desc": "High quality economical coding model", "badge": "popular"},
        {"cmd": "gpt-4o",            "label": "gpt-4o",            "name": "GPT-4o",            "desc": "OpenAI flagship multimodal omni model", "badge": "official"},
        {"cmd": "gemini-3.8-flash",  "label": "gemini-3.8-flash",  "name": "Gemini 3.8 Flash",  "desc": "Google fast smart multimodal model", "badge": "official"},
    ]


def _load_agent_models_uncached(agent):
    if agent == "opencode":
        return load_opencode_models()
    elif agent == "claude":
        return load_claude_models()
    elif agent == "codex":
        return load_codex_models()
    elif agent == "agy":
        return load_agy_models()
    elif agent == "aider":
        return load_aider_models()
    elif agent == "goose":
        return [{"cmd": "default", "label": "default", "name": "Goose Default", "desc": "Goose agent default model configuration", "badge": "default"}]
    elif agent == "shell":
        return [{"cmd": "none", "label": "none", "name": "Native Shell", "desc": "Raw terminal shell without LLM model wrapper", "badge": "system"}]
    else:
        return load_agy_models()


def get_agent_models(agent_id, force_refresh=False):
    """
    Dynamically gets the model list for a given agent by inspecting its local config.
    agent_id: 'opencode', 'claude', 'codex', 'agy', 'aider', 'goose', 'shell'

    Results are cached for _MODELS_TTL seconds because this is called from
    keystroke-frequency UI paths; pass force_refresh=True after config edits.
    """
    agent = (agent_id or "agy").lower().strip()
    now = time.time()
    hit = _MODELS_CACHE.get(agent)
    if hit and not force_refresh and (now - hit[0]) < _MODELS_TTL:
        return hit[1]
    models = _load_agent_models_uncached(agent)
    _MODELS_CACHE[agent] = (now, models)
    return models


def get_default_model_for_agent(agent_id):
    """
    Returns the first / default model ID for the given agent.
    """
    models = get_agent_models(agent_id)
    if models:
        return models[0]["cmd"]
    return "gemini-3.8-flash"
