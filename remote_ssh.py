"""
Remote SSH Manager
Handles Paramiko SSH connection, interactive PTY shell streaming, SFTP file access, and remote execution.
"""
import os
import io
import time
import socket
import select
import threading
import traceback
import paramiko


class SSHSession:
    """
    Manages an active interactive SSH shell channel.
    Streams output in real-time to a callback and receives user/agent input.
    """

    def __init__(self, host, port=22, username="root", password=None, key_path=None, initial_cmd=None, on_output=None, on_close=None):
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.key_path = os.path.expanduser(key_path) if key_path else None
        self.initial_cmd = initial_cmd
        self.on_output = on_output
        self.on_close = on_close

        self.client = None
        self.channel = None
        self.sftp = None
        self.is_connected = False
        self._read_thread = None
        self._stop_event = threading.Event()

    def connect(self, cols=120, rows=30):
        try:
            self._emit(f"\r\n\x1b[36m[SSH]\x1b[0m 正在连接到 {self.username}@{self.host}:{self.port} ...\r\n")
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": self.host,
                "port": self.port,
                "username": self.username,
                "timeout": 12,
                "banner_timeout": 15
            }

            # Auth by private key if provided or exists
            key_loaded = False
            if self.key_path and os.path.isfile(self.key_path):
                try:
                    connect_kwargs["key_filename"] = self.key_path
                    self.client.connect(**connect_kwargs)
                    key_loaded = True
                except Exception as e:
                    self._emit(f"\x1b[33m[SSH 警告]\x1b[0m 密钥认证失败 ({e})，尝试密码认证...\r\n")

            if not key_loaded:
                if self.password:
                    connect_kwargs["password"] = self.password
                else:
                    # check default ssh keys
                    for default_key in [os.path.expanduser("~/.ssh/id_rsa"), os.path.expanduser("~/.ssh/id_ed25519")]:
                        if os.path.isfile(default_key):
                            connect_kwargs["key_filename"] = default_key
                            break

                self.client.connect(**connect_kwargs)

            # Optimize SSH transport for minimum latency (disable Nagle buffering)
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
            self._emit(f"\x1b[32m[SSH 成功]\x1b[0m 已成功建立会话 ({self.username}@{self.host})！\r\n\r\n")

            # Start reading thread
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()

            # Execute initial command if provided
            if self.initial_cmd:
                time.sleep(0.1)
                self.write(self.initial_cmd.strip() + "\r\n")

            return True, "Connected"

        except paramiko.AuthenticationException:
            err = f"\r\n\x1b[31m[SSH 错误]\x1b[0m 认证失败：请检查用户名、密码或 SSH 密钥。\r\n"
            self._emit(err)
            self.close()
            return False, "Authentication failed"
        except (socket.timeout, TimeoutError):
            err = f"\r\n\x1b[31m[SSH 错误]\x1b[0m 连接超时：无法访问 {self.host}:{self.port}，请检查网络或防火墙。\r\n"
            self._emit(err)
            self.close()
            return False, "Connection timed out"
        except Exception as e:
            err = f"\r\n\x1b[31m[SSH 错误]\x1b[0m 连接异常: {str(e)}\r\n"
            self._emit(err)
            self.close()
            return False, str(e)

    def write(self, data):
        if not self.is_connected or not self.channel or self.channel.closed:
            return
        try:
            if isinstance(data, str):
                data = data.encode("utf-8", errors="ignore")
            self.channel.send(data)
        except Exception as e:
            self._emit(f"\r\n\x1b[31m[SSH 错误]\x1b[0m 发送失败: {e}\r\n")

    def resize(self, cols, rows):
        if not self.is_connected or not self.channel or self.channel.closed:
            return
        try:
            self.channel.resize_pty(width=max(10, cols), height=max(5, rows))
        except Exception:
            pass

    def _read_loop(self):
        if self.channel:
            self.channel.settimeout(0.01)

        while not self._stop_event.is_set() and self.channel and not self.channel.closed:
            try:
                chunk = self.channel.recv(4096)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                self._emit(text)
            except (socket.timeout, TimeoutError):
                continue
            except Exception:
                break
        self.is_connected = False
        self._emit("\r\n\x1b[33m[SSH]\x1b[0m 会话已断开。\r\n")
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

    def list_sftp_files(self, remote_dir):
        """List files in remote directory via SFTP"""
        if not self.client:
            return []
        try:
            if not self.sftp:
                self.sftp = self.client.open_sftp()
            entries = []
            for attr in self.sftp.listdir_attr(remote_dir):
                is_dir = bool(attr.st_mode & 0o040000)
                entries.append({
                    "name": attr.filename,
                    "is_dir": is_dir,
                    "size": attr.st_size,
                    "mtime": attr.st_mtime
                })
            # sort dirs first, then files
            entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            return entries
        except Exception as e:
            return [{"error": str(e)}]

    def read_sftp_file(self, remote_file_path, max_bytes=1024 * 1024):
        """Read a text file from remote server via SFTP"""
        if not self.client:
            return None, "Not connected"
        try:
            if not self.sftp:
                self.sftp = self.client.open_sftp()
            with self.sftp.open(remote_file_path, "r") as f:
                content = f.read(max_bytes)
                return content.decode("utf-8", errors="replace"), None
        except Exception as e:
            return None, str(e)

    def close(self):
        self._stop_event.set()
        self.is_connected = False
        try:
            if self.channel:
                self.channel.close()
        except Exception:
            pass
        try:
            if self.sftp:
                self.sftp.close()
        except Exception:
            pass
        try:
            if self.client:
                self.client.close()
        except Exception:
            pass
