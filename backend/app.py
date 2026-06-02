"""Flask API for legal text parsing terminal."""
import copy
import json
import os
import re
import sys
import os
import urllib.error
import urllib.request
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

# Ensure backend/ is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parser import (
    parse_text,
    parse_enhancement,
    enrich_graph_output,
    kg_convert,
    extract_case_name,
    evaluate_output,
    _entity_identity,
    _entity_signature_payload,
    _relation_identity,
    _stable_dump,
)

# ── Paths ───────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]
MANUAL_JSONL = REPO_ROOT / "data_lake" / "manual_parsed.jsonl"
EXTRACTED_CANDIDATE_JSONL = REPO_ROOT / "data_lake" / "extracted_candidate_manual_save_v1.jsonl"
CASES_INDEX = REPO_ROOT / "visualization" / "data" / "cases_index.json"
ADMIN_STATIC_DATA = REPO_ROOT / "visualization" / "data" / "admin_instances_data.js"
RUNTIME_RETRIEVAL_ROOT = REPO_ROOT / "runtime_retrieval"

# ── App ─────────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)


# ── Helpers ─────────────────────────────────────────────────────────────────

def load_cases_index() -> list:
    if CASES_INDEX.exists():
        with open(CASES_INDEX, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_jsonl_records(path: Path) -> dict:
    """Load all records from JSONL into a dict keyed by row_id."""
    records = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    records[rec.get("row_id", "")] = rec
                except json.JSONDecodeError:
                    pass
    return records


def load_manual_records() -> dict:
    return load_jsonl_records(MANUAL_JSONL)


def load_candidate_records() -> dict:
    return load_jsonl_records(EXTRACTED_CANDIDATE_JSONL)


@lru_cache(maxsize=1)
def load_admin_static_bundle() -> dict:
    """Load the legacy admin_instances static bundle from JS assignments."""
    if not ADMIN_STATIC_DATA.exists():
        return {"all_graphs": [], "raw_data": {}}

    text = ADMIN_STATIC_DATA.read_text(encoding="utf-8")
    all_graphs_marker = "window.ALL_GRAPHS ="
    raw_data_marker = "window.RAW_DATA ="
    all_graphs_pos = text.find(all_graphs_marker)
    raw_data_pos = text.find(raw_data_marker)

    if all_graphs_pos == -1 or raw_data_pos == -1 or raw_data_pos <= all_graphs_pos:
        raise ValueError("Failed to parse admin_instances_data.js bundle")

    all_graphs_json = text[all_graphs_pos + len(all_graphs_marker):raw_data_pos].strip()
    raw_data_json = text[raw_data_pos + len(raw_data_marker):].strip()

    if all_graphs_json.endswith(";"):
        all_graphs_json = all_graphs_json[:-1].rstrip()
    if raw_data_json.endswith(";"):
        raw_data_json = raw_data_json[:-1].rstrip()

    return {
        "all_graphs": json.loads(all_graphs_json),
        "raw_data": json.loads(raw_data_json),
    }


def _count_non_empty(items) -> int:
    return len([item for item in (items or []) if item])


def _to_case_category_label(value: str) -> str:
    mapping = {
        "civil": "民事案件",
        "criminal": "刑事案件",
        "administrative": "行政案件",
    }
    return mapping.get(value, value or "")


def _extract_static_case_stats(output: dict) -> dict:
    return {
        "facts": _count_non_empty(output.get("facts")),
        "focuses": _count_non_empty(output.get("dispute_focuses")),
        "relations": _count_non_empty(output.get("relations")),
        "evidence": _count_non_empty(output.get("evidence")),
        "provisions": _count_non_empty(output.get("legal_provisions")),
    }


def _extract_case_meta_from_output(output: dict, source_label: str = "static") -> dict:
    output = output or {}
    case_type = output.get("case_type", {}) or {}

    judgment_years = set()
    publication_years = set()
    trial_levels = set()
    procedures = set()
    case_categories = set()
    case_reasons = set()

    for court_case in output.get("court_cases", []) or []:
        court_case = court_case or {}
        date_value = str(court_case.get("judgment_date") or court_case.get("filing_date") or "")
        match = re.search(r"(\d{4})", date_value)
        if match:
            judgment_years.add(match.group(1))
        if court_case.get("trial_level"):
            trial_levels.add(str(court_case["trial_level"]))
        if court_case.get("trial_procedure"):
            procedures.add(court_case["trial_procedure"])

    publication_date = str(
        (output.get("guiding_case") or {}).get("publication_date")
        or output.get("publication_date")
        or ""
    )
    publication_match = re.search(r"(\d{4})", publication_date)
    if publication_match:
        publication_years.add(publication_match.group(1))

    if case_type.get("category"):
        case_categories.add(_to_case_category_label(case_type["category"]))
    if case_type.get("level1"):
        case_reasons.add(str(case_type["level1"]))
    if case_type.get("level2"):
        case_reasons.add(str(case_type["level2"]))

    return {
        "source": source_label,
        "case_categories": sorted(case_categories),
        "case_reasons": sorted(case_reasons),
        "trial_levels": sorted(trial_levels),
        "procedures": list(procedures),
        "judgment_years": sorted(judgment_years, reverse=True),
        "publication_years": sorted(publication_years, reverse=True),
        # Backward-compatible aliases for older front-end code paths.
        "types": sorted(case_categories | case_reasons),
        "years": sorted(judgment_years | publication_years, reverse=True),
        "stats": _extract_static_case_stats(output),
    }


def _extract_static_case_meta(record: dict, source: str = "static") -> dict:
    output = (record or {}).get("output", {}) or {}
    input_meta = (record or {}).get("input", {}) or {}
    return _extract_case_meta_from_output(output, input_meta.get("web_name") or source)


def _find_static_case_record(row_id: str, version: str | None = None) -> tuple[dict | None, dict | None]:
    bundle = load_admin_static_bundle()
    all_graphs = bundle["all_graphs"]
    raw_data = bundle["raw_data"]

    matched = [item for item in all_graphs if str(item.get("row_id")) == str(row_id)]
    if not matched:
        return None, None

    if version is not None:
        summary = next((item for item in matched if str(item.get("version", 1)) == str(version)), None)
    else:
        summary = sorted(matched, key=lambda item: int(item.get("version", 1)), reverse=True)[0]

    if not summary:
        return None, None

    version_no = int(summary.get("version", 1) or 1)
    key = f"{row_id}__v{version_no}" if version_no > 1 else str(row_id)
    record = raw_data.get(key) or raw_data.get(str(row_id))
    return summary, record


def save_cases_index(index: list):
    CASES_INDEX.parent.mkdir(parents=True, exist_ok=True)
    with open(CASES_INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def append_to_jsonl(record: dict):
    MANUAL_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(MANUAL_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def upsert_jsonl_record(path: Path, key_field: str, record: dict):
    """Merge one record into JSONL by key_field, replacing older versions."""
    existing = []
    key_value = record.get(key_field)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if item.get(key_field) != key_value:
                    existing.append(item)
    existing.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for item in existing:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_save_target_info(target_layer: str) -> tuple[Path, str, str]:
    if target_layer == "extracted_candidate":
        return (
            EXTRACTED_CANDIDATE_JSONL,
            "manual_web_save_candidate",
            "backend/app.py:/api/save(extracted_candidate)",
        )
    return (
        MANUAL_JSONL,
        "manual_web_save",
        "backend/app.py:/api/save(manual)",
    )


def build_save_meta(row_id: str, text: str, json_result: dict, case_name: str, target_layer: str) -> dict:
    case_type = (json_result.get("case_type") or {}).get("category", "")
    prompt_path = Path(REPO_ROOT) / "ontology" / "prompts" / "auto_v5_civil.txt"
    prompt_sha1 = ""
    if prompt_path.exists():
        prompt_sha1 = hashlib.sha1(prompt_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    target_path, batch_label, entrypoint = get_save_target_info(target_layer)
    return {
        "schema_version": "extracted_record_meta_v1",
        "run_started_at": _utc_now_iso(),
        "run_id": f"{target_layer}-save-{row_id}",
        "generator": {
            "extractor": "backend/parser.py",
            "entrypoint": entrypoint,
            "batch_label": batch_label,
        },
        "input": {
            "path": "manual://web-terminal",
            "source": "web_terminal",
            "text_sha1": hashlib.sha1((text or "").encode("utf-8")).hexdigest(),
            "text_length": len(text or ""),
        },
        "output": {
            "path": str(target_path.relative_to(REPO_ROOT)),
        },
        "prompt": {
            "path": str(prompt_path.relative_to(REPO_ROOT)) if prompt_path.exists() else "",
            "version": "manual_web_v2",
            "sha1": prompt_sha1,
            "length": len(prompt_path.read_text(encoding="utf-8")) if prompt_path.exists() else 0,
        },
        "model": {
            "provider": "deepseek",
            "name": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
        },
        "record": {
            "row_id": row_id,
            "row_index": 0,
            "status": "saved",
            "generated_at": _utc_now_iso(),
            "case_name": case_name or "",
            "case_type": case_type or "",
            "target_layer": target_layer,
        },
    }


ENTITY_COLLECTION_KEYS = [
    "legal_subjects",
    "evidence",
    "facts",
    "dispute_focuses",
    "judgment_results",
    "legal_provisions",
    "legal_provision_elements",
    "judges",
    "attorneys",
]

ENTITY_NODE_TYPE_MAP = {
    "legal_subjects": "LegalSubject",
    "evidence": "Evidence",
    "facts": "Fact",
    "dispute_focuses": "DisputeFocus",
    "judgment_results": "JudgmentResult",
    "legal_provisions": "LegalProvision",
    "legal_provision_elements": "LegalProvisionElement",
    "judges": "Judge",
    "attorneys": "Attorney",
    "case_summary": "CaseSummary",
}


def _next_enhancement_run_id() -> str:
    return f"enh_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"


def _get_case_summary_identity(item: dict) -> str:
    return "case_summary"


def _normalize_output_snapshot(output: dict) -> dict:
    return enrich_graph_output(copy.deepcopy(output or {}))


def _build_graph_payload(output: dict) -> dict:
    normalized_output = _normalize_output_snapshot(output)
    graph = kg_convert(normalized_output)
    return {
        "json_result": normalized_output,
        "nodes": graph["nodes"],
        "edges": graph["edges"],
    }


def _coerce_change_summary(summary: dict | None) -> dict:
    summary = summary or {}
    return {
        "entity_added": summary.get("entity_added") or {},
        "entity_updated": summary.get("entity_updated") or {},
        "relation_added": summary.get("relation_added") or {},
        "relation_updated": summary.get("relation_updated") or {},
        "derived_relation_added": summary.get("derived_relation_added") or {},
        "derived_relation_updated": summary.get("derived_relation_updated") or {},
        "changed_keys": summary.get("changed_keys") or [],
        "unresolved": summary.get("unresolved") or [],
    }


def _build_version_entry(
    version_id: str,
    label: str,
    output: dict,
    *,
    version_type: str = "base",
    source_run_id: str | None = None,
    change_summary: dict | None = None,
    highlight_patch: dict | None = None,
    created_at: str | None = None,
) -> dict:
    payload = _build_graph_payload(output)
    return {
        "version_id": version_id,
        "label": label,
        "version_type": version_type,
        "source_run_id": source_run_id,
        "created_at": created_at or _utc_now_iso(),
        "change_summary": _coerce_change_summary(change_summary),
        "highlight_patch": highlight_patch or {},
        **payload,
    }


def _ensure_versions(record_like: dict, default_output: dict) -> tuple[list, str]:
    versions = copy.deepcopy(record_like.get("parse_versions") or [])
    active_version_id = record_like.get("active_version_id") or ""
    if not versions:
        versions = [
            _build_version_entry(
                "v0",
                "初始解析",
                default_output,
                version_type="base",
                source_run_id=None,
                change_summary={},
                highlight_patch={},
            )
        ]
        active_version_id = "v0"
    else:
        for version in versions:
            if not version.get("json_result"):
                version.update(_build_graph_payload(default_output))
            elif not version.get("nodes") or not version.get("edges"):
                version.update(_build_graph_payload(version.get("json_result") or default_output))
            version["change_summary"] = _coerce_change_summary(version.get("change_summary"))
            version["highlight_patch"] = version.get("highlight_patch") or {}
        if not active_version_id:
            active_version_id = versions[-1].get("version_id") or "v0"
    return versions, active_version_id


def _find_version(versions: list, version_id: str | None) -> dict | None:
    if not versions:
        return None
    if version_id:
        for version in versions:
            if version.get("version_id") == version_id:
                return version
    return versions[-1]


def _ensure_enhancement_runs(record_like: dict) -> list:
    runs = copy.deepcopy(record_like.get("enhancement_runs") or record_like.get("term_enhancement_runs") or [])
    latest = record_like.get("enhancement_result") or record_like.get("term_enhancement_result")
    if latest and isinstance(latest, dict):
        latest_run_id = latest.get("run_id") or _next_enhancement_run_id()
        latest.setdefault("run_id", latest_run_id)
        latest.setdefault("apply_status", "pending")
        if not any((run or {}).get("run_id") == latest_run_id for run in runs):
            runs.append(copy.deepcopy(latest))
    normalized = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        cloned = copy.deepcopy(run)
        cloned.setdefault("run_id", _next_enhancement_run_id())
        cloned.setdefault("apply_status", "pending")
        normalized.append(cloned)
    return normalized


def _resolve_enhancement_run(runs: list, enhancement_run_id: str | None) -> dict | None:
    if not runs:
        return None
    if enhancement_run_id:
        for run in runs:
            if run.get("run_id") == enhancement_run_id:
                return run
    return runs[-1]


def _replace_enhancement_run(runs: list, updated_run: dict) -> list:
    result = []
    updated_id = updated_run.get("run_id")
    replaced = False
    for run in runs:
        if (run or {}).get("run_id") == updated_id:
            result.append(copy.deepcopy(updated_run))
            replaced = True
        else:
            result.append(copy.deepcopy(run))
    if not replaced:
        result.append(copy.deepcopy(updated_run))
    return result


def _entity_identity_for_key(key: str, item: dict) -> str:
    if key == "case_summary":
        return _get_case_summary_identity(item if isinstance(item, dict) else {})
    return _entity_identity(key, item)


def _entity_payload_dump(key: str, item: dict) -> str:
    if key == "case_summary":
        return _stable_dump(item or {})
    return _stable_dump(_entity_signature_payload(key, item))


def _entity_label_candidates(key: str, item: dict) -> list[str]:
    if not isinstance(item, dict):
        return []
    if key == "legal_provisions":
        statute = str(item.get("statute") or item.get("law_name") or "").strip()
        article = str(item.get("article") or "").strip()
        if statute and article:
            return [f"{statute}第{article}条"]
    if key == "legal_provision_elements":
        content = str(item.get("content") or item.get("applicable_fact_pattern") or "").strip()
        return [content[:36]] if content else []
    if key == "evidence":
        content = str(item.get("content") or "").strip()
        return [content[:40]] if content else []
    if key == "facts":
        content = str(item.get("content") or "").strip()
        return [content[:40]] if content else []
    if key == "dispute_focuses":
        content = str(item.get("content") or "").strip()
        return [content[:40]] if content else []
    if key == "judgment_results":
        result_type = str(item.get("result_type") or item.get("specific_judgment") or "").strip()
        return [result_type] if result_type else []
    if key == "legal_subjects":
        name = str(item.get("name") or "").strip()
        return [name] if name else []
    if key == "judges":
        name = str(item.get("name") or "").strip()
        return [name] if name else []
    if key == "attorneys":
        name = str(item.get("name") or "").strip()
        return [name] if name else []
    if key == "case_summary":
        summary = item or {}
        text = summary.get("key_facts") or summary.get("disputed_issues") or ""
        if isinstance(text, list):
            text = "; ".join(str(x) for x in text if x)
        text = str(text).strip()
        return [text[:60]] if text else []
    return []


def _find_graph_node_ids(graph_payload: dict, key: str, item: dict) -> list[str]:
    node_type = ENTITY_NODE_TYPE_MAP.get(key)
    if not node_type:
        return []
    stable_id = str(item.get("stable_id") or item.get("evidence_id") or "").strip()
    source_id = str(item.get("id") or item.get("node_id") or "").strip()
    label_candidates = {label for label in _entity_label_candidates(key, item) if label}
    matched = []
    for node in graph_payload.get("nodes") or []:
        if node.get("nodeType") != node_type:
            continue
        if stable_id and str(node.get("entityStableId") or "").strip() == stable_id:
            matched.append(str(node.get("id")))
            continue
        if source_id and (
            str(node.get("entitySourceId") or "").strip() == source_id
            or str(node.get("id") or "").strip() == source_id
        ):
            matched.append(str(node.get("id")))
            continue
        if label_candidates and str(node.get("label") or "").strip() in label_candidates:
            matched.append(str(node.get("id")))
    return list(dict.fromkeys(matched))


def _find_graph_edge_ids(graph_payload: dict, relation: dict, *, is_derived: bool) -> list[str]:
    if not isinstance(relation, dict):
        return []
    source_ref = str(relation.get("source_id") or "").strip()
    target_ref = str(relation.get("target_id") or "").strip()
    relation_type = str(relation.get("relation_type") or "").strip()
    edge_type = "derived" if is_derived else "explicit"
    matched = []
    for edge in graph_payload.get("edges") or []:
        if str(edge.get("edgeType") or "") != edge_type:
            continue
        if str(edge.get("relationType") or "") != relation_type:
            continue
        if source_ref and str(edge.get("sourceRef") or "").strip() != source_ref:
            continue
        if target_ref and str(edge.get("targetRef") or "").strip() != target_ref:
            continue
        matched.append(str(edge.get("id") or ""))
    return [edge_id for edge_id in dict.fromkeys(matched) if edge_id]


def _compute_highlight_patch(base_output: dict, next_output: dict, graph_payload: dict) -> tuple[dict, dict]:
    base_output = base_output or {}
    next_output = next_output or {}
    highlight = {
        "addedNodeIds": [],
        "updatedNodeIds": [],
        "addedEdgeIds": [],
        "updatedEdgeIds": [],
        "addedDerivedEdgeIds": [],
        "updatedDerivedEdgeIds": [],
        "changedKeys": [],
    }
    summary = {
        "entity_added": {},
        "entity_updated": {},
        "relation_added": {},
        "relation_updated": {},
        "derived_relation_added": {},
        "derived_relation_updated": {},
        "changed_keys": [],
        "unresolved": [],
    }

    for key in ENTITY_COLLECTION_KEYS:
        base_items = [item for item in (base_output.get(key) or []) if isinstance(item, dict)]
        next_items = [item for item in (next_output.get(key) or []) if isinstance(item, dict)]
        base_lookup = {
            _entity_identity_for_key(key, item): _entity_payload_dump(key, item)
            for item in base_items
        }
        for item in next_items:
            identity = _entity_identity_for_key(key, item)
            payload_dump = _entity_payload_dump(key, item)
            if identity not in base_lookup:
                summary["entity_added"][key] = summary["entity_added"].get(key, 0) + 1
                highlight["addedNodeIds"].extend(_find_graph_node_ids(graph_payload, key, item))
            elif base_lookup[identity] != payload_dump:
                summary["entity_updated"][key] = summary["entity_updated"].get(key, 0) + 1
                highlight["updatedNodeIds"].extend(_find_graph_node_ids(graph_payload, key, item))

    base_summary = base_output.get("case_summary") or {}
    next_summary = next_output.get("case_summary") or {}
    if next_summary:
        base_dump = _entity_payload_dump("case_summary", base_summary)
        next_dump = _entity_payload_dump("case_summary", next_summary)
        if not base_summary and next_summary:
            summary["entity_added"]["case_summary"] = 1
            highlight["addedNodeIds"].extend(_find_graph_node_ids(graph_payload, "case_summary", next_summary))
        elif base_dump != next_dump:
            summary["entity_updated"]["case_summary"] = 1
            highlight["updatedNodeIds"].extend(_find_graph_node_ids(graph_payload, "case_summary", next_summary))

    for key, is_derived, added_key, updated_key, added_target, updated_target in (
        ("relations", False, "relation_added", "relation_updated", "addedEdgeIds", "updatedEdgeIds"),
        ("derived_relations", True, "derived_relation_added", "derived_relation_updated", "addedDerivedEdgeIds", "updatedDerivedEdgeIds"),
    ):
        base_items = [item for item in (base_output.get(key) or []) if isinstance(item, dict)]
        next_items = [item for item in (next_output.get(key) or []) if isinstance(item, dict)]
        base_lookup = {
            _relation_identity(item): _stable_dump(item)
            for item in base_items
        }
        for item in next_items:
            relation_type = str(item.get("relation_type") or "").strip() or "unknown"
            identity = _relation_identity(item)
            payload_dump = _stable_dump(item)
            if identity not in base_lookup:
                summary[added_key][relation_type] = summary[added_key].get(relation_type, 0) + 1
                highlight[added_target].extend(_find_graph_edge_ids(graph_payload, item, is_derived=is_derived))
            elif base_lookup[identity] != payload_dump:
                summary[updated_key][relation_type] = summary[updated_key].get(relation_type, 0) + 1
                highlight[updated_target].extend(_find_graph_edge_ids(graph_payload, item, is_derived=is_derived))

    changed_keys = set()
    changed_keys.update(summary["entity_added"].keys())
    changed_keys.update(summary["entity_updated"].keys())
    if summary["relation_added"] or summary["relation_updated"]:
        changed_keys.add("relations")
    if summary["derived_relation_added"] or summary["derived_relation_updated"]:
        changed_keys.add("derived_relations")
    highlight["changedKeys"] = sorted(changed_keys)
    summary["changed_keys"] = sorted(changed_keys)

    for key in (
        "addedNodeIds",
        "updatedNodeIds",
        "addedEdgeIds",
        "updatedEdgeIds",
        "addedDerivedEdgeIds",
        "updatedDerivedEdgeIds",
    ):
        highlight[key] = [item for item in dict.fromkeys(highlight[key]) if item]

    return highlight, summary


def _build_preview_result(base_output: dict, enhancement_result: dict) -> tuple[dict, dict, dict]:
    enhancement_payload = enhancement_result.get("enhancement_payload") or {}
    enhanced_output = enhancement_result.get("enhanced_json_result") or base_output
    if not enhanced_output and enhancement_payload:
        enhanced_output = copy.deepcopy(base_output or {})
    preview_graph = _build_graph_payload(enhanced_output)
    highlight_patch, change_summary = _compute_highlight_patch(base_output, preview_graph.get("json_result") or {}, preview_graph)
    return preview_graph, highlight_patch, change_summary


def _serialize_version_summaries(versions: list, active_version_id: str) -> list:
    serialized = []
    for version in versions:
        serialized.append({
            "version_id": version.get("version_id"),
            "label": version.get("label"),
            "version_type": version.get("version_type"),
            "source_run_id": version.get("source_run_id"),
            "created_at": version.get("created_at"),
            "change_summary": _coerce_change_summary(version.get("change_summary")),
            "is_active": version.get("version_id") == active_version_id,
        })
    return serialized


def _resolve_runtime_case(row_id: str | None) -> tuple[str, dict, Path | None]:
    row_id = str(row_id or "").strip()
    if row_id:
        manual_records = load_manual_records()
        if row_id in manual_records:
            return "manual", copy.deepcopy(manual_records[row_id]), MANUAL_JSONL
        candidate_records = load_candidate_records()
        if row_id in candidate_records:
            return "extracted_candidate", copy.deepcopy(candidate_records[row_id]), EXTRACTED_CANDIDATE_JSONL
    payload = _load_test_data()
    if payload.get("json_result"):
        return "test_data", copy.deepcopy(payload), None
    return "unknown", {}, None


def _persist_runtime_case(kind: str, payload: dict, path: Path | None = None):
    if kind == "manual" and path:
        upsert_jsonl_record(path, "row_id", payload)
        return
    if kind == "extracted_candidate" and path:
        upsert_jsonl_record(path, "row_id", payload)
        return
    _patch_test_data(payload)


RETRIEVAL_EDITABLE_FIELDS = {
    "title",
    "summary",
    "retrieval_text",
    "expanded_text",
    "keywords",
    "scene_tags",
    "notes",
}
RETRIEVAL_TEXT_FIELDS = {"title", "summary", "retrieval_text", "expanded_text"}
RETRIEVAL_EMBED_DIM = 12
RETRIEVAL_EMBED_URL = os.environ.get("RETRIEVAL_EMBED_URL", "http://10.1.5.3:8080/v1/embeddings")
RETRIEVAL_EMBED_MODEL = os.environ.get("RETRIEVAL_EMBED_MODEL", "BAAI/bge-base-zh-v1.5")
RETRIEVAL_EMBED_TIMEOUT = float(os.environ.get("RETRIEVAL_EMBED_TIMEOUT", "12"))
RETRIEVAL_RESULT_TYPE_LABELS = {
    "guilty": "有罪判决",
    "not_guilty": "无罪判决",
    "liable": "承担责任",
    "not_liable": "不承担责任",
    "dismissed": "驳回",
    "withdrawn": "撤诉",
    "partially_upheld": "部分维持",
    "remanded": "发回重审",
    "punitive_damages": "惩罚性赔偿",
    "procedural_ruling": "程序性裁定",
    "bankruptcy_declared": "宣告破产",
    "mediation_agreement": "调解协议",
    "arbitration_award": "仲裁裁决",
    "administrative_decision": "行政决定",
}


def _retrieval_short_text(value: str | None, limit: int = 64) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _retrieval_slug(value: str | None) -> str:
    text = re.sub(r"[^0-9A-Za-z_\-]+", "_", str(value or "").strip())
    return text.strip("_") or "default"


def _retrieval_case_reason(output: dict) -> str:
    case_type = output.get("case_type") or {}
    return str(case_type.get("level2") or case_type.get("level1") or case_type.get("category") or "")


def _retrieval_case_taxonomy(output: dict, case_meta: dict | None = None) -> dict:
    case_type = output.get("case_type") or {}
    case_meta = case_meta or {}
    return {
        "case_type": _to_case_category_label(case_type.get("category") or ""),
        "reason_level1": str(case_type.get("level1") or ""),
        "reason_level2": str(case_type.get("level2") or ""),
        "reason_level3": str(case_type.get("level3") or ""),
        "trial_level": "、".join(case_meta.get("trial_levels") or []),
        "judgment_year": "、".join(case_meta.get("judgment_years") or []),
        "publication_year": "、".join(case_meta.get("publication_years") or []),
    }


def _retrieval_meta_header(output: dict, case_meta: dict, asset_view: str, view_label: str) -> dict:
    return {
        **_retrieval_case_taxonomy(output, case_meta),
        "asset_view": asset_view,
        "view_label": view_label,
    }


def _retrieval_meta_lines(meta_header: dict) -> list[str]:
    return [
        f"案件类型：{meta_header.get('case_type') or '未标注'}",
        f"一级案由：{meta_header.get('reason_level1') or '未标注'}",
        f"二级案由：{meta_header.get('reason_level2') or '未标注'}",
        f"三级案由：{meta_header.get('reason_level3') or '未标注'}",
        f"审级：{meta_header.get('trial_level') or '未标注'}",
    ]


def _retrieval_relation_label(edge: dict | None) -> str:
    edge = edge or {}
    preferred = str(edge.get("label") or "").strip()
    if preferred and re.search(r"[\u4e00-\u9fff]", preferred):
        return preferred
    mapping = {
        "has_subject": "涉及主体",
        "has_fact": "关联事实",
        "has_focus": "形成争点",
        "has_dispute_focus": "形成争点",
        "relates_to_focus": "关联争点",
        "proves_fact": "证明事实",
        "leads_to": "导向裁判",
        "resolved_by": "对应裁判",
        "judgment_cites": "适用法条",
        "supports_reasoning": "支撑说理",
        "element_of_provision": "对应法条",
        "matches_element": "命中法条要件",
        "relates_to_fact": "关联事实",
        "receives_judgment": "对应裁判",
    }
    raw = str(edge.get("relation_type") or preferred).strip()
    return mapping.get(raw, raw.replace("_", ""))


def _retrieval_chain_narrative(chain_nodes: list[dict], chain_edges: list[dict]) -> str:
    safe_nodes = [item for item in (chain_nodes or []) if item and item.get("label")]
    safe_edges = [item for item in (chain_edges or []) if item and (item.get("relation_type") or item.get("label"))]
    if not safe_nodes:
        return ""
    if len(safe_nodes) == 1:
        return f"{safe_nodes[0].get('label')}。"
    parts = [str(safe_nodes[0].get("label") or "").strip()]
    for idx, edge in enumerate(safe_edges):
        next_index = idx + 1
        if next_index >= len(safe_nodes):
            break
        target = str(safe_nodes[next_index].get("label") or "").strip()
        if not target:
            continue
        relation_text = _retrieval_relation_label(edge)
        parts.append(f"{relation_text}{target}" if relation_text else target)
    return "，".join([item for item in parts if item]) + "。"


def _retrieval_chain_transition_label(node: dict | None) -> str:
    node = node or {}
    return str(node.get("full_label") or node.get("label") or node.get("type") or "未命名实体").strip()


def _retrieval_chain_missing_items(chain_nodes: list[dict], chain_edges: list[dict]) -> list[str]:
    safe_nodes = [item for item in (chain_nodes or []) if item and item.get("label")]
    safe_edges = [item for item in (chain_edges or []) if item and (item.get("relation_type") or item.get("label"))]
    if len(safe_nodes) < 2:
        return ["链路中的实体节点不足，至少需要两个实体才能形成关系链"]
    items = []
    for idx in range(len(safe_nodes) - 1):
        left = _retrieval_chain_transition_label(safe_nodes[idx])
        right = _retrieval_chain_transition_label(safe_nodes[idx + 1])
        edge = safe_edges[idx] if idx < len(safe_edges) else None
        if edge is None:
            items.append(f"缺少“{left}”到“{right}”的关系")
            continue
        if not edge.get("verified", True):
            relation_text = _retrieval_relation_label(edge) or str(edge.get("relation_type") or "关联").strip()
            items.append(f"缺少已验证的“{left}”到“{right}”关系，当前期望关系为“{relation_text}”")
    return items


def _retrieval_chain_warning_text(missing_items: list[str] | None = None) -> str:
    items = [str(item).strip() for item in (missing_items or []) if str(item).strip()]
    if not items:
        return "当前未形成有效的实体关系链，暂不能自动生成主检索正文，请先补充实体之间的关联关系。"
    return "当前未形成有效的实体关系链，暂不能自动生成主检索正文。\n" + "\n".join([f"- {item}" for item in items])


def _retrieval_has_valid_chain(chain_nodes: list[dict], chain_edges: list[dict]) -> bool:
    safe_nodes = [item for item in (chain_nodes or []) if item and item.get("label")]
    safe_edges = [item for item in (chain_edges or []) if item and (item.get("relation_type") or item.get("label"))]
    if len(safe_nodes) < 2:
        return False
    verified_edges = [item for item in safe_edges if item.get("verified", True)]
    return len(verified_edges) >= (len(safe_nodes) - 1)


def _retrieval_line_to_sentence(line: str | None) -> str:
    text = str(line or "").strip().strip("；")
    if not text:
        return ""
    if text.endswith("。"):
        return text
    if "：" in text:
        key, value = text.split("：", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            return f"{key}。"
        return f"{key}为{value}。"
    return f"{text}。"


def _retrieval_compose_text(view_label: str, meta_header: dict, graph_payload: dict | None, lines: list[str]) -> str:
    graph_payload = graph_payload or {}
    if not graph_payload.get("is_valid_chain"):
        return ""
    sentences = [
        f"该检索资产采用{view_label}。",
        *[_retrieval_line_to_sentence(line) for line in _retrieval_meta_lines(meta_header)],
        str(graph_payload.get("chain_text") or "").strip(),
        *[_retrieval_line_to_sentence(line) for line in (lines or [])],
    ]
    return "".join([item for item in sentences if item])


def _retrieval_chain_node(node_type: str, label: str, node_id: str | None = None, *, full_label: str | None = None) -> dict:
    label_text = str(label or "").strip()
    return {
        "id": str(node_id or ""),
        "type": str(node_type or ""),
        "label": _retrieval_short_text(label_text, 28),
        "full_label": str(full_label or label_text),
    }


def _retrieval_chain_edge(relation_type: str, label: str | None = None, edge_id: str | None = None, *, verified: bool = True) -> dict:
    relation_text = str(relation_type or label or "").strip()
    return {
        "id": str(edge_id or ""),
        "relation_type": relation_text,
        "label": str(label or relation_text),
        "verified": bool(verified),
    }


def _retrieval_graph_payload(
    path_type: str,
    chain_nodes: list[dict],
    chain_edges: list[dict],
    *,
    path_label: str = "",
    description: str = "",
    seed_node_ids: list | None = None,
    seed_edge_ids: list | None = None,
) -> dict:
    safe_nodes = [item for item in (chain_nodes or []) if item and item.get("label")]
    safe_edges = [item for item in (chain_edges or []) if item and (item.get("relation_type") or item.get("label"))]
    chain_text = _retrieval_chain_narrative(safe_nodes, safe_edges)
    is_valid_chain = _retrieval_has_valid_chain(safe_nodes, safe_edges)
    missing_items = [] if is_valid_chain else _retrieval_chain_missing_items(safe_nodes, safe_edges)
    return {
        "path_type": path_type,
        "path_label": path_label or path_type,
        "description": description or "",
        "chain_text": chain_text,
        "is_valid_chain": is_valid_chain,
        "warning_text": "" if is_valid_chain else _retrieval_chain_warning_text(missing_items),
        "missing_items": missing_items,
        "chain_nodes": safe_nodes,
        "chain_edges": safe_edges,
        "seed_node_ids": seed_node_ids or [item.get("id") for item in safe_nodes[:1] if item.get("id")],
        "seed_edge_ids": seed_edge_ids or [item.get("id") for item in safe_edges[:1] if item.get("id")],
        "node_ids": [item.get("id") for item in safe_nodes if item.get("id")],
        "edge_ids": [item.get("id") for item in safe_edges if item.get("id")],
        "entity_types": list(dict.fromkeys(item.get("type") for item in safe_nodes if item.get("type"))),
        "relation_types": list(dict.fromkeys(item.get("relation_type") for item in safe_edges if item.get("relation_type"))),
    }


def _retrieval_ontology_payload(
    asset_view: str,
    view_label: str,
    entity_types: list[str],
    relation_types: list[str],
    field_refs: list[str] | None = None,
    enum_refs: list[str] | None = None,
) -> dict:
    entity_types = list(dict.fromkeys([item for item in (entity_types or []) if item]))
    relation_types = list(dict.fromkeys([item for item in (relation_types or []) if item]))
    field_refs = list(dict.fromkeys([item for item in (field_refs or []) if item]))
    enum_refs = list(dict.fromkeys([item for item in (enum_refs or []) if item]))
    return {
        "asset_view": asset_view,
        "view_label": view_label,
        "entity_types": entity_types,
        "relation_types": relation_types,
        "field_refs": field_refs,
        "enum_refs": enum_refs,
        "structure_text": "；".join(filter(None, [
            f"实体：{' / '.join(entity_types)}" if entity_types else "",
            f"关系：{' / '.join(relation_types)}" if relation_types else "",
            f"字段：{' / '.join(field_refs)}" if field_refs else "",
        ])),
    }


def _retrieval_subject_identifier(subject: dict, index: int) -> str:
    return str(subject.get("stable_id") or subject.get("id") or f"subject_{index}")


def _retrieval_subject_role_text(subject: dict) -> str:
    role_lines = []
    for role in subject.get("roles") or []:
        role_name = str(role.get("role_name") or role.get("role_code") or "").strip()
        case_number = str(role.get("case_number") or "").strip()
        if role_name and case_number:
            role_lines.append(f"{role_name}（{case_number}）")
        elif role_name:
            role_lines.append(role_name)
    return "；".join(role_lines)


def _retrieval_is_party_subject(subject: dict) -> bool:
    roles = subject.get("roles") or []
    role_codes = {str(item.get("role_code") or "").strip() for item in roles}
    role_names = " ".join([str(item.get("role_name") or "") for item in roles])
    name = str(subject.get("name") or "").strip()
    if "prosecutor" in role_codes:
        return False
    if any(flag in role_names for flag in ["公诉机关", "检察院", "检察机关", "抗诉机关"]):
        return False
    if "检察院" in name or "检察机关" in name:
        return False
    return True


def _retrieval_result_type_label(value: str | None) -> str:
    raw = str(value or "").strip()
    return RETRIEVAL_RESULT_TYPE_LABELS.get(raw, raw)


def _retrieval_bundle_id(row_id: str, version_id: str) -> str:
    return f"rb_{_retrieval_slug(row_id)}_{_retrieval_slug(version_id)}"


def _retrieval_entry_id(bundle_id: str, entry_type: str, signature_payload) -> str:
    digest = hashlib.sha1(_stable_dump(signature_payload).encode("utf-8")).hexdigest()[:10]
    return f"{bundle_id}_{entry_type}_{digest}"


def _retrieval_keywords(*groups) -> list:
    seen = set()
    result = []
    for group in groups:
        values = group if isinstance(group, list) else [group]
        for value in values:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
    return result


def _retrieval_provision_ref(provision: dict | None, *, include_content: bool = False, content_limit: int = 48) -> str:
    provision = provision or {}
    statute = str(provision.get("statute") or provision.get("law_name") or "").strip()
    article = str(provision.get("article") or "").strip()
    paragraph = str(provision.get("paragraph") or "").strip()
    item_no = str(provision.get("item") or "").strip()
    base = ""
    if statute and article:
        base = f"《{statute}》第{article}条"
    elif article:
        base = f"第{article}条"
    elif statute:
        base = statute
    if paragraph and base:
        base += f"第{paragraph}款"
    if item_no and base:
        base += f"第{item_no}项"
    if not base:
        base = str(provision.get("content") or "").strip()
    if include_content:
        content = _retrieval_short_text(provision.get("content"), content_limit)
        if content and content != base:
            return f"{base}：{content}" if base else content
    return base


def _retrieval_provision_refs(provisions: list[dict], limit: int | None = None) -> list[str]:
    refs = []
    for item in provisions or []:
        ref = _retrieval_provision_ref(item)
        if ref and ref not in refs:
            refs.append(ref)
        if limit and len(refs) >= limit:
            break
    return refs


def _retrieval_primary_entity(entity_type: str, label: str, entity_id: str | None = None) -> dict:
    return {
        "entity_type": str(entity_type or ""),
        "entity_id": str(entity_id or ""),
        "label": str(label or "").strip(),
    }


def _retrieval_mock_embedding(text: str, dim: int = RETRIEVAL_EMBED_DIM) -> list:
    digest = hashlib.sha256((text or "").encode("utf-8")).digest()
    values = []
    for idx in range(dim):
        byte = digest[idx % len(digest)]
        values.append(round((byte / 255.0) * 2 - 1, 6))
    return values


def _retrieval_request_embeddings(texts: list[str]) -> tuple[list[list], dict]:
    cleaned_texts = [str(text or "").strip() for text in texts]
    payload = {
        "input": cleaned_texts if len(cleaned_texts) > 1 else (cleaned_texts[0] if cleaned_texts else ""),
        "model": RETRIEVAL_EMBED_MODEL,
    }
    req = urllib.request.Request(
        RETRIEVAL_EMBED_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=RETRIEVAL_EMBED_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(str(exc)) from exc

    data = body.get("data")
    if isinstance(data, list) and data:
        embeddings = []
        for item in sorted(data, key=lambda x: x.get("index", 0)):
            vector = item.get("embedding")
            if not isinstance(vector, list):
                raise RuntimeError("invalid_embedding_response")
            embeddings.append(vector)
        return embeddings, {
            "provider": RETRIEVAL_EMBED_URL,
            "model": body.get("model") or RETRIEVAL_EMBED_MODEL,
            "source": "remote",
        }

    vector = body.get("embedding")
    if isinstance(vector, list):
        return [vector], {
            "provider": RETRIEVAL_EMBED_URL,
            "model": body.get("model") or RETRIEVAL_EMBED_MODEL,
            "source": "remote",
        }
    raise RuntimeError("invalid_embedding_response")


def _retrieval_write_dir(row_id: str, version_id: str) -> Path:
    return RUNTIME_RETRIEVAL_ROOT / _retrieval_slug(row_id) / _retrieval_slug(version_id)


def _build_retrieval_entry(
    bundle_id: str,
    row_id: str,
    version_id: str,
    case_name: str,
    output: dict,
    *,
    entry_type: str,
    scene_tags: list,
    signature_payload,
    title: str,
    summary: str,
    retrieval_text: str,
    expanded_text: str,
    source_refs: dict,
    ontology_payload: dict,
    exact_payload: dict,
    graph_payload: dict | None = None,
    keywords: list | None = None,
    priority: float = 0.5,
    notes: str = "",
    meta_header: dict | None = None,
    view_label: str = "",
    primary_entity: dict | None = None,
) -> dict:
    entry_id = _retrieval_entry_id(bundle_id, entry_type, signature_payload)
    case_taxonomy = _retrieval_case_taxonomy(output)
    vector_payload = {
        "summary_text": summary,
        "retrieval_text": retrieval_text,
        "expanded_text": expanded_text,
        "metadata": {
            "row_id": row_id,
            "version_id": version_id,
            "entry_type": entry_type,
            "case_type": case_taxonomy.get("case_type") or "",
            "reason_level1": case_taxonomy.get("reason_level1") or "",
            "reason_level2": case_taxonomy.get("reason_level2") or "",
            "reason_level3": case_taxonomy.get("reason_level3") or "",
            "view_label": view_label or entry_type,
        },
        "embedding": None,
        "embedding_meta": {
            "provider": RETRIEVAL_EMBED_URL,
            "model": RETRIEVAL_EMBED_MODEL,
            "source": "pending",
            "dimension": 0,
            "error": None,
        },
    }
    return {
        "entry_id": entry_id,
        "entry_type": entry_type,
        "asset_view": entry_type,
        "view_label": view_label or entry_type,
        "primary_entity": primary_entity or {},
        "scene_tags": scene_tags,
        "priority": priority,
        "title": title,
        "summary": summary,
        "retrieval_text": retrieval_text,
        "expanded_text": expanded_text,
        "keywords": keywords or [],
        "language": "zh-CN",
        "meta_header": meta_header or {},
        "source_refs": {
            **(source_refs or {}),
            "version_id": version_id,
        },
        "ontology_payload": ontology_payload or {},
        "exact_payload": {
            "row_id": row_id,
            "case_name": case_name,
            **case_taxonomy,
            "case_reason": _retrieval_case_reason(output),
            **(exact_payload or {}),
        },
        "graph_payload": graph_payload or {},
        "vector_payload": vector_payload,
        "edit_state": {
            "source_mode": "generated",
            "dirty": False,
            "dirty_fields": [],
            "embedding_status": "pending",
            "last_embedded_at": None,
            "last_edited_at": None,
            "editor": None,
        },
        "write_state": {
            "confirmed": False,
            "written": False,
            "last_written_at": None,
        },
        "notes": notes,
    }


def _build_retrieval_bundle(row_id: str, version_id: str, output: dict, *, case_name: str = "", source_enhancement_run_id: str | None = None) -> dict:
    normalized_output = _normalize_output_snapshot(output)
    case_name = case_name or extract_case_name(normalized_output) or "未命名案件"
    bundle_id = _retrieval_bundle_id(row_id or "manual_case", version_id or "v0")
    case_meta = _extract_case_meta_from_output(normalized_output, "retrieval")
    entries = []

    facts = normalized_output.get("facts") or []
    focuses = normalized_output.get("dispute_focuses") or []
    judgments = normalized_output.get("judgment_results") or []
    provisions = normalized_output.get("legal_provisions") or []
    provision_elements = normalized_output.get("legal_provision_elements") or []
    subjects = normalized_output.get("legal_subjects") or []
    evidence_items = normalized_output.get("evidence") or []
    relations = [*(normalized_output.get("relations") or []), *(normalized_output.get("derived_relations") or [])]

    facts_by_id = {str((item.get("id") or f"fact_{idx}")): item for idx, item in enumerate(facts)}
    focuses_by_id = {str((item.get("id") or f"focus_{idx}")): item for idx, item in enumerate(focuses)}
    judgments_by_id = {str((item.get("id") or f"jr_{idx}")): item for idx, item in enumerate(judgments)}
    provisions_by_id = {str((item.get("id") or f"prov_{idx}")): item for idx, item in enumerate(provisions)}
    provision_elements_by_id = {str((item.get("id") or f"prov_elem_{idx}")): item for idx, item in enumerate(provision_elements)}
    evidence_by_id = {str((item.get("id") or f"evid_{idx}")): item for idx, item in enumerate(evidence_items)}

    def relation_src(rel):
        return str(rel.get("source_id") or rel.get("source") or "")

    def relation_tgt(rel):
        return str(rel.get("target_id") or rel.get("target") or "")

    def relation_matches(*, source_id=None, target_id=None, relation_types=None):
        for rel in relations:
            if source_id is not None and relation_src(rel) != str(source_id):
                continue
            if target_id is not None and relation_tgt(rel) != str(target_id):
                continue
            if relation_types and rel.get("relation_type") not in set(relation_types):
                continue
            return rel
        return None

    def relation_matches_all(*, source_id=None, target_id=None, relation_types=None):
        relation_type_set = set(relation_types or [])
        matched = []
        for rel in relations:
            if source_id is not None and relation_src(rel) != str(source_id):
                continue
            if target_id is not None and relation_tgt(rel) != str(target_id):
                continue
            if relation_type_set and rel.get("relation_type") not in relation_type_set:
                continue
            matched.append(rel)
        return matched

    def subject_in_judgment(subject_name: str, judgment: dict | None) -> bool:
        searchable = " ".join([
            str((judgment or {}).get("specific_judgment") or ""),
            str((judgment or {}).get("reasoning") or ""),
        ])
        return bool(subject_name and searchable and subject_name in searchable)

    def _case_set(value):
        if isinstance(value, str):
            text = value.strip()
            return {text} if text else set()
        if isinstance(value, list):
            result = set()
            for item in value:
                result.update(_case_set(item))
            return result
        return set()

    def _entity_case_set(item: dict | None):
        return _case_set((item or {}).get("case_number") or (item or {}).get("related_case_number") or "")

    def _subject_case_set(subject: dict | None):
        values = set()
        for role in (subject or {}).get("roles") or []:
            case_number = str(role.get("case_number") or "").strip()
            if case_number:
                values.add(case_number)
        return values

    def _cases_compatible(left, right):
        left = set(left or [])
        right = set(right or [])
        if not left or not right:
            return True
        return bool(left & right)

    def _first_focus_for_fact(fact: dict | None):
        if not fact:
            return None, None
        fact_id = str((fact or {}).get("id") or "")
        fact_cases = _entity_case_set(fact)
        rel = next((rel for rel in relations if relation_src(rel) == fact_id and relation_tgt(rel) in focuses_by_id and rel.get("relation_type") in {"has_dispute_focus", "relates_to_focus", "leads_to"}), None)
        if rel:
            return focuses_by_id.get(relation_tgt(rel)), rel
        candidate = next((focus for focus in focuses if _cases_compatible(fact_cases, _entity_case_set(focus))), None)
        return candidate, None

    def _first_judgment_for_focus(focus: dict | None):
        if not focus:
            return None, None
        focus_id = str((focus or {}).get("id") or "")
        focus_cases = _entity_case_set(focus)
        rel = next((rel for rel in relations if relation_src(rel) == focus_id and relation_tgt(rel) in judgments_by_id and rel.get("relation_type") in {"leads_to", "resolved_by"}), None)
        if rel:
            return judgments_by_id.get(relation_tgt(rel)), rel
        candidate = next((judgment for judgment in judgments if _cases_compatible(focus_cases, _entity_case_set(judgment))), None)
        return candidate, None

    def _first_provision_for_judgment(judgment: dict | None):
        if not judgment:
            return None, None
        judgment_id = str((judgment or {}).get("id") or "")
        judgment_cases = _entity_case_set(judgment)
        rel = next((rel for rel in relations if relation_src(rel) == judgment_id and relation_tgt(rel) in provisions_by_id and rel.get("relation_type") == "judgment_cites"), None)
        if rel:
            return provisions_by_id.get(relation_tgt(rel)), rel
        candidate = next((provision for provision in provisions if _cases_compatible(judgment_cases, _entity_case_set(provision))), None)
        return candidate, None

    case_taxonomy = _retrieval_case_taxonomy(normalized_output, case_meta)
    fact_summaries = [_retrieval_short_text(item.get("content"), 40) for item in facts[:4] if item.get("content")]
    focus_summaries = [_retrieval_short_text(item.get("content") or item.get("focus") or item.get("issue"), 32) for item in focuses[:4] if (item.get("content") or item.get("focus") or item.get("issue"))]
    judgment_summaries = [_retrieval_short_text(item.get("specific_judgment") or _retrieval_result_type_label(item.get("result_type")), 48) for item in judgments[:4]]
    provision_summaries = _retrieval_provision_refs(provisions, limit=4)
    subject_summaries = [_retrieval_short_text(item.get("name") or "", 18) for item in subjects[:5] if item.get("name")]

    meta_header = _retrieval_meta_header(normalized_output, case_meta, "case_profile", "整案画像视角")
    case_graph = _retrieval_graph_payload(
        "case_profile",
        [
            _retrieval_chain_node("CourtCase", case_name, "court_case"),
            _retrieval_chain_node("LegalSubject", "、".join(subject_summaries[:3]) or "当事人", "subjects_group"),
            _retrieval_chain_node("Fact", "；".join(fact_summaries[:2]) or "关键事实", "facts_group"),
            _retrieval_chain_node("DisputeFocus", "；".join(focus_summaries[:2]) or "争点", "focus_group"),
            _retrieval_chain_node("JudgmentResult", "；".join(judgment_summaries[:2]) or "裁判结果", "judgment_group"),
            _retrieval_chain_node("LegalProvision", "；".join(provision_summaries[:2]) or "法条依据", "provision_group"),
        ],
        [
            _retrieval_chain_edge("has_subject", "主体区"),
            _retrieval_chain_edge("has_fact", "事实链"),
            _retrieval_chain_edge("has_focus", "争点链"),
            _retrieval_chain_edge("leads_to", "导向裁判"),
            _retrieval_chain_edge("judgment_cites", "适用法条"),
        ],
        path_label="整案总览链",
        description="从案件整体出发串联主体、事实、争点、裁判和法条。",
    )
    case_lines = [
        f"案件名称：{case_name}",
        f"主体概览：{'；'.join(subject_summaries)}" if subject_summaries else "",
        f"关键事实：{'；'.join(fact_summaries)}" if fact_summaries else "",
        f"核心争点：{'；'.join(focus_summaries)}" if focus_summaries else "",
        f"裁判结果：{'；'.join(judgment_summaries)}" if judgment_summaries else "",
        f"涉及法条：{'；'.join(provision_summaries)}" if provision_summaries else "",
    ]
    entries.append(_build_retrieval_entry(
        bundle_id, row_id, version_id, case_name, normalized_output,
        entry_type="case_profile",
        scene_tags=["case_overview"],
        signature_payload={"type": "case_profile", "row_id": row_id, "version_id": version_id},
        title=f"{case_name}｜整案画像",
        summary="从整案视角概括主体、事实、争点、裁判结果与法条依据。",
        retrieval_text=_retrieval_compose_text("整案画像视角", meta_header, case_graph, case_lines),
        expanded_text=_retrieval_compose_text("整案画像视角", meta_header, case_graph, case_lines + [f"本体结构：{case_graph.get('path_label')}"]),
        source_refs={"json_paths": ["$"], "entity_ids": [], "stable_ids": []},
        ontology_payload=_retrieval_ontology_payload("case_profile", "整案画像视角", ["CourtCase", "LegalSubject", "Fact", "DisputeFocus", "JudgmentResult", "LegalProvision"], ["has_subject", "has_fact", "has_focus", "leads_to", "judgment_cites"], ["case_type", "court_cases", "legal_subjects", "facts", "dispute_focuses", "judgment_results", "legal_provisions"]),
        exact_payload={"entity_types": case_graph.get("entity_types"), "relation_types": case_graph.get("relation_types"), "result_types": [item.get("result_type") for item in judgments if item.get("result_type")], "law_names": [item.get("statute") or item.get("law_name") for item in provisions if item.get("statute") or item.get("law_name")], "provision_refs": _retrieval_provision_refs(provisions), "scene_tags": ["case_overview"], **case_taxonomy},
        graph_payload=case_graph,
        keywords=_retrieval_keywords(case_name, subject_summaries, fact_summaries, focus_summaries, provision_summaries),
        priority=0.95,
        meta_header=meta_header,
        view_label="整案画像视角",
        primary_entity=_retrieval_primary_entity("CourtCase", case_name, "court_case"),
    ))

    for idx, fact in enumerate(facts):
        content = str(fact.get("content") or "").strip()
        if not content:
            continue
        fact_id = str(fact.get("id") or f"fact_{idx}")
        evidence_rel = relation_matches(target_id=fact_id, relation_types={"proves_fact"})
        focus_item, focus_rel = _first_focus_for_fact(fact)
        judgment_item, judgment_rel = _first_judgment_for_focus(focus_item)
        evidence_item = evidence_by_id.get(relation_src(evidence_rel)) if evidence_rel else (evidence_items[0] if evidence_items else None)
        view_label = "事实链视角"
        meta_header = _retrieval_meta_header(normalized_output, case_meta, "fact_chain_unit", view_label)
        chain_nodes = []
        chain_edges = []
        if evidence_item:
            chain_nodes.append(_retrieval_chain_node("Evidence", evidence_item.get("content") or evidence_item.get("label") or "证据", evidence_item.get("id") or ""))
            chain_edges.append(_retrieval_chain_edge("proves_fact", "证明事实", _relation_identity(evidence_rel) if evidence_rel else "", verified=bool(evidence_rel)))
        chain_nodes.append(_retrieval_chain_node("Fact", content, fact_id))
        if focus_item:
            chain_nodes.append(_retrieval_chain_node("DisputeFocus", focus_item.get("content") or focus_item.get("focus") or focus_item.get("issue") or "争点", focus_item.get("id") or ""))
            chain_edges.append(_retrieval_chain_edge((focus_rel or {}).get("relation_type") or "has_dispute_focus", "引出争点", _relation_identity(focus_rel) if focus_rel else "", verified=bool(focus_rel)))
        if judgment_item:
            chain_nodes.append(_retrieval_chain_node("JudgmentResult", judgment_item.get("specific_judgment") or _retrieval_result_type_label(judgment_item.get("result_type")) or "裁判结果", judgment_item.get("id") or ""))
            chain_edges.append(_retrieval_chain_edge((judgment_rel or {}).get("relation_type") or "leads_to", "影响裁判", _relation_identity(judgment_rel) if judgment_rel else "", verified=bool(judgment_rel)))
        graph_payload = _retrieval_graph_payload("fact_chain_unit", chain_nodes, chain_edges, path_label="证据-事实-争点链", description="从事实出发，展示其证据支撑、争点归属和裁判影响。")
        lines = [
            f"案件名称：{case_name}",
            f"事实内容：{content}",
            f"事实类型：{fact.get('fact_type') or '未标注'}",
            f"关联证据：{_retrieval_short_text((evidence_item or {}).get('content') or '', 60)}" if evidence_item else "",
            f"关联争点：{_retrieval_short_text((focus_item or {}).get('content') or (focus_item or {}).get('focus') or (focus_item or {}).get('issue') or '', 48)}" if focus_item else "",
            f"对应裁判：{_retrieval_short_text((judgment_item or {}).get('specific_judgment') or _retrieval_result_type_label((judgment_item or {}).get('result_type')), 56)}" if judgment_item else "",
        ]
        entries.append(_build_retrieval_entry(
            bundle_id, row_id, version_id, case_name, normalized_output,
            entry_type="fact_chain_unit",
            scene_tags=["fact_similarity"],
            signature_payload={"type": "fact_chain_unit", "stable_id": fact.get("stable_id") or fact_id, "content": content},
            title=_retrieval_short_text(content, 28),
            summary=f"从事实切入，查看证据支撑、争点归属和裁判影响。",
            retrieval_text=_retrieval_compose_text(view_label, meta_header, graph_payload, lines),
            expanded_text=_retrieval_compose_text(view_label, meta_header, graph_payload, lines + [f"适用法条候选：{'；'.join(provision_summaries[:3])}" if provision_summaries else ""]),
            source_refs={"json_paths": [f"$.facts[{idx}]"], "entity_ids": [fact_id], "stable_ids": [fact.get("stable_id") or ""]},
            ontology_payload=_retrieval_ontology_payload("fact_chain_unit", view_label, graph_payload.get("entity_types"), graph_payload.get("relation_types"), ["Fact.content", "Fact.fact_type", "Evidence.content", "DisputeFocus.content", "JudgmentResult.specific_judgment"]),
            exact_payload={"entity_types": graph_payload.get("entity_types"), "relation_types": graph_payload.get("relation_types"), "result_types": [judgment_item.get("result_type")] if judgment_item and judgment_item.get("result_type") else [], "law_names": [item.get("statute") or item.get("law_name") for item in provisions if item.get("statute") or item.get("law_name")], "provision_refs": _retrieval_provision_refs(provisions), "scene_tags": ["fact_similarity"], "fact_types": [fact.get("fact_type")] if fact.get("fact_type") else [], **case_taxonomy},
            graph_payload=graph_payload,
            keywords=_retrieval_keywords(fact.get("fact_type"), (focus_item or {}).get("content"), (judgment_item or {}).get("specific_judgment")),
            priority=0.84,
            meta_header=meta_header,
            view_label=view_label,
            primary_entity=_retrieval_primary_entity("Fact", content, fact_id),
        ))

    for idx, focus in enumerate(focuses):
        content = str(focus.get("content") or focus.get("focus") or focus.get("issue") or "").strip()
        if not content:
            continue
        focus_id = str(focus.get("id") or f"focus_{idx}")
        fact_rel = next((rel for rel in relations if relation_tgt(rel) == focus_id and relation_src(rel) in facts_by_id), None)
        judgment_item, judgment_rel = _first_judgment_for_focus(focus)
        fact_item = facts_by_id.get(relation_src(fact_rel)) if fact_rel else (next((item for item in facts if _cases_compatible(_entity_case_set(item), _entity_case_set(focus))), None) if facts else None)
        provision_item, provision_rel = _first_provision_for_judgment(judgment_item)
        view_label = "争点视角"
        meta_header = _retrieval_meta_header(normalized_output, case_meta, "focus_unit", view_label)
        chain_nodes = [
            _retrieval_chain_node("Fact", (fact_item or {}).get("content") or "关键事实", (fact_item or {}).get("id") or ""),
            _retrieval_chain_node("DisputeFocus", content, focus_id),
        ]
        chain_edges = [_retrieval_chain_edge((fact_rel or {}).get("relation_type") or "has_dispute_focus", "形成争点", _relation_identity(fact_rel) if fact_rel else "", verified=bool(fact_rel))]
        if judgment_item:
            chain_nodes.append(_retrieval_chain_node("JudgmentResult", judgment_item.get("specific_judgment") or _retrieval_result_type_label(judgment_item.get("result_type")) or "裁判结果", judgment_item.get("id") or ""))
            chain_edges.append(_retrieval_chain_edge((judgment_rel or {}).get("relation_type") or "leads_to", "导向裁判", _relation_identity(judgment_rel) if judgment_rel else "", verified=bool(judgment_rel)))
        if provision_item:
            chain_nodes.append(_retrieval_chain_node("LegalProvision", _retrieval_provision_ref(provision_item) or "法条", provision_item.get("id") or ""))
            chain_edges.append(_retrieval_chain_edge("judgment_cites", "适用法条", _relation_identity(provision_rel) if provision_rel else "", verified=bool(provision_rel)))
        graph_payload = _retrieval_graph_payload("focus_unit", chain_nodes, chain_edges, path_label="事实-争点-裁判链", description="从争点出发查看其事实基础、裁判结果和法条依据。")
        lines = [
            f"案件名称：{case_name}",
            f"争点内容：{content}",
            f"支撑事实：{_retrieval_short_text((fact_item or {}).get('content') or '', 64)}" if fact_item else "",
            f"对应裁判：{_retrieval_short_text((judgment_item or {}).get('specific_judgment') or _retrieval_result_type_label((judgment_item or {}).get('result_type')), 64)}" if judgment_item else "",
            f"涉及法条：{_retrieval_provision_ref(provision_item, include_content=True, content_limit=48)}" if provision_item else "",
        ]
        entries.append(_build_retrieval_entry(
            bundle_id, row_id, version_id, case_name, normalized_output,
            entry_type="focus_unit",
            scene_tags=["focus_view"],
            signature_payload={"type": "focus_unit", "stable_id": focus.get("stable_id") or focus_id, "content": content},
            title=_retrieval_short_text(content, 28),
            summary="从争点出发组织事实、裁判和法条适用。",
            retrieval_text=_retrieval_compose_text(view_label, meta_header, graph_payload, lines),
            expanded_text="",
            source_refs={"json_paths": [f"$.dispute_focuses[{idx}]"], "entity_ids": [focus_id], "stable_ids": [focus.get("stable_id") or ""]},
            ontology_payload=_retrieval_ontology_payload("focus_unit", view_label, graph_payload.get("entity_types"), graph_payload.get("relation_types"), ["DisputeFocus.content", "Fact.content", "JudgmentResult.specific_judgment", "LegalProvision.statute"]),
            exact_payload={"entity_types": graph_payload.get("entity_types"), "relation_types": graph_payload.get("relation_types"), "result_types": [judgment_item.get("result_type")] if judgment_item and judgment_item.get("result_type") else [], "law_names": [provision_item.get("statute") or provision_item.get("law_name")] if provision_item else [], "provision_refs": [_retrieval_provision_ref(provision_item)] if provision_item else [], "scene_tags": ["focus_view"], "focus_labels": [content], **case_taxonomy},
            graph_payload=graph_payload,
            keywords=_retrieval_keywords(content, (judgment_item or {}).get("result_type"), _retrieval_provision_ref(provision_item)),
            priority=0.86,
            meta_header=meta_header,
            view_label=view_label,
            primary_entity=_retrieval_primary_entity("DisputeFocus", content, focus_id),
        ))

    for idx, judgment in enumerate(judgments):
        result_type = judgment.get("result_type") or ""
        result_type_label = _retrieval_result_type_label(result_type)
        specific_judgment = str(judgment.get("specific_judgment") or "").strip()
        reasoning = str(judgment.get("reasoning") or "").strip()
        judgment_id = str(judgment.get("id") or f"jr_{idx}")
        focus_rel = next((rel for rel in relations if relation_tgt(rel) == judgment_id and relation_src(rel) in focuses_by_id), None)
        focus_item = focuses_by_id.get(relation_src(focus_rel)) if focus_rel else (next((item for item in focuses if _cases_compatible(_entity_case_set(item), _entity_case_set(judgment))), None) if focuses else None)
        provision_item, provision_rel = _first_provision_for_judgment(judgment)
        view_label = "裁判结果视角"
        meta_header = _retrieval_meta_header(normalized_output, case_meta, "judgment_unit", view_label)
        graph_payload = _retrieval_graph_payload(
            "judgment_unit",
            [
                _retrieval_chain_node("DisputeFocus", (focus_item or {}).get("content") or (focus_item or {}).get("focus") or "争点", (focus_item or {}).get("id") or ""),
                _retrieval_chain_node("JudgmentResult", specific_judgment or result_type_label or f"裁判结果_{idx}", judgment_id),
                _retrieval_chain_node("LegalProvision", _retrieval_provision_ref(provision_item) or "法条", (provision_item or {}).get("id") or ""),
            ],
            [
                _retrieval_chain_edge((focus_rel or {}).get("relation_type") or "leads_to", "争点导向", _relation_identity(focus_rel) if focus_rel else "", verified=bool(focus_rel)),
                _retrieval_chain_edge("judgment_cites", "结果依据", _relation_identity(provision_rel) if provision_rel else "", verified=bool(provision_rel)),
            ],
            path_label="争点-裁判-法条链",
            description="从单个裁判结果出发回看争点并连接法条依据。",
        )
        lines = [
            f"案件名称：{case_name}",
            f"结果类型：{result_type_label}",
            f"具体裁判：{specific_judgment}",
            f"关联争点：{_retrieval_short_text((focus_item or {}).get('content') or (focus_item or {}).get('focus') or '', 60)}" if focus_item else "",
            f"法条依据：{_retrieval_provision_ref(provision_item, include_content=True, content_limit=48)}" if provision_item else "",
        ]
        entries.append(_build_retrieval_entry(
            bundle_id, row_id, version_id, case_name, normalized_output,
            entry_type="judgment_unit",
            scene_tags=["judgment_view"],
            signature_payload={"type": "judgment_unit", "stable_id": judgment.get("stable_id") or judgment_id, "specific": specific_judgment, "result_type": result_type},
            title=_retrieval_short_text(specific_judgment or result_type_label or f"裁判结果_{idx}", 40),
            summary="从单个裁判结果切入，查看其争点来源和法条依据。",
            retrieval_text=_retrieval_compose_text(view_label, meta_header, graph_payload, lines),
            expanded_text=_retrieval_compose_text(view_label, meta_header, graph_payload, lines + [f"裁判理由：{reasoning}" if reasoning else ""]),
            source_refs={"json_paths": [f"$.judgment_results[{idx}]"], "entity_ids": [judgment_id], "stable_ids": [judgment.get("stable_id") or ""]},
            ontology_payload=_retrieval_ontology_payload("judgment_unit", view_label, graph_payload.get("entity_types"), graph_payload.get("relation_types"), ["JudgmentResult.result_type", "JudgmentResult.specific_judgment", "DisputeFocus.content", "LegalProvision.statute"], [f"JudgmentResult.result_type:{result_type}"] if result_type else []),
            exact_payload={"entity_types": graph_payload.get("entity_types"), "relation_types": graph_payload.get("relation_types"), "result_types": [result_type] if result_type else [], "law_names": [provision_item.get("statute") or provision_item.get("law_name")] if provision_item else [], "provision_refs": [_retrieval_provision_ref(provision_item)] if provision_item else [], "scene_tags": ["judgment_view"], **case_taxonomy},
            graph_payload=graph_payload,
            keywords=_retrieval_keywords(result_type_label, specific_judgment, _retrieval_provision_ref(provision_item)),
            priority=0.88,
            meta_header=meta_header,
            view_label=view_label,
            primary_entity=_retrieval_primary_entity("JudgmentResult", specific_judgment or result_type_label or f"裁判结果_{idx}", judgment_id),
        ))
        if reasoning:
            reasoning_view = "裁判说理视角"
            reasoning_meta = _retrieval_meta_header(normalized_output, case_meta, "reasoning_unit", reasoning_view)
            reasoning_graph = _retrieval_graph_payload(
                "reasoning_unit",
                [
                    _retrieval_chain_node("Fact", fact_summaries[0] if fact_summaries else "关键事实", (facts[0] or {}).get("id") if facts else ""),
                    _retrieval_chain_node("DisputeFocus", (focus_item or {}).get("content") or (focus_item or {}).get("focus") or "争点", (focus_item or {}).get("id") or ""),
                    _retrieval_chain_node("JudgmentResult", specific_judgment or result_type_label or "裁判结果", judgment_id),
                    _retrieval_chain_node("LegalProvision", _retrieval_provision_ref(provision_item) or "法条", (provision_item or {}).get("id") or ""),
                ],
                [
                    _retrieval_chain_edge("supports_reasoning", "事实前提", verified=bool(facts)),
                    _retrieval_chain_edge((focus_rel or {}).get("relation_type") or "leads_to", "争点分析", _relation_identity(focus_rel) if focus_rel else "", verified=bool(focus_rel)),
                    _retrieval_chain_edge("judgment_cites", "法条支撑", _relation_identity(provision_rel) if provision_rel else "", verified=bool(provision_rel)),
                ],
                path_label="事实-争点-说理链",
                description="从裁判理由出发，回看关键事实、争点和法条支持。",
            )
            reasoning_lines = [
                f"案件名称：{case_name}",
                f"结果类型：{result_type_label}",
                f"具体裁判：{specific_judgment}",
                f"裁判理由：{reasoning}",
                f"争点：{_retrieval_short_text((focus_item or {}).get('content') or (focus_item or {}).get('focus') or '', 60)}" if focus_item else "",
                f"法条依据：{_retrieval_provision_ref(provision_item, include_content=True, content_limit=48)}" if provision_item else "",
            ]
            entries.append(_build_retrieval_entry(
                bundle_id, row_id, version_id, case_name, normalized_output,
                entry_type="reasoning_unit",
                scene_tags=["reasoning_view"],
                signature_payload={"type": "reasoning_unit", "stable_id": judgment.get("stable_id") or judgment_id, "reasoning": reasoning},
                title=f"裁判说理｜{_retrieval_short_text(specific_judgment or result_type_label, 24)}",
                summary="从裁判说理切入，展示事实前提、争点判断和法条支持。",
                retrieval_text=_retrieval_compose_text(reasoning_view, reasoning_meta, reasoning_graph, reasoning_lines),
                expanded_text="",
                source_refs={"json_paths": [f"$.judgment_results[{idx}]"], "entity_ids": [judgment_id], "stable_ids": [judgment.get("stable_id") or ""]},
                ontology_payload=_retrieval_ontology_payload("reasoning_unit", reasoning_view, reasoning_graph.get("entity_types"), reasoning_graph.get("relation_types"), ["JudgmentResult.reasoning", "DisputeFocus.content", "Fact.content", "LegalProvision.statute"], [f"JudgmentResult.result_type:{result_type}"] if result_type else []),
                exact_payload={"entity_types": reasoning_graph.get("entity_types"), "relation_types": reasoning_graph.get("relation_types"), "result_types": [result_type] if result_type else [], "law_names": [provision_item.get("statute") or provision_item.get("law_name")] if provision_item else [], "provision_refs": [_retrieval_provision_ref(provision_item)] if provision_item else [], "scene_tags": ["reasoning_view"], **case_taxonomy},
                graph_payload=reasoning_graph,
                keywords=_retrieval_keywords(result_type_label, reasoning, (focus_item or {}).get("content")),
                priority=0.9,
                meta_header=reasoning_meta,
                view_label=reasoning_view,
                primary_entity=_retrieval_primary_entity("JudgmentResult", specific_judgment or result_type_label or "裁判结果", judgment_id),
            ))

    for idx, judgment in enumerate(judgments[: max(1, len(judgments)) ]):
        result_type_label = _retrieval_result_type_label(judgment.get("result_type"))
        specific_judgment = judgment.get("specific_judgment") or ""
        provision_item, provision_rel = _first_provision_for_judgment(judgment)
        if not provision_item:
            continue
        provision_index = provision_item.get("index") if isinstance(provision_item, dict) else None
        if provision_index is None and isinstance(provision_item, dict):
            provision_index = provision_item.get("provision_index")
        if provision_index is None and provision_item in provisions:
            provision_index = provisions.index(provision_item)
        provision_element_item = next((item for item in provision_elements if item.get("provision_index") == provision_index), None) or (provision_elements[0] if provision_elements else None)
        fact_item = facts[0] if facts else None
        view_label = "法条适用视角"
        meta_header = _retrieval_meta_header(normalized_output, case_meta, "judgment_provision_chain", view_label)
        chain_nodes = []
        chain_edges = []
        if fact_item:
            chain_nodes.append(_retrieval_chain_node("Fact", fact_item.get("content") or "关键事实", fact_item.get("id") or ""))
            if provision_element_item:
                chain_edges.append(_retrieval_chain_edge("matches_element", "命中法条要件", verified=bool(provision_element_item)))
        if provision_element_item:
            chain_nodes.append(_retrieval_chain_node("LegalProvisionElement", provision_element_item.get("content") or provision_element_item.get("applicable_fact_pattern") or "法条要件", provision_element_item.get("id") or ""))
            chain_edges.append(_retrieval_chain_edge("element_of_provision", "属于法条", verified=True))
        chain_nodes.append(_retrieval_chain_node("LegalProvision", _retrieval_provision_ref(provision_item) or "法条", provision_item.get("id") or ""))
        chain_nodes.append(_retrieval_chain_node("JudgmentResult", specific_judgment or result_type_label or "裁判结果", judgment.get("id") or ""))
        chain_edges.append(_retrieval_chain_edge("judgment_cites", "裁判适用", _relation_identity(provision_rel) if provision_rel else "", verified=bool(provision_rel)))
        graph_payload = _retrieval_graph_payload("judgment_provision_chain", chain_nodes, chain_edges, path_label="事实-法条要件-法条-裁判链", description="从法条适用链路观察事实如何命中法条要件并导向裁判。")
        lines = [
            f"案件名称：{case_name}",
            f"关键事实：{_retrieval_short_text((fact_item or {}).get('content') or '', 64)}" if fact_item else "",
            f"法条要件：{_retrieval_short_text((provision_element_item or {}).get('content') or (provision_element_item or {}).get('applicable_fact_pattern') or '', 64)}" if provision_element_item else "",
            f"法条依据：{_retrieval_provision_ref(provision_item, include_content=True, content_limit=48)}",
            f"对应裁判：{_retrieval_short_text(specific_judgment or result_type_label, 64)}",
        ]
        entries.append(_build_retrieval_entry(
            bundle_id, row_id, version_id, case_name, normalized_output,
            entry_type="judgment_provision_chain",
            scene_tags=["law_application"],
            signature_payload={"type": "judgment_provision_chain", "judgment_id": judgment.get("stable_id") or judgment.get("id") or idx, "law": provision_item.get("statute") or provision_item.get("law_name")},
            title=f"法条适用链｜{_retrieval_short_text(_retrieval_provision_ref(provision_item) or provision_item.get('content') or '', 24)}",
            summary="从法条适用链路切入，展示事实、法条要件与裁判结果。",
            retrieval_text=_retrieval_compose_text(view_label, meta_header, graph_payload, lines),
            expanded_text=_retrieval_compose_text(view_label, meta_header, graph_payload, lines + [f"裁判理由：{judgment.get('reasoning') or ''}" if judgment.get("reasoning") else ""]),
            source_refs={"json_paths": [f"$.judgment_results[{idx}]"], "entity_ids": [judgment.get("id") or f"jr_{idx}", provision_item.get("id") or ""], "stable_ids": [judgment.get("stable_id") or "", (provision_element_item or {}).get("stable_id") or ""]},
            ontology_payload=_retrieval_ontology_payload("judgment_provision_chain", view_label, graph_payload.get("entity_types"), graph_payload.get("relation_types"), ["Fact.content", "LegalProvisionElement.content", "LegalProvision.statute", "JudgmentResult.specific_judgment"], [f"JudgmentResult.result_type:{judgment.get('result_type')}" ] if judgment.get("result_type") else []),
            exact_payload={"entity_types": graph_payload.get("entity_types"), "relation_types": graph_payload.get("relation_types"), "result_types": [judgment.get("result_type")] if judgment.get("result_type") else [], "law_names": [provision_item.get("statute") or provision_item.get("law_name")], "provision_refs": [_retrieval_provision_ref(provision_item)], "scene_tags": ["law_application"], **case_taxonomy},
            graph_payload=graph_payload,
            keywords=_retrieval_keywords(result_type_label, _retrieval_provision_ref(provision_item), (provision_element_item or {}).get("applicable_fact_pattern")),
            priority=0.9,
            meta_header=meta_header,
            view_label=view_label,
            primary_entity=_retrieval_primary_entity("LegalProvision", _retrieval_provision_ref(provision_item), provision_item.get("id") or ""),
        ))

    for idx, subject in enumerate(subjects):
        subject_name = str(subject.get("name") or "").strip()
        if not subject_name:
            continue
        if not _retrieval_is_party_subject(subject):
            continue
        role_text = _retrieval_subject_role_text(subject)
        subject_id = _retrieval_subject_identifier(subject, idx)
        subject_fact_rel = next((rel for rel in relation_matches_all(source_id=subject_id, relation_types={"relates_to_fact"}) if relation_tgt(rel) in facts_by_id), None)
        fact_item = facts_by_id.get(relation_tgt(subject_fact_rel)) if subject_fact_rel else None
        subject_fact_verified = bool(subject_fact_rel)

        subject_focus_rel = next((rel for rel in relation_matches_all(source_id=subject_id, relation_types={"concerns_focus"}) if relation_tgt(rel) in focuses_by_id), None)
        fact_focus_rel = next((rel for rel in relation_matches_all(source_id=(fact_item or {}).get("id"), relation_types={"has_dispute_focus", "relates_to_focus"}) if relation_tgt(rel) in focuses_by_id), None) if fact_item else None
        focus_item = focuses_by_id.get(relation_tgt(subject_focus_rel)) if subject_focus_rel else None
        if not focus_item and fact_focus_rel:
            focus_item = focuses_by_id.get(relation_tgt(fact_focus_rel))

        subject_judgment_rel = next((rel for rel in relation_matches_all(source_id=subject_id, relation_types={"receives_judgment"}) if relation_tgt(rel) in judgments_by_id), None)
        focus_judgment_rel = next((rel for rel in relation_matches_all(source_id=(focus_item or {}).get("id"), relation_types={"leads_to", "resolved_by"}) if relation_tgt(rel) in judgments_by_id), None) if focus_item else None
        judgment_item = judgments_by_id.get(relation_tgt(subject_judgment_rel)) if subject_judgment_rel else None
        if not judgment_item and focus_judgment_rel:
            judgment_item = judgments_by_id.get(relation_tgt(focus_judgment_rel))

        subject_judgment_verified = bool(subject_judgment_rel) or bool(focus_judgment_rel and (subject_focus_rel or subject_fact_rel))
        if judgment_item and not subject_in_judgment(subject_name, judgment_item) and not subject_judgment_rel:
            judgment_item = None
            focus_judgment_rel = None
            subject_judgment_verified = False

        judgment_provision_rel = next((rel for rel in relation_matches_all(source_id=(judgment_item or {}).get("id"), relation_types={"judgment_cites"}) if relation_tgt(rel) in provisions_by_id), None) if judgment_item else None
        provision_item = provisions_by_id.get(relation_tgt(judgment_provision_rel)) if judgment_provision_rel else None
        view_label = "当事人视角"
        meta_header = _retrieval_meta_header(normalized_output, case_meta, "party_view_unit", view_label)
        chain_nodes = [_retrieval_chain_node("LegalSubject", subject_name, subject_id)]
        chain_edges = []
        if fact_item:
            chain_nodes.append(_retrieval_chain_node("Fact", (fact_item or {}).get("content") or "关联事实", (fact_item or {}).get("id") or ""))
            chain_edges.append(_retrieval_chain_edge((subject_fact_rel or {}).get("relation_type") or "relates_to_fact", "关联事实", _relation_identity(subject_fact_rel) if subject_fact_rel else "", verified=bool(subject_fact_rel)))
        if focus_item:
            chain_nodes.append(_retrieval_chain_node("DisputeFocus", (focus_item or {}).get("content") or (focus_item or {}).get("focus") or "关联争点", (focus_item or {}).get("id") or ""))
            if fact_item:
                chain_edges.append(_retrieval_chain_edge((fact_focus_rel or {}).get("relation_type") or "relates_to_focus", "触发争点", _relation_identity(fact_focus_rel) if fact_focus_rel else "", verified=bool(fact_focus_rel)))
            else:
                chain_edges.append(_retrieval_chain_edge((subject_focus_rel or {}).get("relation_type") or "concerns_focus", "关联争点", _relation_identity(subject_focus_rel) if subject_focus_rel else "", verified=bool(subject_focus_rel)))
        if judgment_item:
            chain_nodes.append(_retrieval_chain_node("JudgmentResult", (judgment_item or {}).get("specific_judgment") or _retrieval_result_type_label((judgment_item or {}).get("result_type")) or "裁判结果", (judgment_item or {}).get("id") or ""))
            if focus_item:
                chain_edges.append(_retrieval_chain_edge((focus_judgment_rel or {}).get("relation_type") or "leads_to", "对应裁判", _relation_identity(focus_judgment_rel) if focus_judgment_rel else "", verified=bool(focus_judgment_rel and subject_judgment_verified)))
            else:
                chain_edges.append(_retrieval_chain_edge((subject_judgment_rel or {}).get("relation_type") or "receives_judgment", "对应裁判", _relation_identity(subject_judgment_rel) if subject_judgment_rel else "", verified=bool(subject_judgment_rel)))
        if provision_item:
            chain_nodes.append(_retrieval_chain_node("LegalProvision", _retrieval_provision_ref(provision_item) or "法条", (provision_item or {}).get("id") or ""))
            chain_edges.append(_retrieval_chain_edge("judgment_cites", "对应法条", _relation_identity(judgment_provision_rel) if judgment_provision_rel else "", verified=bool(judgment_provision_rel)))
        graph_payload = _retrieval_graph_payload(
            "party_view_unit",
            chain_nodes,
            chain_edges,
            path_label="当事人-事实-争点-裁判链",
            description="围绕单个当事人组织其相关事实、争点、裁判结果和法条依据。",
        )
        lines = [
            f"案件名称：{case_name}",
            f"当事人：{subject_name}",
            f"主体类型：{subject.get('subject_type') or '未标注'}",
            f"角色：{role_text or '未标注'}",
            f"相关事实：{_retrieval_short_text((fact_item or {}).get('content') or '', 64)}" if fact_item else "",
            f"相关争点：{_retrieval_short_text((focus_item or {}).get('content') or (focus_item or {}).get('focus') or '', 64)}" if focus_item else "",
            f"对应裁判：{_retrieval_short_text((judgment_item or {}).get('specific_judgment') or _retrieval_result_type_label((judgment_item or {}).get('result_type')), 64)}" if judgment_item else "",
            f"对应法条：{_retrieval_provision_ref(provision_item, include_content=True, content_limit=48)}" if provision_item else "",
        ]
        entries.append(_build_retrieval_entry(
            bundle_id, row_id, version_id, case_name, normalized_output,
            entry_type="party_view_unit",
            scene_tags=["party_view"],
            signature_payload={"type": "party_view_unit", "subject": subject_name, "roles": role_text},
            title=f"当事人视角｜{subject_name}",
            summary="围绕单个当事人查看其角色、相关事实、争点与裁判结果。",
            retrieval_text=_retrieval_compose_text(view_label, meta_header, graph_payload, lines),
            expanded_text="",
            source_refs={"json_paths": [f"$.legal_subjects[{idx}]"], "entity_ids": [subject_id], "stable_ids": [subject.get("stable_id") or ""]},
            ontology_payload=_retrieval_ontology_payload("party_view_unit", view_label, graph_payload.get("entity_types"), graph_payload.get("relation_types"), ["LegalSubject.roles", "LegalSubject.subject_type", "Fact.content", "DisputeFocus.content", "JudgmentResult.specific_judgment"]),
            exact_payload={"entity_types": graph_payload.get("entity_types"), "relation_types": graph_payload.get("relation_types"), "result_types": [judgment_item.get("result_type")] if judgment_item and judgment_item.get("result_type") else [], "law_names": [provision_item.get("statute") or provision_item.get("law_name")] if provision_item else [], "provision_refs": [_retrieval_provision_ref(provision_item)] if provision_item else [], "scene_tags": ["party_view"], "subject_roles": [role.get("role_name") or role.get("role_code") for role in subject.get("roles") or []], **case_taxonomy},
            graph_payload=graph_payload,
            keywords=_retrieval_keywords(subject_name, role_text, (judgment_item or {}).get("result_type")),
            priority=0.92,
            meta_header=meta_header,
            view_label=view_label,
            primary_entity=_retrieval_primary_entity("LegalSubject", subject_name, subject_id),
        ))

    bundle = {
        "bundle_id": bundle_id,
        "row_id": row_id,
        "case_name": case_name,
        "source_parse_version_id": version_id,
        "source_enhancement_run_id": source_enhancement_run_id,
        "bundle_schema_version": "retrieval_bundle_v2",
        "generator_version": "retrieval_builder_v2",
        "generated_at": _utc_now_iso(),
        "updated_at": _utc_now_iso(),
        "status": {
            "draft": True,
            "has_manual_edits": False,
            "has_stale_embeddings": True,
            "write_status": "pending",
        },
        "meta": {
            **case_meta,
            "case_taxonomy": case_taxonomy,
            "available_asset_views": sorted(list({item.get("entry_type") for item in entries if item.get("entry_type")})),
        },
        "entries": entries,
    }
    return _refresh_retrieval_bundle_stats(bundle)


def _refresh_retrieval_bundle_stats(bundle: dict) -> dict:
    entries = bundle.get("entries") or []
    edited_count = sum(1 for item in entries if ((item.get("edit_state") or {}).get("dirty")))
    stale_count = sum(1 for item in entries if (item.get("edit_state") or {}).get("embedding_status") in {"pending", "stale", "failed"})
    ready_count = sum(1 for item in entries if (item.get("edit_state") or {}).get("embedding_status") == "ready")
    written_count = sum(1 for item in entries if (item.get("write_state") or {}).get("written"))
    remote_count = sum(1 for item in entries if ((item.get("vector_payload") or {}).get("embedding_meta") or {}).get("source") == "remote")
    fallback_count = sum(1 for item in entries if ((item.get("vector_payload") or {}).get("embedding_meta") or {}).get("source") == "mock_fallback")
    bundle["updated_at"] = _utc_now_iso()
    bundle["status"] = {
        "draft": True,
        "has_manual_edits": edited_count > 0,
        "has_stale_embeddings": stale_count > 0,
        "write_status": "written" if entries and written_count == len(entries) else ("partial" if written_count else "pending"),
    }
    bundle["stats"] = {
        "entry_total": len(entries),
        "entry_generated": len(entries),
        "entry_edited": edited_count,
        "exact_doc_total": len(entries),
        "vector_doc_total": len(entries),
        "graph_doc_total": sum(1 for item in entries if item.get("graph_payload")),
        "ready_embedding_total": ready_count,
        "stale_embedding_total": stale_count,
        "remote_embedding_total": remote_count,
        "fallback_embedding_total": fallback_count,
        "written_total": written_count,
    }
    return bundle


def _update_retrieval_entry(bundle: dict, entry_id: str, patch: dict) -> tuple[dict, dict]:
    entries = bundle.get("entries") or []
    for entry in entries:
        if entry.get("entry_id") != entry_id:
            continue
        sanitized = {key: value for key, value in (patch or {}).items() if key in RETRIEVAL_EDITABLE_FIELDS}
        if not sanitized:
            raise ValueError("invalid_patch")
        dirty_fields = set((entry.get("edit_state") or {}).get("dirty_fields") or [])
        for key, value in sanitized.items():
            entry[key] = value
            dirty_fields.add(key)
            if key == "summary":
                entry.setdefault("vector_payload", {})["summary_text"] = value
            elif key == "retrieval_text":
                entry.setdefault("vector_payload", {})["retrieval_text"] = value
            elif key == "expanded_text":
                entry.setdefault("vector_payload", {})["expanded_text"] = value
        edit_state = entry.setdefault("edit_state", {})
        edit_state["source_mode"] = "edited"
        edit_state["dirty"] = True
        edit_state["dirty_fields"] = sorted(dirty_fields)
        edit_state["last_edited_at"] = _utc_now_iso()
        if dirty_fields & RETRIEVAL_TEXT_FIELDS:
            edit_state["embedding_status"] = "stale"
        return _refresh_retrieval_bundle_stats(bundle), entry
    raise ValueError("entry_not_found")


def _reembed_retrieval_entries(bundle: dict, entry_ids: list | None = None) -> dict:
    target_ids = set(entry_ids or [])
    target_entries = []
    for entry in bundle.get("entries") or []:
        if target_ids and entry.get("entry_id") not in target_ids:
            continue
        edit_state = entry.setdefault("edit_state", {})
        if target_ids or edit_state.get("embedding_status") in {"pending", "stale", "failed"}:
            target_entries.append(entry)
    updated = bool(target_entries)
    if target_entries:
        texts = [
            (entry.setdefault("vector_payload", {}).get("retrieval_text") or entry.get("retrieval_text") or "")
            for entry in target_entries
        ]
        remote_error = None
        remote_vectors = None
        remote_meta = None
        try:
            remote_vectors, remote_meta = _retrieval_request_embeddings(texts)
            if len(remote_vectors) != len(target_entries):
                raise RuntimeError("embedding_count_mismatch")
        except Exception as exc:
            remote_error = str(exc)
        for idx, entry in enumerate(target_entries):
            vector_payload = entry.setdefault("vector_payload", {})
            edit_state = entry.setdefault("edit_state", {})
            if remote_vectors:
                vector = remote_vectors[idx]
                vector_payload["embedding"] = vector
                vector_payload["embedding_meta"] = {
                    "provider": remote_meta.get("provider"),
                    "model": remote_meta.get("model"),
                    "source": remote_meta.get("source"),
                    "dimension": len(vector or []),
                    "error": None,
                }
            else:
                fallback_vector = _retrieval_mock_embedding(texts[idx])
                vector_payload["embedding"] = fallback_vector
                vector_payload["embedding_meta"] = {
                    "provider": RETRIEVAL_EMBED_URL,
                    "model": RETRIEVAL_EMBED_MODEL,
                    "source": "mock_fallback",
                    "dimension": len(fallback_vector or []),
                    "error": remote_error,
                }
            edit_state["embedding_status"] = "ready"
            edit_state["last_embedded_at"] = _utc_now_iso()
    if not updated and target_ids:
        raise ValueError("entry_not_found")
    return _refresh_retrieval_bundle_stats(bundle)


def _project_exact_doc(entry: dict, bundle: dict) -> dict:
    payload = entry.get("exact_payload") or {}
    return {
        "doc_id": f"exact_{entry.get('entry_id')}",
        "entry_id": entry.get("entry_id"),
        "row_id": bundle.get("row_id"),
        "case_name": bundle.get("case_name"),
        **payload,
        "scene_tags": entry.get("scene_tags") or [],
        "keywords": entry.get("keywords") or [],
        "has_manual_edits": bool((entry.get("edit_state") or {}).get("dirty")),
        "confirmed": bool((entry.get("write_state") or {}).get("confirmed")),
    }


def _project_vector_doc(entry: dict, bundle: dict) -> dict:
    payload = entry.get("vector_payload") or {}
    return {
        "doc_id": f"vector_{entry.get('entry_id')}",
        "entry_id": entry.get("entry_id"),
        "bundle_id": bundle.get("bundle_id"),
        "embed_profile": "default_zh_v1",
        "title": entry.get("title"),
        "summary_text": payload.get("summary_text") or entry.get("summary"),
        "retrieval_text": payload.get("retrieval_text") or entry.get("retrieval_text"),
        "expanded_text": payload.get("expanded_text") or entry.get("expanded_text"),
        "scene_tags": entry.get("scene_tags") or [],
        "ontology_tags": (entry.get("ontology_payload") or {}).get("entity_types", []) + (entry.get("ontology_payload") or {}).get("relation_types", []) + (entry.get("ontology_payload") or {}).get("enum_refs", []),
        "keywords": entry.get("keywords") or [],
        "metadata": payload.get("metadata") or {},
        "embedding": payload.get("embedding"),
        "embedding_meta": payload.get("embedding_meta") or {},
    }


def _project_graph_doc(entry: dict, bundle: dict) -> dict:
    payload = entry.get("graph_payload") or {}
    ontology_payload = entry.get("ontology_payload") or {}
    return {
        "doc_id": f"graph_{entry.get('entry_id')}",
        "entry_id": entry.get("entry_id"),
        "bundle_id": bundle.get("bundle_id"),
        "row_id": bundle.get("row_id"),
        "case_name": bundle.get("case_name"),
        "path_type": payload.get("path_type") or entry.get("entry_type"),
        "center_entity_id": (payload.get("seed_node_ids") or [None])[0],
        "seed_node_ids": payload.get("seed_node_ids") or [],
        "seed_edge_ids": payload.get("seed_edge_ids") or [],
        "node_ids": payload.get("node_ids") or [],
        "edge_ids": payload.get("edge_ids") or [],
        "entity_types": payload.get("entity_types") or ontology_payload.get("entity_types") or [],
        "relation_types": payload.get("relation_types") or ontology_payload.get("relation_types") or [],
        "subgraph_text": entry.get("expanded_text") or "",
        "expansion_policy": {
            "max_hops": 2,
            "include_derived": True,
            "priority_relations": payload.get("relation_types") or ontology_payload.get("relation_types") or [],
        },
        "scene_tags": entry.get("scene_tags") or [],
    }


def _build_retrieval_manifest(bundle: dict, output_dir: Path) -> dict:
    graph_doc_total = sum(1 for item in (bundle.get("entries") or []) if item.get("graph_payload"))
    remote_count = sum(1 for item in (bundle.get("entries") or []) if ((item.get("vector_payload") or {}).get("embedding_meta") or {}).get("source") == "remote")
    fallback_count = sum(1 for item in (bundle.get("entries") or []) if ((item.get("vector_payload") or {}).get("embedding_meta") or {}).get("source") == "mock_fallback")
    return {
        "bundle_id": bundle.get("bundle_id"),
        "row_id": bundle.get("row_id"),
        "source_parse_version_id": bundle.get("source_parse_version_id"),
        "written_at": _utc_now_iso(),
        "writer_version": "retrieval_writer_v1",
        "embedding_profile": "default_zh_v1",
        "embedding_provider": RETRIEVAL_EMBED_URL,
        "embedding_model": RETRIEVAL_EMBED_MODEL,
        "entry_total": len(bundle.get("entries") or []),
        "vector_doc_total": len(bundle.get("entries") or []),
        "graph_doc_total": graph_doc_total,
        "remote_embedding_total": remote_count,
        "fallback_embedding_total": fallback_count,
        "has_manual_edits": bool((bundle.get("status") or {}).get("has_manual_edits")),
        "stale_entry_count": sum(1 for item in (bundle.get("entries") or []) if (item.get("edit_state") or {}).get("embedding_status") in {"pending", "stale", "failed"}),
        "target": {
            "mode": "file_only",
            "base_dir": str(output_dir.relative_to(REPO_ROOT)),
        },
    }


def _write_retrieval_bundle(bundle: dict) -> tuple[dict, str]:
    stale_entries = [
        item.get("entry_id")
        for item in (bundle.get("entries") or [])
        if (item.get("edit_state") or {}).get("embedding_status") in {"pending", "stale", "failed"}
    ]
    if stale_entries:
        raise ValueError("stale_entries_exist")
    output_dir = _retrieval_write_dir(bundle.get("row_id") or "manual_case", bundle.get("source_parse_version_id") or "v0")
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = copy.deepcopy(bundle)
    write_time = _utc_now_iso()
    for entry in bundle.get("entries") or []:
        entry.setdefault("write_state", {})
        entry["write_state"]["confirmed"] = True
        entry["write_state"]["written"] = True
        entry["write_state"]["last_written_at"] = write_time
    bundle = _refresh_retrieval_bundle_stats(bundle)
    exact_docs = [_project_exact_doc(item, bundle) for item in (bundle.get("entries") or [])]
    vector_docs = [_project_vector_doc(item, bundle) for item in (bundle.get("entries") or [])]
    graph_docs = [_project_graph_doc(item, bundle) for item in (bundle.get("entries") or []) if item.get("graph_payload")]
    manifest = _build_retrieval_manifest(bundle, output_dir)
    (output_dir / "bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(output_dir / "exact_docs.jsonl", "w", encoding="utf-8") as f:
        for item in exact_docs:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    with open(output_dir / "vector_docs.jsonl", "w", encoding="utf-8") as f:
        for item in vector_docs:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    with open(output_dir / "graph_docs.jsonl", "w", encoding="utf-8") as f:
        for item in graph_docs:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return bundle, str(output_dir)


def _load_retrieval_bundle_by_id(bundle_id: str) -> dict | None:
    for path in RUNTIME_RETRIEVAL_ROOT.rglob("bundle.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("bundle_id") == bundle_id:
            return payload
    return None


# ── Routes ──────────────────────────────────────────────────────────────────

TEST_DATA_PATH = REPO_ROOT / "visualization" / "data" / "test_data.json"

def _load_test_data() -> dict:
    if TEST_DATA_PATH.exists():
        try:
            with open(TEST_DATA_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
                json_result = payload.get("json_result") or {}
                if json_result:
                    repaired_output = enrich_graph_output(json_result)
                    repaired_graph = kg_convert(repaired_output)
                    payload["json_result"] = repaired_output
                    payload["nodes"] = repaired_graph.get("nodes", [])
                    payload["edges"] = repaired_graph.get("edges", [])
                    payload["case_name"] = payload.get("case_name") or extract_case_name(repaired_output)
                    if payload.get("score") in (None, ""):
                        payload["score"] = evaluate_output(repaired_output, "manual_restore").get("score", 0)
                    if not payload.get("issues"):
                        payload["issues"] = evaluate_output(repaired_output, "manual_restore").get("issues", [])
                    versions = payload.get("parse_versions") or []
                    if isinstance(versions, list):
                        rebuilt_versions = []
                        for version in versions:
                            if not isinstance(version, dict):
                                continue
                            version_output = enrich_graph_output(version.get("json_result") or repaired_output)
                            version_graph = kg_convert(version_output)
                            next_version = copy.deepcopy(version)
                            next_version["json_result"] = version_output
                            next_version["nodes"] = version_graph.get("nodes", [])
                            next_version["edges"] = version_graph.get("edges", [])
                            rebuilt_versions.append(next_version)
                        payload["parse_versions"] = rebuilt_versions
                return payload
        except Exception:
            pass
    return {"text": "", "json_result": {}}

def _save_test_data(text: str, json_result: dict, extra: dict = None):
    TEST_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"text": text, "json_result": json_result}
    if extra:
        payload.update(extra)
    with open(TEST_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _patch_test_data(extra: dict):
    payload = _load_test_data()
    for key, value in (extra or {}).items():
        if value is not None:
            payload[key] = value
    TEST_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TEST_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/test-data", methods=["GET"])
def api_get_test_data():
    """Return the last saved test data (text + parse result)."""
    return jsonify(_load_test_data())


@app.route("/api/test-data", methods=["POST"])
def api_save_test_data():
    """Save the current text and parse result as test data."""
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    json_result = data.get("json_result", {})
    extra = {
        key: data.get(key)
        for key in (
            "nodes",
            "edges",
            "score",
            "issues",
            "case_name",
            "row_id",
            "term_quality_result",
            "term_eval_result",
            "term_enhancement_result",
            "retrieval_bundle",
            "retrieval_write_manifest",
            "active_tab",
        )
        if key in data
    }
    _save_test_data(text, json_result, extra=extra)
    return jsonify({"status": "ok"})


@app.route("/api/parse", methods=["POST"])
def api_parse():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    try:
        result = parse_text(text)
        # 自动保存解析结果作为测试数据，刷新页面后依然可见
        _save_test_data(text, result.get("json_result", {}),
                       extra={k: result.get(k) for k in ("nodes", "edges", "score", "issues", "case_name", "row_id")})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json(silent=True) or {}
    row_id = data.get("row_id", "")
    json_result = data.get("json_result", {})
    case_name = data.get("case_name", "")
    raw_text = data.get("text", "")
    target_layer = (data.get("target_layer") or "manual").strip()
    ontology_eval = data.get("ontology_eval")
    quality_result = data.get("quality_result")
    enhancement_result = data.get("enhancement_result")
    enhancement_runs = data.get("enhancement_runs")
    parse_versions = data.get("parse_versions")
    active_version_id = data.get("active_version_id")
    retrieval_bundle = data.get("retrieval_bundle")
    retrieval_write_manifest = data.get("retrieval_write_manifest")

    if not row_id:
        return jsonify({"error": "row_id is required"}), 400
    if target_layer not in {"manual", "extracted_candidate"}:
        return jsonify({"error": "target_layer must be manual or extracted_candidate"}), 400

    target_path, _, _ = get_save_target_info(target_layer)

    # Build record in extractor-compatible format
    record = {
        "row_id": row_id,
        "input": {"id": row_id, "text": raw_text},
        "output": json_result,
        "eval": {"row_id": row_id, "score": data.get("score", 0), "issues": data.get("issues", [])},
        "case_name": case_name or "",
        "source": target_layer,
        "_meta": build_save_meta(row_id, raw_text, json_result, case_name, target_layer),
    }
    if ontology_eval:
        record["ontology_eval"] = ontology_eval
    if quality_result:
        record["quality_result"] = quality_result
    if enhancement_result:
        record["enhancement_result"] = enhancement_result
    if enhancement_runs:
        record["enhancement_runs"] = enhancement_runs
    if parse_versions:
        record["parse_versions"] = parse_versions
    if active_version_id:
        record["active_version_id"] = active_version_id
    if retrieval_bundle:
        record["retrieval_bundle"] = retrieval_bundle
    if retrieval_write_manifest:
        record["retrieval_write_manifest"] = retrieval_write_manifest
    upsert_jsonl_record(target_path, "row_id", record)

    # Update cases_index
    index = load_cases_index()
    # Check if already exists (replace)
    index = [e for e in index if e.get("row_id") != row_id]
    meta = _extract_case_meta_from_output(json_result, target_layer)
    index.append({
        "row_id": row_id,
        "case_name": case_name or "未命名案例",
        "case_type": (json_result.get("case_type") or {}).get("category", "unknown"),
        "version": 1,
        "source": target_layer,
        "meta": meta,
    })
    save_cases_index(index)

    return jsonify({
        "status": "ok",
        "file": str(target_path),
        "row_id": row_id,
        "target_layer": target_layer,
        "merged_into": str(target_path.relative_to(REPO_ROOT)),
    })


@app.route("/api/retrieval/build", methods=["POST"])
def api_retrieval_build():
    data = request.get_json(silent=True) or {}
    json_result = data.get("json_result") or {}
    row_id = str(data.get("row_id") or "manual_case")
    version_id = str(data.get("version_id") or "v0")
    case_name = str(data.get("case_name") or "")
    source_enhancement_run_id = data.get("source_enhancement_run_id")
    if not json_result:
        return jsonify({"error": "json_result is required"}), 400
    bundle = _build_retrieval_bundle(
        row_id,
        version_id,
        json_result,
        case_name=case_name,
        source_enhancement_run_id=source_enhancement_run_id,
    )
    _patch_test_data({"retrieval_bundle": bundle, "active_tab": "retrieval"})
    return jsonify({
        "status": "ok",
        "bundle_id": bundle.get("bundle_id"),
        "source_parse_version_id": bundle.get("source_parse_version_id"),
        "bundle": bundle,
    })


@app.route("/api/retrieval/update-entry", methods=["POST"])
def api_retrieval_update_entry():
    data = request.get_json(silent=True) or {}
    bundle = copy.deepcopy(data.get("bundle") or {})
    entry_id = data.get("entry_id")
    patch = data.get("patch") or {}
    if not bundle or not entry_id:
        return jsonify({"error": "bundle and entry_id are required"}), 400
    try:
        updated_bundle, updated_entry = _update_retrieval_entry(bundle, entry_id, patch)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    _patch_test_data({"retrieval_bundle": updated_bundle, "active_tab": "retrieval"})
    return jsonify({
        "status": "ok",
        "bundle_id": updated_bundle.get("bundle_id"),
        "source_parse_version_id": updated_bundle.get("source_parse_version_id"),
        "bundle": updated_bundle,
        "entry": updated_entry,
    })


@app.route("/api/retrieval/re-embed", methods=["POST"])
def api_retrieval_reembed():
    data = request.get_json(silent=True) or {}
    bundle = copy.deepcopy(data.get("bundle") or {})
    entry_ids = data.get("entry_ids") or []
    if not bundle:
        return jsonify({"error": "bundle is required"}), 400
    try:
        updated_bundle = _reembed_retrieval_entries(bundle, entry_ids)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    _patch_test_data({"retrieval_bundle": updated_bundle, "active_tab": "retrieval"})
    return jsonify({
        "status": "ok",
        "bundle_id": updated_bundle.get("bundle_id"),
        "source_parse_version_id": updated_bundle.get("source_parse_version_id"),
        "bundle": updated_bundle,
    })


@app.route("/api/retrieval/write", methods=["POST"])
def api_retrieval_write():
    data = request.get_json(silent=True) or {}
    bundle = copy.deepcopy(data.get("bundle") or {})
    if not bundle:
        return jsonify({"error": "bundle is required"}), 400
    try:
        written_bundle, output_dir = _write_retrieval_bundle(bundle)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    manifest = _build_retrieval_manifest(written_bundle, Path(output_dir))
    _patch_test_data({
        "retrieval_bundle": written_bundle,
        "retrieval_write_manifest": manifest,
        "active_tab": "retrieval",
    })
    return jsonify({
        "status": "ok",
        "bundle_id": written_bundle.get("bundle_id"),
        "source_parse_version_id": written_bundle.get("source_parse_version_id"),
        "bundle": written_bundle,
        "output_dir": output_dir,
        "manifest": manifest,
    })


@app.route("/api/retrieval/bundle/<bundle_id>", methods=["GET"])
def api_retrieval_bundle(bundle_id):
    bundle = _load_retrieval_bundle_by_id(bundle_id)
    if not bundle:
        return jsonify({"error": "bundle_not_found"}), 404
    return jsonify({
        "status": "ok",
        "bundle_id": bundle.get("bundle_id"),
        "source_parse_version_id": bundle.get("source_parse_version_id"),
        "bundle": bundle,
    })


@app.route("/api/cases", methods=["GET"])
def api_cases():
    """Return the full cases index (for admin_instances.html)."""
    index = load_cases_index()
    manual_records = load_manual_records()
    candidate_records = load_candidate_records()

    for item in index:
        meta = item.get("meta") or {}
        needs_meta_refresh = not meta or any(
            key not in meta
            for key in ("case_categories", "case_reasons", "trial_levels", "judgment_years", "publication_years")
        )
        row_id = str(item.get("row_id", ""))
        rec = manual_records.get(row_id) or candidate_records.get(row_id)
        if not needs_meta_refresh and meta:
            continue
        if not rec:
            continue
        item["meta"] = _extract_case_meta_from_output(
            (rec.get("output") or {}),
            rec.get("source") or item.get("source") or "manual"
        )
    return jsonify(index)


@app.route("/api/admin-static-cases", methods=["GET"])
def api_admin_static_cases():
    """Return the legacy admin_instances static case index with filter metadata."""
    bundle = load_admin_static_bundle()
    raw_data = bundle["raw_data"]
    result = []

    for summary in bundle["all_graphs"]:
      row_id = str(summary.get("row_id", ""))
      version = int(summary.get("version", 1) or 1)
      key = f"{row_id}__v{version}" if version > 1 else row_id
      record = raw_data.get(key) or raw_data.get(row_id) or {}
      meta = _extract_static_case_meta(record, source="static")
      result.append({
          "key": key,
          "row_id": row_id,
          "case_name": summary.get("case_name", ""),
          "case_type": summary.get("case_type", ""),
          "version": version,
          "source": summary.get("source", "static"),
          "meta": meta,
      })

    return jsonify(result)


@app.route("/api/admin-static-case/<row_id>", methods=["GET"])
def api_admin_static_case(row_id):
    """Return one legacy admin_instances static case detail."""
    version = request.args.get("version")
    summary, record = _find_static_case_record(row_id, version)
    if not summary or not record:
        return jsonify({"error": "static case not found"}), 404

    version_no = int(summary.get("version", 1) or 1)
    key = f"{row_id}__v{version_no}" if version_no > 1 else str(row_id)
    meta = _extract_static_case_meta(record, source="static")

    return jsonify({
        "key": key,
        "row_id": str(summary.get("row_id", row_id)),
        "case_name": summary.get("case_name", ""),
        "case_type": summary.get("case_type", ""),
        "version": version_no,
        "source": summary.get("source", "static"),
        "json_result": record.get("output", {}) or {},
        "raw_record": record,
        "meta": meta,
    })


@app.route("/api/saved-case/<row_id>", methods=["GET"])
def api_saved_case(row_id):
    """Return full graph data for a saved manual case."""
    records = load_manual_records()
    candidate_records = load_candidate_records()
    rec = records.get(row_id) or candidate_records.get(row_id)
    if not rec:
        return jsonify({"error": "case not found"}), 404

    output = rec.get("output", {})
    versions, active_version_id = _ensure_versions(rec, output)
    requested_version = request.args.get("version_id")
    active_version = _find_version(versions, requested_version or active_version_id)
    version_payload = active_version or versions[-1]
    case_name = rec.get("case_name", "")
    if not case_name:
        from parser import extract_case_name
        case_name = extract_case_name(output)

    return jsonify({
        "row_id": row_id,
        "json_result": version_payload.get("json_result") or output,
        "nodes": version_payload.get("nodes") or [],
        "edges": version_payload.get("edges") or [],
        "case_name": case_name,
        "raw_text": ((rec.get("input") or {}).get("text") or ""),
        "parse_eval": rec.get("eval") or {},
        "ontology_eval": rec.get("ontology_eval") or None,
        "quality_result": rec.get("quality_result") or None,
        "enhancement_result": rec.get("enhancement_result") or None,
        "enhancement_runs": _ensure_enhancement_runs(rec),
        "parse_versions": versions,
        "active_version_id": (active_version or {}).get("version_id") or active_version_id,
        "change_summary": (active_version or {}).get("change_summary") or {},
        "highlight_patch": (active_version or {}).get("highlight_patch") or {},
        "source": rec.get("source", "manual"),
        "meta": _extract_case_meta_from_output(output, rec.get("source", "manual")),
        "raw_record": rec,
        "_meta": rec.get("_meta") or {},
    })


@app.route("/api/parse-quality", methods=["POST"])
def api_parse_quality():
    """Local parse quality analysis — no LLM call, pure statistics."""
    data = request.get_json(silent=True) or {}
    json_result = data.get("json_result", {})
    raw_text = data.get("raw_text")
    row_id = data.get("row_id")

    if not json_result:
        return jsonify({"error": "json_result is required"}), 400

    try:
        from quality_analyzer import parse_quality
        result = parse_quality(json_result)
        _patch_test_data({
            "text": raw_text,
            "row_id": row_id,
            "json_result": json_result,
            "term_quality_result": result,
            "active_tab": "issues",
        })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ontology-evaluate", methods=["POST"])
def api_ontology_evaluate():
    """Evaluate LLM extraction quality against ontology."""
    data = request.get_json(silent=True) or {}
    raw_text = data.get("raw_text", "")
    json_result = data.get("json_result", {})
    row_id = data.get("row_id", "manual_eval")

    if not json_result:
        return jsonify({"error": "json_result is required"}), 400

    try:
        from evaluator import ontology_evaluate
        result = ontology_evaluate(raw_text, json_result, row_id, use_llm=True)
        _patch_test_data({
            "text": raw_text,
            "row_id": row_id,
            "json_result": json_result,
            "term_eval_result": result,
            "active_tab": "eval",
        })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/parse-enhancement", methods=["POST"])
def api_parse_enhancement():
    """Run targeted second-pass parsing for uncovered or weak ontology areas."""
    data = request.get_json(silent=True) or {}
    raw_text = (data.get("raw_text") or "").strip()
    json_result = data.get("json_result") or {}
    row_id = data.get("row_id", "manual_enhance")
    quality_result = data.get("quality_result") or {}
    ontology_eval = data.get("ontology_eval") or {}

    if not raw_text:
        return jsonify({"error": "raw_text is required"}), 400
    if not json_result:
        return jsonify({"error": "json_result is required"}), 400
    if not ontology_eval:
        return jsonify({"error": "ontology_eval is required"}), 400

    try:
        result = parse_enhancement(
            raw_text,
            json_result,
            row_id=row_id,
            quality_result=quality_result,
            ontology_eval=ontology_eval,
        )
        run_id = result.get("run_id") or _next_enhancement_run_id()
        result["run_id"] = run_id
        result["apply_status"] = result.get("apply_status") or "pending"
        existing_runs = _ensure_enhancement_runs(_load_test_data())
        existing_runs = _replace_enhancement_run(existing_runs, result)
        _patch_test_data({
            "text": raw_text,
            "row_id": row_id,
            "json_result": json_result,
            "term_quality_result": quality_result or None,
            "term_eval_result": ontology_eval or None,
            "term_enhancement_result": result,
            "term_enhancement_runs": existing_runs,
            "active_tab": "enhance",
        })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/parse-enhancement/preview-merge", methods=["POST"])
def api_preview_merge_enhancement():
    data = request.get_json(silent=True) or {}
    row_id = data.get("row_id")
    enhancement_run_id = data.get("enhancement_run_id")
    base_version_id = data.get("base_version_id")

    kind, payload, _path = _resolve_runtime_case(row_id)
    if kind == "unknown" or not payload:
        return jsonify({"error": "case not found"}), 404

    base_output = payload.get("output") if kind in {"manual", "extracted_candidate"} else payload.get("json_result")
    versions, active_version_id = _ensure_versions(payload, base_output or {})
    base_version = _find_version(versions, base_version_id or active_version_id)
    if not base_version:
        return jsonify({"error": "base version not found"}), 404

    runs = _ensure_enhancement_runs(payload)
    run = _resolve_enhancement_run(runs, enhancement_run_id)
    if not run:
        return jsonify({"error": "enhancement run not found"}), 404

    preview_graph, highlight_patch, change_summary = _build_preview_result(
        base_version.get("json_result") or {},
        run,
    )
    updated_run = copy.deepcopy(run)
    if updated_run.get("apply_status") == "pending":
        updated_run["apply_status"] = "previewed"

    if kind == "test_data":
        _patch_test_data({
            "term_enhancement_runs": _replace_enhancement_run(runs, updated_run),
            "term_enhancement_result": updated_run,
        })

    return jsonify({
        "row_id": row_id,
        "base_version_id": base_version.get("version_id") or active_version_id,
        "enhancement_run_id": updated_run.get("run_id"),
        "preview_graph": preview_graph,
        "highlight_patch": highlight_patch,
        "change_summary": change_summary,
        "versions": _serialize_version_summaries(versions, active_version_id),
        "apply_status": updated_run.get("apply_status"),
    })


@app.route("/api/parse-enhancement/merge", methods=["POST"])
def api_merge_enhancement():
    data = request.get_json(silent=True) or {}
    row_id = data.get("row_id")
    enhancement_run_id = data.get("enhancement_run_id")
    base_version_id = data.get("base_version_id")

    kind, payload, path = _resolve_runtime_case(row_id)
    if kind == "unknown" or not payload:
        return jsonify({"error": "case not found"}), 404

    base_output = payload.get("output") if kind in {"manual", "extracted_candidate"} else payload.get("json_result")
    versions, active_version_id = _ensure_versions(payload, base_output or {})
    base_version = _find_version(versions, base_version_id or active_version_id)
    if not base_version:
        return jsonify({"error": "base version not found"}), 404

    runs = _ensure_enhancement_runs(payload)
    run = _resolve_enhancement_run(runs, enhancement_run_id)
    if not run:
        return jsonify({"error": "enhancement run not found"}), 404
    if run.get("apply_status") == "merged" and run.get("merged_version_id"):
        existing_version = _find_version(versions, run.get("merged_version_id"))
        return jsonify({
            "row_id": row_id,
            "new_version_id": run.get("merged_version_id"),
            "active_version_id": run.get("merged_version_id"),
            "merged_graph": existing_version or {},
            "versions": _serialize_version_summaries(versions, run.get("merged_version_id")),
            "highlight_patch": (existing_version or {}).get("highlight_patch") or {},
            "change_summary": (existing_version or {}).get("change_summary") or {},
            "enhancement_run_status": "merged",
        })

    merged_graph, highlight_patch, change_summary = _build_preview_result(
        base_version.get("json_result") or {},
        run,
    )
    next_version_id = f"v{len(versions)}"
    version_entry = _build_version_entry(
        next_version_id,
        f"第{len(versions)}次增量合并",
        merged_graph.get("json_result") or {},
        version_type="enhancement_merge",
        source_run_id=run.get("run_id"),
        change_summary=change_summary,
        highlight_patch=highlight_patch,
    )
    versions.append(version_entry)
    active_version_id = next_version_id

    updated_run = copy.deepcopy(run)
    updated_run["apply_status"] = "merged"
    updated_run["merged_version_id"] = next_version_id
    runs = _replace_enhancement_run(runs, updated_run)

    if kind in {"manual", "extracted_candidate"}:
        payload["output"] = version_entry.get("json_result") or payload.get("output") or {}
        payload["enhancement_result"] = updated_run
        payload["enhancement_runs"] = runs
        payload["parse_versions"] = versions
        payload["active_version_id"] = active_version_id
        _persist_runtime_case(kind, payload, path)
    else:
        _patch_test_data({
            "json_result": version_entry.get("json_result") or {},
            "nodes": version_entry.get("nodes") or [],
            "edges": version_entry.get("edges") or [],
            "term_enhancement_result": updated_run,
            "term_enhancement_runs": runs,
            "parse_versions": versions,
            "active_version_id": active_version_id,
            "term_merge_highlight": highlight_patch,
            "active_tab": "enhance",
        })

    return jsonify({
        "row_id": row_id,
        "new_version_id": next_version_id,
        "active_version_id": active_version_id,
        "merged_graph": version_entry,
        "highlight_patch": highlight_patch,
        "change_summary": change_summary,
        "versions": versions,
        "version_summaries": _serialize_version_summaries(versions, active_version_id),
        "enhancement_run_status": "merged",
        "enhancement_run": updated_run,
    })


@app.route("/api/saved-case/<row_id>/versions", methods=["GET"])
def api_saved_case_versions(row_id):
    kind, payload, _path = _resolve_runtime_case(row_id)
    if kind == "unknown" or not payload:
        return jsonify({"error": "case not found"}), 404

    base_output = payload.get("output") if kind in {"manual", "extracted_candidate"} else payload.get("json_result")
    versions, active_version_id = _ensure_versions(payload, base_output or {})
    return jsonify({
        "row_id": row_id,
        "active_version_id": active_version_id,
        "versions": versions,
        "version_summaries": _serialize_version_summaries(versions, active_version_id),
        "enhancement_runs": _ensure_enhancement_runs(payload),
    })


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9120)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--serve-files", action="store_true",
                        help="Also serve static files from visualization/ on the same port")
    args = parser.parse_args()

    # Load .env if available
    hermes_env = Path.home() / ".hermes" / ".env"
    if hermes_env.exists():
        from dotenv import load_dotenv
        load_dotenv(hermes_env)

    if args.serve_files:
        from flask import send_from_directory
        VIS_DIR = REPO_ROOT / "visualization"

        @app.route("/")
        def serve_index():
            return send_from_directory(VIS_DIR, "ontology_v2.2.html")

        @app.route("/<path:filename>")
        def serve_static(filename):
            resp = send_from_directory(VIS_DIR, filename)
            resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp.headers['Pragma'] = 'no-cache'
            resp.headers['Expires'] = '0'
            return resp

    # Try to free the port automatically
    import socket
    import subprocess
    import time
    import os
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((args.host, args.port)) == 0:
                print(f"Port {args.port} is in use. Attempting to free it...", flush=True)
                try:
                    out = subprocess.check_output(["lsof", "-t", f"-i:{args.port}"]).decode().strip()
                    if out:
                        for pid in out.split('\n'):
                            os.system(f"kill -9 {pid}")
                        time.sleep(1)
                except:
                    subprocess.run(["fuser", "-k", f"{args.port}/tcp"], check=False)
                    time.sleep(1)
    except Exception as e:
        pass

    print(f"Starting parse API on {args.host}:{args.port}", flush=True)
    app.run(host=args.host, port=args.port, debug=args.debug)
