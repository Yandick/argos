"""
ServerHelper - Lightweight Multi-Agent & Remote SSH Orchestrator
Main Tornado Server providing Web UI, REST API, and WebSocket Terminal Channels.
"""
import os
import sys

# Ensure UTF-8 output on Windows console without crashes
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import psutil
import webbrowser
import tornado.ioloop
import tornado.web
import tornado.websocket
from config_manager import ConfigManager
from session_manager import SessionManager
from agent_engine import AgentEngine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

config_mgr = ConfigManager()
session_mgr = SessionManager()
agent_engine = AgentEngine(config_mgr, session_mgr)


class BaseHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with, content-type")
        self.set_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS, DELETE")

    def options(self, *args, **kwargs):
        self.set_status(204)
        self.finish()

    def write_json(self, data, status=200):
        self.set_status(status)
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        self.write(json.dumps(data, ensure_ascii=False))


class StatusHandler(BaseHandler):
    def get(self):
        process = psutil.Process(os.getpid())
        mem_mb = round(process.memory_info().rss / (1024 * 1024), 1)
        cpu_pct = process.cpu_percent(interval=None)

        self.write_json({
            "success": True,
            "memory_mb": mem_mb,
            "cpu_percent": cpu_pct,
            "active_sessions": len(session_mgr.sessions),
            "total_servers": len(config_mgr.get_servers())
        })


class ConfigHandler(BaseHandler):
    def get(self):
        self.write_json(config_mgr.get_all())

    def post(self):
        try:
            body = json.loads(self.request.body)
            if "settings" in body:
                config_mgr.update_settings(body["settings"])
            self.write_json({"success": True, "config": config_mgr.get_all()})
        except Exception as e:
            self.write_json({"success": False, "error": str(e)}, status=400)


class ServerHandler(BaseHandler):
    def post(self):
        try:
            body = json.loads(self.request.body)
            res = config_mgr.save_server(body)
            self.write_json({"success": True, "server": res})
        except Exception as e:
            self.write_json({"success": False, "error": str(e)}, status=400)

    def delete(self):
        try:
            body = json.loads(self.request.body)
            server_id = body.get("id")
            if not server_id:
                return self.write_json({"success": False, "error": "Missing id"}, status=400)
            config_mgr.delete_server(server_id)
            self.write_json({"success": True})
        except Exception as e:
            self.write_json({"success": False, "error": str(e)}, status=400)


class PresetHandler(BaseHandler):
    def post(self):
        try:
            body = json.loads(self.request.body)
            res = config_mgr.save_task_preset(body)
            self.write_json({"success": True, "preset": res})
        except Exception as e:
            self.write_json({"success": False, "error": str(e)}, status=400)

    def delete(self):
        try:
            body = json.loads(self.request.body)
            preset_id = body.get("id")
            if not preset_id:
                return self.write_json({"success": False, "error": "Missing id"}, status=400)
            config_mgr.delete_task_preset(preset_id)
            self.write_json({"success": True})
        except Exception as e:
            self.write_json({"success": False, "error": str(e)}, status=400)


class SessionsHandler(BaseHandler):
    def get(self):
        self.write_json({
            "success": True,
            "sessions": session_mgr.list_sessions()
        })

    def post(self):
        """Create and start a new session"""
        try:
            body = json.loads(self.request.body)
            session_type = body.get("session_type", "remote_ssh")
            name = body.get("name", "New Session")
            server_id = body.get("server_id")
            remote_dir = body.get("remote_dir", "")
            startup_cmd = body.get("startup_cmd", "")
            local_cmd = body.get("local_cmd", "")
            cwd = body.get("cwd", "")
            cols = int(body.get("cols", 120))
            rows = int(body.get("rows", 30))

            server_info = None
            if session_type == "remote_ssh":
                server_info = config_mgr.get_server_by_id(server_id)
                if not server_info:
                    return self.write_json({"success": False, "error": f"找不到服务器配置: {server_id}"}, status=400)

            session, err = session_mgr.create_session(
                session_type=session_type,
                name=name,
                server_info=server_info,
                remote_dir=remote_dir,
                startup_cmd=startup_cmd,
                local_cmd=local_cmd,
                cwd=cwd,
                cols=cols,
                rows=rows
            )

            if err:
                return self.write_json({"success": False, "error": err}, status=400)

            self.write_json({"success": True, "session": session.to_dict()})
        except Exception as e:
            self.write_json({"success": False, "error": str(e)}, status=500)


class SessionActionHandler(BaseHandler):
    def post(self, session_id, action):
        if action == "close":
            closed = session_mgr.close_session(session_id)
            self.write_json({"success": closed})
        elif action == "input":
            body = json.loads(self.request.body)
            text = body.get("text", "")
            session_mgr.write(session_id, text)
            self.write_json({"success": True})
        else:
            self.write_json({"success": False, "error": "Unknown action"}, status=400)


class BroadcastHandler(BaseHandler):
    def post(self):
        try:
            body = json.loads(self.request.body)
            cmd = body.get("command", "")
            if not cmd:
                return self.write_json({"success": False, "error": "Command is empty"}, status=400)
            count = session_mgr.broadcast_command(cmd)
            self.write_json({"success": True, "broadcasted_to": count})
        except Exception as e:
            self.write_json({"success": False, "error": str(e)}, status=400)


class SftpHandler(BaseHandler):
    def post(self, action):
        try:
            body = json.loads(self.request.body)
            session_id = body.get("session_id")
            session = session_mgr.get_session(session_id)
            if not session or session.session_type != "remote_ssh" or not session.backend:
                return self.write_json({"success": False, "error": "该会话不是有效的远程 SSH 会话"}, status=400)

            backend = session.backend
            if action == "list":
                path = body.get("path") or session.remote_dir or "."
                files = backend.list_sftp_files(path)
                self.write_json({"success": True, "path": path, "files": files})
            elif action == "read":
                path = body.get("path")
                content, err = backend.read_sftp_file(path)
                if err:
                    return self.write_json({"success": False, "error": err}, status=400)
                self.write_json({"success": True, "content": content})
            else:
                self.write_json({"success": False, "error": "Unknown sftp action"}, status=400)
        except Exception as e:
            self.write_json({"success": False, "error": str(e)}, status=500)


class TerminalWebSocketHandler(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def open(self, session_id):
        self.session_id = session_id
        ok = session_mgr.attach_ws(session_id, self)
        if not ok:
            self.write_message("\r\n\x1b[31m[错误] 会话不存在或已关闭。\x1b[0m\r\n")
            self.close()

    def on_message(self, message):
        # Check if control packet (e.g. resize)
        if message.startswith("{") and message.endswith("}"):
            try:
                data = json.loads(message)
                if data.get("type") == "resize":
                    cols = int(data.get("cols", 120))
                    rows = int(data.get("rows", 30))
                    session_mgr.resize(self.session_id, cols, rows)
                    return
            except Exception:
                pass

        # Regular user typing / keystrokes
        session_mgr.write(self.session_id, message)

class AgentWebSocketHandler(tornado.websocket.WebSocketHandler):
    connections = {}  # session_id -> set of ws instances

    def check_origin(self, origin):
        return True

    def open(self, session_id):
        self.session_id = session_id
        if session_id not in self.connections:
            self.connections[session_id] = set()
        self.connections[session_id].add(self)
        self.write_json({"event": "connected", "session_id": session_id})

    def on_message(self, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            if msg_type == "prompt":
                prompt = data.get("prompt", "").strip()
                if not prompt:
                    return

                def on_event(event):
                    cls = AgentWebSocketHandler
                    clients = cls.connections.get(self.session_id, set())
                    for c in list(clients):
                        try:
                            tornado.ioloop.IOLoop.current().add_callback(
                                c.write_json, event
                            )
                        except Exception:
                            pass

                task = agent_engine.create_task(self.session_id, prompt, on_event=on_event)
                agent_engine.start_task(task.task_id)

            elif msg_type == "stop":
                task_id = data.get("task_id")
                if task_id:
                    agent_engine.stop_task(task_id)
        except Exception as e:
            self.write_json({"event": "error", "message": str(e)})

    def write_json(self, data):
        try:
            self.write_message(json.dumps(data, ensure_ascii=False))
        except Exception:
            pass

    def on_close(self):
        if self.session_id in self.connections:
            self.connections[self.session_id].discard(self)


class AgentTaskHandler(BaseHandler):
    def post(self, action):
        try:
            body = json.loads(self.request.body)
            if action == "create":
                session_id = body.get("session_id")
                prompt = body.get("prompt", "")
                task = agent_engine.create_task(session_id, prompt)
                agent_engine.start_task(task.task_id)
                self.write_json({"success": True, "task_id": task.task_id})
            elif action == "stop":
                task_id = body.get("task_id")
                ok = agent_engine.stop_task(task_id)
                self.write_json({"success": ok})
            else:
                self.write_json({"success": False, "error": "Unknown action"}, status=400)
        except Exception as e:
            self.write_json({"success": False, "error": str(e)}, status=500)


def make_app():
    handlers = [
        (r"/", tornado.web.RedirectHandler, {"url": "/index.html"}),
        (r"/api/status", StatusHandler),
        (r"/api/config", ConfigHandler),
        (r"/api/config/server", ServerHandler),
        (r"/api/config/preset", PresetHandler),
        (r"/api/sessions", SessionsHandler),
        (r"/api/sessions/([^/]+)/([^/]+)", SessionActionHandler),
        (r"/api/broadcast", BroadcastHandler),
        (r"/api/sftp/([^/]+)", SftpHandler),
        (r"/api/agent/([^/]+)", AgentTaskHandler),
        (r"/ws/terminal/([^/]+)", TerminalWebSocketHandler),
        (r"/ws/agent/([^/]+)", AgentWebSocketHandler),
        (r"/(.*)", tornado.web.StaticFileHandler, {"path": STATIC_DIR, "default_filename": "index.html"}),
    ]
    return tornado.web.Application(handlers, autoreload=False)


def run_server(port=8765, open_browser=True):
    app = make_app()
    server = None
    actual_port = port

    # Try binding to 127.0.0.1 to avoid Windows dual-stack IPv6 socket conflict (WinError 10048)
    for p in range(port, port + 20):
        try:
            server = app.listen(p, address="127.0.0.1")
            actual_port = p
            break
        except OSError:
            continue

    if not server:
        print(f"[错误] 无法在端口范围 {port} - {port + 20} 启动服务，端口均已被占用。")
        sys.exit(1)

    url = f"http://localhost:{actual_port}"

    print("=" * 60)
    print("  ServerHelper - 本地 Agent 远程多任务工作台已启动")
    print(f"  访问网址: {url}")
    print("  轻量化特性: 仅占约 30MB 内存，支持同时多开 Local Agent 与 Remote SSH")
    print("  按 Ctrl+C 停止服务")
    print("=" * 60)

    if open_browser:
        def _open():
            try:
                webbrowser.open(url)
            except Exception:
                pass
        tornado.ioloop.IOLoop.current().call_later(0.8, _open)

    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ServerHelper - Multi-Agent & Remote Task Manager")
    parser.add_argument("--port", type=int, default=8765, help="Port to listen on (default: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    run_server(port=args.port, open_browser=not args.no_browser)
