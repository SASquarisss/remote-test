#!/usr/bin/env python3
"""每日代码评审脚本
每日 08:30 执行：拉取大剑的评审意见 → LLM分析 → 生成comment → push → 输出汇报
"""

import os
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

REPO_PATH = Path("/root/.hermes/hermes-agent/remote-test")
OPINION_DIR = REPO_PATH / "opinion" / "opinion_from_大剑"
ENV_FILE = Path("/root/.hermes/.env")

def get_yesterday_str():
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime("%Y%m%d")

def load_env():
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key, value)

def run_git(args, check=True):
    return subprocess.run(["git"] + args, cwd=REPO_PATH, capture_output=True, text=True, check=check)

def find_opinion_file(date_str):
    for ext in ["", ".md", ".txt"]:
        path = OPINION_DIR / f"{date_str}{ext}"
        if path.exists():
            return path
    return None

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def analyze_with_llm(opinion_content):
    from openai import OpenAI
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1"
    )

    prompt = f"""你是 Hermes Agent（sxc的魔法老头），负责审核另一位 AI Agent（sxc的大剑）对代码的评审意见。

请仔细阅读以下评审意见，并给出你的专业判断：

【大剑的评审意见】
{opinion_content}

请从以下几个维度进行分析：
1. 准确性：大剑指出的问题是否真实存在？
2. 优先级：建议的修改优先级是否合理？
3. 可行性：提出的修改建议是否可行？
4. 遗漏：是否有重要的问题被大剑遗漏了？

请输出以下格式的回复：
- 总体评价：（简要总结，100字以内）
- 逐条确认：（对每条建议给出同意/部分同意/不同意及理由，每条不超100字）
- 遗漏补充：（如有遗漏，请补充）
- 后续行动：（建议优先处理哪些事项）

请用中文输出，保持专业、简洁。"""

    resp = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4096,
        timeout=300,
    )
    return resp.choices[0].message.content

def write_comment(date_str, content):
    path = OPINION_DIR / f"comment_{date_str}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path

def git_push_comment(comment_path):
    run_git(["add", str(comment_path)], check=False)
    commit_result = run_git(["commit", "-m", f"daily review comment for {comment_path.name}"], check=False)
    if commit_result.returncode != 0:
        if "nothing to commit" in commit_result.stdout or "nothing to commit" in commit_result.stderr:
            print("⚠️ 无新内容需推送")
            return False
        raise RuntimeError(f"git commit 失败: {commit_result.stderr}")
    push_result = run_git(["push", "origin", "main"], check=False)
    if push_result.returncode != 0:
        raise RuntimeError(f"git push 失败: {push_result.stderr}")
    return True

def main():
    try:
        load_env()
        yesterday = get_yesterday_str()

        # 1. git pull
        pull_result = run_git(["pull", "origin", "main"], check=False)
        if pull_result.returncode != 0:
            raise RuntimeError(f"git pull 失败: {pull_result.stderr}")

        # 2. 查找大剑的意见文件
        opinion_path = find_opinion_file(yesterday)
        if not opinion_path:
            msg = f"⚠️ 未找到 {yesterday} 的评审意见文件\n目录: {OPINION_DIR}"
            print(msg)
            return 1

        # 3. 读取并分析
        opinion_content = read_file(opinion_path)
        if len(opinion_content.strip()) < 10:
            print(f"⚠️ 意见文件内容过短，跳过分析")
            return 1

        analysis = analyze_with_llm(opinion_content)

        # 4. 写入 comment 文件
        comment_path = write_comment(yesterday, analysis)

        # 5. push
        pushed = git_push_comment(comment_path)

        # 6. 输出汇报摘要
        summary = f"""📋 每日代码评审报告 ({yesterday})

{analysis[:1000]}

✅ 已生成并推送 comment_{yesterday}
📌 请查看并讨论是否需要调整，或直接微信回复。"""
        print(summary)
        return 0

    except Exception as e:
        print(f"❌ 每日评审流程异常: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
