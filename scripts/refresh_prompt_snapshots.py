#!/usr/bin/env python3
"""
refresh_prompt_snapshots.py

统一刷新 civil / criminal / administrative 三类 prompt 快照，
并输出：
1. 本体快照与上次快照的差异
2. 当前 few-shot 候选是否覆盖本体变化内容
3. 每类 prompt 的生成元数据
4. 本体驱动的评估 prompt 快照
"""

from __future__ import annotations

import json
import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from ontology.generators.ontology_reader import load_ontology
from ontology.generators.evaluation_prompt_renderer import render_evaluation_prompt
from ontology.generators.prompt_renderer import render_extraction_prompt
from scripts.generate_prompt import inject_few_shots, load_best_few_shots, CASE_CATEGORIES


PROMPT_TARGETS = {
    "civil": {
        "case_type": "民事-通用",
        "output": REPO_ROOT / "ontology" / "prompts" / "auto_v5_civil.txt",
    },
    "criminal": {
        "case_type": "刑事-通用",
        "output": REPO_ROOT / "ontology" / "prompts" / "auto_v5_criminal.txt",
    },
    "administrative": {
        "case_type": "行政-通用",
        "output": REPO_ROOT / "ontology" / "prompts" / "auto_v5_admin.txt",
    },
}

PROMPT_META_DIR = REPO_ROOT / "ontology" / "prompts" / "_meta"
STATE_PATH = PROMPT_META_DIR / "refresh_state.json"
REPORT_PATH = PROMPT_META_DIR / "refresh_report.md"
EVALUATION_PROMPT_PATH = REPO_ROOT / "ontology" / "prompts" / "auto_ontology_evaluation.txt"

ENTITY_OUTPUT_KEYS = {
    "GuidingCase": "guiding_case",
    "CaseType": "case_type",
    "CourtCase": "court_cases",
    "LegalSubject": "legal_subjects",
    "Attorney": "attorneys",
    "Judge": "judges",
    "Prosecutor": "prosecutors",
    "TrialOrganization": "trial_organizations",
    "LegalProvision": "legal_provisions",
    "Evidence": "evidence",
    "JudgmentResult": "judgment_results",
    "CaseSummary": "case_summary",
    "LegalProvisionElement": "legal_provision_elements",
    "Fact": "facts",
    "DisputeFocus": "dispute_focuses",
}


@dataclass
class DiffResult:
    added_entities: List[str]
    removed_entities: List[str]
    added_relations: List[str]
    removed_relations: List[str]
    field_changes: Dict[str, Dict[str, List[str]]]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_sha1(data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def summarize_ontology(ontology: Dict[str, Any]) -> Dict[str, Any]:
    entities = {}
    for name, edef in sorted((ontology.get("entities") or {}).items()):
        entities[name] = {
            "parent": edef.get("parent"),
            "required": sorted(edef.get("required") or []),
            "optional": sorted(edef.get("optional") or []),
            "fields": sorted(
                {
                    field.get("field_name"): {
                        "required": bool(field.get("required")),
                        "enum_values": field.get("enum_values") or [],
                    }
                    for field in (edef.get("fields") or [])
                }.items()
            ),
        }
    relations = {}
    for name, rdef in sorted((ontology.get("relations") or {}).items()):
        relations[name] = {
            "from_type": rdef.get("from_type"),
            "to_type": rdef.get("to_type"),
            "cardinality": rdef.get("cardinality"),
            "attributes": sorted(rdef.get("attributes") or []),
        }
    summary = {
        "entities": entities,
        "relations": relations,
        "entity_count": len(entities),
        "relation_count": len(relations),
    }
    summary["sha1"] = stable_sha1(summary)
    return summary


def diff_ontology(prev: Dict[str, Any], curr: Dict[str, Any]) -> DiffResult:
    prev_entities = set((prev.get("entities") or {}).keys())
    curr_entities = set((curr.get("entities") or {}).keys())
    prev_relations = set((prev.get("relations") or {}).keys())
    curr_relations = set((curr.get("relations") or {}).keys())

    field_changes: Dict[str, Dict[str, List[str]]] = {}
    for entity_name in sorted(prev_entities & curr_entities):
        prev_def = prev["entities"][entity_name]
        curr_def = curr["entities"][entity_name]
        prev_fields = {name: meta for name, meta in prev_def.get("fields") or []}
        curr_fields = {name: meta for name, meta in curr_def.get("fields") or []}
        added = sorted(set(curr_fields) - set(prev_fields))
        removed = sorted(set(prev_fields) - set(curr_fields))
        changed = []
        for field_name in sorted(set(prev_fields) & set(curr_fields)):
            if prev_fields[field_name] != curr_fields[field_name]:
                changed.append(field_name)
        if added or removed or changed:
            field_changes[entity_name] = {
                "added": added,
                "removed": removed,
                "changed": changed,
            }

    return DiffResult(
        added_entities=sorted(curr_entities - prev_entities),
        removed_entities=sorted(prev_entities - curr_entities),
        added_relations=sorted(curr_relations - prev_relations),
        removed_relations=sorted(prev_relations - curr_relations),
        field_changes=field_changes,
    )


def load_prev_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def is_nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value) > 0
    return True


def entity_present(output: Dict[str, Any], entity_name: str) -> bool:
    key = ENTITY_OUTPUT_KEYS.get(entity_name)
    if not key:
        return False
    value = output.get(key)
    return is_nonempty(value)


def field_covered(output: Dict[str, Any], entity_name: str, field_name: str) -> bool:
    key = ENTITY_OUTPUT_KEYS.get(entity_name)
    if not key:
        return False
    value = output.get(key)
    if isinstance(value, dict):
        return is_nonempty(value.get(field_name))
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and is_nonempty(item.get(field_name)):
                return True
    return False


def relation_covered(output: Dict[str, Any], relation_name: str) -> bool:
    for rel in (output.get("relations") or []):
        if (rel.get("relation_type") or "").strip() == relation_name:
            return True
    return False


def assess_fewshot_against_changes(output: Dict[str, Any], diff: DiffResult) -> Dict[str, Any]:
    covered_entities = [name for name in diff.added_entities if entity_present(output, name)]
    missing_entities = [name for name in diff.added_entities if name not in covered_entities]

    covered_relations = [name for name in diff.added_relations if relation_covered(output, name)]
    missing_relations = [name for name in diff.added_relations if name not in covered_relations]

    field_status = {}
    for entity_name, delta in diff.field_changes.items():
        per_entity = {"added": [], "missing_added": [], "changed": [], "missing_changed": []}
        for field_name in delta.get("added") or []:
            if field_covered(output, entity_name, field_name):
                per_entity["added"].append(field_name)
            else:
                per_entity["missing_added"].append(field_name)
        for field_name in delta.get("changed") or []:
            if field_covered(output, entity_name, field_name):
                per_entity["changed"].append(field_name)
            else:
                per_entity["missing_changed"].append(field_name)
        if any(per_entity.values()):
            field_status[entity_name] = per_entity

    return {
        "covered_entities": covered_entities,
        "missing_entities": missing_entities,
        "covered_relations": covered_relations,
        "missing_relations": missing_relations,
        "field_status": field_status,
    }


def assess_overall_fewshot(output: Dict[str, Any]) -> Dict[str, Any]:
    present_entities = sorted(
        entity_name for entity_name in ENTITY_OUTPUT_KEYS
        if entity_present(output, entity_name)
    )
    relation_types = sorted(
        {
            (rel.get("relation_type") or "").strip()
            for rel in (output.get("relations") or [])
            if (rel.get("relation_type") or "").strip()
        }
    )
    return {
        "present_entities": present_entities,
        "relation_types": relation_types,
    }


def render_report(
    ontology_summary: Dict[str, Any],
    prev_summary: Dict[str, Any],
    diff: DiffResult,
    per_category_meta: Dict[str, Any],
) -> str:
    lines = [
        "# Prompt Refresh Report",
        "",
        f"- generated_at: `{utc_now_iso()}`",
        f"- ontology_sha1: `{ontology_summary.get('sha1', '')}`",
    ]
    prev_sha = prev_summary.get("sha1")
    if prev_sha:
        lines.append(f"- previous_ontology_sha1: `{prev_sha}`")
    else:
        lines.append("- previous_ontology_sha1: `(none)`")
    lines.extend([
        "",
        "## Ontology Changes",
        "",
    ])
    if not prev_summary:
        lines.append("- 首次生成基线快照，当前没有历史快照可供对比。")
    else:
        if diff.added_entities:
            lines.append("- Added entities: " + ", ".join(f"`{x}`" for x in diff.added_entities))
        if diff.removed_entities:
            lines.append("- Removed entities: " + ", ".join(f"`{x}`" for x in diff.removed_entities))
        if diff.added_relations:
            lines.append("- Added relations: " + ", ".join(f"`{x}`" for x in diff.added_relations))
        if diff.removed_relations:
            lines.append("- Removed relations: " + ", ".join(f"`{x}`" for x in diff.removed_relations))
        if diff.field_changes:
            for entity_name, delta in diff.field_changes.items():
                parts = []
                if delta.get("added"):
                    parts.append("added=" + ",".join(delta["added"]))
                if delta.get("removed"):
                    parts.append("removed=" + ",".join(delta["removed"]))
                if delta.get("changed"):
                    parts.append("changed=" + ",".join(delta["changed"]))
                lines.append(f"- {entity_name}: " + " | ".join(parts))
        if not any([
            diff.added_entities, diff.removed_entities,
            diff.added_relations, diff.removed_relations,
            diff.field_changes,
        ]):
            lines.append("- No ontology structure changes detected.")

    lines.extend(["", "## Few-shot Coverage", ""])
    for cat in CASE_CATEGORIES:
        meta = per_category_meta.get(cat) or {}
        lines.append(f"### {cat}")
        if not meta:
            lines.append("- no prompt generated")
            lines.append("")
            continue
        shot = meta.get("few_shot") or {}
        if not shot:
            lines.append("- no few-shot selected")
            lines.append("")
            continue
        lines.append(
            f"- selected_shot: `{shot.get('row_id', '?')}` | "
            f"score=`{shot.get('score', '?')}` | case_type=`{shot.get('case_type', '')}`"
        )
        overall = shot.get("overall_coverage") or {}
        lines.append(
            "- present_entities: "
            + (", ".join(f"`{x}`" for x in (overall.get("present_entities") or [])) or "(none)")
        )
        lines.append(
            "- relation_types: "
            + (", ".join(f"`{x}`" for x in (overall.get("relation_types") or [])) or "(none)")
        )
        change_cov = shot.get("change_coverage") or {}
        missing_entities = change_cov.get("missing_entities") or []
        missing_relations = change_cov.get("missing_relations") or []
        if missing_entities:
            lines.append("- missing_changed_entities: " + ", ".join(f"`{x}`" for x in missing_entities))
        if missing_relations:
            lines.append("- missing_changed_relations: " + ", ".join(f"`{x}`" for x in missing_relations))
        field_status = change_cov.get("field_status") or {}
        for entity_name, status in field_status.items():
            parts = []
            if status.get("missing_added"):
                parts.append("missing_added=" + ",".join(status["missing_added"]))
            if status.get("missing_changed"):
                parts.append("missing_changed=" + ",".join(status["missing_changed"]))
            if parts:
                lines.append(f"- {entity_name}: " + " | ".join(parts))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def refresh_prompts() -> Tuple[Dict[str, Any], Dict[str, Any], DiffResult, Dict[str, Any]]:
    ontology_path = REPO_ROOT / "ontology" / "schemas" / "legal_ontology_v2.yaml"
    ontology = load_ontology(str(ontology_path))
    current_summary = summarize_ontology(ontology)
    prev_state = load_prev_state()
    prev_summary = prev_state.get("ontology_summary") or {}
    diff = diff_ontology(prev_summary, current_summary) if prev_summary else DiffResult([], [], [], [], {})

    best_shots = load_best_few_shots()
    per_category_meta: Dict[str, Any] = {}

    evaluation_prompt = render_evaluation_prompt(ontology)
    EVALUATION_PROMPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVALUATION_PROMPT_PATH.write_text(evaluation_prompt, encoding="utf-8")
    evaluation_meta = {
        "prompt_file": str(EVALUATION_PROMPT_PATH.relative_to(REPO_ROOT)),
        "prompt_sha1": stable_sha1(evaluation_prompt),
        "ontology_sha1": current_summary.get("sha1"),
        "generated_at": utc_now_iso(),
    }
    (PROMPT_META_DIR / f"{EVALUATION_PROMPT_PATH.name}.meta.json").write_text(
        json.dumps(evaluation_meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    for cat, cfg in PROMPT_TARGETS.items():
        prompt = render_extraction_prompt(ontology)
        prompt = inject_few_shots(prompt, target_case_type=cfg["case_type"])
        output_path = cfg["output"]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(prompt, encoding="utf-8")

        shot_meta = None
        shot = best_shots.get(cat)
        if shot:
            output = shot.get("output") or {}
            shot_meta = {
                "row_id": shot.get("row_id"),
                "score": shot.get("score"),
                "quality": shot.get("quality"),
                "case_type": shot.get("case_type"),
                "file": shot.get("file"),
                "details": shot.get("details"),
                "overall_coverage": assess_overall_fewshot(output),
                "change_coverage": assess_fewshot_against_changes(output, diff),
            }
        per_category_meta[cat] = {
            "prompt_file": str(output_path.relative_to(REPO_ROOT)),
            "prompt_sha1": stable_sha1(prompt),
            "few_shot": shot_meta,
        }

        meta_path = PROMPT_META_DIR / f"{output_path.name}.meta.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(per_category_meta[cat], ensure_ascii=False, indent=2), encoding="utf-8")

    report = render_report(current_summary, prev_summary, diff, per_category_meta)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    state = {
        "generated_at": utc_now_iso(),
        "ontology_path": str(ontology_path.relative_to(REPO_ROOT)),
        "ontology_summary": current_summary,
        "categories": per_category_meta,
        "evaluation_prompt": evaluation_meta,
    }
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return current_summary, prev_summary, diff, per_category_meta


def main() -> None:
    current_summary, prev_summary, diff, per_category_meta = refresh_prompts()
    print("✅ prompt 刷新完成")
    print(f"ontology_sha1={current_summary['sha1']}")
    if prev_summary:
        print(f"previous_ontology_sha1={prev_summary.get('sha1', '')}")
    else:
        print("previous_ontology_sha1=(none)")
    print(f"report={REPORT_PATH}")
    for cat in CASE_CATEGORIES:
        shot = ((per_category_meta.get(cat) or {}).get("few_shot") or {})
        if shot:
            print(
                f"{cat}: row_id={shot.get('row_id')} score={shot.get('score')} "
                f"relations={(((shot.get('details') or {}).get('relations')))}"
            )


if __name__ == "__main__":
    main()
