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

EVALUATION_PROMPT_PATH = os.path.join(
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
    with open(EVALUATION_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def load_ontology_schema_summary() -> str:
    """Load and summarize the ontology schema for use in the evaluation prompt."""
    try:
        with open(ONTOLOGY_SCHEMA_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        # Extract key enum definitions and constraints for a compact summary
        lines = content.split("\n")
        summary_parts = []
        enum_section = []
        constraint_section = []
        in_constraint = False
        for line in lines:
            if "enum:" in line and ("_enum" in line or "enum" in line):
                enum_section.append(line.strip())
            if "constraints:" in line:
                in_constraint = True
                continue
            if in_constraint:
                if line.strip().startswith("-") or line.strip().startswith("  -"):
                    constraint_section.append(line.strip())
                elif line.strip() == "":
                    in_constraint = False

        summary = "## 本体论枚举值\n"
        summary += "\n".join(enum_section[:50])
        summary += "\n\n## 本体论约束规则\n"
        summary += "\n".join(constraint_section[:20])
        return summary
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
    ]
    for key in required_top_keys:
        if key not in output:
            issues.append({"field": key, "msg": f"顶层键 '{key}' 缺失", "severity": "critical"})
            score -= 8

    # --- D4: Ontology Consistency - Required fields check ---
    gc = output.get("guiding_case") or {}
    for field in ["guiding_case_number", "guiding_case_name", "binding_force"]:
        if not gc.get(field):
            issues.append({"field": f"guiding_case.{field}", "msg": f"{field} 为空", "severity": "major"})
            score -= 4

    ct = output.get("case_type") or {}
    if not ct.get("category"):
        issues.append({"field": "case_type.category", "msg": "案例类型为空", "severity": "major"})
        score -= 4

    # --- D2: Entity Completeness ---
    court_cases = output.get("court_cases") or []
    if not court_cases:
        issues.append({"field": "court_cases", "msg": "法院案件列表为空", "severity": "critical"})
        score -= 20
    else:
        has_case_number = any(cc.get("case_number") for cc in court_cases)
        if not has_case_number:
            issues.append({"field": "court_cases[].case_number", "msg": "所有 court_cases 均无案号", "severity": "major"})
            score -= 8

    provisions = output.get("legal_provisions") or []
    if not provisions:
        issues.append({"field": "legal_provisions", "msg": "法条引用为空", "severity": "major"})
        score -= 10
    else:
        for i, p in enumerate(provisions):
            if not p.get("article"):
                issues.append({"field": f"legal_provisions[{i}].article", "msg": f"第{i+1}条法条缺少条号", "severity": "major"})
                score -= 4
            if not p.get("content"):
                issues.append({"field": f"legal_provisions[{i}].content", "msg": f"第{i+1}条法条缺少原文上下文", "severity": "minor"})
                score -= 2

    cs = output.get("case_summary") or {}
    for field in ["key_facts", "disputed_issues", "conclusion"]:
        if not cs.get(field):
            issues.append({"field": f"case_summary.{field}", "msg": f"案件摘要.{field} 为空", "severity": "major"})
            score -= 5

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

    return {
        "row_id": row_id,
        "score": round(max(0, score), 1),
        "issues": issues,
        "total_score": round(max(0, score), 1),
        "confidence": "优" if score >= 90 else ("良" if score >= 70 else ("中" if score >= 50 else "差")),
        "dimension_scores": {
            "D1": {"name": "structure_integrity", "score": 0},  # Not computable locally
            "D2": {"name": "entity_completeness", "score": 0},
            "D3": {"name": "attribute_accuracy", "score": 0},
            "D4": {"name": "ontology_consistency", "score": 0},
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
