"""
Argos Terminal UI Interactive Picker
Provides smooth arrow-key navigation, live previews, and modal selections.
Inspired by OpenCode, Pi, and Gum selector patterns.
"""
import sys
import os
import shutil

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
    """Reads a single keypress cross-platform."""
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


def _reset_screen():
    """Move cursor to top-left and clear from cursor down. Less flicker than full erase."""
    sys.stdout.write("\x1b[H\x1b[J")
    sys.stdout.flush()


def interactive_theme_picker(themes, current_theme_id):
    """
    Arrow-key theme picker with LIVE REAL-TIME PREVIEW.
    Compact layout designed to fit in 24-row terminals.
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
            hl = cur_theme.get("highlight", p)

            _reset_screen()

            # Header
            console.print(f"  [{p}][bold]Theme Selector[/bold][/{p}] [{d}]|[/{d}] [{d}][bold]Up[/bold]/[bold]Down[/bold] navigate  [bold]Enter[/bold] apply  [bold]Esc[/bold] cancel[/{d}]\n")

            # Theme list - compact single-column
            for idx, t in enumerate(themes):
                is_selected = (idx == selected_idx)
                is_current = (t["id"] == current_theme_id)

                if is_selected:
                    marker = f"[{p}]  > [/{p}]"
                    name_fmt = f"[{p}][bold]{t['name']}[/bold][/{p}]"
                else:
                    marker = f"[{d}]    [/{d}]"
                    name_fmt = f"[{txt}]{t['name']}[/{txt}]"

                cur_tag = f" [{s}]<=[/{s}]" if is_current else ""
                console.print(f"{marker}{name_fmt} [{d}]{t['desc']}[/{d}]{cur_tag}")

            console.print()

            # Compact live preview (7 lines total to fit 24-row terminals)
            preview = (
                f"[{p}]>[/{p}] [{txt}]What GPU resources are available?[/{txt}]\n"
                f"[{a}]>[/{a}] [{d}]Checking system resources...[/{d}]\n"
                f"  [{s}]+ NVIDIA A800-SXM4 80GB (38C, 4.2/80.0GB used)[/{s}]\n"
                f"  [{w}]! 8 GPUs available, cluster healthy[/{w}]\n"
                f"  [{e}]x 0 jobs in queue[/{e}]\n"
                f"  [{d}]Palette:[/{d}] [{p}]@[/{p}][{a}]@[/{a}][{s}]@[/{s}][{w}]@[/{w}][{e}]@[/{e}][{hl}]@[/{hl}]"
            )
            console.print(Panel(
                preview,
                title=f"[{p}] {cur_theme['name']} [/{p}]",
                border_style=cur_theme.get("border", d),
                padding=(0, 1),
                width=min(60, shutil.get_terminal_size().columns - 4),
            ))

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
        _reset_screen()


def interactive_menu_select(title, items, current_idx=0, extra_shortcuts=None, theme=None):
    """
    General arrow-key interactive selector with pagination (max 8 visible).
    """
    hide_cursor()
    p = theme["primary"] if theme else "cyan"
    a = theme["accent"] if theme else "magenta"
    s = theme["success"] if theme else "green"
    d = theme["dim"] if theme else "dim"
    txt = theme.get("text", "white") if theme else "white"

    selected_idx = max(0, min(current_idx, len(items) - 1)) if items else 0
    max_visible = 8

    try:
        while True:
            _reset_screen()
            console.print(f"  [{p}][bold]{title}[/bold][/{p}]\n")

            # Pagination window
            total = len(items)
            half = max_visible // 2
            start = max(0, min(selected_idx - half, total - max_visible))
            end = min(start + max_visible, total)

            for idx in range(start, end):
                item = items[idx]
                is_selected = (idx == selected_idx)
                marker = f"[{p}]  > [/{p}]" if is_selected else f"[{d}]    [/{d}]"
                label = item.get("label", str(item))
                desc = item.get("desc", "")
                badge = item.get("badge", "")

                label_fmt = f"[{p}][bold]{label}[/bold][/{p}]" if is_selected else f"[{txt}]{label}[/{txt}]"
                desc_fmt = f" [{d}]{desc}[/{d}]" if desc else ""
                badge_fmt = f" [{s}]{badge}[/{s}]" if badge else ""

                console.print(f"{marker}{label_fmt}{desc_fmt}{badge_fmt}")

            if total > max_visible:
                console.print(f"  [{d}]({selected_idx + 1}/{total})[/{d}]")

            console.print()
            shortcuts_hint = f"  [{d}]Up/Down navigate  Enter select  Esc cancel[/{d}]"
            if extra_shortcuts:
                parts = []
                for k, (name, _) in extra_shortcuts.items():
                    parts.append(f"[{a}]{k}[/{a}] {name}")
                shortcuts_hint += "  " + "  ".join(parts)
            console.print(shortcuts_hint)

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
        _reset_screen()
