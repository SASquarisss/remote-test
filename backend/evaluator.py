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
    Full ontology evaluation pipeline.

    Args:
        raw_text: Original legal text input by user.
        extracted_json: Structured JSON output from LLM extraction.
        row_id: Optional identifier for the row being evaluated.
        use_llm: If True, use LLM for full evaluation; if False, use local quick check.

    Returns:
        Dict with evaluation result conforming to the evaluation JSON schema.
    """
    # Always do quick local check first (fast, no API call)
    local_result = quick_evaluate(extracted_json, row_id)

    if not use_llm:
        return local_result

    # Load prompt and build user input
    try:
        system_prompt = load_evaluation_prompt()
    except FileNotFoundError:
        # Fallback to inline prompt if file not found
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
    try:
        llm_result = call_llm(system_prompt, user_input)
    except Exception as e:
        print(f"  [evaluator] LLM evaluation failed, falling back to local: {e}", flush=True)
        return local_result

    # Merge local quick checks with LLM evaluation
    # LLM result should already contain full schema, but we overlay local checks
    merged = {
        "row_id": row_id,
        "evaluation_type": "llm",
        "local_score": local_result["score"],
        "local_issues": local_result["issues"],
        **llm_result,
    }

    # Ensure required fields exist
    if "summary" not in merged:
        merged["summary"] = {
            "total_score": llm_result.get("total_score", local_result["score"]),
            "confidence": llm_result.get("confidence", local_result["confidence"]),
        }
    if "total_score" not in merged:
        merged["total_score"] = merged["summary"]["total_score"]
    if "confidence" not in merged:
        merged["confidence"] = merged["summary"].get("confidence", "中")

    return merged


def _default_evaluation_prompt() -> str:
    """Fallback inline evaluation prompt if prompt file is missing."""
    return """你是一个法律文本解析质量评估专家。你需要对 LLM 从法律文本中提取的结构化结果进行多维度的质量评分。

## 评估维度
1. **结构完整性**（权重5%）：检查 JSON 顶层键是否存在，数组字段类型是否正确
2. **实体完整性**（权重25%）：检查关键实体（当事人、法官、律师、案号、法条）是否全部覆盖
3. **属性准确性**（权重25%）：检查字段值是否与原文一致，案号格式、日期、枚举值映射是否正确
4. **本体论一致性**（权重20%）：检查枚举值是否合规、必填字段是否非空、时序约束是否成立
5. **引用完整性**（权重15%）：检查法条引用的上下文、位置标注、案号关联是否准确
6. **语义连贯性**（权重10%）：检查摘要文本是否结构清晰、语言规范

## 评分规则
- 每个维度满分100分，按子指标分值加权求和后除以总分值得出
- 最终总分 = Σ(维度得分 × 维度权重)
- 置信度：≥90→"优", 70-89→"良", 50-69→"中", <50→"差"

## 输出格式
严格按照以下 JSON Schema 输出评估结果。必须包含原文证据引用。"""
