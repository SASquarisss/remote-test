"""
Ontology-based evaluation of LLM extraction results.
Multi-dimensional scoring system that goes beyond simple empty-field checks.

Usage:
    from evaluator import ontology_evaluate

    result = ontology_evaluate(raw_text, extracted_json, ontology_schema)
    print(result["total_score"])  # 0-100
"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from ontology.generators.evaluation_prompt_renderer import (
    render_evaluation_prompt,
    render_evaluation_schema_summary,
)
from ontology.generators.ontology_reader import load_ontology

AUTO_EVALUATION_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ontology", "prompts", "auto_ontology_evaluation.txt",
)

LEGACY_EVALUATION_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "prompts", "ontology_evaluation_prompt_v1.txt",
)

ONTOLOGY_SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ontology", "schemas", "legal_ontology_v2.yaml",
)


# ── Prompt Loading ──────────────────────────────────────────────────────────

def load_evaluation_prompt() -> str:
    """Load the ontology evaluation system prompt."""
    if os.path.exists(AUTO_EVALUATION_PROMPT_PATH):
        with open(AUTO_EVALUATION_PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read()

    ontology = load_ontology(ONTOLOGY_SCHEMA_PATH)
    prompt = render_evaluation_prompt(ontology)
    try:
        os.makedirs(os.path.dirname(AUTO_EVALUATION_PROMPT_PATH), exist_ok=True)
        with open(AUTO_EVALUATION_PROMPT_PATH, "w", encoding="utf-8") as f:
            f.write(prompt)
    except OSError:
        pass
    return prompt


def load_ontology_schema_summary() -> str:
    """Load and summarize the ontology schema for use in the evaluation prompt."""
    try:
        ontology = load_ontology(ONTOLOGY_SCHEMA_PATH)
        return render_evaluation_schema_summary(ontology)
    except (FileNotFoundError, IOError):
        return "本体论 Schema 加载失败，使用默认约束。"


# ── Safe JSON parsing ──────────────────────────────────────────────────────

def _safe_json_parse(content: str) -> dict:
    """Tolerant JSON parser — tries to extract last complete JSON object if truncated."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        if start == -1:
            raise
        depth, end = 0, start
        for i in range(start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
            if depth == 0 and i > start:
                end = i + 1
                break
        if end > start:
            return json.loads(content[start:end])
        raise


# ── LLM Call ────────────────────────────────────────────────────────────────

def call_llm(prompt: str, user_input: str) -> Dict[str, Any]:
    """Single LLM call with retry. Uses deepseek-chat with JSON response format."""
    from openai import OpenAI

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")

    last_error = None
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_input},
                ],
                max_tokens=4096,
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=180,
            )
            content = resp.choices[0].message.content or "{}"
            return _safe_json_parse(content)
        except Exception as e:
            last_error = e
            print(f"  [evaluator retry {attempt+1}] {e}", flush=True)
            time.sleep(2 ** attempt)

    raise RuntimeError(f"All 3 LLM evaluation attempts failed: {last_error}")


# ── Quick Local Evaluation (fallback / lightweight) ────────────────────────

GRAPH_REQUIRED_RELATIONS = {
    "facts": ["has_fact"],
    "dispute_focuses": ["has_dispute_focus"],
    "evidence": ["submitted_for"],
    "evidence_to_claims": ["proves_fact"],
    "judgment_results": ["judgment_cites"],
}


def _make_issue(field: str, msg: str, severity: str = "major") -> Dict[str, str]:
    return {"field": field, "msg": msg, "severity": severity}


def _generated_item_id(prefix: str, idx: int, item: Dict[str, Any]) -> str:
    if isinstance(item, dict) and item.get("id"):
        return str(item["id"])
    return f"{prefix}_{idx}"


def _normalize_graph_ref(ref: str) -> str:
    if not isinstance(ref, str):
        return str(ref)
    mapping = {
        "evidence_": "evid_",
        "judgment_result_": "jr_",
        "judgment_results_": "jr_",
        "legal_provision_": "prov_",
        "legal_provisions_": "prov_",
        "dispute_focus_": "focus_",
        "dispute_focuses_": "focus_",
    }
    for old, new in mapping.items():
        if ref.startswith(old):
            return new + ref[len(old):]
    return ref


def _collect_valid_graph_refs(output: Dict[str, Any]) -> Dict[str, set]:
    refs = {
        "all": set(),
        "court_cases": set(),
        "facts": set(),
        "dispute_focuses": set(),
        "evidence": set(),
        "judgment_results": set(),
        "legal_provisions": set(),
    }

    for cc in (output.get("court_cases") or []):
        case_number = (cc.get("case_number") or "").strip()
        if case_number:
            refs["court_cases"].add(case_number)
            refs["all"].add(case_number)

    for idx, fact in enumerate(output.get("facts") or []):
        fact_id = _normalize_graph_ref(_generated_item_id("fact", idx, fact))
        refs["facts"].add(fact_id)
        refs["all"].add(fact_id)

    for idx, focus in enumerate(output.get("dispute_focuses") or []):
        focus_id = _normalize_graph_ref(_generated_item_id("focus", idx, focus))
        refs["dispute_focuses"].add(focus_id)
        refs["all"].add(focus_id)

    for idx, evid in enumerate(output.get("evidence") or []):
        evid_id = _normalize_graph_ref(_generated_item_id("evid", idx, evid))
        refs["evidence"].add(evid_id)
        refs["all"].add(evid_id)

    for idx, jr in enumerate(output.get("judgment_results") or []):
        jr_id = _normalize_graph_ref(_generated_item_id("jr", idx, jr))
        refs["judgment_results"].add(jr_id)
        refs["all"].add(jr_id)

    for idx, prov in enumerate(output.get("legal_provisions") or []):
        prov_id = _normalize_graph_ref(_generated_item_id("prov", idx, prov))
        refs["legal_provisions"].add(prov_id)
        refs["all"].add(prov_id)

    return refs


def _assess_relation_graph(output: Dict[str, Any]) -> Dict[str, Any]:
    issues: List[Dict[str, str]] = []
    relation_types = {}
    valid_refs = _collect_valid_graph_refs(output)
    relations = output.get("relations") or []

    dangling_edges = 0
    missing_endpoints = 0
    duplicate_edges = 0
    seen_edges = set()

    for idx, rel in enumerate(relations):
        if not isinstance(rel, dict):
            issues.append(_make_issue(f"relations[{idx}]", "关系项不是对象", "major"))
            continue

        src = _normalize_graph_ref((rel.get("source_id") or "").strip())
        tgt = _normalize_graph_ref((rel.get("target_id") or "").strip())
        rtype = (rel.get("relation_type") or "").strip()
        edge_key = (src, tgt, rtype)

        if edge_key in seen_edges:
            duplicate_edges += 1
            issues.append(_make_issue(f"relations[{idx}]", f"重复关系边 {src}->{tgt}:{rtype}", "minor"))
        seen_edges.add(edge_key)

        if not src or not tgt or not rtype:
            missing_endpoints += 1
            issues.append(_make_issue(f"relations[{idx}]", "source_id / target_id / relation_type 存在空值", "critical"))
            continue

        relation_types[rtype] = relation_types.get(rtype, 0) + 1
        if src not in valid_refs["all"] or tgt not in valid_refs["all"]:
            dangling_edges += 1
            issues.append(_make_issue(
                f"relations[{idx}]",
                f"关系引用悬空: {src}->{tgt} ({rtype}) 未能在输出节点中找到",
                "major",
            ))

    facts = output.get("facts") or []
    focuses = output.get("dispute_focuses") or []
    evidence = output.get("evidence") or []
    judgment_results = output.get("judgment_results") or []
    provisions = output.get("legal_provisions") or []

    def require_relation(group_key: str, field: str, reason: str, severity: str = "major"):
        expected = GRAPH_REQUIRED_RELATIONS[group_key]
        if not any(relation_types.get(name) for name in expected):
            issues.append(_make_issue(field, reason + "，缺少 " + "/".join(expected), severity))

    if facts:
        require_relation("facts", "relations", "存在 facts 但没有把案件挂到事实")
    if focuses:
        require_relation("dispute_focuses", "relations", "存在 dispute_focuses 但没有把案件挂到争议焦点")
    if evidence:
        require_relation("evidence", "relations", "存在 evidence 但没有 submitted_for 关系")
    if evidence and (facts or focuses):
        require_relation("evidence_to_claims", "relations", "存在 evidence 且存在 facts/dispute_focuses，但没有证明链")
    if judgment_results and provisions:
        require_relation("judgment_results", "relations", "存在 judgment_results 与 legal_provisions，但没有裁判依据链")

    return {
        "issues": issues,
        "relation_types": relation_types,
        "relation_count": len(relations),
        "dangling_edges": dangling_edges,
        "missing_endpoints": missing_endpoints,
        "duplicate_edges": duplicate_edges,
    }

def quick_evaluate(output: Dict[str, Any], row_id: str = "") -> Dict[str, Any]:
    """
    Lightweight local evaluation — does NOT call LLM.
    Checks field presence and basic ontology compliance.
    Returns a simplified version of the full evaluation schema.

    This is used as a synchronous fallback or quick-check before the
    full LLM-based ontology evaluation.
    """
    issues = []
    score = 100.0

    # --- D1: Structure Integrity ---
    required_top_keys = [
        "guiding_case", "case_type", "court_cases",
        "legal_subjects", "legal_provisions", "case_summary",
        "facts", "dispute_focuses", "relations",
    ]
    for key in required_top_keys:
        if key not in output:
            severity = "critical" if key in {"court_cases", "facts", "dispute_focuses", "relations"} else "major"
            issues.append(_make_issue(key, f"顶层键 '{key}' 缺失", severity))
            score -= 10 if severity == "critical" else 6

    # --- D4: Ontology Consistency - Required fields check ---
    gc = output.get("guiding_case") or {}
    for field in ["guiding_case_number", "guiding_case_name", "binding_force"]:
        if not gc.get(field):
            issues.append(_make_issue(f"guiding_case.{field}", f"{field} 为空", "major"))
            score -= 4

    ct = output.get("case_type") or {}
    if not ct.get("category"):
        issues.append(_make_issue("case_type.category", "案例类型为空", "major"))
        score -= 4

    # --- D2: Entity Completeness ---
    court_cases = output.get("court_cases") or []
    if not court_cases:
        issues.append(_make_issue("court_cases", "法院案件列表为空", "critical"))
        score -= 20
    else:
        has_case_number = any(cc.get("case_number") for cc in court_cases)
        if not has_case_number:
            issues.append(_make_issue("court_cases[].case_number", "所有 court_cases 均无案号", "major"))
            score -= 8

    provisions = output.get("legal_provisions") or []
    if not provisions:
        issues.append(_make_issue("legal_provisions", "法条引用为空", "major"))
        score -= 10
    else:
        for i, p in enumerate(provisions):
            if not p.get("article"):
                issues.append(_make_issue(f"legal_provisions[{i}].article", f"第{i+1}条法条缺少条号", "major"))
                score -= 4
            if not p.get("content"):
                issues.append(_make_issue(f"legal_provisions[{i}].content", f"第{i+1}条法条缺少原文上下文", "minor"))
                score -= 2

    cs = output.get("case_summary") or {}
    for field in ["key_facts", "disputed_issues", "conclusion"]:
        if not cs.get(field):
            issues.append(_make_issue(f"case_summary.{field}", f"案件摘要.{field} 为空", "major"))
            score -= 5

    facts = output.get("facts") or []
    if not facts:
        issues.append(_make_issue("facts", "事实节点为空", "critical"))
        score -= 12
    else:
        if not any((fact.get("content") or "").strip() for fact in facts if isinstance(fact, dict)):
            issues.append(_make_issue("facts[].content", "facts 存在但内容均为空", "major"))
            score -= 8

    dispute_focuses = output.get("dispute_focuses") or []
    if not dispute_focuses:
        issues.append(_make_issue("dispute_focuses", "争议焦点节点为空", "critical"))
        score -= 12
    else:
        if not any((focus.get("content") or "").strip() for focus in dispute_focuses if isinstance(focus, dict)):
            issues.append(_make_issue("dispute_focuses[].content", "dispute_focuses 存在但内容均为空", "major"))
            score -= 8

    relation_eval = _assess_relation_graph(output)
    issues.extend(relation_eval["issues"])
    score -= relation_eval["dangling_edges"] * 4
    score -= relation_eval["missing_endpoints"] * 6
    score -= relation_eval["duplicate_edges"] * 2

    if not relation_eval["relation_count"]:
        issues.append(_make_issue("relations", "关系边为空", "critical"))
        score -= 14

    # --- D4.6: Temporal constraints ---
    for i, cc in enumerate(court_cases):
        filing = cc.get("filing_date", "")
        judgment = cc.get("judgment_date", "")
        if filing and judgment:
            if filing > judgment:
                issues.append({
                    "field": f"court_cases[{i}]",
                    "msg": f"时序异常: 立案日期({filing}) 晚于判决日期({judgment})",
                    "severity": "critical"
                })
                score -= 10

    # --- D3.1: Case number format check ---
    for i, cc in enumerate(court_cases):
        cn = cc.get("case_number", "")
        if cn and not re.match(r"^\(\d{4}\)", cn):
            issues.append({
                "field": f"court_cases[{i}].case_number",
                "msg": f"案号格式异常: '{cn}' (应有年份括号前缀)",
                "severity": "minor"
            })
            score -= 2

    # --- Entity duplication check ---
    seen_case_numbers = set()
    for i, cc in enumerate(court_cases):
        cn = cc.get("case_number", "")
        if cn and cn in seen_case_numbers:
            issues.append({
                "field": f"court_cases[{i}].case_number",
                "msg": f"重复案号: '{cn}'",
                "severity": "minor"
            })
            score -= 3
        seen_case_numbers.add(cn)

    dim_scores = {
        "D1": 100,
        "D2": max(0, 100 - 6 * len([x for x in issues if x["field"] in {"court_cases", "facts", "dispute_focuses", "legal_provisions"}])),
        "D3": max(0, 100 - 4 * len([x for x in issues if "case_number" in x["field"] or "date" in x["field"] or "category" in x["field"]])),
        "D4": max(0, 100 - 6 * (relation_eval["dangling_edges"] + relation_eval["missing_endpoints"]) - 4 * len([x for x in issues if x["field"] == "relations"])),
        "D5": max(0, 100 - 8 * len([x for x in issues if x["field"] in {"relations", "legal_provisions", "evidence"}])),
        "D6": max(0, 100 - 6 * len([x for x in issues if x["field"].startswith("case_summary.")])),
    }

    return {
        "row_id": row_id,
        "score": round(max(0, score), 1),
        "issues": issues,
        "total_score": round(max(0, score), 1),
        "confidence": "优" if score >= 90 else ("良" if score >= 70 else ("中" if score >= 50 else "差")),
        "dimension_scores": {
            "D1": {"name": "structure_integrity", "score": dim_scores["D1"]},
            "D2": {"name": "entity_and_graph_completeness", "score": dim_scores["D2"]},
            "D3": {"name": "attribute_accuracy", "score": dim_scores["D3"]},
            "D4": {"name": "ontology_consistency_and_relation_validity", "score": dim_scores["D4"]},
            "D5": {"name": "citation_and_reasoning_chain", "score": dim_scores["D5"]},
            "D6": {"name": "semantic_coherence", "score": dim_scores["D6"]},
        },
        "graph_summary": {
            "facts_count": len(facts),
            "dispute_focuses_count": len(dispute_focuses),
            "relations_count": relation_eval["relation_count"],
            "relation_types": relation_eval["relation_types"],
            "dangling_edges": relation_eval["dangling_edges"],
        },
    }


# ── Full Ontology Evaluation (LLM-based) ───────────────────────────────────

def ontology_evaluate(
    raw_text: str,
    extracted_json: Dict[str, Any],
    row_id: str = "",
    use_llm: bool = True,
) -> Dict[str, Any]:
    """
    Two-part ontology evaluation pipeline via LLM.

    Returns a dict with two top-level keys:
      - parsing_evaluation: 评估 LLM 解析结果的质量 (完整性/一致性/准确性)
      - ontology_coverage:   评估原始文本中有无未被本体论覆盖的实体/关系

    Args:
        raw_text: Original legal text input by user.
        extracted_json: Structured JSON output from LLM extraction.
        row_id: Optional identifier for the row being evaluated.
        use_llm: If True, use LLM for full evaluation; if False, raise error.

    Returns:
        Dict with "parsing_evaluation" and "ontology_coverage" sub-results.
    """
    if not use_llm:
        raise ValueError("ontology_evaluate requires use_llm=True for proper evaluation")

    # Load prompt and build user input
    try:
        system_prompt = load_evaluation_prompt()
    except FileNotFoundError:
        system_prompt = _default_evaluation_prompt()

    ontology_summary = load_ontology_schema_summary()

    # Truncate raw text if too long (evaluation only needs key sections)
    truncated_text = raw_text[:8000] if len(raw_text) > 8000 else raw_text

    user_input = f"""
===== 原始法律文本 =====
{truncated_text}

===== LLM 提取结果 =====
{json.dumps(extracted_json, ensure_ascii=False, indent=2)}

===== 本体论 Schema =====
{ontology_summary}
"""

    # Call LLM evaluator
    llm_result = call_llm(system_prompt, user_input)

    # The LLM should return a JSON with "parsing_evaluation" and "ontology_coverage"
    # Some LLMs follow the old 1.x prompt format — remap those to the new structure
    result = {
        "row_id": row_id,
        "evaluation_type": "llm",
    }

    # Try to parse parsing_evaluation from multiple possible locations
    pe = llm_result.get("parsing_evaluation", llm_result.get("parsing", {}))
    if pe and isinstance(pe, dict) and pe.get("dimensions"):
        result["parsing_evaluation"] = _ensure_parsing_evaluation(pe)
    else:
        # Legacy format: flatten dimension_scores + issues + suggestions from top level
        result["parsing_evaluation"] = _legacy_to_parsing_evaluation(llm_result)

    # Try ontology_coverage
    oc = llm_result.get("ontology_coverage", llm_result.get("coverage", {}))
    if oc and isinstance(oc, dict) and oc.get("coverage_items"):
        result["ontology_coverage"] = _ensure_ontology_coverage(oc)
    else:
        # Legacy fallback: look for ontology_violations in detailed_report
        oc_fallback = _legacy_to_ontology_coverage(llm_result)
        result["ontology_coverage"] = oc_fallback

    return result


def _legacy_to_parsing_evaluation(llm_result: Dict[str, Any]) -> Dict[str, Any]:
    """Convert legacy flat LLM result to parsing_evaluation structure."""
    dims = llm_result.get("dimension_scores", llm_result.get("dimensions", []))
    issues = llm_result.get("issues", [])
    suggestions = llm_result.get("suggestions", [])
    total_score = llm_result.get("total_score", 0)
    confidence = llm_result.get("confidence", "中")

    # Normalize dimension_scores to our 'dimensions' format
    normalized = []
    if isinstance(dims, list):
        for d in dims:
            normalized.append({
                "code": d.get("dimension_id", d.get("code", "")),
                "name": d.get("dimension_name", d.get("name", "")),
                "score": d.get("score", 0),
                "detail": _format_dimension_detail(d),
            })
    elif isinstance(dims, dict):
        for k, v in dims.items():
            normalized.append({
                "code": k,
                "name": v.get("name", k),
                "score": v.get("score", 0),
                "detail": v.get("detail", ""),
            })

    return {
        "total_score": total_score,
        "confidence": confidence,
        "dimensions": normalized,
        "issues": issues,
        "suggestions": suggestions,
    }


def _format_dimension_detail(d: Dict[str, Any]) -> str:
    """Format sub_scores into a detail string."""
    subs = d.get("sub_scores", [])
    if not subs:
        return d.get("reason", d.get("detail", ""))
    parts = []
    for s in subs:
        parts.append(f"{s.get('indicator_name', s.get('name',''))}: {s.get('score',0)}分 — {s.get('reason', s.get('detail',''))}")
    return "\n".join(parts)


def _legacy_to_ontology_coverage(llm_result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ontology coverage info from legacy format's detailed_report."""
    dr = llm_result.get("detailed_report", {})
    violations = dr.get("ontology_violations", []) if isinstance(dr, dict) else []
    coverage_items = []
    uncovered = []
    suggestions = []

    # Violations become uncovered items
    for v in violations:
        if isinstance(v, dict):
            uncovered.append({
                "entity": v.get("violation_path", v.get("entity", "")),
                "relation": v.get("constraint", v.get("relation", "")),
                "detail": v.get("description", v.get("detail", "")),
            })

    if isinstance(dr, dict):
        suggestions = dr.get("suggestions", llm_result.get("suggestions", []))

    # Try to deduce ontology_coverage total_score from parsing evaluation
    # Higher violations = lower ontology score
    pe = llm_result.get("parsing_evaluation", {})
    pe_score = pe.get("total_score", llm_result.get("total_score", 100)) if isinstance(pe, dict) else 100
    violation_penalty = min(40, len(uncovered) * 10)
    total_score = max(0, pe_score - violation_penalty)

    return {
        "total_score": total_score,
        "coverage_items": coverage_items,
        "uncovered": uncovered,
        "suggestions": suggestions,
    }


def _ensure_parsing_evaluation(pe: Any) -> Dict[str, Any]:
    """Ensure parsing_evaluation has the expected structure."""
    if not isinstance(pe, dict):
        return {"total_score": 0, "confidence": "中", "dimensions": [], "issues": [], "suggestions": []}
    dims = pe.get("dimensions", [])
    if isinstance(dims, dict):
        dims = [{"code": k, "name": v.get("name", ""), "score": v.get("score", 0), "detail": v.get("detail", "")}
                for k, v in dims.items()]
    pe.setdefault("dimensions", dims)
    pe.setdefault("issues", [])
    pe.setdefault("suggestions", [])
    pe.setdefault("total_score", pe.get("total_score", 0))
    pe.setdefault("confidence", pe.get("confidence", "中"))
    return pe


def _ensure_ontology_coverage(oc: Any) -> Dict[str, Any]:
    """Ensure ontology_coverage has the expected structure."""
    if not isinstance(oc, dict):
        return {"total_score": 100, "coverage_items": [], "uncovered": [], "suggestions": []}
    oc.setdefault("coverage_items", [])
    oc.setdefault("uncovered", [])
    oc.setdefault("suggestions", [])
    oc.setdefault("total_score", oc.get("total_score", 100))
    return oc


def _default_evaluation_prompt() -> str:
    """Fallback inline evaluation prompt if prompt file is missing."""
    return """你是一个法律文本解析质量评估专家。你需要对 LLM 从法律文本中提取的结构化结果进行两方面的评估，**严格按照以下 JSON Schema 输出**：

## 第一部分：解析结果评估 (parsing_evaluation)

评估 LLM 解析结果的质量，从以下维度打分：

### 评估维度
1. **结构完整性**（权重5%）：检查 JSON 顶层键是否存在，数组字段类型是否正确
2. **实体完整性**（权重25%）：检查关键实体（当事人、法官、律师、案号、法条）是否全部覆盖
3. **属性准确性**（权重25%）：检查字段值是否与原文一致，案号格式、日期、枚举值映射是否正确
4. **本体论一致性**（权重20%）：检查枚举值是否合规、必填字段是否非空
5. **引用完整性**（权重15%）：检查法条引用的上下文、位置标注、案号关联是否准确
6. **语义连贯性**（权重10%）：检查摘要文本是否结构清晰、语言规范

### 评分规则
- 每个维度满分100分
- 最终总分 = Σ(维度得分 × 维度权重)
- 置信度：≥90→"优", 70-89→"良", 50-69→"中", <50→"差"

### 维度 score 字段说明
- score ∈ [0, 100]，小数向下取整
- 为每个给出具体的扣分项和原因，放在 detail 字段中

## 第二部分：本体论覆盖评估 (ontology_coverage)

分析原始法律文本，与本体论 Schema 对比，评估本体论对文本中出现的实体和关系的覆盖程度。

### 评估内容
1. 文本中出现的实体类型是否被本体论模型涵盖
2. 实体间关系是否被本体论定义的关系类型覆盖
3. 是否存在文本中有但本体论未定义的实体或关系
4. 对未被覆盖的内容给出具体示例和建议

### 输出要求
- coverage_items: 已经覆盖的实体/关系列表
- uncovered: 未被覆盖的实体/关系列表（每个包含 entity 和 relation 字段）
- suggestions: 对本体论扩展的建议

## JSON Schema 输出格式（必须严格遵循，使用以下结构）

```json
{
  "parsing_evaluation": {
    "total_score": 85,
    "confidence": "良",
    "dimensions": [
      {"code": "D1", "name": "结构完整性", "score": 90, "detail": "所有顶层键存在，数组字段类型正确"},
      {"code": "D2", "name": "实体完整性", "score": 80, "detail": "未提取被告辩护律师信息"}
    ],
    "issues": [
      {"field": "case_type.category", "msg": "案例类型为空", "severity": "major"},
      {"field": "legal_provisions", "msg": "未引用具体法条", "severity": "critical"}
    ],
    "suggestions": [
      "建议补充被告辩护律师的提取逻辑",
      "法条引用应包含具体条款编号和原文上下文"
    ]
  },
  "ontology_coverage": {
    "total_score": 80,
    "coverage_items": [
      {"entity": "当事人", "relation": "参与案件", "status": "covered"},
      {"entity": "法官", "relation": "审理案件", "status": "covered"}
    ],
    "uncovered": [
      {"entity": "鉴定人", "relation": "参与鉴定", "detail": "文本中出现了'法医鉴定人'但本体论未定义鉴定人实体类型"},
      {"entity": "附带民事诉讼原告人", "relation": "参与案件", "detail": "刑事附带民事诉讼中出现的原告人类型未被单独定义"}
    ],
    "suggestions": [
      "建议在 LegalSubject 中添加 '鉴定人' 子类型",
      "建议增加 '附带民事诉讼原告人' 角色类型"
    ]
  }
}
```"""
