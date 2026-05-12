// Auto-generated ontology data for detail panel
// Generated from legal_ontology_v2.zh.yaml
var ENTITY_DATA = {
  "LegalNorm": {
    "description": "法律规范顶层类",
    "required": [
      "id",
      "name",
      "source",
      "desensitize",
      "create_time",
      "update_time"
    ],
    "optional": [],
    "enums": {},
    "constraints": [],
    "is_a": null
  },
  "JudicialEntity": {
    "description": "司法实体顶层类",
    "required": [
      "id",
      "name",
      "source",
      "desensitize",
      "create_time",
      "update_time"
    ],
    "optional": [],
    "enums": {},
    "constraints": [],
    "is_a": null
  },
  "LegalSubject": {
    "description": "法律主体顶层类",
    "required": [
      "id",
      "name",
      "source",
      "desensitize",
      "create_time",
      "update_time"
    ],
    "optional": [],
    "enums": {},
    "constraints": [],
    "is_a": null
  },
  "Law": {
    "description": "法律",
    "required": [
      "name",
      "law_level",
      "document_number",
      "status",
      "enactment_date",
      "effective_date"
    ],
    "optional": [
      "legislative_purpose",
      "repealed_date"
    ],
    "enums": {
      "law_level": [
        "constitution",
        "basic_law",
        "ordinary_law",
        "administrative_regulation",
        "local_regulation",
        "self_governing_regulation",
        "military_regulation",
        "judicial_interpretation",
        "department_rule",
        "normative_document"
      ],
      "status": [
        "effective",
        "amended",
        "repealed"
      ]
    },
    "constraints": [],
    "is_a": "LegalNorm"
  },
  "LegalProvision": {
    "description": "法律条文（当前生效版本）",
    "required": [
      "article"
    ],
    "optional": [
      "law_id",
      "paragraph",
      "item",
      "content",
      "status",
      "legislative_purpose",
      "related_provisions",
      "repealed_date"
    ],
    "enums": {
      "status": [
        "effective",
        "amended",
        "repealed"
      ]
    },
    "constraints": [],
    "is_a": "LegalNorm"
  },
  "LegalProvisionVersion": {
    "description": "法律条文历史版本",
    "required": [],
    "optional": [
      "provision_id",
      "version_date",
      "content",
      "status",
      "superseded_by_version_id",
      "amendment_reason"
    ],
    "enums": {
      "status": [
        "effective",
        "amended",
        "repealed"
      ]
    },
    "constraints": [],
    "is_a": "LegalNorm"
  },
  "CaseType": {
    "description": "案由类型",
    "required": [
      "code",
      "category",
      "level1",
      "level2"
    ],
    "optional": [
      "description",
      "typical_provision_ids"
    ],
    "enums": {
      "category": [
        "civil",
        "criminal",
        "administrative",
        "ip",
        "execution",
        "state_compensation"
      ]
    },
    "constraints": [],
    "is_a": "LegalNorm"
  },
  "GuidingCase": {
    "description": "指导性案例",
    "required": [
      "guiding_case_number",
      "issuing_court_id",
      "publication_date",
      "guiding_points",
      "binding_force"
    ],
    "optional": [
      "guiding_points_vector",
      "related_case_type_ids"
    ],
    "enums": {
      "binding_force": [
        "mandatory",
        "persuasive",
        "reference"
      ]
    },
    "constraints": [],
    "is_a": "LegalNorm"
  },
  "SentencingStandard": {
    "description": "量刑/赔偿标准",
    "required": [
      "case_type_id",
      "applicable_provision_id",
      "standard_type",
      "sentence_range_min",
      "sentence_range_max",
      "sentence_unit"
    ],
    "optional": [
      "circumstance_levels",
      "measurement_formula",
      "region_id",
      "valid_from",
      "valid_to"
    ],
    "enums": {
      "standard_type": [
        "criminal_sentence",
        "civil_compensation",
        "administrative_penalty"
      ],
      "sentence_unit": [
        "month",
        "year",
        "yuan",
        "percent"
      ]
    },
    "constraints": [
      "sentence_range_min <= sentence_range_max",
      {
        "rule": "sentence_range_min <= sentence_range_max",
        "enforcement": "block",
        "description": "量刑下限不得高于上限"
      }
    ],
    "is_a": "LegalNorm"
  },
  "typically_applies": {
    "description": "案由典型适用的法律条文（用于法条补提和类案推荐）",
    "required": [],
    "optional": [],
    "enums": {},
    "constraints": [],
    "is_a": null
  },
  "Person": {
    "description": "自然人（跨案件不消歧，每个案件独立节点）",
    "required": [],
    "optional": [],
    "enums": {},
    "constraints": [],
    "is_a": null
  },
  "Judge": {
    "description": "法官",
    "required": [
      "court_id",
      "position"
    ],
    "optional": [
      "judge_level",
      "appointment_date"
    ],
    "enums": {},
    "constraints": [],
    "is_a": "Person"
  },
  "Attorney": {
    "description": "律师",
    "required": [
      "license_number",
      "law_firm_id"
    ],
    "optional": [
      "specialization",
      "bar_association"
    ],
    "enums": {},
    "constraints": [],
    "is_a": "Person"
  },
  "Clerk": {
    "description": "书记员",
    "required": [
      "court_id"
    ],
    "optional": [
      "position"
    ],
    "enums": {},
    "constraints": [],
    "is_a": "Person"
  },
  "Prosecutor": {
    "description": "检察官",
    "required": [
      "procuratorate_id",
      "position"
    ],
    "optional": [],
    "enums": {},
    "constraints": [],
    "is_a": "Person"
  },
  "Organization": {
    "description": "组织机构（企业用credit_code跨案件全局关联，包含法人实体、个体工商户、合伙企业、个人独资企业）",
    "required": [
      "org_type"
    ],
    "optional": [
      "credit_code",
      "legal_representative",
      "registered_capital",
      "business_scope",
      "legal_name_alias"
    ],
    "enums": {
      "org_type": [
        "company",
        "government_agency",
        "ngo",
        "law_firm",
        "expert_institution",
        "court",
        "procuratorate",
        "individual_business",
        "partnership",
        "sole_proprietorship"
      ]
    },
    "constraints": [
      {
        "rule": "credit_code =~ /^[0-9A-HJ-NPQRTUWXY]{2}\\d{6}[0-9A-HJ-NPQRTUWXY]{10}$/",
        "enforcement": "block",
        "description": "统一社会信用代码18位校验"
      }
    ],
    "is_a": "LegalSubject"
  },
  "Court": {
    "description": "法院",
    "required": [
      "court_level",
      "district_id"
    ],
    "optional": [
      "chambers",
      "jurisdiction_area"
    ],
    "enums": {
      "court_level": [
        "supreme",
        "high",
        "intermediate",
        "basic",
        "special"
      ]
    },
    "constraints": [],
    "is_a": "Organization"
  },
  "Procuratorate": {
    "description": "检察院",
    "required": [
      "procuratorate_level",
      "district_id"
    ],
    "optional": [
      "departments"
    ],
    "enums": {
      "procuratorate_level": [
        "supreme",
        "provincial",
        "municipal",
        "district"
      ]
    },
    "constraints": [],
    "is_a": "Organization"
  },
  "LawFirm": {
    "description": "律师事务所",
    "required": [
      "firm_type",
      "license_number"
    ],
    "optional": [
      "partners",
      "practice_areas"
    ],
    "enums": {
      "firm_type": [
        "partnership",
        "limited_liability",
        "sole_practitioner"
      ]
    },
    "constraints": [],
    "is_a": "Organization"
  },
  "ExpertInstitution": {
    "description": "鉴定机构",
    "required": [
      "expertise_fields",
      "accreditation_number"
    ],
    "optional": [
      "accreditation_authority",
      "validity_period"
    ],
    "enums": {},
    "constraints": [],
    "is_a": "Organization"
  },
  "District": {
    "description": "辖区",
    "required": [
      "name",
      "code"
    ],
    "optional": [
      "administrative_level",
      "parent_district_id"
    ],
    "enums": {},
    "constraints": [],
    "is_a": "JudicialEntity"
  },
  "LegalRole": {
    "description": "法律角色",
    "required": [
      "name",
      "code"
    ],
    "optional": [
      "description",
      "permissions"
    ],
    "enums": {
      "role": [
        "plaintiff",
        "defendant",
        "third_party",
        "witness",
        "agent",
        "expert_witness",
        "interpreter",
        "prosecutor",
        "applicant",
        "respondent",
        "relator",
        "appellant",
        "appellee",
        "retrial_applicant",
        "retrial_respondent",
        "mediator",
        "arbitrator",
        "beneficiary"
      ]
    },
    "constraints": [],
    "is_a": "JudicialEntity"
  },
  "CourtCase": {
    "description": "法院案件（精简节点，全文存ES）",
    "required": [
      "case_type_id",
      "filing_date",
      "court_id",
      "status",
      "trial_level"
    ],
    "optional": [
      "case_number",
      "claim_amount",
      "cause_of_action",
      "summary",
      "related_cases",
      "first_instance_case_number",
      "source_text_hash",
      "source_text_path",
      "dispute_resolution_type"
    ],
    "enums": {
      "trial_level": [
        "first_instance",
        "second_instance",
        "retrial"
      ],
      "status": [
        "filing",
        "trial",
        "judged",
        "effective",
        "appealed",
        "retried",
        "executing",
        "terminated"
      ],
      "dispute_resolution_type": [
        "litigation",
        "mediation",
        "arbitration",
        "judicial_aid",
        "administrative_review"
      ]
    },
    "constraints": [
      {
        "rule": "case_number =~ /^\\(\\d{4}\\)[\\u4e00-\\u9fa5]{1,5}\\d+([民刑行执])\\d+第\\d+号$/",
        "enforcement": "block",
        "description": "民/刑/行/执案号统一校验"
      },
      {
        "rule": "filing_date < judgment_date AND judgment_date < effective_date",
        "enforcement": "block",
        "description": "立案<裁判<生效"
      },
      {
        "rule": "trial_level == 'second_instance' IMPLIES first_instance_case_number IS NOT NULL",
        "enforcement": "block",
        "description": "二审必须有一审案号"
      },
      {
        "rule": "ALL x IN cites WHERE x.status == 'effective'",
        "enforcement": "soft",
        "description": "仅引用有效法条（软约束：允许历史案件引用当时有效现已废止的法条）"
      },
      {
        "rule": "Court.id == court_id AND Court.court_level == 'supreme' IMPLIES trial_level != 'second_instance'",
        "enforcement": "block",
        "description": "最高院判决不得上诉"
      }
    ],
    "is_a": "JudicialEntity"
  },
  "CaseSummary": {
    "description": "案件结构化摘要（用于热层类案相似度计算）",
    "required": [
      "case_id"
    ],
    "optional": [
      "key_facts",
      "disputed_issues",
      "conclusion",
      "fact_vector",
      "issue_tags",
      "amount_involved",
      "sentencing_referral_id"
    ],
    "enums": {},
    "constraints": [],
    "is_a": "JudicialEntity"
  },
  "TrialOrganization": {
    "description": "审判组织",
    "required": [
      "organization_type",
      "case_id"
    ],
    "optional": [
      "judge_ids",
      "presiding_judge_id",
      "clerk_id"
    ],
    "enums": {
      "organization_type": [
        "sole_judge",
        "collegiate_bench",
        "judicial_committee"
      ]
    },
    "constraints": [],
    "is_a": "JudicialEntity"
  },
  "JudgmentResult": {
    "description": "裁判结果",
    "required": [
      "case_id",
      "result_type"
    ],
    "optional": [
      "judgment_date",
      "effective_date",
      "sentence_term",
      "compensation_amount",
      "reasoning",
      "sentencing_standard_id"
    ],
    "enums": {
      "result_type": [
        "guilty",
        "not_guilty",
        "liable",
        "not_liable",
        "dismissed",
        "withdrawn",
        "mediation_agreement",
        "arbitration_award",
        "administrative_decision"
      ]
    },
    "constraints": [],
    "is_a": "JudicialEntity"
  },
  "ExecutionInfo": {
    "description": "执行信息",
    "required": [],
    "optional": [
      "case_id",
      "execution_status",
      "execution_court_id",
      "execution_amount",
      "execution_measures",
      "completion_date"
    ],
    "enums": {
      "execution_status": [
        "pending",
        "in_progress",
        "completed",
        "terminated"
      ]
    },
    "constraints": [],
    "is_a": "JudicialEntity"
  },
  "LegalDocument": {
    "description": "法律文书",
    "required": [],
    "optional": [
      "document_type",
      "case_id",
      "creation_date",
      "signed_by_judge_id",
      "issuing_court_id",
      "document_number",
      "content_hash",
      "file_path",
      "content"
    ],
    "enums": {
      "document_type": [
        "judgment",
        "ruling",
        "mediation",
        "order",
        "notice",
        "indictment",
        "petition"
      ]
    },
    "constraints": [],
    "is_a": "JudicialEntity"
  },
  "Evidence": {
    "description": "证据",
    "required": [],
    "optional": [
      "evidence_type",
      "case_id",
      "submitter_id",
      "submission_date",
      "examination_status",
      "admission_status",
      "description",
      "file_path",
      "chain_of_custody"
    ],
    "enums": {
      "evidence_type": [
        "document",
        "physical",
        "digital",
        "testimony",
        "expert_opinion"
      ],
      "examination_status": [
        "not_examined",
        "examined"
      ],
      "admission_status": [
        "admitted",
        "not_admitted"
      ],
      "probative_force": [
        "valid",
        "invalid"
      ]
    },
    "constraints": [
      {
        "rule": "admission_status == 'admitted' IMPLIES examination_status == 'examined'",
        "enforcement": "block",
        "description": "证据未经质证不得采信"
      }
    ],
    "is_a": "JudicialEntity"
  },
  "DisputeFocus": {
    "description": "案件争议焦点",
    "required": [],
    "optional": [
      "case_id",
      "content",
      "focus_category_id",
      "canonical_template_id"
    ],
    "enums": {},
    "constraints": [],
    "is_a": "JudicialEntity"
  },
  "Fact": {
    "description": "案件事实",
    "required": [],
    "optional": [
      "case_id",
      "content",
      "fact_type",
      "proven_by_evidence_ids"
    ],
    "enums": {
      "fact_type": [
        "undisputed",
        "disputed",
        "to_be_proven"
      ]
    },
    "constraints": [],
    "is_a": "JudicialEntity"
  },
  "CaseParticipant": {
    "description": "案件参与人（含审级角色变更）",
    "required": [
      "case_id",
      "role_code"
    ],
    "optional": [
      "subject_id",
      "trial_level",
      "is_primary",
      "role_name"
    ],
    "enums": {
      "role_code": [
        "plaintiff",
        "defendant",
        "third_party",
        "witness",
        "agent",
        "expert_witness",
        "interpreter",
        "prosecutor",
        "applicant",
        "respondent",
        "relator",
        "appellant",
        "appellee",
        "retrial_applicant",
        "retrial_respondent",
        "mediator",
        "arbitrator",
        "beneficiary"
      ]
    },
    "constraints": [],
    "is_a": "JudicialEntity"
  },
  "LegalProvisionElement": {
    "description": "法条构成要件要素（主体/行为/结果/因果关系/主观要件等结构化分解，用于事实→法条匹配推理）",
    "required": [
      "provision_id",
      "element_type"
    ],
    "optional": [
      "content",
      "applicable_fact_pattern"
    ],
    "enums": {
      "element_type": [
        "subject_element",
        "object_element",
        "act_element",
        "result_element",
        "causality_element",
        "subjective_element",
        "legal_consequence",
        "exception_clause"
      ]
    },
    "constraints": [],
    "is_a": null
  }
};

var RELATIONS_BY_ENTITY = {
  "LegalProvision": {
    "outgoing": [
      {
        "relation": "belongs_to",
        "target": "Law",
        "cardinality": "many_to_one",
        "description": "法律条文归属法律",
        "attributes": []
      },
      {
        "relation": "has_version",
        "target": "LegalProvisionVersion",
        "cardinality": "one_to_many",
        "description": "法条具有历史版本",
        "attributes": []
      }
    ],
    "incoming": [
      {
        "relation": "cites",
        "source": "CourtCase",
        "cardinality": "many_to_many",
        "description": "案件引用法律条文",
        "attributes": [
          "citation_position",
          "citation_purpose",
          "context"
        ]
      },
      {
        "relation": "judgment_cites",
        "source": "JudgmentResult",
        "cardinality": "many_to_many",
        "description": "裁判结果依据法律条文",
        "attributes": []
      },
      {
        "relation": "resolved_by",
        "source": "DisputeFocus",
        "cardinality": "many_to_many",
        "description": "争议焦点由法律条文解决（争议焦点→法条映射）",
        "attributes": []
      }
    ]
  },
  "Law": {
    "outgoing": [],
    "incoming": [
      {
        "relation": "belongs_to",
        "source": "LegalProvision",
        "cardinality": "many_to_one",
        "description": "法律条文归属法律",
        "attributes": []
      }
    ]
  },
  "LegalProvisionVersion": {
    "outgoing": [
      {
        "relation": "superseded_by",
        "target": "LegalProvisionVersion",
        "cardinality": "one_to_one",
        "description": "旧版本被新版本替代",
        "attributes": []
      }
    ],
    "incoming": [
      {
        "relation": "has_version",
        "source": "LegalProvision",
        "cardinality": "one_to_many",
        "description": "法条具有历史版本",
        "attributes": []
      },
      {
        "relation": "superseded_by",
        "source": "LegalProvisionVersion",
        "cardinality": "one_to_one",
        "description": "旧版本被新版本替代",
        "attributes": []
      }
    ]
  },
  "GuidingCase": {
    "outgoing": [
      {
        "relation": "guides_case_type",
        "target": "CaseType",
        "cardinality": "one_to_many",
        "description": "指导性案例指导案由适用",
        "attributes": []
      }
    ],
    "incoming": [
      {
        "relation": "cites_guiding_case",
        "source": "CourtCase",
        "cardinality": "many_to_many",
        "description": "案件引用指导性案例",
        "attributes": []
      }
    ]
  },
  "CaseType": {
    "outgoing": [],
    "incoming": [
      {
        "relation": "guides_case_type",
        "source": "GuidingCase",
        "cardinality": "one_to_many",
        "description": "指导性案例指导案由适用",
        "attributes": []
      },
      {
        "relation": "has_case_type",
        "source": "CourtCase",
        "cardinality": "one_to_many",
        "description": "案件具有案由类型",
        "attributes": []
      }
    ]
  },
  "CourtCase": {
    "outgoing": [
      {
        "relation": "cites_guiding_case",
        "target": "GuidingCase",
        "cardinality": "many_to_many",
        "description": "案件引用指导性案例",
        "attributes": []
      },
      {
        "relation": "applies_standard",
        "target": "SentencingStandard",
        "cardinality": "many_to_many",
        "description": "案件适用量刑/赔偿标准",
        "attributes": []
      },
      {
        "relation": "has_summary",
        "target": "CaseSummary",
        "cardinality": "one_to_one",
        "description": "案件具有结构化摘要",
        "attributes": []
      },
      {
        "relation": "tried_by",
        "target": "TrialOrganization",
        "cardinality": "one_to_one",
        "description": "案件由审判组织审理",
        "attributes": []
      },
      {
        "relation": "has_case_type",
        "target": "CaseType",
        "cardinality": "one_to_many",
        "description": "案件具有案由类型",
        "attributes": []
      },
      {
        "relation": "cites",
        "target": "LegalProvision",
        "cardinality": "many_to_many",
        "description": "案件引用法律条文",
        "attributes": [
          "citation_position",
          "citation_purpose",
          "context"
        ]
      },
      {
        "relation": "appeals_to",
        "target": "CourtCase",
        "cardinality": "one_to_one",
        "description": "二审案件上诉一审案件",
        "attributes": []
      },
      {
        "relation": "retries_from",
        "target": "CourtCase",
        "cardinality": "one_to_one",
        "description": "再审案件源自原审案件",
        "attributes": []
      },
      {
        "relation": "has_dispute_focus",
        "target": "DisputeFocus",
        "cardinality": "one_to_many",
        "description": "案件具有争议焦点",
        "attributes": []
      },
      {
        "relation": "has_fact",
        "target": "Fact",
        "cardinality": "one_to_many",
        "description": "案件具有事实",
        "attributes": []
      }
    ],
    "incoming": [
      {
        "relation": "undertakes",
        "source": "Judge",
        "cardinality": "one_to_many",
        "description": "法官承办案件",
        "attributes": []
      },
      {
        "relation": "prosecutes",
        "source": "Procuratorate",
        "cardinality": "one_to_many",
        "description": "检察院公诉案件",
        "attributes": []
      },
      {
        "relation": "submitted_for",
        "source": "Evidence",
        "cardinality": "many_to_one",
        "description": "证据提交给案件",
        "attributes": []
      },
      {
        "relation": "appeals_to",
        "source": "CourtCase",
        "cardinality": "one_to_one",
        "description": "二审案件上诉一审案件",
        "attributes": []
      },
      {
        "relation": "retries_from",
        "source": "CourtCase",
        "cardinality": "one_to_one",
        "description": "再审案件源自原审案件",
        "attributes": []
      }
    ]
  },
  "SentencingStandard": {
    "outgoing": [],
    "incoming": [
      {
        "relation": "applies_standard",
        "source": "CourtCase",
        "cardinality": "many_to_many",
        "description": "案件适用量刑/赔偿标准",
        "attributes": []
      }
    ]
  },
  "CaseSummary": {
    "outgoing": [],
    "incoming": [
      {
        "relation": "has_summary",
        "source": "CourtCase",
        "cardinality": "one_to_one",
        "description": "案件具有结构化摘要",
        "attributes": []
      }
    ]
  },
  "TrialOrganization": {
    "outgoing": [
      {
        "relation": "includes",
        "target": "Judge",
        "cardinality": "one_to_many",
        "description": "审判组织包含法官",
        "attributes": []
      },
      {
        "relation": "includes_clerk",
        "target": "Clerk",
        "cardinality": "one_to_one",
        "description": "审判组织配备书记员",
        "attributes": []
      }
    ],
    "incoming": [
      {
        "relation": "tried_by",
        "source": "CourtCase",
        "cardinality": "one_to_one",
        "description": "案件由审判组织审理",
        "attributes": []
      },
      {
        "relation": "presides_over",
        "source": "Judge",
        "cardinality": "one_to_one",
        "description": "法官主持审判组织",
        "attributes": []
      }
    ]
  },
  "Judge": {
    "outgoing": [
      {
        "relation": "presides_over",
        "target": "TrialOrganization",
        "cardinality": "one_to_one",
        "description": "法官主持审判组织",
        "attributes": []
      },
      {
        "relation": "undertakes",
        "target": "CourtCase",
        "cardinality": "one_to_many",
        "description": "法官承办案件",
        "attributes": []
      }
    ],
    "incoming": [
      {
        "relation": "signed_by",
        "source": "LegalDocument",
        "cardinality": "many_to_one",
        "description": "文书由法官签署",
        "attributes": []
      },
      {
        "relation": "includes",
        "source": "TrialOrganization",
        "cardinality": "one_to_many",
        "description": "审判组织包含法官",
        "attributes": []
      }
    ]
  },
  "LegalSubject": {
    "outgoing": [
      {
        "relation": "plays_role",
        "target": "LegalRole",
        "cardinality": "many_to_many",
        "description": "主体在案件中担任角色",
        "attributes": [
          "case_id",
          "start_time",
          "end_time",
          "role_description"
        ]
      }
    ],
    "incoming": [
      {
        "relation": "represents",
        "source": "Attorney",
        "cardinality": "many_to_many",
        "description": "律师代理当事人",
        "attributes": [
          "case_id",
          "authorization_scope",
          "authorization_period_start",
          "authorization_period_end"
        ]
      }
    ]
  },
  "LegalRole": {
    "outgoing": [],
    "incoming": [
      {
        "relation": "plays_role",
        "source": "LegalSubject",
        "cardinality": "many_to_many",
        "description": "主体在案件中担任角色",
        "attributes": [
          "case_id",
          "start_time",
          "end_time",
          "role_description"
        ]
      }
    ]
  },
  "Court": {
    "outgoing": [
      {
        "relation": "has_jurisdiction_over",
        "target": "District",
        "cardinality": "one_to_one",
        "description": "法院管辖辖区",
        "attributes": []
      }
    ],
    "incoming": []
  },
  "District": {
    "outgoing": [],
    "incoming": [
      {
        "relation": "has_jurisdiction_over",
        "source": "Court",
        "cardinality": "one_to_one",
        "description": "法院管辖辖区",
        "attributes": []
      }
    ]
  },
  "Procuratorate": {
    "outgoing": [
      {
        "relation": "prosecutes",
        "target": "CourtCase",
        "cardinality": "one_to_many",
        "description": "检察院公诉案件",
        "attributes": []
      },
      {
        "relation": "employs",
        "target": "Prosecutor",
        "cardinality": "one_to_many",
        "description": "检察院雇佣检察官",
        "attributes": []
      }
    ],
    "incoming": []
  },
  "ExecutionInfo": {
    "outgoing": [
      {
        "relation": "based_on",
        "target": "JudgmentResult",
        "cardinality": "one_to_one",
        "description": "执行依据裁判结果",
        "attributes": []
      }
    ],
    "incoming": []
  },
  "JudgmentResult": {
    "outgoing": [
      {
        "relation": "judgment_cites",
        "target": "LegalProvision",
        "cardinality": "many_to_many",
        "description": "裁判结果依据法律条文",
        "attributes": []
      }
    ],
    "incoming": [
      {
        "relation": "based_on",
        "source": "ExecutionInfo",
        "cardinality": "one_to_one",
        "description": "执行依据裁判结果",
        "attributes": []
      },
      {
        "relation": "leads_to",
        "source": "Fact",
        "cardinality": "many_to_many",
        "description": "事实/争议焦点推导出裁判结果（三段论推理的结论链路）",
        "attributes": []
      },
      {
        "relation": "leads_to",
        "source": "DisputeFocus",
        "cardinality": "many_to_many",
        "description": "事实/争议焦点推导出裁判结果（三段论推理的结论链路）",
        "attributes": []
      }
    ]
  },
  "LegalDocument": {
    "outgoing": [
      {
        "relation": "signed_by",
        "target": "Judge",
        "cardinality": "many_to_one",
        "description": "文书由法官签署",
        "attributes": []
      }
    ],
    "incoming": []
  },
  "Attorney": {
    "outgoing": [
      {
        "relation": "represents",
        "target": "LegalSubject",
        "cardinality": "many_to_many",
        "description": "律师代理当事人",
        "attributes": [
          "case_id",
          "authorization_scope",
          "authorization_period_start",
          "authorization_period_end"
        ]
      }
    ],
    "incoming": [
      {
        "relation": "employs_attorney",
        "source": "LawFirm",
        "cardinality": "one_to_many",
        "description": "律所雇佣律师",
        "attributes": []
      }
    ]
  },
  "Prosecutor": {
    "outgoing": [],
    "incoming": [
      {
        "relation": "employs",
        "source": "Procuratorate",
        "cardinality": "one_to_many",
        "description": "检察院雇佣检察官",
        "attributes": []
      }
    ]
  },
  "LawFirm": {
    "outgoing": [
      {
        "relation": "employs_attorney",
        "target": "Attorney",
        "cardinality": "one_to_many",
        "description": "律所雇佣律师",
        "attributes": []
      }
    ],
    "incoming": []
  },
  "Evidence": {
    "outgoing": [
      {
        "relation": "submitted_for",
        "target": "CourtCase",
        "cardinality": "many_to_one",
        "description": "证据提交给案件",
        "attributes": []
      },
      {
        "relation": "proves_fact",
        "target": "Fact",
        "cardinality": "many_to_many",
        "description": "证据证明案件事实/争议焦点",
        "attributes": []
      },
      {
        "relation": "proves_fact",
        "target": "DisputeFocus",
        "cardinality": "many_to_many",
        "description": "证据证明案件事实/争议焦点",
        "attributes": []
      }
    ],
    "incoming": []
  },
  "Fact": {
    "outgoing": [
      {
        "relation": "matches_element",
        "target": "LegalProvisionElement",
        "cardinality": "many_to_many",
        "description": "案件事实匹配法条构成要件要素（三段论推理的小前提→大前提匹配）",
        "attributes": [
          "match_score",
          "match_reasoning"
        ]
      },
      {
        "relation": "leads_to",
        "target": "JudgmentResult",
        "cardinality": "many_to_many",
        "description": "事实/争议焦点推导出裁判结果（三段论推理的结论链路）",
        "attributes": []
      }
    ],
    "incoming": [
      {
        "relation": "proves_fact",
        "source": "Evidence",
        "cardinality": "many_to_many",
        "description": "证据证明案件事实/争议焦点",
        "attributes": []
      },
      {
        "relation": "has_fact",
        "source": "CourtCase",
        "cardinality": "one_to_many",
        "description": "案件具有事实",
        "attributes": []
      }
    ]
  },
  "DisputeFocus": {
    "outgoing": [
      {
        "relation": "resolved_by",
        "target": "LegalProvision",
        "cardinality": "many_to_many",
        "description": "争议焦点由法律条文解决（争议焦点→法条映射）",
        "attributes": []
      },
      {
        "relation": "leads_to",
        "target": "JudgmentResult",
        "cardinality": "many_to_many",
        "description": "事实/争议焦点推导出裁判结果（三段论推理的结论链路）",
        "attributes": []
      }
    ],
    "incoming": [
      {
        "relation": "proves_fact",
        "source": "Evidence",
        "cardinality": "many_to_many",
        "description": "证据证明案件事实/争议焦点",
        "attributes": []
      },
      {
        "relation": "has_dispute_focus",
        "source": "CourtCase",
        "cardinality": "one_to_many",
        "description": "案件具有争议焦点",
        "attributes": []
      }
    ]
  },
  "Clerk": {
    "outgoing": [],
    "incoming": [
      {
        "relation": "includes_clerk",
        "source": "TrialOrganization",
        "cardinality": "one_to_one",
        "description": "审判组织配备书记员",
        "attributes": []
      }
    ]
  },
  "LegalProvisionElement": {
    "outgoing": [],
    "incoming": [
      {
        "relation": "matches_element",
        "source": "Fact",
        "cardinality": "many_to_many",
        "description": "案件事实匹配法条构成要件要素（三段论推理的小前提→大前提匹配）",
        "attributes": [
          "match_score",
          "match_reasoning"
        ]
      }
    ]
  }
};

var RELATION_DETAILS = {
  "belongs_to": {
    "name": "belongs_to",
    "cardinality": "many_to_one",
    "description": "法律条文归属法律",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "has_version": {
    "name": "has_version",
    "cardinality": "one_to_many",
    "description": "法条具有历史版本",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "superseded_by": {
    "name": "superseded_by",
    "cardinality": "one_to_one",
    "description": "旧版本被新版本替代",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "guides_case_type": {
    "name": "guides_case_type",
    "cardinality": "one_to_many",
    "description": "指导性案例指导案由适用",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "cites_guiding_case": {
    "name": "cites_guiding_case",
    "cardinality": "many_to_many",
    "description": "案件引用指导性案例",
    "attributes": [],
    "optional_attributes": [
      "citation_purpose",
      "similarity_score"
    ],
    "acyclic": false
  },
  "applies_standard": {
    "name": "applies_standard",
    "cardinality": "many_to_many",
    "description": "案件适用量刑/赔偿标准",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "has_summary": {
    "name": "has_summary",
    "cardinality": "one_to_one",
    "description": "案件具有结构化摘要",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "tried_by": {
    "name": "tried_by",
    "cardinality": "one_to_one",
    "description": "案件由审判组织审理",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "presides_over": {
    "name": "presides_over",
    "cardinality": "one_to_one",
    "description": "法官主持审判组织",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "undertakes": {
    "name": "undertakes",
    "cardinality": "one_to_many",
    "description": "法官承办案件",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "plays_role": {
    "name": "plays_role",
    "cardinality": "many_to_many",
    "description": "主体在案件中担任角色",
    "attributes": [
      "case_id",
      "start_time",
      "end_time",
      "role_description"
    ],
    "optional_attributes": [],
    "acyclic": false
  },
  "has_jurisdiction_over": {
    "name": "has_jurisdiction_over",
    "cardinality": "one_to_one",
    "description": "法院管辖辖区",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "prosecutes": {
    "name": "prosecutes",
    "cardinality": "one_to_many",
    "description": "检察院公诉案件",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "based_on": {
    "name": "based_on",
    "cardinality": "one_to_one",
    "description": "执行依据裁判结果",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "signed_by": {
    "name": "signed_by",
    "cardinality": "many_to_one",
    "description": "文书由法官签署",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "has_case_type": {
    "name": "has_case_type",
    "cardinality": "one_to_many",
    "description": "案件具有案由类型",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "cites": {
    "name": "cites",
    "cardinality": "many_to_many",
    "description": "案件引用法律条文",
    "attributes": [
      "citation_position",
      "citation_purpose",
      "context"
    ],
    "optional_attributes": [],
    "acyclic": false
  },
  "judgment_cites": {
    "name": "judgment_cites",
    "cardinality": "many_to_many",
    "description": "裁判结果依据法律条文",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "represents": {
    "name": "represents",
    "cardinality": "many_to_many",
    "description": "律师代理当事人",
    "attributes": [
      "case_id",
      "authorization_scope",
      "authorization_period_start",
      "authorization_period_end"
    ],
    "optional_attributes": [],
    "acyclic": false
  },
  "employs": {
    "name": "employs",
    "cardinality": "one_to_many",
    "description": "检察院雇佣检察官",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "employs_attorney": {
    "name": "employs_attorney",
    "cardinality": "one_to_many",
    "description": "律所雇佣律师",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "submitted_for": {
    "name": "submitted_for",
    "cardinality": "many_to_one",
    "description": "证据提交给案件",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "proves_fact___Fact": {
    "name": "proves_fact",
    "cardinality": "many_to_many",
    "description": "证据证明案件事实/争议焦点",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "proves_fact___DisputeFocus": {
    "name": "proves_fact",
    "cardinality": "many_to_many",
    "description": "证据证明案件事实/争议焦点",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "includes": {
    "name": "includes",
    "cardinality": "one_to_many",
    "description": "审判组织包含法官",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "includes_clerk": {
    "name": "includes_clerk",
    "cardinality": "one_to_one",
    "description": "审判组织配备书记员",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "appeals_to": {
    "name": "appeals_to",
    "cardinality": "one_to_one",
    "description": "二审案件上诉一审案件",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": true
  },
  "retries_from": {
    "name": "retries_from",
    "cardinality": "one_to_one",
    "description": "再审案件源自原审案件",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": true
  },
  "has_dispute_focus": {
    "name": "has_dispute_focus",
    "cardinality": "one_to_many",
    "description": "案件具有争议焦点",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "has_fact": {
    "name": "has_fact",
    "cardinality": "one_to_many",
    "description": "案件具有事实",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "matches_element": {
    "name": "matches_element",
    "cardinality": "many_to_many",
    "description": "案件事实匹配法条构成要件要素（三段论推理的小前提→大前提匹配）",
    "attributes": [
      "match_score",
      "match_reasoning"
    ],
    "optional_attributes": [],
    "acyclic": false
  },
  "resolved_by": {
    "name": "resolved_by",
    "cardinality": "many_to_many",
    "description": "争议焦点由法律条文解决（争议焦点→法条映射）",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  },
  "leads_to": {
    "name": "leads_to",
    "cardinality": "many_to_many",
    "description": "事实/争议焦点推导出裁判结果（三段论推理的结论链路）",
    "attributes": [],
    "optional_attributes": [],
    "acyclic": false
  }
};