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
    "/server",
    "/servers",
    "/connect",
    "/tasks",
    "/switch",
    "/terminal",
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

pt_style = Style.from_dict({
    'prompt': '#6366f1 bold',
    'badge': '#10b981 bold',
})

BANNER = r"""
 [bold cyan]  █████╗ ██████╗  ██████╗  ██████╗ ███████╗[/bold cyan]
 [bold cyan] ██╔══██╗██╔══██╗██╔════╝ ██╔═══██╗██╔════╝[/bold cyan]
 [bold cyan] ███████║██████╔╝██║  ███╗██║   ██║███████╗[/bold cyan]
 [bold cyan] ██╔══██║██╔══██╗██║   ██║██║   ██║╚════██║[/bold cyan]
 [bold cyan] ██║  ██║██║  ██║╚██████╔╝╚██████╔╝███████║[/bold cyan]
 [bold cyan] ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚══════╝[/bold cyan]
 [dim]⚡ [bold]ARGOS[/bold] (Ἄργος) v0.3.0 | All-Seeing Multi-Agent Remote Orchestrator[/dim]
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
            console.print(f"[red]未知指令: {cmd}。输入 /help 查看所有可用命令。[/red]")

    def show_help(self):
        table = Table(title="📖 Argos Agent CLI 指令表", border_style="cyan")
        table.add_column("命令", style="bold yellow")
        table.add_column("说明", style="white")

        table.add_row("/server (或 /connect)", "类似 /model 列出服务器选择、挑选远程目录并快速连接")
        table.add_row("/server add", "在终端中交互式录入新的 SSH 服务器与密码/私钥并保存")
        table.add_row("/server rm", "从 setting.json 中删除指定服务器配置")
        table.add_row("/tasks (或 /ls)", "列出当前所有并发运行的任务会话与状态")
        table.add_row("/switch <名称>", "在多个任务间无缝切换活跃上下文 (例如 /switch safety)")
        table.add_row("/terminal (或 /sh)", "挂载进入当前任务的原生交互式终端 (按 Ctrl+] 脱离)")
        table.add_row("/agent <名称>", "更换当前任务的 Agent 引擎 (claude / agy / codex / shell)")
        table.add_row("/status", "查看当前任务服务器的 GPU 显存、CPU、内存及 Git 状态")
        table.add_row("/broadcast <指令>", "向所有活跃任务同时广播执行命令 (如 /broadcast nvidia-smi)")
        table.add_row("/close [名称]", "关闭当前或指定任务")
        table.add_row("/config", "查看当前 setting.json 路径与配置")
        table.add_row("/clear", "清屏")
        table.add_row("/exit (或 /quit)", "退出 CLI 终端 (后台任务保持运行)")
        console.print(table)

    def action_connect(self, arg):
        """Interactive connection flow (alias to /server)"""
        self.action_servers(arg)

    def action_servers(self, arg=""):
        """
        Interactive Server Manager like /model in coding agents.
        Lists all servers, lets user pick server by number, select remote directory, and connect.
        Also supports adding and removing servers directly from terminal.
        """
        arg = (arg or "").strip()
        arg_lower = arg.lower()

        if arg_lower == "add":
            new_srv = self._prompt_new_server()
            if new_srv:
                console.print(f"[bold green]✅ 服务器 '{new_srv.get('name')}' 已保存至 setting.json！[/bold green]")
                try:
                    ask_conn = input(f"是否立即连接到 {new_srv.get('name')} 并选择目录？(Y/n): ").strip().lower()
                    if ask_conn != "n":
                        self._connect_to_server(new_srv)
                except (KeyboardInterrupt, EOFError):
                    pass
            return

        if arg_lower in ("rm", "remove", "del"):
            self._prompt_remove_server()
            return

        is_interactive = sys.stdin.isatty()
        servers = self.config.get_servers()
        if not servers:
            console.print(Panel(
                "[yellow]尚未配置任何远程服务器。[/yellow]\n\n"
                "[dim]• 您可以在此交互式录入常用 SSH 服务器与密码，将自动保存到 setting.json。\n"
                "• 也可以直接用文本编辑器打开 setting.json 填入平时用的服务器。[/dim]",
                title="🖥️ 远程服务器配置",
                border_style="yellow"
            ))
            if not is_interactive:
                return
            try:
                ask_add = input("是否现在添加一个新服务器？(Y/n): ").strip().lower()
                if ask_add != "n":
                    new_srv = self._prompt_new_server()
                    if new_srv:
                        console.print(f"[bold green]✅ 服务器 '{new_srv.get('name')}' 已保存至 setting.json！[/bold green]")
                        ask_conn = input(f"是否立即连接到 {new_srv.get('name')} 并选择目录？(Y/n): ").strip().lower()
                        if ask_conn != "n":
                            self._connect_to_server(new_srv)
            except (KeyboardInterrupt, EOFError):
                pass
            return

        if arg_lower in ("ls", "list"):
            self._print_servers_table(servers)
            return

        # List servers like /model in coding agents
        self._print_servers_table(servers)
        console.print(f"[dim]快捷操作: [bold yellow][1-{len(servers)}][/bold yellow] 选择连接 | [bold green][a][/bold green] 添加新服务器 | [bold red][d][/bold red] 删除服务器 | [bold][q][/bold] 退出[/dim]\n")

        if not is_interactive:
            return

        selected_server = None
        if arg:
            try:
                idx = int(arg) - 1
                if 0 <= idx < len(servers):
                    selected_server = servers[idx]
            except ValueError:
                selected_server = self.config.get_server(arg)

        if not selected_server:
            try:
                choice = input("👉 请输入服务器编号或操作 [1]: ").strip() or "1"
                if choice.lower() in ("q", "quit", "cancel"):
                    return
                elif choice.lower() in ("a", "add"):
                    new_srv = self._prompt_new_server()
                    if new_srv:
                        console.print(f"[bold green]✅ 服务器 '{new_srv.get('name')}' 已保存至 setting.json！[/bold green]")
                        ask_conn = input(f"是否立即连接到 {new_srv.get('name')} 并选择目录？(Y/n): ").strip().lower()
                        if ask_conn != "n":
                            self._connect_to_server(new_srv)
                    return
                elif choice.lower() in ("d", "del", "remove", "rm"):
                    self._prompt_remove_server()
                    return
                else:
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(servers):
                            selected_server = servers[idx]
                        else:
                            console.print(f"[red]无效编号: {choice}[/red]")
                            return
                    except ValueError:
                        selected_server = self.config.get_server(choice)
                        if not selected_server:
                            console.print(f"[red]找不到服务器: {choice}[/red]")
                            return
            except (KeyboardInterrupt, EOFError):
                return

        self._connect_to_server(selected_server)

    def _print_servers_table(self, servers):
        table = Table(title="🖥️ 已配置的远程服务器 (类似 /model 列表)", border_style="blue")
        table.add_column("编号", justify="center", style="bold yellow")
        table.add_column("服务器名称", style="bold cyan")
        table.add_column("连接地址", style="white")
        table.add_column("用户名", style="magenta")
        table.add_column("认证方式", style="yellow")
        table.add_column("默认工作目录", style="white")

        for idx, s in enumerate(servers, 1):
            auth_desc = "私钥" if s.get("auth_type") == "key" else "密码"
            table.add_row(
                f"[{idx}]",
                s.get("name"),
                f"{s.get('host')}:{s.get('port', 22)}",
                s.get("user", "root"),
                auth_desc,
                s.get("default_dir") or "/"
            )
        console.print(table)

    def _connect_to_server(self, server_info):
        console.print(Panel(
            f"目标服务器: [bold cyan]{server_info.get('name')}[/bold cyan] ({server_info.get('user')}@{server_info.get('host')}:{server_info.get('port', 22)})\n"
            f"认证方式: [yellow]{'私钥' if server_info.get('auth_type') == 'key' else '密码'}[/yellow]",
            title="🔗 准备建立连接",
            border_style="cyan"
        ))

        # 1. Directory selection
        default_dir = server_info.get("default_dir") or "/workspace"
        console.print(f"[bold]📁 请选择或输入远程工作目录:[/bold]")
        console.print(f"   [dim]直接回车使用默认目录: [bold green]{default_dir}[/bold green]，或输入自定义目录 (如 /data/rec 或 /workspace/safety)[/dim]")
        try:
            remote_dir = input(f"远程工作目录 [{default_dir}]: ").strip() or default_dir
        except (KeyboardInterrupt, EOFError):
            console.print("[yellow]已取消连接。[/yellow]")
            return

        # 2. Agent selection
        agents = self.config.get_agents()
        default_agent = self.config.get_settings().get("default_agent", "claude")
        console.print(f"\n[bold]🤖 请选择挂载的 Agent 引擎:[/bold]")
        console.print(f"  [1] [bold magenta]Claude Code[/bold magenta] (claude) - 推荐")
        console.print(f"  [2] [bold magenta]Antigravity CLI[/bold magenta] (agy)")
        console.print(f"  [3] [bold magenta]Codex / LLM API[/bold magenta] (基于 DeepSeek/OpenAI 自主工具循环)")
        console.print(f"  [4] 原生终端 (shell / bash)")

        try:
            agent_pick = input("选择 Agent [1]: ").strip() or "1"
        except (KeyboardInterrupt, EOFError):
            console.print("[yellow]已取消连接。[/yellow]")
            return
        agent_map = {"1": "claude", "2": "agy", "3": "codex", "4": "shell"}
        agent_type = agent_map.get(agent_pick, "claude")

        # 3. Task Name
        dir_name = os.path.basename(remote_dir.rstrip("/\\")) or "task"
        try:
            task_name = input(f"\n🏷️ 任务标识名称 [{dir_name}]: ").strip() or dir_name
        except (KeyboardInterrupt, EOFError):
            task_name = dir_name

        console.print(f"\n[cyan]正在连接 {server_info.get('host')} 并启动任务 [{task_name}]...[/cyan]")

        # Sync server info to daemon
        api_post("/api/config/server", server_info)

        # Launch session
        payload = {
            "name": task_name,
            "session_type": "remote_ssh",
            "server_id": server_info.get("id"),
            "remote_dir": remote_dir,
            "startup_cmd": agent_type if agent_type != "shell" else ""
        }

        res = api_post("/api/sessions", payload)
        if not res.get("success"):
            console.print(f"[bold red]❌ 连接失败:[/bold red] {res.get('error')}")
            return

        self.active_session = res.get("session")
        console.print(Panel(
            f"[bold green]✅ 任务 [{task_name}] 已成功连接并就绪！[/bold green]\n\n"
            f"[bold]目标节点:[/bold] {server_info.get('user')}@{server_info.get('host')}:{server_info.get('port', 22)}\n"
            f"[bold]工作目录:[/bold] [cyan]{remote_dir}[/cyan]\n"
            f"[bold]Agent 引擎:[/bold] [magenta]{agent_type}[/magenta]\n\n"
            f"💡 [dim]操作指引:[/dim]\n"
            f"  • 直接输入自然语言需求，Agent 将在此目录下自主排查代码与执行任务。\n"
            f"  • 输入 [bold yellow]/terminal[/bold yellow] (或 /sh) 随时挂接进入交互式终端 (按 Ctrl+] 脱离返回)。\n"
            f"  • 输入 [bold yellow]/server[/bold yellow] 可继续连接其他机器或目录并发开启更多任务！",
            title="🚀 任务已就绪",
            border_style="green"
        ))

    def _prompt_new_server(self):
        console.print("\n[bold cyan]➕ 录入新的远程 SSH 服务器配置:[/bold cyan]")
        try:
            name = input("服务器备注名称 (如 gpu-server-1): ").strip() or "remote-server"
            host = input("主机 IP 或域名: ").strip()
            if not host:
                console.print("[red]主机 IP 不能为空，已取消。[/red]")
                return None
            port_input = input("SSH 端口 [22]: ").strip() or "22"
            port = int(port_input) if port_input.isdigit() else 22
            user = input("登录用户名 [root]: ").strip() or "root"
            auth = input("认证方式 (password/key) [password]: ").strip().lower() or "password"

            password = ""
            key_path = ""
            if auth in ("key", "k"):
                auth_type = "key"
                key_path = input("私钥路径 [~/.ssh/id_rsa]: ").strip() or "~/.ssh/id_rsa"
            else:
                auth_type = "password"
                password = input("SSH 登录密码: ").strip()

            default_dir = input("默认工作目录 [/workspace]: ").strip() or "/workspace"

            return self.config.add_or_update_server(name, host, port, user, auth_type, key_path, password, default_dir)
        except (KeyboardInterrupt, EOFError):
            console.print("[yellow]已取消添加。[/yellow]")
            return None

    def _prompt_remove_server(self):
        servers = self.config.get_servers()
        if not servers:
            console.print("[dim]当前没有可删除的服务器。[/dim]")
            return
        console.print("\n[bold red]🗑️ 删除服务器配置:[/bold red]")
        for idx, s in enumerate(servers, 1):
            console.print(f"  [{idx}] [cyan]{s.get('name')}[/cyan] ({s.get('user')}@{s.get('host')})")
        try:
            choice = input("请输入要删除的服务器编号或名称 (输入 q 取消): ").strip()
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
                self.config.remove_server(target.get("id"))
                console.print(f"[bold green]✅ 已成功从 setting.json 删除服务器 '{target.get('name')}'。[/bold green]")
            else:
                console.print(f"[red]找不到服务器 '{choice}'。[/red]")
        except (KeyboardInterrupt, EOFError):
            return

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
