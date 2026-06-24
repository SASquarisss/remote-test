#!/usr/bin/env python3
"""
核查 retrieval 层是否把本可复用的 base 实体又新建成 RetrievalGraphNode。

默认扫描所有已有 retrieval 数据的文书，也支持通过 --doc-id 仅检查单个文书。

输出分为三类：
1. should_reuse_by_id
   - RetrievalGraphNode.original_node_id 已能命中 base 实体，且标签也一致
   - 这类属于高置信重复，理论上应直接复用 base
2. possible_duplicate_by_text
   - 找不到同 id 的 base 实体，但在同标签的 base 实体中找到了同文本候选
   - 这类是中置信重复，通常说明 retrieval 链节点和 base 语义上重复
3. no_base_candidate
   - 当前找不到合适的 base 候选，更接近“真正新增节点”或“现有对齐规则不足”
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.neo4j_models import entity_label_for_type  # noqa: E402
from backend.neo4j_repository import Neo4jRepository  # noqa: E402


BASE_TEXT_FIELDS = (
    "preview_text",
    "name",
    "content",
    "claim_text",
    "argument_text",
    "assessment_text",
    "specific_judgment",
    "article",
    "statute",
    "case_number",
)


def normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[，。；：、“”‘’（）()【】\[\]<>《》,.;:!?！？\-—_]", "", text)
    return text


def compact_text(value: Any, limit: int = 96) -> str:
    text = str(value or "").strip()
    return text[:limit]


def base_text_candidates(node: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for field in BASE_TEXT_FIELDS:
        value = node.get(field)
        if value not in (None, "", [], {}):
            values.append(str(value))
    statute = str(node.get("statute") or "").strip()
    article = str(node.get("article") or "").strip()
    if statute and article:
        values.append(f"《{statute}》第{article}条")
    unique: List[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(str(value))
    return unique


def get_doc_ids(repo: Neo4jRepository, explicit_doc_id: str | None) -> List[str]:
    if explicit_doc_id:
        return [explicit_doc_id]
    rows = repo.run_read(
        """
        MATCH (d:Document)-[r:HAS_ENTITY {graph_layer: 'retrieval'}]->(:RetrievalEntry)
        WHERE coalesce(r.active_flag, true) = true
        RETURN DISTINCT d.doc_id AS doc_id
        ORDER BY doc_id
        """
    )
    return [str(row.get("doc_id") or "").strip() for row in rows if str(row.get("doc_id") or "").strip()]


def fetch_base_nodes(repo: Neo4jRepository, doc_id: str) -> List[Dict[str, Any]]:
    return repo.run_read(
        """
        MATCH (:Document {doc_id: $doc_id})-[r:HAS_ENTITY {graph_layer: 'base'}]->(n)
        WHERE coalesce(r.active_flag, true) = true
        RETURN
          n.id AS id,
          labels(n) AS labels,
          n.preview_text AS preview_text,
          n.name AS name,
          n.content AS content,
          n.claim_text AS claim_text,
          n.argument_text AS argument_text,
          n.assessment_text AS assessment_text,
          n.specific_judgment AS specific_judgment,
          n.article AS article,
          n.statute AS statute,
          n.case_number AS case_number
        ORDER BY id
        """,
        {"doc_id": doc_id},
    )


def fetch_retrieval_fallback_nodes(repo: Neo4jRepository, doc_id: str) -> List[Dict[str, Any]]:
    return repo.run_read(
        """
        MATCH (:Document {doc_id: $doc_id})-[hr:HAS_ENTITY {graph_layer: 'retrieval'}]->(entry:RetrievalEntry)
        WHERE coalesce(hr.active_flag, true) = true
        MATCH (entry)-[rel:RELATES_TO {graph_layer: 'retrieval'}]->(rg:RetrievalGraphNode)
        WHERE coalesce(rel.active_flag, true) = true
          AND rel.relation_type = 'includes_node'
        RETURN
          entry.id AS retrieval_entry_node_id,
          entry.entry_id AS entry_id,
          entry.entry_type AS entry_type,
          entry.title AS entry_title,
          rel.seq AS seq,
          rg.id AS retrieval_node_id,
          rg.original_node_id AS original_node_id,
          rg.node_type AS node_type,
          rg.label_text AS label_text
        ORDER BY entry.entry_id, rel.seq, rg.id
        """,
        {"doc_id": doc_id},
    )


def build_base_indexes(base_nodes: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    by_id: Dict[str, Dict[str, Any]] = {}
    by_label_text: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
    for node in base_nodes:
        node_id = str(node.get("id") or "").strip()
        labels = [str(label).strip() for label in (node.get("labels") or []) if str(label).strip()]
        if not node_id or not labels:
            continue
        label = labels[0]
        row = {
            "id": node_id,
            "label": label,
            "preview": compact_text(
                node.get("preview_text")
                or node.get("name")
                or node.get("content")
                or node.get("specific_judgment")
                or node.get("case_number")
                or node_id
            ),
        }
        by_id[node_id] = row
        for candidate_text in base_text_candidates(node):
            key = (label, normalize_text(candidate_text))
            by_label_text.setdefault(key, []).append(row)
    return {"by_id": by_id, "by_label_text": by_label_text}


def classify_duplicates(doc_id: str, retrieval_nodes: List[Dict[str, Any]], base_indexes: Dict[str, Any]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    base_by_id = base_indexes["by_id"]
    base_by_label_text = base_indexes["by_label_text"]
    for row in retrieval_nodes:
        node_type = str(row.get("node_type") or "").strip()
        expected_label = entity_label_for_type(node_type)
        original_node_id = str(row.get("original_node_id") or "").strip()
        retrieval_text = str(row.get("label_text") or "").strip()
        normalized_retrieval_text = normalize_text(retrieval_text)
        category = "no_base_candidate"
        matched_base: List[Dict[str, Any]] = []
        note = ""

        id_match = base_by_id.get(original_node_id)
        if id_match and expected_label and id_match["label"] == expected_label:
            category = "should_reuse_by_id"
            matched_base = [id_match]
            note = "original_node_id 已命中同标签 base 实体，理论上应直接复用"
        else:
            if id_match and expected_label and id_match["label"] != expected_label:
                note = f"original_node_id 命中 base，但标签不一致：expected={expected_label}, actual={id_match['label']}"
            if expected_label and normalized_retrieval_text:
                text_matches = base_by_label_text.get((expected_label, normalized_retrieval_text), [])
                if text_matches:
                    category = "possible_duplicate_by_text"
                    matched_base = text_matches[:5]
                    if not note:
                        note = "同标签且文本归一化后相同，疑似语义重复"

        results.append(
            {
                "doc_id": doc_id,
                "entry_id": str(row.get("entry_id") or ""),
                "entry_type": str(row.get("entry_type") or ""),
                "entry_title": str(row.get("entry_title") or ""),
                "seq": row.get("seq"),
                "retrieval_node_id": str(row.get("retrieval_node_id") or ""),
                "original_node_id": original_node_id,
                "node_type": node_type,
                "expected_label": expected_label,
                "label_text": retrieval_text,
                "category": category,
                "note": note,
                "matched_base": matched_base,
            }
        )
    return results


def print_report(results: List[Dict[str, Any]]) -> None:
    if not results:
        print("未发现 retrieval fallback 节点。")
        return
    category_counts = Counter(item["category"] for item in results)
    type_counts = Counter((item["category"], item["entry_type"]) for item in results)
    print("=== Summary ===")
    print(f"retrieval_fallback_node_count: {len(results)}")
    for category, count in category_counts.most_common():
        print(f"- {category}: {count}")
    print("\n=== By Entry Type ===")
    for (category, entry_type), count in sorted(type_counts.items()):
        print(f"- {category} / {entry_type or 'unknown'}: {count}")

    for category in ("should_reuse_by_id", "possible_duplicate_by_text", "no_base_candidate"):
        bucket = [item for item in results if item["category"] == category]
        if not bucket:
            continue
        print(f"\n=== {category} ({len(bucket)}) ===")
        for item in bucket:
            matched_text = ", ".join(
                f"{base['label']}:{base['id']}:{base['preview']}"
                for base in item["matched_base"]
            )
            print(
                f"- doc={item['doc_id']} entry={item['entry_id']} "
                f"type={item['entry_type']} seq={item['seq']} node_type={item['node_type']} "
                f"original={item['original_node_id']} retrieval_node={item['retrieval_node_id']}"
            )
            print(f"  title={compact_text(item['entry_title'])}")
            print(f"  text={compact_text(item['label_text'])}")
            if item["note"]:
                print(f"  note={item['note']}")
            if matched_text:
                print(f"  matched_base={matched_text}")


def main() -> int:
    parser = argparse.ArgumentParser(description="核查 retrieval 层是否重复创建本应复用的 base 节点")
    parser.add_argument("--doc-id", help="仅检查指定文书，例如 CASE:manual_1780383896")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出详细结果")
    args = parser.parse_args()

    repo = Neo4jRepository()
    try:
        all_results: List[Dict[str, Any]] = []
        doc_ids = get_doc_ids(repo, args.doc_id)
        if not doc_ids:
            print("未找到包含 retrieval 数据的文书。")
            return 0
        for doc_id in doc_ids:
            base_nodes = fetch_base_nodes(repo, doc_id)
            retrieval_nodes = fetch_retrieval_fallback_nodes(repo, doc_id)
            if not retrieval_nodes:
                continue
            base_indexes = build_base_indexes(base_nodes)
            all_results.extend(classify_duplicates(doc_id, retrieval_nodes, base_indexes))
        if args.json:
            print(json.dumps(all_results, ensure_ascii=False, indent=2))
        else:
            print_report(all_results)
        return 0
    finally:
        repo.close()


if __name__ == "__main__":
    raise SystemExit(main())
