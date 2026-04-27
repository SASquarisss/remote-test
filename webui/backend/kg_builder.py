"""
将 LLM 解析结果（JSON）转换为 Cytoscape.js 可渲染的 elements。
支持本体论定义的所有实体类型和关系。
"""
import hashlib
from typing import Any, Dict, List

# 节点组别 -> 颜色映射
CATEGORY_COLORS = {
    "norm":   "#3b82f6",   # 蓝色 - 规范层
    "subject":"#22c55e",   # 绿色 - 主体层
    "entity": "#f59e0b",   # 橙色 - 案件层
    "meta":   "#a855f7",   # 紫色 - 元信息
}

# 实体类型 -> 组别
ENTITY_CATEGORY = {
    "Law": "norm",
    "LegalProvision": "norm",
    "LegalProvisionVersion": "norm",
    "CaseType": "norm",
    "GuidingCase": "norm",
    "SentencingStandard": "norm",
    "Person": "subject",
    "Judge": "subject",
    "Attorney": "subject",
    "Clerk": "subject",
    "Prosecutor": "subject",
    "Organization": "subject",
    "Court": "subject",
    "Procuratorate": "subject",
    "LawFirm": "subject",
    "ExpertInstitution": "subject",
    "District": "subject",
    "LegalRole": "subject",
    "CourtCase": "entity",
    "CaseSummary": "entity",
    "TrialOrganization": "entity",
    "JudgmentResult": "entity",
    "ExecutionInfo": "entity",
    "LegalDocument": "entity",
    "Evidence": "entity",
    "DisputeFocus": "entity",
    "Fact": "entity",
}

# 实体类型 -> 显示标签字段优先级
LABEL_PRIORITY = [
    "name", "guiding_case_number", "case_number", "article",
    "case_type", "org_type", "document_number", "content"
]


def pick_label(obj: Dict[str, Any]) -> str:
    """从实体字段中选出最佳显示标签"""
    for key in LABEL_PRIORITY:
        if key in obj and obj[key]:
            val = obj[key]
            if isinstance(val, str):
                # 限制长度，过长则截断
                if len(val) > 30:
                    return val[:27] + "..."
                return val
            elif isinstance(val, list) and val:
                return str(val[0])
    # 最后退路：返回第一个非空字段
    for k, v in obj.items():
        if v and isinstance(v, (str, int, float)):
            s = str(v)
            return (s[:27] + "...") if len(s) > 30 else s
    return "Unnamed"


def build_node(entity_type: str, entity_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """构建 Cytoscape node"""
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


def build_edge(source: str, target: str, relation: str, edge_id: str = None) -> Dict[str, Any]:
    """构建 Cytoscape edge"""
    eid = edge_id or f"{source}_{relation}_{target}"
    return {
        "data": {
            "id": eid,
            "source": source,
            "target": target,
            "label": relation,
            "relation": relation
        },
        "classes": relation.lower()
    }


def extract_entities(parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
从 LLM 解析结果中提取所有实体。
支持两种常见格式：
  1. 顶层键名即实体类型：{"GuidingCase": {...}, "LegalProvision": [...]}
  2. 嵌套在案件中：{"court_case": {"parties": [...]}}
"""
    nodes = []
    edges = []
    seen_ids = set()

    def add_entity(etype: str, obj: Any, parent_id: str = None, relation: str = None):
        if not isinstance(obj, dict):
            return
        # 生成稳定 ID
        eid = obj.get("id") or obj.get("case_number") or obj.get("guiding_case_number") or obj.get("name")
        if not eid:
            # 对于无显式 ID 的嵌套实体，用父ID+类型+哈希生成
            import hashlib
            raw = f"{parent_id or 'root'}_{etype}_{str(obj)}"
            eid = "gen_" + hashlib.md5(raw.encode()).hexdigest()[:8]
        if eid in seen_ids:
            # 已存在，只连边
            if parent_id and relation:
                edges.append(build_edge(parent_id, eid, relation))
            return
        seen_ids.add(eid)
        nodes.append(build_node(etype, eid, obj))
        if parent_id and relation:
            edges.append(build_edge(parent_id, eid, relation))

        # 递归处理子实体（常见嵌套）
        # parties → Person / Organization
        if "parties" in obj and isinstance(obj["parties"], list):
            for p in obj["parties"]:
                ptype = "Person" if p.get("type") == "natural_person" else "Organization"
                add_entity(ptype, p, eid, "INVOLVES")

        # legal_provisions → LegalProvision
        if "legal_provisions" in obj and isinstance(obj["legal_provisions"], list):
            for lp in obj["legal_provisions"]:
                add_entity("LegalProvision", lp, eid, "CITES")

        # case_summary → CaseSummary
        if "case_summary" in obj and isinstance(obj["case_summary"], dict):
            add_entity("CaseSummary", obj["case_summary"], eid, "HAS_SUMMARY")

        # trial_organization → TrialOrganization
        if "trial_organization" in obj and isinstance(obj["trial_organization"], dict):
            add_entity("TrialOrganization", obj["trial_organization"], eid, "HAS_TRIAL_ORG")

        # judgment_result → JudgmentResult
        if "judgment_result" in obj and isinstance(obj["judgment_result"], dict):
            add_entity("JudgmentResult", obj["judgment_result"], eid, "HAS_RESULT")

        # dispute_focuses → DisputeFocus
        if "dispute_focuses" in obj and isinstance(obj["dispute_focuses"], list):
            for df in obj["dispute_focuses"]:
                add_entity("DisputeFocus", df, eid, "HAS_FOCUS")

        # facts → Fact
        if "facts" in obj and isinstance(obj["facts"], list):
            for f in obj["facts"]:
                add_entity("Fact", f, eid, "HAS_FACT")

        # evidence → Evidence
        if "evidence" in obj and isinstance(obj["evidence"], list):
            for ev in obj["evidence"]:
                add_entity("Evidence", ev, eid, "HAS_EVIDENCE")

        # execution_info → ExecutionInfo
        if "execution_info" in obj and isinstance(obj["execution_info"], dict):
            add_entity("ExecutionInfo", obj["execution_info"], eid, "HAS_EXECUTION")

        # legal_documents → LegalDocument
        if "legal_documents" in obj and isinstance(obj["legal_documents"], list):
            for ld in obj["legal_documents"]:
                add_entity("LegalDocument", ld, eid, "HAS_DOCUMENT")

        # guiding_case → GuidingCase（引用指导性案例）
        if "guiding_case" in obj and isinstance(obj["guiding_case"], dict):
            add_entity("GuidingCase", obj["guiding_case"], eid, "REFERENCES_GUIDING")

        # court → Court
        if "court" in obj and isinstance(obj["court"], dict):
            add_entity("Court", obj["court"], eid, "HEARD_BY")

        # judges → Judge
        if "judges" in obj and isinstance(obj["judges"], list):
            for j in obj["judges"]:
                add_entity("Judge", j, eid, "PRESIDED_BY")

    # 处理顶层键
    for key, val in parsed.items():
        # 尝试匹配实体类型
        etype = key[0].upper() + key[1:]  # 驻峰命名
        if etype in ENTITY_CATEGORY:
            if isinstance(val, list):
                for item in val:
                    add_entity(etype, item)
            elif isinstance(val, dict):
                add_entity(etype, val)
        elif isinstance(val, list):
            # 可能是嵌套实体列表（如 parties, legal_provisions）
            for item in val:
                if isinstance(item, dict):
                    item_type = item.get("type", "unknown")
                    if item_type in ["natural_person", "legal_person"]:
                        add_entity("Person", item)
                    elif "credit_code" in item:
                        add_entity("Organization", item)
                    elif "article" in item:
                        add_entity("LegalProvision", item)

    return nodes + edges


def convert_to_cytoscape(parsed_result: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """主入口：将 LLM 解析结果转为 Cytoscape elements"""
    elements = extract_entities(parsed_result)
    return {"elements": elements}
