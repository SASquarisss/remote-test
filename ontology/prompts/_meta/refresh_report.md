# Prompt Refresh Report

- generated_at: `2026-06-02T03:25:25+00:00`
- ontology_sha1: `66f27c9387db643126733c331e64781924934fda`
- previous_ontology_sha1: `87caa8bf8f1a8dc47474e2449de4bde341e252b7`

## Ontology Changes

- Added entities: `ArgumentPoint`, `JudicialAssessment`, `LitigationClaim`, `ProceduralOpinion`
- Added relations: `assesses_focus`, `based_on_fact`, `based_on_provision`, `claims_focus`, `evaluates_argument`, `expresses_opinion`, `opines_on_focus`, `raises_claim`, `responds_to_claim`, `responds_to_opinion`, `supports_claim`, `supports_opinion`, `supports_result`, `targets_subject`

## Few-shot Coverage

### civil
- selected_shot: `2478` | score=`95.0` | case_type=`民事-网络侵权责任纠纷`
- present_entities: `CaseSummary`, `CaseType`, `CourtCase`, `DisputeFocus`, `Evidence`, `Fact`, `GuidingCase`, `JudgmentResult`, `LegalProvision`, `LegalProvisionElement`, `LegalSubject`
- relation_types: `based_on`, `has_dispute_focus`, `proves_fact`, `resolved_by`
- missing_changed_entities: `ArgumentPoint`, `JudicialAssessment`, `LitigationClaim`, `ProceduralOpinion`
- missing_changed_relations: `assesses_focus`, `based_on_fact`, `based_on_provision`, `claims_focus`, `evaluates_argument`, `expresses_opinion`, `opines_on_focus`, `raises_claim`, `responds_to_claim`, `responds_to_opinion`, `supports_claim`, `supports_opinion`, `supports_result`, `targets_subject`

### criminal
- selected_shot: `23127` | score=`90.0` | case_type=`刑事-虐待罪`
- present_entities: `CaseSummary`, `CaseType`, `CourtCase`, `DisputeFocus`, `Evidence`, `Fact`, `GuidingCase`, `JudgmentResult`, `LegalProvision`, `LegalProvisionElement`, `LegalSubject`, `Prosecutor`
- relation_types: `based_on`, `has_dispute_focus`, `proves_fact`, `resolved_by`
- missing_changed_entities: `ArgumentPoint`, `JudicialAssessment`, `LitigationClaim`, `ProceduralOpinion`
- missing_changed_relations: `assesses_focus`, `based_on_fact`, `based_on_provision`, `claims_focus`, `evaluates_argument`, `expresses_opinion`, `opines_on_focus`, `raises_claim`, `responds_to_claim`, `responds_to_opinion`, `supports_claim`, `supports_opinion`, `supports_result`, `targets_subject`

### administrative
- selected_shot: `2847` | score=`95.0` | case_type=`行政-专利相关行政案件`
- present_entities: `CaseSummary`, `CaseType`, `CourtCase`, `DisputeFocus`, `Evidence`, `Fact`, `GuidingCase`, `JudgmentResult`, `LegalProvision`, `LegalProvisionElement`, `LegalSubject`
- relation_types: `based_on`, `has_dispute_focus`, `has_fact`, `matches_element`, `proves_fact`, `resolved_by`, `submitted_for`
- missing_changed_entities: `ArgumentPoint`, `JudicialAssessment`, `LitigationClaim`, `ProceduralOpinion`
- missing_changed_relations: `assesses_focus`, `based_on_fact`, `based_on_provision`, `claims_focus`, `evaluates_argument`, `expresses_opinion`, `opines_on_focus`, `raises_claim`, `responds_to_claim`, `responds_to_opinion`, `supports_claim`, `supports_opinion`, `supports_result`, `targets_subject`
