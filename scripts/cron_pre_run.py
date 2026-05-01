#!/usr/bin/env python3
"""
Cron job 前置脚本
运行自动迭代测试，输出摘要供 cron job prompt 使用
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
os.chdir(REPO)

# 加载 .env 到环境变量
env = os.environ.copy()
with open("/root/.hermes/.env", "r") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            # 处理可能带有空格的行，如 "KEY=val  # comment"
            key_part = line.split()[0]
            if "=" in key_part:
                key, val = key_part.split("=", 1)
                env[key] = val

# 运行测试脚本
result = subprocess.run(
    [sys.executable, "scripts/auto_iterative_test.py"],
    capture_output=True,
    text=True,
    env=env,
    timeout=600
)

print("=== AUTO TEST OUTPUT ===")
print(result.stdout)
if result.stderr:
    print("=== STDERR ===")
    print(result.stderr)

# 读取状态
state_file = REPO / "data/processed/auto_test_state.json"
if state_file.exists():
    with open(state_file, "r") as f:
        state = json.load(f)
    print(f"\n=== STATE ===")
    print(f"已完成批次: {state.get('batch_count', 0)}")
    print(f"累计测试: {len(state.get('tested_ids', []))} 条")
    print(f"剩余未测试: {500 - len(state.get('tested_ids', []))} 条")

# 读取最新报告
report_file = REPO / "data/processed/auto_test_report.md"
if report_file.exists():
    content = report_file.read_text()
    # 提取最新一批
    sections = content.split("## 第")
    if len(sections) > 1:
        latest = "## 第" + sections[-1]
        print(f"\n=== LATEST BATCH REPORT ===")
        print(latest)
    else:
        print(f"\n=== FULL REPORT ===")
        print(content)
