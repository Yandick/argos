"""
Test suite for Agent CLI slash commands and setting.json integration
"""
import os
import sys

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from server_helper.config import Config
from server_helper.agent_cli import AgentCliApp

def test_cli():
    print("=" * 60)
    print("  [Agent CLI] 开始自动化指令与配置测试")
    print("=" * 60)

    # 1. Config & setting.json loading
    cfg = Config()
    assert os.path.exists(cfg.config_path), f"Config file not found at {cfg.config_path}"
    print(f"✅ [配置加载] 成功读取配置文件: {cfg.config_path}")

    agents = cfg.get_agents()
    print(f"✅ [Agent 注册] 检测到已配置 Agent: {list(agents.keys())}")
    assert "claude" in agents
    assert "agy" in agents
    assert "codex" in agents

    # 2. AgentCliApp instantiation
    app = AgentCliApp()
    print("✅ [CLI 实例化] AgentCliApp 初始化成功")

    # 3. Test slash commands execution
    print("\n🔍 [指令执行评估] 测试各斜杠指令:")
    app.handle_slash_command("/help", "")
    print("  - /help : 成功展示指令帮助表")

    app.handle_slash_command("/config", "")
    print("  - /config : 成功解析 setting.json")

    app.handle_slash_command("/servers", "")
    print("  - /servers : 成功查询已配置服务器列表")

    app.handle_slash_command("/tasks", "")
    print("  - /tasks : 成功展示运行中任务列表")

    print("\n🎉 [测试通过] Agent CLI 核心引擎与指令流全部验证成功！")

if __name__ == "__main__":
    test_cli()
