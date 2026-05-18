// Auto-generated file. Do not edit by hand.
// Source: ontology/schemas/legal_ontology_v2.yaml + ontology/schemas/legal_ontology_v2.zh.yaml
export const ENTITY_DATA = {
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
      "repealed_date",
      "references"
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
      "sentence_range_min <= sentence_range_max"
    ],
    "is_a": "LegalNorm"
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
    "constraints": [],
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
        "beneficiary",
        "victim",
        "criminal_defendant",
        "enforcement_applicant",
        "enforcement_respondent",
        "judicial_review_applicant",
        "insolvency_debtor",
        "surety",
        "class_representative",
        "insurer"
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
      "dispute_resolution_type",
      "party_count"
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
    "constraints": [],
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
      "sentencing_referral_id",
      "claim_amount",
      "judgment_amount"
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
      "sentencing_standard_id",
      "cost_allocation"
    ],
    "enums": {
      "result_type": [
        "guilty",
        "not_guilty",
        "liable",
        "not_liable",
        "dismissed",
        "withdrawn",
        "partially_upheld",
        "remanded",
        "punitive_damages",
        "procedural_ruling",
        "bankruptcy_declared",
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
      "chain_of_custody",
      "expert_institution",
      "expert_conclusion"
    ],
    "enums": {
      "evidence_type": [
        "documentary",
        "physical",
        "audio_visual",
        "electronic_data",
        "witness_testimony",
        "party_statement",
        "expert_opinion",
        "inspection_record"
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
    "constraints": [],
    "is_a": "JudicialEntity"
  },
  "DisputeFocus": {
    "description": "案件争议焦点",
    "required": [],
    "optional": [
      "case_id",
      "content",
      "focus_category_id",
      "canonical_template_id",
      "resolved_by_provision_ids",
      "resolution_logic"
    ],
    "enums": {},
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
        "beneficiary",
        "victim",
        "criminal_defendant",
        "enforcement_applicant",
        "enforcement_respondent",
        "judicial_review_applicant",
        "insolvency_debtor",
        "surety",
        "class_representative"
      ]
    },
    "constraints": [],
    "is_a": "JudicialEntity"
  }
};
let RELATIONS_BY_ENTITY = {
  "LegalNorm": {
    "outgoing": [],
    "incoming": []
  },
  "JudicialEntity": {
    "outgoing": [],
    "incoming": []
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
        "relation": "typically_applies",
        "source": "CaseType",
        "cardinality": "many_to_many",
        "description": "案由典型适用的法律条文（用于法条补提和类案推荐）",
        "attributes": [
          "applicability_score",
          "is_primary",
          "effective_from",
          "effective_to",
          "source"
        ]
      },
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
  "CaseType": {
    "outgoing": [
      {
        "relation": "typically_applies",
        "target": "LegalProvision",
        "cardinality": "many_to_many",
        "description": "案由典型适用的法律条文（用于法条补提和类案推荐）",
        "attributes": [
          "applicability_score",
          "is_primary",
          "effective_from",
          "effective_to",
          "source"
        ]
      }
    ],
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
        "attributes": [
          "citation_purpose",
          "similarity_score"
        ]
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
  "Person": {
    "outgoing": [],
    "incoming": []
  },
  "Judge": {
    "outgoing": [
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
        "attributes": [
          "is_presiding"
        ]
      }
    ]
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
  "Organization": {
    "outgoing": [],
    "incoming": []
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
  "ExpertInstitution": {
    "outgoing": [],
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
  "CourtCase": {
    "outgoing": [
      {
        "relation": "cites_guiding_case",
        "target": "GuidingCase",
        "cardinality": "many_to_many",
        "description": "案件引用指导性案例",
        "attributes": [
          "citation_purpose",
          "similarity_score"
        ]
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
        "attributes": [
          "is_presiding"
        ]
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
      }
    ]
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
  "CaseParticipant": {
    "outgoing": [],
    "incoming": []
  }
};
let RELATION_DETAILS = {
  "typically_applies": {
    "name": "typically_applies",
    "cardinality": "many_to_many",
    "description": "案由典型适用的法律条文（用于法条补提和类案推荐）",
    "attributes": [
      "applicability_score",
      "is_primary",
      "effective_from",
      "effective_to",
      "source"
    ],
    "optional_attributes": [],
    "acyclic": false
  },
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
  "proves_fact": {
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
    "attributes": [
      "is_presiding"
    ],
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
let ROOT_COLORS = {
  "LegalNorm": {
    "bg": "#2980b9",
    "border": "#154360",
    "group": "LegalNorm系"
  },
  "JudicialEntity": {
    "bg": "#d35400",
    "border": "#7e2e00",
    "group": "JudicialEntity系"
  },
  "LegalSubject": {
    "bg": "#8e44ad",
    "border": "#512e5c",
    "group": "LegalSubject系"
  },
  "Person": {
    "bg": "#16a085",
    "border": "#0b5345",
    "group": "Person系"
  }
};
let DEFAULT_COLOR = {
  "bg": "#7f8c8d",
  "border": "#5d6d7e",
  "group": "其他"
};
export const ENTITY_STYLES = {
  "LegalNorm": {
    "shape": "triangle",
    "color": "#B0C4DE",
    "border": "#8DA3B8",
    "size": 16,
    "note": "辅助规范"
  },
  "JudicialEntity": {
    "shape": "box",
    "color": "#d35400",
    "border": "#7e2e00",
    "size": 18,
    "note": "JudicialEntity系"
  },
  "LegalSubject": {
    "shape": "triangle",
    "color": "#B0C4DE",
    "border": "#7B899B",
    "size": 16,
    "note": "辅助主体"
  },
  "Law": {
    "shape": "hexagon",
    "color": "#483D8B",
    "border": "#3A2D6E",
    "size": 16,
    "note": "法律"
  },
  "LegalProvision": {
    "shape": "hexagon",
    "color": "#483D8B",
    "border": "#3A2D6E",
    "size": 16,
    "note": "法条/法律依据"
  },
  "LegalProvisionVersion": {
    "shape": "hexagon",
    "color": "#2980b9",
    "border": "#154360",
    "size": 16,
    "note": "LegalNorm系"
  },
  "CaseType": {
    "shape": "hexagon",
    "color": "#2980b9",
    "border": "#154360",
    "size": 16,
    "note": "LegalNorm系"
  },
  "GuidingCase": {
    "shape": "star",
    "color": "#4682B4",
    "border": "#35608C",
    "size": 22,
    "note": "指导性案例"
  },
  "SentencingStandard": {
    "shape": "hexagon",
    "color": "#2980b9",
    "border": "#154360",
    "size": 16,
    "note": "LegalNorm系"
  },
  "Person": {
    "shape": "square",
    "color": "#90EE90",
    "border": "#65A765",
    "size": 18,
    "note": "原告/申请人"
  },
  "Judge": {
    "shape": "square",
    "color": "#16a085",
    "border": "#0b5345",
    "size": 18,
    "note": "Person系"
  },
  "Attorney": {
    "shape": "square",
    "color": "#16a085",
    "border": "#0b5345",
    "size": 18,
    "note": "Person系"
  },
  "Clerk": {
    "shape": "square",
    "color": "#16a085",
    "border": "#0b5345",
    "size": 18,
    "note": "Person系"
  },
  "Prosecutor": {
    "shape": "square",
    "color": "#16a085",
    "border": "#0b5345",
    "size": 18,
    "note": "Person系"
  },
  "Organization": {
    "shape": "triangle",
    "color": "#8e44ad",
    "border": "#512e5c",
    "size": 16,
    "note": "LegalSubject系"
  },
  "Court": {
    "shape": "triangle",
    "color": "#8e44ad",
    "border": "#512e5c",
    "size": 16,
    "note": "LegalSubject系"
  },
  "Procuratorate": {
    "shape": "triangle",
    "color": "#8e44ad",
    "border": "#512e5c",
    "size": 16,
    "note": "LegalSubject系"
  },
  "LawFirm": {
    "shape": "triangle",
    "color": "#8e44ad",
    "border": "#512e5c",
    "size": 16,
    "note": "LegalSubject系"
  },
  "ExpertInstitution": {
    "shape": "triangle",
    "color": "#8e44ad",
    "border": "#512e5c",
    "size": 16,
    "note": "LegalSubject系"
  },
  "District": {
    "shape": "box",
    "color": "#d35400",
    "border": "#7e2e00",
    "size": 18,
    "note": "JudicialEntity系"
  },
  "LegalRole": {
    "shape": "diamond",
    "color": "#FFA500",
    "border": "#CC8400",
    "size": 16,
    "note": "诉讼角色"
  },
  "CourtCase": {
    "shape": "box",
    "color": "#FFA07A",
    "border": "#E8875A",
    "size": 22,
    "note": "一审案件"
  },
  "CaseSummary": {
    "shape": "star",
    "color": "#32CD32",
    "border": "#28A428",
    "size": 20,
    "note": "争议焦点"
  },
  "TrialOrganization": {
    "shape": "box",
    "color": "#d35400",
    "border": "#7e2e00",
    "size": 18,
    "note": "JudicialEntity系"
  },
  "JudgmentResult": {
    "shape": "box",
    "color": "#d35400",
    "border": "#7e2e00",
    "size": 18,
    "note": "JudicialEntity系"
  },
  "ExecutionInfo": {
    "shape": "box",
    "color": "#d35400",
    "border": "#7e2e00",
    "size": 18,
    "note": "JudicialEntity系"
  },
  "LegalDocument": {
    "shape": "box",
    "color": "#d35400",
    "border": "#7e2e00",
    "size": 18,
    "note": "JudicialEntity系"
  },
  "Evidence": {
    "shape": "database",
    "color": "#CD853F",
    "border": "#A06B32",
    "size": 6,
    "note": "证据"
  },
  "DisputeFocus": {
    "shape": "star",
    "color": "#E67E22",
    "border": "#CA6F1E",
    "size": 18,
    "note": "争议焦点"
  },
  "LegalProvisionElement": {
    "shape": "box",
    "color": "#7f8c8d",
    "border": "#5d6d7e",
    "size": 18,
    "note": "其他"
  },
  "Fact": {
    "shape": "ellipse",
    "color": "#8E44AD",
    "border": "#6C3483",
    "size": 14,
    "note": "案件事实"
  },
  "CaseParticipant": {
    "shape": "box",
    "color": "#d35400",
    "border": "#7e2e00",
    "size": 18,
    "note": "JudicialEntity系"
  }
};
let TERM_SHAPES = {};
let TERM_COLORS = {};
let TERM_SIZES = {};
Object.keys(ENTITY_STYLES).forEach(function(k) {
  TERM_SHAPES[k] = ENTITY_STYLES[k].shape;
  TERM_COLORS[k] = { bg: ENTITY_STYLES[k].color, border: ENTITY_STYLES[k].border };
  TERM_SIZES[k] = ENTITY_STYLES[k].size || 18;
});
window.__TERM_SHAPES = TERM_SHAPES;
window.__TERM_COLORS = TERM_COLORS;
window.__TERM_SIZES = TERM_SIZES;
let INHERITANCE_CHAIN = {
  "LegalNorm": [
    "LegalNorm"
  ],
  "JudicialEntity": [
    "JudicialEntity"
  ],
  "LegalSubject": [
    "LegalSubject"
  ],
  "Law": [
    "Law",
    "LegalNorm"
  ],
  "LegalProvision": [
    "LegalProvision",
    "LegalNorm"
  ],
  "LegalProvisionVersion": [
    "LegalProvisionVersion",
    "LegalNorm"
  ],
  "CaseType": [
    "CaseType",
    "LegalNorm"
  ],
  "GuidingCase": [
    "GuidingCase",
    "LegalNorm"
  ],
  "SentencingStandard": [
    "SentencingStandard",
    "LegalNorm"
  ],
  "Person": [
    "Person"
  ],
  "Judge": [
    "Judge",
    "Person"
  ],
  "Attorney": [
    "Attorney",
    "Person"
  ],
  "Clerk": [
    "Clerk",
    "Person"
  ],
  "Prosecutor": [
    "Prosecutor",
    "Person"
  ],
  "Organization": [
    "Organization",
    "LegalSubject"
  ],
  "Court": [
    "Court",
    "Organization",
    "LegalSubject"
  ],
  "Procuratorate": [
    "Procuratorate",
    "Organization",
    "LegalSubject"
  ],
  "LawFirm": [
    "LawFirm",
    "Organization",
    "LegalSubject"
  ],
  "ExpertInstitution": [
    "ExpertInstitution",
    "Organization",
    "LegalSubject"
  ],
  "District": [
    "District",
    "JudicialEntity"
  ],
  "LegalRole": [
    "LegalRole",
    "JudicialEntity"
  ],
  "CourtCase": [
    "CourtCase",
    "JudicialEntity"
  ],
  "CaseSummary": [
    "CaseSummary",
    "JudicialEntity"
  ],
  "TrialOrganization": [
    "TrialOrganization",
    "JudicialEntity"
  ],
  "JudgmentResult": [
    "JudgmentResult",
    "JudicialEntity"
  ],
  "ExecutionInfo": [
    "ExecutionInfo",
    "JudicialEntity"
  ],
  "LegalDocument": [
    "LegalDocument",
    "JudicialEntity"
  ],
  "Evidence": [
    "Evidence",
    "JudicialEntity"
  ],
  "DisputeFocus": [
    "DisputeFocus",
    "JudicialEntity"
  ],
  "LegalProvisionElement": [
    "LegalProvisionElement"
  ],
  "Fact": [
    "Fact",
    "JudicialEntity"
  ],
  "CaseParticipant": [
    "CaseParticipant",
    "JudicialEntity"
  ]
};
function getRootColor(typeName) {
  let chain = INHERITANCE_CHAIN[typeName];
  if (!chain) return DEFAULT_COLOR;
  for (let i = 0; i < chain.length; i++) {
    if (ROOT_COLORS[chain[i]]) return ROOT_COLORS[chain[i]];
  }
  return DEFAULT_COLOR;
}
export const ZH_LABELS = {
  "LegalNorm": "法律规范顶层类",
  "JudicialEntity": "司法实体顶层类",
  "LegalSubject": "法律主体顶层类",
  "Law": "法律",
  "LegalProvision": "法律条文（当前生效版本）",
  "LegalProvisionVersion": "法律条文历史版本",
  "CaseType": "案由类型",
  "GuidingCase": "指导性案例",
  "SentencingStandard": "量刑/赔偿标准",
  "Person": "自然人（跨案件不消歧，每个案件独立节点）",
  "Judge": "法官",
  "Attorney": "律师",
  "Clerk": "书记员",
  "Prosecutor": "检察官",
  "Organization": "组织机构（企业用credit_code跨案件全局关联，包含法人实体、个体工商户、合伙企业、个人独资企业）",
  "Court": "法院",
  "Procuratorate": "检察院",
  "LawFirm": "律师事务所",
  "ExpertInstitution": "鉴定机构",
  "District": "辖区",
  "LegalRole": "法律角色",
  "CourtCase": "法院案件（精简节点，全文存ES）",
  "CaseSummary": "案件结构化摘要（用于热层类案相似度计算）",
  "TrialOrganization": "审判组织",
  "JudgmentResult": "裁判结果",
  "ExecutionInfo": "执行信息",
  "LegalDocument": "法律文书",
  "Evidence": "证据",
  "DisputeFocus": "案件争议焦点",
  "LegalProvisionElement": "法条构成要件要素（主体/行为/结果/因果关系/主观要件等结构化分解，用于事实→法条匹配推理）",
  "Fact": "案件事实",
  "CaseParticipant": "案件参与人（含审级角色变更）"
};
export const EN_DESCRIPTIONS = {
  "LegalNorm": "Top-level class for legal norms",
  "JudicialEntity": "Top-level class for judicial entities",
  "LegalSubject": "Top-level class for legal subjects",
  "Law": "Law / Statute",
  "LegalProvision": "Legal provision (current effective version)",
  "LegalProvisionVersion": "Historical version of legal provision",
  "CaseType": "Case type / Cause of action",
  "GuidingCase": "Guiding case",
  "SentencingStandard": "Sentencing/Compensation standard",
  "Person": "Natural person (no cross-case disambiguation, independent per case)",
  "Judge": "Judge",
  "Attorney": "Attorney / Lawyer",
  "Clerk": "Clerk",
  "Prosecutor": "Prosecutor",
  "Organization": "Organization (cross-case global correlation via credit_code)",
  "Court": "Court",
  "Procuratorate": "Procuratorate",
  "LawFirm": "Law firm",
  "ExpertInstitution": "Expert institution / Forensics body",
  "District": "District / Jurisdiction area",
  "LegalRole": "Legal role",
  "CourtCase": "Court case (lightweight node, full text in ES)",
  "CaseSummary": "Case structured summary (for hot-layer similarity)",
  "TrialOrganization": "Trial organization",
  "JudgmentResult": "Judgment result",
  "ExecutionInfo": "Execution information",
  "LegalDocument": "Legal document",
  "Evidence": "Evidence",
  "DisputeFocus": "Dispute focus",
  "LegalProvisionElement": "Legal provision constitutive element",
  "Fact": "Case fact",
  "CaseParticipant": "Case participant (with trial-level role changes)"
};
let ABSTRACT_ROOTS = {
  "LegalNorm": 1,
  "JudicialEntity": 1,
  "LegalSubject": 1,
  "Person": 1,
  "LegalProvisionElement": 1
};
export const TYPE_NAMES = [
  "Law",
  "LegalProvision",
  "LegalProvisionVersion",
  "CaseType",
  "GuidingCase",
  "SentencingStandard",
  "Judge",
  "Attorney",
  "Clerk",
  "Prosecutor",
  "Organization",
  "Court",
  "Procuratorate",
  "LawFirm",
  "ExpertInstitution",
  "District",
  "LegalRole",
  "CourtCase",
  "CaseSummary",
  "TrialOrganization",
  "JudgmentResult",
  "ExecutionInfo",
  "LegalDocument",
  "Evidence",
  "DisputeFocus",
  "Fact",
  "CaseParticipant"
];
let IS_A_EDGES = [
  [
    "Law",
    "LegalNorm"
  ],
  [
    "LegalProvision",
    "LegalNorm"
  ],
  [
    "LegalProvisionVersion",
    "LegalNorm"
  ],
  [
    "CaseType",
    "LegalNorm"
  ],
  [
    "GuidingCase",
    "LegalNorm"
  ],
  [
    "SentencingStandard",
    "LegalNorm"
  ],
  [
    "Judge",
    "Person"
  ],
  [
    "Attorney",
    "Person"
  ],
  [
    "Clerk",
    "Person"
  ],
  [
    "Prosecutor",
    "Person"
  ],
  [
    "Organization",
    "LegalSubject"
  ],
  [
    "Court",
    "Organization"
  ],
  [
    "Procuratorate",
    "Organization"
  ],
  [
    "LawFirm",
    "Organization"
  ],
  [
    "ExpertInstitution",
    "Organization"
  ],
  [
    "District",
    "JudicialEntity"
  ],
  [
    "LegalRole",
    "JudicialEntity"
  ],
  [
    "CourtCase",
    "JudicialEntity"
  ],
  [
    "CaseSummary",
    "JudicialEntity"
  ],
  [
    "TrialOrganization",
    "JudicialEntity"
  ],
  [
    "JudgmentResult",
    "JudicialEntity"
  ],
  [
    "ExecutionInfo",
    "JudicialEntity"
  ],
  [
    "LegalDocument",
    "JudicialEntity"
  ],
  [
    "Evidence",
    "JudicialEntity"
  ],
  [
    "DisputeFocus",
    "JudicialEntity"
  ],
  [
    "Fact",
    "JudicialEntity"
  ],
  [
    "CaseParticipant",
    "JudicialEntity"
  ]
];
export const RELATION_EDGES = [
  [
    "typically_applies",
    "CaseType",
    "LegalProvision"
  ],
  [
    "belongs_to",
    "LegalProvision",
    "Law"
  ],
  [
    "has_version",
    "LegalProvision",
    "LegalProvisionVersion"
  ],
  [
    "superseded_by",
    "LegalProvisionVersion",
    "LegalProvisionVersion"
  ],
  [
    "guides_case_type",
    "GuidingCase",
    "CaseType"
  ],
  [
    "cites_guiding_case",
    "CourtCase",
    "GuidingCase"
  ],
  [
    "applies_standard",
    "CourtCase",
    "SentencingStandard"
  ],
  [
    "has_summary",
    "CourtCase",
    "CaseSummary"
  ],
  [
    "tried_by",
    "CourtCase",
    "TrialOrganization"
  ],
  [
    "undertakes",
    "Judge",
    "CourtCase"
  ],
  [
    "plays_role",
    "LegalSubject",
    "LegalRole"
  ],
  [
    "has_jurisdiction_over",
    "Court",
    "District"
  ],
  [
    "prosecutes",
    "Procuratorate",
    "CourtCase"
  ],
  [
    "based_on",
    "ExecutionInfo",
    "JudgmentResult"
  ],
  [
    "signed_by",
    "LegalDocument",
    "Judge"
  ],
  [
    "has_case_type",
    "CourtCase",
    "CaseType"
  ],
  [
    "cites",
    "CourtCase",
    "LegalProvision"
  ],
  [
    "judgment_cites",
    "JudgmentResult",
    "LegalProvision"
  ],
  [
    "represents",
    "Attorney",
    "LegalSubject"
  ],
  [
    "employs",
    "Procuratorate",
    "Prosecutor"
  ],
  [
    "employs_attorney",
    "LawFirm",
    "Attorney"
  ],
  [
    "submitted_for",
    "Evidence",
    "CourtCase"
  ],
  [
    "proves_fact",
    "Evidence",
    "Fact"
  ],
  [
    "proves_fact",
    "Evidence",
    "DisputeFocus"
  ],
  [
    "includes",
    "TrialOrganization",
    "Judge"
  ],
  [
    "includes_clerk",
    "TrialOrganization",
    "Clerk"
  ],
  [
    "appeals_to",
    "CourtCase",
    "CourtCase"
  ],
  [
    "retries_from",
    "CourtCase",
    "CourtCase"
  ],
  [
    "has_dispute_focus",
    "CourtCase",
    "DisputeFocus"
  ],
  [
    "has_fact",
    "CourtCase",
    "Fact"
  ],
  [
    "matches_element",
    "Fact",
    "LegalProvisionElement"
  ],
  [
    "resolved_by",
    "DisputeFocus",
    "LegalProvision"
  ],
  [
    "leads_to",
    "Fact",
    "JudgmentResult"
  ],
  [
    "leads_to",
    "DisputeFocus",
    "JudgmentResult"
  ]
];
export const RELATION_LABELS = {
  "typically_applies": "典型适用",
  "belongs_to": "归属于",
  "has_version": "具有版本",
  "superseded_by": "被替代",
  "guides_case_type": "指导案由",
  "cites_guiding_case": "引用指导案例",
  "applies_standard": "适用标准",
  "has_summary": "具有摘要",
  "tried_by": "由…审理",
  "undertakes": "承办",
  "plays_role": "担任角色",
  "has_jurisdiction_over": "管辖",
  "prosecutes": "公诉",
  "based_on": "基于",
  "signed_by": "由…签署",
  "has_case_type": "具有案由",
  "cites": "引用法条",
  "judgment_cites": "裁判依据",
  "represents": "代理",
  "employs": "雇佣",
  "employs_attorney": "雇佣律师",
  "submitted_for": "提交给",
  "proves_fact": "证明事实",
  "includes": "包含法官",
  "includes_clerk": "配备书记员",
  "appeals_to": "上诉至",
  "retries_from": "再审源自",
  "has_dispute_focus": "具有争议焦点",
  "has_fact": "具有事实",
  "matches_element": "匹配要件",
  "resolved_by": "由法条解决",
  "leads_to": "事实/争议焦点推导出裁判结果（三段论推理的结论链路）"
};
let RELATION_DESC = {
  "typically_applies": "CaseType → LegalProvision (many_to_many)",
  "belongs_to": "LegalProvision → Law (many_to_one)",
  "has_version": "LegalProvision → LegalProvisionVersion (one_to_many)",
  "superseded_by": "LegalProvisionVersion → LegalProvisionVersion (one_to_one)",
  "guides_case_type": "GuidingCase → CaseType (one_to_many)",
  "cites_guiding_case": "CourtCase → GuidingCase (many_to_many)",
  "applies_standard": "CourtCase → SentencingStandard (many_to_many)",
  "has_summary": "CourtCase → CaseSummary (one_to_one)",
  "tried_by": "CourtCase → TrialOrganization (one_to_one)",
  "undertakes": "Judge → CourtCase (one_to_many)",
  "plays_role": "LegalSubject → LegalRole (many_to_many)",
  "has_jurisdiction_over": "Court → District (one_to_one)",
  "prosecutes": "Procuratorate → CourtCase (one_to_many)",
  "based_on": "ExecutionInfo → JudgmentResult (one_to_one)",
  "signed_by": "LegalDocument → Judge (many_to_one)",
  "has_case_type": "CourtCase → CaseType (one_to_many)",
  "cites": "CourtCase → LegalProvision (many_to_many)",
  "judgment_cites": "JudgmentResult → LegalProvision (many_to_many)",
  "represents": "Attorney → LegalSubject (many_to_many)",
  "employs": "Procuratorate → Prosecutor (one_to_many)",
  "employs_attorney": "LawFirm → Attorney (one_to_many)",
  "submitted_for": "Evidence → CourtCase (many_to_one)",
  "proves_fact": "Evidence → Fact, DisputeFocus (many_to_many)",
  "includes": "TrialOrganization → Judge (one_to_many)",
  "includes_clerk": "TrialOrganization → Clerk (one_to_one)",
  "appeals_to": "CourtCase → CourtCase (one_to_one)",
  "retries_from": "CourtCase → CourtCase (one_to_one)",
  "has_dispute_focus": "CourtCase → DisputeFocus (one_to_many)",
  "has_fact": "CourtCase → Fact (one_to_many)",
  "matches_element": "Fact → LegalProvisionElement (many_to_many)",
  "resolved_by": "DisputeFocus → LegalProvision (many_to_many)",
  "leads_to": "Fact, DisputeFocus → JudgmentResult (many_to_many)"
};
