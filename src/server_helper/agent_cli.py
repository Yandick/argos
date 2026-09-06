"""
Argos (Ἄργος) CLI Interface
Minimalist OpenCode & Pi aesthetic agent orchestrator.
Runs in-process without secondary console popups or external daemons.
"""
import os
import sys
import time
import shutil
import threading
from rich.console import Console
from rich.text import Text

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
from session_manager import SessionManager

console = Console()

SLASH_COMMANDS = [
    "/server",
    "/connect",
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

HEADER = (
    "[bold cyan]●[/bold cyan] [bold]argos[/bold] [dim]v0.3.0 · remote coding agent orchestrator[/dim]\n"
    "[dim]Type [cyan]/server[/cyan] to switch context, [cyan]/help[/cyan] for commands[/dim]\n"
)


class AgentCliApp:
    def __init__(self):
        self.config = Config()
        self.session_mgr = SessionManager()
        self.active_session_id = None
        self.history_file = os.path.expanduser("~/.server-helper/cli_history")
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)

        try:
            pt_out = create_output()
        except Exception:
            pt_out = DummyOutput()

        try:
            pt_in = create_input()
        except Exception:
            pt_in = DummyInput()

        try:
            self.session_prompt = PromptSession(
                history=FileHistory(self.history_file),
                completer=completer,
                output=pt_out,
                input=pt_in
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

    def run(self):
        console.clear()
        console.print(HEADER)

        # Auto-connect or pre-select first server if configured
        servers = self.config.get_servers()
        if servers:
            s0 = servers[0]
            console.print(f"[dim]● Configured remote server available: [bold cyan]{s0.get('name')}[/bold cyan] ({s0.get('user', 'root')}@{s0.get('host')}:{s0.get('port', 22)})[/dim]")
            console.print("[dim]  Type [cyan]/server[/cyan] to connect, or type prompts directly.[/dim]\n")

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
                console.print(f"[bold red]● Error:[/bold red] {e}")

    def _get_active_session(self):
        if self.active_session_id:
            s = self.session_mgr.get_session(self.active_session_id)
            if s and s.status == "running":
                return s
        # If active_session_id is invalid or closed, fallback to first running session
        running = [s for s in self.session_mgr.sessions.values() if s.status == "running"]
        if running:
            self.active_session_id = running[0].session_id
            return running[0]
        self.active_session_id = None
        return None

    def _build_prompt(self):
        session = self._get_active_session()
        if session:
            srv_info = session.server_info or {}
            host = srv_info.get("host", "local")
            user = srv_info.get("user") or srv_info.get("username") or os.getenv("USERNAME", "user")
            rdir = session.remote_dir or "/"
            # Shorten directory path
            short_dir = rdir
            if len(short_dir) > 25:
                short_dir = "..." + short_dir[-22:]
            agent = session.command or "agy"
            return f"● [{user}@{host}:{short_dir} ({agent})] › "
        return "● argos › "

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
            console.print(HEADER)

        elif cmd in ("/server", "/servers", "/connect", "/c"):
            self.action_servers(arg)

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
            console.print(f"[red]Unknown command: {cmd}. Type /help for available commands.[/red]")

    def show_help(self):
        console.print("\n[bold]● Argos Commands[/bold]")
        cmds = [
            ("/server, /connect", "Select or add remote server / local environment"),
            ("/tasks, /ls", "List all running sessions and active context"),
            ("/switch <name|#>", "Switch active session context"),
            ("/terminal, /sh", "Attach terminal to active session (Ctrl+] to detach)"),
            ("/agent <name>", "Switch agent engine (agy, claude, codex, shell)"),
            ("/status", "Show remote CPU, GPU, memory and load status"),
            ("/broadcast <cmd>", "Broadcast shell command to all sessions"),
            ("/close [name|#]", "Close a running session"),
            ("/config", "Show config file path and default settings"),
            ("/clear", "Clear screen"),
            ("/exit, /quit", "Exit Argos")
        ]
        for c, desc in cmds:
            console.print(f"  [cyan]{c:<20}[/cyan] [dim]{desc}[/dim]")
        console.print()

    def action_servers(self, arg=""):
        servers = self.config.get_servers()
        arg_lower = (arg or "").strip().lower()

        if arg_lower == "add":
            new_srv = self._prompt_new_server()
            if new_srv:
                console.print(f"[green]● Server '{new_srv.get('name')}' saved to setting.json[/green]")
                try:
                    ask = input(f"Connect to {new_srv.get('name')} now? (Y/n): ").strip().lower()
                    if ask != "n":
                        self._connect_to_server(new_srv)
                except (KeyboardInterrupt, EOFError):
                    pass
            return

        if arg_lower in ("rm", "remove", "del"):
            self._prompt_remove_server()
            return

        # List environments in clean OpenCode/Pi aesthetic
        console.print("\n[bold]● Available Environments[/bold]\n")
        active = self._get_active_session()
        active_srv_name = (active.server_info.get("name") if active and active.server_info else None) if active else None

        # [0] Local
        cur_mark = " [bold green]● active[/bold green]" if (active and active.session_type == "local_pty") else ""
        console.print(f"  [bold yellow][0][/bold yellow] [bold]Local Machine[/bold]          [dim]native PTY[/dim]         {os.getcwd()}{cur_mark}")

        # [1..N] Remote
        for idx, s in enumerate(servers, 1):
            auth_desc = "key" if s.get("auth_type") == "key" else "password"
            srv_user = s.get("user") or s.get("username") or "root"
            srv_host = s.get("host")
            srv_port = s.get("port", 22)
            cur_mark = " [bold green]● active[/bold green]" if (active and active_srv_name == s.get("name")) else ""
            console.print(f"  [bold yellow][{idx}][/bold yellow] [bold]{s.get('name'):<20}[/bold] [dim]{srv_user}@{srv_host}:{srv_port} ({auth_desc})[/dim]  {s.get('default_dir') or '/'}{cur_mark}")

        console.print("\n  [dim]Select [bold yellow][0-{len(servers)}][/bold yellow], [bold green][a][/bold green] add server, [bold red][d][/bold red] delete, [bold][q][/bold] back[/dim]\n")

        selected_server = None
        if arg:
            if arg == "0":
                selected_server = {"is_local": True, "name": "local", "default_dir": os.getcwd()}
            else:
                try:
                    idx = int(arg) - 1
                    if 0 <= idx < len(servers):
                        selected_server = servers[idx]
                except ValueError:
                    selected_server = self.config.get_server(arg)

        if not selected_server:
            try:
                choice = input("› Select: ").strip()
                if not choice or choice.lower() in ("q", "quit", "cancel"):
                    return
                elif choice == "0":
                    selected_server = {"is_local": True, "name": "local", "default_dir": os.getcwd()}
                elif choice.lower() in ("a", "add"):
                    new_srv = self._prompt_new_server()
                    if new_srv:
                        console.print(f"[green]● Server '{new_srv.get('name')}' saved[/green]")
                        self._connect_to_server(new_srv)
                    return
                elif choice.lower() in ("d", "del", "rm", "remove"):
                    self._prompt_remove_server()
                    return
                else:
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(servers):
                            selected_server = servers[idx]
                        else:
                            console.print(f"[red]● Invalid choice: {choice}[/red]")
                            return
                    except ValueError:
                        selected_server = self.config.get_server(choice)
                        if not selected_server:
                            console.print(f"[red]● Server not found: {choice}[/red]")
                            return
            except (KeyboardInterrupt, EOFError):
                return

        self._connect_to_server(selected_server)

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

        cols, rows = shutil.get_terminal_size((120, 30))

        if is_local:
            console.print(f"● Starting local task [{task_name}] ({agent_type})...")
            startup_cmd = agent_type if agent_type != "shell" else ""
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
            startup_cmd = agent_type if agent_type != "shell" else ""
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
            console.print(f"[bold red]● Connection failed:[/bold red] {err or 'Unknown error'}\n")
            return

        self.active_session_id = session.session_id
        console.print(f"[bold green]● Connected to {task_name}[/bold green] [dim]({session.session_type})[/dim]")
        console.print(f"[dim]● Working directory: [cyan]{work_dir}[/cyan] | Agent: [magenta]{agent_type}[/magenta][/dim]")
        console.print(f"[dim]● Type natural language prompts to run, or [cyan]/sh[/cyan] to enter interactive terminal.[/dim]\n")

    def _prompt_new_server(self):
        console.print("\n[bold]● Add New Remote Server[/bold]")
        try:
            name = input("› Server name (e.g. ustc-gpu): ").strip() or "remote-server"
            host = input("› Host / IP: ").strip()
            if not host:
                console.print("[red]Host IP cannot be empty.[/red]")
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

            default_dir = input("› Default directory [/root/workspace]: ").strip() or "/root/workspace"

            res = self.config.add_or_update_server(name, host, port, user, auth_type, key_path, password, default_dir)
            # Sync to global ~/.server-helper/setting.json as well
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
        console.print("\n[bold]● Delete Server[/bold]")
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
                console.print(f"[green]● Server '{target.get('name')}' removed.[/green]")
        except (KeyboardInterrupt, EOFError):
            pass

    def action_list_tasks(self):
        sessions = list(self.session_mgr.sessions.values())
        if not sessions:
            console.print("[dim]● No active sessions. Type /server to connect.[/dim]")
            return

        console.print("\n[bold]● Active Sessions[/bold]\n")
        active = self._get_active_session()
        for idx, s in enumerate(sessions, 1):
            is_active = " [bold green]● current[/bold green]" if (active and s.session_id == active.session_id) else ""
            target = s.server_info.get("name") if s.server_info else "local"
            rdir = s.remote_dir or "/"
            agent = s.command or "agent"
            console.print(f"  [{idx}] [bold]{s.name:<18}[/bold] [dim]{target:<16}[/dim] [cyan]{rdir:<22}[/cyan] [magenta]{agent:<8}[/magenta] [green]{s.status}[/green]{is_active}")
        console.print("\n  [dim]Type [cyan]/switch <name|#>[/cyan] to switch, [cyan]/sh[/cyan] to attach terminal[/dim]\n")

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
            console.print(f"[green]● Switched to session: [bold]{target.name}[/bold][/green]")
        else:
            console.print(f"[red]● Session '{name}' not found.[/red]")

    def action_open_terminal(self):
        session = self._get_active_session()
        if not session or not session.backend:
            console.print("[yellow]● No active session. Type /server to connect first.[/yellow]")
            return

        console.print(f"\n● [bold]Attached to {session.name}[/bold] ({session.command or 'shell'})")
        console.print("[dim]Press [bold yellow]Ctrl + ][/bold yellow] to detach and return to Argos prompt[/dim]\n")

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
                            # Map arrows to ANSI escape codes
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
                # Unix raw terminal mode
                import select
                while not stop_event.is_set() and session.status == "running":
                    r, _, _ = select.select([sys.stdin], [], [], 0.05)
                    if r:
                        ch = sys.stdin.read(1)
                        if ch == '\x1d':
                            break
                        session.backend.write(ch)

        except Exception as e:
            console.print(f"\n[red]Terminal error: {e}[/red]")
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
            console.print(f"[green]● Active session [{session.name}] agent set to: {agent_name}[/green]")
        else:
            self.config.update_settings({"default_agent": agent_name})
            console.print(f"[green]● Default agent set to: {agent_name}[/green]")

    def action_show_status(self):
        session = self._get_active_session()
        if not session:
            console.print("[yellow]● No active session.[/yellow]")
            return

        console.print(f"● Inspecting environment for [bold cyan]{session.name}[/bold cyan]...")

        if session.session_type == "remote_ssh" and hasattr(session.backend, "exec_command"):
            # Run fast diagnostics over SSH
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
        console.print(f"[green]● Broadcasted to {len(sessions)} active session(s):[/green] {cmd}")

    def action_close_task(self, name):
        session = self._get_active_session()
        target_id = None
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
            console.print(f"[yellow]● Session [{target_name}] closed.[/yellow]")
        else:
            console.print(f"[red]● Session not found: {name}[/red]")

    def action_config(self):
        s = self.config.get_settings()
        console.print("\n[bold]● Argos Configuration[/bold]")
        console.print(f"  Config file:   {self.config.config_path}")
        console.print(f"  Default agent: {s.get('default_agent', 'agy')}")
        console.print(f"  Auto reconnect: {s.get('auto_reconnect', True)}")
        console.print(f"  Servers saved: {len(self.config.get_servers())}\n")

    def handle_natural_language_prompt(self, prompt):
        session = self._get_active_session()
        if not session:
            console.print("[dim]● No environment connected. Type [cyan]/server[/cyan] to connect to a local or remote server.[/dim]")
            return

        agent = (session.command or "agy").lower()

        if agent in ("agy", "claude"):
            # Pass prompt directly into active agent session
            session.backend.write(prompt + "\n")
            console.print(f"[dim]● Sent to {agent}. Type [cyan]/sh[/cyan] to enter interactive terminal and see output.[/dim]")
        elif agent == "shell":
            # Pass directly to shell
            session.backend.write(prompt + "\n")
            time.sleep(0.3)
            recent = session.scrollback[-2000:]
            if recent:
                console.print(recent.strip())
        else:
            # Autonomous agent loop
            session.backend.write(prompt + "\n")
            console.print(f"[dim]● Prompt dispatched. Type [cyan]/sh[/cyan] to attach terminal.[/dim]")


def main():
    app = AgentCliApp()
    app.run()


if __name__ == "__main__":
    main()
