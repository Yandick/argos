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

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
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

SLASH_COMMANDS = [
    "/server",
    "/theme",
    "/model",
    "/effort",
    "/thinking",
    "/tasks",
    "/switch",
    "/terminal",
    "/sh",
    "/agent",
    "/status",
    "/broadcast",
    "/close",
    "/config",
    "/clear",
    "/help",
    "/exit",
    "/quit"
]

completer = WordCompleter(SLASH_COMMANDS, ignore_case=True, sentence=True)

POPULAR_MODELS = [
    {"label": "gemini-2.5-pro", "desc": "Google flagship multimodal & coding model"},
    {"label": "claude-3-7-sonnet", "desc": "Anthropic latest hybrid reasoning model"},
    {"label": "claude-3-5-sonnet", "desc": "High performance standard coding model"},
    {"label": "deepseek-r1", "desc": "Open-weight deep reasoning model"},
    {"label": "deepseek-chat", "desc": "DeepSeek V3 general coding model"},
    {"label": "gpt-4o", "desc": "OpenAI flagship omni model"}
]


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

        self._init_prompt_session()

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

        try:
            self.session_prompt = PromptSession(
                history=FileHistory(self.history_file),
                completer=completer,
                output=pt_out,
                input=pt_in,
                style=pt_style
            )
        except Exception:
            self.session_prompt = None

    def _get_user_input(self, prompt_text):
        if self.session_prompt:
            try:
                return self.session_prompt.prompt(prompt_text).strip()
            except Exception:
                pass
        return input(prompt_text).strip()

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

        card = (
            f"[{p}][bold]● argos[/bold][/{p}] [{d}]v0.3.0 · AI agent remote multi-task orchestrator[/{d}]\n\n"
            f"  [{a}]Target:[/{a}]    [{txt}]{srv_str}[/{txt}] {status_tag}\n"
            f"  [{a}]Workspace:[/{a}] [{p}]{rdir}[/{p}]\n"
            f"  [{a}]Engine:[/{a}]    [{txt}]{agent_str}[/{txt}] [{d}](effort: {effort})[/{d}]\n"
            f"  [{a}]Theme:[/{a}]     [{txt}]{t_name}[/{txt}] {swatch}\n\n"
            f"[{d}]Shortcuts: [/][{a}]/server[/] [{d}]switch target[dim] · [/][{a}]/model[/] [{d}]models[dim] · [/][{a}]/effort[/] [{d}]reasoning[dim] · [/][{a}]/theme[/] [{d}]themes[dim] · [/][{a}]/sh[/] [{d}]terminal[dim] · [/][{a}]/help[/] [{d}]help[dim]"
        )
        return Panel(card, border_style=p, padding=(0, 1))

    def run(self):
        console.clear()
        console.print(self.render_header())
        console.print()

        while True:
            try:
                prompt_text = self._build_prompt()
                user_input = self._get_user_input(prompt_text)

                if not user_input:
                    continue

                if user_input.startswith("/"):
                    parts = user_input.split(maxsplit=1)
                    cmd = parts[0].lower()
                    arg = parts[1].strip() if len(parts) > 1 else ""
                    self.handle_slash_command(cmd, arg)
                else:
                    self.handle_natural_language_prompt(user_input)

            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Use /exit to quit Argos.[/dim]")
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
            host = srv_info.get("host", "local")
            user = srv_info.get("user") or srv_info.get("username") or os.getenv("USERNAME", "user")
            rdir = session.remote_dir or "/"
            if len(rdir) > 22:
                rdir = "..." + rdir[-19:]
            agent = session.command or "agy"
            model_info = getattr(session, "model", "") or self.config.get_model(agent)
            model_short = model_info.split("/")[-1] if model_info else ""
            model_tag = f" · {model_short}" if model_short else ""
            return f"[{p}]●[/{p}] [{s}]{user}@{host}[/{s}]:[{d}]{rdir}[/{d}] [{a}]({agent}{model_tag})[/{a}] › "
        return f"[{p}]●[/{p}] [bold]argos[/bold] › "

    def handle_slash_command(self, cmd, arg):
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

        elif cmd in ("/tasks", "/sessions", "/ls"):
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
            ("/server", "Interactive server & environment manager (↑/↓ to select, [a] add, [r] rename)"),
            ("/theme [name]", "Interactive theme picker with live real-time preview (↑/↓ to preview)"),
            ("/model [name]", "Select model for agent (gemini-2.5-pro, claude-3-7-sonnet...)"),
            ("/effort [level]", "Select reasoning & thinking effort (high, medium, low, off)"),
            ("/tasks, /ls", "List all running sessions and active context"),
            ("/switch <name|#>", "Switch active session context"),
            ("/terminal, /sh", "Attach raw terminal to active session (Ctrl+] to detach)"),
            ("/agent <name>", "Switch agent engine (agy, claude, codex, shell)"),
            ("/status", "Show remote CPU, GPU, memory and load status"),
            ("/broadcast <cmd>", "Broadcast shell command to all sessions"),
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
            default_dir = server_info.get("default_dir") or os.getcwd()
            try:
                work_dir = input(f"› Local directory [{default_dir}]: ").strip() or default_dir
            except (KeyboardInterrupt, EOFError):
                return
        else:
            default_dir = server_info.get("default_dir") or "/workspace"
            try:
                work_dir = input(f"› Remote directory [{default_dir}]: ").strip() or default_dir
            except (KeyboardInterrupt, EOFError):
                return

        # Agent engine choice
        default_agent = self.config.get_settings().get("default_agent", "agy")
        console.print(f"› Agent engine: [1] agy  [2] claude  [3] codex  [4] shell  (default: {default_agent})")
        try:
            agent_pick = input("› Pick [1]: ").strip() or "1"
        except (KeyboardInterrupt, EOFError):
            return
        agent_map = {"1": "agy", "2": "claude", "3": "codex", "4": "shell"}
        agent_type = agent_map.get(agent_pick, default_agent)

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

        console.clear()
        console.print(self.render_header())
        console.print(f"[{s}][bold]● Connected to {task_name}[/bold] [dim]({session.session_type})[/dim][/{s}]")
        console.print(f"[{d}]● Working directory: [{p}]{work_dir}[/{p}] | Agent: [{a}]{agent_type}[/{a}] (model: {model_name}, effort: {effort_level})[/{d}]")
        console.print(f"[{d}]● Type natural language prompts to run, or [{a}]/sh[/{a}] to enter interactive terminal.[/{d}]\n")

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
                while not stop_event.is_set() and session.status == "running":
                    if msvcrt.kbhit():
                        ch = msvcrt.getch()
                        # Ctrl+] (ASCII 29 / 0x1d) detaches
                        if ch == b'\x1d':
                            break
                        # Handle Windows special / arrow keys (0x00 or 0xe0 prefix)
                        if ch in (b'\x00', b'\xe0'):
                            ch2 = msvcrt.getch()
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
                        time.sleep(0.01)
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
        console.print(f"  Default model:   {s.get('default_model', 'gemini-2.5-pro')}")
        console.print(f"  Thinking effort: {s.get('thinking_effort', 'high')}")
        console.print(f"  Servers saved:   {len(self.config.get_servers())}\n")

    def handle_natural_language_prompt(self, prompt):
        session = self._get_active_session()
        if not session:
            console.print(f"[{self.theme['dim']}]● No environment connected. Type [{self.theme['accent']}][bold]/server[/bold][/{self.theme['accent']}] to connect to a local or remote server.[/{self.theme['dim']}]")
            return

        agent = (session.command or "agy").lower()

        if agent in ("agy", "claude"):
            session.backend.write(prompt + "\n")
            console.print(f"[{self.theme['dim']}]● Sent to {agent}. Type [{self.theme['accent']}][bold]/sh[/bold][/{self.theme['accent']}] to enter interactive terminal and observe live output.[/{self.theme['dim']}]")
        elif agent == "shell":
            session.backend.write(prompt + "\n")
            time.sleep(0.3)
            recent = session.scrollback[-2000:]
            if recent:
                console.print(recent.strip())
        else:
            session.backend.write(prompt + "\n")
            console.print(f"[{self.theme['dim']}]● Prompt dispatched. Type [{self.theme['accent']}][bold]/sh[/bold][/{self.theme['accent']}] to attach terminal.[/{self.theme['dim']}]")


def main():
    app = AgentCliApp()
    app.run()


if __name__ == "__main__":
    main()
