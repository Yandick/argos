"""
Argos (Ἄργος) CLI Interface
OpenCode & Pi aesthetic agent orchestrator.
Features:
- Dedicated Dashboard Card UI on launch and refresh.
- Interactive Arrow-Key (/theme) picker with real-time live preview.
- Interactive Arrow-Key (/server, /model, /effort) navigation menus.
- In-process execution with zero popup windows or background daemons.
- Persistent configuration with setting.json.
"""
import os
import sys
import time
import shutil
import threading
import html

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from prompt_toolkit import PromptSession
from prompt_toolkit.document import Document
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.history import FileHistory
from prompt_toolkit.output import create_output, DummyOutput
from prompt_toolkit.input import create_input, DummyInput

import warnings
try:
    from cryptography.utils import CryptographyDeprecationWarning
    warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)
except Exception:
    pass

# Ensure server-helper root is in sys.path
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from server_helper.config import Config
from server_helper.theme import get_theme, list_themes, render_swatch, get_prompt_toolkit_style
from server_helper.ui_picker import interactive_theme_picker, interactive_menu_select
from session_manager import SessionManager

console = Console()

COMMAND_REGISTRY = [
    {"cmd": "/server",    "cat": "Remote", "desc": "切换或管理远程目标服务器 (scut-gpu 等)", "usage": "[scut-gpu|add|rename|rm]"},
    {"cmd": "/files",     "cat": "Remote", "desc": "浏览工作区文件与目录树 (免耗 token)", "usage": "[路径可选]"},
    {"cmd": "/sh",        "cat": "Remote", "desc": "连接全功能交互式终端 (Ctrl+] 返回)", "usage": ""},
    {"cmd": "/model",     "cat": "Agent",  "desc": "切换活跃 LLM 模型 (gemini-3.8-flash 等)", "usage": "[gemini-3.8-flash|claude-3-7-sonnet|...]"},
    {"cmd": "/effort",    "cat": "Agent",  "desc": "调节思考推理深度 (high/med/low/off)", "usage": "[high|medium|low|off]"},
    {"cmd": "/proxy",     "cat": "System", "desc": "配置 HTTP 代理与 SSH 反向隧道 (10808/7897)", "usage": "[http://127.0.0.1:7897|off]"},
    {"cmd": "/tasks",     "cat": "Tasks",  "desc": "查看后台任务运行看板与活动状态", "usage": ""},
    {"cmd": "/switch",    "cat": "Tasks",  "desc": "在多个服务器/本地会话之间快速切换", "usage": "[会话名]"},
    {"cmd": "/broadcast", "cat": "Remote", "desc": "向全部活跃并发会话广播执行 Shell 命令", "usage": "<shell 指令>"},
    {"cmd": "/status",    "cat": "System", "desc": "查看目标环境 GPU、显存与系统负载", "usage": ""},
    {"cmd": "/theme",     "cat": "System", "desc": "切换界面配色主题 (带实时动态预览)", "usage": "[主题名]"},
    {"cmd": "/config",    "cat": "System", "desc": "查看 setting.json 配置详情", "usage": ""},
    {"cmd": "/clear",     "cat": "System", "desc": "清屏并重新绘制状态看板", "usage": ""},
    {"cmd": "/help",      "cat": "System", "desc": "查看完整指令与快捷键指南", "usage": ""},
    {"cmd": "/exit",      "cat": "System", "desc": "安全退出 Argos 并释放所有连接", "usage": ""},
]

SLASH_COMMANDS = [item["cmd"] for item in COMMAND_REGISTRY]


class ArgosSlashCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            query = text.lower()
            for item in COMMAND_REGISTRY:
                if item["cmd"].lower().startswith(query):
                    yield Completion(
                        text=item["cmd"],
                        start_position=-len(text),
                        display=f"{item['cmd']:<12}",
                        display_meta=f"[{item['cat']}] {item['desc']}"
                    )


POPULAR_MODELS = [
    {"label": "gemini-3.8-flash", "desc": "Google latest flagship default model (ultra fast & smart)"},
    {"label": "gemini-3.1-pro",   "desc": "Google top-tier deep reasoning pro model"},
    {"label": "claude-3-7-sonnet", "desc": "Anthropic latest hybrid reasoning & coding model"},
    {"label": "claude-3-5-sonnet", "desc": "Industry standard programming benchmark model"},
    {"label": "deepseek-r1",       "desc": "Open-weight deep reasoning model"},
    {"label": "deepseek-chat",     "desc": "DeepSeek V3 general coding model"},
    {"label": "gpt-4o",            "desc": "OpenAI flagship multimodal omni model"}
]


class PiSelectList:
    """
    Faithful implementation of Pi's SelectList component (from badlogic/pi-mono):
    - Maximum 5 visible items with (startIndex/total) pagination
    - Selected item marked with '  → ' and highlighted in theme primary
    - Unselected items marked with '    ' in theme dim
    - Live fuzzy/prefix filtering that persists seamlessly across Backspace
    - Up/Down arrow key navigation & Tab/Enter selection
    """
    def __init__(self, max_visible=5):
        self.max_visible = max_visible
        self.selected_index = 0

    def get_items(self, text, config, session_mgr):
        if not text.startswith("/"):
            return []
        parts = text.split(maxsplit=1)
        raw_cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        arg_lower = arg.lower()

        if " " in text:
            if raw_cmd == "/model":
                candidates = [{"cmd": m["label"], "desc": m["desc"]} for m in POPULAR_MODELS]
            elif raw_cmd in ("/effort", "/thinking"):
                candidates = [
                    {"cmd": "high", "desc": "Full reasoning capability (recommended)"},
                    {"cmd": "medium", "desc": "Balanced reasoning speed"},
                    {"cmd": "low", "desc": "Fast output, minimal overhead"},
                    {"cmd": "off", "desc": "Disable extended thinking"},
                ]
            elif raw_cmd == "/theme":
                candidates = [{"cmd": t["id"], "desc": t["desc"]} for t in list_themes()]
            elif raw_cmd in ("/server", "/connect", "/c"):
                servers = config.get_servers()
                candidates = [{"cmd": s.get("name", ""), "desc": f"{s.get('user', 'root')}@{s.get('host', '')}"} for s in servers if s.get("name")]
                candidates.extend([
                    {"cmd": "add", "desc": "Add a new target server"},
                    {"cmd": "rename", "desc": "Rename an existing server"},
                    {"cmd": "rm", "desc": "Delete an existing server"},
                ])
            elif raw_cmd in ("/close", "/stop", "/switch", "/sw"):
                candidates = [{"cmd": s.name, "desc": f"Session {s.session_id}"} for s in session_mgr.sessions.values()]
            else:
                candidates = []

            if not candidates:
                return []
            if arg:
                matches = [c for c in candidates if c["cmd"].lower().startswith(arg_lower)]
                if not matches:
                    matches = [c for c in candidates if arg_lower in c["cmd"].lower()]
                return matches
            return candidates

        matches = [c for c in COMMAND_REGISTRY if c["cmd"].lower().startswith(raw_cmd)]
        if not matches:
            matches = [c for c in COMMAND_REGISTRY if raw_cmd in c["cmd"].lower()]
        return matches

    def move_up(self, total):
        if total > 0:
            self.selected_index = (self.selected_index - 1) % total

    def move_down(self, total):
        if total > 0:
            self.selected_index = (self.selected_index + 1) % total

    def get_selected(self, text, config, session_mgr):
        items = self.get_items(text, config, session_mgr)
        if not items:
            return None
        if self.selected_index >= len(items):
            self.selected_index = 0
        return items[self.selected_index]

    def render(self, text, current_theme, config, session_mgr):
        items = self.get_items(text, config, session_mgr)
        if not items:
            return None

        if self.selected_index >= len(items):
            self.selected_index = 0

        p = current_theme.get("primary", "#89b4fa")
        txt = current_theme.get("text", "#cdd6f4")
        d = current_theme.get("dim", "#9399b2")

        total = len(items)
        half = self.max_visible // 2
        start_idx = max(0, min(self.selected_index - half, total - self.max_visible))
        end_idx = min(start_idx + self.max_visible, total)

        lines = []
        is_arg_mode = (" " in text)
        for i in range(start_idx, end_idx):
            item = items[i]
            is_sel = (i == self.selected_index)
            prefix = "  → " if is_sel else "    "
            col_w = 14 if not is_arg_mode else 20
            lbl = html.escape(f"{item['cmd']:<{col_w}}")
            desc = html.escape(item.get("desc", ""))
            if is_sel:
                lines.append(f'<style fg="{p}"><b>{prefix}{lbl}</b></style> <style fg="{txt}">{desc}</style>')
            else:
                lines.append(f'<style fg="{d}">{prefix}{lbl} {desc}</style>')

        if total > self.max_visible:
            lines.append(f'<style fg="{d}">    ({self.selected_index + 1}/{total})</style>')

        return "\n".join(lines)


class AgentCliApp:
    def __init__(self):
        self.config = Config()
        self.session_mgr = SessionManager()
        self.active_session_id = None
        self.history_file = os.path.expanduser("~/.server-helper/cli_history")
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)

        # Load active theme
        self.theme_id = self.config.get_settings().get("theme", "catppuccin")
        self.theme = get_theme(self.theme_id)

        self.select_list = PiSelectList(max_visible=5)
        self._last_sigint_time = 0.0

        self._init_prompt_session()

    def _render_bottom_toolbar(self):
        try:
            curr_text = ""
            if self.session_prompt and hasattr(self.session_prompt, "default_buffer"):
                curr_text = self.session_prompt.default_buffer.text
            if not curr_text:
                try:
                    from prompt_toolkit.application.current import get_app
                    app = get_app()
                    if app and app.current_buffer:
                        curr_text = app.current_buffer.text
                except Exception:
                    pass

            curr_text = (curr_text or "").lstrip()

            # 1. When typing slash command, render Pi SelectList inline directly beneath the prompt
            if curr_text.startswith("/"):
                rendered_list = self.select_list.render(curr_text, self.theme, self.config, self.session_mgr)
                if rendered_list:
                    return HTML(rendered_list)
                else:
                    parts = curr_text.split(maxsplit=1)
                    raw_cmd = html.escape(parts[0].lower())
                    err_col = self.theme.get("error", "#f38ba8")
                    return HTML(f'<style fg="{err_col}">未知命令: {raw_cmd} (输入 /help 查看命令列表)</style>')

            # 2. When idle/typing normal prompt, render Pi clean status footer
            session = self._get_active_session()
            p = self.theme["primary"]
            s = self.theme["success"]
            d = self.theme["dim"]
            a = self.theme["accent"]
            proxy = self.config.get_proxy()
            proxy_str = html.escape(f"proxy: {proxy}" if proxy else "direct")

            if session:
                srv = html.escape(session.name)
                rdir = session.remote_dir or "/"
                if len(rdir) > 26:
                    rdir = "..." + rdir[-23:]
                rdir = html.escape(rdir)
                agent = html.escape(session.command or "agy")
                model = html.escape(getattr(session, "model", "") or self.config.get_model(agent))
                effort = html.escape(str(self.config.get_thinking_effort()))
                return HTML(
                    f'<style fg="{s}">● {srv}</style> '
                    f'<style fg="{d}">│</style> '
                    f'<style fg="{p}">📁 {rdir}</style> '
                    f'<style fg="{d}">│</style> '
                    f'<style fg="{a}">🤖 {agent}:{model} (effort: {effort})</style> '
                    f'<style fg="{d}">│ {proxy_str} │ [Tab] /help</style>'
                )
            return HTML(
                f'<style fg="{d}">● idle │ 输入 /server 连接目标环境 │ {proxy_str} │ [Tab] /help</style>'
            )
        except Exception:
            return HTML('<style fg="#9399b2">Argos Agent Orchestrator</style>')

    def _init_prompt_session(self):
        try:
            pt_out = create_output()
        except Exception:
            pt_out = DummyOutput()

        try:
            pt_in = create_input()
        except Exception:
            pt_in = DummyInput()

        pt_style = get_prompt_toolkit_style(self.theme)

        bindings = KeyBindings()

        @bindings.add("down")
        def _(event):
            buf = event.current_buffer
            items = self.select_list.get_items(buf.text, self.config, self.session_mgr)
            if items:
                self.select_list.move_down(len(items))
            else:
                buf.auto_down()

        @bindings.add("up")
        def _(event):
            buf = event.current_buffer
            items = self.select_list.get_items(buf.text, self.config, self.session_mgr)
            if items:
                self.select_list.move_up(len(items))
            else:
                buf.auto_up()

        @bindings.add("tab")
        def _(event):
            buf = event.current_buffer
            items = self.select_list.get_items(buf.text, self.config, self.session_mgr)
            if items:
                selected = self.select_list.get_selected(buf.text, self.config, self.session_mgr)
                if selected:
                    if " " in buf.text:
                        cmd = buf.text.split(maxsplit=1)[0]
                        new_text = f"{cmd} {selected['cmd']}"
                    else:
                        new_text = f"{selected['cmd']} "
                    buf.document = Document(new_text, cursor_position=len(new_text))
                    self.select_list.selected_index = 0
            else:
                buf.insert_text("  ")

        @bindings.add("enter")
        def _(event):
            buf = event.current_buffer
            text = buf.text.strip()
            exact_cmds = [item["cmd"] for item in COMMAND_REGISTRY]
            if text.startswith("/"):
                if not (" " in text):
                    if text not in exact_cmds:
                        selected = self.select_list.get_selected(buf.text, self.config, self.session_mgr)
                        if selected:
                            new_text = f"{selected['cmd']} "
                            buf.document = Document(new_text, cursor_position=len(new_text))
                            self.select_list.selected_index = 0
                            return
                else:
                    parts = text.split(maxsplit=1)
                    cmd = parts[0].lower()
                    arg = parts[1] if len(parts) > 1 else ""
                    items = self.select_list.get_items(buf.text, self.config, self.session_mgr)
                    exact_args = [item["cmd"] for item in items]
                    if items and (self.select_list.selected_index > 0 or (arg and arg not in exact_args)):
                        selected = self.select_list.get_selected(buf.text, self.config, self.session_mgr)
                        if selected:
                            new_text = f"{cmd} {selected['cmd']}"
                            buf.document = Document(new_text, cursor_position=len(new_text))
                            self.select_list.selected_index = 0
                            return
            buf.validate_and_handle()

        @bindings.add("backspace")
        def _(event):
            buf = event.current_buffer
            buf.delete_before_cursor(count=1)
            self.select_list.selected_index = 0

        @bindings.add("delete")
        def _(event):
            buf = event.current_buffer
            buf.delete(count=1)
            self.select_list.selected_index = 0

        @bindings.add("escape")
        def _(event):
            buf = event.current_buffer
            buf.text = ""
            self.select_list.selected_index = 0

        try:
            self.session_prompt = PromptSession(
                history=FileHistory(self.history_file),
                completer=None,
                key_bindings=bindings,
                bottom_toolbar=self._render_bottom_toolbar,
                output=pt_out,
                input=pt_in,
                style=pt_style
            )
        except Exception:
            self.session_prompt = None

    def _get_user_input(self, prompt_obj):
        if self.session_prompt:
            try:
                with patch_stdout():
                    return self.session_prompt.prompt(prompt_obj).strip()
            except Exception:
                pass
        import re
        plain = getattr(prompt_obj, "value", str(prompt_obj))
        clean_text = re.sub(r"<[^>]+>", "", plain)
        clean_text = re.sub(r"\[/?.*?\]", "", clean_text)
        return input(clean_text).strip()

    def render_header(self):
        p = self.theme["primary"]
        a = self.theme["accent"]
        s = self.theme["success"]
        d = self.theme["dim"]
        txt = self.theme.get("text", "#ffffff")
        t_name = self.theme["name"]
        swatch = render_swatch(self.theme)

        session = self._get_active_session()
        if session:
            srv_info = session.server_info or {}
            srv_str = f"{session.name} ({srv_info.get('user', 'root')}@{srv_info.get('host', 'local')}:{srv_info.get('port', 22)})"
            rdir = session.remote_dir or "/"
            agent_str = f"{session.command or 'agy'} · {session.model or self.config.get_model()}"
            status_tag = f"[{s}]● running[/{s}]"
        else:
            srv_str = "Not connected (type /server to select environment)"
            rdir = "/"
            agent_str = f"{self.config.get_settings().get('default_agent', 'agy')} · {self.config.get_model()}"
            status_tag = f"[{d}]idle[/{d}]"

        effort = self.config.get_thinking_effort()
        proxy = self.config.get_proxy()
        proxy_str = f"[{s}]{proxy}[/{s}]" if proxy else f"[{d}]direct (no proxy)[/{d}]"

        card = (
            f"[{p}]  ▄▀█ █▀█ █▀▀ █▀█ █▀[/{p}]   [{txt}][bold]argos[/bold][/{txt}] [{d}]v0.3.0 · autonomous coding agent orchestrator[/{d}]\n"
            f"[{p}]  █▀█ █▀▄ █▄█ █▄█ ▄█[/{p}]   [{d}]Ἄργος Πανόπτης · multi-server remote workspace harness[/{d}]\n\n"
            f"  [{a}]Target:[/{a}]    [{txt}]{srv_str}[/{txt}] {status_tag}\n"
            f"  [{a}]Workspace:[/{a}] [{p}]{rdir}[/{p}]\n"
            f"  [{a}]Engine:[/{a}]    [{txt}]{agent_str}[/{txt}] [{d}](effort: {effort})[/{d}]\n"
            f"  [{a}]Proxy:[/{a}]     {proxy_str}\n"
            f"  [{a}]Theme:[/{a}]     [{txt}]{t_name}[/{txt}] {swatch}\n\n"
            f"[{d}]Shortcuts:[/{d}] [{a}]/server[/{a}] [{d}]target[/{d}] · [{a}]/files[/{a}] [{d}]files[/{d}] · [{a}]/sh[/{a}] [{d}]terminal[/{d}] · [{a}]/model[/{a}] [{d}]models[/{d}] · [{a}]/proxy[/{a}] [{d}]proxy[/{d}] · [{a}]/help[/{a}] [{d}]help[/{d}]"
        )
        return Panel(card, border_style=p, padding=(0, 1))

    def run(self):
        console.clear()
        console.print(self.render_header())
        console.print()

        self._last_sigint_time = 0.0

        while True:
            try:
                prompt_text = self._build_prompt()
                user_input = self._get_user_input(prompt_text)
                self._last_sigint_time = 0.0

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    parts = user_input.split(maxsplit=1)
                    cmd = parts[0].lower()
                    arg = parts[1].strip() if len(parts) > 1 else ""
                    self.handle_slash_command(cmd, arg)
                else:
                    self.handle_natural_language_prompt(user_input)

            except KeyboardInterrupt:
                now = time.time()
                if (now - self._last_sigint_time) < 2.0:
                    console.print(f"\n[{self.theme['dim']}]Argos session closed. Goodbye![/{self.theme['dim']}]")
                    for s in list(self.session_mgr.sessions.values()):
                        try:
                            s.close()
                        except Exception:
                            pass
                    sys.exit(0)
                else:
                    self._last_sigint_time = now
                    console.print(f"\n[{self.theme['warning']}]Press Ctrl+C again to exit, or type /exit[/{self.theme['warning']}]")
            except EOFError:
                console.print(f"\n[{self.theme['dim']}]Argos session closed. Goodbye![/{self.theme['dim']}]")
                for s in list(self.session_mgr.sessions.values()):
                    try:
                        s.close()
                    except Exception:
                        pass
                sys.exit(0)
            except Exception as e:
                console.print(f"[{self.theme['error']}]● Error:[/{self.theme['error']}] {e}")

    def _get_active_session(self):
        if self.active_session_id:
            s = self.session_mgr.get_session(self.active_session_id)
            if s and s.status == "running":
                return s
        running = [s for s in self.session_mgr.sessions.values() if s.status == "running"]
        if running:
            self.active_session_id = running[0].session_id
            return running[0]
        self.active_session_id = None
        return None

    def _build_prompt(self):
        session = self._get_active_session()
        p = self.theme["primary"]
        s = self.theme["success"]
        a = self.theme["accent"]
        d = self.theme["dim"]

        if session:
            srv_info = session.server_info or {}
            host = srv_info.get("name") or srv_info.get("host", "local")
            rdir = session.remote_dir or "/"
            if len(rdir) > 20:
                rdir = "..." + rdir[-17:]
            agent = session.command or "agy"
            model_info = getattr(session, "model", "") or self.config.get_model(agent)
            model_short = model_info.split("/")[-1] if model_info else ""
            model_tag = f"·{model_short}" if model_short else ""
            return HTML(
                f'<style fg="{p}">●</style> '
                f'<style fg="{s}"><b>[{host}]</b></style> '
                f'<style fg="{d}">📁 {rdir}</style> '
                f'<style fg="{a}">({agent}{model_tag})</style> '
                f'<style fg="{p}">›</style> '
            )
        return HTML(f'<style fg="{p}">●</style> <b>argos</b> <style fg="{a}">›</style> ')

    def handle_slash_command(self, cmd, arg):
        known_cmds = [
            "/exit", "/quit", "/help", "/clear", "/server", "/connect", "/c",
            "/theme", "/model", "/effort", "/thinking", "/proxy", "/files",
            "/ls", "/dir", "/tasks", "/sessions", "/switch", "/sw", "/terminal",
            "/term", "/sh", "/agent", "/status", "/broadcast", "/b", "/config",
            "/close", "/stop"
        ]
        if cmd not in known_cmds:
            candidates = [c for c in SLASH_COMMANDS if c.startswith(cmd)]
            if len(candidates) == 1:
                cmd = candidates[0]

        if cmd in ("/exit", "/quit"):
            console.print("[dim]Exiting Argos. Sessions closed.[/dim]")
            for s in list(self.session_mgr.sessions.values()):
                s.close()
            sys.exit(0)

        elif cmd == "/help":
            self.show_help()

        elif cmd == "/clear":
            console.clear()
            console.print(self.render_header())
            console.print()

        elif cmd in ("/server", "/connect", "/c"):
            self.action_servers(arg)

        elif cmd == "/theme":
            self.action_theme(arg)

        elif cmd == "/model":
            self.action_model(arg)

        elif cmd in ("/effort", "/thinking"):
            self.action_effort(arg)

        elif cmd == "/proxy":
            self.action_proxy(arg)

        elif cmd in ("/files", "/ls", "/dir"):
            self.action_list_files(arg)

        elif cmd in ("/tasks", "/sessions"):
            self.action_list_tasks()

        elif cmd in ("/switch", "/sw"):
            self.action_switch_task(arg)

        elif cmd in ("/terminal", "/term", "/sh"):
            self.action_open_terminal()

        elif cmd == "/agent":
            self.action_set_agent(arg)

        elif cmd == "/status":
            self.action_show_status()

        elif cmd in ("/broadcast", "/b"):
            self.action_broadcast(arg)

        elif cmd == "/config":
            self.action_config()

        elif cmd in ("/close", "/stop"):
            self.action_close_task(arg)

        else:
            console.print(f"[{self.theme['error']}]Unknown command: {cmd}. Type /help for available commands.[/{self.theme['error']}]")

    def show_help(self):
        p = self.theme["primary"]
        a = self.theme["accent"]
        d = self.theme["dim"]
        console.print(f"\n[{p}][bold]● Argos Commands[/bold][/{p}]")
        cmds = [
            ("/server", "Interactive server manager (↑/↓ to select, [a] add, [r] rename)"),
            ("/files, /ls", "List files and directories in remote workspace (zero tokens)"),
            ("/terminal, /sh", "Attach raw interactive terminal to active session (Ctrl+] to detach)"),
            ("/model [name]", "Select model for agent (gemini-3.8-flash, claude-3-7-sonnet...)"),
            ("/effort [level]", "Select reasoning & thinking effort (high, medium, low, off)"),
            ("/proxy [url|off]", "Configure HTTP/HTTPS proxy (e.g. http://127.0.0.1:7897 or off)"),
            ("/tasks", "List all running sessions and active context"),
            ("/switch <name|#>", "Switch active session context"),
            ("/agent <name>", "Switch agent engine (agy, claude, codex, shell)"),
            ("/status", "Show remote CPU, GPU, memory and load status"),
            ("/broadcast <cmd>", "Broadcast shell command to all sessions"),
            ("/theme [name]", "Interactive theme picker with live real-time preview (↑/↓ to preview)"),
            ("/close [name|#]", "Close a running session"),
            ("/config", "Show config file path and default settings"),
            ("/clear", "Clear screen and refresh dashboard"),
            ("/exit, /quit", "Exit Argos")
        ]
        for c, desc in cmds:
            console.print(f"  [{a}]{c:<20}[/{a}] [{d}]{desc}[/{d}]")
        console.print()

    def action_theme(self, arg=""):
        arg = (arg or "").strip().lower()
        themes = list_themes()

        # If user passed a specific theme name directly (e.g. /theme tokyo-night)
        if arg:
            target_theme = get_theme(arg)
            self.theme_id = target_theme["id"]
            self.theme = target_theme
            self.config.update_settings({"theme": self.theme_id})
            self._init_prompt_session()
            console.clear()
            console.print(self.render_header())
            console.print(f"[{self.theme['success']}]● Theme switched to [bold]{self.theme['name']}[/bold] {render_swatch(self.theme)}[/{self.theme['success']}]\n")
            return

        # Open interactive arrow-key picker with LIVE REAL-TIME PREVIEW
        chosen = interactive_theme_picker(themes, self.theme_id)
        if chosen:
            self.theme = chosen
            self.theme_id = chosen["id"]
            self.config.update_settings({"theme": self.theme_id})
            self._init_prompt_session()
            console.clear()
            console.print(self.render_header())
            console.print(f"[{self.theme['success']}]● Theme applied: [bold]{self.theme['name']}[/bold] {render_swatch(self.theme)}[/{self.theme['success']}]\n")
        else:
            console.clear()
            console.print(self.render_header())

    def action_model(self, arg=""):
        arg = (arg or "").strip()
        session = self._get_active_session()
        agent = (session.command if session else None) or self.config.get_settings().get("default_agent", "agy")
        curr_model = getattr(session, "model", "") or self.config.get_model(agent)

        if arg:
            self.config.set_model(arg, agent)
            if session:
                session.model = arg
                if agent == "agy" and session.backend:
                    session.backend.write(f"/model {arg}\n")
            console.print(f"[{self.theme['success']}]● Model set to: [bold]{arg}[/bold] (agent: {agent})[/{self.theme['success']}]\n")
            return

        # Interactive arrow-key model selection
        action, chosen_item, _ = interactive_menu_select(
            title=f"Select AI Model (Agent: {agent})",
            items=POPULAR_MODELS,
            theme=self.theme
        )
        if action == "select" and chosen_item:
            model_name = chosen_item["label"]
            self.config.set_model(model_name, agent)
            if session:
                session.model = model_name
                if agent == "agy" and session.backend:
                    session.backend.write(f"/model {model_name}\n")
            console.clear()
            console.print(self.render_header())
            console.print(f"[{self.theme['success']}]● Active model set to: [bold]{model_name}[/bold][/{self.theme['success']}]\n")
        else:
            console.clear()
            console.print(self.render_header())

    def action_effort(self, arg=""):
        arg = (arg or "").strip().lower()
        curr_effort = self.config.get_thinking_effort()

        if arg in ("low", "medium", "high", "off"):
            self.config.set_thinking_effort(arg)
            session = self._get_active_session()
            if session and session.command == "agy" and session.backend:
                session.backend.write(f"/effort {arg}\n")
            console.print(f"[{self.theme['success']}]● Reasoning effort set to: [bold]{arg}[/bold][/{self.theme['success']}]\n")
            return

        effort_items = [
            {"label": "high", "desc": "Full reasoning capability (recommended for complex tasks)"},
            {"label": "medium", "desc": "Balanced reasoning speed and thoroughness"},
            {"label": "low", "desc": "Faster output, minimal chain-of-thought overhead"},
            {"label": "off", "desc": "Disable extended thinking"}
        ]

        action, chosen_item, _ = interactive_menu_select(
            title="Select Reasoning & Thinking Effort",
            items=effort_items,
            theme=self.theme
        )
        if action == "select" and chosen_item:
            lvl = chosen_item["label"]
            self.config.set_thinking_effort(lvl)
            session = self._get_active_session()
            if session and session.command == "agy" and session.backend:
                session.backend.write(f"/effort {lvl}\n")
            console.clear()
            console.print(self.render_header())
            console.print(f"[{self.theme['success']}]● Thinking effort set to: [bold]{lvl}[/bold][/{self.theme['success']}]\n")
        else:
            console.clear()
            console.print(self.render_header())

    def action_proxy(self, arg=""):
        arg = (arg or "").strip()
        curr_proxy = self.config.get_proxy()

        if arg:
            if arg.lower() in ("off", "disable", "none", "no", "clear"):
                self.config.set_proxy("")
                console.clear()
                console.print(self.render_header())
                console.print(f"[{self.theme['warning']}]● Proxy disabled (direct connection mode).[/{self.theme['warning']}]\n")
            else:
                if not (arg.startswith("http://") or arg.startswith("https://") or arg.startswith("socks5://")):
                    arg = "http://" + arg
                new_p = self.config.set_proxy(arg)
                console.clear()
                console.print(self.render_header())
                console.print(f"[{self.theme['success']}]● Proxy configured: [bold]{new_p}[/bold][/{self.theme['success']}]\n")
            return

        p = self.theme["primary"]
        a = self.theme["accent"]
        d = self.theme["dim"]
        s = self.theme["success"]

        console.print(f"\n[{p}][bold]● Proxy Configuration[/bold][/{p}]")
        if curr_proxy:
            console.print(f"  Current proxy: [{s}]{curr_proxy}[/{s}]")
            console.print(f"  [{d}]Type new proxy URL, or 'off' to disable, or Enter to keep current.[/{d}]")
        else:
            console.print(f"  Current proxy: [{d}]direct (no proxy)[/{d}]")
            console.print(f"  [{d}]Common local proxies: http://127.0.0.1:7897 (Clash Verge), http://127.0.0.1:7890 (Clash), http://127.0.0.1:10809 (v2rayN)[/{d}]")

        try:
            val = input(f"› Proxy URL [{curr_proxy or 'http://127.0.0.1:7897'}]: ").strip()
            if not val:
                if not curr_proxy:
                    val = "http://127.0.0.1:7897"
                else:
                    return
            if val.lower() in ("off", "disable", "none", "clear"):
                self.config.set_proxy("")
                console.clear()
                console.print(self.render_header())
                console.print(f"[{self.theme['warning']}]● Proxy disabled.[/{self.theme['warning']}]\n")
            else:
                if not (val.startswith("http://") or val.startswith("https://") or val.startswith("socks5://")):
                    val = "http://" + val
                new_p = self.config.set_proxy(val)
                console.clear()
                console.print(self.render_header())
                console.print(f"[{self.theme['success']}]● Proxy saved: [bold]{new_p}[/bold] (active for all agent sessions)[/{self.theme['success']}]\n")
        except (KeyboardInterrupt, EOFError):
            return

    def action_servers(self, arg=""):
        arg_lower = (arg or "").strip().lower()

        if arg_lower == "add":
            new_srv = self._prompt_new_server()
            if new_srv:
                self._connect_to_server(new_srv)
            return

        if arg_lower.startswith("rename"):
            parts = arg.split()
            old_name = parts[1] if len(parts) > 1 else ""
            new_name = parts[2] if len(parts) > 2 else ""
            self._prompt_rename_server(old_name, new_name)
            return

        if arg_lower in ("rm", "remove", "del"):
            self._prompt_remove_server()
            return

        servers = self.config.get_servers()
        active = self._get_active_session()
        active_name = active.name if active else None

        # Build items for arrow-key interactive selection
        menu_items = []
        # [0] Local
        local_badge = "● active" if (active and active.session_type == "local_pty") else ""
        menu_items.append({
            "label": "Local Machine",
            "desc": f"native PTY · {os.getcwd()}",
            "badge": local_badge,
            "raw": {"is_local": True, "name": "local", "default_dir": os.getcwd()}
        })

        # [1..N] Remote servers
        for s in servers:
            is_cur = "● active" if (active and active_name == s.get("name")) else ""
            u = s.get("user") or s.get("username") or "root"
            h = s.get("host")
            p = s.get("port", 22)
            auth = s.get("auth_type", "password")
            menu_items.append({
                "label": s.get("name", "remote"),
                "desc": f"{u}@{h}:{p} ({auth}) · {s.get('default_dir') or '/'}",
                "badge": is_cur,
                "raw": s
            })

        extra_keys = {
            "a": ("add server", None),
            "r": ("rename server", None),
            "d": ("delete server", None)
        }

        action, chosen_item, _ = interactive_menu_select(
            title="Available Environments (↑/↓ to navigate, Enter to connect, [a] add, [r] rename, [d] delete)",
            items=menu_items,
            extra_shortcuts=extra_keys,
            theme=self.theme
        )

        console.clear()
        console.print(self.render_header())

        if action == "select" and chosen_item:
            self._connect_to_server(chosen_item["raw"])
        elif action == "add server":
            new_srv = self._prompt_new_server()
            if new_srv:
                self._connect_to_server(new_srv)
        elif action == "rename server":
            if chosen_item and not chosen_item["raw"].get("is_local"):
                self._prompt_rename_server(chosen_item["raw"].get("name"))
            else:
                self._prompt_rename_server()
        elif action == "delete server":
            if chosen_item and not chosen_item["raw"].get("is_local"):
                srv_name = chosen_item["raw"].get("name")
                self.config.remove_server(srv_name)
                console.print(f"[{self.theme['success']}]● Server '{srv_name}' deleted.[/{self.theme['success']}]\n")
            else:
                self._prompt_remove_server()

    def _prompt_rename_server(self, old_name="", new_name=""):
        servers = self.config.get_servers()
        if not servers:
            console.print("[dim]No servers configured.[/dim]")
            return

        if not old_name:
            console.print(f"\n[{self.theme['primary']}][bold]● Rename Server[/bold][/{self.theme['primary']}]")
            for idx, s in enumerate(servers, 1):
                console.print(f"  [{idx}] {s.get('name')} [dim]({s.get('user')}@{s.get('host')})[/dim]")
            try:
                pick = input("› Select server to rename (# or name): ").strip()
                if not pick:
                    return
                try:
                    idx = int(pick) - 1
                    if 0 <= idx < len(servers):
                        old_name = servers[idx].get("name")
                except ValueError:
                    old_name = pick
            except (KeyboardInterrupt, EOFError):
                return

        if not new_name:
            try:
                new_name = input(f"› New name for '{old_name}': ").strip()
            except (KeyboardInterrupt, EOFError):
                return

        if not new_name:
            return

        ok, res = self.config.rename_server(old_name, new_name)
        if ok:
            console.print(f"[{self.theme['success']}]● Server renamed to: [bold]{res}[/bold][/{self.theme['success']}]\n")
        else:
            console.print(f"[{self.theme['error']}]● Rename failed: {res}[/{self.theme['error']}]\n")

    def _connect_to_server(self, server_info):
        is_local = server_info.get("is_local", False)

        if is_local:
            work_dir = server_info.get("default_dir") or os.getcwd()
        else:
            work_dir = server_info.get("default_dir") or "/data/workspace"

        # Use configured default agent without tedious questionnaire
        agent_type = self.config.get_settings().get("default_agent", "agy")
        task_name = server_info.get("name") or (os.path.basename(work_dir.rstrip("/\\")) or "task")

        # Build startup command with model and effort flags
        startup_cmd = ""
        model_name = self.config.get_model(agent_type)
        effort_level = self.config.get_thinking_effort()

        if agent_type == "agy":
            startup_cmd = f"agy --model {model_name} --effort {effort_level}"
        elif agent_type == "claude":
            startup_cmd = f"claude --model {model_name}" if model_name else "claude"
        elif agent_type == "codex":
            startup_cmd = ""
        elif agent_type == "shell":
            startup_cmd = ""

        cols, rows = shutil.get_terminal_size((120, 30))

        if is_local:
            console.print(f"● Starting local task [{task_name}] ({agent_type})...")
            session, err = self.session_mgr.create_session(
                session_type="local_pty",
                name=task_name,
                cwd=work_dir,
                startup_cmd=startup_cmd,
                cols=cols,
                rows=rows
            )
        else:
            srv_user = server_info.get("user") or server_info.get("username") or "root"
            srv_host = server_info.get("host")
            srv_port = server_info.get("port", 22)
            console.print(f"● Connecting to {srv_user}@{srv_host}:{srv_port}...")
            session, err = self.session_mgr.create_session(
                session_type="remote_ssh",
                name=task_name,
                server_info=server_info,
                remote_dir=work_dir,
                startup_cmd=startup_cmd,
                cols=cols,
                rows=rows
            )

        if err or not session:
            console.print(f"[{self.theme['error']}][bold]● Connection failed:[/bold] {err or 'Unknown error'}[/{self.theme['error']}]\n")
            return

        session.model = model_name
        self.active_session_id = session.session_id

        p = self.theme["primary"]
        s = self.theme["success"]
        a = self.theme["accent"]
        d = self.theme["dim"]
        txt = self.theme.get("text", "#ffffff")

        # Automatically fetch workspace files snapshot so user sees their project layout
        files_line = ""
        try:
            if session.session_type == "remote_ssh" and hasattr(session.backend, "list_sftp_files"):
                entries = session.backend.list_sftp_files(work_dir)
            else:
                entries = [{"name": f, "is_dir": os.path.isdir(os.path.join(work_dir, f))} for f in os.listdir(work_dir)]

            if entries and not (len(entries) == 1 and "error" in entries[0]):
                dirs = [e["name"] + "/" for e in entries if e.get("is_dir")][:5]
                files = [e["name"] for e in entries if not e.get("is_dir")][:6]
                d_str = " ".join(dirs)
                f_str = " ".join(files)
                files_line = f"  [{a}]Workspace Files:[/{a}] [{txt}]{d_str} {f_str}[/{txt}] [{d}]({len(entries)} items · type /files to view all)[/{d}]\n"
        except Exception:
            pass

        console.clear()
        console.print(self.render_header())

        srv_host = server_info.get("host", "local")
        srv_user = server_info.get("user") or server_info.get("username") or "root"
        srv_str = f"{srv_user}@{srv_host}:{server_info.get('port', 22)}" if not is_local else "local machine"
        proxy_info = "127.0.0.1:[10808/7897] ➔ 7897 (SSH tunnel active)" if self.config.get_proxy() else "direct"

        banner = (
            f"[{s}][bold]● Connected: {task_name}[/bold][/{s}] [{d}]({session.session_type})[/{d}]\n\n"
            f"  [{a}]Target:[/{a}]          [{txt}]{task_name}[/{txt}] [{d}]({srv_str})[/dim]\n"
            f"  [{a}]Directory:[/{a}]       [{p}]{work_dir}[/{p}]\n"
            f"{files_line}"
            f"  [{a}]Engine:[/{a}]          [{txt}]{agent_type}[/{txt}] [{d}]({model_name}, effort: {effort_level})[/dim]\n"
            f"  [{a}]Proxy Tunnel:[/{a}]    [{s}]{proxy_info}[/{s}]\n\n"
            f"[{d}]Quick Actions: Type prompt to dispatch · [/][{a}]/files[/] [{d}]list files · [/][{a}]/sh[/] [{d}]terminal · [/][{a}]/status[/] [{d}]GPU status[/{d}]"
        )
        console.print(Panel(banner, border_style=s, padding=(0, 1)))
        console.print()

    def _prompt_new_server(self):
        console.print(f"\n[{self.theme['primary']}][bold]● Add New Remote Server[/bold][/{self.theme['primary']}]")
        try:
            name = input("› Server name (e.g. scut-gpu): ").strip() or "remote-server"
            host = input("› Host / IP: ").strip()
            if not host:
                console.print(f"[{self.theme['error']}]Host IP cannot be empty.[/{self.theme['error']}]")
                return None
            port_in = input("› Port [22]: ").strip() or "22"
            port = int(port_in) if port_in.isdigit() else 22
            user = input("› Username [root]: ").strip() or "root"
            auth = input("› Auth type (password/key) [password]: ").strip().lower() or "password"

            password = ""
            key_path = ""
            if auth in ("key", "k"):
                auth_type = "key"
                key_path = input("› Private key path [~/.ssh/id_rsa]: ").strip() or "~/.ssh/id_rsa"
            else:
                auth_type = "password"
                password = input("› Password: ").strip()

            default_dir = input("› Default directory [/data/workspace]: ").strip() or "/data/workspace"

            res = self.config.add_or_update_server(name, host, port, user, auth_type, key_path, password, default_dir)
            try:
                g_cfg = os.path.expanduser("~/.server-helper/setting.json")
                if os.path.isfile(g_cfg):
                    import json
                    with open(g_cfg, "w", encoding="utf-8") as f:
                        json.dump(self.config.data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
            return res
        except (KeyboardInterrupt, EOFError):
            console.print("[yellow]Cancelled.[/yellow]")
            return None

    def _prompt_remove_server(self):
        servers = self.config.get_servers()
        if not servers:
            console.print("[dim]No servers to remove.[/dim]")
            return
        console.print(f"\n[{self.theme['error']}][bold]● Delete Server[/bold][/{self.theme['error']}]")
        for idx, s in enumerate(servers, 1):
            console.print(f"  [{idx}] {s.get('name')} ({s.get('user')}@{s.get('host')})")
        try:
            choice = input("› Select number or name to delete (q to cancel): ").strip()
            if choice.lower() in ("q", "quit", ""):
                return
            target = None
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(servers):
                    target = servers[idx]
            except ValueError:
                target = self.config.get_server(choice)

            if target:
                self.config.remove_server(target.get("name"))
                console.print(f"[{self.theme['success']}]● Server '{target.get('name')}' removed.[/{self.theme['success']}]")
        except (KeyboardInterrupt, EOFError):
            pass

    def action_list_files(self, arg=""):
        session = self._get_active_session()
        if not session:
            console.print(f"[{self.theme['warning']}]● No active session. Type /server to connect.[/{self.theme['warning']}]")
            return

        target_dir = arg.strip() or session.remote_dir or "/"
        console.print(f"● Workspace [{self.theme['primary']}]{target_dir}[/{self.theme['primary']}] ({session.name}):")

        entries = []
        if session.session_type == "remote_ssh" and hasattr(session.backend, "list_sftp_files"):
            entries = session.backend.list_sftp_files(target_dir)
        else:
            try:
                local_dir = target_dir if os.path.isabs(target_dir) else os.path.join(os.getcwd(), target_dir)
                for fname in os.listdir(local_dir):
                    fpath = os.path.join(local_dir, fname)
                    is_d = os.path.isdir(fpath)
                    sz = os.path.getsize(fpath) if not is_d else 0
                    mtime = os.path.getmtime(fpath)
                    entries.append({"name": fname, "is_dir": is_d, "size": sz, "mtime": mtime})
                entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            except Exception as e:
                entries = [{"error": str(e)}]

        if not entries or (len(entries) == 1 and "error" in entries[0]):
            err = entries[0].get("error", "Empty directory or cannot access") if entries else "Empty"
            console.print(f"[{self.theme['dim']}]  ({err})[/{self.theme['dim']}]\n")
            return

        p = self.theme["primary"]
        table = Table(border_style=p, show_header=True, header_style=f"{p} bold")
        table.add_column("Type", width=6, style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Size", justify="right", style="green")

        dirs_cnt = sum(1 for e in entries if e.get("is_dir"))
        files_cnt = len(entries) - dirs_cnt

        for e in entries[:40]:
            if e.get("is_dir"):
                table.add_row("DIR", f"[bold cyan]{e['name']}/[/bold cyan]", "-")
            else:
                sz = e.get("size", 0)
                if sz > 1024 * 1024:
                    sz_str = f"{round(sz / (1024*1024), 1)} MB"
                elif sz > 1024:
                    sz_str = f"{round(sz / 1024, 1)} KB"
                else:
                    sz_str = f"{sz} B"
                table.add_row("FILE", e['name'], sz_str)

        console.print(table)
        console.print(f"[{self.theme['dim']}]  Summary: {dirs_cnt} directories, {files_cnt} files (showing up to 40)[/{self.theme['dim']}]\n")

    def action_list_tasks(self):
        sessions = list(self.session_mgr.sessions.values())
        if not sessions:
            console.print(f"[{self.theme['dim']}]● No active sessions. Type [{self.theme['accent']}][bold]/server[/bold][/{self.theme['accent']}] to connect.[/{self.theme['dim']}]")
            return

        p = self.theme["primary"]
        a = self.theme["accent"]
        d = self.theme["dim"]
        console.print(f"\n[{p}][bold]● Active Sessions[/bold][/{p}]\n")
        active = self._get_active_session()
        for idx, s in enumerate(sessions, 1):
            is_active = f" [{self.theme['success']}][bold]● current[/bold][/{self.theme['success']}]" if (active and s.session_id == active.session_id) else ""
            target = s.server_info.get("name") if s.server_info else "local"
            rdir = s.remote_dir or "/"
            agent = s.command or "agent"
            model_info = getattr(s, "model", "")
            agent_str = f"{agent}({model_info})" if model_info else agent
            console.print(f"  [{idx}] [bold]{s.name:<18}[/bold] [{d}]{target:<14}[/{d}] [{p}]{rdir:<20}[/{p}] [{a}]{agent_str:<18}[/{a}] [{self.theme['success']}]{s.status}[/{self.theme['success']}]{is_active}")
        console.print(f"\n  [{d}]Type [{a}]/switch <name|#>[/{a}] to switch, [{a}]/sh[/{a}] to attach terminal[/{d}]\n")

    def action_switch_task(self, name):
        sessions = list(self.session_mgr.sessions.values())
        if not sessions:
            console.print("[dim]No active sessions.[/dim]")
            return

        if not name:
            self.action_list_tasks()
            try:
                name = input("› Switch to (# or name): ").strip()
            except (KeyboardInterrupt, EOFError):
                return

        target = None
        try:
            idx = int(name) - 1
            if 0 <= idx < len(sessions):
                target = sessions[idx]
        except ValueError:
            for s in sessions:
                if s.name == name or s.session_id == name:
                    target = s
                    break

        if target:
            self.active_session_id = target.session_id
            console.print(f"[{self.theme['success']}]● Switched to session: [bold]{target.name}[/bold][/{self.theme['success']}]")
        else:
            console.print(f"[{self.theme['error']}]● Session '{name}' not found.[/{self.theme['error']}]")

    def action_open_terminal(self):
        session = self._get_active_session()
        if not session or not session.backend:
            console.print(f"[{self.theme['warning']}]● No active session. Type /server to connect first.[/{self.theme['warning']}]")
            return

        a = self.theme["accent"]
        d = self.theme["dim"]
        console.print(f"\n● [bold]Attached to {session.name}[/bold] ({session.command or 'shell'})")
        console.print(f"[{d}]Press [bold yellow]Ctrl + ][/bold yellow] to detach and return to Argos prompt[/{d}]\n")

        # Replay last lines of scrollback if available
        if session.scrollback:
            recent = session.scrollback[-4000:]
            sys.stdout.write(recent)
            sys.stdout.flush()

        stop_event = threading.Event()

        def on_term_output(text):
            if not stop_event.is_set():
                sys.stdout.write(text)
                sys.stdout.flush()

        session.output_listeners.add(on_term_output)

        try:
            if sys.platform == "win32":
                import msvcrt
                # Drain residual input buffer
                while msvcrt.kbhit():
                    try:
                        msvcrt.getch()
                    except Exception:
                        break

                while not stop_event.is_set() and session.status == "running":
                    if msvcrt.kbhit():
                        ch = msvcrt.getch()
                        # Ctrl+] (ASCII 29 / 0x1d) detaches
                        if ch == b'\x1d':
                            break
                        # Handle Windows special / arrow keys (0x00 or 0xe0 prefix)
                        if ch in (b'\x00', b'\xe0'):
                            ch2 = msvcrt.getch() if msvcrt.kbhit() else b''
                            arrow_map = {
                                b'H': b'\x1b[A',  # Up
                                b'P': b'\x1b[B',  # Down
                                b'M': b'\x1b[C',  # Right
                                b'K': b'\x1b[D',  # Left
                                b'G': b'\x1b[H',  # Home
                                b'O': b'\x1b[F',  # End
                                b'S': b'\x1b[3~', # Delete
                            }
                            code = arrow_map.get(ch2, ch + ch2)
                            session.backend.write(code)
                        else:
                            try:
                                session.backend.write(ch.decode("latin1"))
                            except Exception:
                                pass
                    else:
                        time.sleep(0.005)
            else:
                import select
                while not stop_event.is_set() and session.status == "running":
                    r, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if r:
                        ch = sys.stdin.read(1)
                        if ch == '\x1d':
                            break
                        session.backend.write(ch)

        except Exception as e:
            console.print(f"\n[{self.theme['error']}]Terminal error: {e}[/{self.theme['error']}]")
        finally:
            stop_event.set()
            if on_term_output in session.output_listeners:
                session.output_listeners.remove(on_term_output)
            console.print("\n[dim]● [Detached from session][/dim]\n")

    def action_set_agent(self, agent_name):
        if not agent_name:
            console.print("[dim]Supported agents: agy, claude, codex, shell[/dim]")
            return
        session = self._get_active_session()
        if session:
            session.command = agent_name
            console.print(f"[{self.theme['success']}]● Active session [{session.name}] agent set to: {agent_name}[/{self.theme['success']}]")
        else:
            self.config.update_settings({"default_agent": agent_name})
            console.print(f"[{self.theme['success']}]● Default agent set to: {agent_name}[/{self.theme['success']}]")

    def action_show_status(self):
        session = self._get_active_session()
        if not session:
            console.print(f"[{self.theme['warning']}]● No active session.[/{self.theme['warning']}]")
            return

        console.print(f"● Inspecting environment for [{self.theme['primary']}][bold]{session.name}[/bold][/{self.theme['primary']}]...")

        if session.session_type == "remote_ssh" and hasattr(session.backend, "exec_command"):
            check_cmd = (
                "echo '=== GPU ===' && (nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader 2>/dev/null || echo '(No NVIDIA GPU)'); "
                "echo '=== Memory ===' && free -h 2>/dev/null; "
                "echo '=== Load ===' && uptime"
            )
            code, out, err = session.backend.exec_command(check_cmd, cwd=session.remote_dir, timeout=8)
            console.print("\n" + out.strip() + "\n")
        else:
            import psutil
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            console.print(f"  CPU Usage: {cpu}%")
            console.print(f"  RAM Usage: {mem.percent}% ({round(mem.used/(1024**3), 1)}GB / {round(mem.total/(1024**3), 1)}GB)\n")

    def action_broadcast(self, cmd):
        if not cmd:
            try:
                cmd = input("› Command to broadcast: ").strip()
            except (KeyboardInterrupt, EOFError):
                return
        if not cmd:
            return
        sessions = [s for s in self.session_mgr.sessions.values() if s.status == "running"]
        for s in sessions:
            s.backend.write(cmd + "\n")
        console.print(f"[{self.theme['success']}]● Broadcasted to {len(sessions)} active session(s):[/{self.theme['success']}] {cmd}")

    def action_close_task(self, name):
        session = self._get_active_session()
        target_id = None
        target_name = ""
        if not name and session:
            target_id = session.session_id
            target_name = session.name
        elif name:
            for s in self.session_mgr.sessions.values():
                if s.name == name or s.session_id == name:
                    target_id = s.session_id
                    target_name = s.name
                    break

        if target_id:
            self.session_mgr.close_session(target_id)
            if self.active_session_id == target_id:
                self.active_session_id = None
            console.print(f"[{self.theme['warning']}]● Session [{target_name}] closed.[/{self.theme['warning']}]")
        else:
            console.print(f"[{self.theme['error']}]● Session not found: {name}[/{self.theme['error']}]")

    def action_config(self):
        s = self.config.get_settings()
        p = self.theme["primary"]
        d = self.theme["dim"]
        console.print(f"\n[{p}][bold]● Argos Configuration[/bold][/{p}]")
        console.print(f"  Config file:     {self.config.config_path}")
        console.print(f"  Current theme:   {self.theme['name']} ({self.theme_id})")
        console.print(f"  Default agent:   {s.get('default_agent', 'agy')}")
        console.print(f"  Default model:   {s.get('default_model', 'gemini-3.8-flash')}")
        console.print(f"  Thinking effort: {s.get('thinking_effort', 'high')}")
        console.print(f"  Proxy:           {self.config.get_proxy() or 'None (direct)'}")
        console.print(f"  Servers saved:   {len(self.config.get_servers())}\n")

    def handle_natural_language_prompt(self, prompt):
        session = self._get_active_session()
        if not session:
            console.print(f"[{self.theme['dim']}]● No environment connected. Type [{self.theme['accent']}][bold]/server[/bold][/{self.theme['accent']}] to connect to a local or remote server.[/{self.theme['dim']}]")
            return

        agent = (session.command or "agy").lower()
        a = self.theme["accent"]
        d = self.theme["dim"]

        console.print(f"[{a}]● Dispatched to {agent} in [{session.name}]...[/{a}] [{d}](Type /sh to interact directly)[/{d}]")
        session.backend.write(prompt + "\n")

        # Stream output directly to user for a few seconds so user sees response live
        printed = [0]
        def on_stream_output(chunk):
            sys.stdout.write(chunk)
            sys.stdout.flush()
            printed[0] += len(chunk)

        session.output_listeners.add(on_stream_output)
        try:
            t0 = time.time()
            last_change = time.time()
            last_cnt = 0
            while time.time() - t0 < 6:
                time.sleep(0.08)
                if printed[0] != last_cnt:
                    last_cnt = printed[0]
                    last_change = time.time()
                elif printed[0] > 0 and (time.time() - last_change > 1.2):
                    break
        finally:
            if on_stream_output in session.output_listeners:
                session.output_listeners.remove(on_stream_output)
            console.print()


def main():
    app = AgentCliApp()
    app.run()


if __name__ == "__main__":
    main()
