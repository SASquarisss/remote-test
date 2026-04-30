#!/usr/bin/env python3
"""
自动修复执行器
安全解析 LLM 输出的 SEARCH/REPLACE patch，备份、应用、验证、回滚
新增：测试运行支持
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

REPO_PATH = Path(os.environ.get("REPO_PATH", Path(__file__).resolve().parent.parent))
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
    """在文件中执行精确的 SEARCH/REPLACE"""
    if not file_path.exists():
        return False, f"文件不存在: {file_path}"

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return False, f"读取失败: {e}"

    search_stripped = search.rstrip("\n")
    replace_stripped = replace.rstrip("\n")

    occurrences = content.count(search)
    use_stripped = False
    if occurrences == 0:
        occurrences = content.count(search_stripped)
        if occurrences == 0:
            return False, "SEARCH 片段在文件中未找到"
        use_stripped = True

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


def execute_fixes(item_id: int, title: str, file_path_str: str,
                  search: str, replace: str) -> FixResult:
    """执行单条修复：备份 → 应用 patch → 验证 → 提交"""
    try:
        file_path = _repo_relative(file_path_str)
    except ValueError as e:
        return FixResult(item_id, title, file_path_str, False, str(e))

    try:
        backup = backup_file(file_path)
    except Exception as e:
        return FixResult(item_id, title, file_path_str, False,
                        f"备份失败: {e}")

    ok, msg = apply_search_replace(file_path, search, replace)
    if not ok:
        return FixResult(item_id, title, file_path_str, False, msg,
                        backup_path=str(backup))

    v_ok, v_msg = verify_file(file_path)
    if not v_ok:
        rollback_file(file_path, backup)
        return FixResult(item_id, title, file_path_str, False,
                        f"验证失败: {v_msg}", backup_path=str(backup))

    return FixResult(item_id, title, file_path_str, True,
                    f"已修改并通过验证 ({v_msg})", backup_path=str(backup))


def run_tests(test_dir: Optional[Path] = None) -> Tuple[bool, str]:
    """
    运行测试套件。
    如果存在 pytest 和 tests/ 目录，运行 pytest。
    如果没有测试，默认通过。
    返回 (passed, output)
    """
    if test_dir is None:
        test_dir = REPO_PATH / "tests"

    if not test_dir.exists():
        # 检查是否有 pytest
        pytest_check = subprocess.run(
            ["which", "pytest"], capture_output=True, text=True
        )
        if pytest_check.returncode != 0:
            return True, "未找到 pytest，跳过测试"

        # 尝试运行 pytest 发现测试
        result = subprocess.run(
            ["pytest", str(REPO_PATH), "-q", "--tb=short", "--collect-only"],
            capture_output=True, text=True, timeout=60
        )
        if "no tests collected" in result.stdout.lower() or "no tests ran" in result.stdout.lower() or result.returncode == 5:
            return True, "未收集到测试用例，跳过"

        # 运行测试
        result = subprocess.run(
            ["pytest", str(REPO_PATH), "-q", "--tb=short"],
            capture_output=True, text=True, timeout=120
        )
    else:
        result = subprocess.run(
            ["pytest", str(test_dir), "-q", "--tb=short"],
            capture_output=True, text=True, timeout=120
        )

    passed = result.returncode == 0
    if result.returncode == 5:
        return True, "未收集到测试用例，跳过"
    output = (result.stdout + "\n" + result.stderr).strip()
    if len(output) > 2000:
        output = output[:2000] + "\n... (truncated)"
    return passed, output


def rollback_all_fixes(results: List[FixResult]):
    """批量回滚所有已执行的修复"""
    for r in reversed(results):
        if r.success and r.backup_path:
            try:
                bp = Path(r.backup_path)
                fp = _repo_relative(r.file_path)
                if bp.exists():
                    rollback_file(fp, bp)
            except Exception as e:
                print(f"  回滚 #{r.item_id} 失败: {e}")


def format_report(results: List[FixResult]) -> str:
    """格式化执行报告"""
    if not results:
        return "无自动修复执行"
    lines = ["【自动修复执行报告】"]
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
    # patches = parse_patches_from_markdown(test_md)
    # print("提取到 patches:", len(patches))
    # for p in patches:
    #     print(p)
    print("auto_fix.py loaded")
