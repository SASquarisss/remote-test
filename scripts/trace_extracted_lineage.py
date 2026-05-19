#!/usr/bin/env python3
"""
trace_extracted_lineage.py

追溯 data_lake/extracted_*.jsonl 的产出链。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class LineageInfo:
    file_name: str
    lineage_type: str
    script: str
    interface: str
    version_hint: str
    confidence: str
    evidence: str


def load_record_meta(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                meta = record.get("_meta")
                if isinstance(meta, dict):
                    return meta
                return None
    except Exception:
        return None
    return None


def classify_from_meta(file_name: str, meta: Dict[str, Any]) -> LineageInfo:
    generator = meta.get("generator") or {}
    prompt = meta.get("prompt") or {}
    model = meta.get("model") or {}
    entrypoint = generator.get("entrypoint") or generator.get("extractor") or "未知"
    batch_label = generator.get("batch_label") or ""
    prompt_path = prompt.get("path") or ""
    model_name = model.get("name") or ""
    version_hint_parts = []
    if prompt_path:
        version_hint_parts.append(f"prompt={prompt_path}")
    if model_name:
        version_hint_parts.append(f"model={model_name}")
    if batch_label:
        version_hint_parts.append(f"batch={batch_label}")
    version_hint = " | ".join(version_hint_parts) if version_hint_parts else "来自记录内 _meta"
    return LineageInfo(
        file_name=file_name,
        lineage_type="记录内 _meta 落锤",
        script=str(entrypoint),
        interface="CLI/批处理（由 _meta 记录）",
        version_hint=version_hint,
        confidence="高",
        evidence="直接读取 JSONL 记录内的 _meta 字段得到",
    )


def classify_extracted_file(file_name: str, data_lake_dir: Path) -> LineageInfo:
    meta = load_record_meta(data_lake_dir / file_name)
    if meta:
        return classify_from_meta(file_name, meta)

    if file_name == "extracted_guiding_cases.jsonl":
        return LineageInfo(
            file_name=file_name,
            lineage_type="明确脚本生成",
            script="extraction/llm_extractors/guiding_case_extractor.py",
            interface="CLI 脚本",
            version_hint="旧版 guiding_case_extractor，默认 prompt-version=v3",
            confidence="高",
            evidence="代码中默认输出即 data_lake/extracted_guiding_cases.jsonl",
        )

    if file_name.startswith("extracted_v2.2_admin_full_part1"):
        return LineageInfo(
            file_name=file_name,
            lineage_type="明确脚本生成",
            script="scripts/admin_batches/run_admin_part1.py -> guiding_case_extractor_v3.py",
            interface="CLI wrapper",
            version_hint="文件名叫 v2.2_admin，但实际 prompt-path=auto_v5_admin.txt",
            confidence="高",
            evidence="scripts/admin_batches/run_admin_part1.py 显式指定 output=extracted_v2.2_admin_full_part1.jsonl",
        )

    if file_name.startswith("extracted_v2.2_admin_full_part2"):
        return LineageInfo(
            file_name=file_name,
            lineage_type="明确脚本生成",
            script="scripts/admin_batches/run_admin_part2.py -> guiding_case_extractor_v3.py",
            interface="CLI wrapper",
            version_hint="文件名叫 v2.2_admin，但实际 prompt-path=auto_v5_admin.txt",
            confidence="高",
            evidence="scripts/admin_batches/run_admin_part2.py 显式指定 output=extracted_v2.2_admin_full_part2.jsonl",
        )

    if file_name.startswith("extracted_v2.2_admin_full.jsonl"):
        return LineageInfo(
            file_name=file_name,
            lineage_type="双重来源",
            script="scripts/admin_batches/run_admin_extraction.py 或 scripts/admin_batches/check_admin_batch1.py",
            interface="CLI wrapper / 合并脚本",
            version_hint="行政批次，prompt-path=auto_v5_admin.txt",
            confidence="中",
            evidence="scripts/admin_batches/run_admin_extraction.py 默认输出该文件；scripts/admin_batches/check_admin_batch1.py 也会重写同名文件",
        )

    if file_name.startswith("extracted_v2.2_admin_batch1_"):
        return LineageInfo(
            file_name=file_name,
            lineage_type="通用 extractor 手工命名",
            script="guiding_case_extractor_v3.py（推定）",
            interface="CLI 直接调用",
            version_hint="行政 batch1 拆分结果，后续被 check_admin_batch1.py 合并",
            confidence="中",
            evidence="仓库存在消费和合并脚本，但未找到专门创建这两个文件名的脚本",
        )

    if file_name.startswith("extracted_v2.2_admin_all") or file_name.startswith("extracted_v2.2_admin_remaining"):
        return LineageInfo(
            file_name=file_name,
            lineage_type="通用 extractor 手工命名",
            script="guiding_case_extractor_v3.py（推定）",
            interface="CLI 直接调用",
            version_hint="行政总批次/补跑批次；visualization 和文档把它当既有批量结果使用",
            confidence="中",
            evidence="存在下游消费脚本和文档引用，但仓库未找到写出点",
        )

    if file_name.startswith("extracted_v4_civil_"):
        return LineageInfo(
            file_name=file_name,
            lineage_type="通用 extractor 手工命名",
            script="guiding_case_extractor_v3.py（高概率）",
            interface="CLI 直接调用",
            version_hint="v4 更像 prompt 版本；大概率搭配 auto_v4_civil.txt",
            confidence="中",
            evidence="fewshot_cmp_test.py 证实 v4 civil prompt 通过 v3 extractor 的 process_one 运行",
        )

    if file_name.startswith("extracted_v5_civil_") or file_name.startswith("extracted_v5_best_shots") or file_name.startswith("extracted_v5_714_as_fewshot"):
        return LineageInfo(
            file_name=file_name,
            lineage_type="通用 extractor 手工命名",
            script="guiding_case_extractor_v3.py（高概率）",
            interface="CLI 直接调用",
            version_hint="v5 更像 prompt/实验批次标签；大概率搭配 auto_v5_civil.txt 或手工筛样",
            confidence="中",
            evidence="仓库有 auto_v5_civil.txt 和通用 --prompt-path 入口，但未找到这些文件名的专属写出脚本",
        )

    if file_name.startswith("extracted_v3_") or file_name.startswith("extracted_test_v3_"):
        lineage_type = "通用 extractor 手工命名"
        script = "guiding_case_extractor_v3.py"
        confidence = "中"
        evidence = "guiding_case_extractor_v3.py 默认输出 extracted_v3.jsonl，支持任意 --output；文件名形态与批跑/补跑/重试命名习惯一致"
        if "merged" in file_name or "complete" in file_name:
            lineage_type = "合并产物"
            script = "外部合并脚本或人工合并（未在仓库定位到专门脚本）"
            confidence = "低-中"
            evidence = "文件名含 merged/complete，明显是结果集合并态；仓库未找到专门写出脚本"
        return LineageInfo(
            file_name=file_name,
            lineage_type=lineage_type,
            script=script,
            interface="CLI 直接调用",
            version_hint="v3 主线批次/补跑/重试/合并",
            confidence=confidence,
            evidence=evidence,
        )

    return LineageInfo(
        file_name=file_name,
        lineage_type="未落锤",
        script="未知",
        interface="未知",
        version_hint="需结合外部运行记录继续追",
        confidence="低",
        evidence="仓库中未定位到明确写出点",
    )


def render_table(items: List[LineageInfo]) -> str:
    lines = [
        "# Extracted 产出链追溯",
        "",
        "| 文件 | 产出类型 | 脚本 | 接口 | 版本线索 | 置信度 | 说明 |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in items:
        lines.append(
            f"| {item.file_name} | {item.lineage_type} | {item.script} | {item.interface} | "
            f"{item.version_hint} | {item.confidence} | {item.evidence} |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="追溯 extracted_*.jsonl 产出链")
    parser.add_argument("--data-lake", default="data_lake", help="data_lake 目录")
    args = parser.parse_args()

    data_lake_dir = (REPO_ROOT / args.data_lake).resolve()
    files = sorted(p.name for p in data_lake_dir.glob("extracted_*.jsonl"))
    items = [classify_extracted_file(name, data_lake_dir) for name in files]
    print(render_table(items))
    print()
    print("## 结论")
    print()
    print("- 对带 `_meta` 的新记录，脚本优先按记录内真实元数据追溯，不再只靠文件名推断。")
    print("- 对历史旧文件，仍会回退到文件名和仓库脚本证据做启发式判断。")
    print("- `extracted_*` 目前主要来自离线 CLI/批处理脚本，不是后端 HTTP 接口直接写出。")
    print("- 文件名里的 `v3/v4/v5/v2.2` 仍不能简单等同于代码版本；更可靠的来源是新写入的 `_meta`。")


if __name__ == "__main__":
    main()
