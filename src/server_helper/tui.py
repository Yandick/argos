"""
Interactive Terminal & Attach Engine for ServerHelper
Connects current terminal directly to active background task over WebSocket.
"""
import sys
import time
import shutil
import threading
import websocket
from rich.console import Console
from rich.panel import Panel

console = Console()


def attach_terminal(session_id, task_name, agent_type="claude", remote_dir=None):
    """
    Attaches the current terminal window to an active task session via WebSocket.
    Keystrokes are sent in real time with 0ms latency.
    Pressing Ctrl+] detaches back to CLI without closing the task.
    """
    ws_url = f"ws://127.0.0.1:8765/ws/terminal/{session_id}"

    try:
        ws = websocket.create_connection(ws_url, timeout=5)
    except Exception as e:
        console.print(f"[bold red]无法连接到任务终端:[/bold red] {e}")
        return

    cols, rows = shutil.get_terminal_size((120, 30))
    ws.send(f'{{"type": "resize", "cols": {cols}, "rows": {rows}}}')

    console.print(Panel(
        f"[bold green]已挂载任务终端:[/bold green] [bold]{task_name}[/bold]\n"
        f"[dim]Agent: {agent_type} | 目录: {remote_dir or '/'}\n"
        f"快捷键: 按 [bold yellow]Ctrl + ][/bold yellow] 可随时脱离当前任务返回终端 (任务将在后台继续运行)[/dim]",
        border_style="green"
    ))

    stop_event = threading.Event()

    def reader_loop():
        while not stop_event.is_set():
            try:
                data = ws.recv()
                if not data:
                    break
                sys.stdout.write(data)
                sys.stdout.flush()
            except Exception:
                break
        stop_event.set()

    t = threading.Thread(target=reader_loop, daemon=True)
    t.start()

    # Read keystrokes from stdin
    try:
        import msvcrt
        while not stop_event.is_set():
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                # Check for Ctrl+] (ASCII 29 / 0x1d)
                if ch == b'\x1d':
                    console.print("\n[bold yellow][ServerHelper] 已脱离会话，任务仍在后台持续运行。[/bold yellow]")
                    break
                try:
                    ws.send(ch.decode("latin1"))
                except Exception:
                    break
            else:
                time.sleep(0.01)
    except Exception as e:
        console.print(f"\n[red]输入流异常: {e}[/red]")
    finally:
        stop_event.set()
        try:
            ws.close()
        except Exception:
            pass
