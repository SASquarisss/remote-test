#!/usr/bin/env python3
"""
自动修复执行器
安全解析 LLM 输出的 SEARCH/REPLACE patch，备份、应用、验证、回滚
"""

import os
import re
import shutil
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

REPO_PATH = Path("/root/.hermes/hermes-agent/remote-test")
BACKUP_DIR = REPO_PATH / ".auto_fix_backups"


class FixResult:
    def __init__(self, item_id: int, title: str, file_path: str,
                 success: bool, message: str, backup_path: Optional[str] = None):
        self.item_id = item_id
        self.title = title
        self.file_path = file_path
        self.success = success
        self.message = message
        self.backup_path = backup_path

    def __repr__(self):
        status = "✅" if self.success else "❌"
        return f"{status} #{self.item_id} {self.title}: {self.message}"


def _repo_relative(path: str) -> Path:
    """将路径转为 repo 内的绝对路径，防止越界"""
    p = Path(path)
    if p.is_absolute():
        # 确保在 REPO_PATH 内
        try:
            p.relative_to(REPO_PATH)
            return p
        except ValueError:
            raise ValueError(f"路径越界: {path}")
    else:
        return REPO_PATH / p


def backup_file(file_path: Path) -> Path:
    """创建文件备份，返回备份路径"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{file_path.name}.{ts}.bak"
    backup_path = BACKUP_DIR / backup_name
    shutil.copy2(file_path, backup_path)
    return backup_path


def apply_search_replace(file_path: Path, search: str, replace: str) -> Tuple[bool, str]:
    """
    在文件中执行精确的 SEARCH/REPLACE。
    search 必须能在文件中唯一匹配；若不唯一或不存在则失败。
    """
    if not file_path.exists():
        return False, f"文件不存在: {file_path}"

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"读取失败: {e}"

    # 严格匹配：去除末尾的换行差异（SEARCH 和 REPLACE 可能末尾少一个 \n）
    search_stripped = search.rstrip("\n")
    replace_stripped = replace.rstrip("\n")

    occurrences = content.count(search)
    if occurrences == 0:
        # 尝试忽略末尾换行差异
        occurrences = content.count(search_stripped)
        if occurrences == 0:
            return False, "SEARCH 片段在文件中未找到"
        use_stripped = True
    else:
        use_stripped = False

    if occurrences > 1:
        return False, f"SEARCH 片段在文件中匹配了 {occurrences} 处，不唯一"

    if use_stripped:
        new_content = content.replace(search_stripped, replace_stripped, 1)
    else:
        new_content = content.replace(search, replace, 1)

    if new_content == content:
        return False, "替换后内容未变化"

    try:
        file_path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return False, f"写入失败: {e}"

    return True, "替换成功"


def verify_file(file_path: Path) -> Tuple[bool, str]:
    """根据后缀做基本语法/格式验证"""
    suffix = file_path.suffix.lower()

    if suffix == ".py":
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(file_path)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return False, f"Python 语法错误: {result.stderr.strip()[:200]}"
        return True, "Python 语法通过"

    elif suffix in (".yaml", ".yml"):
        try:
            import yaml
            yaml.safe_load(file_path.read_text(encoding="utf-8"))
            return True, "YAML 格式通过"
        except Exception as e:
            return False, f"YAML 格式错误: {str(e)[:200]}"

    elif suffix == ".json":
        try:
            import json
            json.loads(file_path.read_text(encoding="utf-8"))
            return True, "JSON 格式通过"
        except Exception as e:
            return False, f"JSON 格式错误: {str(e)[:200]}"

    return True, "无验证规则，跳过"


def rollback_file(file_path: Path, backup_path: Path) -> bool:
    """从备份回滚"""
    try:
        shutil.copy2(backup_path, file_path)
        return True
    except Exception as e:
        print(f"  回滚失败: {e}")
        return False


def parse_patches_from_markdown(markdown: str) -> List[Dict]:
    """
    从 LLM 输出的 markdown 中提取 patch 块。
    预期格式：

    #### 修复方案
    **文件**: `path/to/file.py`
    ```patch
    SEARCH:
    旧代码
    REPLACE:
    新代码
    ```
    """
    patches = []
    # 匹配 文件路径
    file_pattern = r"\*\*文件\*\*:\s*`([^`]+)`"
    # 匹配 SEARCH/REPLACE 块
    patch_pattern = r"```patch\s*\nSEARCH:\s*\n(.*?)\nREPLACE:\s*\n(.*?)\n```"

    # 先按条目分割，每个条目内可能有一个 patch
    item_pattern = r"### \d+\.\s*(.+?)(?=\n### \d+\.|\n## |结束\b)"
    # 更精确的方法：遍历所有 patch 块
    for m in re.finditer(patch_pattern, markdown, re.DOTALL):
        search_block = m.group(1)
        replace_block = m.group(2)

        # 向前查找最近的文件路径
        before = markdown[:m.start()]
        file_match = None
        for fm in re.finditer(file_pattern, before):
            file_match = fm
        if not file_match:
            continue

        file_path = file_match.group(1).strip()
        patches.append({
            "file_path": file_path,
            "search": search_block,
            "replace": replace_block,
        })

    return patches


def execute_fixes(item_id: int, title: str, file_path_str: str,
                  search: str, replace: str) -> FixResult:
    """
    执行单条修复。
    流程：备份 → 应用 patch → 验证 → 提交
    验证失败则回滚。
    """
    try:
        file_path = _repo_relative(file_path_str)
    except ValueError as e:
        return FixResult(item_id, title, file_path_str, False, str(e))

    # 1. 备份
    try:
        backup = backup_file(file_path)
    except Exception as e:
        return FixResult(item_id, title, file_path_str, False,
                        f"备份失败: {e}")

    # 2. 应用 patch
    ok, msg = apply_search_replace(file_path, search, replace)
    if not ok:
        return FixResult(item_id, title, file_path_str, False, msg,
                        backup_path=str(backup))

    # 3. 验证
    v_ok, v_msg = verify_file(file_path)
    if not v_ok:
        # 验证失败，回滚
        rollback_file(file_path, backup)
        return FixResult(item_id, title, file_path_str, False,
                        f"验证失败: {v_msg}", backup_path=str(backup))

    return FixResult(item_id, title, file_path_str, True,
                    f"已修改并通过验证 ({v_msg})", backup_path=str(backup))


def execute_all_fixes(patches: List[Dict]) -> List[FixResult]:
    """批量执行修复，返回结果列表"""
    results = []
    for i, p in enumerate(patches, 1):
        result = execute_fixes(
            item_id=i,
            title=p.get("title", f"修复 #{i}"),
            file_path_str=p["file_path"],
            search=p["search"],
            replace=p["replace"]
        )
        results.append(result)
    return results


def format_report(results: List[FixResult]) -> str:
    """格式化执行报告"""
    if not results:
        return "无自动修复执行"
    lines = ["【自动修复执行报告【"]
    for r in results:
        status = "✅ 成功" if r.success else "❌ 失败"
        lines.append(f"  #{r.item_id} {r.title}")
        lines.append(f"     文件: {r.file_path}")
        lines.append(f"     结果: {status} — {r.message}")
        if not r.success and r.backup_path:
            lines.append(f"     备份: {r.backup_path}")
    return "\n".join(lines)


if __name__ == "__main__":
    # 简单测试
    test_md = """
#### 修复方案
**文件**: `test_sample.py`
```patch
SEARCH:
def hello():
    return "hi"
REPLACE:
def hello():
    return "hello world"
```
"""
    patches = parse_patches_from_markdown(test_md)
    print("提取到 patches:", len(patches))
    for p in patches:
        print(p)
