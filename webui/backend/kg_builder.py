"""
将 LLM 解析结果（JSON）转换为 Cytoscape.js 可渲染的 elements。
方案 A：关系展开为边属性，不保留 CaseParticipant / LegalProvisionCitation 中间节点。
"""
import hashlib
from typing import Any, Dict, List

# 节点组别 -> 颜色映射
CATEGORY_COLORS = {
    "norm":   "#3b82f6",
    "subject":"#22c55e",
    "entity": "#f59e0b",
    "meta":   "#a855f7",
}

# 实体类型 -> 组别
ENTITY_CATEGORY = {
    "Law": "norm", "LegalProvision": "norm", "LegalProvisionVersion": "norm",
    "CaseType": "norm", "GuidingCase": "norm", "SentencingStandard": "norm",
    "Person": "subject", "Judge": "subject", "Attorney": "subject",
    "Clerk": "subject", "Prosecutor": "subject", "Organization": "subject",
    "Court": "subject", "Procuratorate": "subject", "LawFirm": "subject",
    "ExpertInstitution": "subject", "District": "subject", "LegalRole": "subject",
    "CourtCase": "entity", "CaseSummary": "entity", "TrialOrganization": "entity",
    "JudgmentResult": "entity", "ExecutionInfo": "entity", "LegalDocument": "entity",
    "Evidence": "entity", "DisputeFocus": "entity", "Fact": "entity",
}

LABEL_PRIORITY = ["name", "guiding_case_number", "case_number", "article", "case_type", "org_type", "content"]


def pick_label(obj: Dict[str, Any]) -> str:
    for key in LABEL_PRIORITY:
        if key in obj and obj[key]:
            val = obj[key]
            if isinstance(val, str):
                return val[:27] + "..." if len(val) > 30 else val
            elif isinstance(val, list) and val:
                return str(val[0])
    for k, v in obj.items():
        if v and isinstance(v, (str, int, float)):
            s = str(v)
            return (s[:27] + "...") if len(s) > 30 else s
    return "Unnamed"


def build_node(entity_type: str, entity_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    cat = ENTITY_CATEGORY.get(entity_type, "meta")
    label = pick_label(data)
    return {
        "data": {
            "id": entity_id,
            "label": label,
            "entity_type": entity_type,
            "category": cat,
            **{k: v for k, v in data.items() if v is not None}
        },
        "classes": cat
    }


def build_edge(source: str, target: str, relation: str, edge_data: Dict[str, Any] = None) -> Dict[str, Any]:
    eid = f"{source}_{relation}_{target}"
    data = {"id": eid, "source": source, "target": target, "label": relation, "relation": relation}
    if edge_data:
        data.update({k: v for k, v in edge_data.items() if v is not None})
    return {"data": data, "classes": relation.lower()}


def safe_id(text: str) -> str:
    """生成稳定 ID，移除特殊字符"""
    return hashlib.md5(str(text).encode("utf-8")).hexdigest()[:12]


def extract_entities(parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes = []
    edges = []
    seen_ids = set()

    def add_node(etype: str, eid: str, data: Dict[str, Any]):
        if eid in seen_ids:
            return eid
        seen_ids.add(eid)
        nodes.append(build_node(etype, eid, data))
        return eid

    # ========== 1. GuidingCase ==========
    gc_data = parsed.get("guiding_case", {})
    gc_id = None
    if gc_data:
        gc_id = gc_data.get("guiding_case_number") or gc_data.get("storage_no") or "guiding_main"
        add_node("GuidingCase", gc_id, gc_data)

    # ========== 2. CaseType ==========
    ct_data = parsed.get("case_type", {})
    ct_id = None
    if ct_data:
        ct_id = safe_id(f"casetype_{ct_data.get('level1')}_{ct_data.get('level2')}")
        add_node("CaseType", ct_id, ct_data)
        if gc_id:
            edges.append(build_edge(gc_id, ct_id, "HAS_CASE_TYPE"))

    # ========== 3. CourtCases + Courts ==========
    case_map = {}  # case_number -> 是否存在
    for cc in parsed.get("court_cases", []):
        cn = cc.get("case_number")
        if not cn:
            continue
        case_map[cn] = True
        add_node("CourtCase", cn, cc)

        # Court 嵌套对象 → 独立 Court 节点 + HEARD_BY 边
        court = cc.get("court", {})
        if court and court.get("name"):
            court_id = court.get("name")
            add_node("Court", court_id, court)
            edges.append(build_edge(cn, court_id, "HEARD_BY"))

        # 与 GuidingCase 关联
        if gc_id:
            edges.append(build_edge(gc_id, cn, "HAS_INSTANCE"))
        # 与 CaseType 关联
        if ct_id:
            edges.append(build_edge(cn, ct_id, "HAS_CASE_TYPE"))

    # ========== 4. LegalSubjects → Person/Organization + INVOLVES 边属性 ==========
    for subj in parsed.get("legal_subjects", []):
        stype = "Person" if subj.get("subject_type") == "natural_person" else "Organization"
        sid = subj.get("name")
        if not sid:
            continue
        add_node(stype, sid, subj)

        for role in subj.get("roles", []):
            case_num = role.get("case_number")
            if case_num and case_num in case_map:
                edges.append(build_edge(case_num, sid, "INVOLVES", {
                    "role_code": role.get("role_code"),
                    "role_name": role.get("role_name"),
                }))

    # ========== 5. LegalProvisions + CITES 边属性 ==========
    for lp in parsed.get("legal_provisions", []):
        statute = lp.get("statute", "")
        article = lp.get("article", "")
        para = lp.get("paragraph", "")
        item = lp.get("item", "")
        # 生成稳定 provision ID
        pid = safe_id(f"{statute}_{article}_{para}_{item}") if article else safe_id(statute)
        add_node("LegalProvision", pid, lp)

        case_num = lp.get("case_number")
        if case_num and case_num in case_map:
            edges.append(build_edge(case_num, pid, "CITES", {
                "citation_position": lp.get("citation_position"),
                "citation_purpose": lp.get("citation_purpose"),
                "statute_name": statute,
            }))

    # ========== 6. CaseSummary ==========
    cs_data = parsed.get("case_summary", {})
    if cs_data:
        cs_id = safe_id(f"summary_{gc_id}") if gc_id else "summary_main"
        add_node("CaseSummary", cs_id, cs_data)
        target = gc_id if gc_id else (list(case_map.keys())[0] if case_map else None)
        if target:
            edges.append(build_edge(target, cs_id, "HAS_SUMMARY"))

    # ========== 7. DisputeFocuses ==========
    for i, df in enumerate(parsed.get("dispute_focuses", [])):
        df_id = safe_id(f"focus_{gc_id}_{i}") if gc_id else f"focus_{i}"
        add_node("DisputeFocus", df_id, df)
        target = gc_id if gc_id else (list(case_map.keys())[0] if case_map else None)
        if target:
            edges.append(build_edge(target, df_id, "HAS_FOCUS"))

    # ========== 8. Facts ==========
    for i, f in enumerate(parsed.get("facts", [])):
        f_id = safe_id(f"fact_{gc_id}_{i}") if gc_id else f"fact_{i}"
        add_node("Fact", f_id, f)
        target = gc_id if gc_id else (list(case_map.keys())[0] if case_map else None)
        if target:
            edges.append(build_edge(target, f_id, "HAS_FACT"))

    return nodes + edges


def convert_to_cytoscape(parsed_result: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    elements = extract_entities(parsed_result)
    return {"elements": elements}
