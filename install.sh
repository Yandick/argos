#!/usr/bin/env bash
# ==============================================================================
# Argos (Ἄργος) - One-line Installer for Linux & macOS
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Yandick/argos/main/install.sh | bash
# ==============================================================================
set -e

BOLD="\033[1m"
CYAN="\033[36m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
RESET="\033[0m"

echo -e "${CYAN}${BOLD}"
echo "  █████╗ ██████╗  ██████╗  ██████╗ ███████╗"
echo " ██╔══██╗██╔══██╗██╔════╝ ██╔═══██╗██╔════╝"
echo " ███████║██████╔╝██║  ███╗██║   ██║███████╗"
echo " ██╔══██║██╔══██╗██║   ██║██║   ██║╚════██║"
echo " ██║  ██║██║  ██║╚██████╔╝╚██████╔╝███████║"
echo " ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚══════╝"
echo -e " ⚡ Argos (Ἄργος) Multi-Agent Orchestrator Installer${RESET}\n"

INSTALL_DIR="$HOME/.argos"
BIN_DIR="$INSTALL_DIR/bin"
VENV_DIR="$INSTALL_DIR/venv"

mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

# 1. Detect Python
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PY_VER=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        PY_MAJOR=$("$cmd" -c 'import sys; print(sys.version_info.major)')
        PY_MINOR=$("$cmd" -c 'import sys; print(sys.version_info.minor)')
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 9 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}[错误] 未找到 Python 3.9+ 环境。请先安装 Python 3.9 或更高版本。${RESET}"
    exit 1
fi

echo -e "${GREEN}[1/4]${RESET} 检测到 Python 环境: $($PYTHON --version)"

# 2. Setup virtual environment (use uv if present, otherwise venv)
echo -e "${GREEN}[2/4]${RESET} 正在配置独立运行环境于 $VENV_DIR ..."
if command -v uv >/dev/null 2>&1; then
    uv venv "$VENV_DIR" --python "$PYTHON" >/dev/null 2>&1
    VENV_PIP="$VENV_DIR/bin/pip"
    uv pip install argos-agent --python "$VENV_DIR/bin/python"
else
    "$PYTHON" -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --upgrade pip >/dev/null 2>&1
    "$VENV_DIR/bin/pip" install argos-agent
fi

# 3. Create launcher script in ~/.argos/bin/argos
echo -e "${GREEN}[3/4]${RESET} 创建执行器符号链接与可执行脚本..."
cat << 'EOF' > "$BIN_DIR/argos"
#!/usr/bin/env bash
ARGOS_HOME="$HOME/.argos"
exec "$ARGOS_HOME/venv/bin/argos" "$@"
EOF
chmod +x "$BIN_DIR/argos"

# Also symlink to ~/.local/bin if it exists or create it
LOCAL_BIN="$HOME/.local/bin"
mkdir -p "$LOCAL_BIN"
ln -sf "$BIN_DIR/argos" "$LOCAL_BIN/argos"

# 4. PATH check
echo -e "${GREEN}[4/4]${RESET} 检查 PATH 环境变量..."
CURRENT_SHELL=$(basename "$SHELL")
SHELL_RC=""

case "$CURRENT_SHELL" in
    zsh)  SHELL_RC="$HOME/.zshrc" ;;
    bash) SHELL_RC="$HOME/.bashrc" ;;
    *)    SHELL_RC="$HOME/.profile" ;;
esac

EXPORT_LINE="export PATH=\"$BIN_DIR:\$PATH\""
if [[ ":$PATH:" != *":$BIN_DIR:"* ]] && [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
    # Only append if not already present, so repeated installs don't pile up
    # duplicate export lines in the user's shell rc.
    if [ -f "$SHELL_RC" ] && ! grep -qF "$BIN_DIR" "$SHELL_RC"; then
        echo "$EXPORT_LINE" >> "$SHELL_RC"
        echo -e "${YELLOW}[提示] 已将 $BIN_DIR 添加至 $SHELL_RC${RESET}"
    fi
fi

echo -e "\n${GREEN}${BOLD}🎉 Argos 安装成功！${RESET}"
echo -e "请在终端执行 ${CYAN}source $SHELL_RC${RESET} (或重启终端)，然后直接运行:"
echo -e "   ${BOLD}${CYAN}argos${RESET}\n"
