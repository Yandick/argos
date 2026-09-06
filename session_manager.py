"""
Session Manager
Maintains concurrent local agent PTY sessions and remote SSH sessions.
Handles output buffering, WebSocket broadcasting, and session lifecycle.
"""
import time
import uuid
import shlex
import threading
from remote_ssh import SSHSession
from local_pty import LocalPtySession


class Session:
    def __init__(self, session_id, name, session_type, server_info=None, remote_dir=None, command=None):
        self.session_id = session_id
        self.name = name
        self.session_type = session_type  # 'remote_ssh' or 'local_pty'
        self.server_info = server_info or {}
        self.remote_dir = remote_dir or ""
        self.command = command or ""
        self.status = "starting"  # 'starting', 'running', 'closed', 'error'
        self.created_at = time.time()
        self.scrollback = ""
        self.max_scrollback = 500000  # ~500KB buffer per session

        self.backend = None
        self.ws_clients = set()
        self.output_listeners = set()
        self._lock = threading.Lock()

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "name": self.name,
            "session_type": self.session_type,
            "server_name": self.server_info.get("name", "Local") if self.session_type == "remote_ssh" else "Local Machine",
            "remote_dir": self.remote_dir,
            "command": self.command,
            "status": self.status,
            "connected_clients": len(self.ws_clients) + len(self.output_listeners),
            "created_at": self.created_at
        }

    def append_output(self, text):
        with self._lock:
            self.scrollback += text
            if len(self.scrollback) > self.max_scrollback:
                self.scrollback = self.scrollback[-self.max_scrollback:]

        # Broadcast to local CLI subscribers (in-process)
        for listener in list(self.output_listeners):
            try:
                listener(text)
            except Exception:
                pass

        # Broadcast to attached websockets (if Web UI running)
        with self._lock:
            clients = list(self.ws_clients)
        if clients:
            try:
                import tornado.ioloop
                loop = tornado.ioloop.IOLoop.current(instance=False)
                dead_clients = set()
                for ws in clients:
                    try:
                        if loop:
                            loop.add_callback(ws.write_message, text)
                        else:
                            ws.write_message(text)
                    except Exception:
                        dead_clients.add(ws)
                if dead_clients:
                    with self._lock:
                        self.ws_clients.difference_update(dead_clients)
            except Exception:
                pass

    def close(self):
        self.status = "closed"
        if self.backend:
            try:
                self.backend.close()
            except Exception:
                pass


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self._lock = threading.Lock()

    def create_session(self, session_type, name, server_info=None, remote_dir=None, startup_cmd=None, local_cmd=None, cwd=None, cols=120, rows=30):
        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            name=name,
            session_type=session_type,
            server_info=server_info,
            remote_dir=remote_dir,
            command=startup_cmd if session_type == "remote_ssh" else (local_cmd or startup_cmd)
        )

        def on_output(data):
            session.append_output(data)

        def on_close():
            session.status = "closed"

        if session_type == "remote_ssh":
            if not server_info:
                return None, "未指定服务器配置"

            # Combine remote_dir with startup_cmd if provided
            full_init_cmd = ""
            try:
                r_proxy_port = int(server_info.get("remote_proxy_port") or 10808)
            except (TypeError, ValueError):
                r_proxy_port = 10808
            try:
                from server_helper.config import Config
                proxy_url = Config().get_proxy()
                if proxy_url:
                    proxy_addr = f"http://127.0.0.1:{r_proxy_port}"
                    full_init_cmd += (
                        f"export http_proxy={shlex.quote(proxy_addr)} "
                        f"https_proxy={shlex.quote(proxy_addr)} "
                        f"all_proxy={shlex.quote(proxy_addr)} 2>/dev/null; "
                    )
            except Exception:
                pass

            if remote_dir:
                full_init_cmd += f"cd {shlex.quote(remote_dir)} 2>/dev/null\n"
            if startup_cmd:
                full_init_cmd += startup_cmd.strip() + "\n"

            ssh_user = server_info.get("user") or server_info.get("username") or "root"
            ssh_pass = server_info.get("password") or server_info.get("pass")
            ssh_key = server_info.get("key_path") or server_info.get("key")
            ssh_auth = server_info.get("auth_type") or server_info.get("auth")

            backend = SSHSession(
                host=server_info.get("host"),
                port=server_info.get("port", 22),
                username=ssh_user,
                password=ssh_pass,
                key_path=ssh_key,
                auth_type=ssh_auth,
                initial_cmd=full_init_cmd,
                on_output=on_output,
                on_close=on_close,
                remote_proxy_port=r_proxy_port
            )
            session.backend = backend
            ok, msg = backend.connect(cols=cols, rows=rows)
            if not ok:
                session.status = "error"
                return None, f"SSH 连接失败: {msg}"
            session.status = "running"

        elif session_type == "local_pty":
            backend = LocalPtySession(
                cmd=local_cmd or startup_cmd or "powershell.exe -NoLogo",
                cwd=cwd,
                on_output=on_output,
                on_close=on_close
            )
            session.backend = backend
            ok, msg = backend.start(cols=cols, rows=rows)
            if not ok:
                session.status = "error"
                return None, f"启动本地 PTY 失败: {msg}"
            session.status = "running"

        else:
            return None, f"未知的会话类型: {session_type}"

        with self._lock:
            self.sessions[session_id] = session

        return session, None

    def get_session(self, session_id):
        with self._lock:
            return self.sessions.get(session_id)

    def list_sessions(self):
        with self._lock:
            return [s.to_dict() for s in self.sessions.values()]

    def attach_ws(self, session_id, ws_handler):
        session = self.get_session(session_id)
        if not session:
            return False
        with session._lock:
            session.ws_clients.add(ws_handler)
            scrollback = session.scrollback
        # Replay scrollback buffer so terminal looks identical
        if scrollback:
            try:
                ws_handler.write_message(scrollback)
            except Exception:
                pass
        return True

    def detach_ws(self, session_id, ws_handler):
        session = self.get_session(session_id)
        if session:
            with session._lock:
                session.ws_clients.discard(ws_handler)

    def write(self, session_id, data):
        session = self.get_session(session_id)
        if session and session.backend:
            session.backend.write(data)

    def resize(self, session_id, cols, rows):
        session = self.get_session(session_id)
        if session and session.backend:
            session.backend.resize(cols, rows)

    def close_session(self, session_id):
        with self._lock:
            session = self.sessions.pop(session_id, None)
        if session:
            session.status = "closed"
            if session.backend:
                session.backend.close()
            # Notify clients
            for ws in list(session.ws_clients):
                try:
                    ws.write_message("\r\n\x1b[31m[会话已关闭]\x1b[0m\r\n")
                    ws.close()
                except Exception:
                    pass
            return True
        return False

    def broadcast_command(self, cmd):
        """Send command to all active running sessions"""
        count = 0
        with self._lock:
            active_sessions = list(self.sessions.values())
        for s in active_sessions:
            if s.status == "running" and s.backend:
                s.backend.write(cmd + "\r\n")
                count += 1
        return count
