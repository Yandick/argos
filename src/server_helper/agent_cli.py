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
from rich.markup import escape as rich_escape

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
from server_helper.agent_detector import (
    detect_local_agents,
    get_installed_agents,
    get_agent_info,
    is_agent_installed,
    build_startup_command
)
from server_helper.agent_models import (
    get_agent_models,
    get_default_model_for_agent
)
from server_helper import i18n
from server_helper.i18n import t as _t
from session_manager import SessionManager

console = Console()

COMMAND_REGISTRY = [
    {"cmd": "/server",    "cat": "Remote", "desc_key": "cmd.server", "usage": "[scut-gpu|add|rename|rm]"},
    {"cmd": "/agent",     "cat": "Agent",  "desc_key": "cmd.agent",  "usage": "[agy|claude|opencode|codex]"},
    {"cmd": "/model",     "cat": "Agent",  "desc_key": "cmd.model",  "usage": "[gemini-3.8-flash|claude-3-7-sonnet|...]"},
    {"cmd": "/effort",    "cat": "Agent",  "desc_key": "cmd.effort", "usage": "[high|medium|low|off]"},
    {"cmd": "/files",     "cat": "Remote", "desc_key": "cmd.files",  "usage": "[path]"},
    {"cmd": "/sh",        "cat": "Remote", "desc_key": "cmd.sh",     "usage": ""},
    {"cmd": "/proxy",     "cat": "System", "desc_key": "cmd.proxy",  "usage": "[http://127.0.0.1:7897|off]"},
    {"cmd": "/tasks",     "cat": "Tasks",  "desc_key": "cmd.tasks",  "usage": ""},
    {"cmd": "/switch",    "cat": "Tasks",  "desc_key": "cmd.switch", "usage": "[name]"},
    {"cmd": "/broadcast", "cat": "Remote", "desc_key": "cmd.broadcast", "usage": "<shell cmd>"},
    {"cmd": "/status",    "cat": "System", "desc_key": "cmd.status", "usage": ""},
    {"cmd": "/theme",     "cat": "System", "desc_key": "cmd.theme",  "usage": "[name]"},
    {"cmd": "/lang",      "cat": "System", "desc_key": "cmd.lang",   "usage": "[en|zh]"},
    {"cmd": "/config",    "cat": "System", "desc_key": "cmd.config", "usage": ""},
    {"cmd": "/clear",     "cat": "System", "desc_key": "cmd.clear",  "usage": ""},
    {"cmd": "/help",      "cat": "System", "desc_key": "cmd.help",   "usage": ""},
    {"cmd": "/exit",      "cat": "System", "desc_key": "cmd.exit",   "usage": ""},
]


def _registry_desc(item):
    """Resolve a registry/candidate item's description in the active language."""
    if "desc" in item:
        return item["desc"]
    return _t(item.get("desc_key", ""))

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
                        display_meta=f"[{item['cat']}] {_registry_desc(item)}"
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
        self.has_navigated = False

    def reset(self):
        self.selected_index = 0
        self.has_navigated = False

    def get_items(self, text, config, session_mgr):
        if not text.startswith("/"):
            return []
        parts = text.split(maxsplit=1)
        raw_cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        arg_lower = arg.lower()

        subcommand_cmds = (
            "/agent", "/model", "/effort", "/thinking", "/theme",
            "/lang", "/language", "/server", "/connect", "/c",
            "/close", "/stop", "/switch", "/sw"
        )

        if " " in text or (raw_cmd in subcommand_cmds and text.strip().lower() == raw_cmd):
            if raw_cmd == "/agent":
                detected = detect_local_agents()
                candidates = [
                    {"cmd": a["id"], "desc": f"{a['name']} ({a['badge']})"}
                    for a in detected
                ]
            elif raw_cmd == "/model":
                active_agent = config.get_settings().get("default_agent", "agy")
                if session_mgr:
                    for s in session_mgr.sessions.values():
                        if s.status == "running" and s.command:
                            active_agent = s.command
                            break
                models = get_agent_models(active_agent)
                candidates = [{"cmd": m["cmd"], "desc": m["desc"]} for m in models]
            elif raw_cmd in ("/effort", "/thinking"):
                candidates = [
                    {"cmd": "high", "desc": "Full reasoning capability (recommended)"},
                    {"cmd": "medium", "desc": "Balanced reasoning speed"},
                    {"cmd": "low", "desc": "Fast output, minimal overhead"},
                    {"cmd": "off", "desc": "Disable extended thinking"},
                ]
            elif raw_cmd == "/theme":
                candidates = [{"cmd": t["id"], "desc": t["desc"]} for t in list_themes()]
            elif raw_cmd in ("/lang", "/language"):
                candidates = [
                    {"cmd": "en", "desc": "English"},
                    {"cmd": "zh", "desc": "中文"},
                ]
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
            self.has_navigated = True

    def move_down(self, total):
        if total > 0:
            self.selected_index = (self.selected_index + 1) % total
            self.has_navigated = True

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
        a = current_theme.get("accent", "#cba6f7")
        txt = current_theme.get("text", "#cdd6f4")
        d = current_theme.get("dim", "#6c7086")

        total = len(items)
        half = self.max_visible // 2
        start_idx = max(0, min(self.selected_index - half, total - self.max_visible))
        end_idx = min(start_idx + self.max_visible, total)

        # Dynamic column width based on longest visible item
        visible = items[start_idx:end_idx]
        col_w = max((len(it["cmd"]) for it in visible), default=12) + 2

        lines = []
        for i in range(start_idx, end_idx):
            item = items[i]
            is_sel = (i == self.selected_index)
            prefix = "  > " if is_sel else "    "
            lbl = html.escape(f"{item['cmd']:<{col_w}}")
            desc = html.escape(_registry_desc(item))
            if is_sel:
                lines.append(f'<style fg="{p}">{prefix}{lbl}</style><style fg="{txt}">{desc}</style>')
            else:
                lines.append(f'<style fg="{d}">{prefix}{lbl}{desc}</style>')

        if total > self.max_visible:
            lines.append(f'<style fg="{d}">    ({self.selected_index + 1}/{total})</style>')

        return "\n".join(lines)


class AgentCliApp:
    def __init__(self):
        self.config = Config()
        i18n.init_lang(self.config)
        self.session_mgr = SessionManager()
        self.active_session_id = None
        self.history_file = os.path.expanduser("~/.server-helper/cli_history")
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)

        # Auto-detect local agents and validate default agent
        self.local_agents = detect_local_agents()
        default_agent = self.config.get_settings().get("default_agent")
        if not default_agent or not is_agent_installed(default_agent):
            installed = [a["id"] for a in self.local_agents if a["installed"] and a["id"] != "shell"]
            if installed:
                self.config.update_settings({"default_agent": installed[0]})

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

            # 1. When typing slash command, render SelectList inline
            if curr_text.startswith("/"):
                rendered_list = self.select_list.render(curr_text, self.theme, self.config, self.session_mgr)
                if rendered_list:
                    return HTML(rendered_list)
                else:
                    parts = curr_text.split(maxsplit=1)
                    raw_cmd = html.escape(parts[0].lower())
                    err_col = self.theme.get("error", "#f38ba8")
                    msg = _t('toolbar.unknownCmd', cmd=raw_cmd)
                    return HTML(f'<style fg="{err_col}">{msg}</style>')

            # 2. Single-line status bar (no emojis - they cause cursor drift on Windows)
            session = self._get_active_session()
            p = self.theme["primary"]
            s = self.theme["success"]
            d = self.theme["dim"]
            a = self.theme["accent"]
            proxy = self.config.get_proxy()
            proxy_str = html.escape(f"{proxy}" if proxy else "direct")

            if session:
                srv = html.escape(session.name)
                rdir = session.remote_dir or "/"
                if len(rdir) > 22:
                    rdir = "..." + rdir[-19:]
                rdir = html.escape(rdir)
                agent = html.escape(session.command or "agy")
                model = html.escape(getattr(session, "model", "") or self.config.get_model(agent))
                effort = html.escape(str(self.config.get_thinking_effort()))
                return HTML(
                    f'<style fg="{s}">{srv}</style>'
                    f'<style fg="{d}"> | </style>'
                    f'<style fg="{p}">{rdir}</style>'
                    f'<style fg="{d}"> | </style>'
                    f'<style fg="{a}">{agent}:{model}</style>'
                    f'<style fg="{d}"> | effort:{effort} | {proxy_str}</style>'
                )
            idle_hint = _t('toolbar.idleHint', proxy=proxy_str)
            return HTML(
                f'<style fg="{d}">{idle_hint}</style>'
            )
        except Exception:
            return HTML(f'<style fg="#6c7086">{_t("toolbar.fallback")}</style>')

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
                    elif selected["cmd"].startswith("/"):
                        new_text = f"{selected['cmd']} "
                    else:
                        new_text = f"{buf.text.strip()} {selected['cmd']}"
                    buf.document = Document(new_text, cursor_position=len(new_text))
                    self.select_list.reset()
            else:
                buf.insert_text("  ")

        @bindings.add("enter")
        def _(event):
            buf = event.current_buffer
            raw_text = buf.text
            text = raw_text.strip()
            exact_cmds = [item["cmd"] for item in COMMAND_REGISTRY]

            if text.startswith("/"):
                items = self.select_list.get_items(raw_text, self.config, self.session_mgr)
                if items:
                    is_subcommand_mode = (" " in raw_text) or any(raw_text.strip().lower() == c["cmd"] for c in COMMAND_REGISTRY if c.get("usage"))
                    # If user actively navigated dropdown OR typed a space with subcommand, accept and execute immediately!
                    if self.select_list.has_navigated or (is_subcommand_mode and " " in raw_text):
                        selected = self.select_list.get_selected(raw_text, self.config, self.session_mgr)
                        if selected:
                            if " " in raw_text:
                                cmd = raw_text.split(maxsplit=1)[0]
                                new_text = f"{cmd} {selected['cmd']}"
                            elif selected["cmd"].startswith("/"):
                                new_text = selected["cmd"]
                            else:
                                new_text = f"{raw_text.strip()} {selected['cmd']}"
                            buf.document = Document(new_text, cursor_position=len(new_text))
                            self.select_list.reset()
                            buf.validate_and_handle()
                            return
                    elif not (" " in raw_text) and text not in exact_cmds:
                        selected = self.select_list.get_selected(raw_text, self.config, self.session_mgr)
                        if selected and selected["cmd"].startswith("/"):
                            new_text = f"{selected['cmd']} "
                            buf.document = Document(new_text, cursor_position=len(new_text))
                            self.select_list.reset()
                            return

            self.select_list.reset()
            buf.validate_and_handle()

        @bindings.add("backspace")
        def _(event):
            buf = event.current_buffer
            buf.delete_before_cursor(count=1)
            self.select_list.reset()

        @bindings.add("delete")
        def _(event):
            buf = event.current_buffer
            buf.delete(count=1)
            self.select_list.reset()

        @bindings.add("escape")
        def _(event):
            buf = event.current_buffer
            if buf.text.startswith("/"):
                buf.text = ""
            self.select_list.reset()

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
        border = self.theme.get("border", d)
        t_name = self.theme["name"]
        swatch = render_swatch(self.theme)

        session = self._get_active_session()
        active_agent = (session.command if session else None) or self.config.get_settings().get("default_agent", "agy")
        ag_info = get_agent_info(active_agent)
        ver_badge = f" ({ag_info['version']})" if ag_info and ag_info.get("version") else ""
        model_name = getattr(session, "model", "") if session else self.config.get_model(active_agent)

        if session:
            srv_info = session.server_info or {}
            srv_str = f"{session.name} ({srv_info.get('user', 'root')}@{srv_info.get('host', 'local')}:{srv_info.get('port', 22)})"
            rdir = session.remote_dir or "/"
            agent_str = f"{active_agent}{ver_badge} · {model_name}"
            status_tag = f"[{s}]● {_t('banner.running')}[/{s}]"
        else:
            srv_str = _t('banner.notConnected')
            rdir = "/"
            agent_str = f"{active_agent}{ver_badge} · {model_name}"
            status_tag = f"[{d}]{_t('banner.idle')}[/{d}]"

        effort = self.config.get_thinking_effort()
        proxy = self.config.get_proxy()
        proxy_str = f"[{s}]{proxy}[/{s}]" if proxy else f"[{d}]{_t('banner.directNoProxy')}[/{d}]"

        # Logo + tagline
        logo = (
            f"[{p}]  ▄▀█ █▀█ █▀▀ █▀█ █▀[/{p}]   [{txt}][bold]argos[/bold][/{txt}] [{d}]v0.3.0[/{d}]\n"
            f"[{p}]  █▀█ █▀▄ █▄█ █▄█ ▄█[/{p}]   [{d}]{_t('banner.tagline')}[/{d}]"
        )

        # Status grid using Rich Table for proper alignment across languages
        grid = Table.grid(padding=(0, 1))
        grid.add_column(style=a, min_width=10, justify="right")
        grid.add_column()
        grid.add_row(f"{_t('banner.target')}", f"[{txt}]{srv_str}[/{txt}] {status_tag}")
        grid.add_row(f"{_t('banner.workspace')}", f"[{p}]{rdir}[/{p}]")
        grid.add_row(f"{_t('banner.engine')}", f"[{txt}]{agent_str}[/{txt}] [{d}](effort: {effort})[/{d}]")
        grid.add_row(f"{_t('banner.proxy')}", proxy_str)
        grid.add_row(f"{_t('banner.theme')}", f"[{txt}]{t_name}[/{txt}] {swatch}")

        # Compact shortcuts
        shortcuts = (
            f"[{d}]/[/{d}][{a}]server[/{a}] [{d}]·[/{d}] "
            f"[{d}]/[/{d}][{a}]agent[/{a}] [{d}]·[/{d}] "
            f"[{d}]/[/{d}][{a}]model[/{a}] [{d}]·[/{d}] "
            f"[{d}]/[/{d}][{a}]files[/{a}] [{d}]·[/{d}] "
            f"[{d}]/[/{d}][{a}]sh[/{a}] [{d}]·[/{d}] "
            f"[{d}]/[/{d}][{a}]theme[/{a}] [{d}]·[/{d}] "
            f"[{d}]/[/{d}][{a}]help[/{a}]"
        )

        # Assemble
        from io import StringIO
        grid_buf = StringIO()
        grid_console = Console(file=grid_buf, force_terminal=True, width=shutil.get_terminal_size().columns - 6)
        grid_console.print(grid, end="")
        grid_text = grid_buf.getvalue().rstrip()

        card = f"{logo}\n\n{grid_text}\n\n  {shortcuts}"
        return Panel(card, border_style=border, padding=(1, 2))

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
                    console.print(f"\n[{self.theme['dim']}]{_t('run.goodbye')}[/{self.theme['dim']}]")
                    for s in list(self.session_mgr.sessions.values()):
                        try:
                            s.close()
                        except Exception:
                            pass
                    sys.exit(0)
                else:
                    self._last_sigint_time = now
                    console.print(f"\n[{self.theme['warning']}]{_t('run.ctrlCAgain')}[/{self.theme['warning']}]")
            except EOFError:
                console.print(f"\n[{self.theme['dim']}]{_t('run.goodbye')}[/{self.theme['dim']}]")
                for s in list(self.session_mgr.sessions.values()):
                    try:
                        s.close()
                    except Exception:
                        pass
                sys.exit(0)
            except Exception as e:
                console.print(f"[{self.theme['error']}]● {_t('run.error')}:[/{self.theme['error']}] {rich_escape(str(e))}")

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
            host = html.escape(srv_info.get("name") or srv_info.get("host", "local"))
            return HTML(
                f'<style fg="{s}"><b>{host}</b></style> '
                f'<style fg="{p}">></style> '
            )
        return HTML(f'<style fg="{p}"><b>argos</b></style> <style fg="{a}">></style> ')

    def handle_slash_command(self, cmd, arg):
        known_cmds = [
            "/exit", "/quit", "/help", "/clear", "/server", "/connect", "/c",
            "/theme", "/model", "/effort", "/thinking", "/proxy", "/files",
            "/ls", "/dir", "/tasks", "/sessions", "/switch", "/sw", "/terminal",
            "/term", "/sh", "/agent", "/status", "/broadcast", "/b", "/config",
            "/close", "/stop", "/lang", "/language"
        ]
        if cmd not in known_cmds:
            candidates = [c for c in SLASH_COMMANDS if c.startswith(cmd)]
            if len(candidates) == 1:
                cmd = candidates[0]

        if cmd in ("/exit", "/quit"):
            console.print(f"[dim]{_t('run.exiting')}[/dim]")
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

        elif cmd == "/lang":
            self.action_lang(arg)

        else:
            console.print(f"[{self.theme['error']}]Unknown command: {cmd}. Type /help for available commands.[/{self.theme['error']}]")

    def show_help(self):
        p = self.theme["primary"]
        a = self.theme["accent"]
        d = self.theme["dim"]
        txt = self.theme.get("text", "#cdd6f4")
        border = self.theme.get("border", d)

        console.print(f"\n  [{p}][bold]{_t('help.title')}[/bold][/{p}]\n")

        # Group commands by category from COMMAND_REGISTRY
        cat_order = ["Remote", "Agent", "Tasks", "System"]
        groups = {}
        for item in COMMAND_REGISTRY:
            cat = item.get("cat", "System")
            groups.setdefault(cat, []).append(item)

        # Also include aliases not in registry
        extra_cmds = [
            {"cmd": "/close", "cat": "Tasks", "desc_key": "help.close", "usage": "[name|#]"},
        ]
        for item in extra_cmds:
            cat = item.get("cat", "System")
            # Don't add duplicates
            existing = [c["cmd"] for c in groups.get(cat, [])]
            if item["cmd"] not in existing:
                groups.setdefault(cat, []).append(item)

        for cat in cat_order:
            items = groups.get(cat, [])
            if not items:
                continue
            console.print(f"  [{d}]{cat}[/{d}]")
            for item in items:
                cmd_str = item["cmd"]
                usage = item.get("usage", "")
                if usage:
                    cmd_str = f"{cmd_str} {usage}"
                desc = _registry_desc(item)
                console.print(f"    [{a}]{cmd_str:<22}[/{a}][{d}]{desc}[/{d}]")
            console.print()

        console.print(f"  [{d}]Type naturally to send prompts to the AI agent.[/{d}]")
        console.print(f"  [{d}]Ctrl+C twice to exit | Tab to autocomplete | Esc to clear[/{d}]\n")

    def action_lang(self, arg=""):
        """Switch the interface language (en/zh) and persist it to setting.json."""
        arg = (arg or "").strip().lower()
        if not arg:
            new_lang = "zh" if i18n.get_lang() == "en" else "en"
        elif arg in ("en", "zh", "english", "chinese", "cn", "zh-cn", "zh_cn"):
            new_lang = arg
        else:
            console.print(f"[{self.theme['warning']}]● {_t('lang.invalid')}[/{self.theme['warning']}]")
            return
        new_lang = i18n.set_lang(new_lang)
        try:
            self.config.update_settings({"language": new_lang})
        except Exception:
            pass
        console.clear()
        console.print(self.render_header())
        console.print(f"[{self.theme['success']}]● {_t('lang.switched')}[/{self.theme['success']}]\n")

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

        models = get_agent_models(agent)

        if arg:
            self.config.set_model(arg, agent)
            if session:
                session.model = arg
                if agent == "agy" and session.backend:
                    session.backend.write(f"/model {arg}\n")
            console.clear()
            console.print(self.render_header())
            console.print(f"[{self.theme['success']}]● Model set to: [bold]{arg}[/bold] (agent: {agent})[/{self.theme['success']}]\n")
            return

        # Interactive arrow-key model selection from agent's local models
        items = []
        selected_idx = 0
        for idx, m in enumerate(models):
            is_cur = (m["cmd"] == curr_model)
            if is_cur:
                selected_idx = idx
            badge = m.get("badge", "")
            if is_cur:
                badge = f"● {badge} (active)" if badge else "● active"
            items.append({
                "label": m["cmd"],
                "desc": m["desc"],
                "badge": badge,
                "installed": True
            })

        # Add custom model manual entry option at the end
        items.append({
            "label": "[+] Custom Model...",
            "desc": "Manually enter any model identifier not in the list",
            "badge": "input",
            "installed": True
        })

        action, chosen_item, _ = interactive_menu_select(
            title=f"Select AI Model for [{agent}]",
            items=items,
            current_idx=selected_idx,
            theme=self.theme
        )
        if action == "select" and chosen_item:
            if chosen_item["label"] == "[+] Custom Model...":
                console.print(f"\n  [{self.theme['accent']}]Enter custom model identifier:[/{self.theme['accent']}]")
                custom_name = self._get_user_input("  › model: ")
                if not custom_name:
                    console.clear()
                    console.print(self.render_header())
                    return
                model_name = custom_name
            else:
                model_name = chosen_item["label"]

            self.config.set_model(model_name, agent)
            if session:
                session.model = model_name
                if agent == "agy" and session.backend:
                    session.backend.write(f"/model {model_name}\n")
            console.clear()
            console.print(self.render_header())
            console.print(f"[{self.theme['success']}]● Model switched to: [bold]{model_name}[/bold] (agent: {agent})[/{self.theme['success']}]\n")
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

        # Direct server connection by name or 'local'
        if arg_lower == "local":
            self._connect_to_server({"is_local": True, "name": "local", "default_dir": os.getcwd()})
            return

        if arg_lower:
            matched = [s for s in servers if s.get("name", "").lower() == arg_lower or s.get("host", "").lower() == arg_lower or s.get("id", "").lower() == arg_lower]
            if matched:
                self._connect_to_server(matched[0])
                return

            if arg_lower in ("codex", "claude", "agy", "opencode", "shell"):
                console.print(f"[{self.theme['accent']}]● Detected agent '{arg_lower}'. Switching active agent to '{arg_lower}'...[/{self.theme['accent']}]")
                self.action_set_agent(arg_lower)
                if servers:
                    self._connect_to_server(servers[0])
                return

            avail = ["local"] + [s.get("name", "") for s in servers if s.get("name")]
            console.print(f"[{self.theme['warning']}]● Server not found: {arg}. Available: {', '.join(avail)}[/{self.theme['warning']}]\n")
            return

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
        model_name = self.config.get_model(agent_type)
        effort_level = self.config.get_thinking_effort()
        startup_cmd = build_startup_command(agent_type, model=model_name, effort=effort_level)

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
        proxy_info = "127.0.0.1:(10808/7897) ➔ 7897 (SSH tunnel active)" if self.config.get_proxy() else "direct"

        banner = (
            f"[{s}][bold]● Connected: {task_name}[/bold][/{s}] [{d}]({session.session_type})[/{d}]\n\n"
            f"  [{a}]Target:[/{a}]          [{txt}]{task_name}[/{txt}] [{d}]({srv_str})[/{d}]\n"
            f"  [{a}]Directory:[/{a}]       [{p}]{work_dir}[/{p}]\n"
            f"{files_line}"
            f"  [{a}]Engine:[/{a}]          [{txt}]{agent_type}[/{txt}] [{d}]({model_name}, effort: {effort_level})[/{d}]\n"
            f"  [{a}]Proxy Tunnel:[/{a}]    [{s}]{proxy_info}[/{s}]\n\n"
            f"[{d}]Quick Actions: Type prompt to dispatch · [/{d}][{a}]/files[/{a}] [{d}]list files · [/{d}][{a}]/sh[/{a}] [{d}]terminal · [/{d}][{a}]/status[/{a}] [{d}]GPU status[/{d}]"
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
                import getpass
                password = getpass.getpass("› Password: ").strip()

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
                                b'H': '\x1b[A',  # Up
                                b'P': '\x1b[B',  # Down
                                b'M': '\x1b[C',  # Right
                                b'K': '\x1b[D',  # Left
                                b'G': '\x1b[H',  # Home
                                b'O': '\x1b[F',  # End
                                b'S': '\x1b[3~', # Delete
                                b'I': '\x1b[5~', # PgUp
                                b'Q': '\x1b[6~', # PgDn
                            }
                            # Always send str: LocalPty (pywinpty) requires str, and
                            # unmapped function keys are ignored rather than sent as
                            # raw prefix bytes that would corrupt the remote shell.
                            code = arrow_map.get(ch2)
                            if code is not None:
                                try:
                                    session.backend.write(code)
                                except Exception:
                                    pass
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

    def action_set_agent(self, agent_name=""):
        agent_name = (agent_name or "").strip().lower()
        session = self._get_active_session()
        curr_agent = (session.command if session else None) or self.config.get_settings().get("default_agent", "agy")

        detected = detect_local_agents(force_refresh=True)

        # Interactive arrow-key selection if no agent_name provided
        if not agent_name:
            items = []
            selected_idx = 0
            for idx, a in enumerate(detected):
                is_active = (a["id"] == curr_agent)
                if is_active:
                    selected_idx = idx

                status_badge = (f"● {a['badge']}" if a["installed"] else "not found")
                if is_active:
                    status_badge += " (active)"

                items.append({
                    "id": a["id"],
                    "label": a["id"],
                    "desc": a["desc"],
                    "badge": status_badge,
                    "installed": a["installed"],
                    "path": a.get("path"),
                    "version": a.get("version"),
                })

            action, chosen, _ = interactive_menu_select(
                title=_t("agent.title"),
                items=items,
                current_idx=selected_idx,
                theme=self.theme
            )

            if action == "select" and chosen:
                agent_name = chosen["id"]
            else:
                console.clear()
                console.print(self.render_header())
                return

        # Validate agent
        info = get_agent_info(agent_name)
        if not info:
            console.print(f"[{self.theme['warning']}]● Unknown agent: {agent_name}. Valid: agy, claude, opencode, codex, aider, goose, shell[/{self.theme['warning']}]\n")
            return

        if not info.get("installed") and agent_name != "shell":
            console.print(f"[{self.theme['warning']}]● {_t('agent.notFound', name=agent_name)}[/{self.theme['warning']}]\n")
            return

        new_model = self.config.get_model(agent_name)
        self.config.update_settings({"default_agent": agent_name})

        relaunch_note = ""
        if session and session.status == "running" and session.backend:
            session.command = agent_name
            session.model = new_model
            try:
                # Terminate any current agent process with Ctrl+C
                session.backend.write("\x03\x03")
                time.sleep(0.4)
                effort = self.config.get_thinking_effort()
                startup_cmd = build_startup_command(agent_name, model=new_model, effort=effort)
                if startup_cmd:
                    session.backend.write(f"{startup_cmd}\r\n")
                relaunch_note = f"  Active session [{session.name}] switched to {agent_name}."
            except Exception:
                pass

        console.clear()
        console.print(self.render_header())
        ver_tag = f" ({info['version']})" if info.get("version") else ""
        path_tag = f" [{self.theme['dim']}]{info.get('path', '')}[/{self.theme['dim']}]" if info.get('path') else ""
        switched_label = f"[bold]{info['name']}{ver_tag}[/bold]"
        console.print(f"[{self.theme['success']}]● {_t('agent.switched', name=switched_label)}{path_tag}[/{self.theme['success']}]")
        console.print(f"[{self.theme['dim']}]  Model: [bold]{new_model}[/bold] (synced from {agent_name} local configuration)[/{self.theme['dim']}]")
        if relaunch_note:
            console.print(f"[{self.theme['accent']}]{relaunch_note}[/{self.theme['accent']}]\n")
        elif not session:
            servers = self.config.get_servers()
            srv_hint = f"/server {servers[0]['name']}" if servers else "/server local"
            console.print(f"[{self.theme['accent']}]  Tip: Type [{self.theme['primary']}]{srv_hint}[/{self.theme['primary']}] to launch {agent_name} on your server or local machine.[/{self.theme['accent']}]\n")

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

        console.print(f"[{a}]● Dispatched to {agent} in [{session.name}]...[/{a}] [{d}](Type /sh to interact directly, Ctrl+C to return to prompt)[/{d}]")
        # Send text, followed by brief delay and \r so raw terminal TUIs (Codex, Claude, etc.) register Submit
        session.backend.write(prompt)
        time.sleep(0.08)
        session.backend.write("\r")

        # Stream output directly to user so user sees response live
        printed = [0]
        def on_stream_output(chunk):
            try:
                sys.stdout.write(chunk)
                sys.stdout.flush()
                printed[0] += len(chunk)
            except Exception:
                pass

        session.output_listeners.add(on_stream_output)
        try:
            t0 = time.time()
            last_change = time.time()
            last_cnt = 0
            while time.time() - t0 < 120:
                time.sleep(0.08)
                if printed[0] != last_cnt:
                    last_cnt = printed[0]
                    last_change = time.time()
                elif printed[0] > 0 and (time.time() - last_change > 4.5):
                    break
        except KeyboardInterrupt:
            pass
        finally:
            if on_stream_output in session.output_listeners:
                session.output_listeners.remove(on_stream_output)
            console.print()


def main():
    app = AgentCliApp()
    app.run()


if __name__ == "__main__":
    main()
