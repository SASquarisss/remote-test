from neo4j_repository import Neo4jRepository


CONSTRAINT_STATEMENTS = [
    "CREATE CONSTRAINT document_doc_id IF NOT EXISTS FOR (n:Document) REQUIRE n.doc_id IS UNIQUE",
    "CREATE CONSTRAINT chunk_chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.chunk_id IS UNIQUE",
    "CREATE CONSTRAINT ingest_run_id IF NOT EXISTS FOR (n:IngestRun) REQUIRE n.run_id IS UNIQUE",
    "CREATE CONSTRAINT court_case_id IF NOT EXISTS FOR (n:CourtCase) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT trial_organization_id IF NOT EXISTS FOR (n:TrialOrganization) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT judge_id IF NOT EXISTS FOR (n:Judge) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT legal_subject_id IF NOT EXISTS FOR (n:LegalSubject) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT attorney_id IF NOT EXISTS FOR (n:Attorney) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT fact_id IF NOT EXISTS FOR (n:Fact) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT dispute_focus_id IF NOT EXISTS FOR (n:DisputeFocus) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT litigation_claim_id IF NOT EXISTS FOR (n:LitigationClaim) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT procedural_opinion_id IF NOT EXISTS FOR (n:ProceduralOpinion) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT argument_point_id IF NOT EXISTS FOR (n:ArgumentPoint) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT judicial_assessment_id IF NOT EXISTS FOR (n:JudicialAssessment) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT evidence_id IF NOT EXISTS FOR (n:Evidence) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT judgment_result_id IF NOT EXISTS FOR (n:JudgmentResult) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT legal_provision_id IF NOT EXISTS FOR (n:LegalProvision) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT legal_provision_element_id IF NOT EXISTS FOR (n:LegalProvisionElement) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT retrieval_entry_id IF NOT EXISTS FOR (n:RetrievalEntry) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT retrieval_graph_node_id IF NOT EXISTS FOR (n:RetrievalGraphNode) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT discovery_record_id IF NOT EXISTS FOR (n:DiscoveryRecord) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT discovery_node_id IF NOT EXISTS FOR (n:DiscoveryNode) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT discovery_anchor_id IF NOT EXISTS FOR (n:DiscoveryAnchor) REQUIRE n.id IS UNIQUE",
]


def ensure_constraints(repo: Neo4jRepository) -> None:
    for statement in CONSTRAINT_STATEMENTS:
        repo.run_write(statement)
