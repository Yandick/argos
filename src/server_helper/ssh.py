"""
Low-latency SSH Client Wrapper for ServerHelper
Provides interactive PTY channels with TCP_NODELAY and non-blocking streaming.
"""
import os
import time
import shlex
import socket
import paramiko


class SSHClientWrapper:
    def __init__(self, host, port=22, user="root", auth_type="key", key_path=None, password=None):
        self.host = host
        self.port = int(port)
        self.user = user
        self.auth_type = auth_type
        self.key_path = os.path.expanduser(key_path) if key_path else None
        self.password = password

        self.client = None
        self.channel = None
        self.is_connected = False

        import warnings
        try:
            from cryptography.utils import CryptographyDeprecationWarning
            warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)
        except Exception:
            pass

    def connect(self, cols=120, rows=30):
        self.client = paramiko.SSHClient()
        # Load known_hosts first so a *changed* host key is rejected (MITM
        # protection); only genuinely unknown hosts get auto-added.
        try:
            self.client.load_system_host_keys()
            self.client.load_host_keys(os.path.expanduser("~/.ssh/known_hosts"))
        except Exception:
            pass
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        use_pass = (self.auth_type == "password" or bool(self.password))
        connect_kwargs = {
            "hostname": self.host,
            "port": self.port,
            "username": self.user,
            "timeout": 12,
            "banner_timeout": 15,
            "compress": False,
            "look_for_keys": not use_pass,
            "allow_agent": not use_pass
        }

        if not use_pass and self.key_path and os.path.isfile(self.key_path):
            connect_kwargs["key_filename"] = self.key_path
        elif use_pass:
            connect_kwargs["password"] = self.password
        else:
            for default_key in [os.path.expanduser("~/.ssh/id_rsa"), os.path.expanduser("~/.ssh/id_ed25519")]:
                if os.path.isfile(default_key):
                    connect_kwargs["key_filename"] = default_key
                    break

        self.client.connect(**connect_kwargs)

        # Optimize underlying TCP socket for 0ms Nagle latency
        transport = self.client.get_transport()
        if transport:
            transport.use_compression(False)
            transport.set_keepalive(15)
            if hasattr(transport, "sock") and transport.sock:
                try:
                    transport.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except Exception:
                    pass

        # Open interactive shell channel
        self.channel = self.client.invoke_shell(term="xterm-256color", width=cols, height=rows)
        self.channel.settimeout(0.01)
        self.is_connected = True
        return True

    def write(self, data):
        if not self.is_connected or not self.channel or self.channel.closed:
            return
        if isinstance(data, str):
            data = data.encode("utf-8", errors="ignore")
        self.channel.send(data)

    def read(self, size=4096):
        if not self.is_connected or not self.channel or self.channel.closed:
            return None
        try:
            chunk = self.channel.recv(size)
            if not chunk:
                return None
            return chunk.decode("utf-8", errors="replace")
        except (socket.timeout, TimeoutError):
            return ""
        except Exception:
            return None

    def resize(self, cols, rows):
        if self.is_connected and self.channel and not self.channel.closed:
            try:
                self.channel.resize_pty(width=max(10, cols), height=max(5, rows))
            except Exception:
                pass

    def exec_command(self, cmd, cwd=None, timeout=30):
        if not self.client:
            return -1, "", "SSH Client Not Connected"
        full_cmd = f"cd {shlex.quote(cwd)} 2>/dev/null; {cmd}" if cwd else cmd
        stdin, stdout, stderr = self.client.exec_command(full_cmd, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        return code, out, err

    def close(self):
        self.is_connected = False
        try:
            if self.channel:
                self.channel.close()
        except Exception:
            pass
        try:
            if self.client:
                self.client.close()
        except Exception:
            pass
