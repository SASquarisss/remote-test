#!/usr/bin/env python3
"""
用户确认执行器
当用户在聊天中回复"同意X"或"不同意X"时：
1. 将用户反馈追加到 opinion md 文件
2. 对于"同意X"，执行对应的修复
3. 如果对应分支存在，merge 到 main；否则直接修改 main
4. 更新状态
5. git push
"""

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent))
from auto_fix import execute_fixes, REPO_PATH
from review_state import ReviewState

OPINION_DIR = REPO_PATH / "opinion" / "opinion_from_大剑"
MY_NAME = "sxc的魔法老头"


def get_now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def run_git(args, check=True):
    return subprocess.run(
        ["git"] + args, cwd=REPO_PATH, capture_output=True, text=True, check=check
    )


def ensure_on_main():
    result = run_git(["rev-parse", "--abbrev-ref", "HEAD"], check=False)
    if result.stdout.strip() != "main":
        run_git(["checkout", "main"], check=False)


def parse_user_confirmation(text: str) -> List[Tuple[int, bool]]:
    """解析用户回复，提取确认/否决"""
    results = []
    for m in re.finditer(r'不同意\s*(\d+)', text):
        results.append((int(m.group(1)), False))
    denied_ids = {item_id for item_id, _ in results}
    for m in re.finditer(r'(?<!不)同意\s*(\d+)', text):
        item_id = int(m.group(1))
        if item_id not in denied_ids:
            results.append((item_id, True))
    return results


def find_opinion_file_by_date(date_str: Optional[str] = None) -> Optional[Path]:
    if date_str:
        path = OPINION_DIR / f"{date_str}.md"
        if path.exists():
            return path
    md_files = sorted(OPINION_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    return md_files[0] if md_files else None


def append_user_feedback(file_path: Path, user_content: str):
    now = get_now_str()
    section = f"""
# 用户确认 | {now}

{user_content}
"""
    with open(file_path, "a", encoding="utf-8") as f:
        f.write("\n\n---\n\n" + section + "\n\n---\n")
    return file_path


def extract_patch_from_opinion(file_path: Path, item_id: int) -> Optional[dict]:
    text = file_path.read_text(encoding="utf-8")
    pattern = rf'### {item_id}\.\s*(.+?)(?=\n### \d+\.|\n## |\Z)'
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return None

    body = match.group(0)
    title = match.group(1).strip().split('\n')[0]
    title = re.sub(r'\*+', '', title).strip()

    fp_match = re.search(r'\*\*\u6587\u4ef6\*\*[:\uff1a]\s*`([^`]+)`', body)
    patch_match = re.search(
        r'```patch\s*\nSEARCH:\s*\n(.*?)\nREPLACE:\s*\n(.*?)\n```',
        body, re.DOTALL
    )

    if fp_match and patch_match:
        return {
            "title": title,
            "file_path": fp_match.group(1).strip(),
            "search": patch_match.group(1),
            "replace": patch_match.group(2),
        }
    return None


def merge_branch_to_main(branch_name: str) -> Tuple[bool, str]:
    """merge 分支到 main，并 push"""
    ensure_on_main()
    run_git(["pull", "--rebase", "origin", "main"], check=False)

    merge_result = run_git(["merge", "--no-ff", branch_name, "-m", f"merge {branch_name} by user confirmation"])
    if merge_result.returncode != 0:
        # 尝试解决冲突
        run_git(["merge", "--abort"], check=False)
        return False, f"merge 失败: {merge_result.stderr}"

    push_result = run_git(["push", "origin", "main"])
    if push_result.returncode != 0:
        return False, f"push 失败: {push_result.stderr}"

    # 删除已 merge 的远程分支
    run_git(["push", "origin", "--delete", branch_name], check=False)
    # 删除本地分支
    run_git(["branch", "-d", branch_name], check=False)

    return True, "merge 成功"


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

    state = ReviewState()
    state_opinion = state.get_opinion(opinion_file.name)
    branch_name = state_opinion.get("branch")

    # 追加用户反馈到 md 文件
    append_user_feedback(opinion_file, user_message)
    paths_to_push = [opinion_file]

    executed = []
    for item_id, approved in confirmations:
        if not approved:
            print(f"  ❌ 用户否决 #{item_id}，更新状态")
            state.mark_item_state(opinion_file.name, item_id, "rejected_by_user")
            continue

        # 如果对应分支存在，执行 merge
        if branch_name:
            print(f"  🔀 将分支 {branch_name} merge 到 main...")
            ok, msg = merge_branch_to_main(branch_name)
            if ok:
                print(f"  ✅ {msg}")
                state.mark_item_state(opinion_file.name, item_id, "merged", branch=branch_name)
            else:
                print(f"  ❌ {msg}")
            # 分支只能 merge 一次，清空以免重复
            branch_name = None
            continue

        # 如果没有分支（比如测试失败后降级的建议），尝试直接修改 main
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
        state.mark_item_state(
            opinion_file.name, item_id,
            "merged" if result.success else "failed",
            message=result.message
        )

    # push main
    if executed or paths_to_push:
        ensure_on_main()
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
