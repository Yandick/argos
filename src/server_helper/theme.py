"""
Argos Theme & Aesthetic Engine
Modern, carefully crafted color palettes with semantic design tokens.
Inspired by Catppuccin, Tokyo Night, Nord, and other popular developer themes.
"""
from prompt_toolkit.styles import Style

THEMES = {
    "catppuccin": {
        "id": "catppuccin",
        "name": "Catppuccin Mocha",
        "desc": "Soft modern pastel tones",
        "primary": "#89b4fa",
        "accent": "#cba6f7",
        "success": "#a6e3a1",
        "warning": "#f9e2af",
        "error": "#f38ba8",
        "dim": "#6c7086",
        "text": "#cdd6f4",
        "highlight": "#b4befe",
        "surface": "#313244",
        "border": "#45475a",
        "selection": "#45475a",
    },
    "tokyo-night": {
        "id": "tokyo-night",
        "name": "Tokyo Night",
        "desc": "Deep clean indigo, neon cyan & purple",
        "primary": "#7aa2f7",
        "accent": "#bb9af7",
        "success": "#9ece6a",
        "warning": "#e0af68",
        "error": "#f7768e",
        "dim": "#565f89",
        "text": "#c0caf5",
        "highlight": "#7dcfff",
        "surface": "#1f2335",
        "border": "#3b4261",
        "selection": "#283457",
    },
    "dracula": {
        "id": "dracula",
        "name": "Dracula",
        "desc": "Vampire purple, vibrant pink & neon green",
        "primary": "#bd93f9",
        "accent": "#ff79c6",
        "success": "#50fa7b",
        "warning": "#f1fa8c",
        "error": "#ff5555",
        "dim": "#6272a4",
        "text": "#f8f8f2",
        "highlight": "#8be9fd",
        "surface": "#343746",
        "border": "#44475a",
        "selection": "#44475a",
    },
    "nord": {
        "id": "nord",
        "name": "Nord",
        "desc": "Arctic cool frost, blue & slate",
        "primary": "#88c0d0",
        "accent": "#81a1c1",
        "success": "#a3be8c",
        "warning": "#ebcb8b",
        "error": "#bf616a",
        "dim": "#4c566a",
        "text": "#eceff4",
        "highlight": "#8fbcbb",
        "surface": "#3b4252",
        "border": "#4c566a",
        "selection": "#434c5e",
    },
    "gruvbox": {
        "id": "gruvbox",
        "name": "Gruvbox Dark",
        "desc": "Warm retro earthy tones",
        "primary": "#fe8019",
        "accent": "#d3869b",
        "success": "#b8bb26",
        "warning": "#fabd2f",
        "error": "#fb4934",
        "dim": "#665c54",
        "text": "#ebdbb2",
        "highlight": "#8ec07c",
        "surface": "#3c3836",
        "border": "#504945",
        "selection": "#504945",
    },
    "monokai": {
        "id": "monokai",
        "name": "Monokai Pro",
        "desc": "High-contrast vibrant classic",
        "primary": "#66d9ef",
        "accent": "#ae81ff",
        "success": "#a6e22e",
        "warning": "#fd971f",
        "error": "#f92672",
        "dim": "#75715e",
        "text": "#f8f8f2",
        "highlight": "#e6db74",
        "surface": "#3e3d32",
        "border": "#49483e",
        "selection": "#49483e",
    },
    "cyberpunk": {
        "id": "cyberpunk",
        "name": "Cyberpunk Neon",
        "desc": "Electric neon with dark matrix vibes",
        "primary": "#00d4aa",
        "accent": "#0ea5e9",
        "success": "#22c55e",
        "warning": "#eab308",
        "error": "#ef4444",
        "dim": "#4a5568",
        "text": "#e2e8f0",
        "highlight": "#a855f7",
        "surface": "#1a1a2e",
        "border": "#2d2d4a",
        "selection": "#16213e",
    },
    "minimal": {
        "id": "minimal",
        "name": "Minimal",
        "desc": "Clean monochrome with subtle accents",
        "primary": "#a1a1aa",
        "accent": "#71717a",
        "success": "#86efac",
        "warning": "#fde047",
        "error": "#fca5a5",
        "dim": "#52525b",
        "text": "#e4e4e7",
        "highlight": "#d4d4d8",
        "surface": "#27272a",
        "border": "#3f3f46",
        "selection": "#3f3f46",
    },
}

DEFAULT_THEME_ID = "catppuccin"


def get_theme(theme_id=None):
    if not theme_id:
        theme_id = DEFAULT_THEME_ID
    return THEMES.get(theme_id.lower()) or THEMES[DEFAULT_THEME_ID]


def list_themes():
    return list(THEMES.values())


def render_swatch(theme):
    p = theme["primary"]
    a = theme["accent"]
    s = theme["success"]
    w = theme["warning"]
    e = theme["error"]
    h = theme.get("highlight", p)
    return f"[{p}]●[/{p}][{a}]●[/{a}][{s}]●[/{s}][{w}]●[/{w}][{e}]●[/{e}][{h}]●[/{h}]"


def get_prompt_toolkit_style(theme):
    p = theme["primary"]
    a = theme["accent"]
    s = theme["success"]
    d = theme["dim"]
    txt = theme.get("text", "#ffffff")
    return Style.from_dict({
        "prompt": f"{p} bold",
        "badge": f"{s} bold",
        "dim": f"{d}",
        "accent": f"{a}",
        "bottom-toolbar": f"noreverse {txt}",
        "bottom-toolbar.text": f"noreverse {txt}",
    })
