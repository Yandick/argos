"""
OpenCode & Pi style Agent CLI Interface for ServerHelper
Provides interactive slash commands, autocompletion, multi-task switching, and terminal attachment.
"""
import os
import sys
import time
import shutil
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style

from prompt_toolkit.output import create_output, DummyOutput
from prompt_toolkit.input import create_input, DummyInput

from server_helper.config import Config
from server_helper.daemon import api_get, api_post, ensure_daemon_running
from server_helper.tui import attach_terminal
from server_helper.agent_bridge import run_cli_agent_task
from server_helper.ssh import SSHClientWrapper

console = Console()

SLASH_COMMANDS = [
    "/connect",
    "/tasks",
    "/switch",
    "/terminal",
    "/agent",
    "/status",
    "/broadcast",
    "/close",
    "/servers",
    "/config",
    "/clear",
    "/help",
    "/exit",
    "/quit"
]

completer = WordCompleter(SLASH_COMMANDS, ignore_case=True, sentence=True)

pt_style = Style.from_dict({
    'prompt': '#6366f1 bold',
    'badge': '#10b981 bold',
})

BANNER = r"""
 [bold cyan]███████╗███████╗██████╗ ██╗   ██╗███████╗██████╗ [/bold cyan]
 [bold cyan]██╔════╝██╔════╝██╔══██╗██║   ██║██╔════╝██╔══██╗[/bold cyan]
 [bold cyan]███████╗█████╗  ██████╔╝██║   ██║█████╗  ██████╔╝[/bold cyan]
 [bold cyan]╚════██║██╔══╝  ██╔══██╗╚██╗ ██╔╝██╔══╝  ██╔══██╗[/bold cyan]
 [bold cyan]███████║███████╗██║  ██║ ╚████╔╝ ███████╗██║  ██║[/bold cyan]
 [bold cyan]╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝[/bold cyan]
 [dim]⚡ ServerHelper Agent CLI v0.2.0 | OpenCode / Pi Style[/dim]
 [dim]输入 [bold yellow]/help[/bold yellow] 查看指令列表，输入 [bold yellow]/connect[/bold yellow] 连接远程服务器[/dim]
"""


class AgentCliApp:
    def __init__(self):
        self.config = Config()
        self.active_session = None  # dictionary of active session
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

        self.session_prompt = PromptSession(
            history=FileHistory(self.history_file),
            completer=completer,
            output=pt_out,
            input=pt_in
        )

    def run(self):
        # Ensure daemon is running
        ensure_daemon_running()
        console.clear()
        console.print(BANNER)

        # Restore last active session if any
        self._sync_sessions()

        while True:
            try:
                prompt_text = self._build_prompt()
                user_input = self.session_prompt.prompt(prompt_text).strip()

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
                console.print("\n[dim]使用 /exit 退出程序。[/dim]")
            except Exception as e:
                console.print(f"[bold red]运行异常:[/bold red] {e}")

    def _build_prompt(self):
        if self.active_session:
            name = self.active_session.get("name", "task")
            srv = self.active_session.get("server_name", "local")
            rdir = self.active_session.get("remote_dir", "/")
            short_dir = os.path.basename(rdir.rstrip("/\\")) or rdir
            agent = self.active_session.get("command") or "agent"
            return f"[{name}@{srv}:{short_dir} ({agent})] ❯ "
        return "server-helper ❯ "

    def _sync_sessions(self):
        res = api_get("/api/sessions")
        sessions = res.get("sessions", [])
        if sessions:
            if not self.active_session or not any(s.get("session_id") == self.active_session.get("session_id") for s in sessions):
                self.active_session = sessions[0]
        else:
            self.active_session = None

    def handle_slash_command(self, cmd, arg):
        if cmd in ("/exit", "/quit"):
            console.print("[dim]ServerHelper CLI 已退出，后台任务将持续保持运行。[/dim]")
            sys.exit(0)

        elif cmd == "/help":
            self.show_help()

        elif cmd == "/clear":
            console.clear()
            console.print(BANNER)

        elif cmd in ("/connect", "/c"):
            self.action_connect(arg)

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

        elif cmd == "/servers":
            self.action_servers()

        elif cmd == "/config":
            self.action_config()

        elif cmd in ("/close", "/stop"):
            self.action_close_task(arg)

        else:
            console.print(f"[red]未知指令: {cmd}。输入 /help 查看所有可用命令。[/red]")

    def show_help(self):
        table = Table(title="📖 ServerHelper Agent CLI 指令表", border_style="cyan")
        table.add_column("命令", style="bold yellow")
        table.add_column("说明", style="white")

        table.add_row("/connect (或 /c)", "交互式选择远程服务器与目录，快速建立任务连接")
        table.add_row("/tasks (或 /ls)", "列出当前所有并发运行的任务会话与状态")
        table.add_row("/switch <名称>", "在多个任务间无缝切换活跃上下文 (例如 /switch safety)")
        table.add_row("/terminal (或 /sh)", "挂载进入当前任务的原生交互式终端 (按 Ctrl+] 脱离)")
        table.add_row("/agent <名称>", "更换当前任务的 Agent 引擎 (claude / agy / codex / shell)")
        table.add_row("/status", "查看当前任务服务器的 GPU 显存、CPU、内存及 Git 状态")
        table.add_row("/broadcast <指令>", "向所有活跃任务同时广播执行命令 (如 /broadcast nvidia-smi)")
        table.add_row("/close [名称]", "关闭当前或指定任务")
        table.add_row("/servers", "管理已保存的远程服务器配置")
        table.add_row("/config", "查看或编辑当前 setting.json")
        table.add_row("/clear", "清屏")
        table.add_row("/exit (或 /quit)", "退出 CLI 终端 (后台任务保持运行)")
        console.print(table)

    def action_connect(self, arg):
        """Interactive connection flow"""
        console.print(Panel("[bold cyan]🔗 建立远程 Agent 工作区连接[/bold cyan]", border_style="cyan"))

        servers = self.config.get_servers()
        selected_server = None

        if servers:
            console.print("[bold]请选择目标服务器:[/bold]")
            for idx, s in enumerate(servers, 1):
                console.print(f"  [{idx}] [bold cyan]{s.get('name')}[/bold cyan] ({s.get('user')}@{s.get('host')}:{s.get('port', 22)})")
            console.print("  [0] 输入新的服务器地址...")

            pick = input("选择编号 [1]: ").strip() or "1"
            if pick == "0":
                selected_server = self._prompt_new_server()
            else:
                try:
                    idx = int(pick) - 1
                    if 0 <= idx < len(servers):
                        selected_server = servers[idx]
                except ValueError:
                    selected_server = self.config.get_server(pick)
        else:
            console.print("[yellow]尚未配置服务器，请录入连接信息:[/yellow]")
            selected_server = self._prompt_new_server()

        if not selected_server:
            console.print("[red]取消连接。[/red]")
            return

        # Remote dir
        default_dir = selected_server.get("default_dir") or "/workspace"
        remote_dir = input(f"远程工作目录 [{default_dir}]: ").strip() or default_dir

        # Agent type
        agents = self.config.get_agents()
        default_agent = self.config.get_settings().get("default_agent", "claude")
        console.print("\n[bold]选择接入的 Agent:[/bold]")
        console.print("  [1] [bold magenta]Claude Code[/bold magenta] (claude)")
        console.print("  [2] [bold magenta]Antigravity CLI[/bold magenta] (agy)")
        console.print("  [3] [bold magenta]Codex / LLM Agent[/bold magenta] (codex API)")
        console.print("  [4] 纯交互 Shell (bash)")

        agent_pick = input("选择 Agent [1]: ").strip() or "1"
        agent_map = {"1": "claude", "2": "agy", "3": "codex", "4": "shell"}
        agent_type = agent_map.get(agent_pick, "claude")

        # Task name
        dir_name = os.path.basename(remote_dir.rstrip("/\\")) or "task"
        task_name = input(f"任务标识名称 [{dir_name}]: ").strip() or dir_name

        console.print(f"\n正在连接 [cyan]{selected_server.get('host')}[/cyan] 并初始化任务 [bold]{task_name}[/bold]...")

        # Sync server to daemon
        api_post("/api/config/server", selected_server)

        # Launch session
        payload = {
            "name": task_name,
            "session_type": "remote_ssh",
            "server_id": selected_server.get("id"),
            "remote_dir": remote_dir,
            "startup_cmd": agent_type if agent_type != "shell" else ""
        }

        res = api_post("/api/sessions", payload)
        if not res.get("success"):
            console.print(f"[bold red]连接失败:[/bold red] {res.get('error')}")
            return

        self.active_session = res.get("session")
        console.print(Panel(
            f"[bold green]✅ 任务 [{task_name}] 已成功连接并就绪！[/bold green]\n"
            f"[dim]目标: {selected_server.get('user')}@{selected_server.get('host')}:{remote_dir}\n"
            f"Agent: {agent_type}\n"
            f"💡 直接输入自然语言需求，Agent 将在此目录自主执行；或输入 [bold yellow]/terminal[/bold yellow] 切换到交互终端。[/dim]",
            border_style="green"
        ))

    def _prompt_new_server(self):
        name = input("服务器备注名称: ").strip() or "remote-server"
        host = input("主机 IP 或域名: ").strip()
        if not host:
            return None
        port = int(input("SSH 端口 [22]: ").strip() or "22")
        user = input("用户名 [root]: ").strip() or "root"
        auth = input("认证方式 (key/password) [key]: ").strip() or "key"
        key_path = input("私钥路径 [~/.ssh/id_rsa]: ").strip() or "~/.ssh/id_rsa" if auth == "key" else ""
        password = input("密码: ").strip() if auth == "password" else ""
        default_dir = input("默认目录 [/workspace]: ").strip() or "/workspace"

        return self.config.add_or_update_server(name, host, port, user, auth, key_path, password, default_dir)

    def action_list_tasks(self):
        res = api_get("/api/sessions")
        sessions = res.get("sessions", [])
        if not sessions:
            console.print("[dim]当前没有活跃任务。使用 /connect 连接远程任务。[/dim]")
            return

        table = Table(title="🚀 运行中的任务工作区", border_style="cyan")
        table.add_column("当前", justify="center", style="bold green")
        table.add_column("任务标识", style="bold cyan")
        table.add_column("服务器", style="blue")
        table.add_column("工作目录", style="white")
        table.add_column("状态", style="green")

        for s in sessions:
            is_cur = "●" if self.active_session and s.get("session_id") == self.active_session.get("session_id") else ""
            table.add_row(
                is_cur,
                s.get("name"),
                s.get("server_name", "本地"),
                s.get("remote_dir", "/"),
                s.get("status")
            )
        console.print(table)
        console.print("[dim]使用 /switch <名称> 切换当前任务。[/dim]")

    def action_switch_task(self, name):
        res = api_get("/api/sessions")
        sessions = res.get("sessions", [])
        if not sessions:
            console.print("[dim]当前没有任务运行。[/dim]")
            return

        if not name:
            console.print("[bold]可用任务:[/bold]")
            for idx, s in enumerate(sessions, 1):
                console.print(f"  [{idx}] {s.get('name')} ({s.get('remote_dir')})")
            pick = input("输入切换的任务编号或名称: ").strip()
            try:
                idx = int(pick) - 1
                if 0 <= idx < len(sessions):
                    self.active_session = sessions[idx]
                    console.print(f"[bold green]已切换到任务: {self.active_session.get('name')}[/bold green]")
                    return
            except ValueError:
                name = pick

        for s in sessions:
            if s.get("name") == name or s.get("session_id") == name:
                self.active_session = s
                console.print(f"[bold green]已切换到任务: {s.get('name')}[/bold green]")
                return

        console.print(f"[red]找不到任务 '{name}'。[/red]")

    def action_open_terminal(self):
        if not self.active_session:
            console.print("[yellow]当前未连接到任何任务。请先使用 /connect 连接。[/yellow]")
            return

        session_id = self.active_session.get("session_id")
        name = self.active_session.get("name")
        agent = self.active_session.get("command") or "agent"
        rdir = self.active_session.get("remote_dir")

        attach_terminal(session_id, name, agent, rdir)

    def action_set_agent(self, agent_name):
        if not agent_name:
            console.print("[bold]支持的 Agent:[/bold] claude (Claude Code), agy (Antigravity), codex (LLM API), shell")
            return
        if self.active_session:
            self.active_session["command"] = agent_name
            console.print(f"[bold green]任务 [{self.active_session.get('name')}] 的 Agent 已设为: {agent_name}[/bold green]")
        else:
            self.config.update_settings({"default_agent": agent_name})
            console.print(f"[bold green]默认 Agent 已设为: {agent_name}[/bold green]")

    def action_show_status(self):
        if not self.active_session or self.active_session.get("session_type") != "remote_ssh":
            console.print("[yellow]当前无活跃远程任务。[/yellow]")
            return

        session_id = self.active_session.get("session_id")
        console.print("[cyan]正在获取远程服务器状态 (GPU / 内存 / CPU)...[/cyan]")

        # Run check via sftp / exec
        cmd = "echo '=== GPU ===' && nvidia-smi 2>/dev/null || echo '(无可用 NVIDIA GPU)'; echo '=== 内存 ===' && free -h 2>/dev/null; echo '=== 系统负载 ===' && uptime"
        api_post(f"/api/sessions/{session_id}/input", {"text": cmd + "\r\n"})
        time.sleep(0.3)
        res = api_get("/api/sessions")
        # Print status summary
        console.print(Panel(
            f"任务: [bold cyan]{self.active_session.get('name')}[/bold cyan]\n"
            f"服务器: {self.active_session.get('server_name')}\n"
            f"工作目录: {self.active_session.get('remote_dir')}\n"
            f"Agent: {self.active_session.get('command') or 'claude'}",
            title="📊 任务状态概览",
            border_style="blue"
        ))

    def action_broadcast(self, cmd):
        if not cmd:
            cmd = input("待广播的命令: ").strip()
        if not cmd:
            return
        res = api_post("/api/broadcast", {"command": cmd})
        console.print(f"[bold green]已向 {res.get('broadcasted_to', 0)} 个运行中的任务广播指令:[/bold green] {cmd}")

    def action_servers(self):
        servers = self.config.get_servers()
        if not servers:
            console.print("[dim]尚未配置远程服务器。输入 /connect 可直接添加。[/dim]")
            return

        table = Table(title="🖥️ 已配置的远程服务器", border_style="blue")
        table.add_column("备注名称", style="bold cyan")
        table.add_column("地址", style="white")
        table.add_column("用户名", style="magenta")
        table.add_column("认证方式", style="yellow")
        table.add_column("默认目录", style="dim")

        for s in servers:
            table.add_row(
                s.get("name"),
                f"{s.get('host')}:{s.get('port', 22)}",
                s.get("user", "root"),
                "私钥" if s.get("auth_type") == "key" else "密码",
                s.get("default_dir") or "/"
            )
        console.print(table)

    def action_config(self):
        s = self.config.get_settings()
        agents = self.config.get_agents()
        console.print(Panel(
            f"[bold]配置文件路径:[/bold] {self.config.config_path}\n\n"
            f"[bold cyan]默认 Agent:[/bold cyan] {s.get('default_agent', 'claude')}\n"
            f"[bold cyan]配置的 Agent 列表:[/bold cyan] {', '.join(agents.keys())}\n"
            f"[bold cyan]LLM API 模型:[/bold cyan] {agents.get('codex', {}).get('model', 'deepseek-chat')}\n"
            f"[bold cyan]LLM API Base:[/bold cyan] {agents.get('codex', {}).get('api_base')}\n"
            f"[dim]直接编辑 setting.json 即可即时生效。[/dim]",
            title="⚙️ setting.json 配置",
            border_style="cyan"
        ))

    def action_close_task(self, name):
        if not name and self.active_session:
            name = self.active_session.get("name")
        if not name:
            console.print("[yellow]请指定要关闭的任务名称。[/yellow]")
            return

        res = api_get("/api/sessions")
        sessions = res.get("sessions", [])
        for s in sessions:
            if s.get("name") == name or s.get("session_id") == name:
                api_post(f"/api/sessions/{s.get('session_id')}/close")
                console.print(f"[bold yellow]任务 [{name}] 已关闭。[/bold yellow]")
                if self.active_session and self.active_session.get("session_id") == s.get("session_id"):
                    self._sync_sessions()
                return

        console.print(f"[red]未找到任务 [{name}]。[/red]")

    def handle_natural_language_prompt(self, prompt):
        """Dispatches natural language task to the active session's Agent"""
        if not self.active_session:
            console.print("[yellow]提示: 当前未连接任何任务。请先使用 /connect 连接远程服务器工作区。[/yellow]")
            return

        session_id = self.active_session.get("session_id")
        agent_type = (self.active_session.get("command") or "claude").lower()
        rdir = self.active_session.get("remote_dir", "~")

        console.print(f"\n[dim]向任务 [{self.active_session.get('name')}] 下发 Agent 需求...[/dim]")

        if agent_type == "codex":
            # Autonomous LLM Agent Loop over SSH
            # Create task via agent engine
            res = api_post("/api/agent/create", {"session_id": session_id, "prompt": prompt})
            console.print(f"[bold green]Agent 任务已启动 (ID: {res.get('task_id')})，可通过 /terminal 观察底层动作。[/bold green]")
        else:
            # Send prompt directly into interactive agent CLI (claude / agy)
            api_post(f"/api/sessions/{session_id}/input", {"text": prompt + "\r\n"})
            console.print(f"[bold green]需求已下发至 {agent_type} 终端！输入 [bold yellow]/terminal[/bold yellow] 即可实时查看和交互。[/bold green]")


def main():
    app = AgentCliApp()
    app.run()


if __name__ == "__main__":
    main()
