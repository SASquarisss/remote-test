"""
批量导入脚本：Gold 层 CSV → Neo4j（离线 neo4j-admin import 或在线 LOAD CSV）
适用于 MVP 初始化和增量更新
"""
import os
import sys
import csv
import argparse
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from kg_core.graph_store.neo4j_hot_client import Neo4jHotClient


def load_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def import_courts(client: Neo4jHotClient, csv_path: str):
    rows = load_csv(csv_path)
    cypher = """
    UNWIND $rows AS row
    MERGE (c:Court {id: row.id})
    SET c.name = row.name,
        c.court_level = row.court_level,
        c.credit_code = row.credit_code
    WITH c, row
    MERGE (d:District {id: row.district_id})
    MERGE (c)-[:HAS_JURISDICTION_OVER]->(d)
    """
    with client.session() as sess:
        sess.run(cypher, rows=rows)
    print(f"Imported {len(rows)} courts")


def import_cases(client: Neo4jHotClient, csv_path: str, batch_size: int = 500):
    rows = load_csv(csv_path)
    cypher = """
    UNWIND $rows AS row
    MERGE (c:CourtCase {id: row.id})
    SET c.case_number = row.case_number,
        c.filing_date = date(row.filing_date),
        c.claim_amount = toFloat(row.claim_amount),
        c.trial_level = row.trial_level,
        c.status = row.status,
        c.cause_of_action = row.cause_of_action,
        c.summary = row.summary
    WITH c, row
    MERGE (ct:CaseType {id: row.case_type_id})
    MERGE (c)-[:HAS_CASE_TYPE]->(ct)
    WITH c, row
    MERGE (co:Court {id: row.court_id})
    MERGE (c)-[:FILED_IN]->(co)
    """
    # 批量执行
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        with client.session() as sess:
            sess.run(cypher, rows=batch)
        print(f"  Cases batch {i//batch_size + 1}/{(len(rows)-1)//batch_size + 1} done")
    print(f"Imported {len(rows)} cases")


def import_provisions(client: Neo4jHotClient, csv_path: str):
    rows = load_csv(csv_path)
    cypher = """
    UNWIND $rows AS row
    MERGE (p:LegalProvision {id: row.id})
    SET p.law_id = row.law_id,
        p.article = row.article,
        p.paragraph = row.paragraph,
        p.item = row.item,
        p.content = row.content,
        p.status = row.status
    WITH p, row
    MERGE (l:Law {id: row.law_id})
    MERGE (p)-[:BELONGS_TO]->(l)
    """
    with client.session() as sess:
        sess.run(cypher, rows=rows)
    print(f"Imported {len(rows)} provisions")


def import_sentencing_standards(client: Neo4jHotClient, csv_path: str):
    rows = load_csv(csv_path)
    cypher = """
    UNWIND $rows AS row
    MERGE (s:SentencingStandard {id: row.id})
    SET s.name = row.name,
        s.standard_type = row.standard_type,
        s.sentence_range_min = toFloat(row.sentence_range_min),
        s.sentence_range_max = toFloat(row.sentence_range_max),
        s.sentence_unit = row.sentence_unit,
        s.measurement_formula = row.measurement_formula
    WITH s, row
    MERGE (ct:CaseType {id: row.case_type_id})
    MERGE (s)-[:APPLIES_TO]->(ct)
    """
    with client.session() as sess:
        sess.run(cypher, rows=rows)
    print(f"Imported {len(rows)} sentencing standards")


def import_guiding_cases(client: Neo4jHotClient, csv_path: str):
    rows = load_csv(csv_path)
    cypher = """
    UNWIND $rows AS row
    MERGE (g:GuidingCase {id: row.id})
    SET g.guiding_case_number = row.guiding_case_number,
        g.name = row.name,
        g.issuing_court_id = row.issuing_court_id,
        g.publication_date = date(row.publication_date),
        g.guiding_points = row.guiding_points,
        g.binding_force = row.binding_force
    WITH g, row
    MERGE (c:Court {id: row.issuing_court_id})
    MERGE (g)-[:ISSUED_BY]->(c)
    WITH g, row
    UNWIND split(row.related_case_type_ids, ";") AS ct_id
    MERGE (ct:CaseType {id: trim(ct_id)})
    MERGE (g)-[:GUIDES_CASE_TYPE]->(ct)
    """
    with client.session() as sess:
        sess.run(cypher, rows=rows)
    print(f"Imported {len(rows)} guiding cases")


def import_relations_cites(client: Neo4jHotClient, csv_path: str, batch_size: int = 1000):
    rows = load_csv(csv_path)
    cypher = """
    UNWIND $rows AS row
    MATCH (c:CourtCase {id: row.case_id})
    MATCH (p:LegalProvision {id: row.provision_id})
    MERGE (c)-[r:CITES]->(p)
    SET r.citation_position = row.citation_position,
        r.citation_purpose = row.citation_purpose
    """
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        with client.session() as sess:
            sess.run(cypher, rows=batch)
        print(f"  Cites batch {i//batch_size + 1}/{(len(rows)-1)//batch_size + 1} done")
    print(f"Imported {len(rows)} citation relations")


def main():
    parser = argparse.ArgumentParser(description="Legal KG Bulk Import Tool")
    parser.add_argument("--data-dir", default="./data_lake/gold", help="Gold层CSV目录")
    parser.add_argument("--entity", choices=["all", "courts", "cases", "provisions",
                                              "sentencing_standards", "guiding_cases", "relations_cites"],
                        default="all")
    args = parser.parse_args()

    client = Neo4jHotClient()
    client.ensure_indexes()
    data_dir = Path(args.data_dir)

    mapping = {
        "courts": (data_dir / "Court.csv", import_courts),
        "cases": (data_dir / "CourtCase.csv", import_cases),
        "provisions": (data_dir / "LegalProvision.csv", import_provisions),
        "sentencing_standards": (data_dir / "SentencingStandard.csv", import_sentencing_standards),
        "guiding_cases": (data_dir / "GuidingCase.csv", import_guiding_cases),
        "relations_cites": (data_dir / "edges_CITES.csv", import_relations_cites),
    }

    if args.entity == "all":
        for name, (path, fn) in mapping.items():
            if path.exists():
                print(f"\n=== Importing {name} from {path} ===")
                fn(client, str(path))
            else:
                print(f"Skipping {name}: {path} not found")
    else:
        path, fn = mapping[args.entity]
        if path.exists():
            fn(client, str(path))
        else:
            print(f"File not found: {path}")

    print("\nBulk import completed.")


if __name__ == "__main__":
    main()
