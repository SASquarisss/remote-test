#!/usr/bin/env python3
"""
每2小时代码评审自动修复脚本
支持 4 级分类：同意/有争议/同意但不优先/不同意
同意级别自动实施，其他等待用户确认
"""

import os
import re
import sys
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# 将 auto_fix 目录加入 path
sys.path.insert(0, str(Path(__file__).parent))
from auto_fix import execute_fixes, format_report, REPO_PATH

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
    for author, ts, content in blocks:
        if author == "opinion":
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
        self.classification = classification  # 同意/有争议/同意但不优先/不同意
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
    """
    从 LLM 输出的 markdown 中解析每条建议的分类和 patch。
    预期格式：
    ### 1. 问题标题
    - **分类**: 同意
    - **理由**: ...
    #### 修复方案
    **文件**: `path/to/file`
    ```patch
    SEARCH:
    ...
    REPLACE:
    ...
    ```
    """
    items = []
    # 匹配条目标题
    item_pattern = r"### (\d+)\.\s*(.+?)(?=\n### \d+\.|\n## |完\b)"

    # 更精确：匹配到下一个 ### 数字. 或 ## 或文本结尾
    sections = re.split(r'\n### (\d+)\.\s*', text)
    # sections[0] 是头部信息，之后每两个元素为一组：(标题, 内容)
    for i in range(1, len(sections), 2):
        if i + 1 >= len(sections):
            break
        title = sections[i].strip()
        body = sections[i + 1]

        idx_match = re.match(r'(\d+)', sections[i])
        idx = int(idx_match.group(1)) if idx_match else (i + 1) // 2

        # 提取分类
        cls_match = re.search(r'[\*\-]\s*\*\*分类\*\*[:\uff1a]\s*(同意|有争议|同意但不优先|不同意)', body)
        classification = cls_match.group(1) if cls_match else "未知"

        # 提取理由
        reason_match = re.search(r'[\*\-]\s*\*\*理由\*\*[:\uff1a]\s*(.+?)(?=\n[\*\-]\s*\*\*|####|\n## |$)', body, re.DOTALL)
        reason = reason_match.group(1).strip() if reason_match else ""

        # 提取 patch
        file_path = None
        search = None
        replace = None

        if classification == "同意":
            fp_match = re.search(r'\*\*文件\*\*[:\uff1a]\s*`([^`]+)`', body)
            if fp_match:
                file_path = fp_match.group(1).strip()

            patch_match = re.search(r'```patch\s*\nSEARCH:\s*\n(.*?)\nREPLACE:\s*\n(.*?)\n```', body, re.DOTALL)
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
{opinion_content[:4000]}

{history_section}

请对评审意见中的**每一条**建议进行分析，并分类为以下四级之一：

1. **同意**：建议正确、无争议、改动范围明确且风险低。**你必须立即实施**，并给出具体的修复方案。
2. **有争议**：方案不明确，或未必能实现目标，或相比当前代码改动太大、风险高。需要用户确认才能执行。
3. **同意但不优先**：建议本身合理，但当前优先级不高，可以延后处理。需要用户确认才能执行。
4. **不同意**：建议有基本错误，或无法在当前架构/约束下落地。不执行。

输出格式要求（**严格遵守**，不要漏条目）：

# {MY_NAME} | {now}

## 总体评价
（简要总结评审意见的整体质量，100字以内）

## 逐条分析

### 1. 问题标题
- **分类**: 同意 | 有争议 | 同意但不优先 | 不同意
- **理由**: （为什么这样分类，150字以内）

#### 修复方案（**仅"同意"级别需要**）
**文件**: `相对路径/to/file.py`
```patch
SEARCH:
（精确的旧代码片段，必须能在文件中唯一匹配，包含足够的上下文）
REPLACE:
（新的代码片段）
```

### 2. 问题标题
...（按此格式继续）

## 执行摘要
- **已自动实施**: N 条（列出编号）
- **等待用户确认**: N 条（列出编号和分类）
- **已拒绝**: N 条（列出编号）

## 用户确认说明
以下建议需要你在1小时内回复确认：
1. 编号X（有争议）: 问题标题 — 回复"同意X"或"不同意X"
2. 编号X（同意但不优先）: 问题标题 — 回复"同意X"或"不同意X"

用中文输出，严肃、专业、简洁。不要在末尾添加 "---" 分隔线。"""


def normalize_reply(content: str) -> str:
    """确保回复内容以正确的标题格式开头"""
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("# "):
            if MY_NAME not in line:
                lines[i] = f"# {MY_NAME} | {get_now_str()}"
            return "\n".join(lines[i:])
    return f"# {MY_NAME} | {get_now_str()}\n\n{content}"


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
        max_tokens=4096,
        timeout=300,
    )
    return normalize_reply(resp.choices[0].message.content.strip())


# ========================================================================
# 文件操作
# ========================================================================

def append_reply(file_path, content):
    """在文件末尾追加回复内容"""
    with open(file_path, "a", encoding="utf-8") as f:
        f.write("\n\n---\n\n" + content + "\n\n---\n")
    return file_path


def append_user_feedback(file_path, user_content):
    """追加用户反馈，标识为用户意见"""
    now = get_now_str()
    section = f"""
# 用户确认 | {now}

{user_content}
"""
    with open(file_path, "a", encoding="utf-8") as f:
        f.write("\n\n---\n\n" + section + "\n\n---\n")
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

def generate_user_report(items: List[ReviewItem], fix_results: List) -> str:
    """生成发送给用户的报告"""
    lines = [f"📋 代码评审自动修复报告 ({get_now_str()})"]

    agreed = [it for it in items if it.is_agreed]
    pending = [it for it in items if it.needs_user_confirm]
    rejected = [it for it in items if it.classification == "不同意"]

    # 已自动实施
    if agreed:
        lines.append("\n【已自动实施】")
        for it in agreed:
            # 查找对应的执行结果
            fr = next((r for r in fix_results if r.item_id == it.idx), None)
            if fr and fr.success:
                lines.append(f"✅ #{it.idx} {it.title} → 修改了 {fr.file_path}")
            elif fr:
                lines.append(f"❌ #{it.idx} {it.title} → 自动修复失败: {fr.message}")
            else:
                lines.append(f"⚠️ #{it.idx} {it.title} → 未找到执行结果")

    # 等待用户确认
    if pending:
        lines.append("\n【等待您确认（请在1小时内回复）】")
        for it in pending:
            lines.append(f"📝 #{it.idx} ({it.classification}): {it.title}")
            lines.append(f"   理由: {it.reason}")
            lines.append(f'   请回复"同意{it.idx}"或"不同意{it.idx}"')

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

def process_opinion(opinion_path):
    need, reason = needs_reply(opinion_path)
    if not need:
        print(f"  ⏭️ 跳过 {opinion_path.name}: {reason}")
        return None, reason

    print(f"  📄 处理 {opinion_path.name} ({reason})")
    blocks = parse_discussion(opinion_path)
    analysis = analyze_with_llm(blocks)

    # 解析分类
    items = parse_classified_items(analysis)
    print(f"  解析到 {len(items)} 条建议")

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

    # 追加分析到 md 文件
    append_reply(opinion_path, analysis)

    return opinion_path, reason, items, fix_results


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
        all_items = []
        all_fix_results = []

        for opinion_path in opinion_files:
            result = process_opinion(opinion_path)
            if result[0]:
                processed.append(result[0])
                all_items.extend(result[2])
                all_fix_results.extend(result[3])
            else:
                skip_reasons.append(f"{opinion_path.name}: {result[1]}")

        if not processed:
            print("✅ 无需回复，所有对话已收敛或等待对方")
            if skip_reasons:
                for r in skip_reasons:
                    print(f"   {r}")
            return 0

        # 3. push 所有变更（意见文件 + 自动修复的代码）
        paths_to_push = list(processed)
        # 检查是否有代码修改需要提交
        status = run_git(["status", "--short"], check=False)
        if status.stdout.strip():
            # 有变更（包括代码修改）
            pass

        pushed = git_push_changes(paths_to_push)

        # 4. 生成用户报告
        user_report = generate_user_report(all_items, all_fix_results)
        print("\n" + user_report)

        return 0

    except Exception as e:
        print(f"❌ 评审流程异常: {str(e)}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
