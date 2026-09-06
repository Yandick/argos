"""
Argos Theme & Aesthetic Engine
Provides modern, carefully crafted color palettes inspired by OpenCode, Pi, and popular developer themes.
"""
from prompt_toolkit.styles import Style

THEMES = {
    "catppuccin": {
        "id": "catppuccin",
        "name": "Catppuccin Mocha",
        "desc": "Soft modern pastel tones",
        "primary": "#89b4fa",    # Blue
        "accent": "#cba6f7",     # Mauve
        "success": "#a6e3a1",    # Green
        "warning": "#f9e2af",    # Yellow
        "error": "#f38ba8",      # Red
        "dim": "#6c7086",        # Overlay0
        "text": "#cdd6f4",       # Text
        "highlight": "#b4befe",  # Lavender
    },
    "tokyo-night": {
        "id": "tokyo-night",
        "name": "Tokyo Night",
        "desc": "Deep clean indigo, neon cyan & purple",
        "primary": "#7aa2f7",    # Blue
        "accent": "#bb9af7",     # Purple
        "success": "#9ece6a",    # Green
        "warning": "#e0af68",    # Orange
        "error": "#f7768e",      # Red
        "dim": "#565f89",        # Comment
        "text": "#c0caf5",       # Foreground
        "highlight": "#7dcfff",  # Cyan
    },
    "dracula": {
        "id": "dracula",
        "name": "Dracula",
        "desc": "Vampire purple, vibrant pink & neon green",
        "primary": "#bd93f9",    # Purple
        "accent": "#ff79c6",     # Pink
        "success": "#50fa7b",    # Green
        "warning": "#f1fa8c",    # Yellow
        "error": "#ff5555",      # Red
        "dim": "#6272a4",        # Comment
        "text": "#f8f8f2",       # Foreground
        "highlight": "#8be9fd",  # Cyan
    },
    "nord": {
        "id": "nord",
        "name": "Nord",
        "desc": "Arctic cool frost, blue & slate",
        "primary": "#88c0d0",    # Frost Blue
        "accent": "#81a1c1",     # Frost Darker
        "success": "#a3be8c",    # Green
        "warning": "#ebcb8b",    # Yellow
        "error": "#bf616a",      # Red
        "dim": "#616e88",        # Slate
        "text": "#eceff4",       # Snow Storm
        "highlight": "#8fbcbb",  # Teal
    },
    "gruvbox": {
        "id": "gruvbox",
        "name": "Gruvbox Dark",
        "desc": "Warm retro earthy tones",
        "primary": "#fe8019",    # Orange
        "accent": "#d3869b",     # Purple
        "success": "#b8bb26",    # Green
        "warning": "#fabd2f",    # Yellow
        "error": "#fb4934",      # Red
        "dim": "#928374",        # Gray
        "text": "#ebdbb2",       # Light
        "highlight": "#8ec07c",  # Aqua
    },
    "monokai": {
        "id": "monokai",
        "name": "Monokai Pro",
        "desc": "High-contrast vibrant classic",
        "primary": "#66d9ef",    # Cyan
        "accent": "#ae81ff",     # Purple
        "success": "#a6e22e",    # Green
        "warning": "#fd971f",    # Orange
        "error": "#f92672",      # Pink
        "dim": "#75715e",        # Gray
        "text": "#f8f8f2",       # White
        "highlight": "#e6db74",  # Yellow
    },
    "cyberpunk": {
        "id": "cyberpunk",
        "name": "Cyberpunk Matrix",
        "desc": "Electric neon green, cyan & magenta",
        "primary": "#00ff9f",    # Neon Green
        "accent": "#00b8ff",     # Neon Blue
        "success": "#00ff66",    # Matrix
        "warning": "#ffff00",    # Yellow
        "error": "#ff0055",      # Neon Pink
        "dim": "#336644",        # Dark Green
        "text": "#e0ffe0",       # Light Green
        "highlight": "#d600ff",  # Magenta
    },
    "minimal": {
        "id": "minimal",
        "name": "Minimalist Monolith",
        "desc": "Clean monochrome grayscale with subtle mint",
        "primary": "#e4e4e7",    # Zinc-200
        "accent": "#a1a1aa",     # Zinc-400
        "success": "#86efac",    # Mint-300
        "warning": "#fde047",    # Yellow-300
        "error": "#fca5a5",      # Red-300
        "dim": "#71717a",        # Zinc-500
        "text": "#f4f4f5",       # Zinc-100
        "highlight": "#ffffff",  # White
    }
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
    return f"[{p}]●[/{p}] [{p}]■[/{p}][{a}]■[/{a}][{s}]■[/{s}][{w}]■[/{w}]"


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
        "bottom-toolbar": f"bg:#181825 fg:{d}",
        "completion-menu": f"bg:#1e1e2e fg:{txt}",
        "completion-menu.completion": f"fg:{txt}",
        "completion-menu.completion.current": f"bg:{p} fg:#11111b bold",
        "completion-menu.meta.completion": f"fg:{d}",
        "completion-menu.meta.completion.current": f"bg:{p} fg:#1e1e2e",
        "scrollbar.background": f"bg:#181825",
        "scrollbar.button": f"bg:{d}",
    })

