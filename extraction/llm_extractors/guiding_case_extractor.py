"""
Guiding Case LLM Extractor (V2)
Fixes:
- max_tokens 4096 -> 8192 (in config.yaml)
- Multi-case-number extraction from related_info / basic_facts
- Non-standard role fallback to "other" + original name
"""
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def load_config() -> Dict[str, Any]:
    config_path = REPO_ROOT / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Auto-load env from ~/.hermes/.env if present
from dotenv import load_dotenv
_HERMES_ENV = Path.home() / ".hermes" / ".env"
if _HERMES_ENV.exists():
    load_dotenv(_HERMES_ENV)


def load_prompt(version: str = "v2") -> str:
    prompt_path = REPO_ROOT / f"extraction/llm_extractors/prompt_{version}.txt"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def robust_parse_tsv(path: Path) -> List[Dict[str, str]]:
    """Reuse robust parser from parse_guiding_cases.py"""
    HEADER = [
        "id", "web_name", "web_url", "case_type", "storage_no", "court_name",
        "key_words", "trial_procedure", "trial_year", "case_level",
        "basic_facts", "judgment_reason", "judgment_essence",
        "related_info", "related_law", "related_judgment_body",
        "create_time", "update_time", "md5_value", "judgment_mean", "dt"
    ]
    EXPECTED_COLS = len(HEADER)

    raw_lines: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            raw_lines.append(line.rstrip("\n\r"))

    merged: List[str] = []
    current = ""
    for line in raw_lines:
        stripped = line.lstrip()
        if stripped and stripped.split(None, 1)[0].isdigit():
            if current:
                merged.append(current)
            current = line
        else:
            current += "\n" + line
    if current:
        merged.append(current)

    rows: List[Dict[str, str]] = []
    for line in merged:
        parts = line.split("\t")
        if len(parts) < EXPECTED_COLS:
            parts += [""] * (EXPECTED_COLS - len(parts))
        elif len(parts) > EXPECTED_COLS:
            parts = parts[:EXPECTED_COLS - 1] + ["\t".join(parts[EXPECTED_COLS - 1:])]
        rows.append(dict(zip(HEADER, parts)))
    return rows


def build_llm_input(row: Dict[str, str]) -> str:
    """Compose the text block sent to LLM."""
    fields = [
        ("web_name", "案例来源"),
        ("case_type", "案由分类"),
        ("storage_no", "入库编号"),
        ("court_name", "审理法院"),
        ("trial_procedure", "审判程序"),
        ("trial_year", "裁判年份"),
        ("case_level", "审级"),
        ("basic_facts", "基本案情"),
        ("judgment_reason", "裁判理由"),
        ("judgment_essence", "裁判要旨"),
        ("related_info", "相关案情/关联案件"),
        ("related_law", "相关法条"),
        ("related_judgment_body", "关联裁判文书"),
    ]
    lines = []
    for key, label in fields:
        val = row.get(key, "") or ""
        # Strip HTML tags for cleaner input
        val = re.sub(r'<[^>]+>', '', val)
        val = val.replace("\\N", "").strip()
        if val:
            lines.append(f"【{label}】\n{val}\n")
    return "\n".join(lines)


def call_llm(prompt: str, text: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Call LLM API with retry logic."""
    extraction_cfg = config.get("extraction", {})
    provider = extraction_cfg.get("llm_provider", "openai")
    model = extraction_cfg.get("llm_model", "gpt-4-turbo-preview")
    max_tokens = extraction_cfg.get("max_tokens", 8192)
    temperature = extraction_cfg.get("temperature", 0.1)

    system_msg = prompt
    user_msg = text

    if provider == "openai":
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY") or extraction_cfg.get("api_key")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not found in env or config")
        client = OpenAI(api_key=api_key)

        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    timeout=300,
                )
                content = resp.choices[0].message.content or "{}"
                return json.loads(content)
            except Exception as e:
                print(f"  Attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)
        raise RuntimeError("All 3 attempts failed")

    elif provider == "deepseek":
        from openai import OpenAI
        api_key = os.environ.get("DEEPSEEK_API_KEY") or extraction_cfg.get("api_key")
        base_url = extraction_cfg.get("base_url", "https://api.deepseek.com/v1")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not found in env or config")
        client = OpenAI(api_key=api_key, base_url=base_url)

        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                    timeout=300,
                )
                content = resp.choices[0].message.content or "{}"
                return json.loads(content)
            except Exception as e:
                print(f"  Attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)
        raise RuntimeError("All 3 attempts failed")

    elif provider in ("kimi", "moonshot"):
        from openai import OpenAI
        api_key = os.environ.get("KIMI_API_KEY") or extraction_cfg.get("api_key")
        base_url = extraction_cfg.get("base_url", "https://api.kimi.com/coding/v1")
        if not api_key:
            raise RuntimeError("KIMI_API_KEY not found in env or config")
        client = OpenAI(api_key=api_key, base_url=base_url)

        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                content = resp.choices[0].message.content or "{}"
                return json.loads(content)
            except Exception as e:
                print(f"  Attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)
        raise RuntimeError("All 3 attempts failed")

    elif provider == "anthropic":
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY") or extraction_cfg.get("api_key")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not found in env or config")
        client = anthropic.Anthropic(api_key=api_key)

        for attempt in range(3):
            try:
                resp = client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_msg,
                    messages=[{"role": "user", "content": user_msg}],
                )
                content = resp.content[0].text if resp.content else "{}"
                return json.loads(content)
            except Exception as e:
                print(f"  Attempt {attempt + 1} failed: {e}")
                time.sleep(2 ** attempt)
        raise RuntimeError("All 3 attempts failed")

    else:
        raise RuntimeError(f"Unsupported provider: {provider}")


def evaluate_output(output: Dict[str, Any], row_id: str) -> Dict[str, Any]:
    """Quick automated evaluation."""
    issues = []
    score = 100.0

    court_cases = output.get("court_cases") or []
    if not court_cases:
        issues.append("court_cases 为空或缺失")
        score -= 35
    else:
        for i, cc in enumerate(court_cases):
            if not cc.get("case_number"):
                issues.append(f"court_cases[{i}].case_number 为空")
                score -= 10
            # Check parties
            parties = cc.get("parties") or []
            for j, p in enumerate(parties):
                if not p.get("role_code"):
                    issues.append(f"court_cases[{i}].parties[{j}].role_code 为空 (名称={p.get('name')})")
                    score -= 5
                if not p.get("role_name"):
                    issues.append(f"court_cases[{i}].parties[{j}].role_name 为空 (名称={p.get('name')})")
                    score -= 2

    # Check required top-level fields
    for field in ["guiding_case_number", "guiding_case_name", "binding_force"]:
        if not output.get(field):
            issues.append(f"{field} 为空")
            score -= 5

    # Check case_type
    ct = output.get("case_type") or {}
    if not ct.get("category"):
        issues.append("case_type.category 为空")
        score -= 5

    return {
        "row_id": row_id,
        "score": max(0, score),
        "issues": issues,
        "court_case_count": len(court_cases),
        "party_count": sum(len(cc.get("parties") or []) for cc in court_cases),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data_samples/guiding_cases_raw.csv")
    parser.add_argument("--output", default="data_lake/extracted_guiding_cases.jsonl")
    parser.add_argument("--limit", type=int, default=0, help="0 = all")
    parser.add_argument("--prompt-version", default="v2")
    parser.add_argument("--start", type=int, default=0, help="Start index")
    parser.add_argument("--append", action="store_true", help="Append to output file instead of overwrite")
    args = parser.parse_args()

    config = load_config()
    prompt = load_prompt(args.prompt_version)

    input_path = REPO_ROOT / args.input
    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = robust_parse_tsv(input_path)
    # Skip header-like row if present
    if rows and not rows[0].get("id", "").isdigit():
        rows = rows[1:]

    if args.limit > 0:
        rows = rows[args.start:args.start + args.limit]
    else:
        rows = rows[args.start:]

    print(f"Processing {len(rows)} rows (start={args.start}, limit={args.limit or 'all'})")
    print(f"Config: provider={config['extraction']['llm_provider']}, model={config['extraction']['llm_model']}, max_tokens={config['extraction']['max_tokens']}")

    results = []
    for idx, row in enumerate(rows):
        row_id = row.get("id", f"row_{idx}")
        print(f"\n[{idx + 1}/{len(rows)}] Processing id={row_id} ...")
        text = build_llm_input(row)
        print(f"  Input length: {len(text)} chars")

        try:
            output = call_llm(prompt, text, config)
            eval_result = evaluate_output(output, row_id)
            print(f"  Score: {eval_result['score']:.1f}, Cases: {eval_result['court_case_count']}, Parties: {eval_result['party_count']}")
            if eval_result["issues"]:
                for issue in eval_result["issues"]:
                    print(f"    - {issue}")
            results.append({
                "row_id": row_id,
                "input": {k: row.get(k, "") for k in ["id", "web_name", "case_type", "storage_no"]},
                "output": output,
                "eval": eval_result,
            })
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "row_id": row_id,
                "input": {k: row.get(k, "") for k in ["id", "web_name", "case_type", "storage_no"]},
                "output": None,
                "eval": {"error": str(e)},
            })

    # Write JSONL
    mode = "a" if args.append else "w"
    with open(output_path, mode, encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nDone. Results written to {output_path}")

    # Summary
    success = sum(1 for r in results if r["output"] is not None and "error" not in r.get("eval", {}))
    total = len(results)
    avg_score = sum(r["eval"].get("score", 0) for r in results if "error" not in r.get("eval", {})) / max(success, 1)
    print(f"Success: {success}/{total} ({100*success/total:.0f}%)")
    print(f"Avg score (successful): {avg_score:.1f}")


if __name__ == "__main__":
    main()
