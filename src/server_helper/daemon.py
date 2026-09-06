"""
Background Daemon Manager for ServerHelper
Ensures the lightweight background service is running so tasks persist across CLI invocations.
"""
import os
import sys
import time
import subprocess
import requests

DAEMON_PORT = 8765
BASE_URL = f"http://127.0.0.1:{DAEMON_PORT}"


def is_daemon_running():
    try:
        r = requests.get(f"{BASE_URL}/api/status", timeout=1.0)
        if r.status_code != 200:
            return False
        # Verify it's actually our daemon, not some other service that happens
        # to occupy port 8765 (e.g. Jupyter). Otherwise every API call would be
        # silently routed to the wrong process.
        data = r.json()
        return data.get("server") == "argos"
    except Exception:
        return False


def _find_app_script():
    """Locate app.py across install layouts (source tree, editable, cwd)."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(here)), "app.py"),  # src/server_helper -> repo root
        os.path.join(os.path.dirname(here), "app.py"),
        os.path.join(os.getcwd(), "app.py"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return candidates[0]


def ensure_daemon_running():
    if is_daemon_running():
        return True

    # Find python interpreter - prefer pythonw.exe on Windows to guarantee no console window
    python_exe = sys.executable
    if sys.platform == "win32":
        pythonw = os.path.join(os.path.dirname(python_exe), "pythonw.exe")
        if os.path.isfile(pythonw):
            python_exe = pythonw

    # Run app.py in a background detached process
    script_path = _find_app_script()
    if not os.path.isfile(script_path):
        print(f"[Daemon] 找不到后台服务脚本 app.py（尝试路径: {script_path}）")
        return False

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    try:
        subprocess.Popen(
            [python_exe, script_path, "--no-browser", "--port", str(DAEMON_PORT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True
        )
    except Exception as e:
        print(f"[Daemon] 启动后台守护进程失败: {e}")
        return False

    # Wait for daemon to become ready
    for _ in range(30):
        time.sleep(0.1)
        if is_daemon_running():
            return True

    return False


def api_get(endpoint):
    ensure_daemon_running()
    try:
        r = requests.get(f"{BASE_URL}{endpoint}", timeout=5.0)
        return r.json()
    except Exception as e:
        return {"success": False, "error": str(e)}


def api_post(endpoint, data=None):
    ensure_daemon_running()
    try:
        r = requests.post(f"{BASE_URL}{endpoint}", json=data or {}, timeout=10.0)
        return r.json()
    except Exception as e:
        return {"success": False, "error": str(e)}
