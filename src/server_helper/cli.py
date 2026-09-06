"""
ServerHelper CLI Main Entry Point
Supports multi-agent orchestration, remote SSH sessions, codex/claude/agy integration, and terminal attachment.
"""
import os
import sys
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from server_helper.config import Config
from server_helper.daemon import api_get, api_post, ensure_daemon_running
from server_helper.tui import attach_terminal
from server_helper.agent_bridge import AGENT_CHOICES, build_agent_cmd

console = Console()
config = Config()


def cmd_list(args):
    """List active tasks and their current state"""
    res = api_get("/api/sessions")
    if not res.get("success"):
        console.print(f"[bold red]获取任务列表失败:[/bold red] {res.get('error')}")
        return

    sessions = res.get("sessions", [])
    if not sessions:
        console.print("[dim]当前暂无运行中的任务。使用 'server-helper start <name>' 创建一个任务。[/dim]")
        return

    table = Table(title="🚀 ServerHelper 运行中的任务", border_style="cyan")
    table.add_column("任务标识", style="bold cyan")
    table.add_column("运行模式", style="magenta")
    table.add_column("服务器 / 目标", style="blue")
    table.add_column("工作目录 / 命令", style="white")
    table.add_column("状态", style="green")

    for s in sessions:
        mode_str = "远程 SSH" if s.get("session_type") == "remote_ssh" else "本地 Agent"
        srv_str = s.get("server_name", "本地")
        dir_cmd = s.get("remote_dir") or s.get("command") or "/"
        status_style = "green" if s.get("status") == "running" else "yellow"
        table.add_row(
            s.get("name"),
            mode_str,
            srv_str,
            dir_cmd,
            f"[{status_style}]{s.get('status')}[/{status_style}]"
        )

    console.print(table)


def cmd_start(args):
    """Start a new agent or SSH task"""
    name = args.name
    agent_type = args.agent or config.get_settings().get("default_agent", "claude")

    server_info = None
    session_type = "local_pty"

    if args.server:
        server_info = config.get_server(args.server)
        if not server_info:
            console.print(f"[bold red]错误:[/bold red] 找不到已保存的服务器配置 '{args.server}'。")
            console.print("请先使用 [bold cyan]server-helper server add[/bold cyan] 添加服务器，或运行 [bold cyan]server-helper server list[/bold cyan] 查看。")
            return
        session_type = "remote_ssh"

    remote_dir = args.dir or (server_info.get("default_dir") if server_info else os.getcwd())

    # Build startup command if not specified
    startup_cmd = args.cmd
    if not startup_cmd:
        if agent_type == "claude":
            startup_cmd = "claude"
        elif agent_type == "agy":
            startup_cmd = "agy"
        elif agent_type == "codex":
            startup_cmd = "codex"
        else:
            startup_cmd = ""

    console.print(f"正在启动任务 [bold cyan]{name}[/bold cyan] (Agent: [magenta]{agent_type}[/magenta], 模式: [blue]{session_type}[/blue])...")

    payload = {
        "name": name,
        "session_type": session_type,
        "remote_dir": remote_dir,
        "startup_cmd": startup_cmd,
        "local_cmd": startup_cmd,
        "cwd": remote_dir
    }

    if server_info:
        # Sync server config to daemon
        api_post("/api/config/server", server_info)
        payload["server_id"] = server_info.get("id")

    res = api_post("/api/sessions", payload)

    if not res.get("success"):
        console.print(f"[bold red]启动失败:[/bold red] {res.get('error')}")
        return

    session = res.get("session")
    session_id = session.get("session_id")
    console.print(f"[bold green]✅ 任务 {name} 已成功在后台拉起就绪！[/bold green]")

    if args.attach:
        attach_terminal(session_id, name, agent_type, remote_dir)
    else:
        console.print(f"[dim]提示: 运行 'server-helper attach {name}' 即可挂接到该任务的交互终端。[/dim]")


def cmd_attach(args):
    """Attach terminal to an active task"""
    res = api_get("/api/sessions")
    if not res.get("success"):
        console.print(f"[bold red]连接守护进程失败:[/bold red] {res.get('error')}")
        return

    sessions = res.get("sessions", [])
    target = None
    for s in sessions:
        if s.get("name") == args.name or s.get("session_id") == args.name:
            target = s
            break

    if not target:
        console.print(f"[bold red]错误:[/bold red] 找不到运行中的任务 '{args.name}'。")
        console.print("可用任务列表:")
        cmd_list(None)
        return

    attach_terminal(
        target.get("session_id"),
        target.get("name"),
        target.get("command") or "agent",
        target.get("remote_dir")
    )


def cmd_exec(args):
    """Run an autonomous agent prompt on the task or send an input string"""
    res = api_get("/api/sessions")
    sessions = res.get("sessions", [])
    target = None
    for s in sessions:
        if s.get("name") == args.name:
            target = s
            break

    if not target:
        console.print(f"[bold red]错误:[/bold red] 任务 '{args.name}' 未在运行。")
        return

    session_id = target.get("session_id")
    console.print(f"向任务 [bold cyan]{args.name}[/bold cyan] 下发指令: {args.prompt}")

    # Send input or trigger agent task
    r = api_post(f"/api/sessions/{session_id}/input", {"text": args.prompt + "\r\n"})
    if r.get("success"):
        console.print("[bold green]指令已发送至任务终端！[/bold green]")
    else:
        console.print(f"[red]发送失败: {r.get('error')}[/red]")


def cmd_broadcast(args):
    """Broadcast a command to all active tasks"""
    res = api_post("/api/broadcast", {"command": args.command})
    if res.get("success"):
        console.print(f"[bold green]已向 {res.get('broadcasted_to', 0)} 个活跃任务广播指令:[/bold green] {args.command}")
    else:
        console.print(f"[red]广播失败: {res.get('error')}[/red]")


def cmd_stop(args):
    """Stop a task session"""
    res = api_get("/api/sessions")
    sessions = res.get("sessions", [])
    target = None
    for s in sessions:
        if s.get("name") == args.name or s.get("session_id") == args.name:
            target = s
            break

    if not target:
        console.print(f"[dim]任务 '{args.name}' 未在运行。[/dim]")
        return

    r = api_post(f"/api/sessions/{target.get('session_id')}/close")
    if r.get("success"):
        console.print(f"[bold yellow]任务 '{args.name}' 已停止并释放资源。[/bold yellow]")
    else:
        console.print(f"[red]停止任务失败: {r.get('error')}[/red]")


def cmd_server(args):
    """Manage server profiles"""
    action = args.action

    if action in ("list", "ls"):
        servers = config.get_servers()
        if not servers:
            console.print("[dim]暂无配置的服务器。使用 'server-helper server add' 添加。[/dim]")
            return

        table = Table(title="🖥️ 已配置的远程服务器", border_style="blue")
        table.add_column("标识名称", style="bold cyan")
        table.add_column("连接地址", style="white")
        table.add_column("登录用户", style="magenta")
        table.add_column("认证方式", style="yellow")
        table.add_column("默认目录", style="dim")

        for s in servers:
            table.add_row(
                s.get("name"),
                f"{s.get('host')}:{s.get('port', 22)}",
                s.get("user", "root"),
                "SSH 私钥" if s.get("auth_type") == "key" else "密码",
                s.get("default_dir") or "/"
            )
        console.print(table)

    elif action == "add":
        if args.name and args.host:
            name = args.name
            host = args.host
            port = args.port or 22
            user = args.user or "root"
            auth_type = args.auth or "key"
            key_path = args.key or os.path.expanduser("~/.ssh/id_rsa")
            password = args.password or ""
            default_dir = args.dir or ""
        else:
            name = args.name or Prompt.ask("服务器备注名称 (如 gpu-server)")
            host = args.host or Prompt.ask("主机 IP 或域名")
            port = args.port or int(Prompt.ask("SSH 端口", default="22"))
            user = args.user or Prompt.ask("登录用户名", default="root")
            auth_type = args.auth or Prompt.ask("认证方式 (key/password)", default="key")
            key_path = args.key or (Prompt.ask("私钥路径", default="~/.ssh/id_rsa") if auth_type == "key" else "")
            password = args.password or (Prompt.ask("密码", password=True) if auth_type == "password" else "")
            default_dir = args.dir or Prompt.ask("默认工作目录", default="/root/workspace")

        s = config.add_or_update_server(name, host, port, user, auth_type, key_path, password, default_dir)
        api_post("/api/config/server", s)
        console.print(f"[bold green]✅ 服务器 '{s['name']}' 已成功保存！[/bold green]")

    elif action in ("remove", "rm"):
        if not args.name:
            console.print("[red]请提供要删除的服务器名称: server-helper server remove <name>[/red]")
            return
        ok = config.remove_server(args.name)
        if ok:
            console.print(f"[bold green]已删除服务器配置 '{args.name}'。[/bold green]")
        else:
            console.print(f"[red]找不到服务器 '{args.name}'。[/red]")


def cmd_config(args):
    """View or update settings"""
    settings = config.get_settings()

    if args.key:
        config.update_settings({"api_key": args.key})
        console.print("[bold green]API Key 已更新！[/bold green]")
    if args.base:
        config.update_settings({"api_base": args.base})
        console.print(f"[bold green]API Base URL 已更新为: {args.base}[/bold green]")
    if args.model:
        config.update_settings({"model": args.model})
        console.print(f"[bold green]Model 已更新为: {args.model}[/bold green]")
    if args.agent:
        config.update_settings({"default_agent": args.agent})
        console.print(f"[bold green]默认 Agent 已更新为: {args.agent}[/bold green]")

    s = config.get_settings()
    console.print(Panel(
        f"[bold cyan]默认 Agent:[/bold cyan] {s.get('default_agent', 'claude')}\n"
        f"[bold cyan]API Base:[/bold cyan] {s.get('api_base')}\n"
        f"[bold cyan]Model:[/bold cyan] {s.get('model')}\n"
        f"[bold cyan]API Key:[/bold cyan] {'******' if s.get('api_key') else '[dim](未配置)[/dim]'}",
        title="⚙️ ServerHelper 配置信息",
        border_style="cyan"
    ))


def cmd_web(args):
    """Launch the Web Dashboard"""
    console.print("[bold cyan]正在启动 ServerHelper Web 界面...[/bold cyan]")
    import app
    app.run_server(port=args.port or 8765, open_browser=not args.no_browser)


def cmd_dashboard():
    """Interactive CLI Home Dashboard"""
    console.print(Panel(
        "[bold cyan]ServerHelper - 本地 Agent 远程多任务工作台 (CLI 版本)[/bold cyan]\n"
        "[dim]聚合管理本地及远程 Coding Agent (Claude Code / agy / codex) 并发任务[/dim]",
        border_style="cyan"
    ))

    cmd_list(None)

    console.print("\n[bold]可用命令快捷方式:[/bold]")
    console.print("  1. [bold cyan]server-helper start <name> --server <srv> --dir <path> --agent <claude|agy|codex>[/bold cyan] : 启动任务")
    console.print("  2. [bold cyan]server-helper attach <name>[/bold cyan] : 连接任务终端 (按 Ctrl+] 脱离)")
    console.print("  3. [bold cyan]server-helper exec <name> \"<prompt>\"[/bold cyan] : 向任务终端下发指令")
    console.print("  4. [bold cyan]server-helper broadcast \"<cmd>\"[/bold cyan] : 全局多任务广播指令")
    console.print("  5. [bold cyan]server-helper server add/list[/bold cyan] : 远程服务器管理")
    console.print("  6. [bold cyan]server-helper web[/bold cyan] : 打开 Web 网页工作台")


def main():
    parser = argparse.ArgumentParser(
        prog="server-helper",
        description="ServerHelper - Lightweight Multi-Agent & Remote SSH Orchestrator (Claude Code, agy, codex)"
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # list
    p_list = subparsers.add_parser("list", aliases=["ls"], help="列出所有活跃任务")
    p_list.set_defaults(func=cmd_list)

    # start
    p_start = subparsers.add_parser("start", aliases=["run"], help="启动新任务")
    p_start.add_argument("name", help="任务标识名称 (如 rec-pipeline, safety-eval)")
    p_start.add_argument("--server", "-s", help="远程服务器名称或 IP")
    p_start.add_argument("--dir", "-d", help="远程或本地工作目录")
    p_start.add_argument("--agent", "-a", choices=AGENT_CHOICES, default="claude", help="Agent 类型 (claude/agy/codex/shell)")
    p_start.add_argument("--cmd", "-c", help="自定义启动指令")
    p_start.add_argument("--attach", action="store_true", help="启动后立即挂接到终端")
    p_start.set_defaults(func=cmd_start)

    # attach
    p_attach = subparsers.add_parser("attach", aliases=["a"], help="挂接到任务终端")
    p_attach.add_argument("name", help="任务名称")
    p_attach.set_defaults(func=cmd_attach)

    # exec
    p_exec = subparsers.add_parser("exec", aliases=["x"], help="向任务下发指令")
    p_exec.add_argument("name", help="任务名称")
    p_exec.add_argument("prompt", help="自然语言需求指令")
    p_exec.set_defaults(func=cmd_exec)

    # broadcast
    p_bc = subparsers.add_parser("broadcast", aliases=["b"], help="向所有运行中的任务广播命令")
    p_bc.add_argument("command", help="待广播命令 (如 nvidia-smi 或 git pull)")
    p_bc.set_defaults(func=cmd_broadcast)

    # stop
    p_stop = subparsers.add_parser("stop", aliases=["kill"], help="停止任务")
    p_stop.add_argument("name", help="任务名称")
    p_stop.set_defaults(func=cmd_stop)

    # server
    p_srv = subparsers.add_parser("server", help="管理远程服务器配置")
    p_srv.add_argument("action", choices=["list", "ls", "add", "remove", "rm"], help="操作")
    p_srv.add_argument("name", nargs="?", help="服务器名称")
    p_srv.add_argument("--host", help="主机 IP 或域名")
    p_srv.add_argument("--port", type=int, default=22, help="SSH 端口")
    p_srv.add_argument("--user", default="root", help="SSH 用户名")
    p_srv.add_argument("--auth", choices=["key", "password"], default="key", help="认证方式")
    p_srv.add_argument("--key", help="私钥路径")
    p_srv.add_argument("--password", help="登录密码")
    p_srv.add_argument("--dir", help="默认基准目录")
    p_srv.set_defaults(func=cmd_server)

    # config
    p_cfg = subparsers.add_parser("config", help="查看或修改全局配置")
    p_cfg.add_argument("--key", help="设置 API Key")
    p_cfg.add_argument("--base", help="设置 API Base URL")
    p_cfg.add_argument("--model", help="设置模型名称")
    p_cfg.add_argument("--agent", choices=AGENT_CHOICES, help="设置默认 Agent")
    p_cfg.set_defaults(func=cmd_config)

    # web
    p_web = subparsers.add_parser("web", help="启动 Web 网页版仪表盘")
    p_web.add_argument("--port", type=int, default=8765, help="Web 端口")
    p_web.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    p_web.set_defaults(func=cmd_web)

    args = parser.parse_args()

    if not args.command:
        from server_helper.agent_cli import AgentCliApp
        app = AgentCliApp()
        app.run()
    else:
        args.func(args)


if __name__ == "__main__":
    main()
