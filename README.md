# ServerHelper (shmux) ⚡

> **轻量级、低延迟、面向 Coding Agent（Claude Code / agy / Codex / LLM）的远程多任务并发终端工作台**
> 灵感源自 OpenCode 与 Pi 的交互美学，专为解决“多任务并发管理难、多个 Agent 终端窗口杂乱、内存占用高”而设计。

---

## 🌟 为什么需要 ServerHelper？

当我们在本地使用 Coding Agent（如 `claude code`、Google `agy` 或基于 API 的自定义 Agent）连接远程服务器处理多个任务时（例如：一个做推荐系统 `rec` 数据处理，一个做对齐安全评测 `safety`，一个跑持续测试），传统的做法通常是：
1. 本地同时开启 3~5 个终端黑框，窗口切换繁琐且容易输错目录或误关任务；
2. 或者是远程配置一套沉重的 Web/GUI 方案，消耗大量内存；
3. 本地与远程 Agent 缺乏统一的配置中心与上下文调度。

**ServerHelper** 采用纯终端 CLI 交互，内存仅占用约 **15MB ~ 35MB**，秒级极速启动。它支持通过单个统一终端管理所有远程与本地任务，任务在后台守护进程中持续运行，并提供类似 OpenCode / Pi 的斜杠命令体验与 Agent 交互桥梁。

---

## ✨ 核心特性

- 🎯 **OpenCode & Pi 风格的交互式 Agent CLI**：
  - 在终端输入 `server-helper` 即可进入沉浸式工作台。
  - 支持快捷斜杠命令（`/connect`, `/tasks`, `/switch`, `/terminal`, `/agent`, `/status`, `/broadcast` 等）与 Tab 自动补全。
  - 直接输入自然语言需求，无缝分发给指定 Agent 自动化执行。

- 🤖 **支持多 Agent 灵活接入**：
  - **Claude Code (`claude`)**：无缝拉起本地或远程 Claude Code 交互会话。
  - **Antigravity CLI (`agy`)**：集成 Google Antigravity Agent 执行工作流。
  - **OpenAI / Codex / DeepSeek API (`codex`)**：内置轻量级自主 Agent Loop，支持自动调用远程工具（`run_command`, `read_file`, `edit_file`, `list_directory` 等）。
  - **原生 Shell (`shell`)**：快速挂载原生交互式 SSH / 本地 PTY 终端。

- ⚡ **极致轻量与超低延迟**：
  - 启动内存仅 **15MB - 35MB**，极低 CPU 占用。
  - SSH 连接针对交互延迟深度优化（开启 `TCP_NODELAY`，禁用压缩，优化套接字缓冲区读取）。

- 🔄 **会话持久化与后台守护 (Daemon)**：
  - 所有任务在独立后台线程中运行，即使退出当前 CLI 终端，远程训练或评测任务依然在后台持续执行。
  - 重新输入 `server-helper` 并使用 `/switch <任务名>` 即可秒级重新挂载接管。

- 📢 **多任务全量广播 (Broadcast)**：
  - 一键向所有运行中的并发任务同时下发监控指令（例如 `/broadcast nvidia-smi` 或 `/broadcast git pull`）。

- 📦 **标准开源可发布规范**：
  - 符合现代 Python 打包标准（`pyproject.toml`、PEP 621），支持 `pip install -e .` 安装后全局直接使用 `server-helper` 或 `shmux` 别名。

---

## 📦 安装与快速开始

### 方式一：克隆仓库与本地开发安装（推荐）

```bash
# 克隆仓库
git clone https://github.com/your-repo/server-helper.git
cd server-helper

# 使用 uv（推荐，极速）
uv venv
uv pip install -e .

# 或者使用标准 venv
python -m venv .venv
.\.venv\Scripts\pip install -e .
```

### 方式二：一键运行（Windows）

直接双击 [start.bat](file:///D:/server-helper/start.bat) 或在终端执行：
```powershell
.\start.ps1
```

---

## ⚙️ 配置文件说明 (`setting.json`)

ServerHelper 优先读取工作目录下的 `./setting.json`，若未找到则自动使用 `~/.server-helper/setting.json`。

完整配置示例如下：

```json
{
  "servers": [
    {
      "name": "gpu-node-1",
      "host": "192.168.1.100",
      "port": 22,
      "user": "ubuntu",
      "auth": "key",
      "key_path": "C:/Users/username/.ssh/id_rsa",
      "default_dir": "/workspace"
    }
  ],
  "agents": {
    "default": "claude",
    "claude": {
      "name": "Claude Code",
      "cmd": "claude",
      "type": "cli"
    },
    "agy": {
      "name": "Antigravity CLI",
      "cmd": "agy",
      "type": "cli"
    },
    "codex": {
      "name": "OpenAI / Codex API",
      "api_base": "https://api.deepseek.com/v1",
      "api_key": "sk-your-api-key-here",
      "model": "deepseek-chat",
      "type": "api"
    }
  },
  "settings": {
    "theme": "dark",
    "auto_reconnect": true,
    "keepalive_interval": 15
  }
}
```

---

## 🎮 CLI 交互体验 (OpenCode / Pi 风格)

终端运行：
```bash
server-helper
# 或者使用简短别名
shmux
```

进入交互终端后，即可通过斜杠指令（支持 Tab 自动补全）操作多任务：

```text
 ███████╗███████╗██████╗ ██╗   ██╗███████╗██████╗ 
 ██╔════╝██╔════╝██╔══██╗██║   ██║██╔════╝██╔══██╗
 ███████╗█████╗  ██████╔╝██║   ██║█████╗  ██████╔╝
 ╚════██║██╔══╝  ██╔══██╗╚██╗ ██╔╝██╔══╝  ██╔══██╗
 ███████║███████╗██║  ██║ ╚████╔╝ ███████╗██║  ██║
 ╚══════╝╚══════╝╚═╝  ╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝
 ⚡ ServerHelper Agent CLI v0.2.0 | OpenCode / Pi Style
 输入 /help 查看指令列表，输入 /connect 连接远程服务器

server-helper > /help
```

### 常用指令表

| 命令 | 别名 | 功能说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `/connect` | `/c` | 交互式选择远程服务器与工作目录，快速建立新任务 | `/connect` |
| `/tasks` | `/ls` | 查看当前所有运行中的任务及状态 | `/tasks` |
| `/switch <名称>` | | 切换当前活跃工作区上下文 | `/switch safety-eval` |
| `/terminal` | `/sh` | 进入当前任务的原生交互终端（按 `Ctrl+]` 随时脱离返回） | `/terminal` |
| `/agent <类型>` | | 切换当前任务关联的 Agent 引擎（`claude`, `agy`, `codex`, `shell`） | `/agent agy` |
| `/status` | | 查看当前服务器硬件监控（GPU 显存、CPU、内存）及 Git 状态 | `/status` |
| `/broadcast <命令>`| `/b` | 向所有活跃并发任务同时广播执行指令 | `/broadcast nvidia-smi` |
| `/close [名称]` | | 停止当前或指定的任务 | `/close rec-task` |
| `/servers` | | 查看或管理已保存的远程服务器配置 | `/servers` |
| `/config` | | 查看或检查当前 `setting.json` 状态 | `/config` |
| `/clear` | | 清除当前终端屏幕 | `/clear` |
| `/exit` | `/quit` | 退出 CLI 交互界面（**后台任务不受影响，继续稳定运行**） | `/exit` |

### 自然语言下发

在选定活跃任务后，无需输入斜杠，直接在输入框中输入自然语言即可下发任务：
```text
[gpu-node-1: /workspace/safety] server-helper > 检查当前目录下的评测日志，并排查 OOM 报错
```

---

## 🖥️ 命令行非交互调用 (Subcommands)

除了全功能交互式 CLI 之外，ServerHelper 还支持直接在脚本或命令行中单次调用：

```bash
# 查看所有后台任务
server-helper list

# 启动新任务 (指定服务器、目录和 Agent)
server-helper start safety --server gpu-node-1 --dir /workspace/safety --agent claude

# 直接挂接到任务的终端
server-helper attach safety

# 向所有后台任务广播执行指令
server-helper broadcast "nvidia-smi"

# 停止任务
server-helper stop safety

# 管理远程服务器
server-helper server list
server-helper server add node-2 --host 192.168.1.101 --user ubuntu --auth key --key ~/.ssh/id_rsa --dir /workspace
server-helper server rm node-2

# 启动可选的 Web 浏览器版控制台
server-helper web --port 8765
```

---

## 🧪 自动化测试验证

运行测试验证全链路指令与配置读取：
```bash
python test_agent_cli.py
```

执行 Agent 仿真并发压测：
```bash
python test_agent_simulation.py
```

---

## 📄 开源许可证

本项目基于 MIT License 开源发布。
