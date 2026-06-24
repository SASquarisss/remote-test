from typing import Any, Dict

from parser import normalize_graph_output
from neo4j_models import (
    build_alignment_payloads,
    build_chunk_payloads,
    build_discovery_layer_payload,
    build_doc_id,
    build_document_payload,
    build_entity_payloads,
    build_relation_payloads,
    build_retrieval_layer_payload,
    build_run_id,
    utc_now_iso,
)
from neo4j_repository import Neo4jRepository
from neo4j_schema import ensure_constraints


def _normalize_write_case_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    doc_context = payload.get("doc_context") or {}
    data = payload.get("data") or {}
    write_options = payload.get("write_options") or {}

    row_id = str(doc_context.get("row_id") or payload.get("row_id") or data.get("row_id") or "manual_case")
    doc_type = str(doc_context.get("doc_type") or payload.get("doc_type") or "case")
    external_id = str(doc_context.get("external_id") or payload.get("external_id") or row_id)
    doc_id = str(doc_context.get("doc_id") or payload.get("doc_id") or build_doc_id(row_id, doc_type, external_id))
    case_name = str(doc_context.get("case_name") or payload.get("case_name") or data.get("case_name") or "")
    raw_text = str(data.get("raw_text") or payload.get("raw_text") or "")
    json_result = data.get("json_result") or payload.get("json_result") or {}
    parse_versions = data.get("parse_versions") or payload.get("parse_versions") or []
    active_version_id = str(data.get("active_version_id") or payload.get("active_version_id") or "v0")
    graph_layer = str(write_options.get("graph_layer") or payload.get("graph_layer") or "base")
    text_chunks = data.get("text_chunks") or payload.get("text_chunks") or []
    source_alignment = data.get("source_alignment") or payload.get("source_alignment") or {}
    source = str(doc_context.get("source") or payload.get("source") or "manual")
    overwrite_scope = str(write_options.get("overwrite_scope") or "doc_layer")

    return {
        "row_id": row_id,
        "doc_type": doc_type,
        "external_id": external_id,
        "doc_id": doc_id,
        "case_name": case_name,
        "raw_text": raw_text,
        "json_result": normalize_graph_output(json_result) if isinstance(json_result, dict) else {},
        "parse_versions": parse_versions,
        "active_version_id": active_version_id,
        "graph_layer": graph_layer,
        "text_chunks": text_chunks,
        "source_alignment": source_alignment,
        "source": source,
        "overwrite_scope": overwrite_scope,
    }


def get_repository() -> Neo4jRepository:
    return Neo4jRepository()


def _upsert_entities_and_relations(repo: Neo4jRepository, entity_payloads, relation_payloads) -> None:
    for entity in entity_payloads:
        repo.upsert_entity(entity["label"], entity["properties"])
    for rel in relation_payloads:
        repo.upsert_relation(rel["source_label"], rel["target_label"], rel["properties"])


def _upsert_entity_references(repo: Neo4jRepository, entity_reference_payloads) -> None:
    for entity_ref in entity_reference_payloads:
        repo.upsert_entity_reference(entity_ref["label"], entity_ref["properties"])


def neo4j_health() -> Dict[str, Any]:
    repo = get_repository()
    try:
        ensure_constraints(repo)
        repo.verify_connectivity()
        rows = repo.run_read("RETURN 1 AS ok")
        return {
            "status": "ok",
            "connected": bool(rows and rows[0].get("ok") == 1),
            "database": repo.database,
            "uri": repo.uri,
        }
    finally:
        repo.close()


def write_case_graph(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _normalize_write_case_payload(payload)
    if normalized["graph_layer"] != "base":
        raise ValueError("graph_layer must be base for write_case_graph")
    if not normalized["json_result"]:
        raise ValueError("json_result is required")

    source_run_id = build_run_id(normalized["doc_id"], normalized["graph_layer"])
    now = utc_now_iso()
    doc_payload = build_document_payload(
        doc_id=normalized["doc_id"],
        doc_type=normalized["doc_type"],
        external_id=normalized["external_id"],
        row_id=normalized["row_id"],
        case_name=normalized["case_name"],
        raw_text=normalized["raw_text"],
        source=normalized["source"],
        graph_layer=normalized["graph_layer"],
    )
    ingest_payload = {
        "run_id": source_run_id,
        "doc_id": normalized["doc_id"],
        "graph_layer": normalized["graph_layer"],
        "status": "written",
        "updated_at": now,
    }
    chunk_payloads = build_chunk_payloads(normalized["doc_id"], normalized["text_chunks"])
    entity_payloads = build_entity_payloads(
        doc_id=normalized["doc_id"],
        json_result=normalized["json_result"],
        graph_layer=normalized["graph_layer"],
        source_run_id=source_run_id,
        version_id=normalized["active_version_id"],
    )
    relation_payloads = build_relation_payloads(
        doc_id=normalized["doc_id"],
        json_result=normalized["json_result"],
        graph_layer=normalized["graph_layer"],
        source_run_id=source_run_id,
    )
    explicit_relation_count = sum(
        1 for rel in relation_payloads if (rel.get("properties") or {}).get("relation_origin") == "explicit"
    )
    derived_relation_count = sum(
        1 for rel in relation_payloads if (rel.get("properties") or {}).get("relation_origin") == "derived"
    )
    alignment_payloads = build_alignment_payloads(
        source_alignment=normalized["source_alignment"],
        entity_payloads=entity_payloads,
    )

    repo = get_repository()
    try:
        ensure_constraints(repo)
        repo.upsert_document(doc_payload)
        repo.upsert_ingest_run(ingest_payload)
        if normalized["overwrite_scope"] == "doc_layer":
            repo.deactivate_layer(normalized["doc_id"], normalized["graph_layer"], now)
        for chunk in chunk_payloads:
            repo.upsert_chunk(chunk)
        _upsert_entities_and_relations(
            repo,
            entity_payloads,
            [
                {**rel, "properties": {**rel["properties"], "source_id": rel["source_id"], "target_id": rel["target_id"]}}
                for rel in relation_payloads
            ],
        )
        for alignment in alignment_payloads:
            repo.upsert_alignment(alignment["entity_label"], alignment)
        status = repo.query_case_status(normalized["doc_id"])
    finally:
        repo.close()

    return {
        "status": "ok",
        "doc_id": normalized["doc_id"],
        "graph_layer": normalized["graph_layer"],
        "source_run_id": source_run_id,
        "write_summary": {
            "document_written": True,
            "chunk_count": len(chunk_payloads),
            "node_count": len(entity_payloads),
            "relation_count": len(relation_payloads),
            "explicit_relation_count": explicit_relation_count,
            "derived_relation_count": derived_relation_count,
            "alignment_count": len(alignment_payloads),
            "deactivated_count": 0,
        },
        "neo4j_status": status.get("layers") or {},
    }


def get_case_status(doc_id: str) -> Dict[str, Any]:
    repo = get_repository()
    try:
        ensure_constraints(repo)
        status = repo.query_case_status(doc_id)
    finally:
        repo.close()
    return {"status": "ok", **status}


def get_case_status_map(doc_ids: list[str]) -> Dict[str, Dict[str, Any]]:
    repo = get_repository()
    result: Dict[str, Dict[str, Any]] = {}
    try:
        ensure_constraints(repo)
        for doc_id in [item for item in doc_ids if item]:
            result[doc_id] = repo.query_case_status(doc_id)
    finally:
        repo.close()
    return result


def get_case_graph_detail(doc_id: str) -> Dict[str, Any]:
    repo = get_repository()
    try:
        ensure_constraints(repo)
        detail = repo.query_case_graph_detail(doc_id)
    finally:
        repo.close()
    return {"status": "ok", **detail}


def get_case_subgraph(doc_id: str, graph_layer: str = "base", limit: int = 120) -> Dict[str, Any]:
    repo = get_repository()
    try:
        ensure_constraints(repo)
        subgraph = repo.query_case_subgraph(doc_id, graph_layer, limit=limit)
    finally:
        repo.close()
    return {"status": "ok", **subgraph}


def write_retrieval_layer(payload: Dict[str, Any]) -> Dict[str, Any]:
    bundle = payload.get("bundle") or {}
    write_mode = str(payload.get("write_mode") or "strict")
    skipped_entries = [item for item in (payload.get("skipped_entries") or []) if isinstance(item, dict)]
    row_id = str(payload.get("row_id") or bundle.get("row_id") or "manual_case")
    if not bundle:
        raise ValueError("bundle is required")
    doc_id = str(payload.get("doc_id") or build_doc_id(row_id, "case", row_id))
    source_run_id = build_run_id(doc_id, "retrieval")
    now = utc_now_iso()
    doc_payload = build_document_payload(
        doc_id=doc_id,
        doc_type="case",
        external_id=row_id,
        row_id=row_id,
        case_name=str(bundle.get("case_name") or payload.get("case_name") or ""),
        raw_text="",
        source="retrieval_bundle",
        graph_layer="retrieval",
    )
    ingest_payload = {
        "run_id": source_run_id,
        "doc_id": doc_id,
        "graph_layer": "retrieval",
        "status": "written",
        "updated_at": now,
    }
    repo = get_repository()
    try:
        ensure_constraints(repo)
        base_entity_index = repo.query_layer_entity_index(doc_id, "base")
        base_entity_lookup = repo.query_layer_entity_lookup(doc_id, "base")
        mapped = build_retrieval_layer_payload(
            doc_id=doc_id,
            bundle=bundle,
            source_run_id=source_run_id,
            base_entity_index=base_entity_index,
            base_entity_lookup=base_entity_lookup,
        )
        repo.upsert_document(doc_payload)
        repo.upsert_ingest_run(ingest_payload)
        repo.deactivate_layer(doc_id, "retrieval", now)
        _upsert_entities_and_relations(repo, mapped["entity_payloads"], [])
        _upsert_entity_references(repo, mapped.get("entity_reference_payloads") or [])
        for rel in mapped["relation_payloads"]:
            repo.upsert_relation(rel["source_label"], rel["target_label"], rel["properties"])
        status = repo.query_case_status(doc_id)
    finally:
        repo.close()
    entity_reference_payloads = mapped.get("entity_reference_payloads") or []
    fallback_node_count = sum(1 for item in mapped["entity_payloads"] if item.get("label") == "RetrievalGraphNode")
    return {
        "status": "ok",
        "doc_id": doc_id,
        "graph_layer": "retrieval",
        "source_run_id": source_run_id,
        "write_summary": {
            "write_mode": write_mode,
            "entry_count": len(bundle.get("entries") or []),
            "written_entry_count": len(bundle.get("entries") or []),
            "skipped_entry_count": len(skipped_entries),
            "skipped_entries": skipped_entries,
            "node_count": len(mapped["entity_payloads"]) + len(entity_reference_payloads),
            "entity_ref_count": len(entity_reference_payloads),
            "fallback_node_count": fallback_node_count,
            "relation_count": len(mapped["relation_payloads"]),
        },
        "neo4j_status": status.get("layers") or {},
    }


def write_discovery_layer(payload: Dict[str, Any]) -> Dict[str, Any]:
    discovery_record = payload.get("discovery_record") or {}
    discovery_history = [item for item in (payload.get("discovery_history") or []) if isinstance(item, dict)]
    row_id = str(payload.get("row_id") or payload.get("doc_context", {}).get("row_id") or "manual_case")
    if not discovery_history and not discovery_record:
        raise ValueError("discovery_record or discovery_history is required")
    doc_id = str(payload.get("doc_id") or build_doc_id(row_id, "case", row_id))
    source_run_id = build_run_id(doc_id, "discovery")
    now = utc_now_iso()
    records_to_write = discovery_history or [discovery_record]
    latest_record = records_to_write[-1] if records_to_write else {}
    result = latest_record.get("result") or {}
    doc_payload = build_document_payload(
        doc_id=doc_id,
        doc_type="case",
        external_id=row_id,
        row_id=row_id,
        case_name=str(payload.get("case_name") or ""),
        raw_text="",
        source="discovery_history",
        graph_layer="discovery",
    )
    ingest_payload = {
        "run_id": source_run_id,
        "doc_id": doc_id,
        "graph_layer": "discovery",
        "status": "written",
        "updated_at": now,
    }
    repo = get_repository()
    try:
        ensure_constraints(repo)
        mapped = build_discovery_layer_payload(
            doc_id=doc_id,
            discovery_record=latest_record if not discovery_history else None,
            discovery_history=records_to_write,
            source_run_id=source_run_id,
            base_entity_index=repo.query_layer_entity_index(doc_id, "base"),
            base_entity_lookup=repo.query_layer_entity_lookup(doc_id, "base"),
        )
        repo.upsert_document(doc_payload)
        repo.upsert_ingest_run(ingest_payload)
        repo.deactivate_layer(doc_id, "discovery", now)
        _upsert_entities_and_relations(repo, mapped["entity_payloads"], [])
        _upsert_entity_references(repo, mapped.get("entity_reference_payloads") or [])
        for rel in mapped["relation_payloads"]:
            repo.upsert_relation(rel["source_label"], rel["target_label"], rel["properties"])
        status = repo.query_case_status(doc_id)
    finally:
        repo.close()
    entity_reference_payloads = mapped.get("entity_reference_payloads") or []
    derived_node_count = sum(
        1
        for item in mapped["entity_payloads"]
        if item.get("label") == "DiscoveryNode"
        and str((item.get("properties") or {}).get("node_role") or "") == "document_canonical_derived"
    )
    anchor_count = sum(1 for item in mapped["entity_payloads"] if item.get("label") == "DiscoveryAnchor")
    enum_anchor_count = sum(
        1
        for item in mapped["entity_payloads"]
        if item.get("label") == "DiscoveryAnchor"
        and str((item.get("properties") or {}).get("anchor_kind") or "") == "enum_value"
    )
    return {
        "status": "ok",
        "doc_id": doc_id,
        "graph_layer": "discovery",
        "source_run_id": source_run_id,
        "write_summary": {
            "record_count": len(records_to_write),
            "record_ids": [item.get("id") for item in records_to_write if item.get("id")],
            "record_id": latest_record.get("id"),
            "conclusion": result.get("conclusion"),
            "node_count": len(mapped["entity_payloads"]) + len(entity_reference_payloads),
            "entity_ref_count": len(entity_reference_payloads),
            "derived_node_count": derived_node_count,
            "document_derived_node_count": derived_node_count,
            "enum_anchor_count": enum_anchor_count,
            "anchor_count": anchor_count,
            "relation_count": len(mapped["relation_payloads"]),
        },
        "neo4j_status": status.get("layers") or {},
    }
