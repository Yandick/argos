"""
Simulation and Multi-Agent Evaluation Script
Simulates concurrent coding agent loops running on separate tasks,
testing tool calling, state transitions, file operations, and memory consumption.
"""
import os
import sys

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import time
import json
import threading
import psutil

from config_manager import ConfigManager
from session_manager import SessionManager
from agent_engine import AgentEngine

def run_evaluation():
    print("=" * 60)
    print("  [Agent Deck] 开始多方面自动化评估与 Agent Loop 仿真测试")
    print("=" * 60)

    cfg = ConfigManager()
    sm = SessionManager()
    engine = AgentEngine(cfg, sm)

    # 1. Memory benchmark before tasks
    proc = psutil.Process()
    mem_initial = proc.memory_info().rss / (1024 * 1024)
    print(f"📊 [基准测试] 初始常驻内存占用: {mem_initial:.2f} MB")

    # 2. Create two isolated test workspaces (simulating rec and safety tasks locally)
    test_dir_rec = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_env", "rec_project")
    test_dir_safety = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_env", "safety_project")
    os.makedirs(test_dir_rec, exist_ok=True)
    os.makedirs(test_dir_safety, exist_ok=True)

    # Put a mock training script in rec
    with open(os.path.join(test_dir_rec, "train_rec.py"), "w", encoding="utf-8") as f:
        f.write("# Recommendation Model Training Script\nprint('Initializing Rec Model...')\nprint('Batch size: 128')\n")

    # Put a mock evaluation script in safety
    with open(os.path.join(test_dir_safety, "eval_safety.py"), "w", encoding="utf-8") as f:
        f.write("# Safety Alignment Evaluation\nprint('Running Toxicity & Red-Teaming Benchmarks...')\n")

    print("📁 [环境准备] 已创建隔离测试工作目录: rec_project 与 safety_project")

    # 3. Create Session 1 (Rec Task) and Session 2 (Safety Task)
    sess1, err1 = sm.create_session(
        session_type="local_pty",
        name="rec-model-train",
        cwd=test_dir_rec,
        startup_cmd="powershell.exe -NoLogo"
    )
    assert sess1 is not None, f"Failed to create Session 1: {err1}"

    sess2, err2 = sm.create_session(
        session_type="local_pty",
        name="safety-alignment",
        cwd=test_dir_safety,
        startup_cmd="powershell.exe -NoLogo"
    )
    assert sess2 is not None, f"Failed to create Session 2: {err2}"

    print(f"✅ [会话创建] 会话1 (Rec): {sess1.session_id} | 会话2 (Safety): {sess2.session_id}")

    # 4. Test tool execution directly
    print("\n🛠️ [工具链评估] 测试 Agent 工具调用能力:")
    # Test list_directory
    res_list = engine._execute_tool(sess1, "list_directory", {"path": test_dir_rec})
    print(f"  - list_directory: {res_list.strip()[:60]}... (PASS)")
    assert "train_rec.py" in res_list

    # Test read_file
    res_read = engine._execute_tool(sess1, "read_file", {"path": os.path.join(test_dir_rec, "train_rec.py")})
    print(f"  - read_file: {res_read.strip()[:60]}... (PASS)")
    assert "Batch size" in res_read

    # Test write_file
    res_write = engine._execute_tool(sess1, "write_file", {
        "path": os.path.join(test_dir_rec, "params.json"),
        "content": '{"learning_rate": 0.001, "epochs": 50}'
    })
    print(f"  - write_file: {res_write} (PASS)")
    assert os.path.exists(os.path.join(test_dir_rec, "params.json"))

    # Test edit_file
    res_edit = engine._execute_tool(sess1, "edit_file", {
        "path": os.path.join(test_dir_rec, "train_rec.py"),
        "old_str": "Batch size: 128",
        "new_str": "Batch size: 256 (Optimized for GPU)"
    })
    print(f"  - edit_file: {res_edit} (PASS)")
    with open(os.path.join(test_dir_rec, "train_rec.py"), "r", encoding="utf-8") as f:
        assert "Batch size: 256" in f.read()

    # Test run_command
    res_cmd = engine._execute_tool(sess1, "run_command", {"command": "echo AGENT_TOOL_EXEC_SUCCESS"})
    print(f"  - run_command: {res_cmd.strip()} (PASS)")
    assert "AGENT_TOOL_EXEC_SUCCESS" in res_cmd

    # 5. Simulate Multi-Agent Concurrent Loops (Agent 1 & Agent 2 running in parallel)
    print("\n🤖 [并发 Agent Loop 仿真] 同时并发运行两个 Agent 任务:")
    events_rec = []
    events_safety = []

    def on_event_rec(ev):
        events_rec.append(ev)

    def on_event_safety(ev):
        events_safety.append(ev)

    task1 = engine.create_task(sess1.session_id, "分析 rec 项目结构并检查模型训练参数", on_event=on_event_rec)
    task2 = engine.create_task(sess2.session_id, "检查 safety 评测环境并进行安全对齐诊断", on_event=on_event_safety)

    engine.start_task(task1.task_id)
    engine.start_task(task2.task_id)

    print("  - Agent 1 (Rec Task) 已启动循环...")
    print("  - Agent 2 (Safety Task) 已启动循环...")

    # Wait for completion
    timeout = 15
    start_t = time.time()
    while time.time() - start_t < timeout:
        if task1.status in ("completed", "stopped") and task2.status in ("completed", "stopped"):
            break
        time.sleep(0.3)

    print(f"\n📈 [并发结果] Agent 1 状态: {task1.status} (收集 {len(events_rec)} 个事件)")
    print(f"📈 [并发结果] Agent 2 状态: {task2.status} (收集 {len(events_safety)} 个事件)")

    assert len(events_rec) > 0, "Agent 1 should produce events"
    assert len(events_safety) > 0, "Agent 2 should produce events"

    # Verify event types produced
    rec_event_types = set(e["event"] for e in events_rec)
    print(f"  - Agent 1 事件流包含: {rec_event_types}")
    assert "thought" in rec_event_types
    assert "tool_call" in rec_event_types
    assert "tool_result" in rec_event_types

    # 6. Memory benchmark during active load
    mem_final = proc.memory_info().rss / (1024 * 1024)
    print(f"\n💡 [内存与性能评估] 两个 Agent 并发运行且维护 2 个 PTY 会话时常驻内存: {mem_final:.2f} MB")
    print(f"  - 内存增量: {mem_final - mem_initial:.2f} MB")
    assert mem_final < 100.0, "Memory must remain lightweight (<100MB)"

    # Clean up sessions
    sm.close_session(sess1.session_id)
    sm.close_session(sess2.session_id)
    print("\n🎉 [评估完成] 全部测试用例均 100% 通过！系统各模块表现完美！")

if __name__ == "__main__":
    run_evaluation()
