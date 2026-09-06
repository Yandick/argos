"""
Agent Bridge & Integration
Handles invocation command building for Claude Code, agy, codex,
and provides autonomous CLI-based agent task execution with Rich formatting.
"""
import os
import sys
import json
import time
import base64
import shlex
import requests
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

AGENT_CHOICES = ["claude", "agy", "codex", "shell"]


def build_agent_cmd(agent_type, server=None, remote_dir=None):
    """
    Builds the exact shell command to launch the selected agent targeting the remote workspace.
    """
    agent = (agent_type or "claude").lower().strip()
    rdir = remote_dir or "~"

    if server:
        # Remote execution over SSH with allocated pseudo-terminal (-t)
        host = server.get("host")
        port = server.get("port", 22)
        user = server.get("user", "root")
        key_path = server.get("key_path")

        parts = ["ssh"]
        if key_path and os.path.isfile(os.path.expanduser(key_path)):
            parts += ["-i", shlex.quote(os.path.expanduser(key_path))]
        try:
            port_num = int(port)
        except (TypeError, ValueError):
            port_num = 22
        if port_num != 22:
            parts += ["-p", str(port_num)]

        agent_bin = {
            "claude": "claude",
            "agy": "agy",
            "codex": "codex",
        }.get(agent)
        # Command executed by the remote shell; rdir is quoted for the remote side.
        if agent_bin:
            remote_cmd = f"cd {shlex.quote(rdir)} && {agent_bin}"
        else:
            remote_cmd = f"cd {shlex.quote(rdir)} && (bash -l || sh)"

        # Quote host/user and the whole remote command for the local shell.
        parts += ["-t", shlex.quote(f"{user}@{host}"), shlex.quote(remote_cmd)]
        return " ".join(parts)

    else:
        # Local execution
        if agent == "claude":
            return "claude"
        elif agent == "agy":
            return "agy"
        elif agent == "codex":
            return "codex"
        else:
            return "powershell.exe -NoLogo"


def run_cli_agent_task(ssh_client, remote_dir, prompt, config, console=None):
    """
    Executes an autonomous agent task loop in the terminal with live Rich output.
    """
    if console is None:
        console = Console()

    settings = config.get_settings()
    api_key = (settings.get("api_key") or "").strip()
    base_url = settings.get("api_base") or "https://api.deepseek.com/v1"
    model = settings.get("model") or "deepseek-chat"

    console.print(Panel(f"[bold cyan]任务下发:[/bold cyan] {prompt}\n[bold blue]远程工作目录:[/bold blue] {remote_dir}", title="🤖 ServerHelper Coding Agent", border_style="cyan"))

    # Tool definitions
    tools = [
        {
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "在远程工作目录下执行命令",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Shell 命令"}
                    },
                    "required": ["command"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取远程文件内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"}
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "在远程文件中将 old_str 替换为 new_str",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                        "old_str": {"type": "string", "description": "待替换的原字符串"},
                        "new_str": {"type": "string", "description": "新字符串"}
                    },
                    "required": ["path", "old_str", "new_str"]
                }
            }
        }
    ]

    history = [
        {
            "role": "system",
            "content": f"你是一个在远程服务器（目录: {remote_dir}）上协助开发者的 Coding Agent。通过调用工具查看环境、阅读代码、修改文件并执行测试。完成目标后总结成果。"
        },
        {"role": "user", "content": prompt}
    ]

    max_steps = 10
    step = 0

    while step < max_steps:
        step += 1
        console.print(f"\n[dim]── 步骤 {step}/{max_steps} ──[/dim]")

        if api_key:
            try:
                resp = requests.post(
                    f"{base_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={"model": model, "messages": history, "tools": tools, "temperature": 0.2},
                    timeout=60
                )
                res_data = resp.json()
                if "choices" not in res_data:
                    console.print(f"[bold red]API 报错:[/bold red] {res_data.get('error', {}).get('message', '未知错误')}")
                    break

                choice = res_data["choices"][0]["message"]
                content = choice.get("content") or ""
                tool_calls = choice.get("tool_calls") or []

                if content:
                    console.print(Panel(Markdown(content), title="🤔 Agent 思考", border_style="yellow"))

                if not tool_calls:
                    console.print("[bold green]✅ Agent 已达成目标并完成任务！[/bold green]")
                    break

                history.append(choice)

                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    try:
                        fn_args = json.loads(tc["function"]["arguments"])
                    except Exception:
                        fn_args = {}

                    console.print(f"[bold yellow]⚡ 调用工具:[/bold yellow] [bold]{fn_name}[/bold]({json.dumps(fn_args, ensure_ascii=False)})")

                    # Execute tool via SSH
                    tool_output = ""
                    if fn_name == "run_command":
                        cmd = fn_args.get("command", "")
                        _, out, err = ssh_client.exec_command(cmd, cwd=remote_dir)
                        tool_output = out if out else err
                    elif fn_name == "read_file":
                        p = fn_args.get("path", "")
                        _, out, err = ssh_client.exec_command(f"cat {shlex.quote(p)}", cwd=remote_dir)
                        tool_output = out if out else err
                    elif fn_name == "edit_file":
                        p = fn_args.get("path", "")
                        old_s = fn_args.get("old_str", "")
                        new_s = fn_args.get("new_str", "")
                        # Pass the parameters as base64-encoded JSON and run a
                        # fixed Python program on the remote. This avoids any
                        # shell/Python string interpolation of untrusted content
                        # (paths, quotes, newlines) that would allow injection.
                        payload = json.dumps({"path": p, "old": old_s, "new": new_s})
                        payload_b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")
                        remote_py = (
                            "import base64,json,io,sys\n"
                            f"d=json.loads(base64.b64decode('{payload_b64}').decode('utf-8'))\n"
                            "p,o,n=d['path'],d['old'],d['new']\n"
                            "with io.open(p,'r',encoding='utf-8') as f: c=f.read()\n"
                            "if o not in c:\n"
                            "    sys.stderr.write('old_str not found\\n'); sys.exit(2)\n"
                            "c=c.replace(o,n,1)\n"
                            "with io.open(p,'w',encoding='utf-8') as f: f.write(c)\n"
                            "print('OK')\n"
                        )
                        script_b64 = base64.b64encode(remote_py.encode("utf-8")).decode("ascii")
                        run = f"python3 -c \"import base64;exec(base64.b64decode('{script_b64}').decode('utf-8'))\""
                        _, out, err = ssh_client.exec_command(run, cwd=remote_dir)
                        tool_output = "修改成功" if not err else f"修改失败: {err}"

                    console.print(Panel(tool_output[:400] + ("..." if len(tool_output) > 400 else ""), title="工具返回结果", border_style="dim"))

                    history.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": str(tool_output)
                    })

            except Exception as e:
                console.print(f"[bold red]调用异常:[/bold red] {e}")
                break
        else:
            # Guided direct tool execution if no API key
            console.print("[yellow]提示: 未检测到 API Key，执行默认远程环境探测与诊断命令:[/yellow]")
            _, out, err = ssh_client.exec_command("git status 2>/dev/null || (pwd && ls -la && whoami)", cwd=remote_dir)
            console.print(Panel(out or err, title="诊断输出", border_style="green"))
            console.print("[dim]请使用 'server-helper config --key sk-...' 配置大模型 API Key 以启用完全自主交互。[/dim]")
            break
