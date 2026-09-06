"""
Agent Engine - Autonomous Remote Coding Agent
Executes multi-step agent loops on remote servers via SSH.
Provides tool calling (remote command execution, file inspection, editing, search).
"""
import os
import json
import time
import uuid
import threading
import traceback
import requests


SYSTEM_PROMPT = """你是一个高级远程 Coding Agent，专为在远程 Linux/Unix 服务器上协助开发者执行代码开发、训练监控、环境诊断与调试工作。
你可以通过调用提供的系统工具（运行终端命令、读取文件、编辑文件、查看系统资源）来一步一步探索并达成用户交付的目标。

工作原则：
1. 先了解当前环境与目录结构，再进行修改。
2. 保持操作谨慎，修改代码前可先读取关键片段。
3. 每次操作后，根据工具返回的真实结果进行下一步决策。
4. 遇到报错时，主动排查日志并尝试修复。
5. 当你认为任务已经完成时，提供清晰的总结报告。
"""

AGENT_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "在远程服务器当前工作目录下执行 Shell 命令并返回 stdout 与 stderr",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的 Shell 指令，如 ls -la, python script.py, git status"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "执行超时时间（秒），默认 30",
                        "default": 30
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取远程服务器上的文本文件内容",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "远程文件路径（相对路径或绝对路径）"
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "可选：起始行号（从 1 开始）"
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "可选：结束行号"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "在远程服务器上创建或覆盖写入文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "远程文件路径"
                    },
                    "content": {
                        "type": "string",
                        "description": "要写入的文件完整文本内容"
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "在远程文件中将 old_str 精确替换为 new_str",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "远程文件路径"
                    },
                    "old_str": {
                        "type": "string",
                        "description": "待替换的精确原文本"
                    },
                    "new_str": {
                        "type": "string",
                        "description": "替换后的新文本"
                    }
                },
                "required": ["path", "old_str", "new_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "列出远程指定目录下的文件和子目录",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "目录路径，默认为当前工作目录"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_gpu_and_system",
            "description": "查看远程服务器的 GPU 状态 (nvidia-smi)、内存占用 (free -m) 和 CPU 负载",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


class AgentTask:
    def __init__(self, task_id, session_id, prompt, on_event=None):
        self.task_id = task_id
        self.session_id = session_id
        self.prompt = prompt
        self.on_event = on_event  # callback for streaming events to UI
        self.status = "idle"     # idle, running, completed, error, stopped
        self.messages = []
        self.stop_requested = False
        self.thread = None
        self.created_at = time.time()
        self.current_step = 0
        self.max_steps = 15

    def emit(self, event_type, data):
        if self.on_event:
            try:
                self.on_event({
                    "task_id": self.task_id,
                    "session_id": self.session_id,
                    "event": event_type,
                    "data": data,
                    "timestamp": time.time()
                })
            except Exception:
                pass


class AgentEngine:
    def __init__(self, config_manager, session_manager):
        self.config_manager = config_manager
        self.session_manager = session_manager
        self.active_tasks = {}  # task_id -> AgentTask
        self._lock = threading.Lock()

    def create_task(self, session_id, prompt, on_event=None):
        task_id = "agent-" + str(uuid.uuid4())[:8]
        task = AgentTask(task_id, session_id, prompt, on_event)
        with self._lock:
            self.active_tasks[task_id] = task
        return task

    def start_task(self, task_id):
        with self._lock:
            task = self.active_tasks.get(task_id)
        if not task:
            return False, "Task not found"

        task.status = "running"
        task.thread = threading.Thread(target=self._run_loop, args=(task,), daemon=True)
        task.thread.start()
        return True, None

    def stop_task(self, task_id):
        with self._lock:
            task = self.active_tasks.get(task_id)
        if task:
            task.stop_requested = True
            task.status = "stopped"
            task.emit("status_change", {"status": "stopped", "message": "用户已停止 Agent 运行"})
            return True
        return False

    def get_task_history(self, task_id):
        with self._lock:
            task = self.active_tasks.get(task_id)
        if task:
            return {
                "task_id": task.task_id,
                "session_id": task.session_id,
                "status": task.status,
                "prompt": task.prompt,
                "messages": task.messages,
                "current_step": task.current_step
            }
        return None

    def _resolve_path(self, filepath, remote_dir):
        filepath = (filepath or "").strip()
        if not filepath:
            return ""
        if filepath.startswith("/") or os.path.isabs(filepath) or (len(filepath) > 1 and filepath[1] == ":"):
            return filepath
        if remote_dir and remote_dir != ".":
            sep = "/" if "/" in remote_dir else "\\"
            return remote_dir.rstrip("/\\") + sep + filepath
        return filepath

    def _execute_tool(self, session, tool_name, tool_args):
        """Execute a tool against the remote session or local session"""
        backend = getattr(session, "backend", None)
        client = getattr(backend, "client", None)
        remote_dir = getattr(session, "remote_dir", "") or "."

        if tool_name == "run_command":
            cmd = tool_args.get("command", "").strip()
            timeout = int(tool_args.get("timeout", 30))
            if not cmd:
                return "错误: 命令不能为空"

            if session.session_type == "remote_ssh" and client:
                full_cmd = f"cd '{remote_dir}' 2>/dev/null || cd {remote_dir}; {cmd}"
                try:
                    stdin, stdout, stderr = client.exec_command(full_cmd, timeout=timeout)
                    out = stdout.read().decode("utf-8", errors="replace")
                    err = stderr.read().decode("utf-8", errors="replace")
                    res = ""
                    if out:
                        res += out
                    if err:
                        res += ("\n[STDERR]\n" if res else "") + err
                    return res if res else "(命令执行成功，无输出)"
                except Exception as e:
                    return f"执行出错: {str(e)}"

            elif session.session_type == "local_pty":
                import subprocess
                try:
                    p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, cwd=session.remote_dir or None)
                    return (p.stdout + p.stderr) if (p.stdout or p.stderr) else "(执行完成，无输出)"
                except Exception as e:
                    return f"本地执行出错: {str(e)}"
            return "会话后端未就绪"

        elif tool_name == "list_directory":
            path = tool_args.get("path") or remote_dir
            if session.session_type == "remote_ssh" and backend:
                files = backend.list_sftp_files(path)
                return json.dumps(files, ensure_ascii=False, indent=2)
            else:
                try:
                    items = os.listdir(path if os.path.isabs(path) else os.path.join(os.getcwd(), path))
                    return json.dumps(items, ensure_ascii=False, indent=2)
                except Exception as e:
                    return f"读取目录失败: {e}"

        elif tool_name == "read_file":
            filepath = self._resolve_path(tool_args.get("path", ""), remote_dir)
            if not filepath:
                return "错误: 文件路径不能为空"

            if session.session_type == "remote_ssh" and backend:
                content, err = backend.read_sftp_file(filepath)
                if err:
                    return f"读取文件失败: {err}"
            else:
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception as e:
                    return f"读取文件失败: {e}"

            start = tool_args.get("start_line")
            end = tool_args.get("end_line")
            if start or end:
                lines = content.splitlines()
                s_idx = max(0, (start or 1) - 1)
                e_idx = end if end else len(lines)
                content = "\n".join(lines[s_idx:e_idx])
            return content

        elif tool_name == "write_file":
            filepath = self._resolve_path(tool_args.get("path", ""), remote_dir)
            content = tool_args.get("content", "")

            if session.session_type == "remote_ssh" and client:
                try:
                    sftp = client.open_sftp()
                    with sftp.open(filepath, "w") as f:
                        f.write(content)
                    return f"成功写入文件: {filepath} ({len(content)} 字符)"
                except Exception as e:
                    return f"写入文件失败: {e}"
            else:
                try:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    return f"本地写入成功: {filepath}"
                except Exception as e:
                    return f"本地写入失败: {e}"

        elif tool_name == "edit_file":
            filepath = self._resolve_path(tool_args.get("path", ""), remote_dir)
            old_str = tool_args.get("old_str", "")
            new_str = tool_args.get("new_str", "")

            if session.session_type == "remote_ssh" and backend:
                content, err = backend.read_sftp_file(filepath)
                if err:
                    return f"读取原文件失败: {err}"
                if old_str not in content:
                    return f"错误: 在文件 {filepath} 中未匹配到原文本内容"
                new_content = content.replace(old_str, new_str, 1)
                try:
                    sftp = client.open_sftp()
                    with sftp.open(filepath, "w") as f:
                        f.write(new_content)
                    return f"成功修改文件 {filepath}！"
                except Exception as e:
                    return f"保存修改失败: {e}"
            else:
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                    if old_str not in content:
                        return f"错误: 在文件 {filepath} 中未匹配到原文本内容"
                    new_content = content.replace(old_str, new_str, 1)
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    return f"成功修改文件 {filepath}！"
                except Exception as e:
                    return f"修改文件失败: {e}"

        elif tool_name == "check_gpu_and_system":
            if session.session_type == "remote_ssh" and client:
                cmd = "echo '=== GPU STATUS ===' && nvidia-smi 2>/dev/null || echo '(未检测到 NVIDIA 驱动或无 GPU)'; echo '=== MEMORY ===' && free -h 2>/dev/null || free -m; echo '=== CPU LOAD ===' && uptime"
                try:
                    stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
                    return stdout.read().decode("utf-8", errors="replace")
                except Exception as e:
                    return f"获取状态失败: {e}"
            return "仅远程 SSH 会话支持该状态查询"

        return f"未知的工具: {tool_name}"

    def _run_loop(self, task):
        """Main Agent execution loop"""
        task.emit("status_change", {"status": "running", "message": "Agent 循环启动"})
        task.emit("message", {"role": "user", "content": task.prompt})
        task.messages.append({"role": "user", "content": task.prompt})

        settings = self.config_manager.get_settings()
        api_key = (settings.get("api_key") or "").strip()
        base_url = settings.get("api_base") or "https://api.deepseek.com/v1"
        model = settings.get("model") or "deepseek-chat"

        session = self.session_manager.get_session(task.session_id)
        if not session:
            task.status = "error"
            task.emit("status_change", {"status": "error", "message": f"找不到会话 {task.session_id}"})
            return

        # Prepare system instructions with session context
        context_prompt = f"{SYSTEM_PROMPT}\n当前任务关联的远程环境：\n- 会话名称: {session.name}\n- 模式: {session.session_type}\n- 远程工作目录: {session.remote_dir or '根目录'}\n"
        history = [{"role": "system", "content": context_prompt}]
        history.append({"role": "user", "content": task.prompt})

        fallback_to_guided = False

        while task.current_step < task.max_steps and not task.stop_requested:
            task.current_step += 1
            task.emit("step_start", {"step": task.current_step, "max_steps": task.max_steps})

            # Check if user has an API Key configured and valid
            if api_key and not fallback_to_guided:
                try:
                    task.emit("thinking_start", {"step": task.current_step})
                    resp = requests.post(
                        f"{base_url.rstrip('/')}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": model,
                            "messages": history,
                            "tools": AGENT_TOOLS_SCHEMA,
                            "tool_choice": "auto",
                            "temperature": 0.2
                        },
                        timeout=60
                    )
                    resp_json = resp.json()
                    if "choices" not in resp_json:
                        err_msg = resp_json.get("error", {}).get("message", "API Key 未授权或服务不可达")
                        task.emit("error", {"message": f"LLM API 提醒: {err_msg}，正在切换为自主探测模式..."})
                        fallback_to_guided = True
                        continue

                    choice = resp_json["choices"][0]["message"]
                    content = choice.get("content") or ""
                    tool_calls = choice.get("tool_calls") or []

                    if content:
                        task.emit("thought", {"step": task.current_step, "content": content})
                        task.messages.append({"role": "assistant", "content": content})

                    if not tool_calls:
                        # Agent has finished and provided final response
                        task.status = "completed"
                        task.emit("status_change", {"status": "completed", "message": "Agent 已完成任务！"})
                        break

                    # Append assistant message to history
                    history.append(choice)

                    # Execute each tool call
                    for tc in tool_calls:
                        func_name = tc["function"]["name"]
                        try:
                            func_args = json.loads(tc["function"]["arguments"])
                        except Exception:
                            func_args = {}

                        task.emit("tool_call", {
                            "step": task.current_step,
                            "tool_id": tc["id"],
                            "tool_name": func_name,
                            "arguments": func_args
                        })

                        # Execute tool on remote SSH
                        tool_result = self._execute_tool(session, func_name, func_args)

                        task.emit("tool_result", {
                            "step": task.current_step,
                            "tool_id": tc["id"],
                            "tool_name": func_name,
                            "result": tool_result
                        })

                        history.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": str(tool_result)
                        })

                except Exception as e:
                    task.emit("error", {"message": f"Agent 调用发生异常: {str(e)}"})
                    task.status = "error"
                    break

            else:
                # Guided Exploration Mode: Executes real commands on the remote server step-by-step
                step = task.current_step
                task.emit("thinking_start", {"step": step})

                if step == 1:
                    thought = "正在自动探测远程工作环境与项目结构..."
                    task.emit("thought", {"step": step, "content": thought})
                    func_name = "list_directory"
                    func_args = {"path": session.remote_dir or "."}
                elif step == 2:
                    thought = "检查服务器资源与硬件负载（GPU/CPU/内存）..."
                    task.emit("thought", {"step": step, "content": thought})
                    func_name = "check_gpu_and_system"
                    func_args = {}
                elif step == 3:
                    thought = "执行环境诊断并检查 Git 仓库状态..."
                    task.emit("thought", {"step": step, "content": thought})
                    func_name = "run_command"
                    func_args = {"command": "git status 2>/dev/null || (pwd && whoami && uname -a)"}
                else:
                    # Final step
                    thought = f"已完成对远程目录「{session.remote_dir or '当前目录'}」的自动探测与诊断。\n\n提示：如需启用完全自主的自然语言改代码、排查 Bug 与执行复杂任务，请在顶部「设置」中配置您的 LLM API Key (如 DeepSeek / Claude / OpenAI / 本地 Ollama)。"
                    task.emit("thought", {"step": step, "content": thought})
                    task.emit("status_change", {"status": "completed", "message": "任务诊断流程已完成"})
                    task.status = "completed"
                    break

                task.emit("tool_call", {
                    "step": step,
                    "tool_name": func_name,
                    "arguments": func_args
                })

                result = self._execute_tool(session, func_name, func_args)

                task.emit("tool_result", {
                    "step": step,
                    "tool_name": func_name,
                    "result": result
                })

        if task.stop_requested:
            task.status = "stopped"
            task.emit("status_change", {"status": "stopped", "message": "任务已中断"})
        elif task.current_step >= task.max_steps and task.status != "completed":
            task.status = "completed"
            task.emit("status_change", {"status": "completed", "message": "达到最大步数限制，已停止"})
