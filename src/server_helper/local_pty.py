"""
Windows Local PTY Process Manager via pywinpty
"""
import os
import sys
import shutil

try:
    from winpty import PtyProcess
except ImportError:  # non-Windows platform or pywinpty not installed
    PtyProcess = None


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
            claude_cmd = shutil.which("claude.cmd") or shutil.which("claude.exe") or shutil.which("claude")
            if claude_cmd and os.path.exists(claude_cmd):
                return f'powershell.exe -NoLogo -ExecutionPolicy Bypass -Command "& \'{claude_cmd}\' {cmd[6:]}"'
            return f'powershell.exe -NoLogo -ExecutionPolicy Bypass -Command "{cmd}"'

        if cmd == "agy" or cmd.startswith("agy "):
            agy_cmd = shutil.which("agy.exe") or shutil.which("agy") or os.path.expanduser(r"~\AppData\Local\agy\bin\agy.exe")
            if agy_cmd and os.path.exists(agy_cmd):
                return f'"{agy_cmd}" {cmd[3:]}'.strip()
            return f'powershell.exe -NoLogo -ExecutionPolicy Bypass -Command "{cmd}"'

        # If user asked for codex
        if cmd == "codex" or cmd.startswith("codex "):
            codex_cmd = shutil.which("codex.cmd") or shutil.which("codex.exe") or shutil.which("codex")
            args = cmd[5:].strip()
            if codex_cmd and os.path.exists(codex_cmd):
                return f'powershell.exe -NoLogo -ExecutionPolicy Bypass -Command "& \'{codex_cmd}\' {args}"'.strip()
            return f'powershell.exe -NoLogo -ExecutionPolicy Bypass -Command "{cmd}"'

        # If user asked for opencode
        if cmd == "opencode" or cmd.startswith("opencode "):
            opencode_cmd = shutil.which("opencode.cmd") or shutil.which("opencode.exe") or shutil.which("opencode")
            args = cmd[8:].strip()
            if opencode_cmd and os.path.exists(opencode_cmd):
                return f'powershell.exe -NoLogo -ExecutionPolicy Bypass -Command "& \'{opencode_cmd}\' {args}"'.strip()
            return f'powershell.exe -NoLogo -ExecutionPolicy Bypass -Command "{cmd}"'

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
