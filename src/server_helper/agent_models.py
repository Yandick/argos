"""
Argos Dynamic Agent Model Loader
Inspects local configuration files of installed coding agents
(OpenCode, Claude Code, Codex, Antigravity, Aider) and dynamically
discovers their configured and available AI models.
"""
import os
import json
import re

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


def load_codex_models():
    """
    Reads Codex models from ~/.codex/config.toml or ~/.codex/config.json.
    """
    home = _get_home()
    config_toml = os.path.join(home, ".codex", "config.toml")
    models = []
    seen = set()

    if os.path.isfile(config_toml):
        try:
            with open(config_toml, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            m = re.search(r'model\s*=\s*"([^"]+)"', content)
            if m:
                model_name = m.group(1).strip()
                seen.add(model_name)
                p_match = re.search(r'model_provider\s*=\s*"([^"]+)"', content)
                prov = p_match.group(1) if p_match else "config.toml"
                models.append({
                    "cmd": model_name,
                    "label": model_name,
                    "name": model_name,
                    "desc": f"Configured in ~/.codex/config.toml (provider: {prov})",
                    "badge": "configured",
                    "source": config_toml
                })
        except Exception:
            pass

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


def get_agent_models(agent_id):
    """
    Dynamically gets the model list for a given agent by inspecting its local config.
    agent_id: 'opencode', 'claude', 'codex', 'agy', 'aider', 'goose', 'shell'
    """
    agent = (agent_id or "agy").lower().strip()
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
    elif agent == "shell":
        return [{"cmd": "none", "label": "none", "name": "Native Shell", "desc": "Raw terminal shell without LLM model wrapper", "badge": "system"}]
    else:
        return load_agy_models()


def get_default_model_for_agent(agent_id):
    """
    Returns the first / default model ID for the given agent.
    """
    models = get_agent_models(agent_id)
    if models:
        return models[0]["cmd"]
    return "gemini-3.8-flash"
