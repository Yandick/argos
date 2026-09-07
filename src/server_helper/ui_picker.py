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


def _stdin_interactive():
    """True only when raw single-key input can actually be read.

    The pickers block on msvcrt.getch() / termios reads; in non-TTY contexts
    (piped stdin, CI, automated tests) they would hang forever. Callers fall
    back to a one-shot non-interactive listing when this returns False.
    """
    try:
        return bool(sys.stdin.isatty())
    except Exception:
        return False


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
    if not _stdin_interactive():
        console.print("  Available themes (interactive picker needs a TTY):")
        for t in themes:
            cur = " [green]<=[/green]" if t["id"] == current_theme_id else ""
            console.print(f"    {t['id']:<20} {t['name']}{cur}")
        console.print("  [dim]Use /theme <name> to switch directly.[/dim]")
        return None

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
    if not _stdin_interactive():
        # Non-TTY fallback: print the list once instead of blocking forever
        # on raw key reads (pipes, CI, automated tests).
        console.print(f"  [bold]{title}[/bold]")
        for it in items:
            if isinstance(it, dict):
                label = str(it.get("label", ""))
                desc = str(it.get("desc", ""))
                badge = str(it.get("badge", ""))
            else:
                label, desc, badge = str(it), "", ""
            console.print(f"    {label:<22} [dim]{desc}[/dim] {badge}".rstrip())
        console.print("  [dim](non-interactive terminal: pass the choice as an argument instead)[/dim]")
        return ("cancel", None, -1)

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

            visible_items = items[start:end]
            col_w = max((len(str(it.get("label", it))) for it in visible_items), default=12) + 2

            for idx in range(start, end):
                item = items[idx]
                is_selected = (idx == selected_idx)
                marker = f"[{p}]  > [/{p}]" if is_selected else f"[{d}]    [/{d}]"
                label = item.get("label", str(item))
                desc = item.get("desc", "")
                badge = item.get("badge", "")

                lbl_padded = f"{label:<{col_w}}"
                label_fmt = f"[{p}][bold]{lbl_padded}[/bold][/{p}]" if is_selected else f"[{txt}]{lbl_padded}[/{txt}]"
                desc_fmt = f"[{d}]{desc:<32}[/{d}]" if desc else ""
                badge_col = s if item.get("installed", True) else d
                badge_fmt = f" [{badge_col}]{badge}[/{badge_col}]" if badge else ""

                console.print(f"{marker}{label_fmt} {desc_fmt}{badge_fmt}")

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


def interactive_dir_picker(
    initial_dir,
    list_dirs_fn,
    is_remote=False,
    recent_dirs=None,
    theme=None,
    title=None,
):
    """
    Humane, arrow-key navigable directory browser.
    Supports:
      - Drilled-down folder navigation (Enter on a folder)
      - Immediate selection of current directory ([✓] item, or pressing 'c' or 's' or Space)
      - Going up to parent directory ('..' item, or pressing 'u' or Backspace or Left)
      - Quick jumping to recent workspaces
      - Custom path entry ('[✎] Type path' item, or pressing 't')
      - Safe cancellation (Esc or 'q')
    """
    import posixpath

    if not _stdin_interactive():
        shown = initial_dir or os.getcwd()
        console.print(f"  {title or 'Workspace directory'}: [bold]{shown}[/bold]")
        console.print("  [dim](non-interactive terminal: directory picker unavailable — pass a path directly, e.g. /cd <path>)[/dim]")
        return None

    hide_cursor()
    p = theme["primary"] if theme else "cyan"
    a = theme["accent"] if theme else "magenta"
    s = theme["success"] if theme else "green"
    w = theme["warning"] if theme else "yellow"
    e = theme["error"] if theme else "red"
    d = theme["dim"] if theme else "dim"
    txt = theme.get("text", "white") if theme else "white"

    # Determine path style
    if is_remote or (initial_dir and str(initial_dir).startswith("/")):
        pmod = posixpath
        sep = "/"
        curr_dir = initial_dir or "/"
    else:
        pmod = os.path
        sep = os.sep
        curr_dir = os.path.abspath(initial_dir) if initial_dir else os.getcwd()

    selected_idx = 0
    err_msg = ""
    max_visible = 8

    def get_parent(path):
        cleaned = str(path).rstrip("/\\")
        if not cleaned:
            return "/" if pmod == posixpath else path
        parent = pmod.dirname(cleaned)
        if not parent or parent == cleaned:
            if pmod == posixpath:
                return "/"
            return cleaned + sep if not cleaned.endswith(sep) else cleaned
        return parent

    try:
        while True:
            # 1. Fetch subdirectories
            try:
                raw_dirs = list_dirs_fn(curr_dir)
                if isinstance(raw_dirs, list):
                    if raw_dirs and isinstance(raw_dirs[0], dict) and "error" in raw_dirs[0]:
                        err_msg = str(raw_dirs[0]["error"])
                        subdirs = []
                    else:
                        subdirs = []
                        for item in raw_dirs:
                            if isinstance(item, dict):
                                if item.get("is_dir") and item.get("name") not in (".", ".."):
                                    subdirs.append(item["name"])
                            elif isinstance(item, str) and item not in (".", ".."):
                                subdirs.append(item)
                        subdirs.sort(key=str.lower)
                        err_msg = ""
                else:
                    subdirs = []
            except Exception as ex:
                subdirs = []
                err_msg = str(ex)

            parent_dir = get_parent(curr_dir)
            is_at_root = (parent_dir == curr_dir)

            # 2. Build items list
            items = []
            # Option 0: Confirm current directory
            items.append({
                "type": "confirm",
                "label": "[✓] Select this directory",
                "desc": curr_dir,
                "badge": "select",
                "path": curr_dir
            })

            # Option 1: Go up
            if not is_at_root:
                items.append({
                    "type": "up",
                    "label": "📁 ..",
                    "desc": f"Parent: {parent_dir}",
                    "badge": "up",
                    "path": parent_dir
                })

            # Option 2..N: Recent workspaces (if any, excluding current)
            if recent_dirs:
                for r in recent_dirs[:3]:
                    if r and str(r).rstrip("/\\") != str(curr_dir).rstrip("/\\"):
                        base_r = pmod.basename(str(r).rstrip("/\\")) or str(r)
                        items.append({
                            "type": "recent",
                            "label": f"🏷️ {base_r}/",
                            "desc": f"Recent: {r}",
                            "badge": "recent",
                            "path": r
                        })

            # Option: Type custom path
            items.append({
                "type": "custom",
                "label": "[✎] Type custom path...",
                "desc": "Input directory manually",
                "badge": "input",
                "path": None
            })

            # Subfolders
            for sub in subdirs:
                if pmod == posixpath:
                    sub_full = pmod.normpath(f"{curr_dir.rstrip('/')}/{sub}")
                else:
                    sub_full = os.path.normpath(os.path.join(curr_dir, sub))
                items.append({
                    "type": "dir",
                    "label": f"📁 {sub}/",
                    "desc": sub_full,
                    "badge": "dir",
                    "path": sub_full
                })

            if not subdirs and not err_msg:
                items.append({
                    "type": "info",
                    "label": "(no subdirectories)",
                    "desc": "",
                    "badge": "",
                    "path": None
                })

            # Bound selected index
            if selected_idx >= len(items):
                selected_idx = 0
            elif selected_idx < 0:
                selected_idx = len(items) - 1

            # 3. Render view
            _reset_screen()
            header_title = title or "Workspace Directory Browser"
            console.print(f"  [{p}][bold]{header_title}[/bold][/{p}]")
            console.print(f"  [{d}]Current:[/{d}] [{s}][bold]{curr_dir}[/bold][/{s}]")
            if err_msg:
                console.print(f"  [{e}]! {err_msg}[/{e}]")
            console.print()

            # Pagination window
            total = len(items)
            half = max_visible // 2
            start = max(0, min(selected_idx - half, total - max_visible))
            end = min(start + max_visible, total)

            visible_items = items[start:end]
            col_w = max((len(str(it.get("label", ""))) for it in visible_items), default=20) + 2

            for idx in range(start, end):
                item = items[idx]
                is_selected = (idx == selected_idx)
                marker = f"[{p}]  > [/{p}]" if is_selected else f"[{d}]    [/{d}]"
                label = item.get("label", "")
                desc = item.get("desc", "")
                badge = item.get("badge", "")

                lbl_padded = f"{label:<{col_w}}"
                if is_selected:
                    label_fmt = f"[{p}][bold]{lbl_padded}[/bold][/{p}]"
                elif item["type"] == "confirm":
                    label_fmt = f"[{s}]{lbl_padded}[/{s}]"
                elif item["type"] == "info":
                    label_fmt = f"[{d}]{lbl_padded}[/{d}]"
                else:
                    label_fmt = f"[{txt}]{lbl_padded}[/{txt}]"

                desc_fmt = f"[{d}]{desc:<36}[/{d}]" if desc else ""
                badge_fmt = f" [{a}]{badge}[/{a}]" if badge and badge not in ("dir", "info") else ""

                console.print(f"{marker}{label_fmt} {desc_fmt}{badge_fmt}")

            if total > max_visible:
                console.print(f"  [{d}]({selected_idx + 1}/{total})[/{d}]")

            console.print()
            shortcuts = (
                f"  [{d}]↑/↓ navigate  Enter open/select  [/{d}]"
                f"[{a}][c][/{a}] [{d}]select  [/{d}]"
                f"[{a}][u][/{a}] [{d}]parent  [/{d}]"
                f"[{a}][t][/{a}] [{d}]type path  [/{d}]"
                f"[{d}]Esc cancel[/{d}]"
            )
            console.print(shortcuts)

            # 4. Handle input
            key = read_single_key()
            if key in ("up", "k"):
                selected_idx = (selected_idx - 1) % len(items)
            elif key in ("down", "j"):
                selected_idx = (selected_idx + 1) % len(items)
            elif key in ("c", "s", " "):
                # Confirm current directory immediately!
                return curr_dir
            elif key in ("u", "backspace", "left"):
                if not is_at_root:
                    curr_dir = parent_dir
                    selected_idx = 0
            elif key == "t" or (key == "enter" and items[selected_idx]["type"] == "custom"):
                show_cursor()
                console.print(f"\n  [{a}][bold]Type Directory Path[/bold][/{a}]")
                console.print(f"  [{d}]Current: {curr_dir}[/{d}]")
                try:
                    user_val = input("  › Path: ").strip()
                    if user_val:
                        if pmod == posixpath:
                            if user_val.startswith("/"):
                                curr_dir = pmod.normpath(user_val)
                            else:
                                curr_dir = pmod.normpath(pmod.join(curr_dir, user_val))
                        else:
                            if os.path.isabs(user_val):
                                curr_dir = os.path.normpath(user_val)
                            else:
                                curr_dir = os.path.normpath(os.path.join(curr_dir, user_val))
                        selected_idx = 0
                except (KeyboardInterrupt, EOFError):
                    pass
                hide_cursor()
            elif key == "enter":
                it = items[selected_idx]
                if it["type"] == "confirm":
                    return it["path"]
                elif it["type"] in ("up", "dir", "recent"):
                    curr_dir = it["path"]
                    selected_idx = 0
                elif it["type"] == "info":
                    pass
            elif key in ("escape", "q"):
                return None

    finally:
        show_cursor()
        _reset_screen()

