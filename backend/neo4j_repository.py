import os
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase
from dotenv import load_dotenv


load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _serialize_temporal(value: Any) -> Any:
    if value is None:
        return None
    isoformat = getattr(value, "iso_format", None)
    if callable(isoformat):
        return isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


class Neo4jRepository:
    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ) -> None:
        self.uri = uri or os.getenv("NEO4J_URI", "")
        self.user = user or os.getenv("NEO4J_USER", "")
        self.password = password or os.getenv("NEO4J_PASSWORD", "")
        self.database = database or os.getenv("NEO4J_DATABASE", "neo4j")
        if not self.uri or not self.user or not self.password:
            raise RuntimeError("Neo4j configuration is incomplete. Please set NEO4J_URI/USER/PASSWORD.")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self) -> None:
        self.driver.close()

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    def run_write(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            result = session.execute_write(lambda tx: list(tx.run(query, parameters or {}).data()))
        return result

    def run_read(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            result = session.execute_read(lambda tx: list(tx.run(query, parameters or {}).data()))
        return result

    def upsert_document(self, payload: Dict[str, Any]) -> None:
        self.run_write(
            """
            MERGE (d:Document {doc_id: $doc_id})
            ON CREATE SET
              d.doc_type = $doc_type,
              d.external_id = $external_id,
              d.row_id = $row_id,
              d.case_name = $case_name,
              d.source = $source,
              d.graph_layer = $graph_layer,
              d.raw_text_ref = $raw_text_ref,
              d.raw_text_preview = $raw_text_preview,
              d.source_text_hash = $source_text_hash,
              d.created_at = datetime($updated_at),
              d.updated_at = datetime($updated_at)
            ON MATCH SET
              d.case_name = $case_name,
              d.row_id = $row_id,
              d.source = $source,
              d.graph_layer = $graph_layer,
              d.raw_text_ref = $raw_text_ref,
              d.raw_text_preview = $raw_text_preview,
              d.source_text_hash = $source_text_hash,
              d.updated_at = datetime($updated_at)
            """,
            payload,
        )

    def upsert_ingest_run(self, payload: Dict[str, Any]) -> None:
        self.run_write(
            """
            MERGE (r:IngestRun {run_id: $run_id})
            ON CREATE SET
              r.doc_id = $doc_id,
              r.graph_layer = $graph_layer,
              r.status = $status,
              r.created_at = datetime($updated_at),
              r.updated_at = datetime($updated_at)
            ON MATCH SET
              r.status = $status,
              r.updated_at = datetime($updated_at)
            WITH r
            MATCH (d:Document {doc_id: $doc_id})
            MERGE (d)-[:INGESTED_BY {graph_layer: $graph_layer}]->(r)
            """,
            payload,
        )

    def deactivate_layer(self, doc_id: str, graph_layer: str, updated_at: str) -> None:
        self.run_write(
            """
            MATCH (d:Document {doc_id: $doc_id})-[r:HAS_ENTITY {graph_layer: $graph_layer}]->()
            SET r.active_flag = false,
                r.updated_at = datetime($updated_at)
            """,
            {"doc_id": doc_id, "graph_layer": graph_layer, "updated_at": updated_at},
        )
        self.run_write(
            """
            MATCH (d:Document {doc_id: $doc_id})-[rs:HAS_ENTITY {graph_layer: $graph_layer}]->(s)
            WHERE coalesce(rs.active_flag, true) = true
            MATCH (s)-[r:RELATES_TO {graph_layer: $graph_layer}]->(t)
            MATCH (d)-[rt:HAS_ENTITY {graph_layer: $graph_layer}]->(t)
            WHERE coalesce(rt.active_flag, true) = true
            SET r.active_flag = false,
                r.updated_at = datetime($updated_at)
            """,
            {"doc_id": doc_id, "graph_layer": graph_layer, "updated_at": updated_at},
        )

    def upsert_chunk(self, payload: Dict[str, Any]) -> None:
        self.run_write(
            """
            MATCH (d:Document {doc_id: $doc_id})
            MERGE (c:Chunk {chunk_id: $chunk_id})
            ON CREATE SET
              c.doc_id = $doc_id,
              c.section_type = $section_type,
              c.seq = $seq,
              c.section_seq = $section_seq,
              c.paragraph_index = $paragraph_index,
              c.text = $text,
              c.char_start = $char_start,
              c.char_end = $char_end,
              c.chunking_version = $chunking_version,
              c.created_at = datetime($updated_at),
              c.updated_at = datetime($updated_at)
            ON MATCH SET
              c.text = $text,
              c.section_type = $section_type,
              c.seq = $seq,
              c.section_seq = $section_seq,
              c.paragraph_index = $paragraph_index,
              c.char_start = $char_start,
              c.char_end = $char_end,
              c.chunking_version = $chunking_version,
              c.updated_at = datetime($updated_at)
            MERGE (d)-[:HAS_CHUNK]->(c)
            """,
            payload,
        )

    def upsert_entity(self, label: str, payload: Dict[str, Any]) -> None:
        query = f"""
            MATCH (d:Document {{doc_id: $doc_id}})
            MERGE (n:{label} {{id: $id}})
            ON CREATE SET
              n += $props,
              n.created_at = datetime($updated_at),
              n.updated_at = datetime($updated_at)
            ON MATCH SET
              n += $props,
              n.updated_at = datetime($updated_at)
            MERGE (d)-[r:HAS_ENTITY {{entity_id: $id, graph_layer: $graph_layer}}]->(n)
            ON CREATE SET
              r.active_flag = true,
              r.source_run_id = $source_run_id,
              r.created_at = datetime($updated_at),
              r.updated_at = datetime($updated_at)
            ON MATCH SET
              r.active_flag = true,
              r.source_run_id = $source_run_id,
              r.updated_at = datetime($updated_at)
        """
        params = {
            "id": payload["id"],
            "doc_id": payload["doc_id"],
            "graph_layer": payload["graph_layer"],
            "source_run_id": payload["source_run_id"],
            "updated_at": payload["updated_at"],
            "props": payload,
        }
        self.run_write(query, params)

    def upsert_entity_reference(self, label: str, payload: Dict[str, Any]) -> None:
        query = f"""
            MATCH (d:Document {{doc_id: $doc_id}})
            MATCH (n:{label} {{id: $id}})
            MERGE (d)-[r:HAS_ENTITY {{entity_id: $id, graph_layer: $graph_layer}}]->(n)
            ON CREATE SET
              r.active_flag = true,
              r.source_run_id = $source_run_id,
              r.reference_only = true,
              r.created_at = datetime($updated_at),
              r.updated_at = datetime($updated_at)
            ON MATCH SET
              r.active_flag = true,
              r.source_run_id = $source_run_id,
              r.reference_only = true,
              r.updated_at = datetime($updated_at)
        """
        params = {
            "id": payload["id"],
            "doc_id": payload["doc_id"],
            "graph_layer": payload["graph_layer"],
            "source_run_id": payload["source_run_id"],
            "updated_at": payload["updated_at"],
        }
        self.run_write(query, params)

    def upsert_alignment(self, label: str, payload: Dict[str, Any]) -> None:
        query = f"""
            MATCH (n:{label} {{id: $entity_id}})
            MATCH (c:Chunk {{chunk_id: $chunk_id}})
            MERGE (n)-[r:SUPPORTED_BY_CHUNK {{chunk_id: $chunk_id}}]->(c)
            ON CREATE SET
              r.score = $score,
              r.match_type = $match_type,
              r.created_at = datetime($updated_at),
              r.updated_at = datetime($updated_at)
            ON MATCH SET
              r.score = $score,
              r.match_type = $match_type,
              r.updated_at = datetime($updated_at)
        """
        self.run_write(query, payload)

    def upsert_relation(self, source_label: str, target_label: str, payload: Dict[str, Any]) -> None:
        query = f"""
            MATCH (s:{source_label} {{id: $source_id}})
            MATCH (t:{target_label} {{id: $target_id}})
            MERGE (s)-[r:RELATES_TO {{relation_id: $relation_id, graph_layer: $graph_layer}}]->(t)
            ON CREATE SET
              r += $props,
              r.created_at = datetime($updated_at),
              r.updated_at = datetime($updated_at)
            ON MATCH SET
              r += $props,
              r.updated_at = datetime($updated_at)
        """
        params = {
            "source_id": payload["source_id"],
            "target_id": payload["target_id"],
            "relation_id": payload["relation_id"],
            "graph_layer": payload["graph_layer"],
            "updated_at": payload["updated_at"],
            "props": payload,
        }
        self.run_write(query, params)

    def query_layer_entity_index(self, doc_id: str, graph_layer: str) -> Dict[str, str]:
        rows = self.run_read(
            """
            MATCH (:Document {doc_id: $doc_id})-[r:HAS_ENTITY {graph_layer: $graph_layer}]->(n)
            WHERE coalesce(r.active_flag, true) = true
            RETURN n.id AS id, labels(n) AS labels
            """,
            {"doc_id": doc_id, "graph_layer": graph_layer},
        )
        result: Dict[str, str] = {}
        for row in rows:
            entity_id = str(row.get("id") or "").strip()
            labels = [str(label).strip() for label in (row.get("labels") or []) if str(label).strip()]
            if not entity_id or not labels:
                continue
            result[entity_id] = labels[0]
        return result

    def query_layer_entity_lookup(self, doc_id: str, graph_layer: str) -> Dict[str, Any]:
        rows = self.run_read(
            """
            MATCH (:Document {doc_id: $doc_id})-[r:HAS_ENTITY {graph_layer: $graph_layer}]->(n)
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
            """,
            {"doc_id": doc_id, "graph_layer": graph_layer},
        )
        by_id: Dict[str, str] = {}
        by_label_text: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
        by_label: Dict[str, List[str]] = {}

        def _normalize_text(value: Any) -> str:
            import re
            text = str(value or "").strip().lower()
            if not text:
                return ""
            text = re.sub(r"\s+", "", text)
            text = re.sub(r"[，。；：、“”‘’（）()【】\\[\\]<>《》,.;:!?！？\\-—_]", "", text)
            return text

        for row in rows:
            entity_id = str(row.get("id") or "").strip()
            labels = [str(label).strip() for label in (row.get("labels") or []) if str(label).strip()]
            if not entity_id or not labels:
                continue
            label = labels[0]
            by_id[entity_id] = label
            by_label.setdefault(label, []).append(entity_id)
            candidate_texts = [
                row.get("preview_text"),
                row.get("name"),
                row.get("content"),
                row.get("claim_text"),
                row.get("argument_text"),
                row.get("assessment_text"),
                row.get("specific_judgment"),
                row.get("case_number"),
            ]
            statute = str(row.get("statute") or "").strip()
            article = str(row.get("article") or "").strip()
            if statute and article:
                candidate_texts.append(f"《{statute}》第{article}条")
            else:
                candidate_texts.extend([row.get("article"), row.get("statute")])
            seen_texts: set[str] = set()
            for value in candidate_texts:
                normalized_text = _normalize_text(value)
                if not normalized_text or normalized_text in seen_texts:
                    continue
                seen_texts.add(normalized_text)
                by_label_text.setdefault((label, normalized_text), []).append({
                    "id": entity_id,
                    "label": label,
                })
        return {
            "by_id": by_id,
            "by_label_text": by_label_text,
            "by_label": by_label,
        }

    def query_case_status(self, doc_id: str) -> Dict[str, Any]:
        doc_rows = self.run_read(
            """
            MATCH (d:Document {doc_id: $doc_id})
            RETURN d.doc_id AS doc_id, d.case_name AS case_name
            """,
            {"doc_id": doc_id},
        )
        if not doc_rows:
            return {"exists": False, "doc_id": doc_id}

        layers: Dict[str, Dict[str, Any]] = {}
        for graph_layer in ("base", "retrieval", "discovery"):
            rows = self.run_read(
                """
                MATCH (d:Document {doc_id: $doc_id})
                OPTIONAL MATCH (d)-[r:HAS_ENTITY {graph_layer: $graph_layer}]->(n)
                WHERE coalesce(r.active_flag, true) = true
                OPTIONAL MATCH (d)-[:INGESTED_BY {graph_layer: $graph_layer}]->(run:IngestRun)
                RETURN count(DISTINCT n) AS entity_count,
                       max(run.updated_at) AS updated_at,
                       collect(DISTINCT run.run_id)[0] AS source_run_id
                """,
                {"doc_id": doc_id, "graph_layer": graph_layer},
            )
            row = rows[0] if rows else {}
            entity_count = int(row.get("entity_count") or 0)
            layers[graph_layer] = {
                "status": "written" if entity_count > 0 else "not_written",
                "entity_count": entity_count,
                "updated_at": _serialize_temporal(row.get("updated_at")),
                "source_run_id": row.get("source_run_id"),
            }

        return {
            "exists": True,
            "doc_id": doc_id,
            "case_name": doc_rows[0].get("case_name") or "",
            "layers": layers,
        }

    def query_case_graph_detail(self, doc_id: str) -> Dict[str, Any]:
        status = self.query_case_status(doc_id)
        if not status.get("exists"):
            return {"exists": False, "doc_id": doc_id}

        layers: Dict[str, Dict[str, Any]] = {}
        for graph_layer in ("base", "retrieval", "discovery"):
            label_rows = self.run_read(
                """
                MATCH (:Document {doc_id: $doc_id})-[r:HAS_ENTITY {graph_layer: $graph_layer}]->(n)
                WHERE coalesce(r.active_flag, true) = true
                UNWIND labels(n) AS label
                RETURN label, count(*) AS count
                ORDER BY count DESC, label ASC
                """,
                {"doc_id": doc_id, "graph_layer": graph_layer},
            )
            relation_rows = self.run_read(
                """
                MATCH (d:Document {doc_id: $doc_id})-[rs:HAS_ENTITY {graph_layer: $graph_layer}]->(s)
                WHERE coalesce(rs.active_flag, true) = true
                MATCH (s)-[r:RELATES_TO {graph_layer: $graph_layer}]->(t)
                MATCH (d)-[rt:HAS_ENTITY {graph_layer: $graph_layer}]->(t)
                WHERE coalesce(rt.active_flag, true) = true
                  AND coalesce(r.active_flag, true) = true
                RETURN r.relation_type AS relation_type, count(*) AS count
                ORDER BY count DESC, relation_type ASC
                """,
                {"doc_id": doc_id, "graph_layer": graph_layer},
            )
            chunk_rows = self.run_read(
                """
                MATCH (:Document {doc_id: $doc_id})-[:HAS_CHUNK]->(c:Chunk)
                RETURN count(c) AS chunk_count
                """,
                {"doc_id": doc_id},
            ) if graph_layer == "base" else [{"chunk_count": 0}]
            summary_counts = []
            summary_entity_count = 0
            if graph_layer == "discovery":
                entity_ref_rows = self.run_read(
                    """
                    MATCH (:Document {doc_id: $doc_id})-[r:HAS_ENTITY {graph_layer: 'discovery'}]->(n)
                    WHERE coalesce(r.active_flag, true) = true
                      AND NOT n:DiscoveryRecord
                      AND NOT n:DiscoveryNode
                      AND NOT n:DiscoveryAnchor
                    RETURN count(DISTINCT n) AS count
                    """,
                    {"doc_id": doc_id},
                )
                document_derived_rows = self.run_read(
                    """
                    MATCH (:Document {doc_id: $doc_id})-[r:HAS_ENTITY {graph_layer: 'discovery'}]->(n:DiscoveryNode)
                    WHERE coalesce(r.active_flag, true) = true
                      AND coalesce(n.node_role, '') = 'document_canonical_derived'
                    RETURN count(DISTINCT n) AS count
                    """,
                    {"doc_id": doc_id},
                )
                enum_anchor_rows = self.run_read(
                    """
                    MATCH (:Document {doc_id: $doc_id})-[r:HAS_ENTITY {graph_layer: 'discovery'}]->(n:DiscoveryAnchor)
                    WHERE coalesce(r.active_flag, true) = true
                      AND coalesce(n.anchor_kind, '') = 'enum_value'
                    RETURN count(DISTINCT n) AS count
                    """,
                    {"doc_id": doc_id},
                )
                summary_counts = [
                    {"label": "实体引用", "count": int((entity_ref_rows[0] or {}).get("count") or 0)},
                    {"label": "文书级派生节点", "count": int((document_derived_rows[0] or {}).get("count") or 0)},
                    {"label": "枚举锚点", "count": int((enum_anchor_rows[0] or {}).get("count") or 0)},
                ]
                summary_entity_count = sum(item["count"] for item in summary_counts)
            layers[graph_layer] = {
                "label_counts": [
                    {"label": row.get("label"), "count": int(row.get("count") or 0)}
                    for row in label_rows
                    if row.get("label")
                ],
                "summary_counts": [item for item in summary_counts if item.get("count")],
                "summary_entity_count": summary_entity_count,
                "relation_type_counts": [
                    {"relation_type": row.get("relation_type") or "unknown", "count": int(row.get("count") or 0)}
                    for row in relation_rows
                ],
                "chunk_count": int((chunk_rows[0] or {}).get("chunk_count") or 0),
            }

        status["detail"] = layers
        return status

    def query_case_subgraph(self, doc_id: str, graph_layer: str, limit: int = 120) -> Dict[str, Any]:
        status = self.query_case_status(doc_id)
        if not status.get("exists"):
            return {"exists": False, "doc_id": doc_id, "graph_layer": graph_layer}

        node_rows = self.run_read(
            """
            MATCH (:Document {doc_id: $doc_id})-[r:HAS_ENTITY {graph_layer: $graph_layer}]->(n)
            WHERE coalesce(r.active_flag, true) = true
            RETURN n.id AS id,
                   labels(n) AS labels,
                   coalesce(n.preview_text, n.label_text, n.name, n.id) AS label,
                   coalesce(n.source_collection, '') AS source_collection
            ORDER BY id
            LIMIT $limit
            """,
            {"doc_id": doc_id, "graph_layer": graph_layer, "limit": int(limit)},
        )
        edge_rows = self.run_read(
            """
            MATCH (d:Document {doc_id: $doc_id})-[rs:HAS_ENTITY {graph_layer: $graph_layer}]->(s)
            WHERE coalesce(rs.active_flag, true) = true
            MATCH (s)-[r:RELATES_TO {graph_layer: $graph_layer}]->(t)
            MATCH (d)-[rt:HAS_ENTITY {graph_layer: $graph_layer}]->(t)
            WHERE coalesce(rt.active_flag, true) = true
              AND coalesce(r.active_flag, true) = true
            RETURN s.id AS source_id,
                   t.id AS target_id,
                   coalesce(r.relation_type, 'RELATES_TO') AS relation_type,
                   r.relation_id AS relation_id
            ORDER BY relation_id
            LIMIT $limit
            """,
            {"doc_id": doc_id, "graph_layer": graph_layer, "limit": int(limit)},
        )
        return {
            "exists": True,
            "doc_id": doc_id,
            "graph_layer": graph_layer,
            "nodes": [
                {
                    "id": row.get("id"),
                    "labels": row.get("labels") or [],
                    "label": row.get("label") or row.get("id") or "",
                    "source_collection": row.get("source_collection") or "",
                }
                for row in node_rows
                if row.get("id")
            ],
            "edges": [
                {
                    "id": row.get("relation_id") or f"{row.get('source_id')}->{row.get('target_id')}",
                    "from": row.get("source_id"),
                    "to": row.get("target_id"),
                    "relation_type": row.get("relation_type") or "RELATES_TO",
                }
                for row in edge_rows
                if row.get("source_id") and row.get("target_id")
            ],
        }
