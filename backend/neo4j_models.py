import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


ENTITY_COLLECTION_LABELS: Dict[str, str] = {
    "court_cases": "CourtCase",
    "trial_organizations": "TrialOrganization",
    "judges": "Judge",
    "legal_subjects": "LegalSubject",
    "attorneys": "Attorney",
    "facts": "Fact",
    "dispute_focuses": "DisputeFocus",
    "litigation_claims": "LitigationClaim",
    "procedural_opinions": "ProceduralOpinion",
    "argument_points": "ArgumentPoint",
    "judicial_assessments": "JudicialAssessment",
    "evidence": "Evidence",
    "judgment_results": "JudgmentResult",
    "legal_provisions": "LegalProvision",
    "legal_provision_elements": "LegalProvisionElement",
}


ENTITY_PREVIEW_FIELDS: Tuple[str, ...] = (
    "case_number",
    "name",
    "content",
    "claim_text",
    "argument_text",
    "assessment_text",
    "specific_judgment",
    "article",
    "statute",
)

ENTITY_TYPE_LABELS: Dict[str, str] = {
    label: label for label in ENTITY_COLLECTION_LABELS.values()
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_doc_id(row_id: str, doc_type: str = "case", external_id: str = "") -> str:
    prefix = "GUIDE" if str(doc_type or "case").strip() == "guiding_case" else "CASE"
    base = str(external_id or row_id or "manual_case").strip() or "manual_case"
    return f"{prefix}:{base}"


def build_run_id(doc_id: str, graph_layer: str) -> str:
    compact_doc = re.sub(r"[^A-Za-z0-9]+", "_", doc_id).strip("_") or "doc"
    compact_layer = re.sub(r"[^A-Za-z0-9]+", "_", graph_layer).strip("_") or "base"
    return f"ingest_{compact_layer}_{compact_doc}_{int(datetime.now(timezone.utc).timestamp())}"


def _sanitize_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list) and all(isinstance(item, (str, int, float, bool)) for item in value):
        return value
    return None


def _preview_text(item: Dict[str, Any]) -> str:
    for key in ENTITY_PREVIEW_FIELDS:
        value = item.get(key)
        if value:
            return str(value)[:200]
    return ""


def entity_id_for_item(item: Dict[str, Any]) -> str:
    for key in (
        "id", "stable_id", "court_case_id", "trial_org_id", "judge_id", "subject_id",
        "evidence_id", "fact_id", "focus_id", "result_id", "provision_id", "element_id"
    ):
        value = item.get(key)
        if value not in (None, "", [], {}):
            return str(value).strip()
    return ""


def entity_label_for_type(entity_type: Any) -> str:
    return ENTITY_TYPE_LABELS.get(str(entity_type or "").strip(), "")


def _unique_non_empty_strings(values: List[Any]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _normalize_entity_match_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[，。；：、“”‘’（）()【】\\[\\]<>《》,.;:!?！？\\-—_]", "", text)
    return text


def _strip_discovery_prefix(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    for sep in ("：", ":"):
        if sep in raw:
            _, tail = raw.split(sep, 1)
            tail = tail.strip()
            if tail:
                return tail
    return raw


def _strip_parenthetical(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    cleaned = re.sub(r"（[^）]{1,40}）", "", raw)
    cleaned = re.sub(r"\([^)]{1,40}\)", "", cleaned)
    return cleaned.strip()


def _legal_provision_element_text_candidates(node: Dict[str, Any]) -> List[str]:
    base_texts = _unique_non_empty_strings([
        node.get("label"),
        node.get("content"),
        node.get("title"),
    ])
    result: List[str] = []
    for text in base_texts:
        result.append(text)
        stripped_prefix = _strip_discovery_prefix(text)
        if stripped_prefix and stripped_prefix != text:
            result.append(stripped_prefix)
        stripped_paren = _strip_parenthetical(text)
        if stripped_paren and stripped_paren != text:
            result.append(stripped_paren)
        if stripped_prefix:
            stripped_both = _strip_parenthetical(stripped_prefix)
            if stripped_both and stripped_both not in (text, stripped_prefix):
                result.append(stripped_both)
    return _unique_non_empty_strings(result)


def _resolve_entity_text_match(
    *,
    expected_label: str,
    text_candidates: List[Any],
    base_entity_lookup: Dict[str, Any] | None = None,
) -> Tuple[str, str]:
    if not expected_label:
        return "", ""
    base_entity_lookup = base_entity_lookup or {}
    base_by_label_text = base_entity_lookup.get("by_label_text") or {}
    text_matches: List[Tuple[str, str]] = []
    seen_ids: set[str] = set()
    for text in _unique_non_empty_strings(text_candidates):
        normalized_text = _normalize_entity_match_text(text)
        if not normalized_text:
            continue
        for match in base_by_label_text.get((expected_label, normalized_text), []):
            entity_id = str(match.get("id") or "").strip()
            if not entity_id or entity_id in seen_ids:
                continue
            seen_ids.add(entity_id)
            text_matches.append((entity_id, match.get("label") or expected_label))
    if len(text_matches) == 1:
        return text_matches[0]
    return "", ""


def _resolve_retrieval_base_entity_ref(
    *,
    node: Dict[str, Any],
    entry: Dict[str, Any],
    base_entity_index: Dict[str, str],
    base_entity_lookup: Dict[str, Any] | None = None,
) -> Tuple[str, str]:
    base_entity_lookup = base_entity_lookup or {}
    base_by_id = base_entity_lookup.get("by_id") or base_entity_index
    base_by_label = base_entity_lookup.get("by_label") or {}
    expected_label = entity_label_for_type(node.get("type"))
    source_refs = entry.get("source_refs") or {}
    primary_entity = entry.get("primary_entity") or {}
    candidate_ids = _unique_non_empty_strings([
        node.get("id"),
        primary_entity.get("entity_id") if str(primary_entity.get("entity_type") or "").strip() == str(node.get("type") or "").strip() else "",
        *list(source_refs.get("entity_ids") or []),
        *list(source_refs.get("stable_ids") or []),
    ])
    direct_matches = [
        candidate_id
        for candidate_id in candidate_ids
        if candidate_id in base_by_id
        and (not expected_label or base_by_id[candidate_id] == expected_label)
    ]
    if len(direct_matches) == 1:
        entity_id = direct_matches[0]
        return entity_id, base_by_id[entity_id]
    if node.get("id") in base_by_id and (not expected_label or base_by_id[str(node.get("id"))] == expected_label):
        entity_id = str(node.get("id"))
        return entity_id, base_by_id[entity_id]
    if expected_label:
        text_candidates = [
            node.get("full_label"),
            node.get("label"),
            primary_entity.get("label") if str(primary_entity.get("entity_type") or "").strip() == str(node.get("type") or "").strip() else "",
        ]
        entity_id, label = _resolve_entity_text_match(
            expected_label=expected_label,
            text_candidates=text_candidates,
            base_entity_lookup=base_entity_lookup,
        )
        if entity_id and label:
            return entity_id, label
        if expected_label == "CourtCase":
            label_entities = [str(entity_id or "").strip() for entity_id in (base_by_label.get(expected_label) or []) if str(entity_id or "").strip()]
            unique_entities = list(dict.fromkeys(label_entities))
            if len(unique_entities) == 1:
                entity_id = unique_entities[0]
                return entity_id, expected_label
    return "", ""


def _resolve_discovery_base_entity_ref(
    *,
    node: Dict[str, Any],
    base_entity_index: Dict[str, str],
    base_entity_lookup: Dict[str, Any] | None = None,
) -> Tuple[str, str]:
    expected_label = entity_label_for_type(node.get("type") or node.get("nodeType"))
    base_entity_lookup = base_entity_lookup or {}
    base_by_id = base_entity_lookup.get("by_id") or base_entity_index
    original_id = str(node.get("id") or "").strip()
    if expected_label and original_id and base_by_id.get(original_id) == expected_label:
        return original_id, expected_label
    if expected_label == "LegalProvisionElement":
        entity_id, label = _resolve_entity_text_match(
            expected_label=expected_label,
            text_candidates=_legal_provision_element_text_candidates(node),
            base_entity_lookup=base_entity_lookup,
        )
        if entity_id and label:
            return entity_id, label
    entity_id, label = _resolve_entity_text_match(
        expected_label=expected_label,
        text_candidates=[
            node.get("label"),
            node.get("content"),
            node.get("title"),
        ],
        base_entity_lookup=base_entity_lookup,
    )
    if entity_id and label:
        return entity_id, label
    return "", ""


def _resolve_discovery_external_ref(
    *,
    node_ref: str,
    base_entity_index: Dict[str, str],
    base_entity_lookup: Dict[str, Any] | None = None,
) -> Tuple[str, str]:
    base_entity_lookup = base_entity_lookup or {}
    base_by_id = base_entity_lookup.get("by_id") or base_entity_index
    entity_label = str(base_by_id.get(node_ref) or "").strip()
    if entity_label:
        return node_ref, entity_label
    return "", ""


def _build_discovery_canonical_node_id(
    *,
    doc_id: str,
    node_type: str,
    label_text: str,
    original_id: str,
) -> str:
    compact_type = re.sub(r"[^A-Za-z0-9]+", "_", str(node_type or "node")).strip("_") or "node"
    basis = _normalize_entity_match_text(label_text) or str(original_id or "").strip() or compact_type
    digest = hashlib.sha1(f"{compact_type}|{basis}".encode("utf-8")).hexdigest()[:12]
    return f"discovery_node:{doc_id}:{compact_type}:{digest}"


def _discovery_effective_node_type(
    raw_node_type: str,
    *,
    resolved_base: bool,
) -> str:
    node_type = str(raw_node_type or "").strip()
    if node_type == "LegalProvisionElement" and not resolved_base:
        return "AppliedLegalProvisionElement"
    return node_type


def _is_document_canonical_discovery_type(node_type: str) -> bool:
    return str(node_type or "").strip() in {
        "AppliedLegalProvisionElement",
        "SentencingCircumstance",
        "EvidenceChain",
    }


def build_document_payload(
    *,
    doc_id: str,
    doc_type: str,
    external_id: str,
    row_id: str,
    case_name: str,
    raw_text: str,
    source: str,
    graph_layer: str,
) -> Dict[str, Any]:
    return {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "external_id": external_id or row_id,
        "row_id": row_id,
        "case_name": case_name or "",
        "source": source or "manual",
        "graph_layer": graph_layer,
        "raw_text_ref": row_id or "",
        "source_text_hash": "",
        "raw_text_preview": str(raw_text or "")[:500],
        "updated_at": utc_now_iso(),
    }


def build_chunk_payloads(doc_id: str, text_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    for item in text_chunks or []:
        payloads.append({
            "chunk_id": str(item.get("chunk_id") or "").strip(),
            "doc_id": doc_id,
            "section_type": str(item.get("section_type") or "").strip() or "unknown",
            "seq": int(item.get("seq") or 0),
            "section_seq": int(item.get("section_seq") or 0),
            "paragraph_index": int(item.get("paragraph_index") or 0),
            "text": str(item.get("text") or ""),
            "char_start": int(item.get("char_start") or -1),
            "char_end": int(item.get("char_end") or -1),
            "chunking_version": str(item.get("chunking_version") or "v1"),
            "updated_at": utc_now_iso(),
        })
    return [item for item in payloads if item["chunk_id"]]


def build_entity_payloads(
    *,
    doc_id: str,
    json_result: Dict[str, Any],
    graph_layer: str,
    source_run_id: str,
    version_id: str,
) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    for collection, label in ENTITY_COLLECTION_LABELS.items():
        items = json_result.get(collection) or []
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            entity_id = entity_id_for_item(item)
            if not entity_id:
                continue
            props: Dict[str, Any] = {
                "id": entity_id,
                "doc_id": doc_id,
                "graph_layer": graph_layer,
                "source_collection": collection,
                "source_run_id": source_run_id,
                "version_id": version_id,
                "active_flag": True,
                "preview_text": _preview_text(item),
                "payload_json": json.dumps(item, ensure_ascii=False),
                "updated_at": utc_now_iso(),
            }
            for key, value in item.items():
                sanitized = _sanitize_scalar(value)
                if sanitized is not None and key not in props:
                    props[key] = sanitized
            payloads.append({
                "label": label,
                "collection": collection,
                "id": entity_id,
                "properties": props,
            })
    return payloads


def build_relation_payloads(
    *,
    doc_id: str,
    json_result: Dict[str, Any],
    graph_layer: str,
    source_run_id: str,
) -> List[Dict[str, Any]]:
    entity_index: Dict[str, str] = {}
    for payload in build_entity_payloads(
        doc_id=doc_id,
        json_result=json_result,
        graph_layer=graph_layer,
        source_run_id=source_run_id,
        version_id="",
    ):
        entity_index[payload["id"]] = payload["label"]

    results: List[Dict[str, Any]] = []
    relation_groups = [
        ("relations", "explicit"),
        ("derived_relations", "derived"),
    ]
    for collection_name, relation_origin in relation_groups:
        for rel in json_result.get(collection_name) or []:
            if not isinstance(rel, dict):
                continue
            source_id = str(rel.get("source_id") or "").strip()
            target_id = str(rel.get("target_id") or "").strip()
            relation_type = str(rel.get("relation_type") or "").strip() or "unknown"
            if not source_id or not target_id:
                continue
            derived_rule = str(rel.get("derived_rule") or "").strip()
            if relation_origin == "derived":
                relation_id = f"{source_id}|{target_id}|{relation_type}|{derived_rule or 'derived'}|{graph_layer}"
            else:
                relation_id = f"{source_id}|{target_id}|{relation_type}|{graph_layer}"
            props = {
                "relation_id": relation_id,
                "doc_id": doc_id,
                "graph_layer": graph_layer,
                "relation_type": relation_type,
                "source_run_id": source_run_id,
                "relation_origin": relation_origin,
                "derived_rule": derived_rule,
                "active_flag": True,
                "payload_json": json.dumps(rel, ensure_ascii=False),
                "updated_at": utc_now_iso(),
            }
            results.append({
                "source_id": source_id,
                "source_label": entity_index.get(source_id),
                "target_id": target_id,
                "target_label": entity_index.get(target_id),
                "properties": props,
            })
    return [item for item in results if item["source_label"] and item["target_label"]]


def build_alignment_payloads(
    *,
    source_alignment: Dict[str, Any],
    entity_payloads: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    entity_index = {item["id"]: item["label"] for item in entity_payloads}
    payloads: List[Dict[str, Any]] = []
    for node_key, matches in (source_alignment or {}).items():
        _, _, entity_id = str(node_key).partition(":")
        entity_id = entity_id or str(node_key)
        label = entity_index.get(entity_id)
        if not label:
            continue
        for match in matches or []:
            chunk_id = str(match.get("chunk_id") or "").strip()
            if not chunk_id:
                continue
            payloads.append({
                "entity_id": entity_id,
                "entity_label": label,
                "chunk_id": chunk_id,
                "score": float(match.get("score") or 0),
                "match_type": str(match.get("match_type") or "unknown"),
                "updated_at": utc_now_iso(),
            })
    return payloads


def build_retrieval_layer_payload(
    *,
    doc_id: str,
    bundle: Dict[str, Any],
    source_run_id: str,
    base_entity_index: Dict[str, str] | None = None,
    base_entity_lookup: Dict[str, Any] | None = None,
) -> Dict[str, List[Dict[str, Any]]]:
    entity_payloads: List[Dict[str, Any]] = []
    entity_reference_payloads: List[Dict[str, Any]] = []
    relation_payloads: List[Dict[str, Any]] = []
    base_entity_index = base_entity_index or {}

    for entry_index, entry in enumerate(bundle.get("entries") or []):
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("entry_id") or f"entry_{entry_index}").strip()
        if not entry_id:
            continue
        retrieval_entry_id = f"retrieval_entry:{entry_id}"
        entry_props = {
            "id": retrieval_entry_id,
            "doc_id": doc_id,
            "graph_layer": "retrieval",
            "source_collection": "retrieval_entries",
            "source_run_id": source_run_id,
            "bundle_id": str(bundle.get("bundle_id") or ""),
            "row_id": str(bundle.get("row_id") or ""),
            "entry_id": entry_id,
            "entry_type": str(entry.get("entry_type") or ""),
            "view_label": str(entry.get("view_label") or ""),
            "title": str(entry.get("title") or ""),
            "summary": str(entry.get("summary") or ""),
            "retrieval_text": str(entry.get("retrieval_text") or ""),
            "expanded_text": str(entry.get("expanded_text") or ""),
            "scene_tags": [str(item) for item in (entry.get("scene_tags") or []) if item not in (None, "")],
            "keywords": [str(item) for item in (entry.get("keywords") or []) if item not in (None, "")],
            "priority": float(entry.get("priority") or 0),
            "source_parse_version_id": str(bundle.get("source_parse_version_id") or ""),
            "active_flag": True,
            "payload_json": json.dumps(entry, ensure_ascii=False),
            "updated_at": utc_now_iso(),
        }
        entity_payloads.append({
            "label": "RetrievalEntry",
            "id": retrieval_entry_id,
            "properties": entry_props,
        })

        chain_nodes = ((entry.get("graph_payload") or {}).get("chain_nodes") or [])
        chain_edges = ((entry.get("graph_payload") or {}).get("chain_edges") or [])
        node_refs: List[Dict[str, Any]] = []
        for node_index, node in enumerate(chain_nodes):
            if not isinstance(node, dict):
                continue
            original_id = str(node.get("id") or f"node_{node_index}").strip()
            base_entity_id, base_entity_label = _resolve_retrieval_base_entity_ref(
                node=node,
                entry=entry,
                base_entity_index=base_entity_index,
                base_entity_lookup=base_entity_lookup,
            )
            if base_entity_id and base_entity_label:
                entity_reference_payloads.append({
                    "label": base_entity_label,
                    "id": base_entity_id,
                    "properties": {
                        "id": base_entity_id,
                        "doc_id": doc_id,
                        "graph_layer": "retrieval",
                        "source_run_id": source_run_id,
                        "updated_at": utc_now_iso(),
                    },
                })
                node_refs.append({
                    "original_id": original_id,
                    "graph_node_id": base_entity_id,
                    "graph_node_label": base_entity_label,
                    "is_base_entity_ref": True,
                })
                relation_payloads.append({
                    "source_label": "RetrievalEntry",
                    "target_label": base_entity_label,
                    "properties": {
                        "relation_id": f"{retrieval_entry_id}|{base_entity_id}|uses_entity|retrieval|{node_index}",
                        "doc_id": doc_id,
                        "graph_layer": "retrieval",
                        "relation_type": "uses_entity",
                        "source_run_id": source_run_id,
                        "relation_origin": "retrieval_entry_entity_ref",
                        "original_node_id": original_id,
                        "node_type": str(node.get("type") or ""),
                        "seq": node_index,
                        "active_flag": True,
                        "payload_json": json.dumps({
                            "entry_id": entry_id,
                            "node_id": original_id,
                            "node_type": str(node.get("type") or ""),
                            "resolved_entity_id": base_entity_id,
                        }, ensure_ascii=False),
                        "updated_at": utc_now_iso(),
                        "source_id": retrieval_entry_id,
                        "target_id": base_entity_id,
                    },
                })
                continue

            graph_node_id = f"retrieval_node:{entry_id}:{original_id}"
            node_props = {
                "id": graph_node_id,
                "doc_id": doc_id,
                "graph_layer": "retrieval",
                "source_collection": "retrieval_graph_nodes",
                "source_run_id": source_run_id,
                "bundle_id": str(bundle.get("bundle_id") or ""),
                "entry_id": entry_id,
                "original_node_id": original_id,
                "node_type": str(node.get("type") or ""),
                "label_text": str(node.get("label") or ""),
                "preview_text": str(node.get("label") or "")[:200],
                "active_flag": True,
                "payload_json": json.dumps(node, ensure_ascii=False),
                "updated_at": utc_now_iso(),
            }
            entity_payloads.append({
                "label": "RetrievalGraphNode",
                "id": graph_node_id,
                "properties": node_props,
            })
            node_refs.append({
                "original_id": original_id,
                "graph_node_id": graph_node_id,
                "graph_node_label": "RetrievalGraphNode",
                "is_base_entity_ref": False,
            })
            relation_payloads.append({
                "source_label": "RetrievalEntry",
                "target_label": "RetrievalGraphNode",
                "properties": {
                    "relation_id": f"{retrieval_entry_id}|{graph_node_id}|includes_node|retrieval",
                    "doc_id": doc_id,
                    "graph_layer": "retrieval",
                    "relation_type": "includes_node",
                    "source_run_id": source_run_id,
                    "relation_origin": "retrieval_entry",
                    "active_flag": True,
                    "payload_json": json.dumps({"entry_id": entry_id, "node_id": original_id}, ensure_ascii=False),
                    "updated_at": utc_now_iso(),
                    "source_id": retrieval_entry_id,
                    "target_id": graph_node_id,
                },
            })

        for edge_index, edge in enumerate(chain_edges):
            if not isinstance(edge, dict):
                continue
            from_node_ref = node_refs[edge_index] if edge_index < len(node_refs) else None
            to_node_ref = node_refs[edge_index + 1] if (edge_index + 1) < len(node_refs) else None
            if not from_node_ref or not to_node_ref:
                continue
            from_ref = from_node_ref["graph_node_id"]
            to_ref = to_node_ref["graph_node_id"]
            relation_type = str(edge.get("relation_type") or edge.get("label") or "retrieval_chain")
            relation_payloads.append({
                "source_label": from_node_ref["graph_node_label"],
                "target_label": to_node_ref["graph_node_label"],
                "properties": {
                    "relation_id": f"{from_ref}|{to_ref}|{relation_type}|retrieval",
                    "doc_id": doc_id,
                    "graph_layer": "retrieval",
                    "relation_type": relation_type,
                    "source_run_id": source_run_id,
                    "relation_origin": "retrieval_chain",
                    "active_flag": True,
                    "payload_json": json.dumps(edge, ensure_ascii=False),
                    "updated_at": utc_now_iso(),
                    "source_id": from_ref,
                    "target_id": to_ref,
                },
            })

    return {
        "entity_payloads": entity_payloads,
        "entity_reference_payloads": entity_reference_payloads,
        "relation_payloads": relation_payloads,
    }


def build_discovery_layer_payload(
    *,
    doc_id: str,
    discovery_record: Dict[str, Any] | None = None,
    discovery_history: List[Dict[str, Any]] | None = None,
    source_run_id: str,
    base_entity_index: Dict[str, str] | None = None,
    base_entity_lookup: Dict[str, Any] | None = None,
) -> Dict[str, List[Dict[str, Any]]]:
    entity_payloads: List[Dict[str, Any]] = []
    entity_reference_payloads: List[Dict[str, Any]] = []
    relation_payloads: List[Dict[str, Any]] = []
    entity_seen: set[str] = set()
    entity_reference_seen: set[Tuple[str, str]] = set()
    anchor_entity_ids: Dict[str, str] = {}
    base_entity_index = base_entity_index or {}
    base_entity_lookup = base_entity_lookup or {}
    records = [item for item in (discovery_history or []) if isinstance(item, dict)]
    if not records and discovery_record:
        records = [discovery_record]

    def append_entity(label: str, entity_id: str, properties: Dict[str, Any]) -> None:
        if entity_id in entity_seen:
            return
        entity_seen.add(entity_id)
        entity_payloads.append({
            "label": label,
            "id": entity_id,
            "properties": properties,
        })

    def append_entity_reference(label: str, entity_id: str) -> None:
        key = (label, entity_id)
        if not label or not entity_id or key in entity_reference_seen:
            return
        entity_reference_seen.add(key)
        entity_reference_payloads.append({
            "label": label,
            "id": entity_id,
            "properties": {
                "id": entity_id,
                "doc_id": doc_id,
                "graph_layer": "discovery",
                "source_run_id": source_run_id,
                "updated_at": utc_now_iso(),
            },
        })

    def ensure_anchor(node_ref: str) -> str:
        anchor_id = anchor_entity_ids.get(node_ref)
        if anchor_id:
            return anchor_id
        anchor_id = f"discovery_anchor:{doc_id}:{node_ref}"
        anchor_entity_ids[node_ref] = anchor_id
        append_entity(
            "DiscoveryAnchor",
            anchor_id,
            {
                "id": anchor_id,
                "doc_id": doc_id,
                "graph_layer": "discovery",
                "source_collection": "discovery_anchors",
                "source_run_id": source_run_id,
                "original_node_id": node_ref,
                "preview_text": node_ref[:200],
                "active_flag": True,
                "payload_json": json.dumps({"original_node_id": node_ref}, ensure_ascii=False),
                "updated_at": utc_now_iso(),
            },
        )
        return anchor_id

    for record_index, item in enumerate(records):
        record_id = str(item.get("id") or f"discovery_{record_index}_{int(datetime.now(timezone.utc).timestamp())}")
        result = item.get("result") or {}
        discovery_payload = result.get("knowledge_discovery") or {}
        discovery_record_id = f"discovery_record:{doc_id}:{record_id}"
        append_entity(
            "DiscoveryRecord",
            discovery_record_id,
            {
                "id": discovery_record_id,
                "doc_id": doc_id,
                "graph_layer": "discovery",
                "source_collection": "discovery_records",
                "source_run_id": source_run_id,
                "record_id": record_id,
                "step_type": str(item.get("type") or ""),
                "timestamp_text": str(item.get("timestamp") or ""),
                "reasoning": str(item.get("reasoning") or ""),
                "conclusion": str(result.get("conclusion") or ""),
                "preview_text": str(result.get("conclusion") or "")[:200],
                "active_flag": True,
                "payload_json": json.dumps(item, ensure_ascii=False),
                "updated_at": utc_now_iso(),
            },
        )

        node_id_map: Dict[str, Dict[str, Any]] = {}
        outcome_node_map: Dict[str, Dict[str, str]] = {}
        record_anchor_refs: set[str] = set()
        record_entity_refs: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for node_index, node in enumerate(discovery_payload.get("new_nodes") or []):
            if not isinstance(node, dict):
                continue
            original_id = str(node.get("id") or f"node_{node_index}").strip()
            if not original_id:
                continue
            raw_node_type = str(node.get("type") or node.get("nodeType") or "")
            label_text = str(node.get("label") or node.get("content") or node.get("title") or "")
            if raw_node_type == "ArgumentOutcome":
                outcome_code = str(label_text or original_id or "unknown").strip() or "unknown"
                outcome_node_map[original_id] = {
                    "outcome_code": outcome_code,
                    "outcome_text": label_text or outcome_code,
                    "original_node_id": original_id,
                }
                continue
            base_entity_id, base_entity_label = _resolve_discovery_base_entity_ref(
                node=node,
                base_entity_index=base_entity_index,
                base_entity_lookup=base_entity_lookup,
            )
            node_type = _discovery_effective_node_type(
                raw_node_type,
                resolved_base=bool(base_entity_id and base_entity_label),
            )
            if base_entity_id and base_entity_label:
                append_entity_reference(base_entity_label, base_entity_id)
                node_id_map[original_id] = {
                    "graph_node_id": base_entity_id,
                    "graph_node_label": base_entity_label,
                    "is_base_entity_ref": True,
                }
                record_entity_refs[(base_entity_label, base_entity_id)] = {
                    "entity_label": base_entity_label,
                    "entity_id": base_entity_id,
                    "original_node_id": original_id,
                    "node_type": node_type,
                }
                continue
            discovery_node_id = _build_discovery_canonical_node_id(
                doc_id=doc_id,
                node_type=node_type,
                label_text=label_text,
                original_id=original_id,
            )
            node_id_map[original_id] = {
                "graph_node_id": discovery_node_id,
                "graph_node_label": "DiscoveryNode",
                "is_base_entity_ref": False,
            }
            append_entity(
                "DiscoveryNode",
                discovery_node_id,
                {
                    "id": discovery_node_id,
                    "doc_id": doc_id,
                    "graph_layer": "discovery",
                    "source_collection": "discovery_nodes",
                    "source_run_id": source_run_id,
                    "record_id": record_id,
                    "original_node_id": original_id,
                    "node_type": node_type,
                    "canonical_scope": "document" if _is_document_canonical_discovery_type(node_type) else "record",
                    "node_role": "document_canonical_derived" if _is_document_canonical_discovery_type(node_type) else "discovery_node",
                    "derived_type": node_type if _is_document_canonical_discovery_type(node_type) else "",
                    "label_text": label_text,
                    "preview_text": label_text[:200],
                    "active_flag": True,
                    "payload_json": json.dumps(node, ensure_ascii=False),
                    "updated_at": utc_now_iso(),
                },
            )
            relation_payloads.append({
                "source_label": "DiscoveryRecord",
                "target_label": "DiscoveryNode",
                "properties": {
                    "relation_id": f"{discovery_record_id}|{discovery_node_id}|produces_node|discovery",
                    "doc_id": doc_id,
                    "graph_layer": "discovery",
                    "relation_type": "produces_node",
                    "source_run_id": source_run_id,
                    "relation_origin": "discovery_record",
                    "active_flag": True,
                    "payload_json": json.dumps({"record_id": record_id, "node_id": original_id}, ensure_ascii=False),
                    "updated_at": utc_now_iso(),
                    "source_id": discovery_record_id,
                    "target_id": discovery_node_id,
                },
            })

        for edge_index, edge in enumerate(discovery_payload.get("new_edges") or []):
            if not isinstance(edge, dict):
                continue
            raw_from = str(edge.get("from") or "").strip()
            raw_to = str(edge.get("to") or "").strip()
            if not raw_from or not raw_to:
                continue
            relation_type = str(edge.get("type") or edge.get("label") or f"discovery_edge_{edge_index}")
            if raw_to in outcome_node_map:
                if raw_from in node_id_map:
                    source_label, source_id = node_id_map[raw_from]["graph_node_label"], node_id_map[raw_from]["graph_node_id"]
                else:
                    source_id, source_label = _resolve_discovery_external_ref(
                        node_ref=raw_from,
                        base_entity_index=base_entity_index,
                        base_entity_lookup=base_entity_lookup,
                    )
                    if source_id and source_label:
                        append_entity_reference(source_label, source_id)
                        record_entity_refs[(source_label, source_id)] = {
                            "entity_label": source_label,
                            "entity_id": source_id,
                            "original_node_id": raw_from,
                            "node_type": "",
                        }
                    else:
                        source_label, source_id = "DiscoveryAnchor", ensure_anchor(raw_from)
                        record_anchor_refs.add(raw_from)
                outcome_info = outcome_node_map[raw_to]
                relation_payloads.append({
                    "source_label": source_label,
                    "target_label": "DiscoveryRecord",
                    "properties": {
                        "relation_id": f"{source_id}|{discovery_record_id}|{relation_type}|{outcome_info['outcome_code']}|discovery",
                        "doc_id": doc_id,
                        "graph_layer": "discovery",
                        "relation_type": relation_type,
                        "source_run_id": source_run_id,
                        "relation_origin": "discovery_edge_outcome_property",
                        "outcome_code": outcome_info["outcome_code"],
                        "outcome_text": outcome_info["outcome_text"],
                        "outcome_node_id": outcome_info["original_node_id"],
                        "active_flag": True,
                        "payload_json": json.dumps(edge, ensure_ascii=False),
                        "updated_at": utc_now_iso(),
                        "source_id": source_id,
                        "target_id": discovery_record_id,
                    },
                })
                continue
            if raw_from in outcome_node_map:
                outcome_info = outcome_node_map[raw_from]
                if raw_to in node_id_map:
                    target_label, target_id = node_id_map[raw_to]["graph_node_label"], node_id_map[raw_to]["graph_node_id"]
                else:
                    target_id, target_label = _resolve_discovery_external_ref(
                        node_ref=raw_to,
                        base_entity_index=base_entity_index,
                        base_entity_lookup=base_entity_lookup,
                    )
                    if target_id and target_label:
                        append_entity_reference(target_label, target_id)
                        record_entity_refs[(target_label, target_id)] = {
                            "entity_label": target_label,
                            "entity_id": target_id,
                            "original_node_id": raw_to,
                            "node_type": "",
                        }
                    else:
                        target_label, target_id = "DiscoveryAnchor", ensure_anchor(raw_to)
                        record_anchor_refs.add(raw_to)
                relation_payloads.append({
                    "source_label": "DiscoveryRecord",
                    "target_label": target_label,
                    "properties": {
                        "relation_id": f"{discovery_record_id}|{target_id}|{relation_type}|{outcome_info['outcome_code']}|discovery",
                        "doc_id": doc_id,
                        "graph_layer": "discovery",
                        "relation_type": relation_type,
                        "source_run_id": source_run_id,
                        "relation_origin": "discovery_edge_outcome_property",
                        "outcome_code": outcome_info["outcome_code"],
                        "outcome_text": outcome_info["outcome_text"],
                        "outcome_node_id": outcome_info["original_node_id"],
                        "active_flag": True,
                        "payload_json": json.dumps(edge, ensure_ascii=False),
                        "updated_at": utc_now_iso(),
                        "source_id": discovery_record_id,
                        "target_id": target_id,
                    },
                })
                continue
            from_ref = node_id_map.get(raw_from)
            to_ref = node_id_map.get(raw_to)
            if from_ref:
                source_label, source_id = from_ref["graph_node_label"], from_ref["graph_node_id"]
            else:
                source_id, source_label = _resolve_discovery_external_ref(
                    node_ref=raw_from,
                    base_entity_index=base_entity_index,
                    base_entity_lookup=base_entity_lookup,
                )
                if source_id and source_label:
                    append_entity_reference(source_label, source_id)
                    record_entity_refs[(source_label, source_id)] = {
                        "entity_label": source_label,
                        "entity_id": source_id,
                        "original_node_id": raw_from,
                        "node_type": "",
                    }
                else:
                    source_label, source_id = "DiscoveryAnchor", ensure_anchor(raw_from)
                    record_anchor_refs.add(raw_from)
            if to_ref:
                target_label, target_id = to_ref["graph_node_label"], to_ref["graph_node_id"]
            else:
                target_id, target_label = _resolve_discovery_external_ref(
                    node_ref=raw_to,
                    base_entity_index=base_entity_index,
                    base_entity_lookup=base_entity_lookup,
                )
                if target_id and target_label:
                    append_entity_reference(target_label, target_id)
                    record_entity_refs[(target_label, target_id)] = {
                        "entity_label": target_label,
                        "entity_id": target_id,
                        "original_node_id": raw_to,
                        "node_type": "",
                    }
                else:
                    target_label, target_id = "DiscoveryAnchor", ensure_anchor(raw_to)
                    record_anchor_refs.add(raw_to)
            relation_payloads.append({
                "source_label": source_label,
                "target_label": target_label,
                "properties": {
                    "relation_id": f"{source_id}|{target_id}|{relation_type}|discovery",
                    "doc_id": doc_id,
                    "graph_layer": "discovery",
                    "relation_type": relation_type,
                    "source_run_id": source_run_id,
                    "relation_origin": "discovery_edge",
                    "active_flag": True,
                    "payload_json": json.dumps(edge, ensure_ascii=False),
                    "updated_at": utc_now_iso(),
                    "source_id": source_id,
                    "target_id": target_id,
                },
            })

        for ref_info in record_entity_refs.values():
            relation_payloads.append({
                "source_label": "DiscoveryRecord",
                "target_label": ref_info["entity_label"],
                "properties": {
                    "relation_id": f"{discovery_record_id}|{ref_info['entity_id']}|references_entity|discovery",
                    "doc_id": doc_id,
                    "graph_layer": "discovery",
                    "relation_type": "references_entity",
                    "source_run_id": source_run_id,
                    "relation_origin": "discovery_record_entity_ref",
                    "original_node_id": ref_info["original_node_id"],
                    "node_type": ref_info["node_type"],
                    "active_flag": True,
                    "payload_json": json.dumps(
                        {
                            "record_id": record_id,
                            "node_id": ref_info["original_node_id"],
                            "resolved_entity_id": ref_info["entity_id"],
                        },
                        ensure_ascii=False,
                    ),
                    "updated_at": utc_now_iso(),
                    "source_id": discovery_record_id,
                    "target_id": ref_info["entity_id"],
                },
            })

        for node_ref in sorted(record_anchor_refs):
            anchor_id = anchor_entity_ids[node_ref]
            relation_payloads.append({
                "source_label": "DiscoveryRecord",
                "target_label": "DiscoveryAnchor",
                "properties": {
                    "relation_id": f"{discovery_record_id}|{anchor_id}|references_anchor|discovery",
                    "doc_id": doc_id,
                    "graph_layer": "discovery",
                    "relation_type": "references_anchor",
                    "source_run_id": source_run_id,
                    "relation_origin": "discovery_record",
                    "active_flag": True,
                    "payload_json": json.dumps({"record_id": record_id, "anchor_id": node_ref}, ensure_ascii=False),
                    "updated_at": utc_now_iso(),
                    "source_id": discovery_record_id,
                    "target_id": anchor_id,
                },
            })

    return {
        "entity_payloads": entity_payloads,
        "entity_reference_payloads": entity_reference_payloads,
        "relation_payloads": relation_payloads,
    }
