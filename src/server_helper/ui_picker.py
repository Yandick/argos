"""
Argos Terminal UI Interactive Picker
Provides smooth arrow-key navigation (↑/↓), live previews, and modal selections
inspired by OpenCode, Pi, and Gum.
"""
import sys
import os
import time

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.text import Text
from rich.panel import Panel

console = Console()


def read_single_key():
    """
    Reads a single keypress cross-platform.
    Returns: 'up', 'down', 'left', 'right', 'enter', 'escape', 'backspace', or character.
    """
    if sys.platform == "win32":
        import msvcrt
        ch = msvcrt.getch()
        if ch in (b'\x00', b'\xe0'):
            ch2 = msvcrt.getch()
            if ch2 == b'H':
                return "up"
            elif ch2 == b'P':
                return "down"
            elif ch2 == b'K':
                return "left"
            elif ch2 == b'M':
                return "right"
            return "special"
        if ch in (b'\r', b'\n'):
            return "enter"
        if ch == b'\x1b':
            return "escape"
        if ch == b'\x08':
            return "backspace"
        if ch == b'\x03':  # Ctrl+C
            return "escape"
        try:
            return ch.decode("utf-8", errors="ignore").lower()
        except Exception:
            return ""
    else:
        import tty
        import termios
        import select
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                r, _, _ = select.select([sys.stdin], [], [], 0.05)
                if r:
                    ch2 = sys.stdin.read(1)
                    if ch2 == '[':
                        ch3 = sys.stdin.read(1)
                        if ch3 == 'A':
                            return "up"
                        elif ch3 == 'B':
                            return "down"
                        elif ch3 == 'C':
                            return "right"
                        elif ch3 == 'D':
                            return "left"
                return "escape"
            if ch in ('\r', '\n'):
                return "enter"
            if ch == '\x03':
                return "escape"
            return ch.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def hide_cursor():
    sys.stdout.write("\x1b[?25l")
    sys.stdout.flush()


def show_cursor():
    sys.stdout.write("\x1b[?25h")
    sys.stdout.flush()


def clear_screen():
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()


def interactive_theme_picker(themes, current_theme_id):
    """
    Arrow-key theme picker with LIVE REAL-TIME PREVIEW.
    As user presses Up/Down, the entire preview card renders in that exact theme.
    Enter applies, Esc cancels.
    """
    hide_cursor()
    selected_idx = 0
    for idx, t in enumerate(themes):
        if t["id"] == current_theme_id:
            selected_idx = idx
            break

    try:
        while True:
            cur_theme = themes[selected_idx]
            p = cur_theme["primary"]
            a = cur_theme["accent"]
            s = cur_theme["success"]
            w = cur_theme["warning"]
            e = cur_theme["error"]
            d = cur_theme["dim"]
            txt = cur_theme.get("text", "#ffffff")

            clear_screen()

            # 1. Header
            console.print(f"[{p}][bold]● Argos Theme Selector[/bold][/{p}] [{d}]· Press [bold]↑[/bold]/[bold]↓[/bold] to navigate, [bold]Enter[/bold] to apply, [bold]Esc[/bold] to cancel[/{d}]\n")

            # 2. Theme List
            for idx, t in enumerate(themes):
                is_selected = (idx == selected_idx)
                is_current = (t["id"] == current_theme_id)

                marker = f"[{p}][bold]❯ ◉[/bold][/{p}]" if is_selected else f"[{d}]  ○[/{d}]"
                name_fmt = f"[{p}][bold]{t['name']:<22}[/bold][/{p}]" if is_selected else f"[{txt}]{t['name']:<22}[/{txt}]"
                id_tag = f"[{a}]({t['id']})[/{a}]" if is_selected else f"[{d}]({t['id']})[/{d}]"
                cur_tag = f" [{s}][bold]● active[/bold][/{s}]" if is_current else ""

                console.print(f"  {marker} {name_fmt} {id_tag:<18} [{d}]{t['desc']}[/{d}]{cur_tag}")

            console.print()

            # 3. Live Preview Card
            # Renders sample header, sample prompt, and sample tool output using cur_theme colors
            preview_content = (
                f"[{p}][bold]● argos v0.3.0 · remote coding agent orchestrator[/bold][/{p}] [{a}]({cur_theme['name']})[/{a}]\n\n"
                f"[{d}]Prompt Preview:[/{d}]\n"
                f"[{p}]●[/{p}] [{s}]yhwu@202.38.247.29[/{s}]:[{d}]/data/yhwu[/{d}] [{a}](agy · gemini-3.8-flash)[/{a}] › [{txt}]帮我查看当前显卡状态并编写代码[/{txt}]\n\n"
                f"[{d}]Tool & Agent Action Preview:[/{d}]\n"
                f"[{a}]▸[/{a}] [{txt}]Executing:[/{txt}] [{p}]nvidia-smi --query-gpu=name,memory.used,memory.total[/{p}]\n"
                f"[{s}]● NVIDIA A800-SXM4-80GB (Used: 4.2GB / 80.0GB, Temp: 38°C)[/{s}]\n"
                f"[{w}]● Notice: GPU cluster is healthy with 8 available accelerators[/{w}]\n"
                f"[{e}]● Warning: 0 tasks in queue[/{e}]\n\n"
                f"[{d}]Color Swatch:[/{d}] [{p}]●[/{p}] [{p}]■[/{p}] [{a}]■[/{a}] [{s}]■[/{s}] [{w}]■[/{w}] [{e}]■[/{e}] [{d}]■[/{d}]"
            )

            console.print(Panel(
                preview_content,
                title=f"[{p}][bold] Live Preview: {cur_theme['name']} [/bold][/{p}]",
                border_style=p,
                padding=(1, 2)
            ))

            console.print(f"[{d}]  [↑/↓ or j/k] Select   [Enter] Save Theme   [Esc/q] Cancel[/{d}]")

            key = read_single_key()
            if key in ("up", "k"):
                selected_idx = (selected_idx - 1) % len(themes)
            elif key in ("down", "j"):
                selected_idx = (selected_idx + 1) % len(themes)
            elif key == "enter":
                return cur_theme
            elif key in ("escape", "q"):
                return None

    finally:
        show_cursor()
        clear_screen()


def interactive_menu_select(title, items, current_idx=0, extra_shortcuts=None, theme=None):
    """
    General arrow-key interactive selector with extra shortcut key support.
    extra_shortcuts: dict of char -> (action_name, callback)
    """
    hide_cursor()
    p = theme["primary"] if theme else "cyan"
    a = theme["accent"] if theme else "magenta"
    s = theme["success"] if theme else "green"
    d = theme["dim"] if theme else "dim"
    txt = theme.get("text", "white") if theme else "white"

    selected_idx = max(0, min(current_idx, len(items) - 1)) if items else 0

    try:
        while True:
            clear_screen()
            console.print(f"[{p}][bold]● {title}[/bold][/{p}]\n")

            for idx, item in enumerate(items):
                is_selected = (idx == selected_idx)
                marker = f"[{p}][bold]❯ ◉[/bold][/{p}]" if is_selected else f"[{d}]  ○[/{d}]"
                label = item.get("label", str(item))
                desc = item.get("desc", "")
                badge = item.get("badge", "")

                label_fmt = f"[{p}][bold]{label:<22}[/bold][/{p}]" if is_selected else f"[{txt}]{label:<22}[/{txt}]"
                desc_fmt = f"[{d}]{desc}[/{d}]" if desc else ""
                badge_fmt = f" [{s}]{badge}[/{s}]" if badge else ""

                console.print(f"  {marker} {label_fmt} {desc_fmt}{badge_fmt}")

            console.print()
            shortcuts_hint = "  [↑/↓] Navigate   [Enter] Select   [Esc] Cancel"
            if extra_shortcuts:
                for k, (name, _) in extra_shortcuts.items():
                    shortcuts_hint += f"   [{a}][{k}][/{a}] {name}"
            console.print(f"[{d}]{shortcuts_hint}[/{d}]")

            key = read_single_key()
            if key in ("up", "k"):
                selected_idx = (selected_idx - 1) % len(items)
            elif key in ("down", "j"):
                selected_idx = (selected_idx + 1) % len(items)
            elif key == "enter":
                return ("select", items[selected_idx], selected_idx)
            elif key in ("escape", "q"):
                return ("cancel", None, -1)
            elif extra_shortcuts and key in extra_shortcuts:
                return (extra_shortcuts[key][0], items[selected_idx], selected_idx)

    finally:
        show_cursor()
        clear_screen()
