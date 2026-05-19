#!/usr/bin/env python3
"""
audit_extracted_fewshot_pool.py

专项审计 `data_lake/extracted_*.jsonl` 正式候选池：
1. 统计 facts / dispute_focuses / relations 覆盖率
2. 定位存在图谱结构的“漏网样本”
3. 如果没有任何正样本，给出明确结论，便于回溯上游抽取链
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.data_lake_layers import OFFICIAL_CANDIDATE_LAYER, get_data_lake_layer_files


def classify_case_type(case_type: str) -> str:
    ct = (case_type or "").strip()
    if ct.startswith("刑事"):
        return "criminal"
    if ct.startswith("民事"):
        return "civil"
    if ct.startswith("行政"):
        return "administrative"
    return "other"


def count_nonempty_relations(relations: List[dict]) -> tuple[int, List[str]]:
    kept = []
    for rel in relations or []:
        if not isinstance(rel, dict):
            continue
        if str(rel.get("source_id", "")).strip() and str(rel.get("target_id", "")).strip() and str(rel.get("relation_type", "")).strip():
            kept.append(rel)
    types = sorted({str(rel.get("relation_type", "")).strip() for rel in kept if str(rel.get("relation_type", "")).strip()})
    return len(kept), types


def main() -> None:
    parser = argparse.ArgumentParser(description="审计 extracted_* few-shot 正式候选池")
    parser.add_argument("--data-lake", default="data_lake", help="data_lake 目录")
    parser.add_argument("--limit", type=int, default=20, help="最多展示多少条漏网正样本")
    args = parser.parse_args()

    data_lake_dir = (REPO_ROOT / args.data_lake).resolve()
    files = get_data_lake_layer_files(data_lake_dir, OFFICIAL_CANDIDATE_LAYER)

    by_category = defaultdict(lambda: {"records": 0, "facts": 0, "focuses": 0, "relations": 0, "rich": 0})
    by_file = defaultdict(lambda: {"records": 0, "facts": 0, "focuses": 0, "relations": 0, "rich": 0})
    positive_records = []
    relation_type_counter = Counter()

    for path in files:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except Exception:
                    continue

                inp = record.get("input") or {}
                out = record.get("output") or {}
                category = classify_case_type(inp.get("case_type", ""))
                if category == "other":
                    category = ((out.get("case_type") or {}).get("category") or "other").strip() or "other"

                facts = len(out.get("facts") or [])
                focuses = len(out.get("dispute_focuses") or [])
                relations, relation_types = count_nonempty_relations(out.get("relations") or [])

                by_category[category]["records"] += 1
                by_file[path.name]["records"] += 1
                if facts > 0:
                    by_category[category]["facts"] += 1
                    by_file[path.name]["facts"] += 1
                if focuses > 0:
                    by_category[category]["focuses"] += 1
                    by_file[path.name]["focuses"] += 1
                if relations > 0:
                    by_category[category]["relations"] += 1
                    by_file[path.name]["relations"] += 1
                    relation_type_counter.update(relation_types)
                if facts > 0 and focuses > 0 and relations > 0:
                    by_category[category]["rich"] += 1
                    by_file[path.name]["rich"] += 1

                if facts > 0 or focuses > 0 or relations > 0:
                    positive_records.append({
                        "row_id": record.get("row_id") or inp.get("id", ""),
                        "file": path.name,
                        "category": category,
                        "case_type": inp.get("case_type", ""),
                        "facts": facts,
                        "focuses": focuses,
                        "relations": relations,
                        "relation_types": relation_types,
                    })

    print("# Extracted Few-shot 候选池审计")
    print()
    print(f"- 目录: `{data_lake_dir}`")
    print(f"- 正式候选文件数: {len(files)}")
    print()
    print("## 分类覆盖")
    print()
    print("| 类别 | 样本数 | facts非空 | focuses非空 | relations非空 | 三者同时非空 |")
    print("|---|---:|---:|---:|---:|---:|")
    for category in ["civil", "criminal", "administrative", "other"]:
        stat = by_category.get(category, {})
        print(
            f"| {category} | {stat.get('records', 0)} | {stat.get('facts', 0)} | "
            f"{stat.get('focuses', 0)} | {stat.get('relations', 0)} | {stat.get('rich', 0)} |"
        )

    print()
    print("## 文件覆盖")
    print()
    print("| 文件 | 样本数 | facts非空 | focuses非空 | relations非空 | 三者同时非空 |")
    print("|---|---:|---:|---:|---:|---:|")
    for file_name in sorted(by_file.keys()):
        stat = by_file[file_name]
        print(
            f"| {file_name} | {stat['records']} | {stat['facts']} | {stat['focuses']} | "
            f"{stat['relations']} | {stat['rich']} |"
        )

    print()
    print("## 关系类型")
    print()
    if relation_type_counter:
        for rel_type, count in relation_type_counter.most_common():
            print(f"- `{rel_type}`: {count}")
    else:
        print("- 当前 `extracted_*` 候选池中没有任何非空 `relations`。")

    print()
    print("## 漏网正样本")
    print()
    if positive_records:
        positive_records.sort(key=lambda x: (x["relations"], x["focuses"], x["facts"]), reverse=True)
        print("| row_id | 文件 | 类别 | facts | focuses | relations | relation_type | case_type |")
        print("|---|---|---|---:|---:|---:|---|---|")
        for item in positive_records[: args.limit]:
            rel_types = ", ".join(item["relation_types"]) or "-"
            print(
                f"| {item['row_id']} | {item['file']} | {item['category']} | {item['facts']} | "
                f"{item['focuses']} | {item['relations']} | {rel_types} | {item['case_type']} |"
            )
    else:
        print("- 没有发现任何带 `facts`、`dispute_focuses` 或 `relations` 的漏网样本。")
        print("- 结论：当前应回到上游抽取链补产出，而不是继续从全量 `extracted_*` 中挑 few-shot。")


if __name__ == "__main__":
    main()
