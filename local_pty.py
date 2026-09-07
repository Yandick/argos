"""
Local PTY Manager
Handles local interactive agent processes (e.g. claude, agy, powershell, cmd) via pywinpty on Windows.
"""
import os
import sys
import time
import shutil
import threading

try:
    from winpty import PtyProcess
except ImportError:  # non-Windows platform or pywinpty not installed
    PtyProcess = None


class LocalPtySession:
    """
    Manages an active local pseudo-terminal session.
    Streams output in real-time to a callback and handles stdin / resize.
    """

    def __init__(self, cmd=None, cwd=None, on_output=None, on_close=None):
        self.cmd = cmd or "powershell.exe -NoLogo"
        self.cwd = cwd or os.getcwd()
        self.on_output = on_output
        self.on_close = on_close

        self.pty = None
        self.is_alive = False
        self._read_thread = None
        self._stop_event = threading.Event()

    def start(self, cols=120, rows=30):
        if PtyProcess is None:
            err = "本地 PTY 需要 pywinpty（仅支持 Windows）。请在 Windows 上运行，或改用远程 SSH 会话。"
            self._emit(f"\r\n\x1b[31m[Local Agent 错误]\x1b[0m {err}\r\n")
            return False, err
        try:
            self._emit(f"\x1b[36m[Local Agent]\x1b[0m 正在启动本地进程: {self.cmd} ...\r\n")

            # Format command line for Windows
            cmdline = self._resolve_command(self.cmd)

            # Ensure cwd exists
            cwd = self.cwd if (self.cwd and os.path.isdir(self.cwd)) else os.getcwd()

            self.pty = PtyProcess.spawn(cmdline, cwd=cwd, dimensions=(max(5, rows), max(10, cols)))
            self.is_alive = True
            self._emit(f"\x1b[32m[Local Agent 成功]\x1b[0m 进程已就绪 (PID: {self.pty.pid})\r\n\r\n")

            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            return True, "Started"

        except Exception as e:
            err = f"\r\n\x1b[31m[Local Agent 错误]\x1b[0m 启动失败: {str(e)}\r\n"
            self._emit(err)
            self.close()
            return False, str(e)

    def _resolve_command(self, cmd):
        cmd = cmd.strip()
        # If user directly asked for claude
        if cmd == "claude" or cmd.startswith("claude "):
            claude_cmd = shutil.which("claude.cmd") or shutil.which("claude.exe") or shutil.which("claude")
            if claude_cmd and os.path.exists(claude_cmd):
                # Run via cmd.exe /c to keep standard stdio wrapping or powershell
                return f'powershell.exe -NoLogo -ExecutionPolicy Bypass -Command "& \'{claude_cmd}\' {cmd[6:]}"'
            return f'powershell.exe -NoLogo -ExecutionPolicy Bypass -Command "{cmd}"'

        # If user asked for agy
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

        # Default shell if empty or powershell
        if cmd in ("pwsh", "powershell", "powershell.exe"):
            return "powershell.exe -NoLogo -ExecutionPolicy Bypass"
        if cmd in ("cmd", "cmd.exe"):
            return "cmd.exe"

        # If it's a script or multi-word command, run inside PowerShell
        if " " in cmd or "&&" in cmd or "|" in cmd:
            return f'powershell.exe -NoLogo -ExecutionPolicy Bypass -Command "{cmd}"'

        return cmd

    def write(self, data):
        if not self.is_alive or not self.pty:
            return
        try:
            self.pty.write(data)
        except Exception as e:
            self._emit(f"\r\n\x1b[31m[Local Agent 错误]\x1b[0m 输入写入失败: {e}\r\n")

    def resize(self, cols, rows):
        if not self.is_alive or not self.pty:
            return
        try:
            self.pty.set_winsize(max(5, rows), max(10, cols))
        except Exception:
            pass

    def _read_loop(self):
        while not self._stop_event.is_set() and self.pty and self.pty.isalive():
            try:
                # read available bytes
                data = self.pty.read()
                if data:
                    self._emit(data)
                else:
                    time.sleep(0.02)
            except EOFError:
                break
            except Exception:
                break

        self.is_alive = False
        self._emit("\r\n\x1b[33m[Local Agent]\x1b[0m 本地进程已退出。\r\n")
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass

    def _emit(self, text):
        if self.on_output:
            try:
                self.on_output(text)
            except Exception:
                pass

    def close(self):
        self._stop_event.set()
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
