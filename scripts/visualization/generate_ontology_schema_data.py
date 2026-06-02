#!/usr/bin/env python3
"""
Generate front-end ontology schema data for `visualization/ontology_v2.2.html`.

Source of truth:
- ontology/schemas/legal_ontology_v2.yaml
- ontology/schemas/legal_ontology_v2.zh.yaml

Output:
- visualization/data/ontology_schema_data.js
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
ONTOLOGY_EN = REPO_ROOT / "ontology" / "schemas" / "legal_ontology_v2.yaml"
ONTOLOGY_ZH = REPO_ROOT / "ontology" / "schemas" / "legal_ontology_v2.zh.yaml"
OUTPUT_JS = REPO_ROOT / "visualization" / "data" / "ontology_schema_data.js"
REFACTORED_OUTPUT_JS = REPO_ROOT / "visualization" / "ontology-refactored" / "src" / "data" / "schema.js"

ROOT_COLORS = {
    "LegalNorm": {"bg": "#2980b9", "border": "#154360", "group": "LegalNorm系"},
    "JudicialEntity": {"bg": "#d35400", "border": "#7e2e00", "group": "JudicialEntity系"},
    "LegalSubject": {"bg": "#8e44ad", "border": "#512e5c", "group": "LegalSubject系"},
    "Person": {"bg": "#16a085", "border": "#0b5345", "group": "Person系"},
}
DEFAULT_COLOR = {"bg": "#7f8c8d", "border": "#5d6d7e", "group": "其他"}

# Preserve current visual language where possible; unknown types fall back by root.
ENTITY_STYLE_OVERRIDES = {
    "CourtCase": {"shape": "box", "color": "#FFA07A", "border": "#E8875A", "size": 22, "note": "一审案件"},
    "Person": {"shape": "square", "color": "#90EE90", "border": "#65A765", "size": 18, "note": "原告/申请人"},
    "LegalProvision": {"shape": "hexagon", "color": "#483D8B", "border": "#3A2D6E", "size": 16, "note": "法条/法律依据"},
    "Law": {"shape": "hexagon", "color": "#483D8B", "border": "#3A2D6E", "size": 16, "note": "法律"},
    "Evidence": {"shape": "database", "color": "#CD853F", "border": "#A06B32", "size": 6, "note": "证据"},
    "Fact": {"shape": "ellipse", "color": "#8E44AD", "border": "#6C3483", "size": 14, "note": "案件事实"},
    "DisputeFocus": {"shape": "star", "color": "#E67E22", "border": "#CA6F1E", "size": 18, "note": "争议焦点"},
    "LitigationClaim": {"shape": "box", "color": "#2563EB", "border": "#1D4ED8", "size": 18, "note": "各方诉求"},
    "ProceduralOpinion": {"shape": "box", "color": "#0EA5E9", "border": "#0284C7", "size": 16, "note": "意见表达"},
    "ArgumentPoint": {"shape": "diamond", "color": "#7C3AED", "border": "#6D28D9", "size": 15, "note": "理由点"},
    "JudicialAssessment": {"shape": "hexagon", "color": "#DC2626", "border": "#B91C1C", "size": 18, "note": "法院评判"},
    "LegalRole": {"shape": "diamond", "color": "#FFA500", "border": "#CC8400", "size": 16, "note": "诉讼角色"},
    "CaseSummary": {"shape": "star", "color": "#32CD32", "border": "#28A428", "size": 20, "note": "争议焦点"},
    "LegalSubject": {"shape": "triangle", "color": "#B0C4DE", "border": "#7B899B", "size": 16, "note": "辅助主体"},
    "LegalNorm": {"shape": "triangle", "color": "#B0C4DE", "border": "#8DA3B8", "size": 16, "note": "辅助规范"},
    "GuidingCase": {"shape": "star", "color": "#4682B4", "border": "#35608C", "size": 22, "note": "指导性案例"},
}
ROOT_STYLE_DEFAULTS = {
    "LegalNorm": {"shape": "hexagon", "size": 16},
    "JudicialEntity": {"shape": "box", "size": 18},
    "LegalSubject": {"shape": "triangle", "size": 16},
    "Person": {"shape": "square", "size": 18},
}

EN_DESCRIPTION_OVERRIDES = {
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
    "Fact": "Case fact",
    "LitigationClaim": "Litigation claim / request",
    "ProceduralOpinion": "Procedural opinion / stance",
    "ArgumentPoint": "Argument point / reasoning unit",
    "JudicialAssessment": "Judicial assessment / court response",
    "CaseParticipant": "Case participant (with trial-level role changes)",
    "LegalProvisionElement": "Legal provision constitutive element",
}

RELATION_LABEL_OVERRIDES = {
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
    "proves_focus": "证明争议",
    "includes": "包含法官",
    "includes_clerk": "配备书记员",
    "appeals_to": "上诉至",
    "retries_from": "再审源自",
    "has_dispute_focus": "具有争议焦点",
    "has_fact": "具有事实",
    "raises_claim": "提出诉求",
    "expresses_opinion": "表达意见",
    "supports_claim": "支撑诉求",
    "supports_opinion": "支撑意见",
    "targets_subject": "指向主体",
    "claims_focus": "诉求对应焦点",
    "opines_on_focus": "意见围绕焦点",
    "assesses_focus": "评判争议焦点",
    "responds_to_claim": "回应诉求",
    "responds_to_opinion": "回应意见",
    "evaluates_argument": "评价理由",
    "based_on_fact": "基于事实",
    "based_on_provision": "基于法条",
    "supports_result": "支撑裁判",
    "matches_element": "匹配要件",
    "resolved_by": "由法条解决",
    "leads_to_fact": "推导出",
    "leads_to_focus": "推导出",
}


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def get_desc(block: Dict[str, Any], key: str, section: str) -> str:
    value = (((block.get(section) or {}).get(key) or {}).get("description")) or ""
    return str(value).strip().strip('"')


def collect_entities(raw_en: Dict[str, Any], raw_zh: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    entities: Dict[str, Dict[str, Any]] = {}
    for name, spec in (raw_en.get("types") or {}).items():
        if "from" in spec or "to" in spec:
            continue
        enums = {}
        for key, value in spec.items():
            if key.endswith("_enum") and isinstance(value, list):
                enums[key[:-5]] = value
        constraints = spec.get("constraints", []) or []
        entities[name] = {
            "description": get_desc(raw_zh, name, "types") or str(spec.get("description") or "").strip().strip('"'),
            "required": list(spec.get("required", []) or []),
            "optional": list(spec.get("optional", []) or []),
            "enums": enums,
            "constraints": constraints,
            "is_a": spec.get("is_a"),
        }
    return entities


def collect_relations(raw_en: Dict[str, Any], raw_zh: Dict[str, Any]) -> List[Dict[str, Any]]:
    relations: List[Dict[str, Any]] = []
    for name, spec in (raw_en.get("types") or {}).items():
        if "from" not in spec and "to" not in spec:
            continue
        relations.append(
            {
                "name": name,
                "from": spec.get("from"),
                "to": spec.get("to"),
                "cardinality": spec.get("cardinality", "many_to_many"),
                "attributes": list(spec.get("attributes", []) or []),
                "optional_attributes": list(spec.get("optional_attributes", []) or []),
                "description": get_desc(raw_zh, name, "types") or str(spec.get("description") or "").strip().strip('"'),
                "acyclic": bool(spec.get("acyclic", False)),
            }
        )
    for name, spec in (raw_en.get("relations") or {}).items():
        relations.append(
            {
                "name": name,
                "from": spec.get("from"),
                "to": spec.get("to"),
                "cardinality": spec.get("cardinality", "many_to_many"),
                "attributes": list(spec.get("attributes", []) or []),
                "optional_attributes": list(spec.get("optional_attributes", []) or []),
                "description": get_desc(raw_zh, name, "relations") or str(spec.get("description") or "").strip().strip('"'),
                "acyclic": bool(spec.get("acyclic", False)),
            }
        )
    return relations


def build_inheritance_chain(entity_name: str, entities: Dict[str, Dict[str, Any]]) -> List[str]:
    chain = [entity_name]
    visited = {entity_name}
    parent = entities.get(entity_name, {}).get("is_a")
    while parent and parent not in visited:
        chain.append(parent)
        visited.add(parent)
        parent = entities.get(parent, {}).get("is_a")
    return chain


def resolve_root(entity_name: str, entities: Dict[str, Dict[str, Any]]) -> str | None:
    for item in build_inheritance_chain(entity_name, entities):
        if item in ROOT_COLORS:
            return item
    return None


def derive_entity_style(entity_name: str, entities: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    if entity_name in ENTITY_STYLE_OVERRIDES:
        return dict(ENTITY_STYLE_OVERRIDES[entity_name])
    root = resolve_root(entity_name, entities)
    palette = ROOT_COLORS.get(root or "", DEFAULT_COLOR)
    base = ROOT_STYLE_DEFAULTS.get(root or "", {"shape": "box", "size": 18})
    return {
        "shape": base["shape"],
        "color": palette["bg"],
        "border": palette["border"],
        "size": base["size"],
        "note": (palette.get("group") or "自动样式"),
    }


def build_relations_by_entity(
    entities: Dict[str, Dict[str, Any]], relations: List[Dict[str, Any]]
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    result = {name: {"outgoing": [], "incoming": []} for name in entities}
    for rel in relations:
        sources = rel["from"] if isinstance(rel["from"], list) else [rel["from"]]
        targets = rel["to"] if isinstance(rel["to"], list) else [rel["to"]]
        for source in sources:
            for target in targets:
                if source in result:
                    result[source]["outgoing"].append(
                        {
                            "relation": rel["name"],
                            "target": target,
                            "cardinality": rel["cardinality"],
                            "description": rel["description"],
                            "attributes": rel["attributes"] + rel["optional_attributes"],
                        }
                    )
                if target in result:
                    result[target]["incoming"].append(
                        {
                            "relation": rel["name"],
                            "source": source,
                            "cardinality": rel["cardinality"],
                            "description": rel["description"],
                            "attributes": rel["attributes"] + rel["optional_attributes"],
                        }
                    )
    return result


def js_decl(name: str, value: Any, mode: str = "var") -> str:
    keyword = "var"
    if mode == "export_const":
        keyword = "export const"
    elif mode == "let":
        keyword = "let"
    return f"{keyword} {name} = {json.dumps(value, ensure_ascii=False, indent=2)};\n"


def build_legacy_bundle(payload: Dict[str, Any]) -> str:
    return "".join([
        "// Auto-generated file. Do not edit by hand.\n",
        f"// Source: {ONTOLOGY_EN.relative_to(REPO_ROOT)} + {ONTOLOGY_ZH.relative_to(REPO_ROOT)}\n",
        js_decl("ENTITY_DATA", payload["entities"]),
        js_decl("RELATIONS_BY_ENTITY", payload["relations_by_entity"]),
        js_decl("RELATION_DETAILS", payload["relation_details"]),
        js_decl("ROOT_COLORS", ROOT_COLORS),
        js_decl("DEFAULT_COLOR", DEFAULT_COLOR),
        js_decl("ENTITY_STYLES", payload["entity_styles"]),
        "var TERM_SHAPES = {};\n",
        "var TERM_COLORS = {};\n",
        "var TERM_SIZES = {};\n",
        "Object.keys(ENTITY_STYLES).forEach(function(k) {\n"
        "  TERM_SHAPES[k] = ENTITY_STYLES[k].shape;\n"
        "  TERM_COLORS[k] = { bg: ENTITY_STYLES[k].color, border: ENTITY_STYLES[k].border };\n"
        "  TERM_SIZES[k] = ENTITY_STYLES[k].size || 18;\n"
        "});\n"
        "window.__TERM_SHAPES = TERM_SHAPES;\n"
        "window.__TERM_COLORS = TERM_COLORS;\n"
        "window.__TERM_SIZES = TERM_SIZES;\n",
        js_decl("INHERITANCE_CHAIN", payload["inheritance_chain"]),
        "function getRootColor(typeName) {\n"
        "  var chain = INHERITANCE_CHAIN[typeName];\n"
        "  if (!chain) return DEFAULT_COLOR;\n"
        "  for (var i = 0; i < chain.length; i++) {\n"
        "    if (ROOT_COLORS[chain[i]]) return ROOT_COLORS[chain[i]];\n"
        "  }\n"
        "  return DEFAULT_COLOR;\n"
        "}\n",
        js_decl("ZH_LABELS", payload["zh_labels"]),
        js_decl("EN_DESCRIPTIONS", payload["en_descriptions"]),
        js_decl("ABSTRACT_ROOTS", payload["abstract_roots"]),
        js_decl("TYPE_NAMES", payload["type_names"]),
        js_decl("IS_A_EDGES", payload["is_a_edges"]),
        js_decl("RELATION_EDGES", payload["relation_edges"]),
        js_decl("RELATION_LABELS", payload["relation_labels"]),
        js_decl("RELATION_DESC", payload["relation_desc"]),
    ])


def build_refactored_bundle(payload: Dict[str, Any]) -> str:
    return "".join([
        "// Auto-generated file. Do not edit by hand.\n",
        f"// Source: {ONTOLOGY_EN.relative_to(REPO_ROOT)} + {ONTOLOGY_ZH.relative_to(REPO_ROOT)}\n",
        js_decl("ENTITY_DATA", payload["entities"], "export_const"),
        js_decl("RELATIONS_BY_ENTITY", payload["relations_by_entity"], "let"),
        js_decl("RELATION_DETAILS", payload["relation_details"], "let"),
        js_decl("ROOT_COLORS", ROOT_COLORS, "let"),
        js_decl("DEFAULT_COLOR", DEFAULT_COLOR, "let"),
        js_decl("ENTITY_STYLES", payload["entity_styles"], "export_const"),
        js_decl("TERM_SHAPES", {}, "let"),
        js_decl("TERM_COLORS", {}, "let"),
        js_decl("TERM_SIZES", {}, "let"),
        "Object.keys(ENTITY_STYLES).forEach(function(k) {\n"
        "  TERM_SHAPES[k] = ENTITY_STYLES[k].shape;\n"
        "  TERM_COLORS[k] = { bg: ENTITY_STYLES[k].color, border: ENTITY_STYLES[k].border };\n"
        "  TERM_SIZES[k] = ENTITY_STYLES[k].size || 18;\n"
        "});\n",
        js_decl("INHERITANCE_CHAIN", payload["inheritance_chain"], "let"),
        "function getRootColor(typeName) {\n"
        "  let chain = INHERITANCE_CHAIN[typeName];\n"
        "  if (!chain) return DEFAULT_COLOR;\n"
        "  for (let i = 0; i < chain.length; i++) {\n"
        "    if (ROOT_COLORS[chain[i]]) return ROOT_COLORS[chain[i]];\n"
        "  }\n"
        "  return DEFAULT_COLOR;\n"
        "}\n",
        js_decl("ZH_LABELS", payload["zh_labels"], "export_const"),
        js_decl("EN_DESCRIPTIONS", payload["en_descriptions"], "export_const"),
        js_decl("ABSTRACT_ROOTS", payload["abstract_roots"], "let"),
        js_decl("TYPE_NAMES", payload["type_names"], "export_const"),
        js_decl("IS_A_EDGES", payload["is_a_edges"], "let"),
        js_decl("RELATION_EDGES", payload["relation_edges"], "export_const"),
        js_decl("RELATION_LABELS", payload["relation_labels"], "export_const"),
        js_decl("RELATION_DESC", payload["relation_desc"], "let"),
    ])


def main() -> None:
    raw_en = load_yaml(ONTOLOGY_EN)
    raw_zh = load_yaml(ONTOLOGY_ZH)

    entities = collect_entities(raw_en, raw_zh)
    relations = collect_relations(raw_en, raw_zh)

    abstract_roots = {name: 1 for name, spec in entities.items() if not spec.get("is_a")}
    type_names = [name for name in entities.keys() if name not in abstract_roots]
    is_a_edges = [[name, spec["is_a"]] for name, spec in entities.items() if spec.get("is_a")]

    relations_by_entity = build_relations_by_entity(entities, relations)
    relation_details = {
        rel["name"]: {
            "name": rel["name"],
            "cardinality": rel["cardinality"],
            "description": rel["description"],
            "attributes": rel["attributes"],
            "optional_attributes": rel["optional_attributes"],
            "acyclic": rel["acyclic"],
        }
        for rel in relations
    }

    inheritance_chain = {name: build_inheritance_chain(name, entities) for name in entities}
    entity_styles = {name: derive_entity_style(name, entities) for name in entities}
    zh_labels = {name: data["description"] or name for name, data in entities.items()}
    en_descriptions = {
        name: EN_DESCRIPTION_OVERRIDES.get(name, name)
        for name in entities
    }
    relation_labels = {
        rel["name"]: RELATION_LABEL_OVERRIDES.get(rel["name"], rel["description"] or rel["name"])
        for rel in relations
    }
    relation_desc = {}
    relation_edges: List[List[str]] = []
    for rel in relations:
        sources = rel["from"] if isinstance(rel["from"], list) else [rel["from"]]
        targets = rel["to"] if isinstance(rel["to"], list) else [rel["to"]]
        relation_desc[rel["name"]] = f"{', '.join(sources)} → {', '.join(targets)} ({rel['cardinality']})"
        for source in sources:
            for target in targets:
                relation_edges.append([rel["name"], source, target])

    payload = {
        "entities": entities,
        "relations_by_entity": relations_by_entity,
        "relation_details": relation_details,
        "entity_styles": entity_styles,
        "inheritance_chain": inheritance_chain,
        "zh_labels": zh_labels,
        "en_descriptions": en_descriptions,
        "abstract_roots": abstract_roots,
        "type_names": type_names,
        "is_a_edges": is_a_edges,
        "relation_edges": relation_edges,
        "relation_labels": relation_labels,
        "relation_desc": relation_desc,
    }
    legacy_text = build_legacy_bundle(payload)
    refactored_text = build_refactored_bundle(payload)
    OUTPUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JS.write_text(legacy_text, encoding="utf-8")
    REFACTORED_OUTPUT_JS.parent.mkdir(parents=True, exist_ok=True)
    REFACTORED_OUTPUT_JS.write_text(refactored_text, encoding="utf-8")
    print(f"Wrote {OUTPUT_JS}")
    print(f"Wrote {REFACTORED_OUTPUT_JS}")


if __name__ == "__main__":
    main()
