# Prompt Refresh Report

- generated_at: `2026-05-22T07:46:37+00:00`
- ontology_sha1: `87caa8bf8f1a8dc47474e2449de4bde341e252b7`
- previous_ontology_sha1: `db0a3360846a66e25986d47485e8ba863b6be5ce`

## Ontology Changes

- Added relations: `concerns_focus`, `participates_in_case`

## Few-shot Coverage

### civil
- selected_shot: `2478` | score=`95.0` | case_type=`民事-网络侵权责任纠纷`
- present_entities: `CaseSummary`, `CaseType`, `CourtCase`, `DisputeFocus`, `Evidence`, `Fact`, `GuidingCase`, `JudgmentResult`, `LegalProvision`, `LegalProvisionElement`, `LegalSubject`
- relation_types: `based_on`, `has_dispute_focus`, `proves_fact`, `resolved_by`
- missing_changed_relations: `concerns_focus`, `participates_in_case`

### criminal
- selected_shot: `23127` | score=`90.0` | case_type=`刑事-虐待罪`
- present_entities: `CaseSummary`, `CaseType`, `CourtCase`, `DisputeFocus`, `Evidence`, `Fact`, `GuidingCase`, `JudgmentResult`, `LegalProvision`, `LegalProvisionElement`, `LegalSubject`, `Prosecutor`
- relation_types: `based_on`, `has_dispute_focus`, `proves_fact`, `resolved_by`
- missing_changed_relations: `concerns_focus`, `participates_in_case`

### administrative
- selected_shot: `2847` | score=`95.0` | case_type=`行政-专利相关行政案件`
- present_entities: `CaseSummary`, `CaseType`, `CourtCase`, `DisputeFocus`, `Evidence`, `Fact`, `GuidingCase`, `JudgmentResult`, `LegalProvision`, `LegalProvisionElement`, `LegalSubject`
- relation_types: `based_on`, `has_dispute_focus`, `has_fact`, `matches_element`, `proves_fact`, `resolved_by`, `submitted_for`
- missing_changed_relations: `concerns_focus`, `participates_in_case`
