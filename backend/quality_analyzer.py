"""
Local parse quality analyzer — pure statistics, no LLM call.
Evaluates the parsed JSON result against the ontology structure,
computing resolution rates at field, entity, category and global levels.

Scoring formula:
  - Field level:  extracted=1 point, missing=0 point
  - Entity level: Σ(field scores) / total_fields × 100%
  - Category level: Σ(entity scores) / total_entities × 100%
  - Global: Σ(all entity scores) / total_entities
  - Confidence: ≥90%→"优", 70-89%→"良", 50-69%→"中", <50%→"差"
"""

import copy
from typing import Any, Dict, List, Optional


# ── Ontology → JSON Result Field Mapping ─────────────────────────────────────
# Maps ontology entity types (二级实体) to their corresponding json_result
# field paths and expected sub-fields. Also includes relations.
#
# Structure:
#   entity_key: {
#       path: ["json_result", "key"] or function(json_result) → value,
#       label: "中文名",
#       category: "大类英文名" (一级),
#       category_label: "大类中文名",
#       fields: [field_spec, ...],
#       relations: [relation_spec, ...]
#   }
#   field_spec: {"key": "field_name", "label": "中文标签", "required": bool}
#   relation_spec: {"key": "relation_name", "label": "中文标签", "status": "ok|missing", ...}

ENTITY_FIELD_MAP = [
    # ── LegalNorm (规范层) ──
    {
        "type": "GuidingCase",
        "label": "指导性案例",
        "category": "LegalNorm",
        "category_label": "规范层",
        "path": ("guiding_case",),
        "fields": [
            {"key": "guiding_case_number", "label": "指导案例编号", "required": True},
            {"key": "guiding_case_name", "label": "案例名称", "required": True},
            {"key": "publication_date", "label": "发布日期", "required": True},
            {"key": "binding_force", "label": "约束力", "required": True},
            {"key": "guiding_points", "label": "裁判要旨/指导要点", "required": False},
            {"key": "case_level", "label": "案例层级", "required": False},
            {"key": "trial_procedure", "label": "审判程序", "required": False},
            {"key": "storage_no", "label": "入库编号", "required": False},
            {"key": "judgment_mean", "label": "裁判意义", "required": False},
        ],
        "relations": [
            {"key": "guides_case_type", "label": "指导案由", "target": "CaseType"},
            {"key": "cites_guiding_case", "label": "被案件引用", "target": "CourtCase"},
        ],
    },
    {
        "type": "CaseType",
        "label": "案由类型",
        "category": "LegalNorm",
        "category_label": "规范层",
        "path": ("case_type",),
        "fields": [
            {"key": "category", "label": "大类", "required": True},
            {"key": "level1", "label": "一级案由", "required": False},
            {"key": "level2", "label": "二级案由", "required": False},
        ],
        "relations": [
            {"key": "has_case_type", "label": "案件类型归属", "target": "CourtCase"},
            {"key": "typically_applies", "label": "典型适用法条", "target": "LegalProvision"},
        ],
    },
    {
        "type": "LegalProvision",
        "label": "法律条文",
        "category": "LegalNorm",
        "category_label": "规范层",
        "path": ("legal_provisions",),  # list
        "is_list": True,
        "fields": [
            {"key": "statute", "label": "法典名称", "required": True},
            {"key": "article", "label": "条号", "required": True},
            {"key": "paragraph", "label": "款号", "required": False},
            {"key": "item", "label": "项号", "required": False},
            {"key": "content", "label": "法条原文片段", "required": False},
            {"key": "citation_position", "label": "引用位置", "required": False},
            {"key": "citation_purpose", "label": "引用目的", "required": False},
        ],
        "relations": [
            {"key": "belongs_to", "label": "归属于法律", "target": "Law"},
            {"key": "cites", "label": "被案件引用", "target": "CourtCase"},
            {"key": "judgment_cites", "label": "裁判依据", "target": "JudgmentResult"},
        ],
    },
    # ── JudicialEntity (司法实体层) ──
    {
        "type": "CourtCase",
        "label": "法院案件",
        "category": "JudicialEntity",
        "category_label": "司法实体层",
        "path": ("court_cases",),  # list
        "is_list": True,
        "fields": [
            {"key": "case_number", "label": "案号", "required": True},
            {"key": "filing_date", "label": "立案日期", "required": True},
            {"key": "judgment_date", "label": "判决日期", "required": False},
            {"key": "trial_level", "label": "审级", "required": True},
            {"key": "court.name", "label": "审理法院名称", "required": True},
            {"key": "court.court_level", "label": "法院层级", "required": False},
            {"key": "status", "label": "案件状态", "required": False},
        ],
        "relations": [
            {"key": "has_summary", "label": "具有摘要", "target": "CaseSummary"},
            {"key": "tried_by", "label": "由审判组织审理", "target": "TrialOrganization"},
            {"key": "has_case_type", "label": "具有案由", "target": "CaseType"},
            {"key": "cites", "label": "引用法条", "target": "LegalProvision"},
            {"key": "has_dispute_focus", "label": "具有争议焦点", "target": "DisputeFocus"},
            {"key": "has_fact", "label": "具有事实", "target": "Fact"},
        ],
    },
    {
        "type": "CaseSummary",
        "label": "案件摘要",
        "category": "JudicialEntity",
        "category_label": "司法实体层",
        "path": ("case_summary",),
        "fields": [
            {"key": "key_facts", "label": "关键事实", "required": True},
            {"key": "disputed_issues", "label": "争议焦点", "required": True},
            {"key": "conclusion", "label": "裁判结论", "required": True},
            {"key": "amount_involved", "label": "标的金额", "required": False},
            {"key": "guiding_points", "label": "指导要点", "required": False},
        ],
        "relations": [
            {"key": "has_summary", "label": "属于案件", "target": "CourtCase"},
        ],
    },
    {
        "type": "Evidence",
        "label": "证据",
        "category": "JudicialEntity",
        "category_label": "司法实体层",
        "path": ("evidence",),  # list
        "is_list": True,
        "fields": [
            {"key": "content", "label": "证据内容", "required": True},
            {"key": "evidence_type", "label": "证据类型", "required": True},
            {"key": "submitted_by", "label": "提交方", "required": False},
            {"key": "is_key_evidence", "label": "是否关键证据", "required": False},
            {"key": "admission_status", "label": "采信状态", "required": False},
            {"key": "admission_reason", "label": "采信/不采信理由", "required": False},
            {"key": "probative_force", "label": "证明力", "required": False},
        ],
        "relations": [
            {"key": "submitted_for", "label": "提交给案件", "target": "CourtCase"},
            {"key": "proves_fact", "label": "证明事实", "target": "Fact"},
        ],
    },
    {
        "type": "JudgmentResult",
        "label": "裁判结果",
        "category": "JudicialEntity",
        "category_label": "司法实体层",
        "path": ("judgment_results",),  # list
        "is_list": True,
        "fields": [
            {"key": "result_type", "label": "结果类型", "required": True},
            {"key": "specific_judgment", "label": "具体判决内容", "required": True},
            {"key": "case_number", "label": "关联案号", "required": False},
        ],
        "relations": [
            {"key": "judgment_cites", "label": "依据法条", "target": "LegalProvision"},
            {"key": "leads_to_fact", "label": "推导自事实", "target": "Fact"},
            {"key": "based_on", "label": "执行依据", "target": "ExecutionInfo"},
        ],
    },
    {
        "type": "TrialOrganization",
        "label": "审判组织",
        "category": "JudicialEntity",
        "category_label": "司法实体层",
        "path": None,
        "is_computed": True,
        "desc": "从裁判理由中的合议庭信息提取",
        "fields": [],
        "relations": [
            {"key": "tried_by", "label": "审理案件", "target": "CourtCase"},
            {"key": "includes", "label": "包含法官", "target": "Judge"},
        ],
    },
    {
        "type": "LegalDocument",
        "label": "法律文书",
        "category": "JudicialEntity",
        "category_label": "司法实体层",
        "path": None,
        "is_computed": True,
        "desc": "解析结果对应单一法律文书类型",
        "fields": [],
        "relations": [
            {"key": "signed_by", "label": "由法官签署", "target": "Judge"},
        ],
    },
    {
        "type": "DisputeFocus",
        "label": "争议焦点",
        "category": "JudicialEntity",
        "category_label": "司法实体层",
        "path": None,
        "is_computed": True,
        "desc": "包含在 case_summary.disputed_issues 中",
        "fields": [],
        "relations": [
            {"key": "has_dispute_focus", "label": "属于案件", "target": "CourtCase"},
            {"key": "resolved_by", "label": "由法条解决", "target": "LegalProvision"},
        ],
    },
    {
        "type": "Fact",
        "label": "案件事实",
        "category": "JudicialEntity",
        "category_label": "司法实体层",
        "path": None,
        "is_computed": True,
        "desc": "包含在 case_summary.key_facts 中",
        "fields": [],
        "relations": [
            {"key": "has_fact", "label": "属于案件", "target": "CourtCase"},
            {"key": "proves_fact", "label": "被证据证明", "target": "Evidence"},
            {"key": "matches_element", "label": "匹配要件", "target": "LegalProvisionElement"},
        ],
    },
    # ── LegalSubject (主体层) ──
    {
        "type": "LegalSubject",
        "label": "法律主体（当事人）",
        "category": "LegalSubject",
        "category_label": "主体层",
        "path": ("legal_subjects",),  # list
        "is_list": True,
        "fields": [
            {"key": "name", "label": "名称", "required": True},
            {"key": "subject_type", "label": "主体类型", "required": True},
            {"key": "roles", "label": "角色列表", "required": True},
            {"key": "org_type", "label": "组织类型", "required": False},
        ],
        "relations": [
            {"key": "plays_role", "label": "担任角色", "target": "LegalRole"},
        ],
    },
    {
        "type": "Organization",
        "label": "组织机构",
        "category": "LegalSubject",
        "category_label": "主体层",
        "path": None,
        "is_computed": True,
        "desc": "从 legal_subjects 中 subject_type=organization 的项提取",
        "fields": [],
        "relations": [
            {"key": "plays_role", "label": "担任角色", "target": "LegalRole"},
        ],
    },
    # ── Person (自然人层) ──
    {
        "type": "Judge",
        "label": "法官",
        "category": "Person",
        "category_label": "自然人层",
        "path": ("judges",),  # list
        "is_list": True,
        "fields": [
            {"key": "name", "label": "姓名", "required": True},
            {"key": "role", "label": "角色", "required": True},
            {"key": "case_number", "label": "关联案号", "required": False},
        ],
        "relations": [
            {"key": "undertakes", "label": "承办案件", "target": "CourtCase"},
            {"key": "includes", "label": "属于审判组织", "target": "TrialOrganization"},
        ],
    },
    {
        "type": "Attorney",
        "label": "律师",
        "category": "Person",
        "category_label": "自然人层",
        "path": ("attorneys",),  # list
        "is_list": True,
        "fields": [
            {"key": "name", "label": "姓名", "required": True},
            {"key": "law_firm", "label": "所属律所", "required": True},
            {"key": "representation_for", "label": "代理何方", "required": False},
            {"key": "case_number", "label": "关联案号", "required": False},
        ],
        "relations": [
            {"key": "represents", "label": "代理当事人", "target": "LegalSubject"},
            {"key": "employs_attorney", "label": "被律所雇佣", "target": "LawFirm"},
        ],
    },
    {
        "type": "Prosecutor",
        "label": "检察官",
        "category": "Person",
        "category_label": "自然人层",
        "path": ("prosecutors",),  # list (may be named "prosecutor_info" in some outputs)
        "is_list": True,
        "fields": [
            {"key": "name", "label": "姓名", "required": True},
            {"key": "role", "label": "角色", "required": True},
            {"key": "unit", "label": "所属检察院", "required": False},
            {"key": "case_number", "label": "关联案号", "required": False},
        ],
        "relations": [
            {"key": "employs", "label": "被检察院雇佣", "target": "Procuratorate"},
        ],
    },
]


def _get_field_value(obj: Any, field_key: str) -> Any:
    """Get a nested field value from a dict using dot notation."""
    if obj is None:
        return None
    parts = field_key.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _check_field(field_spec: Dict[str, Any], value: Any) -> Dict[str, Any]:
    """Check a single field's status."""
    key = field_spec["key"]
    label = field_spec["label"]
    required = field_spec.get("required", False)

    if value is None or value == "" or value == [] or value == {}:
        return {
            "name": key,
            "label": label,
            "status": "missing",
            "value": value,
            "required": required,
            "score": 0,
        }

    # For list fields (like roles), check if non-empty
    if isinstance(value, list):
        if len(value) == 0:
            return {
                "name": key,
                "label": label,
                "status": "missing",
                "value": value,
                "required": required,
                "score": 0,
            }
        # Check if all items are properly filled
        all_valid = all(
            (isinstance(v, dict) and any(_check_field({"key": k, "label": k}, v.get(k))["status"] == "ok" for k in v))
            or (isinstance(v, str) and v.strip() != "")
            for v in value
        )
        return {
            "name": key,
            "label": label,
            "status": "ok" if all_valid else "partial",
            "value": value,
            "required": required,
            "score": 1 if all_valid else 0.5,
        }

    # String or number — non-empty is ok
    if isinstance(value, str) and value.strip():
        return {
            "name": key,
            "label": label,
            "status": "ok",
            "value": value,
            "required": required,
            "score": 1,
        }

    # Dict (like court {name, court_level})
    if isinstance(value, dict):
        non_empty = any(v is not None and v != "" for v in value.values())
        return {
            "name": key,
            "label": label,
            "status": "ok" if non_empty else "missing",
            "value": value,
            "required": required,
            "score": 1 if non_empty else 0,
        }

    return {
        "name": key,
        "label": label,
        "status": "ok",
        "value": value,
        "required": required,
        "score": 1,
    }


def _get_entity_count(json_result: Dict[str, Any], entity_def: Dict[str, Any]) -> int:
    """Get the count of instances for a given entity type."""
    path = entity_def.get("path")
    if path is None:
        # Computed entities: 1 if the source data exists
        if entity_def["type"] == "TrialOrganization":
            judges = _get_field_value(json_result, "judges")
            court_cases = _get_field_value(json_result, "court_cases")
            if (judges and len(judges) > 0) or (court_cases and len(court_cases) > 0):
                return 1
            return 0
        if entity_def["type"] == "LegalDocument":
            return 1  # Always one document being parsed
        if entity_def["type"] == "DisputeFocus":
            cs = _get_field_value(json_result, "case_summary")
            if cs and cs.get("disputed_issues"):
                return 1
            return 0
        if entity_def["type"] == "Fact":
            cs = _get_field_value(json_result, "case_summary")
            if cs and cs.get("key_facts"):
                return 1
            return 0
        if entity_def["type"] == "Organization":
            subjects = _get_field_value(json_result, "legal_subjects") or []
            org_count = sum(1 for s in subjects if s.get("subject_type") == "organization")
            return max(org_count, 1 if subjects else 0)
        return 0

    # Navigate the path
    current = json_result
    for part in path:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return 0

    if entity_def.get("is_list"):
        return len(current) if isinstance(current, list) else (1 if current else 0)
    else:
        return 1 if current else 0


def _analyze_entity(json_result: Dict[str, Any], entity_def: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a single entity type and return its quality assessment."""
    path = entity_def.get("path")
    entity_type = entity_def["type"]
    is_list = entity_def.get("is_list", False)
    fields = entity_def.get("fields", [])
    relations = entity_def.get("relations", [])

    # Get the value(s) for this entity
    values = []
    if path is None:
        # Computed entity — create a synthetic entry
        values = [{"_computed": True, "_type": entity_type}]
    else:
        current = json_result
        for part in path:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = None
                break
        if current is None:
            values = []
        elif is_list:
            values = current if isinstance(current, list) else []
        else:
            values = [current]

    # Analyze each instance
    item_scores = []
    item_details = []

    for idx, val in enumerate(values):
        if val is None or (isinstance(val, dict) and val.get("_computed")):
            # Computed entity — check if referenced elsewhere
            entity_present = _get_entity_count(json_result, entity_def) > 0
            item_fields = []
            total_score = 100.0 if entity_present else 0.0
            item_detail = {
                "instance": f"{entity_type}#{idx}",
                "fields": [],
                "score": total_score,
                "status": "ok" if entity_present else "missing",
            }
            # For computed entities, check if source data exists
            if entity_present:
                for field in fields:
                    item_fields.append({
                        "name": field["key"],
                        "label": field["label"],
                        "status": "ok",
                        "value": "(computed)",
                        "required": field.get("required", False),
                        "score": 1,
                    })
                item_detail["fields"] = item_fields
            else:
                for field in fields:
                    item_fields.append({
                        "name": field["key"],
                        "label": field["label"],
                        "status": "missing",
                        "value": None,
                        "required": field.get("required", False),
                        "score": 0,
                    })
                item_detail["fields"] = item_fields

            item_scores.append(total_score)
            item_details.append(item_detail)
            continue

        # Normal entity — check each field
        item_fields = []
        field_scores = []

        for field in fields:
            field_key = field["key"]
            field_value = _get_field_value(val, field_key)
            result = _check_field(field, field_value)
            item_fields.append(result)
            field_scores.append(result["score"])

        # Calculate entity score
        total_fields = len(fields)
        if total_fields == 0:
            entity_score = 100.0
        else:
            entity_score = (sum(field_scores) / total_fields) * 100.0

        # Determine status
        ok_count = sum(1 for f in item_fields if f["status"] == "ok")
        missing_count = sum(1 for f in item_fields if f["status"] == "missing")
        if missing_count == 0:
            entity_status = "ok"
        elif ok_count > 0:
            entity_status = "partial"
        else:
            entity_status = "missing"

        item_detail = {
            "instance": f"{entity_type}#{idx}",
            "label": val.get("case_number") or val.get("name") or val.get("guiding_case_name") or f"实例{idx}",
            "fields": item_fields,
            "score": entity_score,
            "status": entity_status,
        }
        item_scores.append(entity_score)
        item_details.append(item_detail)

    # Aggregate entity-level score across all instances
    if len(item_scores) > 0:
        entity_score = sum(item_scores) / len(item_scores)
    else:
        entity_score = 0.0

    # Check relations
    relation_results = []
    for rel in relations:
        relation_results.append({
            "name": rel["key"],
            "label": rel["label"],
            "target": rel["target"],
            "status": "ok" if _get_entity_count(json_result, entity_def) > 0 else "partial",
        })

    # Build issues list
    issues = []
    for item in item_details:
        for field in item.get("fields", []):
            if field["status"] == "missing" and field.get("required", False):
                issues.append({
                    "entity": f"{entity_type}.{field['name']}",
                    "msg": f"{field['label']}缺失",
                    "severity": "major",
                })
            elif field["status"] == "missing":
                issues.append({
                    "entity": f"{entity_type}.{field['name']}",
                    "msg": f"{field['label']}缺失",
                    "severity": "minor",
                })

    if _get_entity_count(json_result, entity_def) == 0 and path is not None:
        issues.append({
            "entity": entity_type,
            "msg": f"{entity_def['label']}整体缺失",
            "severity": "critical",
        })

    return {
        "type": entity_type,
        "type_label": entity_def["label"],
        "category": entity_def["category"],
        "category_label": entity_def.get("category_label", entity_def["category"]),
        "score": round(entity_score, 1),
        "status": "ok" if entity_score >= 80 else ("partial" if entity_score >= 50 else "missing"),
        "instance_count": len(item_details),
        "items": item_details,
        "relations": relation_results,
        "fields_count": sum(len(item.get("fields", [])) for item in item_details),
        "issues": issues,
    }


def _compute_evidence_admission_fill_rate(json_result: Dict[str, Any]) -> float:
    """Compute the fill rate of admission_status across all evidence items."""
    evidence_list = _get_field_value(json_result, "evidence") or []
    if not evidence_list:
        return 0.0
    filled = sum(1 for e in evidence_list if e.get("admission_status"))
    return round(filled / len(evidence_list), 2)


def parse_quality(json_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze parse quality of a json_result against the ontology structure.

    Returns:
        Dict with total_score, confidence, entities (categorized by ontology level),
        and a flat issues list.
    """
    if not json_result or not isinstance(json_result, dict):
        return {
            "total_score": 0,
            "confidence": "差",
            "categories": [],
            "entities": [],
            "issues": [],
        }

    # Analyze each entity
    entity_results = []
    all_issues = []
    for entity_def in ENTITY_FIELD_MAP:
        result = _analyze_entity(json_result, entity_def)
        entity_results.append(result)
        all_issues.extend(result["issues"])

    # Group by category (一级标题)
    categories = {}
    for er in entity_results:
        cat = er["category"]
        if cat not in categories:
            categories[cat] = {
                "category": cat,
                "category_label": er["category_label"],
                "entities": [],
                "total_score": 0,
                "entity_count": 0,
            }
        categories[cat]["entities"].append(er)
        categories[cat]["total_score"] += er["score"]
        categories[cat]["entity_count"] += 1

    # Calculate category-level and global scores
    category_list = []
    for cat_key, cat_data in categories.items():
        if cat_data["entity_count"] > 0:
            cat_data["score"] = round(cat_data["total_score"] / cat_data["entity_count"], 1)
        else:
            cat_data["score"] = 0
        cat_data["status"] = "ok" if cat_data["score"] >= 80 else ("partial" if cat_data["score"] >= 50 else "missing")
        category_list.append(cat_data)

    # Sort categories: LegalNorm → JudicialEntity → LegalSubject → Person
    cat_order = {"LegalNorm": 0, "JudicialEntity": 1, "LegalSubject": 2, "Person": 3}
    category_list.sort(key=lambda c: cat_order.get(c["category"], 99))

    # Global score
    all_scores = [er["score"] for er in entity_results if er["fields_count"] > 0 or er.get("instance_count", 0) > 0]
    if all_scores:
        total_score = sum(all_scores) / len(all_scores)
    else:
        total_score = 0

    # Confidence
    if total_score >= 90:
        confidence = "优"
    elif total_score >= 70:
        confidence = "良"
    elif total_score >= 50:
        confidence = "中"
    else:
        confidence = "差"

    return {
        "total_score": round(total_score, 1),
        "confidence": confidence,
        "categories": category_list,
        "entities": entity_results,
        "issues": all_issues,
        "summary": {
            "facts_count": len(_get_field_value(json_result, "case_summary.key_facts")) if isinstance(_get_field_value(json_result, "case_summary"), dict) and isinstance(_get_field_value(json_result, "case_summary.key_facts"), list) else 0,
            "dispute_focuses_count": len(_get_field_value(json_result, "case_summary.disputed_issues")) if isinstance(_get_field_value(json_result, "case_summary"), dict) and isinstance(_get_field_value(json_result, "case_summary.disputed_issues"), list) else 0,
            "relations_count": len(json_result.get("relations", [])),
            "evidence_admission_fill_rate": _compute_evidence_admission_fill_rate(json_result),
        },
    }
