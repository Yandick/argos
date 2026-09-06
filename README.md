<div align="center">

<img src="assets/logo.png" width="128" height="128" alt="ServerHelper logo" />

# ⚡ ServerHelper · Argos

**A lightweight, low-latency remote multi-task terminal workbench for Coding Agents.**

Manage Claude Code · Antigravity (`agy`) · Codex / API agents · native shells — all from one terminal, across many servers, with tasks that keep running in the background.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.3.0-green.svg)](./pyproject.toml)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey.svg)](#-install--quick-start)
[![Memory](https://img.shields.io/badge/RAM-15--35MB-brightgreen.svg)](#-why-serverhelper)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-success.svg)](#-contributing)

<strong>English</strong> · <a href="README.zh-CN.md">简体中文</a>

*Inspired by the interaction aesthetics of OpenCode and Pi.*

</div>

---

## 🌟 Why ServerHelper?

When you drive Coding Agents (`claude`, `agy`, or API-based custom agents) against remote servers across several tasks at once — one doing `rec` data processing, one running `safety` evals, one on continuous tests — the usual workflows hurt:

1. **3–5 local terminal windows** open at once; switching is tedious and it's easy to `cd` into the wrong place or kill the wrong task.
2. **Heavy remote web/GUI stacks** eat a lot of memory on the server.
3. **No unified config or context scheduling** between your local and remote agents.

ServerHelper is a **pure terminal CLI** that uses only **~15–35 MB** of RAM and starts in under a second. One unified terminal manages every remote and local task; tasks persist in a background daemon; and you get an OpenCode / Pi-style slash-command experience with an agent bridge.

---

## ✨ Features

- 🎯 **OpenCode & Pi-style interactive Agent CLI**
  - Run `server-helper` (or `shmux` / `argos`) to enter an immersive workbench.
  - Slash commands (`/connect`, `/tasks`, `/switch`, `/terminal`, `/agent`, `/status`, `/broadcast`, `/lang`, …) with **Tab auto-completion** and arrow-key navigation.
  - Type plain natural language to dispatch work straight to the selected agent.

- 🌐 **Bilingual UI (English / 中文)** — switch the whole interface with `/lang` in the CLI or the 🌐 button in the Web console. Choice is persisted; it only affects UI text, never the agent's reply language.

- 🤖 **Flexible multi-agent support**
  - **Claude Code (`claude`)** — launch local or remote interactive sessions.
  - **Antigravity CLI (`agy`)** — Google Antigravity agent workflows.
  - **OpenAI / Codex / DeepSeek API (`codex`)** — a built-in lightweight autonomous agent loop with remote tools (`run_command`, `read_file`, `write_file`, `edit_file`, `list_directory`, `check_gpu_and_system`).
  - **Native shell (`shell`)** — mount a raw interactive SSH / local PTY terminal.

- ⚡ **Extremely light & low-latency**
  - **15–35 MB** startup footprint, minimal CPU.
  - SSH tuned for interactive latency: `TCP_NODELAY` on, compression off, optimized socket reads.

- 🔄 **Persistent sessions & background daemon**
  - Tasks run in independent background threads; exit the CLI and your remote training/eval keeps running.
  - Re-run `server-helper` and `/switch <task>` to re-attach in seconds.

- 📢 **Multi-task broadcast** — send one command to all running tasks at once (`/broadcast nvidia-smi`, `/broadcast git pull`).

- 🖥️ **Optional Web console** — a browser dashboard with live xterm terminals, an agent chat panel, and an SFTP file drawer.

- 📦 **Standard, publishable packaging** — modern `pyproject.toml` (PEP 621); `pip install -e .` gives you global `server-helper` / `shmux` / `argos` commands.

---

## 📦 Install & Quick Start

### Option 1 — Clone & local dev install (recommended)

```bash
git clone https://github.com/Yandick/argos.git
cd argos

# With uv (recommended, fastest)
uv venv
uv pip install -e .

# Or with a standard venv
python -m venv .venv
# Windows
.\.venv\Scripts\pip install -e .
# Linux / macOS
./.venv/bin/pip install -e .
```

### Option 2 — One-click run (Windows)

Double-click [`start.bat`](./start.bat), or run:

```powershell
.\start.ps1
```

### Option 3 — One-line installer

```bash
# Linux / macOS
curl -fsSL https://raw.githubusercontent.com/Yandick/argos/main/install.sh | bash
```
```powershell
# Windows PowerShell
irm https://raw.githubusercontent.com/Yandick/argos/main/install.ps1 | iex
```

---

## ⚙️ Configuration (`setting.json`)

ServerHelper reads `./setting.json` from the working directory first, then falls back to `~/.server-helper/setting.json`. Copy [`setting.example.json`](./setting.example.json) to get started.

```jsonc
{
  "servers": [
    {
      "name": "gpu-node-1",
      "host": "192.168.1.100",
      "port": 22,
      "user": "ubuntu",
      "auth": "key",                 // "key" or "password"
      "key_path": "~/.ssh/id_rsa",
      "default_dir": "/workspace",
      "remote_proxy_port": 10808     // optional SSH reverse-tunnel port
    }
  ],
  "agents": {
    "default": "claude",
    "claude": { "name": "Claude Code", "cmd": "claude", "type": "cli" },
    "agy":    { "name": "Antigravity CLI", "cmd": "agy", "type": "cli" },
    "codex":  { "name": "OpenAI / Codex API", "api_base": "https://api.deepseek.com/v1", "api_key": "sk-...", "model": "deepseek-chat", "type": "api" }
  },
  "settings": {
    "language": "en",                // "en" | "zh"
    "theme": "catppuccin",
    "auto_reconnect": true,
    "keepalive_interval": 15
  }
}
```

> 🔒 **Security note:** `setting.json` may contain SSH passwords and is **git-ignored** by default. Never commit it. If a credential is ever leaked, rotate it immediately.

---

## 🎮 CLI Experience (OpenCode / Pi style)

```bash
server-helper      # or: shmux  /  argos
```

```text
  ▄▀█ █▀█ █▀▀ █▀█ █▀   argos  v0.3.0 · autonomous coding agent orchestrator
  █▀█ █▀▄ █▄█ █▄█ ▄█   Ἄργος Πανόπτης · multi-server remote workspace harness

  Target:    Not connected (type /server to select environment)  idle
  Workspace: /
  Engine:    agy · gemini-3.8-flash (effort: high)
  Proxy:     http://127.0.0.1:7897
  Theme:     catppuccin

Shortcuts: /server target · /files files · /sh terminal · /model models · /help help
```

### Command reference

| Command | Alias | Description | Example |
| :--- | :--- | :--- | :--- |
| `/connect` | `/c` `/server` | Interactively pick a server & working dir, start a task | `/connect` |
| `/tasks` | `/ls` | List all running tasks and their state | `/tasks` |
| `/switch <name>` | `/sw` | Switch the active workspace context | `/switch safety-eval` |
| `/terminal` | `/sh` | Enter the task's raw interactive terminal (`Ctrl+]` to detach) | `/terminal` |
| `/agent <type>` | | Switch the task's agent engine (`claude`, `agy`, `codex`, `shell`) | `/agent agy` |
| `/model <name>` | | Switch the active LLM model | `/model gemini-3.8-flash` |
| `/effort <level>` | | Set reasoning effort (`high`/`medium`/`low`/`off`) | `/effort high` |
| `/proxy <url\|off>` | | Configure HTTP proxy & SSH reverse tunnel | `/proxy http://127.0.0.1:7897` |
| `/status` | | Show remote GPU / CPU / memory and Git status | `/status` |
| `/broadcast <cmd>` | `/b` | Broadcast a command to all active tasks | `/broadcast nvidia-smi` |
| `/theme <name>` | | Switch UI color theme (live preview) | `/theme tokyo-night` |
| `/lang <en\|zh>` | | Switch interface language (no arg = toggle) | `/lang zh` |
| `/close [name]` | `/stop` | Stop the current or a named task | `/close rec-task` |
| `/config` | | Inspect current `setting.json` | `/config` |
| `/clear` | | Clear screen & redraw the dashboard | `/clear` |
| `/help` | | Full command & shortcut guide | `/help` |
| `/exit` | `/quit` | Exit the CLI (**background tasks keep running**) | `/exit` |

### Natural-language dispatch

With an active task selected, just type — no slash needed:

```text
[gpu-node-1: /workspace/safety] argos › check the eval logs in this dir and trace the OOM error
```

---

## 🖥️ Non-interactive Subcommands

```bash
server-helper list                                   # list background tasks
server-helper start safety --server gpu-node-1 --dir /workspace/safety --agent claude
server-helper attach safety                          # attach to a task terminal
server-helper broadcast "nvidia-smi"                 # broadcast to all tasks
server-helper stop safety                            # stop a task
server-helper server list                            # manage saved servers
server-helper server add node-2 --host 192.168.1.101 --user ubuntu --auth key --key ~/.ssh/id_rsa --dir /workspace
server-helper web --port 8765                        # launch the Web console
```

---

## 🧪 Tests

```bash
python test_agent_cli.py          # end-to-end command & config checks
python test_agent_simulation.py   # concurrent agent stress simulation
```

---

## 🗺️ Roadmap

- [ ] Unify the root modules and `src/server_helper/` into a single implementation
- [ ] Optional keyring-backed credential storage
- [ ] Token-based auth for the Web console
- [ ] More themes & agent integrations

---

## 🤝 Contributing

Issues and PRs are welcome. Please keep `setting.json` out of version control and add tests for new behavior.

## 📄 License

Released under the [MIT License](./LICENSE).

---

<div align="center">

**English** · <a href="README.zh-CN.md">简体中文</a>

Made with ⚡ for people running many agents on many servers.

</div>
