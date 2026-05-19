"""
evaluation_prompt_renderer.py

基于本体结构动态生成“本体论评估”提示词，
让评估链与 extraction prompt 使用同一份 ontology 结构源。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from ontology.generators.ontology_reader import OntologySchema


EVALUATION_ENTITY_PRIORITY = [
    "GuidingCase",
    "CaseType",
    "CourtCase",
    "CaseSummary",
    "LegalSubject",
    "Judge",
    "Attorney",
    "Prosecutor",
    "Evidence",
    "JudgmentResult",
    "LegalProvision",
    "Fact",
    "DisputeFocus",
]

GRAPH_RELATION_PRIORITY = [
    "has_fact",
    "has_dispute_focus",
    "proves_fact",
    "resolved_by",
    "based_on",
    "submitted_for",
    "judgment_cites",
    "cites",
]

REPO_ROOT = Path(__file__).resolve().parents[2]
RELATION_POLICY_PATH = REPO_ROOT / "ontology" / "relation_policies.yaml"


def load_relation_policies() -> Dict[str, Any]:
    if not RELATION_POLICY_PATH.exists():
        return {"derived_relations": []}
    return yaml.safe_load(RELATION_POLICY_PATH.read_text(encoding="utf-8")) or {"derived_relations": []}


def _pick_entities(ontology: OntologySchema) -> List[Dict[str, Any]]:
    entities = ontology.get("entities") or {}
    ordered: List[Dict[str, Any]] = []
    seen = set()
    for name in EVALUATION_ENTITY_PRIORITY:
        if name in entities:
            ordered.append(entities[name])
            seen.add(name)
    for name in sorted(entities):
        if name not in seen:
            ordered.append(entities[name])
    return ordered


def _entity_field_summary(entity: Dict[str, Any]) -> str:
    required = entity.get("required") or []
    optional = entity.get("optional") or []
    fields = {f.get("field_name"): f for f in (entity.get("fields") or [])}

    lines = []
    if required:
        lines.append("必填字段: " + ", ".join(f"`{x}`" for x in required))
    if optional:
        preview = optional[:8]
        suffix = " ..." if len(optional) > len(preview) else ""
        lines.append("可选字段: " + ", ".join(f"`{x}`" for x in preview) + suffix)

    enum_lines = []
    for field_name in required + optional:
        field_def = fields.get(field_name) or {}
        enum_values = field_def.get("enum_values") or []
        if enum_values:
            preview = ", ".join(f"`{v}`" for v in enum_values[:8])
            if len(enum_values) > 8:
                preview += " ..."
            enum_lines.append(f"`{field_name}`={preview}")
    if enum_lines:
        lines.append("关键枚举: " + " | ".join(enum_lines[:4]))
    return "；".join(lines) if lines else "无显式字段约束"


def render_evaluation_schema_summary(ontology: OntologySchema) -> str:
    entities = ontology.get("entities") or {}
    relations = ontology.get("relations") or {}
    derived_relations = load_relation_policies().get("derived_relations") or []
    lines = [
        "## 当前本体关键实体",
        "",
    ]
    for entity in _pick_entities(ontology):
        name = entity.get("name") or ""
        if name not in entities:
            continue
        parent = entity.get("parent") or "-"
        desc = entity.get("description") or ""
        lines.append(f"- `{name}` | parent=`{parent}` | {desc}".rstrip())
        lines.append("  " + _entity_field_summary(entity))

    lines.extend([
        "",
        "## 当前本体关键关系",
        "",
    ])
    seen = set()
    for rel_name in GRAPH_RELATION_PRIORITY:
        rel = relations.get(rel_name)
        if not rel:
            continue
        seen.add(rel_name)
        lines.append(
            f"- `{rel_name}`: `{rel.get('from_type', '')}` -> `{rel.get('to_type', '')}`"
            f" | cardinality=`{rel.get('cardinality', '')}`"
            f" | {rel.get('description', '')}"
        )
    for rel_name in sorted(relations):
        if rel_name in seen:
            continue
        rel = relations[rel_name]
        lines.append(
            f"- `{rel_name}`: `{rel.get('from_type', '')}` -> `{rel.get('to_type', '')}`"
            f" | cardinality=`{rel.get('cardinality', '')}`"
        )

    if derived_relations:
        lines.extend([
            "",
            "## 自动补图关系",
            "",
        ])
        for rel in derived_relations:
            lines.append(
                f"- `{rel.get('relation_type', '')}`: `{rel.get('from_type', '')}` -> `{rel.get('to_type', '')}`"
                f" | derivation=`{rel.get('derivation_kind', '')}`"
                f" | {rel.get('description', '')}"
            )

    lines.extend([
        "",
        "## 图谱关键检查项",
        "",
        "- `facts`、`dispute_focuses`、`relations` 是当前抽取链的核心评估对象，不可仅按旧式摘要字段替代。",
        "- 若存在 `facts`，优先检查是否有 `has_fact`、`proves_fact` 等关系将事实挂到案件与证据上。",
        "- 若存在 `dispute_focuses`，优先检查是否有 `has_dispute_focus`、`leads_to`、`resolved_by` 等关系形成“案件 -> 争议焦点 -> 裁判结果/法条”主链。",
        "- 若存在 `evidence`，需检查是否通过 `submitted_for` 指向案件，并通过 `proves_fact` 指向 `Fact` 或 `DisputeFocus`。",
        "- 若存在 `judgment_results` 与 `legal_provisions`，需检查是否形成 `judgment_cites` 等裁判依据链。",
        "- 自动补图关系用于结构补全，不应替代 schema 原生关系；评估时要区分“模型未显式抽取”与“后处理可自动派生”。",
        "- 关系合法性需要检查 `source_id`、`target_id` 是否真实引用到输出中的节点，而不是悬空引用。",
    ])
    return "\n".join(lines).strip() + "\n"


def render_evaluation_prompt(ontology: OntologySchema) -> str:
    schema_summary = render_evaluation_schema_summary(ontology).strip()
    return f"""你是一个法律文本解析质量评估专家。你的任务是对 LLM 从法律文本中提取的结构化 JSON 结果进行两部分评估：`parsing_evaluation` 与 `ontology_coverage`。

## 核心原则
1. 严格输出 JSON，不要任何额外解释。
2. 评价必须基于原文证据；若扣分，请指出对应文本依据或明确说明“原文未提供”。
3. 区分“字段为空但原文存在该信息”和“原文确实没有该信息”。
4. 优先评估真实结构化图谱输出，不要只用 `case_summary` 替代 `facts / dispute_focuses / relations`。
5. 必须识别幻觉、关系悬空、枚举值违规、必填字段缺失与关系主链断裂。

## 当前评估所依据的本体摘要
{schema_summary}

## 第一部分：解析结果评估 parsing_evaluation

从以下 6 个维度打分，每个维度 score 范围 0-100，并在 `detail` 中写清楚主要扣分原因：

### D1 结构完整性（5%）
- 顶层 JSON 是否有效、关键顶层键是否存在。
- `court_cases / legal_subjects / legal_provisions / evidence / judgment_results / facts / dispute_focuses / relations` 的类型是否正确。

### D2 实体与图谱完整性（30%）
- 原文中的关键实体是否被提取。
- `facts` 是否覆盖关键案件事实。
- `dispute_focuses` 是否覆盖原文争议焦点。
- `relations` 是否能把案件、证据、事实、争议焦点、裁判结果、法条连成主链。
- 对当前抽取链，`facts / dispute_focuses / relations` 缺失应显著扣分。

### D3 属性准确性（20%）
- 案号、日期、法院名称、案由、角色、法条条号、裁判结果、证据属性是否与原文一致。
- 是否存在原文未提及的幻觉值。

### D4 本体一致性与关系合法性（20%）
- required 字段是否非空。
- 枚举值是否使用本体允许值。
- `relation_type` 是否属于本体定义的关系类型。
- `source_id / target_id` 是否真实指向输出中的节点。
- 是否存在重复实体、重复边、时序异常或明显字段类型错误。

### D5 引用与推理链完整性（15%）
- 法条引用是否完整，法条是否真正参与裁判依据链。
- 证据是否真正挂到案件并指向事实/争议焦点。
- 争议焦点是否能落到裁判结果/法条解决链上。

### D6 语义连贯性（10%）
- `case_summary` 是否具有“事实 -> 争议 -> 结论”结构。
- 文本字段是否客观、规范、信息密度合适。

## 第二部分：本体覆盖评估 ontology_coverage

比较原始文本与本体：
- 文本中出现的重要实体是否被本体定义覆盖。
- 文本中出现的重要关系是否被本体关系类型覆盖。
- 若未覆盖，请给出未覆盖实体/关系和扩展建议。

## 输出 JSON 格式

```json
{{
  "parsing_evaluation": {{
    "total_score": 85,
    "confidence": "良",
    "dimensions": [
      {{"code": "D1", "name": "结构完整性", "score": 90, "detail": "..." }},
      {{"code": "D2", "name": "实体与图谱完整性", "score": 80, "detail": "..." }},
      {{"code": "D3", "name": "属性准确性", "score": 82, "detail": "..." }},
      {{"code": "D4", "name": "本体一致性与关系合法性", "score": 78, "detail": "..." }},
      {{"code": "D5", "name": "引用与推理链完整性", "score": 75, "detail": "..." }},
      {{"code": "D6", "name": "语义连贯性", "score": 88, "detail": "..." }}
    ],
    "issues": [
      {{"field": "facts", "msg": "缺少关键事实节点", "severity": "critical"}},
      {{"field": "relations[3]", "msg": "source_id 指向不存在的节点", "severity": "major"}}
    ],
    "suggestions": [
      "补充 Fact / DisputeFocus 实体抽取",
      "补齐 Evidence -> Fact / DisputeFocus 的 proves_fact 关系"
    ]
  }},
  "ontology_coverage": {{
    "total_score": 80,
    "coverage_items": [
      {{"entity": "Fact", "relation": "proves_fact", "status": "covered"}}
    ],
    "uncovered": [
      {{"entity": "ExpertInstitution", "relation": "鉴定机构参与鉴定", "detail": "文本中出现鉴定机构但抽取结果/本体链路覆盖不足"}}
    ],
    "suggestions": [
      "补充未覆盖关系或增强关系映射逻辑"
    ]
  }}
}}
```

## 重要提醒
1. 你必须优先按当前结构化图谱格式评估，而不是沿用旧版“只有摘要和法条”的心智。
2. 若 `facts / dispute_focuses / relations` 存在，请直接评价其质量；若缺失且原文明显包含相关内容，应明确扣分。
3. 若某字段原文没有，请不要因缺失而机械扣分。
4. 只输出 JSON。"""
