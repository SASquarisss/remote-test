#!/usr/bin/env python3
"""每2小时代码评审对话脚本
每2小时执行：拉取评审意见 → 判断对话状态 → LLM分析 → 追加comment → push
"""

import os
import sys
import subprocess
import re
from datetime import datetime, timedelta
from pathlib import Path

REPO_PATH = Path("/root/.hermes/hermes-agent/remote-test")
OPINION_DIR = REPO_PATH / "opinion" / "opinion_from_大剑"
ENV_FILE = Path("/root/.hermes/.env")
MY_NAME = "sxc的魔法老头"
END_MARKERS = ["无异议", "按上述共识执行", "共识已达成", "同意按此执行", "讨论结束", "无需进一步讨论"]


def get_now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


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


def find_recent_opinion_files(hours=48):
    """查找最近 hours 小时内修改的 .md 意见文件，按修改时间排序"""
    cutoff = datetime.now().timestamp() - hours * 3600
    files = []
    if not OPINION_DIR.exists():
        return files
    for path in OPINION_DIR.glob("*.md"):
        mtime = path.stat().st_mtime
        if mtime >= cutoff:
            files.append((path, mtime))
    files.sort(key=lambda x: x[1])
    return [p for p, _ in files]


def get_comment_path(opinion_path):
    """根据意见文件路径获取对应的 comment 文件路径"""
    return OPINION_DIR / f"comment_{opinion_path.stem}"


def parse_discussion(comment_path):
    """解析 comment 文件，返回段落列表 [(author, timestamp, content), ...]"""
    if not comment_path.exists():
        return []
    text = comment_path.read_text(encoding="utf-8")
    # 按 "# 名字 | YYYY-MM-DD HH:MM" 分割
    pattern = r'^# (.+?) \| (\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\n'
    parts = re.split(pattern, text, flags=re.MULTILINE)
    blocks = []
    if len(parts) > 1:
        for i in range(1, len(parts), 3):
            if i + 2 <= len(parts):
                author = parts[i].strip()
                ts = parts[i + 1].strip()
                content = parts[i + 2].strip()
                # 移除末尾的分隔线 ---
                content = re.sub(r'\n*---\s*$', '', content)
                blocks.append((author, ts, content))
    return blocks


def is_my_block(author):
    return MY_NAME in author


def has_declared_end(content):
    """检查内容中是否已声明结束/收敛"""
    return any(marker in content for marker in END_MARKERS)


def needs_reply(opinion_path, comment_path):
    """判断是否需要回复。返回 (need: bool, reason: str)"""
    if not comment_path.exists():
        return True, "首次回复"

    opinion_mtime = opinion_path.stat().st_mtime
    comment_mtime = comment_path.stat().st_mtime
    blocks = parse_discussion(comment_path)

    if not blocks:
        return True, "comment 文件无有效段落"

    last_author, last_ts, last_content = blocks[-1]

    if not is_my_block(last_author):
        return True, "对方有新回复"

    # 最后一段是我写的
    if has_declared_end(last_content):
        return False, "已声明结束，等待对方确认"

    if opinion_mtime > comment_mtime + 60:  # 意见文件比我的回复更新（容差60秒）
        return True, "意见文件有新补充"

    return False, "等待对方回复"


def normalize_reply(content):
    """确保回复内容以正确的标题格式开头"""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("# "):
            if MY_NAME not in line:
                # 替换为正确标题
                lines[i] = f"# {MY_NAME} | {get_now_str()}"
            return "\n".join(lines[i:])
    # 未找到标题，在前面添加
    return f"# {MY_NAME} | {get_now_str()}\n\n{content}"


def build_first_prompt(opinion_content):
    now = get_now_str()
    return f"""你是 Hermes Agent「{MY_NAME}」，负责审核另一位 AI Agent 的评审意见。

请仔细阅读以下评审意见，并给出专业判断：

【评审意见】
{opinion_content}

请从以下几个维度进行分析：
1. 准确性：指出的问题是否真实存在？
2. 优先级：建议的修改优先级是否合理？
3. 可行性：提出的修改建议是否可行？
4. 遗漏：是否有重要的问题被遗漏了？

输出格式要求（严格遵守）：
# {MY_NAME} | {now}

总体评价：（简要总结，100字以内）
逐条确认：（对每条建议给出同意/部分同意/不同意及理由，每条不超100字）
遗漏补充：（如有遗漏，请补充）
后续行动：（建议优先处理哪些事项）

用中文输出，保持专业、简洁。不要在末尾添加 "---" 分隔线。"""


def build_dialogue_prompt(opinion_content, discussion_blocks):
    now = get_now_str()

    # 构建对话历史摘要
    history_lines = []
    for author, ts, content in discussion_blocks:
        label = "【我】" if is_my_block(author) else f"【{author}】"
        summary = content[:200] + "..." if len(content) > 200 else content
        history_lines.append(f"{label} {ts}:")
        history_lines.append(summary)
        history_lines.append("")

    # 提取对方的最后一条回复
    opponent_reply = ""
    for author, ts, content in reversed(discussion_blocks):
        if not is_my_block(author):
            opponent_reply = content[:1200]
            break

    return f"""你是 Hermes Agent「{MY_NAME}」。你正在与另一位 AI Agent 就代码评审意见进行技术讨论。

【原始评审意见背景】
{opinion_content[:1200]}

【对话历史摘要】
{chr(10).join(history_lines)}

【对方最新回复】
{opponent_reply}

请针对对方的最新回复进行回应。要求：
1. 判断对方观点的正确性、合理性、可行性
2. 如有分歧，清晰陈述你的立场和依据，将分歧点逐条理清楚
3. 在正确的前提下，尽可能与对方达成一致，使意见收敛
4. 严格控制回复长度，聚焦核心分歧，不展开无关内容
5. 如果已无实质性分歧，明确声明"无异议，按上述共识执行"并结束

输出格式要求（严格遵守）：
# {MY_NAME} | {now}

（你的回复内容，不超过500字，严谨、专业、认真）

用中文。不要在末尾添加 "---" 分隔线。"""


def analyze_with_llm(opinion_content, discussion_blocks=None):
    from openai import OpenAI
    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1"
    )

    if not discussion_blocks:
        prompt = build_first_prompt(opinion_content)
    else:
        prompt = build_dialogue_prompt(opinion_content, discussion_blocks)

    resp = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4096,
        timeout=300,
    )
    return normalize_reply(resp.choices[0].message.content.strip())


def write_first_comment(comment_path, content):
    with open(comment_path, "w", encoding="utf-8") as f:
        f.write(content + "\n\n---\n")
    return comment_path


def append_comment(comment_path, content):
    with open(comment_path, "a", encoding="utf-8") as f:
        f.write("\n" + content + "\n\n---\n")
    return comment_path


def git_push_changes(paths):
    for p in paths:
        run_git(["add", str(p)], check=False)
    commit_result = run_git(["commit", "-m", f"review dialogue update at {get_now_str()}"], check=False)
    if commit_result.returncode != 0:
        out = commit_result.stdout + commit_result.stderr
        if "nothing to commit" in out or "no changes added" in out:
            return False
        raise RuntimeError(f"git commit 失败: {out}")
    # push 前再次 rebase，防止处理期间有更新
    run_git(["pull", "--rebase", "origin", "main"], check=False)
    push_result = run_git(["push", "origin", "main"], check=False)
    if push_result.returncode != 0:
        raise RuntimeError(f"git push 失败: {push_result.stderr}")
    return True


def process_opinion(opinion_path):
    comment_path = get_comment_path(opinion_path)
    need, reason = needs_reply(opinion_path, comment_path)
    if not need:
        print(f"  ⏭️ 跳过 {opinion_path.name}: {reason}")
        return None, reason

    print(f"  📄 处理 {opinion_path.name} ({reason})")
    opinion_content = opinion_path.read_text(encoding="utf-8")
    discussion_blocks = parse_discussion(comment_path)
    analysis = analyze_with_llm(opinion_content, discussion_blocks if discussion_blocks else None)

    if not discussion_blocks:
        write_first_comment(comment_path, analysis)
    else:
        append_comment(comment_path, analysis)

    return comment_path, reason


def main():
    try:
        load_env()

        # 1. git pull --rebase
        pull_result = run_git(["pull", "--rebase", "origin", "main"], check=False)
        if pull_result.returncode != 0:
            raise RuntimeError(f"git pull 失败: {pull_result.stderr}")

        # 2. 查找最近48小时内的意见文件
        opinion_files = find_recent_opinion_files(48)
        if not opinion_files:
            print("⚠️ 未找到最近48小时内的评审意见文件")
            return 0

        processed = []
        skip_reasons = []
        for opinion_path in opinion_files:
            comment_path, reason = process_opinion(opinion_path)
            if comment_path:
                processed.append(comment_path)
                processed.append(opinion_path)
            else:
                skip_reasons.append(f"{opinion_path.name}: {reason}")

        if not processed:
            print("✅ 无需回复，所有对话已收敛或等待对方")
            if skip_reasons:
                for r in skip_reasons:
                    print(f"   {r}")
            return 0

        # 3. push
        pushed = git_push_changes(processed)

        # 4. 输出汇报
        reply_count = len([p for p in processed if "comment_" in p.name])
        summary = f"""📋 代码评审对话报告 ({get_now_str()})

处理意见文件: {len(opinion_files)} 个
生成回复: {reply_count} 个
跳过: {len(skip_reasons)} 个

{'✅ 已推送更新' if pushed else '⚠️ 无新内容需推送'}
"""
        print(summary)
        return 0

    except Exception as e:
        print(f"❌ 评审流程异常: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
