"""
Lightweight i18n for the ServerHelper CLI.

Provides an English / 中文 dictionary for user-facing interface text and a
`t(key, **vars)` resolver. The active language is read from / persisted to the
`settings.language` key in setting.json (default: "en"). Only UI chrome is
translated here — it never changes the language the AI agent replies in.
"""

SUPPORTED_LANGS = ("en", "zh")
DEFAULT_LANG = "en"

_STRINGS = {
    "en": {
        # Command registry (short descriptions shown in completion + /help)
        "cmd.server": "Switch or manage remote target servers",
        "cmd.cd": "Change or browse workspace directory (interactive or path)",
        "cmd.files": "Browse workspace files & directory tree (zero tokens)",
        "cmd.sh": "Attach the full interactive terminal (Ctrl+] to return)",
        "cmd.agent": "Detect & switch local AI agent engine (agy, claude, opencode...)",
        "cmd.model": "Switch the active LLM model",
        "cmd.effort": "Adjust reasoning effort (high/med/low/off)",
        "cmd.proxy": "Configure HTTP proxy & SSH reverse tunnel",
        "cmd.tasks": "View background task dashboard & activity",
        "cmd.switch": "Quickly switch between server/local sessions",
        "cmd.broadcast": "Broadcast a shell command to all active sessions",
        "cmd.status": "Show target GPU, memory & system load",
        "cmd.theme": "Switch UI color theme (with live preview)",
        "cmd.config": "Show setting.json configuration details",
        "cmd.clear": "Clear screen and redraw the dashboard",
        "cmd.help": "Show full command & shortcut guide",
        "cmd.exit": "Safely exit Argos and release all connections",
        "cmd.lang": "Switch interface language (en/zh)",

        # Detailed help list
        "help.title": "Argos Commands",
        "help.server": "Interactive server manager (↑/↓ to select, [a] add, [r] rename)",
        "help.cd": "Change workspace directory (interactive browser or /cd <path>)",
        "help.files": "List files and directories in remote workspace (zero tokens)",
        "help.terminal": "Attach raw interactive terminal to active session (Ctrl+] to detach)",
        "help.model": "Select model for agent (gemini-3.8-flash, claude-3-7-sonnet...)",
        "help.effort": "Select reasoning & thinking effort (high, medium, low, off)",
        "help.proxy": "Configure HTTP/HTTPS proxy (e.g. http://127.0.0.1:7897 or off)",
        "help.tasks": "List all running sessions and active context",
        "help.switch": "Switch active session context",
        "help.agent": "Switch agent engine (agy, claude, codex, shell)",
        "help.status": "Show remote CPU, GPU, memory and load status",
        "help.broadcast": "Broadcast shell command to all sessions",
        "help.theme": "Interactive theme picker with live real-time preview",
        "help.close": "Close a running session",
        "help.config": "Show config file path and default settings",
        "help.clear": "Clear screen and refresh dashboard",
        "help.exit": "Exit Argos",
        "help.lang": "Switch interface language (en / zh)",

        # Header / banner
        "banner.tagline": "autonomous coding agent orchestrator",
        "banner.tagline2": "multi-server remote workspace harness",
        "banner.target": "Target",
        "banner.workspace": "Workspace",
        "banner.engine": "Engine",
        "banner.proxy": "Proxy",
        "banner.theme": "Theme",
        "banner.shortcuts": "Shortcuts",
        "banner.notConnected": "Not connected (type /server to select environment)",
        "banner.directNoProxy": "direct (no proxy)",
        "banner.running": "running",
        "banner.idle": "idle",
        "banner.effort": "effort",
        "sc.target": "target",
        "sc.agent": "agent",
        "sc.files": "files",
        "sc.terminal": "terminal",
        "sc.models": "models",
        "sc.proxy": "proxy",
        "sc.help": "help",

        # Agent command
        "agent.title": "Select AI Agent Engine",
        "agent.switched": "Agent engine switched to: {name}",
        "agent.notFound": "Agent '{name}' was not found in system PATH. Please install it first.",
        "agent.active": "active",
        "agent.installed": "installed",

        # Workspace directory command
        "cd.title": "Select Workspace Directory",
        "cd.switched": "Workspace changed to: {path}",
        "cd.notFound": "Directory not found: {path}",

        # Bottom toolbar
        "toolbar.unknownCmd": "Unknown command: {cmd} (type /help for the command list)",
        "toolbar.idleHint": "idle │ type /server to connect a target │ {proxy} │ [Tab] /help",
        "toolbar.fallback": "Argos Agent Orchestrator",

        # Run loop
        "run.goodbye": "Argos session closed. Goodbye!",
        "run.ctrlCAgain": "Press Ctrl+C again to exit, or type /exit",
        "run.error": "Error",
        "run.exiting": "Exiting Argos. Sessions closed.",

        # Language command
        "lang.switched": "Interface language: English",
        "lang.invalid": "Usage: /lang [en|zh]",
    },

    "zh": {
        "cmd.server": "切换或管理远程目标服务器 (scut-gpu 等)",
        "cmd.cd": "切换或浏览工作区目录 (交互式浏览器或直接路径)",
        "cmd.files": "浏览工作区文件与目录树 (免耗 token)",
        "cmd.sh": "连接全功能交互式终端 (Ctrl+] 返回)",
        "cmd.agent": "自动探测并切换本地已安装的 AI Agent (agy, claude, opencode...)",
        "cmd.model": "切换活跃 LLM 模型 (gemini-3.8-flash 等)",
        "cmd.effort": "调节思考推理深度 (high/med/low/off)",
        "cmd.proxy": "配置 HTTP 代理与 SSH 反向隧道 (10808/7897)",
        "cmd.tasks": "查看后台任务运行看板与活动状态",
        "cmd.switch": "在多个服务器/本地会话之间快速切换",
        "cmd.broadcast": "向全部活跃并发会话广播执行 Shell 命令",
        "cmd.status": "查看目标环境 GPU、显存与系统负载",
        "cmd.theme": "切换界面配色主题 (带实时动态预览)",
        "cmd.config": "查看 setting.json 配置详情",
        "cmd.clear": "清屏并重新绘制状态看板",
        "cmd.help": "查看完整指令与快捷键指南",
        "cmd.exit": "安全退出 Argos 并释放所有连接",
        "cmd.lang": "切换界面语言 (en/zh)",

        "help.title": "Argos 指令列表",
        "help.server": "交互式服务器管理 (↑/↓ 选择, [a] 添加, [r] 重命名)",
        "help.cd": "切换工作区目录 (交互式浏览器或 /cd <路径>)",
        "help.files": "列出远程工作区文件与目录 (免耗 token)",
        "help.terminal": "挂接原生交互终端到当前会话 (Ctrl+] 脱离)",
        "help.model": "为 Agent 选择模型 (gemini-3.8-flash, claude-3-7-sonnet...)",
        "help.effort": "选择推理思考深度 (high, medium, low, off)",
        "help.proxy": "配置 HTTP/HTTPS 代理 (如 http://127.0.0.1:7897 或 off)",
        "help.tasks": "列出所有运行中的会话与当前上下文",
        "help.switch": "切换当前活跃会话上下文",
        "help.agent": "切换 Agent 引擎 (agy, claude, codex, shell)",
        "help.status": "查看远程 CPU、GPU、内存与负载状态",
        "help.broadcast": "向所有会话广播执行 Shell 命令",
        "help.theme": "交互式主题选择器 (带实时动态预览)",
        "help.close": "关闭运行中的会话",
        "help.config": "查看配置文件路径与默认设置",
        "help.clear": "清屏并刷新看板",
        "help.exit": "退出 Argos",
        "help.lang": "切换界面语言 (en / zh)",

        "banner.tagline": "自主编码 Agent 编排器",
        "banner.tagline2": "多服务器远程工作区框架",
        "banner.target": "目标",
        "banner.workspace": "工作区",
        "banner.engine": "引擎",
        "banner.proxy": "代理",
        "banner.theme": "主题",
        "banner.shortcuts": "快捷键",
        "banner.notConnected": "未连接 (输入 /server 选择目标环境)",
        "banner.directNoProxy": "直连 (无代理)",
        "banner.running": "运行中",
        "banner.idle": "空闲",
        "banner.effort": "深度",
        "sc.target": "目标",
        "sc.agent": "引擎",
        "sc.files": "文件",
        "sc.terminal": "终端",
        "sc.models": "模型",
        "sc.proxy": "代理",
        "sc.help": "帮助",

        # Agent command
        "agent.title": "选择本地 AI Agent 引擎",
        "agent.switched": "已将 Agent 引擎切换为: {name}",
        "agent.notFound": "未在系统 PATH 中检测到 Agent '{name}'，请先安装。",
        "agent.active": "当前生效",
        "agent.installed": "已安装",

        # Workspace directory command
        "cd.title": "选择工作区目录",
        "cd.switched": "工作目录已切换至: {path}",
        "cd.notFound": "目录不存在或无法访问: {path}",

        "toolbar.unknownCmd": "未知命令: {cmd} (输入 /help 查看命令列表)",
        "toolbar.idleHint": "空闲 │ 输入 /server 连接目标环境 │ {proxy} │ [Tab] /help",
        "toolbar.fallback": "Argos Agent 编排器",

        "run.goodbye": "Argos 会话已关闭，再见！",
        "run.ctrlCAgain": "再按一次 Ctrl+C 退出，或输入 /exit",
        "run.error": "错误",
        "run.exiting": "正在退出 Argos，会话已关闭。",

        "lang.switched": "界面语言: 中文",
        "lang.invalid": "用法: /lang [en|zh]",
    },
}

# Active language (module-level singleton). Default English.
_lang = DEFAULT_LANG


def get_lang():
    return _lang


def set_lang(lang):
    """Set the active language. Returns the normalized language code."""
    global _lang
    lang = (lang or "").strip().lower()
    if lang in ("english", "en", "en-us", "en_us"):
        lang = "en"
    elif lang in ("chinese", "zh", "cn", "zh-cn", "zh_cn", "中文", "中"):
        lang = "zh"
    if lang not in SUPPORTED_LANGS:
        lang = DEFAULT_LANG
    _lang = lang
    return _lang


def init_lang(config=None):
    """Initialize the active language from a Config object (settings.language)."""
    lang = DEFAULT_LANG
    try:
        if config is not None:
            lang = config.get_settings().get("language") or DEFAULT_LANG
    except Exception:
        lang = DEFAULT_LANG
    return set_lang(lang)


def t(key, **vars):
    """Translate a key into the active language, with optional {var} substitution."""
    table = _STRINGS.get(_lang, _STRINGS[DEFAULT_LANG])
    s = table.get(key)
    if s is None:
        # Fall back to the other language, then the key itself.
        other = "zh" if _lang == "en" else "en"
        s = _STRINGS[other].get(key, key)
    if vars and isinstance(s, str):
        try:
            s = s.format(**vars)
        except Exception:
            pass
    return s
