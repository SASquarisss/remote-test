#!/usr/bin/env python3
"""
用户确认执行器
当用户在聊天中回复"同意X"或"不同意X"时，执行对应操作：
1. 将用户反馈追加到 opinion md 文件
2. 对于"同意X"，执行对应的修复（如果之前未执行）
3. git push
"""

import os
import re
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent))
from auto_fix import execute_fixes, REPO_PATH

OPINION_DIR = REPO_PATH / "opinion" / "opinion_from_大剑"
MY_NAME = "sxc的魔法老头"


def get_now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def run_git(args, check=True):
    return subprocess.run(
        ["git"] + args, cwd=REPO_PATH, capture_output=True, text=True, check=check
    )


def parse_user_confirmation(text: str) -> List[Tuple[int, bool]]:
    """
    解析用户回复，提取确认/否决。
    支持格式：
    - "同意3" → (3, True)
    - "不同意5" → (5, False)
    - "同意 3 和 5" → [(3, True), (5, True)]
    """
    results = []
    # 先匹配 "不同意X"
    for m in re.finditer(r'不同意\s*(\d+)', text):
        results.append((int(m.group(1)), False))
    # 再匹配 "同意X"，但排除已被"不同意"匹配的编号
    denied_ids = {item_id for item_id, _ in results}
    for m in re.finditer(r'(?<!不)同意\s*(\d+)', text):
        item_id = int(m.group(1))
        if item_id not in denied_ids:
            results.append((item_id, True))
    return results


def find_opinion_file_by_date(date_str: Optional[str] = None) -> Optional[Path]:
    """查找对应日期的意见文件。如果未指定，返回最近的 .md 文件"""
    if date_str:
        path = OPINION_DIR / f"{date_str}.md"
        if path.exists():
            return path
    # 找最近的
    md_files = sorted(OPINION_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return md_files[0] if md_files else None


def append_user_feedback(file_path: Path, user_content: str):
    """将用户反馈追加到意见文件"""
    now = get_now_str()
    section = f"""
# 用户确认 | {now}

{user_content}
"""
    with open(file_path, "a", encoding="utf-8") as f:
        f.write("\n\n---\n\n" + section + "\n\n---\n")
    return file_path


def extract_patch_from_opinion(file_path: Path, item_id: int) -> Optional[dict]:
    """
    从意见文件中提取指定编号的 patch 信息。
    假设之前的分析已经写入文件中。
    """
    text = file_path.read_text(encoding="utf-8")
    # 找到对应编号的条目
    pattern = rf'### {item_id}\.\s*(.+?)(?=\n### \d+\.|\n## |\Z)'
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None

    body = match.group(0)
    title = match.group(1).strip().split('\n')[0]

    fp_match = re.search(r'\*\*文件\*\*[:\uff1a]\s*`([^`]+)`', body)
    patch_match = re.search(r'```patch\s*\nSEARCH:\s*\n(.*?)\nREPLACE:\s*\n(.*?)\n```', body, re.DOTALL)

    if fp_match and patch_match:
        return {
            "title": title,
            "file_path": fp_match.group(1).strip(),
            "search": patch_match.group(1),
            "replace": patch_match.group(2),
        }
    return None


def git_push_changes(paths: List[Path]):
    for p in paths:
        run_git(["add", str(p)], check=False)
    commit_result = run_git(
        ["commit", "-m", f"user confirmation + fix at {get_now_str()}"],
        check=False,
    )
    if commit_result.returncode != 0:
        out = commit_result.stdout + commit_result.stderr
        if "nothing to commit" in out or "no changes added" in out:
            return False
        raise RuntimeError(f"git commit 失败: {out}")
    run_git(["pull", "--rebase", "origin", "main"], check=False)
    push_result = run_git(["push", "origin", "main"], check=False)
    if push_result.returncode != 0:
        raise RuntimeError(f"git push 失败: {push_result.stderr}")
    return True


def main(user_message: str, opinion_date: Optional[str] = None):
    """
    主入口
    :param user_message: 用户的聊天消息
    :param opinion_date: 意见文件日期（如 2026-04-29），未指定则用最近的
    """
    confirmations = parse_user_confirmation(user_message)
    if not confirmations:
        print("未在用户消息中检测到确认/否决，跳过")
        return 0

    opinion_file = find_opinion_file_by_date(opinion_date)
    if not opinion_file:
        print("未找到意见文件")
        return 1

    print(f"处理意见文件: {opinion_file.name}")
    print(f"检测到确认: {confirmations}")

    # 追加用户反馈到 md 文件
    append_user_feedback(opinion_file, user_message)
    paths_to_push = [opinion_file]

    # 执行用户同意的修复
    executed = []
    for item_id, approved in confirmations:
        if not approved:
            print(f"  ❌ 用户否决 #{item_id}，跳过")
            continue

        patch_info = extract_patch_from_opinion(opinion_file, item_id)
        if not patch_info:
            print(f"  ⚠️ #{item_id}: 未找到对应的 patch 信息")
            continue

        print(f"  ⚙️ 执行 #{item_id}: {patch_info['title']} → {patch_info['file_path']}")
        result = execute_fixes(
            item_id=item_id,
            title=patch_info["title"],
            file_path_str=patch_info["file_path"],
            search=patch_info["search"],
            replace=patch_info["replace"]
        )
        executed.append(result)
        status = "✅" if result.success else "❌"
        print(f"    {status} {result.message}")

    # push
    git_push_changes(paths_to_push)
    print("✅ 已推送更新")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python apply_user_confirmation.py '用户消息' [YYYY-MM-DD]")
        sys.exit(1)
    msg = sys.argv[1]
    date = sys.argv[2] if len(sys.argv) > 2 else None
    sys.exit(main(msg, date))
