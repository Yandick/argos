"""
Windows Local PTY Process Manager via pywinpty
"""
import os
import sys
import base64
import shutil

try:
    from winpty import PtyProcess
except ImportError:  # non-Windows platform or pywinpty not installed
    PtyProcess = None


def _tokenize_args(s):
    """Split a user-typed argument string on spaces, honoring double quotes.

    Backslashes stay literal so Windows paths survive intact.
    """
    tokens, cur, in_q = [], [], False
    for ch in (s or ""):
        if ch == '"':
            in_q = not in_q
        elif ch == " " and not in_q:
            if cur:
                tokens.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        tokens.append("".join(cur))
    return tokens


def _ps_launch_command(exe_path, user_args):
    """Build a PowerShell launch command safe for arbitrary user arguments.

    The script is passed via -EncodedCommand (base64 of UTF-16LE), so raw
    quotes / $ / backticks / semicolons in user input can never break out of
    the outer Windows command line or the PowerShell parser. Each argument
    becomes a PowerShell single-quoted literal.
    """
    parts = ["&", "'" + str(exe_path).replace("'", "''") + "'"]
    for tok in _tokenize_args(user_args):
        parts.append("'" + tok.replace("'", "''") + "'")
    script = " ".join(parts)
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return f"powershell.exe -NoLogo -ExecutionPolicy Bypass -EncodedCommand {encoded}"


class LocalPty:
    def __init__(self, cmd=None, cwd=None):
        self.cmd = cmd or "powershell.exe -NoLogo"
        self.cwd = cwd or os.getcwd()
        self.pty = None
        self.is_alive = False

    def start(self, cols=120, rows=30):
        if PtyProcess is None:
            raise RuntimeError("本地 PTY 需要 pywinpty（仅支持 Windows）。请在 Windows 上运行，或改用远程 SSH 会话。")
        cmdline = self._resolve_cmd(self.cmd)
        cwd = self.cwd if (self.cwd and os.path.isdir(self.cwd)) else os.getcwd()
        self.pty = PtyProcess.spawn(cmdline, cwd=cwd, dimensions=(max(5, rows), max(10, cols)))
        self.is_alive = True
        return True

    def _resolve_cmd(self, cmd):
        cmd = cmd.strip()
        if cmd == "claude" or cmd.startswith("claude "):
            claude_cmd = shutil.which("claude.cmd") or shutil.which("claude.exe") or shutil.which("claude") or "claude"
            return _ps_launch_command(claude_cmd, cmd[6:].strip())

        if cmd == "agy" or cmd.startswith("agy "):
            agy_cmd = shutil.which("agy.exe") or shutil.which("agy") or os.path.expanduser(r"~\AppData\Local\agy\bin\agy.exe")
            if agy_cmd and os.path.exists(agy_cmd):
                return f'"{agy_cmd}" {cmd[3:]}'.strip()
            return f'powershell.exe -NoLogo -ExecutionPolicy Bypass -Command "{cmd}"'

        # If user asked for codex
        if cmd == "codex" or cmd.startswith("codex "):
            codex_cmd = shutil.which("codex.cmd") or shutil.which("codex.exe") or shutil.which("codex") or "codex"
            return _ps_launch_command(codex_cmd, cmd[5:].strip())

        # If user asked for opencode
        if cmd == "opencode" or cmd.startswith("opencode "):
            opencode_cmd = shutil.which("opencode.cmd") or shutil.which("opencode.exe") or shutil.which("opencode") or "opencode"
            return _ps_launch_command(opencode_cmd, cmd[8:].strip())

        if cmd in ("pwsh", "powershell", "powershell.exe"):
            return "powershell.exe -NoLogo -ExecutionPolicy Bypass"
        if cmd in ("cmd", "cmd.exe"):
            return "cmd.exe"

        if " " in cmd or "&&" in cmd or "|" in cmd:
            return f'powershell.exe -NoLogo -ExecutionPolicy Bypass -Command "{cmd}"'
        return cmd

    def write(self, data):
        if self.is_alive and self.pty:
            self.pty.write(data)

    def read(self):
        if not self.is_alive or not self.pty:
            return None
        try:
            return self.pty.read()
        except EOFError:
            self.is_alive = False
            return None
        except Exception:
            return None

    def resize(self, cols, rows):
        if self.is_alive and self.pty:
            try:
                self.pty.set_winsize(max(5, rows), max(10, cols))
            except Exception:
                pass

    def close(self):
        self.is_alive = False
        if self.pty:
            try:
                self.pty.terminate()
            except Exception:
                pass
            try:
                self.pty.close()
            except Exception:
                pass
            self.pty = None
