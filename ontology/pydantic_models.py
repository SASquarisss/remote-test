"""
生产级法律本体 Pydantic v2 模型
由 legal_ontology_v2.yaml 映射而来，用于数据校验与类型安全
"""

from __future__ import annotations
from datetime import date, datetime
from typing import Literal, Optional, List
from pydantic import BaseModel, Field, field_validator


# ==================== 顶层父类 ====================
class LegalNorm(BaseModel):
    id: str = Field(..., pattern=r"^[a-z]+_[0-9]{4}_[a-z_]+$")
    name: str
    source: str
    desensitize: bool
    create_time: datetime
    update_time: datetime


class JudicialEntity(BaseModel):
    id: str = Field(..., pattern=r"^[a-z]+_[0-9]{4}_[a-z_]+$")
    name: str
    source: str
    desensitize: bool
    create_time: datetime
    update_time: datetime


class LegalSubject(BaseModel):
    id: str = Field(..., pattern=r"^[a-z]+_[0-9]{4}_[a-z_]+$")
    name: str
    source: str
    desensitize: bool
    create_time: datetime
    update_time: datetime


# ==================== 规范层 ====================
class Law(LegalNorm):
    law_level: Literal["constitution", "basic_law", "ordinary_law", "administrative_regulation",
                       "local_regulation", "self_governing_regulation", "military_regulation",
                       "judicial_interpretation", "department_rule", "normative_document"]
    document_number: str
    status: Literal["effective", "amended", "repealed"]
    enactment_date: date
    effective_date: date
    legislative_purpose: Optional[str] = None
    repealed_date: Optional[date] = None


class LegalProvision(LegalNorm):
    law_id: Optional[str] = None
    article: str
    paragraph: Optional[str] = None
    item: Optional[str] = None
    content: Optional[str] = None
    status: Optional[Literal["effective", "amended", "repealed"]] = None
    legislative_purpose: Optional[str] = None
    related_provisions: Optional[List[str]] = None
    repealed_date: Optional[date] = None


class LegalProvisionVersion(LegalNorm):
    provision_id: Optional[str] = None
    version_date: Optional[date] = None
    content: Optional[str] = None
    status: Optional[Literal["effective", "amended", "repealed"]] = None
    superseded_by_version_id: Optional[str] = None
    amendment_reason: Optional[str] = None


class CaseType(LegalNorm):
    code: str
    category: Literal["civil", "criminal", "administrative", "ip", "execution", "state_compensation"]
    level1: str
    level2: str
    description: Optional[str] = None
    typical_provision_ids: Optional[List[str]] = None


class GuidingCase(LegalNorm):
    guiding_case_number: str
    issuing_court_id: str
    publication_date: date
    guiding_points: str
    binding_force: Literal["mandatory", "persuasive", "reference"]
    guiding_points_vector: Optional[List[float]] = None
    related_case_type_ids: Optional[List[str]] = None


class SentencingStandard(LegalNorm):
    case_type_id: Optional[str] = None
    applicable_provision_id: Optional[str] = None
    standard_type: Optional[Literal["criminal_sentence", "civil_compensation", "administrative_penalty"]] = None
    sentence_range_min: Optional[float] = None
    sentence_range_max: Optional[float] = None
    sentence_unit: Optional[Literal["month", "year", "yuan", "percent"]] = None
    circumstance_levels: Optional[List[str]] = None
    measurement_formula: Optional[str] = None
    region_id: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

    @field_validator("sentence_range_max")
    @classmethod
    def max_ge_min(cls, v: float, info) -> float:
        if v < info.data.get("sentence_range_min", float("-inf")):
            raise ValueError("sentence_range_max 必须 >= sentence_range_min")
        return v


# ==================== 主体层 ====================
class Person(LegalSubject):
    type: Literal["natural_person"]
    gender: Optional[Literal["male", "female"]] = None
    birth_date: Optional[date] = None
    nationality: Optional[str] = None
    desensitized_id_number: Optional[str] = Field(None, pattern=r"^\d{6}\*{8}\d{4}$")
    address: Optional[str] = None
    phone: Optional[str] = Field(None, pattern=r"^\d{3}\*{4}\d{4}$")


class Judge(Person):
    court_id: str
    position: str
    judge_level: Optional[str] = None
    appointment_date: Optional[date] = None


class Attorney(Person):
    license_number: str
    law_firm_id: str
    specialization: Optional[str] = None
    bar_association: Optional[str] = None


class Clerk(Person):
    court_id: str
    position: Optional[str] = None


class Prosecutor(Person):
    procuratorate_id: str
    position: str


class Organization(LegalSubject):
    org_type: Literal["company", "government_agency", "ngo", "law_firm",
                      "expert_institution", "court", "procuratorate", "individual_business",
                      "partnership", "sole_proprietorship"]
    credit_code: Optional[str] = Field(None, pattern=r"^[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}$")
    legal_representative: Optional[str] = None
    registered_capital: Optional[float] = None
    business_scope: Optional[str] = None
    legal_name_alias: Optional[str] = None


class Court(Organization):
    court_level: Literal["supreme", "high", "intermediate", "basic", "special"]
    district_id: str
    chambers: Optional[List[str]] = None
    jurisdiction_area: Optional[str] = None


class Procuratorate(Organization):
    procuratorate_level: Literal["supreme", "provincial", "municipal", "district"]
    district_id: str
    departments: Optional[List[str]] = None


class LawFirm(Organization):
    firm_type: Literal["partnership", "limited_liability", "sole_practitioner"]
    license_number: str
    partners: Optional[List[str]] = None
    practice_areas: Optional[List[str]] = None


class ExpertInstitution(Organization):
    expertise_fields: List[str]
    accreditation_number: str
    accreditation_authority: Optional[str] = None
    validity_period: Optional[str] = None


class District(JudicialEntity):
    code: str
    administrative_level: Optional[str] = None
    parent_district_id: Optional[str] = None


class LegalRole(JudicialEntity):
    code: str
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


# ==================== 案件层 ====================
class CourtCase(JudicialEntity):
    case_number: Optional[str] = None
    case_type_id: str
    filing_date: date
    court_id: str
    status: Literal["filing", "trial", "judged", "effective", "appealed", "retried", "executing", "terminated"]
    trial_level: Literal["first_instance", "second_instance", "retrial"]
    dispute_resolution_type: Optional[Literal["litigation", "mediation", "arbitration", "judicial_aid", "administrative_review"]] = None
    claim_amount: Optional[float] = None
    cause_of_action: Optional[str] = None
    summary: Optional[str] = None
    related_cases: Optional[List[str]] = None
    first_instance_case_number: Optional[str] = None
    source_text_hash: Optional[str] = None
    source_text_path: Optional[str] = None


class CaseSummary(JudicialEntity):
    case_id: str
    key_facts: Optional[str] = None
    disputed_issues: Optional[str] = None
    conclusion: Optional[str] = None
    fact_vector: Optional[List[float]] = None
    issue_tags: Optional[List[str]] = None
    amount_involved: Optional[float] = None
    sentencing_referral_id: Optional[str] = None


class TrialOrganization(JudicialEntity):
    organization_type: Literal["sole_judge", "collegiate_bench", "judicial_committee"]
    case_id: str
    judge_ids: Optional[List[str]] = None
    presiding_judge_id: Optional[str] = None
    clerk_id: Optional[str] = None


class JudgmentResult(JudicialEntity):
    case_id: str
    result_type: Optional[Literal["guilty", "not_guilty", "liable", "not_liable", "dismissed", "withdrawn", "mediation_agreement", "arbitration_award", "administrative_decision"]] = None
    judgment_date: Optional[date] = None
    effective_date: Optional[date] = None
    sentence_term: Optional[float] = None
    compensation_amount: Optional[float] = None
    reasoning: Optional[str] = None
    sentencing_standard_id: Optional[str] = None


class ExecutionInfo(JudicialEntity):
    case_id: Optional[str] = None
    execution_status: Optional[Literal["pending", "in_progress", "completed", "terminated"]] = None
    execution_court_id: Optional[str] = None
    execution_amount: Optional[float] = None
    execution_measures: Optional[List[str]] = None
    completion_date: Optional[date] = None


class LegalDocument(JudicialEntity):
    document_type: Optional[Literal["judgment", "ruling", "mediation", "order", "notice", "indictment", "petition"]] = None
    case_id: Optional[str] = None
    creation_date: Optional[date] = None
    signed_by_judge_id: Optional[str] = None
    issuing_court_id: Optional[str] = None
    document_number: Optional[str] = None
    content_hash: Optional[str] = None
    file_path: Optional[str] = None
    content: Optional[str] = None


class Evidence(JudicialEntity):
    evidence_type: Optional[Literal["document", "physical", "digital", "testimony", "expert_opinion"]] = None
    case_id: Optional[str] = None
    submitter_id: Optional[str] = None
    submission_date: Optional[date] = None
    examination_status: Optional[Literal["not_examined", "examined"]] = None
    admission_status: Optional[Literal["admitted", "not_admitted"]] = None
    description: Optional[str] = None
    file_path: Optional[str] = None
    chain_of_custody: Optional[str] = None

    @field_validator("admission_status")
    @classmethod
    def admission_requires_examination(cls, v: str, info) -> str:
        if v == "admitted" and info.data.get("examination_status") != "examined":
            raise ValueError("证据未经质证不得采信")
        return v


class DisputeFocus(JudicialEntity):
    case_id: Optional[str] = None
    content: Optional[str] = None
    focus_category_id: Optional[str] = None
    canonical_template_id: Optional[str] = None


class Fact(JudicialEntity):
    case_id: Optional[str] = None
    content: Optional[str] = None
    fact_type: Optional[Literal["undisputed", "disputed", "to_be_proven"]] = None
    proven_by_evidence_ids: Optional[List[str]] = None


class CaseParticipant(JudicialEntity):
    case_id: str
    subject_id: Optional[str] = None
    role_code: Literal["plaintiff", "defendant", "third_party", "witness", "agent", "expert_witness", "interpreter", "prosecutor", "applicant", "respondent", "relator", "appellant", "appellee", "retrial_applicant", "retrial_respondent", "mediator", "arbitrator", "beneficiary"]
    trial_level: Optional[Literal["first_instance", "second_instance", "retrial", "execution"]] = None
    is_primary: Optional[bool] = None
    role_name: Optional[str] = None


# ==================== 案由法条映射关系 ====================
class TypicallyApplies(BaseModel):
    case_type_id: str
    provision_id: str
    applicability_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_primary: Optional[bool] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    source: Optional[str] = None
