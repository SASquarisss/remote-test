"""
ontology_reader.py — 从 legal_ontology_v2.yaml 读取并解析本体结构。

返回结构化的 OntologySchema 对象供渲染引擎使用。
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict


class EntityField(TypedDict):
    field_name: str
    field_type: str
    required: bool
    enum_values: Optional[List[str]]
    description: str


class EntityDef(TypedDict):
    name: str
    parent: Optional[str]
    required: List[str]
    optional: List[str]
    description: str
    fields: List[EntityField]


class RelationDef(TypedDict):
    name: str
    from_type: str
    to_type: str
    cardinality: str
    attributes: List[str]
    description: str


class OntologySchema(TypedDict):
    entities: Dict[str, EntityDef]
    relations: Dict[str, RelationDef]
    constraints: List[Dict[str, str]]
    engineering: Dict[str, Any]


# 内联类型映射：YAML 字段名 → 用于提示词的中文描述
TYPE_HINT_MAP = {
    "str": "字符串",
    "int": "整数",
    "float": "小数",
    "bool": "布尔值",
    "date": "日期 (YYYY-MM-DD)",
    "datetime": "日期时间 (YYYY-MM-DD HH:MM:SS)",
    "List[str]": "字符串列表",
    "Optional[str]": "可选字符串",
    "Optional[int]": "可选整数",
}


def _normalize_field_type(raw: str) -> str:
    """规范化字段类型描述"""
    raw = raw.strip()
    # Handle Literal[...] — extract all enum-like values
    m = re.match(r"Literal\[(.+)\]", raw)
    if m:
        inner = m.group(1)
        vals = [v.strip().strip('"').strip("'") for v in inner.split(",")]
        return "enum", vals
    if raw.startswith("Optional["):
        inner = raw[9:-1]
        return _normalize_field_type(inner)
    if raw.startswith("List["):
        inner = raw[5:-1]
        base, _ = _normalize_field_type(inner) if inner.startswith("Literal") else (inner, None)
        return f"List[{base}]", None
    return raw, None


def load_ontology(path: str) -> OntologySchema:
    """从 YAML 文件加载本体，返回结构化的 OntologySchema"""
    import yaml

    path = str(Path(path).expanduser().resolve())
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    entities: Dict[str, EntityDef] = {}
    relations: Dict[str, RelationDef] = {}

    # --- 解析主 types 块 ---
    types = raw.get("types", {})
    for name, defn in types.items():
        if "from" in defn or "to" in defn:
            # 是关系定义（嵌入在 types 中的关系）
            rel_name = name
            relations[rel_name] = RelationDef(
                name=rel_name,
                from_type=defn.get("from", ""),
                to_type=defn.get("to", ""),
                cardinality=defn.get("cardinality", "many_to_many"),
                attributes=defn.get("attributes", defn.get("optional_attributes", [])),
                description=defn.get("description", ""),
            )
            continue

        # 实体定义
        parent = defn.get("is_a")
        required = defn.get("required", []) or []
        optional = defn.get("optional", []) or []
        desc = defn.get("description", "")
        fields: List[EntityField] = []

        # 收集所有字段：required + optional，标注是否必须
        all_required = set(required)
        for fname in required + optional:
            enum_values = None
            # 检查枚举 (如 role_code_enum, ... )
            enum_key = f"{fname}_enum"
            raw_enum = defn.get(enum_key, None)
            if raw_enum and isinstance(raw_enum, list):
                enum_values = [str(v) for v in raw_enum]

            # 从 description 获取类型提示（简单方式）
            ftype = "str"
            desc_for_field = ""

            fields.append(EntityField(
                field_name=fname,
                field_type=ftype,
                required=fname in all_required,
                enum_values=enum_values,
                description=desc_for_field,
            ))

        entities[name] = EntityDef(
            name=name,
            parent=parent,
            required=required,
            optional=optional,
            description=desc,
            fields=fields,
        )

    # --- 解析独立的 relations 块 ---
    for rel_name, defn in raw.get("relations", {}).items():
        to_type = defn.get("to", "")
        if isinstance(to_type, list):
            to_type = ", ".join(to_type)
        relations[rel_name] = RelationDef(
            name=rel_name,
            from_type=defn.get("from", ""),
            to_type=to_type,
            cardinality=defn.get("cardinality", "many_to_many"),
            attributes=defn.get("attributes", defn.get("optional_attributes", [])),
            description=defn.get("description", ""),
        )

    constraints = raw.get("constraints", [])
    engineering = raw.get("engineering", {})

    return OntologySchema(
        entities=entities,
        relations=relations,
        constraints=constraints,
        engineering=engineering,
    )


def get_all_enum_tables(ontology: OntologySchema) -> Dict[str, Dict[str, Any]]:
    """聚合所有实体的所有枚举字段，返回 {field_path: {values, description}}"""
    result: Dict[str, Dict[str, Any]] = {}
    for ename, edef in ontology["entities"].items():
        for field in edef["fields"]:
            if field["enum_values"]:
                path = f"{ename}.{field['field_name']}"
                result[path] = {
                    "values": field["enum_values"],
                    "description": edef["description"],
                }
    return result


def get_entity_for_extraction(ontology: OntologySchema) -> List[Dict[str, Any]]:
    """返回提取管线关心的实体列表（GuidingCase/CourtCase/LegalSubject 等）"""
    # 从本体提取管线关心的实体，按顺序排列
    priority = [
        "GuidingCase", "CaseType", "CourtCase", "LegalSubject",
        "LegalRole", "LegalProvision", "CaseSummary",
        "Judge", "Attorney", "Prosecutor", "TrialOrganization",
        "Evidence", "JudgmentResult", "DisputeFocus", "Fact",
        "LitigationClaim", "ProceduralOpinion", "ArgumentPoint",
        "JudicialAssessment",
        "CaseParticipant", "Court", "Organization",
    ]
    result = []
    for name in priority:
        if name in ontology["entities"]:
            result.append({
                "name": name,
                "def": ontology["entities"][name],
            })
    return result


if __name__ == "__main__":
    import json
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "ontology/schemas/legal_ontology_v2.yaml"
    repo_root = Path(__file__).resolve().parents[2]
    full_path = repo_root / path
    onto = load_ontology(str(full_path))
    print(f"实体数: {len(onto['entities'])}")
    print(f"关系数: {len(onto['relations'])}")
    print(f"约束数: {len(onto['constraints'])}")
    enums = get_all_enum_tables(onto)
    print(f"枚举字段数: {len(enums)}")
    for path, info in sorted(enums.items()):
        print(f"  {path}: {len(info['values'])} 个值")
