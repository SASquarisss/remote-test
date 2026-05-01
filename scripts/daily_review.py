#!/usr/bin/env python3
"""
每2小时代码评审自动修复脚本
支持 4 级分类：同意/有争议/同意但不优先/不同意
同意级别自动实施，其他等待用户确认
新增：分支隔离、测试验证、PR 创建、状态持久化
"""

import json
import os
import re
import subprocess
import sys
import traceback
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

sys.path.insert(0, str(Path(__file__).parent))
from auto_fix import (
    execute_fixes, run_tests, rollback_all_fixes,
    REPO_PATH as _REPO_PATH
)
from review_state import ReviewState

REPO_PATH = _REPO_PATH
OPINION_DIR = REPO_PATH / "opinion" / "opinion_from_大剑"
ENV_FILE = Path("/root/.hermes/.env")
MY_NAME = "sxc的魔法老头"
END_MARKERS = ["无异议", "按上述共识执行", "共识已达成",
               "同意按此执行", "讨论结束", "无需进一步讨论"]


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
    return subprocess.run(
        ["git"] + args, cwd=REPO_PATH, capture_output=True, text=True, check=check
    )


def ensure_on_main():
    """确保当前在 main 分支"""
    result = run_git(["rev-parse", "--abbrev-ref", "HEAD"], check=False)
    if result.stdout.strip() != "main":
        run_git(["checkout", "main"], check=False)


def find_recent_opinion_files(hours=48):
    """查找最近 hours 小时内修改的 .md 文件"""
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


def parse_discussion(file_path):
    """解析意见文件，返回段落列表 [(author, timestamp, content), ...]"""
    if not file_path.exists():
        return []
    text = file_path.read_text(encoding="utf-8")
    pattern = r'^# (.+?) \| (\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\n'
    parts = re.split(pattern, text, flags=re.MULTILINE)
    blocks = []

    if len(parts) == 1:
        stripped = parts[0].strip()
        if stripped:
            blocks.append(("opinion", "", stripped))
    else:
        prefix = parts[0].strip()
        if prefix:
            prefix = re.sub(r'\n*---\s*$', '', prefix)
            if prefix:
                blocks.append(("opinion", "", prefix))
        for i in range(1, len(parts), 3):
            if i + 2 <= len(parts):
                author = parts[i].strip()
                ts = parts[i + 1].strip()
                content = parts[i + 2].strip()
                content = re.sub(r'\n*---\s*$', '', content)
                blocks.append((author, ts, content))
    return blocks


def is_my_block(author):
    return author != "opinion" and MY_NAME in author


def has_declared_end(content):
    return any(marker in content for marker in END_MARKERS)


def needs_reply(file_path):
    """判断是否需要回复。返回 (need: bool, reason: str)"""
    if not file_path.exists():
        return False, "文件不存在"
    blocks = parse_discussion(file_path)
    if not blocks:
        return False, "空文件"
    last_author, _last_ts, last_content = blocks[-1]
    if is_my_block(last_author):
        if has_declared_end(last_content):
            return False, "已声明结束，等待对方确认"
        return False, "等待对方回复"
    return True, "首次回复" if last_author == "opinion" else "对方有新回复"


def extract_opinion_and_history(blocks):
    """从解析结果中分离原始评审意见和对话历史"""
    opinion_content = ""
    discussion_blocks = []
    for i, (author, ts, content) in enumerate(blocks):
        if author == "opinion":
            opinion_content = content
        else:
            if i == 0 and not opinion_content:
                # 第一个 block 不是明确的 opinion，但没有其他 opinion，就当作评审意见
                opinion_content = content
            else:
                discussion_blocks.append((author, ts, content))
    return opinion_content, discussion_blocks


# ========================================================================
# 新增：解析 LLM 输出中的分类和 patch
# ========================================================================

class ReviewItem:
    def __init__(self, idx: int, title: str, classification: str,
                 reason: str, file_path: Optional[str] = None,
                 search: Optional[str] = None, replace: Optional[str] = None):
        self.idx = idx
        self.title = title
        self.classification = classification
        self.reason = reason
        self.file_path = file_path
        self.search = search
        self.replace = replace

    @property
    def needs_user_confirm(self) -> bool:
        return self.classification in ("有争议", "同意但不优先")

    @property
    def is_agreed(self) -> bool:
        return self.classification == "同意"

    def __repr__(self):
        return f"#{self.idx} [{self.classification}] {self.title}"


def parse_classified_items(text: str) -> List[ReviewItem]:
    """从 LLM 输出的 markdown 中解析每条建议的分类和 patch"""
    items = []
    sections = re.split(r'\n### (\d+)\.\s*', text)
    for i in range(1, len(sections), 2):
        if i + 1 >= len(sections):
            break
        idx_str = sections[i].strip()
        body = sections[i + 1]

        idx = int(idx_str) if idx_str.isdigit() else (i + 1) // 2

        first_line = body.strip().split('\n')[0].strip()
        # 移除常见markdown标记：粗体、斜体、行内代码、链接语法
        title = re.sub(r'([*_`\[\]]+)', '', first_line).strip()
        title = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', title).strip()

        cls_match = re.search(
            r'[\*\-]\s*\*\*\u5206\u7c7b\*\*[:\uff1a]\s*(\u540c\u610f\u4f46\u4e0d\u4f18\u5148|\u6709\u4e89\u8bae|\u4e0d\u540c\u610f|\u540c\u610f)',
            body
        )
        classification = cls_match.group(1) if cls_match else "\u672a\u77e5"

        reason_match = re.search(
            r'[\*\-]\s*\*\*\u7406\u7531\*\*[:\uff1a]\s*(.+?)(?=\n[\*\-]\s*\*\*|\n####|\n## |$)',
            body, re.DOTALL
        )
        reason = reason_match.group(1).strip() if reason_match else ""

        file_path = None
        search = None
        replace = None

        if classification == "\u540c\u610f":
            fp_match = re.search(r'\*\*\u6587\u4ef6\*\*[:\uff1a]\s*`([^`]+)`', body)
            if fp_match:
                file_path = fp_match.group(1).strip()

            patch_match = re.search(
                r'```patch\s*\nSEARCH:\s*\n(.*?)\nREPLACE:\s*\n(.*?)\n```',
                body, re.DOTALL
            )
            if patch_match:
                search = patch_match.group(1)
                replace = patch_match.group(2)

        items.append(ReviewItem(
            idx=idx, title=title, classification=classification,
            reason=reason, file_path=file_path,
            search=search, replace=replace
        ))

    return items


# ========================================================================
# Prompt 构建
# ========================================================================

def build_classification_prompt(opinion_content: str, discussion_blocks: List) -> str:
    now = get_now_str()

    history = ""
    if discussion_blocks:
        lines = []
        for author, ts, content in discussion_blocks:
            label = "【我】" if is_my_block(author) else f"【{author}】"
            summary = content[:200] + "..." if len(content) > 200 else content
            lines.append(f"{label} {ts}:\n{summary}\n")
        history = "\n".join(lines)

    history_section = f"""
【对话历史】
{history}
""" if history else ""

    return f"""你是 Hermes Agent「{MY_NAME}」，负责审核另一位 AI Agent（大剑）的代码评审意见，并根据严格标准分类处理。

【评审意见】
{opinion_content[:12000]}

{history_section}

请对评审意见中的**每一条**建议进行分析，并分类为以下四级之一：

1. **同意**：建议正确、无争议、改动范围明确且风险低。**你必须立即实施**，并给出具体的修复方案。
2. **有争议**：方案不明确，或未必能实现目标，或相比当前代码改动太大。需要用户确认才能执行。
3. **同意但不优先**：建议本身合理，但当前优先级不高。需要用户确认才能执行。
4. **不同意**：建议有基本错误，或无法在当前架构/约束下落地。

输出格式要求（**严格遵守**，不要漏条目）：

# {MY_NAME} | {now}

## 总体评价
（简要总结，100字以内）

## 逐条分析

### 1. 问题标题
- **分类**: 同意 | 有争议 | 同意但不优先 | 不同意
- **理由**: （4行以内）

#### 修复方案（**仅"同意"级别需要**）
**文件**: `相对路径/to/file.py`
```patch
SEARCH:
（精确的旧代码片段，必须能在文件中唯一匹配，包含足够上下文）
REPLACE:
（新的代码片段）
```

### 2. 问题标题
...

## 执行摘要
- **已自动实施**: N 条
- **等待用户确认**: N 条
- **已拒绝**: N 条

## 用户确认说明
以下建议需要你在1小时内回复确认：
1. 编号X（有争议）: 问题标题 — 回复"同意X"或"不同意X"

用中文。不要在末尾添加 "---" 分隔线。"""


def normalize_reply(content: str) -> str:
    """确保回复内容以正确的标题格式开头"""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("# "):
            if MY_NAME not in line:
                lines[i] = f"# {MY_NAME} | {get_now_str()}"
            return "\n".join(lines[i:])
    return f"# {MY_NAME} | {get_now_str()}\n\n{content}"


import time
from functools import wraps

def retry_on_error(max_retries=3, delay=2):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    time.sleep(delay * (2 ** attempt))
            return None
        return wrapper
    return decorator

@retry_on_error(max_retries=3)
def analyze_with_llm(blocks) -> str:
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1"
    )

    opinion_content, discussion_blocks = extract_opinion_and_history(blocks)
    prompt = build_classification_prompt(opinion_content, discussion_blocks)

    resp = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=8192,
        timeout=300,
    )
    return normalize_reply(resp.choices[0].message.content.strip())


# ========================================================================
# 分支与 PR 管理
# ========================================================================

def create_fix_branch() -> str:
    """创建并切换到新的修复分支"""
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    branch_name = f"auto-fix/{ts}"
    result = run_git(["checkout", "-b", branch_name])
    if result.returncode != 0:
        raise RuntimeError(f"创建分支失败: {result.stderr}")
    print(f"  🌀 创建分支: {branch_name}")
    return branch_name


def delete_local_branch(branch_name: str):
    """删除本地分支（切换回 main 后执行）"""
    run_git(["branch", "-D", branch_name], check=False)


def create_pull_request(branch_name: str, title: str, body: str) -> Optional[str]:
    """使用 GitHub API 创建 PR。需要 GITHUB_TOKEN 环境变量。"""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GITHUB_PAT")
    if not token:
        print("  ⚠️ 未配置 GITHUB_TOKEN，跳过 PR 创建")
        return None

    repo = "SASquarisss/remote-test"
    url = f"https://api.github.com/repos/{repo}/pulls"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }

    data = {
        "title": title,
        "head": branch_name,
        "base": "main",
        "body": body,
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            pr_url = result.get("html_url")
            print(f"  🔗 PR 已创建: {pr_url}")
            return pr_url
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        print(f"  ❌ PR 创建失败: {e.code} {err_body[:200]}")
        return None
    except Exception as e:
        print(f"  ❌ PR 创建异常: {e}")
        return None


def generate_pr_body(opinion_file: str, items: List[ReviewItem],
                     fix_results: List) -> str:
    """生成 PR 描述"""
    lines = [
        f"## 自动修复报告",
        f"",
        f"基于评审意见: `{opinion_file}`",
        f"",
        f"### 已实施的修复",
    ]
    for it in items:
        if it.is_agreed:
            fr = next((r for r in fix_results if r and r.item_id == it.idx), None)
            status = "✅" if (fr and fr.success) else "❌"
            lines.append(f"- {status} #{it.idx} {it.title} (`{it.file_path}`)")
    lines.append("")
    lines.append("### 等待确认的建议")
    for it in items:
        if it.needs_user_confirm:
            lines.append(f"- 📝 #{it.idx} ({it.classification}): {it.title}")
    lines.append("")
    lines.append("### 已拒绝的建议")
    for it in items:
        if it.classification == "不同意":
            lines.append(f"- 🚫 #{it.idx} {it.title}")
    return "\n".join(lines)


# ========================================================================
# 文件操作
# ========================================================================

def append_reply(file_path, content):
    """在文件末尾追加回复内容（带冲突标记检测和备份）"""
    text = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    # 检测 git 冲突标记（仅限行首，避免误判正文描述）
    # 仅匹配行首的 git 冲突标记（<<<<<<< / ======= / >>>>>>>），避免误判正文中的 markdown 引用符号
    if re.search(r'^(<{7}|={7}|>{7})', text, re.MULTILINE):        raise RuntimeError(
            f"文件 {file_path.name} 包含未解决的 git 冲突标记，"
            f"请先手动解决后再运行评审流程。"
        )
    # 备份（在 .md 同目录下生成 .bak.时间戳）
    if text:
        backup_path = file_path.with_suffix(
            f"{file_path.suffix}.bak.{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        backup_path.write_text(text, encoding="utf-8")
    with open(file_path, "a", encoding="utf-8") as f:
        f.write("\n\n---\n\n" + content + "\n\n---\n")
    return file_path


def git_push_changes(paths):
    for p in paths:
        run_git(["add", str(p)], check=False)
    commit_result = run_git(
        ["commit", "-m", f"review + auto-fix at {get_now_str()}"],
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


# ========================================================================
# 报告生成
# ========================================================================

def generate_user_report(items: List[ReviewItem], fix_results: List,
                         test_passed: bool, test_output: str,
                         branch_name: Optional[str] = None,
                         pr_url: Optional[str] = None) -> str:
    """生成发送给用户的报告"""
    lines = [f"📋 代码评审自动修复报告 ({get_now_str()})"]

    if branch_name:
        lines.append(f"🌀 修复分支: `{branch_name}`")
    if pr_url:
        lines.append(f"🔗 PR 链接: {pr_url}")

    agreed = [it for it in items if it.is_agreed]
    pending = [it for it in items if it.needs_user_confirm]
    rejected = [it for it in items if it.classification == "不同意"]

    # 测试结果
    if test_passed:
        lines.append("\n✅ 测试通过")
    else:
        lines.append(f"\n❌ 测试失败，已回滚")
        if test_output:
            lines.append(f"```\n{test_output[:500]}\n```")

    # 已自动实施
    if agreed:
        lines.append("\n【已自动实施】")
        for it in agreed:
            fr = next((r for r in fix_results if r and r.item_id == it.idx), None)
            if fr and fr.success:
                lines.append(f"✅ #{it.idx} {it.title} → `{fr.file_path}`")
            elif fr:
                lines.append(f"❌ #{it.idx} {it.title} → 失败: {fr.message}")
            else:
                lines.append(f"⚠️ #{it.idx} {it.title} → 未找到执行结果")

    # 等待用户确认
    if pending:
        lines.append("\n【等待您确认（请在1小时内回复）】")
        for it in pending:
            lines.append(f"📝 #{it.idx} ({it.classification}): {it.title}")
            lines.append(f"   理由: {it.reason}")
            lines.append(f"   请回复“同意{it.idx}”或“不同意{it.idx}”")

    # 已拒绝
    if rejected:
        lines.append("\n【已拒绝】")
        for it in rejected:
            lines.append(f"🚫 #{it.idx} {it.title}")
            lines.append(f"   理由: {it.reason}")

    return "\n".join(lines)


# ========================================================================
# 主流程
# ========================================================================

def process_opinion(opinion_path, state: ReviewState):
    need, reason = needs_reply(opinion_path)
    if not need:
        print(f"  ⏭️ 跳过 {opinion_path.name}: {reason}")
        return None, reason

    print(f"  📄 处理 {opinion_path.name} ({reason})")
    blocks = parse_discussion(opinion_path)
    analysis = analyze_with_llm(blocks)
    items = parse_classified_items(analysis)
    print(f"  📝 解析到 {len(items)} 条建议")

    # 创建分支
    branch_name = create_fix_branch()
    pr_url = None
    state_items = {}

    # 执行"同意"级别的修复
    fix_results = []
    agreed_items = [it for it in items if it.is_agreed]

    if agreed_items:
        print(f"  ⚙️ 尝试自动实施 {len(agreed_items)} 条修复...")
        for it in agreed_items:
            if it.file_path and it.search and it.replace:
                result = execute_fixes(
                    item_id=it.idx,
                    title=it.title,
                    file_path_str=it.file_path,
                    search=it.search,
                    replace=it.replace
                )
                fix_results.append(result)
                status = "✅" if result.success else "❌"
                print(f"    {status} #{it.idx} {it.title}: {result.message}")
            else:
                print(f"    ⚠️ #{it.idx} {it.title}: 缺少 patch 信息，跳过")
                fix_results.append(None)

        # 运行测试
        print("  🧪 运行测试...")
        test_passed, test_output = run_tests()

        if test_passed:
            print("  ✅ 测试通过")
            # commit + push 分支
            run_git(["add", "-A"], check=False)
            commit_msg = f"auto-fix: apply {len([r for r in fix_results if r and r.success])} fixes on {branch_name}"
            run_git(["commit", "-m", commit_msg], check=False)
            run_git(["push", "-u", "origin", branch_name], check=False)

            # 创建 PR
            pr_title = f"auto-fix: {opinion_path.name}"
            pr_body = generate_pr_body(opinion_path.name, items, fix_results)
            pr_url = create_pull_request(branch_name, pr_title, pr_body)

            # 记录状态
            for it in agreed_items:
                fr = next((r for r in fix_results if r and r.item_id == it.idx), None)
                state_items[str(it.idx)] = {
                    "state": "auto_fixed" if (fr and fr.success) else "failed_patch",
                    "classification": it.classification,
                    "branch": branch_name,
                    "pr_url": pr_url,
                }
        else:
            print(f"  ❌ 测试失败，回滚所有修复")
            rollback_all_fixes([r for r in fix_results if r])
            # 切换回 main 并删除分支
            run_git(["checkout", "main"], check=False)
            run_git(["branch", "-D", branch_name], check=False)
            branch_name = None

            # 降级所有"同意"为 failed_test
            for it in agreed_items:
                state_items[str(it.idx)] = {
                    "state": "failed_test",
                    "classification": "failed_test",
                    "reason": test_output[:500],
                }
    else:
        test_passed = True
        test_output = "无需自动实施的建议"
        # 没有同意的建议，删除空分支
        run_git(["checkout", "main"], check=False)
        run_git(["branch", "-D", branch_name], check=False)
        branch_name = None

    # 记录非同意级别
    for it in items:
        if str(it.idx) not in state_items:
            if it.classification == "不同意":
                state_items[str(it.idx)] = {
                    "state": "rejected",
                    "classification": it.classification,
                }
            elif it.needs_user_confirm:
                state_items[str(it.idx)] = {
                    "state": "pending_user",
                    "classification": it.classification,
                }

    # 切换回 main 分支
    ensure_on_main()

    # 追加分析到 md 文件（在 main 上）
    append_reply(opinion_path, analysis)

    # 保存状态
    state.set_opinion(
        opinion_path.name,
        state_items,
        branch=branch_name,
        pr_url=pr_url
    )

    return opinion_path, reason, items, fix_results, test_passed, test_output, branch_name, pr_url


def main():
    try:
        load_env()
        state = ReviewState()

        # 1. 确保在 main 分支
        ensure_on_main()

        # 2. git pull --rebase
        pull_result = run_git(["pull", "--rebase", "origin", "main"], check=False)
        if pull_result.returncode != 0:
            raise RuntimeError(f"git pull 失败: {pull_result.stderr}")

        # 3. 查找最近48小时内的意见文件
        opinion_files = find_recent_opinion_files(48)
        if not opinion_files:
            print("⚠️ 未找到最近48小时内的评审意见文件")
            return 0

        processed = []
        all_reports = []

        for opinion_path in opinion_files:
            result = process_opinion(opinion_path, state)
            if result[0]:
                processed.append(result[0])
                _, _, items, fix_results, test_passed, test_output, branch, pr = result
                report = generate_user_report(
                    items, fix_results, test_passed, test_output,
                    branch_name=branch, pr_url=pr
                )
                all_reports.append(report)
            else:
                print(f"  跳过: {result[1]}")

        if not processed:
            print("✅ 无需回复，所有对话已收敛或等待对方")
            return 0

        # 4. push main（md 文件更新）
        pushed = git_push_changes(processed)

        # 5. 输出汇总报告
        for report in all_reports:
            print("\n" + report)

        return 0

    except Exception as e:
        print(f"❌ 评审流程异常: {str(e)}")
        traceback.print_exc()
        # 尝试切换回 main
        ensure_on_main()
        return 1


if __name__ == "__main__":
    sys.exit(main())
