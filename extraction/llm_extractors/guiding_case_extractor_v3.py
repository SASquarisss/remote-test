"""
Guiding Case Extractor V3 - Parallel version
Runs multiple items concurrently with immediate per-item output.
"""
import concurrent.futures
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

_HERMES_ENV = Path.home() / ".hermes" / ".env"
if _HERMES_ENV.exists():
    load_dotenv(_HERMES_ENV)


def load_config() -> Dict[str, Any]:
    config_path = REPO_ROOT / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_prompt(version: str = "v3") -> str:
    if version == "v3":
        prompt_path = REPO_ROOT / "scripts/prompts/guiding_case_ontology_aligned_v3.txt"
    elif version == "v2":
        prompt_path = REPO_ROOT / "extraction/llm_extractors/prompt_v2.txt"
    else:
        prompt_path = REPO_ROOT / f"extraction/llm_extractors/prompt_{version}.txt"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def load_csv(path: str) -> List[Dict[str, str]]:
    HEADER = [
        "id", "web_name", "web_url", "case_type", "storage_no", "court_name",
        "key_words", "trial_procedure", "trial_year", "case_level",
        "basic_facts", "judgment_reason", "judgment_essence",
        "related_info", "related_law", "related_judgment_body",
        "create_time", "update_time", "md5_value", "judgment_mean", "dt"
    ]
    EXPECTED = len(HEADER)

    with open(path, "r", encoding="utf-8-sig") as f:
        raw = f.read()
    lines = raw.splitlines()
    if not lines:
        return []
    sample = "\n".join(lines[:5])
    delim = "\t" if sample.count("\t") > sample.count(",") else ","

    reader = csv.reader(lines, delimiter=delim, quotechar='"')
    rows = []
    for idx, parts in enumerate(reader):
        if idx == 0:
            continue
        if len(parts) < EXPECTED:
            parts += [""] * (EXPECTED - len(parts))
        elif len(parts) > EXPECTED:
            parts = parts[:EXPECTED]
        rows.append(dict(zip(HEADER, parts)))
    return rows


def enforce_case_level(row: Dict[str, str], output: Dict[str, Any]) -> Dict[str, Any]:
    """Enforce case_level and binding_force from CSV case_level column (hard override)."""
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
    """Copy web_url from input to output's source_url if output has it empty or generic."""
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
    """Fill empty legal_provision.content with a fallback description."""
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


def build_llm_input(row: Dict[str, str]) -> str:
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
        val = re.sub(r'<[^>]+>', '', val)
        val = val.replace("\\N", "").strip()
        if val:
            lines.append(f"【{label}】\n{val}\n")
    return "\n".join(lines)


def _safe_json_parse(content: str) -> dict:
    """容错 JSON 解析：LLM 输出被截断时尝试提取最后一个完整 JSON 对象"""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # 尝试截取最后一个完整的 JSON 对象
        start = content.find('{')
        if start == -1:
            raise
        depth, end = 0, start
        for i in range(start, len(content)):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
            if depth == 0 and i > start:
                end = i + 1
                break
        if end > start:
            return json.loads(content[start:end])
        raise


def call_llm(prompt: str, text: str, config: Dict[str, Any]) -> Dict[str, Any]:
    extraction_cfg = config.get("extraction", {})
    provider = extraction_cfg.get("llm_provider", "deepseek")
    model = extraction_cfg.get("llm_model", "deepseek-v4-pro")
    max_tokens = extraction_cfg.get("max_tokens", 8192)
    temperature = extraction_cfg.get("temperature", 0.1)
    base_url = extraction_cfg.get("base_url", "https://api.deepseek.com/v1")

    from openai import OpenAI
    api_key = os.environ.get("DEEPSEEK_API_KEY") or extraction_cfg.get("api_key")
    if not api_key:
        raise RuntimeError("API key not found")
    client = OpenAI(api_key=api_key, base_url=base_url)

    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
                timeout=180,
            )
            content = resp.choices[0].message.content or "{}"
            return _safe_json_parse(content)
        except Exception as e:
            print(f"  [retry {attempt+1}] {e}")
            time.sleep(2 ** attempt)
    raise RuntimeError("All 3 attempts failed")


def evaluate_output(output: Dict[str, Any], row_id: str) -> Dict[str, Any]:
    issues = []
    score = 100.0

    gc = output.get("guiding_case") or output
    for field in ["guiding_case_number", "guiding_case_name", "binding_force"]:
        val = gc.get(field) if isinstance(gc, dict) else output.get(field)
        if not val:
            issues.append(f"{field} 为空")
            score -= 5
    storage_no = gc.get("storage_no") if isinstance(gc, dict) else output.get("storage_no")
    if not storage_no:
        issues.append("storage_no 为空")
        score -= 3

    ct = output.get("case_type") or {}
    if not ct.get("category"):
        issues.append("case_type.category 为空")
        score -= 5

    court_cases = output.get("court_cases") or []
    if not court_cases:
        issues.append("court_cases 为空或缺失")
        score -= 35
    else:
        for i, cc in enumerate(court_cases):
            if not cc.get("case_number"):
                issues.append(f"court_cases[{i}].case_number 为空")
                score -= 10
            if not cc.get("filing_date"):
                issues.append(f"court_cases[{i}].filing_date 为空")
                score -= 5

    judges = output.get("judges") or []
    if not judges:
        issues.append("judges 为空")
        score -= 0

    attorneys = output.get("attorneys") or []
    if not attorneys:
        issues.append("attorneys 为空")
        score -= 0

    prosecutors_info = output.get("prosecutors") or []
    if not prosecutors_info and ct.get("category") == "criminal":
        issues.append("prosecutors 为空（刑事应包含公诉信息）")
        score -= 0

    trial_orgs = output.get("trial_organizations") or []
    if not trial_orgs:
        issues.append("trial_organizations 为空")
        score -= 0

    provisions = output.get("legal_provisions") or []
    if not provisions:
        issues.append("legal_provisions 为空或缺失")
        score -= 15
    else:
        for i, p in enumerate(provisions):
            if not p.get("article"):
                issues.append(f"legal_provisions[{i}].article 为空")
                score -= 5
            if not p.get("content"):
                issues.append(f"legal_provisions[{i}].content 为空")
                score -= 3

    evidence = output.get("evidence") or []
    if not evidence:
        issues.append("evidence 为空")
        score -= 2

    judgment_results = output.get("judgment_results") or []
    if not judgment_results:
        issues.append("judgment_results 为空")
        score -= 3

    cs = output.get("case_summary") or {}
    if not cs.get("disputed_issues"):
        issues.append("case_summary.disputed_issues 为空")
        score -= 10
    if not cs.get("conclusion"):
        issues.append("case_summary.conclusion 为空")
        score -= 10
    if not cs.get("key_facts"):
        issues.append("case_summary.key_facts 为空")
        score -= 5

    return {
        "row_id": row_id,
        "score": max(0, score),
        "issues": issues,
        "court_case_count": len(court_cases),
        "judge_count": len(judges),
        "attorney_count": len(attorneys),
        "provision_count": len(provisions),
        "evidence_count": len(evidence),
    }


def process_one(idx: int, row: Dict[str, str], prompt: str, config: Dict[str, Any]) -> Dict[str, Any]:
    row_id = row.get("id", f"row_{idx}")
    text = build_llm_input(row)
    print(f"[{idx}] id={row_id} ({len(text)} chars)...", flush=True)
    t0 = time.time()
    try:
        output = call_llm(prompt, text, config)
        elapsed = time.time() - t0
        # Post-processing: enforce case_level/binding_force from CSV
        output = enforce_case_level(row, output)
        # Post-processing: copy web_url to source_url
        output = enforce_source_url(row, output)
        # Post-processing: fill empty provision content
        output = fill_empty_provision_content(output)
        eval_result = evaluate_output(output, row_id)
        print(f"  {elapsed:.0f}s score={eval_result['score']:.0f} cases={eval_result['court_case_count']} provisions={eval_result['provision_count']}", flush=True)
        return {
            "row_id": row_id,
            "input": {k: row.get(k, "") for k in ["id", "web_name", "case_type", "storage_no"]},
            "output": output,
            "eval": eval_result,
        }
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  ERROR after {elapsed:.0f}s: {e}", flush=True)
        return {
            "row_id": row_id,
            "input": {k: row.get(k, "") for k in ["id", "web_name", "case_type", "storage_no"]},
            "output": None,
            "eval": {"error": str(e)},
        }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/raw/test_20_new.csv")
    parser.add_argument("--output", default="data_lake/extracted_v3.jsonl")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--prompt-version", default=None)
    parser.add_argument("--prompt-path", default=None,
                        help="直接指定 prompt 文件路径（优先级高于 --prompt-version）")
    args = parser.parse_args()

    config = load_config()
    if args.prompt_path:
        prompt_path = REPO_ROOT / args.prompt_path
        prompt = prompt_path.read_text(encoding="utf-8")
        print(f"Using prompt path: {args.prompt_path} ({len(prompt)} chars)", flush=True)
    else:
        prompt = load_prompt(args.prompt_version or "v3")

    input_path = REPO_ROOT / args.input
    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = load_csv(str(input_path))
    if args.limit > 0:
        rows = rows[args.start:args.start + args.limit]
    else:
        rows = rows[args.start:]

    print(f"Processing {len(rows)} rows (start={args.start}, limit={args.limit or 'all'}) with {args.workers} workers", flush=True)

    # Clear output file
    with open(output_path, "w", encoding="utf-8") as f:
        pass

    success = 0
    total_score = 0.0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_one, args.start + idx, row, prompt, config): (args.start + idx, row)
            for idx, row in enumerate(rows)
        }
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            # Write immediately
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
            if result["output"] is not None and "error" not in result.get("eval", {}):
                success += 1
                total_score += result["eval"].get("score", 0)

    total = len(rows)
    avg = total_score / max(success, 1)
    print(f"\nDone. {success}/{total} ({100*success/total:.0f}%) Avg score: {avg:.1f}", flush=True)


if __name__ == "__main__":
    main()
