"""
ontology_prompt_gen.py
从 legal_ontology_v2.yaml 自动生成结构化的 LLM 提取提示词。
替代手写的 guiding_case_ontology_aligned_v3.txt。
"""
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


# ==================== 结构化类型 ====================

class EnumField(TypedDict):
    field_path: str
    enum_values: List[str]
    description: str
    source_entity: str

class EntityDef(TypedDict):
    name: str
    is_a: Optional[str]
    required: List[str]
    optional: List[str]
    description: str
    enums: Dict[str, List[str]]  # field_name -> values

class OntologySchema(TypedDict):
    entities: Dict[str, EntityDef]
    relations: Dict[str, Any]
    version: str


# ==================== 读取层 ====================

def load_ontology(path: str) -> OntologySchema:
    """从 YAML 加载本体，返回结构化 OntologySchema"""
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    entities = {}
    types = raw.get("types", {})

    for name, defn in types.items():
        # 跳过非实体的关系定义（没有 is_a 且没有 required/optional）
        if "from" in defn and "to" in defn:
            continue

        entity: EntityDef = {
            "name": name,
            "is_a": defn.get("is_a"),
            "required": defn.get("required", []),
            "optional": defn.get("optional", []),
            "description": defn.get("description", ""),
            "enums": {},
        }

        # 提取所有 *_enum 字段和普通 enum 字段
        for key, val in defn.items():
            if key.endswith("_enum") and isinstance(val, list):
                field_name = key.replace("_enum", "")
                entity["enums"][field_name] = val

        entities[name] = entity

    # 解析继承关系，把父类的枚举合并到子类
    def _inherit_enums(name: str, visited: set = None):
        if visited is None:
            visited = set()
        if name in visited or name not in entities:
            return
        visited.add(name)
        entity = entities[name]
        parent_name = entity["is_a"]
        if parent_name and parent_name in entities:
            _inherit_enums(parent_name, visited)
            parent = entities[parent_name]
            for field, vals in parent["enums"].items():
                if field not in entity["enums"]:
                    entity["enums"][field] = vals

    for name in entities:
        _inherit_enums(name)

    return OntologySchema(
        entities=entities,
        relations=raw.get("relations", {}),
        version=raw.get("engineering", {}).get("data_version", "unknown"),
    )


def get_relevant_entities(ontology: OntologySchema, source_type: str = "guiding_case") -> List[str]:
    """
    根据提取场景，返回本体系列中需要提取的实体。
    guiding_case 场景需要提取：GuidingCase, CaseType, CourtCase, LegalSubject,
    LegalProvision, CaseSummary, JudgmentResult, Evidence 等。
    """
    # 从文本中可直接提取的实体
    extractable = [
        "GuidingCase", "CaseType", "CourtCase", "Person", "Organization",
        "LegalProvision", "CaseSummary", "Evidence", "JudgmentResult",
        "TrialOrganization", "DisputeFocus", "Fact",
    ]
    return [e for e in extractable if e in ontology["entities"]]


def get_enum_table(ontology: OntologySchema, entity_names: List[str]) -> List[EnumField]:
    """聚合指定实体的所有枚举字段"""
    table = []
    for ename in entity_names:
        entity = ontology["entities"].get(ename)
        if not entity:
            continue
        for field, values in entity["enums"].items():
            # 跳过工程字段
            if field in ("status", "examination_status", "admission_status", "probative_force",
                         "document_type", "firm_type", "procuratorate_level", "court_level",
                         "execution_status", "sentence_unit", "standard_type"):
                continue
            table.append(EnumField(
                field_path=f"{ename}.{field}",
                enum_values=values,
                description=entity["description"],
                source_entity=ename,
            ))
    return table


# ==================== 渲染层 ====================

def render_enum_table(table: List[EnumField]) -> str:
    """渲染枚举值参考表为 markdown 表格"""
    if not table:
        return ""

    lines = [
        "## 枚举值参考表（自动生成）\n",
        "| 字段路径 | 允许值 | 说明 |",
        "|---|---|---|",
    ]
    for ef in sorted(table, key=lambda x: x["field_path"]):
        vals = ", ".join(f"`{v}`" for v in ef["enum_values"])
        desc = ef["description"][:60]
        lines.append(f"| `{ef['field_path']}` | {vals} | {desc} |")

    lines.append("")
    return "\n".join(lines)


def render_entity_fields(ontology: OntologySchema, entity_names: List[str]) -> str:
    """渲染实体字段说明"""
    sections = []
    for ename in entity_names:
        entity = ontology["entities"].get(ename)
        if not entity:
            continue

        lines = [f"### {ename}"]
        if entity["description"]:
            lines.append(f"{entity['description']}\n")

        all_fields = entity["required"] + [f for f in entity["optional"] if not f.endswith("_enum")]
        if not all_fields:
            sections.append("\n".join(lines))
            continue

        lines.append("| 字段 | 必填 | 类型/枚举 |")
        lines.append("|---|---|---|")

        for field in all_fields:
            is_required = "是" if field in entity["required"] else "否"
            field_type = "string"

            # 检查是否有枚举
            if field in entity["enums"]:
                vals = ", ".join(entity["enums"][field])
                field_type = f"enum: {vals}"
            elif field in ("filing_date", "judgment_date", "publication_date"):
                field_type = "date (YYYY-MM-DD)"
            elif field == "binding_force":
                field_type = "enum: mandatory, persuasive, reference"
            elif field == "case_level":
                field_type = "enum: guiding_case, typical_case, reference_case"

            lines.append(f"| `{field}` | {is_required} | {field_type} |")

        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def render_json_schema(ontology: OntologySchema, entity_names: List[str]) -> str:
    """自动生成 JSON 输出模板。输出 snake_case key 名，与评估器和 pydantic 模型对齐。"""
    # 实体名 -> JSON key 映射表
    KEY_MAP = {
        "GuidingCase": "guiding_case",
        "CaseType": "case_type",
        "CourtCase": "court_cases",
        "LegalProvision": "legal_provisions",
        "Evidence": "evidence",
        "JudgmentResult": "judgment_results",
        "CaseSummary": "case_summary",
        "DisputeFocus": "dispute_focuses",
        "Fact": "facts",
        "TrialOrganization": "trial_organizations",
    }
    # 输出为列表（数组）的实体
    LIST_ENTITIES = {"CourtCase", "LegalProvision", "Evidence", "JudgmentResult",
                     "DisputeFocus", "Fact", "TrialOrganization"}

    lines = [
        "```json",
        "{",
    ]

    for ename in entity_names:
        entity = ontology["entities"].get(ename)
        if not entity:
            continue
        key = KEY_MAP.get(ename)
        if not key:
            continue

        is_list = ename in LIST_ENTITIES
        if is_list:
            lines.append(f'  "{key}": [')
            lines.append("    {")
        elif ename == "CaseSummary":
            lines.append(f'  "{key}": {{')
        else:
            # Single dict entities (GuidingCase, CaseType)
            lines.append(f'  "{key}": {{')

        all_fields = entity["required"] + [f for f in entity["optional"] if not f.endswith("_enum") and f != "enums"]

        for field in all_fields:
            if field in entity["enums"]:
                vals = "|".join(entity["enums"][field])
                lines.append(f'      "{field}": "{vals}",')
            elif field == "credit_code":
                lines.append(f'      "{field}": null,')
            elif field in ("amount_involved", "claim_amount", "compensation_amount", "registered_capital"):
                lines.append(f'      "{field}": "",')
            elif field in ("key_facts", "disputed_issues", "conclusion", "content", "specific_judgment", "reasoning", "summary"):
                lines.append(f'      "{field}": "",')
            else:
                lines.append(f'      "{field}": "",')

        if is_list:
            lines.append("    }")
            lines.append("  ],")
        elif ename == "CaseSummary":
            # Add guiding_points since it's not in ontology optional
            lines.append('      "guiding_points": ""')
            lines.append("  },")
        else:
            lines.append("  },")

    lines.append("}")
    lines.append("```")
    return "\n".join(lines)


def render_static_header() -> str:
    """返回静态的任务描述头部"""
    return """你是一个专业的法律文本解析工具。你的任务是从人民法院案例库的案件文本中提取结构化信息。

## 核心原则
1. 严格输出JSON，不要任何额外解释
2. 使用下方枚举值参考表中定义的值，不要自创
3. 尽量从文本中提取完整信息，不要遗漏
4. 所有缺失字段必须尽力从其他文本源推断，不能留空
5. fielding_date 从案号年份或文本中最早日期推断
"""


def render_mapping_rules() -> str:
    """返回固定的映射规则"""
    return """## 映射规则

### 案件号提取规则
- 案号格式：(YYYY)地区简称+案由+第N号
- 常见后缀：民初、刑初、行初、民终、刑终、行终、再、执、执恢
- 从 basic_facts、judgment_reason、related_info、related_judgment_body 中全面提取

### 法院层级映射
- 最高人民法院 → supreme
- 高级人民法院 → high
- 中级人民法院 → intermediate
- 基层人民法院 → basic
- 专门法院（知识产权/互联网/海事等）→ special

### 审级映射规则
- 案号含"初"字 → first_instance
- 案号含"终"字 → second_instance
- 案号含"再"或"提审" → retrial
- 案号含"执" → execution

### 法条文本规则
- article 字段：纯数字。"第30条"→"30"，"第二百六十六条"→"266"，"第二十条之一"→"236之一"
- content 字段：法条原文片段50-100字，不能为空
- citation_position：basic_facts/judgment_reason/judgment_essence/related_info/related_law
- citation_purpose：适用依据/说理依据/反驳依据
"""


def generate_prompt(ontology_path: str = None, output_path: str = None) -> str:
    """完整提示词生成流水线"""
    if ontology_path is None:
        ontology_path = str(REPO_ROOT / "ontology/schemas/legal_ontology_v2.yaml")

    ontology = load_ontology(ontology_path)
    entities = get_relevant_entities(ontology)
    enum_table = get_enum_table(ontology, entities)

    parts = [
        render_static_header(),
        render_mapping_rules(),
        "---\n",
        render_enum_table(enum_table),
        "---\n",
        "## 实体字段说明\n",
        render_entity_fields(ontology, entities),
        "\n---\n",
        "## 输出 JSON Schema\n",
        render_json_schema(ontology, entities),
        "\n---\n",
        "## 案件文本\n{case_text}",
        "\n---\n",
        "## JSON输出\n",
    ]

    prompt = "\n".join(parts)

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        print(f"Prompt written to {output_path}")
        print(f"Total chars: {len(prompt)}")

    return prompt


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="ontology/prompts/auto_generated_v1.txt")
    args = parser.parse_args()
    output = str(REPO_ROOT / args.output) if not os.path.isabs(args.output) else args.output
    generate_prompt(output_path=output)
