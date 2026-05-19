#!/usr/bin/env python3
"""
probe_data_lake_graph_coverage.py

扫描 data_lake 下的 JSONL 文件，统计各类别 facts / dispute_focuses / relations 覆盖情况。

目标：
1. 区分 data_lake 中不同来源/用途的文件族（extracted / fewshot_cmp / compare / manual / other）
2. 给出各类别在不同文件族中的图谱结构覆盖情况
3. 重点输出 generate_prompt.py 当前实际会扫描的 extracted_*.jsonl 候选池质量
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.data_lake_layers import (
    classify_data_lake_layer,
    iter_data_lake_jsonl_files,
    summarize_data_lake_layers,
)


def classify_case_type(case_type: str) -> str:
    ct = (case_type or "").strip()
    if ct.startswith("刑事"):
        return "criminal"
    if ct.startswith("民事"):
        return "civil"
    if ct.startswith("行政"):
        return "administrative"
    return "other"


def normalize_record_category(record: dict) -> str:
    inp = record.get("input") or {}
    out = record.get("output") or {}
    case_type = inp.get("case_type", "") or ""
    cat = classify_case_type(case_type)
    if cat != "other":
        return cat
    out_case_type = out.get("case_type") or {}
    out_cat = (out_case_type.get("category") or "").strip()
    if out_cat in {"civil", "criminal", "administrative"}:
        return out_cat
    return "other"


def count_nonempty_relations(relations: Iterable[dict]) -> tuple[int, List[str]]:
    relation_types = []
    count = 0
    for rel in relations or []:
        if not isinstance(rel, dict):
            continue
        src = str(rel.get("source_id", "")).strip()
        tgt = str(rel.get("target_id", "")).strip()
        rel_type = str(rel.get("relation_type", "")).strip()
        if src and tgt and rel_type:
            count += 1
            relation_types.append(rel_type)
    return count, relation_types


@dataclass
class CoverageStats:
    records: int = 0
    facts_nonempty: int = 0
    focuses_nonempty: int = 0
    relations_nonempty: int = 0
    rich_graph_nonempty: int = 0
    total_facts: int = 0
    total_focuses: int = 0
    total_relations: int = 0
    relation_type_counter: Counter = field(default_factory=Counter)
    files: Counter = field(default_factory=Counter)

    def add(self, file_name: str, facts: int, focuses: int, relations: int, relation_types: List[str]) -> None:
        self.records += 1
        self.files[file_name] += 1
        self.total_facts += facts
        self.total_focuses += focuses
        self.total_relations += relations
        if facts > 0:
            self.facts_nonempty += 1
        if focuses > 0:
            self.focuses_nonempty += 1
        if relations > 0:
            self.relations_nonempty += 1
        if facts > 0 and focuses > 0 and relations > 0:
            self.rich_graph_nonempty += 1
        self.relation_type_counter.update(relation_types)

    def to_row(self, name: str) -> str:
        if self.records == 0:
            return f"| {name} | 0 | 0 | 0 | 0 | 0 | 0 | - |"
        facts_cov = self.facts_nonempty / self.records * 100
        focuses_cov = self.focuses_nonempty / self.records * 100
        rel_cov = self.relations_nonempty / self.records * 100
        rich_cov = self.rich_graph_nonempty / self.records * 100
        avg_facts = self.total_facts / self.records
        avg_focuses = self.total_focuses / self.records
        avg_rel = self.total_relations / self.records
        common_types = ", ".join(t for t, _ in self.relation_type_counter.most_common(5)) or "-"
        return (
            f"| {name} | {self.records} | {facts_cov:.1f}% | {focuses_cov:.1f}% | {rel_cov:.1f}% | "
            f"{rich_cov:.1f}% | {avg_facts:.2f}/{avg_focuses:.2f}/{avg_rel:.2f} | {common_types} |"
        )


def scan_data_lake(data_lake_dir: Path) -> dict:
    by_family: Dict[str, Dict[str, CoverageStats]] = defaultdict(lambda: defaultdict(CoverageStats))
    all_stats: Dict[str, CoverageStats] = defaultdict(CoverageStats)
    file_counts: Dict[str, int] = defaultdict(int)

    for path in iter_data_lake_jsonl_files(data_lake_dir):
        family = classify_data_lake_layer(path)
        file_counts[family] += 1
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except Exception:
                        continue
                    output = record.get("output") or {}
                    category = normalize_record_category(record)
                    facts = len(output.get("facts") or [])
                    focuses = len(output.get("dispute_focuses") or [])
                    relations, relation_types = count_nonempty_relations(output.get("relations") or [])
                    by_family[family][category].add(path.name, facts, focuses, relations, relation_types)
                    all_stats[category].add(path.name, facts, focuses, relations, relation_types)
        except Exception:
            continue

    return {
        "by_family": by_family,
        "all_stats": all_stats,
        "file_counts": file_counts,
    }


def render_family_block(title: str, stats_by_category: Dict[str, CoverageStats]) -> str:
    cats = ["civil", "criminal", "administrative", "other"]
    lines = [
        f"## {title}",
        "",
        "| 类别 | 样本数 | facts覆盖 | focuses覆盖 | relations覆盖 | 三者同时非空 | 平均 facts/focuses/relations | 常见 relation_type |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for cat in cats:
        lines.append(stats_by_category.get(cat, CoverageStats()).to_row(cat))
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="扫描 data_lake 图谱结构覆盖情况")
    parser.add_argument("--data-lake", default="data_lake", help="data_lake 目录")
    args = parser.parse_args()

    data_lake_dir = (REPO_ROOT / args.data_lake).resolve()
    result = scan_data_lake(data_lake_dir)

    print(f"# Data Lake 图谱覆盖探查")
    print()
    print(f"- 目录: `{data_lake_dir}`")
    print(f"- JSONL 文件族数量: " + ", ".join(f"`{k}`={v}" for k, v in sorted(summarize_data_lake_layers(data_lake_dir).items())))
    print()

    print(render_family_block("全部 JSONL 汇总", result["all_stats"]))

    for family in sorted(result["by_family"].keys()):
        print(render_family_block(f"文件族：{family}", result["by_family"][family]))

    extracted_stats = result["by_family"].get("extracted", {})
    if extracted_stats:
        print("## 结论提示")
        print()
        for cat in ["civil", "criminal", "administrative"]:
            stat = extracted_stats.get(cat)
            if not stat or stat.records == 0:
                print(f"- `{cat}`: 当前 `extracted_*` 候选池中没有可统计样本。")
                continue
            print(
                f"- `{cat}`: `extracted_*` 中共有 {stat.records} 条样本，"
                f"`facts` 非空 {stat.facts_nonempty}/{stat.records}，"
                f"`dispute_focuses` 非空 {stat.focuses_nonempty}/{stat.records}，"
                f"`relations` 非空 {stat.relations_nonempty}/{stat.records}，"
                f"三者同时非空 {stat.rich_graph_nonempty}/{stat.records}。"
            )


if __name__ == "__main__":
    main()
