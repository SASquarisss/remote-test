"""
Legal text parser — simplified standalone version.
Reuses logic patterns from guiding_case_extractor_v3.py without importing it.
"""
import ast
import copy
import hashlib
import json
import os
import re
import time
from collections import Counter
from typing import Any, Dict, List, Optional

import yaml

# ── Config ──────────────────────────────────────────────────────────────────

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT_DIR = os.path.join(REPO_ROOT, "ontology", "prompts")
DEFAULT_PROMPT_PATH = os.path.join(REPO_ROOT, "scripts/prompts", "guiding_case_ontology_aligned_v3.txt")
LLM_DEBUG_DIR = os.path.join(REPO_ROOT, "runtime_logs", "llm_parse_failures")
RELATION_POLICY_PATH = os.path.join(REPO_ROOT, "ontology", "relation_policies.yaml")

_RELATION_POLICY_CACHE: Optional[Dict[str, Any]] = None


def load_relation_policies() -> Dict[str, Any]:
    global _RELATION_POLICY_CACHE
    if _RELATION_POLICY_CACHE is not None:
        return _RELATION_POLICY_CACHE

    if not os.path.exists(RELATION_POLICY_PATH):
        _RELATION_POLICY_CACHE = {"derived_relations": []}
        return _RELATION_POLICY_CACHE

    with open(RELATION_POLICY_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    _RELATION_POLICY_CACHE = {
        "derived_relations": data.get("derived_relations") or []
    }
    return _RELATION_POLICY_CACHE

# ── Prompt Loading ──────────────────────────────────────────────────────────

def resolve_prompt_path(case_type: str = "") -> str:
    ct = (case_type or "").strip()
    if ct.startswith("刑事"):
        candidate = os.path.join(PROMPT_DIR, "auto_v5_criminal.txt")
        if os.path.exists(candidate):
            return candidate
    if ct.startswith("行政"):
        candidate = os.path.join(PROMPT_DIR, "auto_v5_admin.txt")
        if os.path.exists(candidate):
            return candidate
    candidate = os.path.join(PROMPT_DIR, "auto_v5_civil.txt")
    if os.path.exists(candidate):
        return candidate
    return DEFAULT_PROMPT_PATH


def load_prompt(case_type: str = "") -> str:
    with open(resolve_prompt_path(case_type), "r", encoding="utf-8") as f:
        return f.read()


def load_legacy_fallback_prompt() -> str:
    with open(DEFAULT_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()

# ── Input Builder ───────────────────────────────────────────────────────────

def build_row_from_text(raw_text: str) -> Dict[str, str]:
    """
    Convert arbitrary user text into a dict that mimics a CSV row.
    Tries to extract known fields via pattern matching; the rest goes to basic_facts.
    """
    row: Dict[str, str] = {
        "id": "",
        "web_name": "",
        "web_url": "",
        "case_type": "",
        "storage_no": "",
        "court_name": "",
        "key_words": "",
        "trial_procedure": "",
        "trial_year": "",
        "case_level": "",
        "basic_facts": "",
        "judgment_reason": "",
        "judgment_essence": "",
        "related_info": "",
        "related_law": "",
        "related_judgment_body": "",
        "create_time": "",
        "update_time": "",
        "md5_value": "",
        "judgment_mean": "",
        "dt": "",
    }

    patterns = {
        "storage_no": r"(?:入库编号|案例库编号)[：:]\s*(\S+)",
        "web_name": r"(?:案例名称|案件名称)[：:]\s*(.+?)(?:\n|$)",
        "court_name": r"(?:审理法院|法院)[：:]\s*(.+?)(?:\n|$)",
        "trial_procedure": r"(?:审判程序|程序)[：:]\s*(.+?)(?:\n|$)",
        "trial_year": r"(?:裁判年份|年份)[：:]\s*(\d{4})",
        "case_type": r"(?:案由分类|案由)[：:]\s*(.+?)(?:\n|$)",
        "key_words": r"(?:关键词)[：:]\s*(.+?)(?:\n|$)",
        "case_level": r"(?:案例层级|层级)[：:]\s*(.+?)(?:\n|$)",
        "judgment_mean": r"(?:裁判意义|意义)[：:]\s*(.+?)(?:\n|$)",
    }

    # Try to extract structured fields
    for field, pat in patterns.items():
        m = re.search(pat, raw_text)
        if m:
            row[field] = m.group(1).strip()

    # Extract multi-line content sections
    section_patterns = {
        "basic_facts": r"(?:基本案情|基本事实)[：:]\s*([\s\S]*?)(?=\n(?:裁判理由|相关法条|裁判要旨|关键词))",
        "judgment_reason": r"(?:裁判理由)[：:]\s*([\s\S]*?)(?=\n(?:裁判要旨|基本案情|相关法条|关键词))",
        "judgment_essence": r"(?:裁判要旨)[：:]\s*([\s\S]*?)(?=\n(?:基本案情|裁判理由|相关法条|关键词))",
        "related_law": r"(?:相关法条)[：:]\s*([\s\S]*?)(?=\n(?:基本案情|裁判理由|裁判要旨|关键词))",
    }
    for field, pat in section_patterns.items():
        m = re.search(pat, raw_text)
        if m:
            row[field] = m.group(1).strip()

    # If no basic_facts extracted, use whole text
    if not row["basic_facts"] and not row["judgment_reason"]:
        row["basic_facts"] = raw_text.strip()

    # If no case_name, use first meaningful line
    if not row["web_name"]:
        first_line = raw_text.strip().split("\n")[0][:100]
        row["web_name"] = first_line

    return row


def build_llm_input(row: Dict[str, str]) -> str:
    """Build LLM input from a row dict, same logic as extractor_v3."""
    fields = [
        ("web_name", "案例来源"),
        ("web_url", "来源URL"),
        ("case_type", "案由分类"),
        ("storage_no", "入库编号"),
        ("court_name", "审理法院"),
        ("trial_procedure", "审判程序"),
        ("trial_year", "裁判年份"),
        ("case_level", "案例层级"),
        ("basic_facts", "基本案情"),
        ("judgment_reason", "裁判理由"),
        ("judgment_essence", "裁判要旨"),
        ("related_info", "相关案情/关联案件"),
        ("related_law", "相关法条"),
        ("related_judgment_body", "关联裁判文书"),
        ("key_words", "关键词"),
        ("judgment_mean", "裁判意义"),
    ]
    lines = []
    for key, label in fields:
        val = row.get(key, "") or ""
        val = re.sub(r"<[^>]+>", "", val)
        val = val.replace("\\N", "").strip()
        if val:
            lines.append(f"【{label}】\n{val}\n")
    return "\n".join(lines)


# ── Safe JSON parsing ──────────────────────────────────────────────────────

def _strip_json_fences(content: str) -> str:
    text = (content or "").replace("\ufeff", "").strip()
    text = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _extract_outer_json_object(content: str) -> str:
    start = content.find("{")
    if start == -1:
        return content
    depth = 0
    end = -1
    in_string = False
    string_quote = ""
    escaped = False
    for i in range(start, len(content)):
        ch = content[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == string_quote:
                in_string = False
            continue
        if ch in {'"', "'"}:
            in_string = True
            string_quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end > start:
        return content[start:end]
    return content[start:]


def _repair_common_json_issues(content: str) -> str:
    text = content
    # Remove JS-style comments occasionally emitted by LLMs.
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    text = re.sub(r"(?m)^\s*//.*$", "", text)
    # Quote bare object keys in JS-like output: { foo: 1 } -> { "foo": 1 }
    text = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_\-]*)(\s*:)', r'\1"\2"\3', text)
    # Remove trailing commas before object/array close.
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text.strip()


def _insert_missing_commas(content: str) -> str:
    text = content
    patterns = [
        # A completed string/object/array/number is followed by a new object key on the next line.
        (r'("|\}|\]|\btrue\b|\bfalse\b|\bnull\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(\s*\n\s*)(?="[^"\n]+"\s*:)', r'\1,\2'),
        # A completed value is followed by a nested object/array on the next line.
        (r'("|\}|\]|\btrue\b|\bfalse\b|\bnull\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(\s*\n\s*)(?=[\{\[])', r'\1,\2'),
        # Same-line missing comma before the next quoted key.
        (r'("|\}|\]|\btrue\b|\bfalse\b|\bnull\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(\s+)(?="[^"\n]+"\s*:)', r'\1,\2'),
    ]
    changed = True
    while changed:
        changed = False
        for pattern, repl in patterns:
            updated = re.sub(pattern, repl, text)
            if updated != text:
                text = updated
                changed = True
    return text


def _escape_newlines_in_strings(content: str) -> str:
    result: List[str] = []
    in_string = False
    quote = ""
    escaped = False
    for ch in content:
        if in_string:
            if escaped:
                result.append(ch)
                escaped = False
                continue
            if ch == "\\":
                result.append(ch)
                escaped = True
                continue
            if ch == quote:
                result.append(ch)
                in_string = False
                quote = ""
                continue
            if ch == "\n":
                result.append("\\n")
                continue
            if ch == "\r":
                result.append("\\r")
                continue
            result.append(ch)
            continue
        if ch in {'"', "'"}:
            in_string = True
            quote = ch
        result.append(ch)
    return "".join(result)


def _balance_truncated_json(content: str) -> str:
    result: List[str] = []
    stack: List[str] = []
    in_string = False
    quote = ""
    escaped = False
    for ch in content:
        result.append(ch)
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                in_string = False
                quote = ""
            continue
        if ch in {'"', "'"}:
            in_string = True
            quote = ch
        elif ch == "{":
            stack.append("}")
        elif ch == "[":
            stack.append("]")
        elif ch in {"}", "]"} and stack and ch == stack[-1]:
            stack.pop()
    if in_string:
        result.append(quote or '"')
    while stack:
        result.append(stack.pop())
    return "".join(result)


def _try_yaml_dict_parse(content: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = yaml.safe_load(content)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _try_python_literal_dict_parse(content: str) -> Optional[Dict[str, Any]]:
    # Handle Python/JS-style dicts that json/yaml still reject.
    candidate = re.sub(r"\btrue\b", "True", content)
    candidate = re.sub(r"\bfalse\b", "False", candidate)
    candidate = re.sub(r"\bnull\b", "None", candidate)
    try:
        parsed = ast.literal_eval(candidate)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _safe_json_parse(content: str) -> dict:
    """Tolerant JSON parser for imperfect LLM output."""
    cleaned = _strip_json_fences(content)
    candidates = []
    for candidate in [cleaned, _extract_outer_json_object(cleaned)]:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    last_error: Optional[Exception] = None
    for candidate in candidates:
        derived_candidates = []
        for derived in [
            candidate,
            _repair_common_json_issues(candidate),
            _insert_missing_commas(_repair_common_json_issues(candidate)),
            _escape_newlines_in_strings(_insert_missing_commas(_repair_common_json_issues(candidate))),
            _balance_truncated_json(_escape_newlines_in_strings(_insert_missing_commas(_repair_common_json_issues(candidate)))),
        ]:
            if derived and derived not in derived_candidates:
                derived_candidates.append(derived)

        for derived in derived_candidates:
            try:
                return json.loads(derived)
            except json.JSONDecodeError as err:
                last_error = err
            yaml_parsed = _try_yaml_dict_parse(derived)
            if yaml_parsed is not None:
                return yaml_parsed
            literal_parsed = _try_python_literal_dict_parse(derived)
            if literal_parsed is not None:
                return literal_parsed

    if last_error:
        raise last_error
    raise json.JSONDecodeError("Unable to parse LLM response as JSON object", cleaned, 0)


def _repair_json_with_llm(client: Any, content: str) -> Optional[Dict[str, Any]]:
    repair_prompt = (
        "You repair malformed JSON produced by another model. "
        "Return exactly one valid JSON object and preserve the original structure/content as much as possible. "
        "Do not add explanations or markdown fences."
    )
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": repair_prompt},
                {"role": "user", "content": content[:24000]},
            ],
            max_tokens=4096,
            temperature=0,
            response_format={"type": "json_object"},
            timeout=120,
        )
    except Exception:
        return None

    repaired = (resp.choices[0].message.content or "").strip()
    if not repaired:
        return None
    try:
        return _safe_json_parse(repaired)
    except Exception:
        return None


def _write_llm_debug_artifact(prefix: str, content: str) -> Optional[str]:
    try:
        os.makedirs(LLM_DEBUG_DIR, exist_ok=True)
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        path = os.path.join(LLM_DEBUG_DIR, f"{timestamp}-{os.getpid()}-{prefix}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content or "")
        return path
    except Exception:
        return None


# ── LLM Call ────────────────────────────────────────────────────────────────

def call_llm(prompt: str, text: str) -> Dict[str, Any]:
    """Single LLM call with retry. Uses deepseek-chat."""
    from openai import OpenAI

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")

    last_error = None
    for attempt in range(3):
        try:
            messages = [{"role": "system", "content": prompt}]
            if attempt > 0:
                messages.append({
                    "role": "system",
                    "content": (
                        "Return one complete and valid JSON object only. "
                        "All string values must have closed quotes. "
                        "Escape embedded newlines inside strings as \\n. "
                        "Do not truncate the final object."
                    ),
                })
            messages.append({"role": "user", "content": text})
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                max_tokens=8192,
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=180,
            )
            content = resp.choices[0].message.content or "{}"
            try:
                return _safe_json_parse(content)
            except Exception as parse_error:
                raw_path = _write_llm_debug_artifact(f"attempt{attempt+1}-raw", content)
                if raw_path:
                    print(f"  saved raw LLM output -> {raw_path}", flush=True)
                repaired = _repair_json_with_llm(client, content)
                if repaired is not None:
                    return repaired
                raise parse_error
        except Exception as e:
            last_error = e
            print(f"  [retry {attempt+1}] {e}", flush=True)
            time.sleep(2 ** attempt)

    raise RuntimeError(f"All 3 LLM attempts failed: {last_error}")


# ── Post-Processing ─────────────────────────────────────────────────────────

def enforce_case_level(row: Dict[str, str], output: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(output, dict):
        return output
    csv_cl = row.get("case_level", "").strip().replace("\\N", "").strip()
    cl_map = {"01": "guiding_case", "02": "typical_case"}
    bf_map = {"01": "mandatory", "02": "persuasive"}
    enforced_cl = cl_map.get(csv_cl, "reference_case")
    enforced_bf = bf_map.get(csv_cl, "reference")
    if "guiding_case" in output and isinstance(output["guiding_case"], dict):
        output["guiding_case"]["case_level"] = enforced_cl
        output["guiding_case"]["binding_force"] = enforced_bf
    return output


def enforce_source_url(row: Dict[str, str], output: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(output, dict):
        return output
    input_url = row.get("web_url", "").strip()
    if input_url and "guiding_case" in output and isinstance(output["guiding_case"], dict):
        GENERIC_URLS = {"https://rmfyalk.court.gov.cn", "https://rmfyalk.court.gov.cn/"}
        existing = output["guiding_case"].get("source_url", "").strip()
        if existing in GENERIC_URLS or not existing:
            output["guiding_case"]["source_url"] = input_url
    return output


def fill_empty_provision_content(output: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(output, dict):
        return output
    provisions = output.get("legal_provisions") or []
    for p in provisions:
        if not p.get("content", "").strip():
            statute = p.get("statute", "").strip()
            article = p.get("article", "").strip()
            if statute and article:
                p["content"] = f"《{statute}》第{article}条（提取自相关法条引用）"
            elif statute:
                p["content"] = f"《{statute}》（提取自相关法条引用）"
            else:
                p["content"] = "法条引用（提取自相关法条引用）"
    return output


def _normalize_relation_ref(ref: str) -> str:
    if not isinstance(ref, str):
        return ref
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


def _normalize_scalar_text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def _normalize_scalar_value(value: Any) -> Any:
    if isinstance(value, str):
        return _normalize_scalar_text(value)
    if isinstance(value, list):
        return [_normalize_scalar_value(item) for item in value if item not in (None, "", [], {})]
    if isinstance(value, dict):
        return {
            key: _normalize_scalar_value(item)
            for key, item in value.items()
            if item not in (None, "", [], {})
        }
    return value


def _fingerprint_payload(value: Any) -> str:
    dumped = _stable_dump(_normalize_scalar_value(value))
    return hashlib.sha1(dumped.encode("utf-8")).hexdigest()[:12]


def _build_stable_entity_id(entity_type: str, item: Dict[str, Any]) -> str:
    prefix_map = {
        "facts": "fact_sig",
        "dispute_focuses": "focus_sig",
        "evidence": "evid_sig",
        "judgment_results": "jr_sig",
        "legal_provisions": "prov_sig",
        "legal_provision_elements": "prov_elem_sig",
    }
    return f"{prefix_map.get(entity_type, 'entity_sig')}_{_fingerprint_payload(_entity_signature_payload(entity_type, item))}"


def _dedupe_preserve_order(values: List[Any]) -> List[Any]:
    seen = set()
    result: List[Any] = []
    for value in values:
        marker = _stable_dump(_normalize_scalar_value(value))
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result


def _entity_signature_payload(entity_type: str, item: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {"value": _normalize_scalar_value(item)}

    builders = {
        "facts": lambda data: {
            "content": _normalize_scalar_text(data.get("content") or data.get("description") or data.get("fact") or data.get("text")),
            "case_number": _normalize_scalar_text(data.get("case_number") or data.get("related_case_number")),
            "fact_type": _normalize_scalar_text(data.get("fact_type") or "undisputed"),
            "proven_by_evidence_ids": sorted(
                _normalize_relation_ref(str(ref))
                for ref in (data.get("proven_by_evidence_ids") or [])
                if str(ref).strip()
            ),
        },
        "dispute_focuses": lambda data: {
            "content": _normalize_scalar_text(data.get("content") or data.get("focus_issue") or data.get("focus") or data.get("text")),
            "case_number": _normalize_scalar_text(data.get("case_number") or data.get("related_case_number")),
            "focus_type": _normalize_scalar_text(data.get("focus_type")),
            "resolution_logic": _normalize_scalar_text(data.get("resolution_logic")),
        },
        "evidence": lambda data: {
            "content": _normalize_scalar_text(data.get("content") or data.get("name") or data.get("text")),
            "evidence_type": _normalize_scalar_text(data.get("evidence_type")),
            "submitted_by": _normalize_scalar_text(data.get("submitted_by")),
            "admission_status": _normalize_scalar_text(data.get("admission_status")),
            "admission_reason": _normalize_scalar_text(data.get("admission_reason")),
            "probative_force": _normalize_scalar_text(data.get("probative_force")),
            "case_number": _normalize_scalar_text(data.get("case_number")),
        },
        "judgment_results": lambda data: {
            "result_type": _normalize_scalar_text(data.get("result_type")),
            "specific_judgment": _normalize_scalar_text(data.get("specific_judgment") or data.get("content") or data.get("result")),
            "reasoning": _normalize_scalar_text(data.get("reasoning")),
            "case_number": _normalize_scalar_text(data.get("case_number")),
        },
        "legal_provisions": lambda data: {
            "statute": _normalize_scalar_text(data.get("statute") or data.get("law_name")),
            "article": _normalize_scalar_text(data.get("article") or data.get("title")),
            "paragraph": _normalize_scalar_text(data.get("paragraph")),
            "item": _normalize_scalar_text(data.get("item")),
            "content": _normalize_scalar_text(data.get("content")),
            "citation_position": _normalize_scalar_text(data.get("citation_position")),
            "citation_purpose": _normalize_scalar_text(data.get("citation_purpose")),
        },
        "legal_provision_elements": lambda data: {
            "provision_index": data.get("provision_index"),
            "statute": _normalize_scalar_text(data.get("statute")),
            "article": _normalize_scalar_text(data.get("article")),
            "element_type": _normalize_scalar_text(data.get("element_type")),
            "content": _normalize_scalar_text(data.get("content")),
            "applicable_fact_pattern": _normalize_scalar_text(data.get("applicable_fact_pattern")),
        },
    }
    builder = builders.get(entity_type)
    payload = builder(item) if builder else {
        key: _normalize_scalar_value(value)
        for key, value in item.items()
        if key not in {"id", "stable_id", "node_id", "evidence_id", "element_id", "provision_id", "result_id", "fact_id", "focus_id"}
    }
    return {
        key: value
        for key, value in payload.items()
        if value not in (None, "", [], {})
    }


def _normalize_evidence_item(evidence: Dict[str, Any], index: int) -> Dict[str, Any]:
    normalized = {
        **evidence,
        "id": _normalize_relation_ref(evidence.get("id") or evidence.get("node_id") or f"evid_{index}"),
        "content": evidence.get("content") or evidence.get("name") or evidence.get("text") or "",
        "evidence_type": evidence.get("evidence_type") or "",
        "submitted_by": evidence.get("submitted_by") or "",
        "admission_status": evidence.get("admission_status") or "",
        "admission_reason": evidence.get("admission_reason") or "",
        "probative_force": evidence.get("probative_force") or "",
        "case_number": evidence.get("case_number") or evidence.get("related_case_number") or "",
    }
    stable_id = evidence.get("stable_id") or evidence.get("evidence_id") or _build_stable_entity_id("evidence", normalized)
    normalized["stable_id"] = stable_id
    normalized["evidence_id"] = evidence.get("evidence_id") or stable_id
    return normalized


def _normalize_judgment_result_item(result: Dict[str, Any], index: int) -> Dict[str, Any]:
    normalized = {
        **result,
        "id": _normalize_relation_ref(result.get("id") or result.get("result_id") or result.get("node_id") or f"jr_{index}"),
        "result_type": result.get("result_type") or "",
        "specific_judgment": result.get("specific_judgment") or result.get("content") or "",
        "reasoning": result.get("reasoning") or "",
        "case_number": result.get("case_number") or "",
    }
    normalized["stable_id"] = result.get("stable_id") or _build_stable_entity_id("judgment_results", normalized)
    return normalized


def _normalize_legal_provision_item(provision: Dict[str, Any], index: int) -> Dict[str, Any]:
    normalized = {
        **provision,
        "id": _normalize_relation_ref(provision.get("id") or provision.get("provision_id") or provision.get("node_id") or f"prov_{index}"),
        "statute": provision.get("statute") or provision.get("law_name") or "",
        "article": provision.get("article") or "",
        "paragraph": provision.get("paragraph") or "",
        "item": provision.get("item") or "",
        "content": provision.get("content") or "",
        "citation_position": provision.get("citation_position") or "",
        "citation_purpose": provision.get("citation_purpose") or "",
    }
    normalized["stable_id"] = provision.get("stable_id") or _build_stable_entity_id("legal_provisions", normalized)
    return normalized


def _normalize_entity_collection_for_payload(entity_type: str, items: Any) -> List[Dict[str, Any]]:
    if not isinstance(items, list):
        return []

    normalizers = {
        "facts": lambda item, idx: {
            **item,
            "id": _normalize_relation_ref(item.get("id") or item.get("fact_id") or item.get("node_id") or f"fact_{idx}"),
            "content": item.get("content") or item.get("description") or item.get("fact") or item.get("text") or "",
            "case_number": item.get("case_number") or item.get("related_case_number") or "",
            "fact_type": item.get("fact_type") or "undisputed",
            "proven_by_evidence_ids": [
                _normalize_relation_ref(x) for x in (item.get("proven_by_evidence_ids") or [])
            ],
        },
        "dispute_focuses": lambda item, idx: {
            **item,
            "id": _normalize_relation_ref(item.get("id") or item.get("focus_id") or item.get("node_id") or f"focus_{idx}"),
            "content": item.get("content") or item.get("focus_issue") or item.get("focus") or item.get("text") or "",
            "case_number": item.get("case_number") or item.get("related_case_number") or "",
            "focus_type": item.get("focus_type") or "",
            "resolution_logic": item.get("resolution_logic") or "",
        },
        "evidence": _normalize_evidence_item,
        "judgment_results": _normalize_judgment_result_item,
        "legal_provisions": _normalize_legal_provision_item,
        "legal_provision_elements": lambda item, idx: {
            **item,
            "id": _normalize_relation_ref(item.get("id") or item.get("element_id") or item.get("node_id") or f"prov_elem_{idx}"),
            "provision_index": int(item.get("provision_index")) if item.get("provision_index") not in ("", None) and str(item.get("provision_index")).isdigit() else (item.get("provision_index") if isinstance(item.get("provision_index"), int) else None),
            "statute": item.get("statute") or "",
            "article": item.get("article") or "",
            "content": item.get("content") or "",
            "element_type": item.get("element_type") or "",
            "applicable_fact_pattern": item.get("applicable_fact_pattern") or "",
        },
    }
    normalizer = normalizers.get(entity_type)
    if not normalizer:
        return [item for item in items if isinstance(item, dict)]

    normalized_items = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        normalized = normalizer(item, idx)
        normalized["stable_id"] = normalized.get("stable_id") or _build_stable_entity_id(entity_type, normalized)
        normalized_items.append(normalized)
    return normalized_items


def _merge_entity_list(entity_type: str, old_items: List[Dict[str, Any]], new_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged = [copy.deepcopy(item) for item in old_items if isinstance(item, dict)]
    identity_to_index = {
        _entity_identity(entity_type, item): idx
        for idx, item in enumerate(merged)
    }

    for item in new_items:
        if not isinstance(item, dict):
            continue
        identity = _entity_identity(entity_type, item)
        if identity in identity_to_index:
            target = merged[identity_to_index[identity]]
            for key, value in item.items():
                if value in (None, "", [], {}):
                    continue
                if isinstance(value, list):
                    target[key] = _dedupe_preserve_order([*(target.get(key) or []), *value])
                elif isinstance(value, dict):
                    current = target.get(key) or {}
                    if isinstance(current, dict):
                        current.update({k: v for k, v in value.items() if v not in (None, "", [], {})})
                        target[key] = current
                    else:
                        target[key] = value
                else:
                    target[key] = value
            continue
        merged.append(copy.deepcopy(item))
        identity_to_index[identity] = len(merged) - 1
    return merged


def _merge_relation_list(old_relations: List[Dict[str, Any]], new_relations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged = [copy.deepcopy(item) for item in old_relations if isinstance(item, dict)]
    identity_to_index = {
        _relation_identity(item): idx
        for idx, item in enumerate(merged)
    }
    for rel in new_relations:
        if not isinstance(rel, dict):
            continue
        identity = _relation_identity(rel)
        if identity in identity_to_index:
            target = merged[identity_to_index[identity]]
            for key, value in rel.items():
                if value not in (None, "", [], {}):
                    target[key] = value
            continue
        merged.append(copy.deepcopy(rel))
        identity_to_index[identity] = len(merged) - 1
    return merged


def align_enhancement_payload(base_output: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = normalize_enhancement_payload(payload)
    aligned = copy.deepcopy(payload)
    normalized_base = normalize_graph_output(copy.deepcopy(base_output or {}))

    entity_keys = ("facts", "dispute_focuses", "evidence", "judgment_results", "legal_provisions", "legal_provision_elements")
    for key in entity_keys:
        if key not in aligned:
            continue
        normalized_items = _normalize_entity_collection_for_payload(key, aligned.get(key) or [])
        existing_items = normalized_base.get(key) or []
        existing_lookup = {
            _entity_identity(key, item): item
            for item in existing_items
            if isinstance(item, dict)
        }
        result_items = []
        for item in normalized_items:
            identity = _entity_identity(key, item)
            existing = existing_lookup.get(identity)
            if existing:
                kept = copy.deepcopy(item)
                for ref_key in ("id", "stable_id", "evidence_id", "fact_id", "focus_id", "result_id", "provision_id", "element_id"):
                    if existing.get(ref_key):
                        kept[ref_key] = existing.get(ref_key)
                result_items.append(kept)
            else:
                result_items.append(item)
        aligned[key] = result_items

    if isinstance(aligned.get("relations"), list):
        normalized_relations = []
        for rel in aligned["relations"]:
            if not isinstance(rel, dict):
                continue
            src = _normalize_relation_ref(rel.get("source_id", ""))
            tgt = _normalize_relation_ref(rel.get("target_id", ""))
            rtype = (rel.get("relation_type") or "").strip()
            if not src or not tgt or not rtype:
                continue
            normalized_relations.append({
                **rel,
                "source_id": src,
                "target_id": tgt,
                "relation_type": rtype,
                "label": rel.get("label") or rtype,
            })
        aligned["relations"] = _merge_relation_list([], normalized_relations)

    return aligned


def normalize_graph_output(output: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(output, dict):
        return output

    facts = output.get("facts") or []
    normalized_facts = []
    for i, fact in enumerate(facts):
        if not isinstance(fact, dict):
            continue
        normalized_facts.append({
            **fact,
            "id": fact.get("id") or f"fact_{i}",
            "content": fact.get("content") or fact.get("description") or "",
            "case_number": fact.get("case_number") or fact.get("related_case_number") or "",
            "fact_type": fact.get("fact_type") or "undisputed",
            "proven_by_evidence_ids": [
                _normalize_relation_ref(x) for x in (fact.get("proven_by_evidence_ids") or [])
            ],
        })
    output["facts"] = normalized_facts

    focuses = output.get("dispute_focuses") or []
    normalized_focuses = []
    for i, focus in enumerate(focuses):
        if not isinstance(focus, dict):
            continue
        normalized_focuses.append({
            **focus,
            "id": focus.get("id") or f"focus_{i}",
            "content": focus.get("content") or focus.get("focus_issue") or "",
            "case_number": focus.get("case_number") or focus.get("related_case_number") or "",
        })
    output["dispute_focuses"] = normalized_focuses

    evidence = output.get("evidence") or []
    output["evidence"] = _normalize_entity_collection_for_payload("evidence", evidence)

    judgment_results = output.get("judgment_results") or []
    output["judgment_results"] = _normalize_entity_collection_for_payload("judgment_results", judgment_results)

    legal_provisions = output.get("legal_provisions") or []
    output["legal_provisions"] = _normalize_entity_collection_for_payload("legal_provisions", legal_provisions)

    elements = output.get("legal_provision_elements") or []
    output["legal_provision_elements"] = _normalize_entity_collection_for_payload("legal_provision_elements", elements)

    relations = output.get("relations") or []
    normalized_relations = []
    derived_relation_types = {
        str(item.get("relation_type") or "").strip()
        for item in (load_relation_policies().get("derived_relations") or [])
        if isinstance(item, dict) and item.get("relation_type")
    }
    for rel in relations:
        if not isinstance(rel, dict):
            continue
        src = _normalize_relation_ref(rel.get("source_id", ""))
        tgt = _normalize_relation_ref(rel.get("target_id", ""))
        rtype = (rel.get("relation_type") or "").strip()
        if rtype in derived_relation_types:
            continue
        normalized_relations.append({
            **rel,
            "source_id": src,
            "target_id": tgt,
            "relation_type": rtype,
            "label": rel.get("label") or rtype,
        })
    output["relations"] = normalized_relations

    derived_relations = output.get("derived_relations") or []
    normalized_derived_relations = []
    for rel in derived_relations:
        if not isinstance(rel, dict):
            continue
        src = _normalize_relation_ref(rel.get("source_id", ""))
        tgt = _normalize_relation_ref(rel.get("target_id", ""))
        rtype = (rel.get("relation_type") or "").strip()
        if not src or not tgt or not rtype:
            continue
        normalized_derived_relations.append({
            **rel,
            "source_id": src,
            "target_id": tgt,
            "relation_type": rtype,
            "label": rel.get("label") or rtype,
            "is_derived": True,
        })
    output["derived_relations"] = normalized_derived_relations
    return output


def _split_graph_text(text: Any, max_items: int = 3) -> List[str]:
    if not text:
        return []
    if isinstance(text, list):
        source = "；".join(str(x).strip() for x in text if str(x).strip())
    else:
        source = str(text).strip()
    if not source:
        return []
    source = re.sub(r"\s+", " ", source)
    parts = re.split(r"(?:^|[；;。])\s*[0-9一二三四五六七八九十]+[、\.．\)]\s*", source)
    candidates = [p.strip("；;。 \n\t") for p in parts if p.strip("；;。 \n\t")]
    if len(candidates) <= 1:
        candidates = [
            p.strip("；;。 \n\t")
            for p in re.split(r"[；;。]\s*", source)
            if p.strip("；;。 \n\t")
        ]
    return candidates[:max_items]


def enrich_graph_output(output: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(output, dict):
        return output
    output = normalize_graph_output(output)

    court_cases = output.get("court_cases") or []
    case_numbers = [cc.get("case_number", "") for cc in court_cases if cc.get("case_number")]
    final_case_number = case_numbers[-1] if case_numbers else ""
    primary_case_number = final_case_number or (case_numbers[0] if case_numbers else "")

    cs = output.get("case_summary") or {}
    facts = output.get("facts") or []
    if not facts:
        facts = []
        for i, seg in enumerate(_split_graph_text(cs.get("key_facts", ""), 3)):
            facts.append({
                "id": f"fact_{i}",
                "content": seg,
                "case_number": primary_case_number,
                "fact_type": "undisputed",
                "proven_by_evidence_ids": [],
            })
        output["facts"] = facts

    focuses = output.get("dispute_focuses") or []
    if not focuses:
        focuses = []
        for i, seg in enumerate(_split_graph_text(cs.get("disputed_issues", ""), 3)):
            focuses.append({
                "id": f"focus_{i}",
                "content": seg,
                "case_number": primary_case_number,
            })
        output["dispute_focuses"] = focuses

    relations = output.get("relations") or []
    derived_relations = output.get("derived_relations") or []
    existing = {
        ((r.get("source_id") or ""), (r.get("target_id") or ""), (r.get("relation_type") or ""))
        for r in relations if isinstance(r, dict)
    }
    derived_existing = {
        ((r.get("source_id") or ""), (r.get("target_id") or ""), (r.get("relation_type") or ""))
        for r in derived_relations if isinstance(r, dict)
    }

    def add_relation(src: str, tgt: str, rtype: str):
        key = (src, tgt, rtype)
        if not src or not tgt or key in existing:
            return
        existing.add(key)
        relations.append({
            "source_id": src,
            "target_id": tgt,
            "relation_type": rtype,
            "label": rtype,
        })

    def add_derived_relation(src: str, tgt: str, rtype: str, label: str, rule_name: str):
        key = (src, tgt, rtype)
        if not src or not tgt or key in existing or key in derived_existing:
            return
        derived_existing.add(key)
        derived_relations.append({
            "source_id": src,
            "target_id": tgt,
            "relation_type": rtype,
            "label": label,
            "is_derived": True,
            "derived_rule": rule_name,
        })

    evids = output.get("evidence") or []
    for i, fact in enumerate(output.get("facts") or []):
        fact_id = fact.get("id") or f"fact_{i}"
        if primary_case_number:
            add_relation(primary_case_number, fact_id, "has_fact")

    for i, focus in enumerate(output.get("dispute_focuses") or []):
        focus_id = focus.get("id") or f"focus_{i}"
        if primary_case_number:
            add_relation(primary_case_number, focus_id, "has_dispute_focus")

    for i, evidence in enumerate(evids):
        evid_id = evidence.get("id") or f"evid_{i}"
        target_case = evidence.get("case_number") or primary_case_number
        if target_case:
            add_relation(evid_id, target_case, "submitted_for")
        if output.get("facts"):
            target_fact = (output["facts"][i % len(output["facts"])].get("id")) or f"fact_{i % len(output['facts'])}"
            add_relation(evid_id, target_fact, "proves_fact")

    jrs = output.get("judgment_results") or []
    if jrs:
        jr_id = "jr_0"
        for i, focus in enumerate(output.get("dispute_focuses") or []):
            focus_id = focus.get("id") or f"focus_{i}"
            add_relation(focus_id, jr_id, "leads_to")
        for i, _ in enumerate(output.get("legal_provisions") or []):
            add_relation(jr_id, f"prov_{i}", "judgment_cites")

    policies = load_relation_policies()
    for rule in policies.get("derived_relations") or []:
        if rule.get("derivation_kind") != "provision_index":
            continue
        relation_type = rule.get("relation_type") or ""
        label = rule.get("label") or relation_type
        rule_name = rule.get("name") or relation_type
        source_key = rule.get("source_collection") or "legal_provision_elements"
        target_prefix = rule.get("target_node_prefix") or "prov_"
        target_items = output.get(rule.get("target_collection") or "legal_provisions") or []
        for i, element in enumerate(output.get(source_key) or []):
            if not isinstance(element, dict):
                continue
            provision_index = element.get("provision_index")
            if not isinstance(provision_index, int):
                continue
            if provision_index < 0 or provision_index >= len(target_items):
                continue
            element_id = element.get("id") or f"prov_elem_{i}"
            add_derived_relation(element_id, f"{target_prefix}{provision_index}", relation_type, label, rule_name)

    output["relations"] = relations
    output["derived_relations"] = derived_relations
    return output


def should_retry_with_fallback_prompt(row: Dict[str, str], output: Dict[str, Any]) -> bool:
    if not isinstance(output, dict):
        return True
    ct = (row.get("case_type") or "").strip()
    if not ct.startswith("行政"):
        return False
    if output:
        if (output.get("court_cases") or []) and (output.get("case_type") or {}).get("category"):
            return False
    return True


def extract_case_name(output: Dict[str, Any]) -> str:
    """Extract a human-readable case name from LLM output."""
    gc = output.get("guiding_case") or {}
    name = gc.get("guiding_case_name", "")
    if name:
        return name
    court_cases = output.get("court_cases") or []
    if court_cases:
        return court_cases[0].get("case_number", "")
    return "未命名案例"


# ── KG Conversion ──────────────────────────────────────────────────────────

def kg_convert(output: Dict[str, Any]) -> Dict[str, List[Dict]]:
    """
    Convert LLM output JSON into vis-network nodes/edges.
    Reuses the same shape/color scheme as admin_instances.html.
    Entities are correctly associated to their court instance via case_number.
    Labels use Chinese.
    """
    # ── Chinese label mapping tables ──────────────────────────────────────
    CASE_TYPE_MAP = {
        "civil": "民事",
        "criminal": "刑事",
        "administrative": "行政",
    }
    BINDING_FORCE_MAP = {
        "reference": "参考案例",
        "mandatory": "指导性案例",
        "persuasive": "典型案例",
    }
    RESULT_TYPE_MAP = {
        "guilty": "有罪判决",
        "not_guilty": "无罪判决",
        "liable": "承担责任",
        "not_liable": "不承担责任",
        "dismissed": "驳回",
        "withdrawn": "撤诉",
        "upheld": "维持",
        "reversed": "撤销",
        "partially_upheld": "部分维持",
        "remanded": "发回重审",
        "punitive_damages": "惩罚性赔偿",
        "procedural_ruling": "程序性裁定",
        "bankruptcy_declared": "宣告破产",
        "mediation_agreement": "调解协议",
        "arbitration_award": "仲裁裁决",
        "administrative_decision": "行政决定",
        "accepted": "支持",
        "rejected": "驳回",
    }

    def summarize_judgment_result(jr: Dict[str, Any], result_type_cn: str) -> str:
        specific = str(jr.get("specific_judgment") or "").strip()
        if specific:
            return specific[:40] + ("..." if len(specific) > 40 else "")
        reasoning = str(jr.get("reasoning") or "").strip()
        if reasoning:
            return reasoning[:40] + ("..." if len(reasoning) > 40 else "")
        return result_type_cn or "裁判结果"

    nodes: List[Dict] = []
    edges: List[Dict] = []
    node_set: set = set()
    edge_set: set = set()

    def add_node(nid: str, label: str, ntype: str, group: str, level: int = 1, title: str = "", extra: dict = None):
        if nid in node_set:
            return
        node_set.add(nid)
        node_entry = {
            "id": nid,
            "label": label,
            "title": title,
            "shape": ADMIN_SHAPES.get(ntype, "ellipse"),
            "size": 35 if level == 0 else (26 if level == 1 else 20),
            "color": ROOT_COLORS.get(group, {"bg": "#7f8c8d", "border": "#5d6d7e"}),
            "font": {"color": "#fff", "size": 14 if level == 0 else 12},
            "borderWidth": 2,
            "group": group,
            "nodeType": ntype,
            "level": level,
        }
        if extra:
            node_entry.update(extra)
        nodes.append(node_entry)

    def add_edge(fr: str, to: str, label: str, extra: dict = None):
        relation_type = (extra or {}).get("relation_type") or label
        edge_type = (extra or {}).get("edge_type") or "explicit"
        key = f"{fr}|{to}|{relation_type}|{edge_type}"
        if key in edge_set:
            return
        edge_set.add(key)
        edge_entry = {
            "id": key,
            "from": fr, "to": to, "label": label,
            "color": {"color": "#7f8c8d", "highlight": "#333", "hover": "#333", "opacity": 0.7},
            "font": {"size": 10, "color": "#555", "strokeWidth": 2, "strokeColor": "#fff"},
            "width": 1.5, "smooth": {"type": "continuous"},
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.6}},
            "relationType": relation_type,
            "edgeType": edge_type,
            "isDerived": bool((extra or {}).get("is_derived")),
        }
        if extra:
            edge_entry.update(extra)
        edges.append(edge_entry)

    # ── Build case_number → cc_id mapping ────────────────────────────────
    court_cases = output.get("court_cases") or []
    cn_to_cc = {}  # "(2024)沪73知民初164号" -> "cc_0"
    first_cc_id = None
    for i, cc in enumerate(court_cases):
        cn = cc.get("case_number", "")
        nid = f"cc_{i}"
        if first_cc_id is None:
            first_cc_id = nid
        if cn:
            cn_to_cc[cn] = nid

    # ── GuidingCase ──────────────────────────────────────────────────────
    gc = output.get("guiding_case") or {}
    if gc.get("guiding_case_name"):
        # Translate binding_force to Chinese
        bf_raw = gc.get("binding_force", "")
        bf_cn = BINDING_FORCE_MAP.get(bf_raw, bf_raw)
        add_node("gc", gc["guiding_case_name"], "GuidingCase", "LegalNorm", 0,
                 f"案号: {gc.get('guiding_case_number', '')}<br>效力: {bf_cn}")
        cn = gc.get("guiding_case_number", "")
        if cn:
            add_node("gc_num", cn, "GuidingCase", "LegalNorm", 1)
            add_edge("gc", "gc_num", "案号")

        # GuidingCase 关联边 — 如果有 trial_procedure="二审" 或无 case_number，关联到 cc_1
        gc_cn = gc.get("guiding_case_number", "")
        gc_trial = gc.get("trial_procedure", "")
        gc_target = first_cc_id  # default to first cc
        if not gc_cn or gc_trial == "二审":
            # 优先找二审案 (cc_1)
            for i, cc in enumerate(court_cases):
                if cc.get("trial_level") == "second_instance" or cc.get("trial_procedure") == "二审":
                    gc_target = f"cc_{i}"
                    break
            if not gc_cn:
                add_edge(gc_target, "gc", "关联")
            else:
                add_edge(gc_target, "gc", "关联")
        else:
            # 有 guiding_case_number，找匹配
            matched = cn_to_cc.get(gc_cn, first_cc_id)
            add_edge(matched, "gc", "关联")

    # ── CaseType ─────────────────────────────────────────────────────────
    ct = output.get("case_type") or {}
    ct_category_raw = ct.get("category", "")
    ct_category_cn = CASE_TYPE_MAP.get(ct_category_raw, ct_category_raw)
    if ct_category_raw:
        add_node("ct", ct_category_cn, "CaseType", "JudicialEntity", 0)
        for lv_key, lv_label in [("level1", "一级案由"), ("level2", "二级案由")]:
            val = ct.get(lv_key)
            if val:
                nid = f"ct_{lv_key}_{val}"
                add_node(nid, val, "CaseType", "JudicialEntity", 1)
                add_edge("ct", nid, lv_label)

    # ── CourtCases — 创建审级节点 ───────────────────────────────────────
    for i, cc in enumerate(court_cases):
        cn = cc.get("case_number", f"case_{i}")
        nid = f"cc_{i}"
        label = cn[:60]
        add_node(nid, label, "CourtCase", "JudicialEntity", 0,
                 f"案号: {cn}<br>立案日期: {cc.get('filing_date', '')}")
        # CaseType 关联到所有 court_cases
        if ct.get("category"):
            add_edge("ct", nid, "案由")

    # ── 审级间关联边 ────────────────────────────────────────────────────
    if len(court_cases) >= 2:
        # 按 trial_level 排序：一审在前，二审在后
        # 简单地按顺序连接：cc_0 → cc_1 → cc_2...
        for i in range(len(court_cases) - 1):
            fr = f"cc_{i}"
            to = f"cc_{i+1}"
            add_edge(fr, to, "上诉")

    # ── LegalSubjects — 按 role 中的 case_number 关联 ────────────────────
    subjects = output.get("legal_subjects") or output.get("parties") or []
    # First pass: create all subject nodes
    for i, subj in enumerate(subjects):
        name = subj.get("name", f"当事人_{i}")
        nid = f"subj_{i}"
        add_node(nid, name[:40], "LegalSubject", "LegalSubject", 0)

    # Second pass: create edges per role with correct cc
    for i, subj in enumerate(subjects):
        nid = f"subj_{i}"
        roles = subj.get("roles") or []
        if roles:
            for role in roles:
                case_num = role.get("case_number", "")
                role_name = role.get("role_name", "当事人")
                if case_num and case_num in cn_to_cc:
                    add_edge(cn_to_cc[case_num], nid, role_name)
                elif court_cases:
                    # fallback to first cc
                    add_edge(first_cc_id, nid, role_name)
        elif court_cases:
            # No roles at all — fallback
            add_edge(first_cc_id, nid, "当事人")

    # ── Judges — 按 case_number 关联 ────────────────────────────────────
    judges = output.get("judges") or []
    for i, j in enumerate(judges):
        name = j.get("name", f"法官_{i}")
        nid = f"judge_{i}"
        add_node(nid, name, "Judge", "LegalSubject", 1, extra={
            "entitySourceId": j.get("id") or j.get("node_id") or nid,
            "entityStableId": j.get("stable_id") or "",
        })
        case_num = j.get("case_number", "")
        if case_num and case_num in cn_to_cc:
            add_edge(cn_to_cc[case_num], nid, "审判")
        elif court_cases:
            add_edge(first_cc_id, nid, "审判")

    # ── Attorneys — 按 case_number 关联 ─────────────────────────────────
    attorneys = output.get("attorneys") or []
    for i, a in enumerate(attorneys):
        name = a.get("name", f"律师_{i}")
        nid = f"atty_{i}"
        add_node(nid, name, "Attorney", "LegalSubject", 1, extra={
            "entitySourceId": a.get("id") or a.get("node_id") or nid,
            "entityStableId": a.get("stable_id") or "",
        })
        case_num = a.get("case_number", "")
        if case_num and case_num in cn_to_cc:
            add_edge(cn_to_cc[case_num], nid, "代理")
        elif court_cases:
            add_edge(first_cc_id, nid, "代理")

    # ── LegalProvisions — 按 case_number 关联 ───────────────────────────
    provisions = output.get("legal_provisions") or []
    for i, p in enumerate(provisions):
        statute = p.get("statute", "法规")
        article = p.get("article", f"{i}")
        label = f"{statute}第{article}条"
        nid = f"prov_{i}"
        add_node(nid, label[:60], "LegalProvision", "LegalNorm", 1,
                 p.get("content", ""),
                 extra={
                     "entitySourceId": p.get("id") or p.get("provision_id") or nid,
                     "entityStableId": p.get("stable_id") or "",
                 })
        case_num = p.get("case_number", "")
        if case_num and case_num in cn_to_cc:
            add_edge(cn_to_cc[case_num], nid, "引用")
        elif court_cases:
            add_edge(first_cc_id, nid, "引用")

    # ── LegalProvisionElements — 通过 provision_index 自动挂到法条 ────────────
    elements = output.get("legal_provision_elements") or []
    for i, elem in enumerate(elements):
        content = elem.get("content") or elem.get("applicable_fact_pattern") or f"法条要件_{i}"
        label = content[:36]
        nid = elem.get("id") or f"prov_elem_{i}"
        detail_lines = [
            f"类型: {elem.get('element_type', '')}",
            f"法条索引: {elem.get('provision_index', '')}",
            f"法规: {elem.get('statute', '')}",
            f"条号: {elem.get('article', '')}",
            f"要件内容: {elem.get('content', '')[:80]}",
            f"适用事实模式: {elem.get('applicable_fact_pattern', '')[:80]}",
        ]
        add_node(nid, label, "LegalProvisionElement", "LegalNorm", 2, "<br>".join(x for x in detail_lines if x and not x.endswith(": ")), extra={
            "entitySourceId": elem.get("id") or elem.get("element_id") or nid,
            "entityStableId": elem.get("stable_id") or "",
        })

    # ── Evidence — 按 case_number 或 submitted_by 关联 ──────────────────
    evids = output.get("evidence") or []
    for i, e in enumerate(evids):
        content = e.get("content", f"证据_{i}")
        label = content[:40]
        nid = e.get("id") or f"evid_{i}"
        admission_status = e.get("admission_status", "")
        admission_reason = e.get("admission_reason", "")
        probative_force = e.get("probative_force", "")
        add_node(nid, label, "Evidence", "JudicialEntity", 1,
                 f"类型: {e.get('evidence_type', '')}<br>提交: {e.get('submitted_by', '')}<br>关键证据: {'是' if e.get('is_key_evidence') else '否'}<br>采信: {admission_status}<br>理由: {admission_reason[:40]}<br>证明力: {probative_force}",
                 extra={"admission_status": admission_status,
                        "admission_reason": admission_reason,
                       "probative_force": probative_force,
                       "entitySourceId": e.get("id") or e.get("evidence_id") or nid,
                       "entityStableId": e.get("stable_id") or e.get("evidence_id") or ""})
        case_num = e.get("case_number", "")
        if case_num and case_num in cn_to_cc:
            add_edge(cn_to_cc[case_num], nid, "证据")
        elif court_cases:
            # Try to find via submitted_by — look for a subject with that name
            submitted_by = e.get("submitted_by", "")
            if submitted_by and len(court_cases) > 1:
                # Find subject with matching name, get their first role's cc
                target_cc = None
                for subj in subjects:
                    if subj.get("name") == submitted_by:
                        roles = subj.get("roles") or []
                        # Get the first role's case_number
                        for role in roles:
                            rcn = role.get("case_number", "")
                            if rcn and rcn in cn_to_cc:
                                target_cc = cn_to_cc[rcn]
                                break
                        break
                if target_cc:
                    add_edge(target_cc, nid, "证据")
                else:
                    add_edge(first_cc_id, nid, "证据")
            else:
                add_edge(first_cc_id, nid, "证据")

    # ── JudgmentResults — 按 case_number 关联 ───────────────────────────
    jrs = output.get("judgment_results") or []
    for i, jr in enumerate(jrs):
        rtype_raw = jr.get("result_type", "裁判结果")
        rtype_cn = RESULT_TYPE_MAP.get(rtype_raw, rtype_raw)
        nid = jr.get("id") or f"jr_{i}"
        label = summarize_judgment_result(jr, rtype_cn)
        details = [
            f"结果类型: {rtype_cn}" if rtype_cn else "",
            f"具体裁判: {jr.get('specific_judgment', '')}" if jr.get("specific_judgment") else "",
            f"裁判理由: {jr.get('reasoning', '')[:120]}" if jr.get("reasoning") else "",
            f"案号: {jr.get('case_number', '')}" if jr.get("case_number") else "",
        ]
        add_node(
            nid,
            label,
            "JudgmentResult",
            "JudicialEntity",
            0,
            "<br>".join(part for part in details if part),
            extra={
                "entitySourceId": jr.get("id") or jr.get("result_id") or nid,
                "entityStableId": jr.get("stable_id") or "",
                "resultType": rtype_raw,
                "resultTypeLabel": rtype_cn,
            },
        )
        case_num = jr.get("case_number", "")
        if case_num and case_num in cn_to_cc:
            add_edge(cn_to_cc[case_num], nid, "裁判")
        elif court_cases:
            add_edge(first_cc_id, nid, "裁判")

    # ── Facts ─────────────────────────────────────────────────────────────
    facts = output.get("facts") or []
    for i, f in enumerate(facts):
        fid = f.get("id", f"fact_{i}")
        label = f.get("content", "")[:40]
        add_node(fid, label, "Fact", "JudicialEntity", 1,
                 f"类型: {f.get('fact_type', '')}<br>案号: {f.get('case_number', '')}",
                 extra={
                     "entitySourceId": f.get("id") or f.get("fact_id") or fid,
                     "entityStableId": f.get("stable_id") or "",
                 })
        case_num = f.get("case_number", "")
        if case_num and case_num in cn_to_cc:
            add_edge(cn_to_cc[case_num], fid, "事实")
        elif court_cases:
            add_edge(first_cc_id, fid, "事实")

    # ── DisputeFocuses ─────────────────────────────────────────────────────
    focuses = output.get("dispute_focuses") or []
    for i, df in enumerate(focuses):
        dfid = df.get("id", f"focus_{i}")
        label = df.get("content", "")[:40]
        add_node(dfid, label, "DisputeFocus", "JudicialEntity", 0,
                 f"类型: {df.get('focus_type', '')}<br>案号: {df.get('case_number', '')}",
                 extra={
                     "entitySourceId": df.get("id") or df.get("focus_id") or dfid,
                     "entityStableId": df.get("stable_id") or "",
                 })
        case_num = df.get("case_number", "")
        if case_num and case_num in cn_to_cc:
            add_edge(cn_to_cc[case_num], dfid, "争议焦点")
        elif court_cases:
            add_edge(first_cc_id, dfid, "争议焦点")

    # ── Relations — 显式关系边 ──────────────────────────────────────────
    rels = output.get("relations") or []
    for r in rels:
        src = r.get("source_id", "")
        tgt = r.get("target_id", "")
        rtype = r.get("relation_type", "")
        rlabel = r.get("label", rtype)
        if src and tgt:
            source_id = cn_to_cc.get(src, src)
            target_id = cn_to_cc.get(tgt, tgt)
            add_edge(str(source_id), str(target_id), rlabel, {
                "relation_type": rtype,
                "edge_type": "explicit",
                "is_derived": False,
                "sourceRef": src,
                "targetRef": tgt,
            })

    derived_rels = output.get("derived_relations") or []
    for r in derived_rels:
        src = r.get("source_id", "")
        tgt = r.get("target_id", "")
        rtype = r.get("relation_type", "")
        rlabel = r.get("label", rtype)
        if src and tgt:
            source_id = cn_to_cc.get(src, src)
            target_id = cn_to_cc.get(tgt, tgt)
            add_edge(str(source_id), str(target_id), rlabel, {
                "relation_type": rtype,
                "edge_type": "derived",
                "is_derived": True,
                "sourceRef": src,
                "targetRef": tgt,
                "dashes": [6, 4],
                "color": {"color": "#6366f1", "highlight": "#4338ca", "hover": "#4338ca", "opacity": 0.82},
                "font": {"size": 10, "color": "#4338ca", "strokeWidth": 2, "strokeColor": "#fff"},
            })

    # ── CaseSummary — 如果有多个审级，优先关联到终审案 ──────────────────
    cs = output.get("case_summary") or {}
    summary_text = cs.get("key_facts", cs.get("disputed_issues", "案件摘要"))
    if summary_text:
        if isinstance(summary_text, list):
            summary_text = "; ".join(summary_text)
        add_node("summary", summary_text[:60], "CaseSummary", "JudicialEntity", 1,
                 summary_text)
        if court_cases:
            if len(court_cases) == 1:
                add_edge(first_cc_id, "summary", "审理")
            else:
                # Multiple instances: try to find final (终审) instance
                summary_target = first_cc_id
                for i, cc in enumerate(court_cases):
                    tl = cc.get("trial_level", "")
                    if tl in ("second_instance", "retrial", "final"):
                        summary_target = f"cc_{i}"
                        break
                add_edge(summary_target, "summary", "审理")

    return {"nodes": nodes, "edges": edges}


# ── Ontology Colors (mirrors admin_instances.html constants) ────────────────

ROOT_COLORS = {
    "LegalNorm": {"bg": "#2980b9", "border": "#1a5276"},
    "JudicialEntity": {"bg": "#d35400", "border": "#a04000"},
    "LegalSubject": {"bg": "#27ae60", "border": "#1e8449"},
    "Person": {"bg": "#16a085", "border": "#0e6655"},
}

ADMIN_SHAPES = {
    "GuidingCase": "hexagon",
    "CourtCase": "box",
    "CaseType": "diamond",
    "LegalProvision": "hexagon",
    "LegalProvisionElement": "square",
    "LegalSubject": "ellipse",
    "Evidence": "database",  # 圆柱体，比 diamond 紧凑
    "Judge": "ellipse",
    "Attorney": "ellipse",
    "JudgmentResult": "box",
    "CaseSummary": "box",
    "Fact": "ellipse",
    "DisputeFocus": "star",
}


# ── Evaluation ──────────────────────────────────────────────────────────────

def evaluate_output(output: Dict[str, Any], row_id: str) -> Dict[str, Any]:
    """Lightweight evaluation — scores 0-100."""
    issues = []
    score = 100.0

    gc = output.get("guiding_case") or output
    for field in ["guiding_case_number", "guiding_case_name", "binding_force"]:
        val = gc.get(field) if isinstance(gc, dict) else output.get(field)
        if not val:
            issues.append(f"{field} 为空")
            score -= 5

    ct = output.get("case_type") or {}
    if not ct.get("category"):
        issues.append("case_type.category 为空")
        score -= 5

    court_cases = output.get("court_cases") or []
    if not court_cases:
        issues.append("court_cases 为空")
        score -= 35
    else:
        for i, cc in enumerate(court_cases):
            if not cc.get("case_number"):
                issues.append(f"court_cases[{i}].case_number 为空")
                score -= 10
            if not cc.get("filing_date"):
                issues.append(f"court_cases[{i}].filing_date 为空")
                score -= 5

    provisions = output.get("legal_provisions") or []
    if not provisions:
        issues.append("legal_provisions 为空")
        score -= 15
    else:
        for i, p in enumerate(provisions):
            if not p.get("article"):
                issues.append(f"legal_provisions[{i}].article 为空")
                score -= 5

    evidence = output.get("evidence") or []
    if not evidence:
        issues.append("evidence 为空")
        score -= 2
    else:
        for i, e in enumerate(evidence):
            if not e.get("admission_status"):
                issues.append(f"evidence[{i}].admission_status 为空")
                score -= 2

    facts = output.get("facts") or []
    if not facts:
        issues.append("facts 为空")
        score -= 12

    dispute_focuses = output.get("dispute_focuses") or []
    if not dispute_focuses:
        issues.append("dispute_focuses 为空")
        score -= 12

    relations = output.get("relations") or []
    if not relations:
        issues.append("relations 为空")
        score -= 14
    elif evidence and not any((r.get("relation_type") == "proves_fact") for r in relations):
        issues.append("relations 缺少 proves_fact")
        score -= 6

    judgment_results = output.get("judgment_results") or []
    if not judgment_results:
        issues.append("judgment_results 为空")
        score -= 3

    if dispute_focuses and judgment_results and not any((r.get("relation_type") == "leads_to") for r in relations):
        issues.append("relations 缺少 leads_to")
        score -= 4

    if provisions and judgment_results and not any((r.get("relation_type") == "judgment_cites") for r in relations):
        issues.append("relations 缺少 judgment_cites")
        score -= 4

    cs = output.get("case_summary") or {}
    if not cs.get("disputed_issues"):
        issues.append("case_summary.disputed_issues 为空")
        score -= 10

    return {
        "row_id": row_id,
        "score": max(0, score),
        "issues": issues,
    }


ENHANCEMENT_TARGET_MAP = {
    "facts": {
        "aliases": ["facts", "事实", "案件事实", "事实认定", "Fact"],
        "label": "事实",
    },
    "dispute_focuses": {
        "aliases": ["dispute_focuses", "争议焦点", "DisputeFocus"],
        "label": "争议焦点",
    },
    "evidence": {
        "aliases": ["evidence", "证据", "Evidence"],
        "label": "证据",
    },
    "judgment_results": {
        "aliases": ["judgment_results", "裁判结果", "JudgmentResult"],
        "label": "裁判结果",
    },
    "legal_provisions": {
        "aliases": ["legal_provisions", "法条", "法律依据", "LegalProvision"],
        "label": "法条依据",
    },
    "relations": {
        "aliases": ["relations", "关系", "relation", "关系边"],
        "label": "关系",
    },
    "matches_element": {
        "aliases": ["matches_element", "事实-要件匹配", "事实要件匹配", "要件匹配", "Fact-LegalProvisionElement"],
        "label": "事实-法条要件匹配",
    },
    "case_summary": {
        "aliases": ["case_summary", "摘要", "争议概括", "CaseSummary"],
        "label": "案件摘要",
    },
}


def _normalize_enhancement_key(name: str) -> Optional[str]:
    text = (name or "").strip()
    if not text:
        return None
    lower = text.lower()
    for key, cfg in ENHANCEMENT_TARGET_MAP.items():
        aliases = [a.lower() for a in cfg["aliases"]]
        if lower == key or lower in aliases:
            return key
        if any(alias in lower for alias in aliases):
            return key
    return None


def _append_enhancement_target(targets: List[Dict[str, str]], key: str, reason: str, priority: str, source: str) -> None:
    if key not in ENHANCEMENT_TARGET_MAP:
        return
    existing = next((item for item in targets if item.get("entity") == key), None)
    candidate = {
        "entity": key,
        "label": ENHANCEMENT_TARGET_MAP[key]["label"],
        "reason": reason,
        "priority": priority,
        "source": source,
    }
    if not existing:
        targets.append(candidate)
        return
    if priority == "high" and existing.get("priority") != "high":
        existing["priority"] = "high"
    if reason and reason not in (existing.get("reason") or ""):
        existing["reason"] = f"{existing.get('reason', '')}；{reason}".strip("；")


def build_enhancement_targets(
    json_result: Dict[str, Any],
    quality_result: Optional[Dict[str, Any]] = None,
    ontology_eval: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    targets: List[Dict[str, str]] = []
    relations = json_result.get("relations") or []

    for key in ("dispute_focuses", "evidence", "relations", "legal_provisions", "judgment_results", "facts"):
        value = json_result.get(key)
        if isinstance(value, list) and not value:
            _append_enhancement_target(targets, key, "初次解析为空", "high", "initial_parse")
        if key == "case_summary" and isinstance(value, dict) and not value.get("disputed_issues"):
            _append_enhancement_target(targets, key, "摘要中的争议概括为空", "medium", "initial_parse")

    if (json_result.get("facts") or []) and (json_result.get("legal_provision_elements") or []):
        has_matches = any(
            isinstance(rel, dict) and str(rel.get("relation_type") or "").strip() == "matches_element"
            for rel in relations
        )
        if not has_matches:
            _append_enhancement_target(
                targets,
                "matches_element",
                "已有事实与法条要件，但缺少显式的事实-法条要件匹配关系",
                "high",
                "initial_parse",
            )

    if isinstance(quality_result, dict):
        for issue in quality_result.get("issues") or []:
            name = issue.get("entity") or issue.get("field") or issue.get("target") or ""
            target = _normalize_enhancement_key(name or issue.get("msg", ""))
            if not target:
                continue
            severity = (issue.get("severity") or "").lower()
            priority = "high" if severity in {"critical", "major"} else "medium"
            reason = issue.get("msg") or issue.get("description") or "质量分析提示该部分薄弱"
            _append_enhancement_target(targets, target, reason, priority, "quality")

    if isinstance(ontology_eval, dict):
        parsing_eval = ontology_eval.get("parsing_evaluation") or {}
        ontology_coverage = ontology_eval.get("ontology_coverage") or {}

        for issue in parsing_eval.get("issues") or []:
            target = _normalize_enhancement_key(
                issue.get("field") or issue.get("field_path") or issue.get("entity") or issue.get("target") or issue.get("msg", "")
            )
            if not target:
                continue
            severity = (issue.get("severity") or "").lower()
            priority = "high" if severity in {"critical", "major", "high"} else "medium"
            reason = issue.get("msg") or issue.get("description") or "本体评估提示该部分待补充"
            _append_enhancement_target(targets, target, reason, priority, "ontology_eval")

        for item in ontology_coverage.get("uncovered") or []:
            target = _normalize_enhancement_key(item.get("entity") or item.get("relation") or item.get("detail", ""))
            if not target:
                continue
            detail = item.get("detail") or item.get("relation") or "本体未覆盖"
            _append_enhancement_target(targets, target, detail, "high", "ontology_uncovered")

        for elem in parsing_eval.get("uncovered_critical_elements") or []:
            target = _normalize_enhancement_key(elem)
            if target:
                _append_enhancement_target(targets, target, "缺失核心要素", "high", "ontology_critical")

    priority_order = {"high": 0, "medium": 1, "low": 2}
    targets.sort(key=lambda item: (priority_order.get(item.get("priority", "medium"), 1), item.get("entity", "")))
    return targets


def _make_enhancement_prompt_preview(targets: List[Dict[str, str]]) -> str:
    if not targets:
        return "本轮未识别到明确补强目标，将默认关注争议焦点、证据和关系闭环。"
    labels = [item.get("label") or item.get("entity") or "" for item in targets]
    visible_labels = [label for label in labels[:8] if label]
    extra_count = max(len(labels) - len(visible_labels), 0)
    suffix = f" 等{extra_count}项" if extra_count > 0 else ""
    return f"本轮仅专项补强：{'、'.join(visible_labels)}{suffix}；保留已有正确内容，不重写整份结果。"


def build_enhancement_prompt(
    base_prompt: str,
    llm_input: str,
    json_result: Dict[str, Any],
    quality_result: Optional[Dict[str, Any]],
    ontology_eval: Optional[Dict[str, Any]],
    targets: List[Dict[str, str]],
) -> Dict[str, str]:
    prompt_preview = _make_enhancement_prompt_preview(targets)
    target_entities = {item.get("entity") for item in targets}
    target_lines = "\n".join(
        f"- {item.get('label') or item.get('entity')}: {item.get('reason') or '待补强'}"
        for item in targets
    ) or "- 争议焦点: 初次解析覆盖不足\n- 证据: 初次解析覆盖不足\n- 关系: 需要补齐关系闭环"

    quality_issues = []
    if isinstance(quality_result, dict):
        for issue in (quality_result.get("issues") or [])[:8]:
            quality_issues.append(f"- {(issue.get('msg') or issue.get('description') or '质量问题')}")
    quality_summary = "\n".join(quality_issues) or "- 暂无结构化质量问题摘要"

    uncovered_lines = []
    if isinstance(ontology_eval, dict):
        oc = ontology_eval.get("ontology_coverage") or {}
        pe = ontology_eval.get("parsing_evaluation") or {}
        for item in (oc.get("uncovered") or [])[:8]:
            label = item.get("entity") or item.get("relation") or "未覆盖项"
            detail = item.get("detail") or ""
            uncovered_lines.append(f"- {label} {detail}".strip())
        for elem in (pe.get("uncovered_critical_elements") or [])[:5]:
            uncovered_lines.append(f"- 核心缺失: {elem}")
    uncovered_summary = "\n".join(uncovered_lines) or "- 暂无本体未覆盖摘要"

    special_instructions = []
    if "matches_element" in target_entities:
        special_instructions.extend([
            "- 若某个事实能够明确对应某个法条构成要件，请在 enhancement_payload.relations 中显式输出 relation_type=\"matches_element\"。",
            "- matches_element 的 source_id 必须使用 facts 中对应事实的 id，target_id 必须使用 legal_provision_elements 中对应要件的 id。",
            "- element_of_provision 属于后处理自动补图关系，不要输出到 enhancement_payload.relations。",
            "- 仅在原文和初次解析已有足够依据时补充 matches_element，不要为了补关系而臆造。",
        ])
    special_instruction_block = "\n".join(special_instructions) or "- 本轮无额外专项关系指令。"

    enhancement_prompt = f"""{base_prompt}

## 现在进入专项二次解析模式
你已经得到一版初次解析结果。当前任务不是重写整份输出，而是只对覆盖不足的部分做定向补强。

### 工作要求
1. 保留初次解析中已经正确且完整的内容，不要整体改写。
2. 仅针对以下目标进行补充：实体缺失、关键字段缺失、关系闭环不足、本体未覆盖项。
3. 如果原文没有足够依据，不要臆造。
4. 输出必须是一个 JSON object。
5. 顶层仅允许包含这些键：
   - enhancement_payload
   - summary
   - notes
6. enhancement_payload 只允许包含需要补充的局部键，可选：
   - facts
   - dispute_focuses
   - evidence
   - judgment_results
   - legal_provisions
   - legal_provision_elements
   - relations
   - case_summary
7. 如果某部分无需补充，就不要输出该键。

### 本轮重点补强目标
{target_lines}

### 本轮专项关系指令
{special_instruction_block}

### 初次解析结果
{json.dumps(json_result, ensure_ascii=False, indent=2)[:16000]}

### 质量问题摘要
{quality_summary}

### 本体覆盖缺口摘要
{uncovered_summary}

### 原始输入
{llm_input[:18000]}
"""
    return {
        "prompt": enhancement_prompt,
        "prompt_preview": prompt_preview,
    }


def normalize_enhancement_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    allowed = {"facts", "dispute_focuses", "evidence", "judgment_results", "legal_provisions", "legal_provision_elements", "relations", "case_summary"}
    normalized: Dict[str, Any] = {}
    for key in allowed:
        if key not in payload:
            continue
        value = payload.get(key)
        if key == "case_summary":
            if isinstance(value, dict):
                normalized[key] = value
            continue
        if isinstance(value, list):
            normalized[key] = value
    return normalized


def merge_enhancement_payload(base_output: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base_output or {})
    payload = align_enhancement_payload(base_output, payload)
    for key, value in payload.items():
        if key == "case_summary":
            current = merged.get("case_summary") or {}
            if isinstance(current, dict) and isinstance(value, dict):
                current.update({k: v for k, v in value.items() if v not in (None, "", [], {})})
                merged[key] = current
            continue
        if key == "relations":
            merged[key] = _merge_relation_list(merged.get(key) or [], value if isinstance(value, list) else [])
            continue
        current_list = merged.get(key) or []
        if not isinstance(current_list, list):
            current_list = []
        if isinstance(value, list):
            merged[key] = _merge_entity_list(key, current_list, value)
    merged = fill_empty_provision_content(merged)
    merged = enrich_graph_output(merged)
    return merged


def _stable_dump(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except TypeError:
        return json.dumps(str(value), ensure_ascii=False)


def _pick_first_non_empty(item: Dict[str, Any], keys: List[str]) -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            return str(value).strip()
    return ""


def _entity_identity(entity_type: str, item: Any) -> str:
    if not isinstance(item, dict):
        return _stable_dump(item)
    stable_id = _pick_first_non_empty(item, ["stable_id", "evidence_id"])
    if stable_id:
        return stable_id
    return _stable_dump(_entity_signature_payload(entity_type, item))


def _relation_identity(item: Any) -> str:
    if not isinstance(item, dict):
        return _stable_dump(item)
    source_id = str(item.get("source_id") or "").strip()
    target_id = str(item.get("target_id") or "").strip()
    relation_type = str(item.get("relation_type") or "").strip() or "unknown"
    if source_id or target_id:
        return f"{source_id}|{target_id}|{relation_type}"
    return _stable_dump(item)


def _build_changed_enhancement_payload(
    old_json: Dict[str, Any],
    enhancement_payload: Dict[str, Any],
) -> Dict[str, Any]:
    changed_payload: Dict[str, Any] = {}

    for key, value in enhancement_payload.items():
        if key == "case_summary":
            old_summary = old_json.get("case_summary") or {}
            if not isinstance(value, dict):
                continue
            changed_summary = {
                field: field_value
                for field, field_value in value.items()
                if field_value not in (None, "", [], {})
                and (not isinstance(old_summary, dict) or old_summary.get(field) != field_value)
            }
            if changed_summary:
                changed_payload[key] = changed_summary
            continue

        if not isinstance(value, list):
            continue

        old_items = old_json.get(key) or []
        if not isinstance(old_items, list):
            old_items = []

        identity_builder = _relation_identity if key == "relations" else (lambda item, entity_key=key: _entity_identity(entity_key, item))
        old_lookup = {
            identity_builder(item): (_stable_dump(item) if key == "relations" else _stable_dump(_entity_signature_payload(key, item)))
            for item in old_items
        }

        changed_items = []
        for item in value:
            identity = identity_builder(item)
            payload_dump = _stable_dump(item) if key == "relations" else _stable_dump(_entity_signature_payload(key, item))
            if identity not in old_lookup or old_lookup[identity] != payload_dump:
                changed_items.append(item)

        if changed_items:
            changed_payload[key] = changed_items

    return changed_payload


def compute_enhancement_delta(
    old_json: Dict[str, Any],
    enhancement_payload: Dict[str, Any],
    new_json: Dict[str, Any],
) -> Dict[str, Any]:
    entity_keys = ("facts", "dispute_focuses", "evidence", "judgment_results", "legal_provisions", "legal_provision_elements")
    entity_added_counts: Counter[str] = Counter()
    entity_updated_counts: Counter[str] = Counter()

    for key in entity_keys:
        old_items = old_json.get(key) or []
        payload_items = enhancement_payload.get(key) or []
        if not isinstance(old_items, list) or not isinstance(payload_items, list):
            continue
        old_lookup = {
            _entity_identity(key, item): _stable_dump(_entity_signature_payload(key, item))
            for item in old_items
        }
        for item in payload_items:
            identity = _entity_identity(key, item)
            payload_dump = _stable_dump(_entity_signature_payload(key, item))
            if identity in old_lookup:
                if old_lookup[identity] != payload_dump:
                    entity_updated_counts[key] += 1
            else:
                entity_added_counts[key] += 1

    relation_added_counts: Counter[str] = Counter()
    relation_updated_counts: Counter[str] = Counter()
    old_relations = old_json.get("relations") or []
    payload_relations = enhancement_payload.get("relations") or []
    if isinstance(old_relations, list) and isinstance(payload_relations, list):
        old_relation_lookup = {
            _relation_identity(rel): _stable_dump(rel)
            for rel in old_relations
            if isinstance(rel, dict)
        }
        for rel in payload_relations:
            if not isinstance(rel, dict):
                continue
            relation_type = str(rel.get("relation_type") or "").strip() or "unknown"
            identity = _relation_identity(rel)
            payload_dump = _stable_dump(rel)
            if identity in old_relation_lookup:
                if old_relation_lookup[identity] != payload_dump:
                    relation_updated_counts[relation_type] += 1
            else:
                relation_added_counts[relation_type] += 1

    return {
        "entity_counts": {
            "added": dict(entity_added_counts),
            "updated": dict(entity_updated_counts),
        },
        "relation_type_counts": {
            "added": dict(relation_added_counts),
            "updated": dict(relation_updated_counts),
        },
        "updated_fields": [key for key in ("case_summary",) if new_json.get(key) != old_json.get(key)],
        "notes": [],
    }


def parse_enhancement(
    raw_text: str,
    json_result: Dict[str, Any],
    row_id: str = "manual_enhance",
    quality_result: Optional[Dict[str, Any]] = None,
    ontology_eval: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    row = build_row_from_text(raw_text)
    base_prompt = load_prompt(row.get("case_type", ""))
    llm_input = build_llm_input(row)
    targets = build_enhancement_targets(json_result, quality_result, ontology_eval)
    prompt_data = build_enhancement_prompt(base_prompt, llm_input, json_result, quality_result, ontology_eval, targets)
    enhancement_raw = call_llm(prompt_data["prompt"], llm_input)

    enhancement_payload = normalize_enhancement_payload(
        enhancement_raw.get("enhancement_payload") or enhancement_raw.get("payload") or enhancement_raw
    )
    enhancement_payload = align_enhancement_payload(json_result, enhancement_payload)
    changed_enhancement_payload = _build_changed_enhancement_payload(json_result, enhancement_payload)
    enhanced_json_result = merge_enhancement_payload(json_result, enhancement_payload)
    delta = compute_enhancement_delta(json_result, enhancement_payload, enhanced_json_result)
    summary = enhancement_raw.get("summary") or "已生成专项补强结果。"
    notes = enhancement_raw.get("notes") or []

    return {
        "row_id": row_id,
        "targets": targets,
        "prompt_preview": prompt_data["prompt_preview"],
        "enhancement_payload": enhancement_payload,
        "changed_enhancement_payload": changed_enhancement_payload,
        "enhanced_json_result": enhanced_json_result,
        "delta": delta,
        "summary": summary,
        "notes": notes,
    }


# ── Main Entry Point ───────────────────────────────────────────────────────

def parse_text(raw_text: str) -> Dict[str, Any]:
    """
    Full pipeline: text → row dict → LLM input → LLM → post-process → KG convert.
    Returns everything the frontend needs.
    """
    row = build_row_from_text(raw_text)
    prompt = load_prompt(row.get("case_type", ""))
    llm_input = build_llm_input(row)

    print(f"  LLM input: {len(llm_input)} chars", flush=True)
    t0 = time.time()
    output = call_llm(prompt, llm_input)
    if should_retry_with_fallback_prompt(row, output):
        print("  admin empty-output fallback -> legacy prompt", flush=True)
        output = call_llm(load_legacy_fallback_prompt(), llm_input)
    elapsed = time.time() - t0

    output = enforce_case_level(row, output)
    output = enforce_source_url(row, output)
    output = fill_empty_provision_content(output)
    output = enrich_graph_output(output)

    case_name = extract_case_name(output)
    eval_result = evaluate_output(output, "manual")
    graph = kg_convert(output)

    print(f"  Done in {elapsed:.0f}s score={eval_result['score']:.0f}", flush=True)

    return {
        "row_id": f"manual_{int(time.time())}",
        "json_result": output,
        "nodes": graph["nodes"],
        "edges": graph["edges"],
        "score": eval_result["score"],
        "issues": eval_result["issues"],
        "case_name": case_name,
    }
