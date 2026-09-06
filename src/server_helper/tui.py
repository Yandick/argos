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

    # Read keystrokes from stdin (platform-specific raw input)
    try:
        if sys.platform == "win32":
            _read_keys_windows(ws, stop_event)
        else:
            _read_keys_posix(ws, stop_event)
    except Exception as e:
        console.print(f"\n[red]输入流异常: {e}[/red]")
    finally:
        stop_event.set()
        try:
            ws.close()
        except Exception:
            pass


# Windows special-key (0x00 / 0xe0 prefix) second byte -> ANSI escape sequence
_WIN_ARROW_MAP = {
    "H": "\x1b[A",  # Up
    "P": "\x1b[B",  # Down
    "M": "\x1b[C",  # Right
    "K": "\x1b[D",  # Left
    "G": "\x1b[H",  # Home
    "O": "\x1b[F",  # End
    "S": "\x1b[3~",  # Delete
    "I": "\x1b[5~",  # PgUp
    "Q": "\x1b[6~",  # PgDn
}


def _read_keys_windows(ws, stop_event):
    import msvcrt
    while not stop_event.is_set():
        if msvcrt.kbhit():
            # getwch returns a Unicode str (correct for non-ASCII / IME input)
            ch = msvcrt.getwch()
            if ch == "\x1d":  # Ctrl+]
                console.print("\n[bold yellow][ServerHelper] 已脱离会话，任务仍在后台持续运行。[/bold yellow]")
                break
            if ch in ("\x00", "\xe0"):  # special / arrow key prefix
                ch2 = msvcrt.getwch() if msvcrt.kbhit() else ""
                seq = _WIN_ARROW_MAP.get(ch2)
                if seq is None:
                    continue  # ignore unmapped function keys
                try:
                    ws.send(seq)
                except Exception:
                    break
            else:
                try:
                    ws.send(ch)
                except Exception:
                    break
        else:
            time.sleep(0.01)


def _read_keys_posix(ws, stop_event):
    import select
    import termios
    import tty
    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while not stop_event.is_set():
            r, _, _ = select.select([sys.stdin], [], [], 0.05)
            if not r:
                continue
            ch = sys.stdin.read(1)
            if not ch:
                break
            if ch == "\x1d":  # Ctrl+]
                console.print("\n[bold yellow][ServerHelper] 已脱离会话，任务仍在后台持续运行。[/bold yellow]")
                break
            try:
                ws.send(ch)
            except Exception:
                break
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
        except Exception:
            pass
