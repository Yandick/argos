"""
Session & Task Manager for ServerHelper
Maintains active tasks in memory with output buffering and multi-task switching.
"""
import time
import shlex
import threading
from server_helper.ssh import SSHClientWrapper
from server_helper.local_pty import LocalPty
from server_helper.agent_bridge import build_agent_cmd


class TaskSession:
    def __init__(self, name, server_info=None, remote_dir=None, agent_type="claude", startup_cmd=None):
        self.name = name
        self.server_info = server_info or {}
        self.remote_dir = remote_dir or ""
        self.agent_type = agent_type or "claude"
        self.startup_cmd = startup_cmd or ""
        self.created_at = time.time()
        self.status = "starting"
        self.backend = None
        self.scrollback = ""
        self.max_scrollback = 200000
        self._lock = threading.Lock()
        self._read_thread = None
        self._stop_event = threading.Event()
        self.on_output = None

    def start(self, cols=120, rows=30):
        try:
            if self.server_info and self.server_info.get("host"):
                # Remote SSH Session
                auth_type = self.server_info.get("auth_type") or self.server_info.get("auth") or "key"
                key_path = self.server_info.get("key_path") or self.server_info.get("key")
                password = self.server_info.get("password") or self.server_info.get("pass")
                ssh_user = self.server_info.get("user") or self.server_info.get("username") or "root"
                backend = SSHClientWrapper(
                    host=self.server_info.get("host"),
                    port=int(self.server_info.get("port", 22)),
                    user=ssh_user,
                    auth_type=auth_type,
                    key_path=key_path,
                    password=password
                )
                backend.connect(cols=cols, rows=rows)
                self.backend = backend
                self.status = "running"

                # Initial directory cd & agent launch
                if self.remote_dir:
                    backend.write(f"cd {shlex.quote(self.remote_dir)} 2>/dev/null\n")
                    time.sleep(0.1)

                if self.startup_cmd:
                    backend.write(self.startup_cmd.strip() + "\n")
                elif self.agent_type and self.agent_type != "shell":
                    backend.write(f"{self.agent_type}\n")

            else:
                # Local PTY Session
                cmd = self.startup_cmd or build_agent_cmd(self.agent_type)
                backend = LocalPty(cmd=cmd, cwd=self.remote_dir or None)
                backend.start(cols=cols, rows=rows)
                self.backend = backend
                self.status = "running"

            # Background thread to read output into buffer
            self._read_thread = threading.Thread(target=self._reader, daemon=True)
            self._read_thread.start()
            return True, None

        except Exception as e:
            self.status = "error"
            return False, str(e)

    def write(self, data):
        backend = self.backend
        if backend:
            backend.write(data)

    def resize(self, cols, rows):
        backend = self.backend
        if backend:
            backend.resize(cols, rows)

    def _reader(self):
        while not self._stop_event.is_set() and self.backend and self.status == "running":
            try:
                data = self.backend.read()
                if data is None:
                    break
                if data:
                    with self._lock:
                        self.scrollback += data
                        if len(self.scrollback) > self.max_scrollback:
                            self.scrollback = self.scrollback[-self.max_scrollback:]
                    if self.on_output:
                        try:
                            self.on_output(data)
                        except Exception:
                            pass
                else:
                    time.sleep(0.01)
            except Exception:
                break
        self.status = "stopped"

    def close(self):
        self._stop_event.set()
        self.status = "stopped"
        # Grab a local reference and clear the attribute first so the reader
        # thread can't call read() on a backend that's being torn down.
        backend = self.backend
        self.backend = None
        if backend:
            backend.close()


class SessionManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
            cls._instance.tasks = {}
            cls._instance._lock = threading.Lock()
        return cls._instance

    def create_task(self, name, server_info=None, remote_dir=None, agent_type="claude", startup_cmd=None, cols=120, rows=30):
        with self._lock:
            if name in self.tasks and self.tasks[name].status == "running":
                return self.tasks[name], "任务已在运行"
            task = TaskSession(name, server_info, remote_dir, agent_type, startup_cmd)
            ok, err = task.start(cols=cols, rows=rows)
            if not ok:
                return None, err
            self.tasks[name] = task
            return task, None

    def get_task(self, name):
        with self._lock:
            return self.tasks.get(name)

    def list_tasks(self):
        with self._lock:
            return list(self.tasks.values())

    def close_task(self, name):
        with self._lock:
            task = self.tasks.pop(name, None)
        if task:
            task.close()
            return True
        return False

    def broadcast(self, cmd):
        with self._lock:
            active = [t for t in self.tasks.values() if t.status == "running"]
        for t in active:
            t.write(cmd + "\r\n")
        return len(active)
