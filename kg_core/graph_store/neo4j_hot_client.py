"""
Neo4j 热层客户端（Community版）
承载实时类案查询、判决推理、增量 MERGE
"""
from __future__ import annotations
import os
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from neo4j import GraphDatabase, Driver, Session, Transaction


NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "legalkg2026")


class Neo4jHotClient:
    def __init__(self, uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD):
        self.driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    @contextmanager
    def session(self):
        sess = self.driver.session()
        try:
            yield sess
        finally:
            sess.close()

    # ---------- 增量写入 ----------
    def merge_court_case(self, case: Dict[str, Any]) -> None:
        """将案件子图 MERGE 进热层 Neo4j（节点+关系一次性写入）"""
        cypher = """
        MERGE (c:CourtCase {id: $case_id})
        SET c.case_number = $case_number,
            c.filing_date = date($filing_date),
            c.claim_amount = $claim_amount,
            c.trial_level = $trial_level,
            c.status = $status,
            c.cause_of_action = $cause_of_action,
            c.summary = $summary
        WITH c
        MERGE (ct:CaseType {id: $case_type_id})
        MERGE (c)-[:HAS_CASE_TYPE]->(ct)
        WITH c
        MERGE (co:Court {id: $court_id})
        MERGE (c)-[:FILED_IN]->(co)
        WITH c
        FOREACH (provision_id IN $provision_ids |
            MERGE (p:LegalProvision {id: provision_id})
            MERGE (c)-[:CITES]->(p)
        )
        WITH c
        FOREACH (party IN $parties |
            MERGE (sub:LegalSubject {id: party.id, name: party.name})
            ON CREATE SET sub.type = party.type
            MERGE (sub)-[:PLAYS_ROLE {case_id: $case_id, role: party.role}]->(c)
        )
        """
        with self.session() as sess:
            sess.run(cypher, **case)

    def merge_sentencing_standard(self, std: Dict[str, Any]) -> None:
        cypher = """
        MERGE (s:SentencingStandard {id: $id})
        SET s.name = $name,
            s.standard_type = $standard_type,
            s.sentence_range_min = $sentence_range_min,
            s.sentence_range_max = $sentence_range_max,
            s.sentence_unit = $sentence_unit,
            s.measurement_formula = $measurement_formula
        WITH s
        MERGE (ct:CaseType {id: $case_type_id})
        MERGE (s)-[:APPLIES_TO]->(ct)
        WITH s
        MERGE (p:LegalProvision {id: $applicable_provision_id})
        MERGE (s)-[:BASED_ON]->(p)
        """
        with self.session() as sess:
            sess.run(cypher, **std)

    # ---------- 类案查询（三层相似度） ----------
    def find_similar_cases(
        self,
        case_type_id: str,
        court_level: str,
        claim_amount: Optional[float] = None,
        provision_ids: Optional[List[str]] = None,
        filing_date_after: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        第一层：结构相似度（同案由+同法院层级+标的额近似+共享引用法条）
        """
        cypher = """
        MATCH (c:CourtCase)-[:HAS_CASE_TYPE]->(ct:CaseType {id: $case_type_id})
        MATCH (c)-[:FILED_IN]->(co:Court {court_level: $court_level})
        WHERE ($filing_date_after IS NULL OR c.filing_date >= date($filing_date_after))
          AND ($claim_amount IS NULL OR abs(c.claim_amount - $claim_amount) < $claim_amount * 0.2)
        OPTIONAL MATCH (c)-[:CITES]->(p:LegalProvision)
        WITH c, collect(p.id) AS cited
        RETURN c.id AS case_id,
               c.case_number AS case_number,
               c.claim_amount AS claim_amount,
               c.filing_date AS filing_date,
               size([x IN cited WHERE x IN $provision_ids]) AS shared_provisions,
               cited AS provisions
        ORDER BY shared_provisions DESC, c.filing_date DESC
        LIMIT $limit
        """
        with self.session() as sess:
            result = sess.run(
                cypher,
                case_type_id=case_type_id,
                court_level=court_level,
                claim_amount=claim_amount,
                provision_ids=provision_ids or [],
                filing_date_after=filing_date_after,
                limit=limit
            )
            return [dict(r) for r in result]

    def find_guiding_case_prioritized(
        self,
        case_type_id: str,
        disputed_issues: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """查找命中的指导性案例，按 binding_force 排序"""
        cypher = """
        MATCH (gc:GuidingCase)-[:GUIDES_CASE_TYPE]->(ct:CaseType {id: $case_type_id})
        WHERE ($disputed_issues IS NULL OR
               ANY(issue IN $disputed_issues WHERE gc.guiding_points CONTAINS issue))
        RETURN gc.id AS id,
               gc.name AS name,
               gc.guiding_case_number AS number,
               gc.binding_force AS binding_force,
               gc.guiding_points AS points
        ORDER BY CASE gc.binding_force
            WHEN 'mandatory' THEN 1
            WHEN 'persuasive' THEN 2
            WHEN 'reference' THEN 3
            ELSE 4
        END
        LIMIT $limit
        """
        with self.session() as sess:
            result = sess.run(cypher, case_type_id=case_type_id,
                              disputed_issues=disputed_issues, limit=limit)
            return [dict(r) for r in result]

    # ---------- 判决推理（统计聚合） ----------
    def predict_judgment_distribution(
        self,
        case_type_id: str,
        court_level: str,
        claim_amount: Optional[float] = None,
        filing_date_after: Optional[str] = "2021-01-01",
        min_samples: int = 30
    ) -> Dict[str, Any]:
        """
        基于类案统计的判决推理：赔偿区间、胜诉率、量刑分布
        """
        cypher = """
        MATCH (c:CourtCase)-[:HAS_CASE_TYPE]->(ct:CaseType {id: $case_type_id})
        MATCH (c)-[:FILED_IN]->(co:Court {court_level: $court_level})
        MATCH (c)-[:HAS_JUDGMENT]->(j:JudgmentResult)
        WHERE ($filing_date_after IS NULL OR c.filing_date >= date($filing_date_after))
          AND ($claim_amount IS NULL OR abs(c.claim_amount - $claim_amount) < c.claim_amount * 0.2)
        WITH count(c) AS total,
             collect(j.result_type) AS results,
             collect(j.compensation_amount) AS compensations,
             collect(j.sentence_term) AS sentences
        RETURN total,
               // 胜诉率统计
               size([r IN results WHERE r IN ['liable', 'guilty']]) * 1.0 / total AS win_rate,
               // 赔偿金额分位数
               apoc.coll.percentiles(compensations, [0.25, 0.5, 0.75]) AS compensation_quartiles,
               // 量刑分位数
               apoc.coll.percentiles([s IN sentences WHERE s IS NOT NULL], [0.25, 0.5, 0.75]) AS sentence_quartiles,
               // 结果分布
               apoc.coll.frequencies(results) AS result_distribution
        """
        with self.session() as sess:
            record = sess.run(
                cypher,
                case_type_id=case_type_id,
                court_level=court_level,
                claim_amount=claim_amount,
                filing_date_after=filing_date_after
            ).single()
            if record is None or record["total"] < min_samples:
                return {
                    "status": "insufficient_samples",
                    "total": record["total"] if record else 0,
                    "message": f"样本不足{min_samples}，推理结果仅供参考"
                }
            return {
                "status": "ok",
                "total": record["total"],
                "win_rate": round(record["win_rate"], 3),
                "compensation_quartiles": record["compensation_quartiles"],
                "sentence_quartiles": record["sentence_quartiles"],
                "result_distribution": record["result_distribution"]
            }

    # ---------- 企业跨案件关联查询 ----------
    def find_cases_by_organization(
        self,
        credit_code: str,
        role: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """通过统一社会信用代码查询企业涉诉历史"""
        cypher = """
        MATCH (o:Organization {credit_code: $credit_code})
        MATCH (o)-[r:PLAYS_ROLE]->(c:CourtCase)
        WHERE ($role IS NULL OR r.role = $role)
        RETURN c.id AS case_id,
               c.case_number AS case_number,
               c.filing_date AS filing_date,
               c.status AS status,
               r.role AS role
        ORDER BY c.filing_date DESC
        LIMIT $limit
        """
        with self.session() as sess:
            result = sess.run(cypher, credit_code=credit_code, role=role, limit=limit)
            return [dict(r) for r in result]

    # ---------- 初始化索引 ----------
    def ensure_indexes(self) -> None:
        """创建常用索引以加速查询"""
        indexes = [
            "CREATE INDEX case_type_idx IF NOT EXISTS FOR (c:CourtCase) ON (c.case_type_id)",
            "CREATE INDEX court_level_idx IF NOT EXISTS FOR (c:Court) ON (c.court_level)",
            "CREATE INDEX filing_date_idx IF NOT EXISTS FOR (c:CourtCase) ON (c.filing_date)",
            "CREATE INDEX credit_code_idx IF NOT EXISTS FOR (o:Organization) ON (o.credit_code)",
            "CREATE INDEX binding_force_idx IF NOT EXISTS FOR (g:GuidingCase) ON (g.binding_force)",
            "CREATE INDEX case_num_idx IF NOT EXISTS FOR (c:CourtCase) ON (c.case_number)",
        ]
        with self.session() as sess:
            for idx in indexes:
                sess.run(idx)
