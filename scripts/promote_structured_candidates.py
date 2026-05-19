#!/usr/bin/env python3
"""
promote_structured_candidates.py

将结构化程度较高的解析结果沉到 data_lake/extracted_candidate_*.jsonl，
供 generate_prompt.py 作为优先 few-shot 候选池使用。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "data_lake" / "extracted_candidate_structured_v1.jsonl"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def summarize_graph_coverage(output: Dict[str, Any]) -> Dict[str, Any]:
    facts = output.get("facts") or []
    focuses = output.get("dispute_focuses") or []
    relations = output.get("relations") or []
    nonempty_relations = [
        r for r in relations
        if (r.get("relation_type") or "").strip()
        and (r.get("source_id") or "").strip()
        and (r.get("target_id") or "").strip()
    ]
    return {
        "facts": len(facts),
        "focuses": len(focuses),
        "relations": len(nonempty_relations),
        "graph_ready": bool(nonempty_relations) and (len(facts) > 0 or len(focuses) > 0),
        "rich_graph": bool(nonempty_relations) and len(facts) > 0 and len(focuses) > 0,
    }


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if not path.exists():
        return items
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def load_first_record(path: Path) -> Dict[str, Any]:
    items = load_jsonl(path)
    if not items:
        raise ValueError(f"{path} 没有可用 JSONL 记录")
    return items[0]


def promote_record(record: Dict[str, Any], source_path: Path) -> Dict[str, Any]:
    meta = record.get("_meta") or {}
    curation = {
        "promoted_at": utc_now_iso(),
        "promoted_by": "scripts/promote_structured_candidates.py",
        "promotion_source": str(source_path),
        "candidate_pool": "extracted_candidate_structured_v1",
    }
    promoted = dict(record)
    promoted["source"] = "extracted_candidate"
    promoted["_meta"] = dict(meta)
    promoted["_meta"]["curation"] = curation
    return promoted


def upsert_records(path: Path, records: List[Dict[str, Any]]) -> int:
    existing = {}
    if path.exists():
        for item in load_jsonl(path):
            existing[item.get("row_id", "")] = item
    for item in records:
        existing[item.get("row_id", "")] = item
    ordered = list(existing.values())
    ordered.sort(key=lambda x: x.get("row_id", ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in ordered:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description="将结构化结果沉到 extracted_candidate 候选池")
    parser.add_argument("inputs", nargs="+", help="待沉淀的 JSONL 文件")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="候选池输出文件")
    parser.add_argument("--min-score", type=float, default=85.0, help="最低评分门槛")
    args = parser.parse_args()

    promoted: List[Dict[str, Any]] = []
    skipped: List[str] = []

    for item in args.inputs:
        path = Path(item).resolve()
        record = load_first_record(path)
        output = record.get("output") or {}
        eval_result = record.get("eval") or {}
        score = float(eval_result.get("score", 0) or 0)
        graph_cov = summarize_graph_coverage(output)
        if score < args.min_score:
            skipped.append(f"{path.name}: score={score} < {args.min_score}")
            continue
        if not graph_cov["graph_ready"]:
            skipped.append(
                f"{path.name}: graph_ready=False (facts={graph_cov['facts']}, "
                f"focuses={graph_cov['focuses']}, relations={graph_cov['relations']})"
            )
            continue
        promoted.append(promote_record(record, path))

    output_path = Path(args.output).resolve()
    written = upsert_records(output_path, promoted) if promoted else 0

    print(f"output={output_path}")
    print(f"promoted={written}")
    if promoted:
        print("rows=" + ", ".join(x.get("row_id", "?") for x in promoted))
    if skipped:
        print("skipped:")
        for msg in skipped:
            print(f"  - {msg}")


if __name__ == "__main__":
    main()
