"""Flask API for legal text parsing terminal."""
import json
import os
import re
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

# Ensure backend/ is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parser import (
    parse_text,
    parse_enhancement,
    enrich_graph_output,
    kg_convert,
    extract_case_name,
    evaluate_output,
)

# ── Paths ───────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]
MANUAL_JSONL = REPO_ROOT / "data_lake" / "manual_parsed.jsonl"
EXTRACTED_CANDIDATE_JSONL = REPO_ROOT / "data_lake" / "extracted_candidate_manual_save_v1.jsonl"
CASES_INDEX = REPO_ROOT / "visualization" / "data" / "cases_index.json"
ADMIN_STATIC_DATA = REPO_ROOT / "visualization" / "data" / "admin_instances_data.js"

# ── App ─────────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)


# ── Helpers ─────────────────────────────────────────────────────────────────

def load_cases_index() -> list:
    if CASES_INDEX.exists():
        with open(CASES_INDEX, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_jsonl_records(path: Path) -> dict:
    """Load all records from JSONL into a dict keyed by row_id."""
    records = {}
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    records[rec.get("row_id", "")] = rec
                except json.JSONDecodeError:
                    pass
    return records


def load_manual_records() -> dict:
    return load_jsonl_records(MANUAL_JSONL)


def load_candidate_records() -> dict:
    return load_jsonl_records(EXTRACTED_CANDIDATE_JSONL)


@lru_cache(maxsize=1)
def load_admin_static_bundle() -> dict:
    """Load the legacy admin_instances static bundle from JS assignments."""
    if not ADMIN_STATIC_DATA.exists():
        return {"all_graphs": [], "raw_data": {}}

    text = ADMIN_STATIC_DATA.read_text(encoding="utf-8")
    all_graphs_marker = "window.ALL_GRAPHS ="
    raw_data_marker = "window.RAW_DATA ="
    all_graphs_pos = text.find(all_graphs_marker)
    raw_data_pos = text.find(raw_data_marker)

    if all_graphs_pos == -1 or raw_data_pos == -1 or raw_data_pos <= all_graphs_pos:
        raise ValueError("Failed to parse admin_instances_data.js bundle")

    all_graphs_json = text[all_graphs_pos + len(all_graphs_marker):raw_data_pos].strip()
    raw_data_json = text[raw_data_pos + len(raw_data_marker):].strip()

    if all_graphs_json.endswith(";"):
        all_graphs_json = all_graphs_json[:-1].rstrip()
    if raw_data_json.endswith(";"):
        raw_data_json = raw_data_json[:-1].rstrip()

    return {
        "all_graphs": json.loads(all_graphs_json),
        "raw_data": json.loads(raw_data_json),
    }


def _count_non_empty(items) -> int:
    return len([item for item in (items or []) if item])


def _to_case_category_label(value: str) -> str:
    mapping = {
        "civil": "民事案件",
        "criminal": "刑事案件",
        "administrative": "行政案件",
    }
    return mapping.get(value, value or "")


def _extract_static_case_stats(output: dict) -> dict:
    return {
        "facts": _count_non_empty(output.get("facts")),
        "focuses": _count_non_empty(output.get("dispute_focuses")),
        "relations": _count_non_empty(output.get("relations")),
        "evidence": _count_non_empty(output.get("evidence")),
        "provisions": _count_non_empty(output.get("legal_provisions")),
    }


def _extract_case_meta_from_output(output: dict, source_label: str = "static") -> dict:
    output = output or {}
    case_type = output.get("case_type", {}) or {}

    judgment_years = set()
    publication_years = set()
    trial_levels = set()
    procedures = set()
    case_categories = set()
    case_reasons = set()

    for court_case in output.get("court_cases", []) or []:
        court_case = court_case or {}
        date_value = str(court_case.get("judgment_date") or court_case.get("filing_date") or "")
        match = re.search(r"(\d{4})", date_value)
        if match:
            judgment_years.add(match.group(1))
        if court_case.get("trial_level"):
            trial_levels.add(str(court_case["trial_level"]))
        if court_case.get("trial_procedure"):
            procedures.add(court_case["trial_procedure"])

    publication_date = str(
        (output.get("guiding_case") or {}).get("publication_date")
        or output.get("publication_date")
        or ""
    )
    publication_match = re.search(r"(\d{4})", publication_date)
    if publication_match:
        publication_years.add(publication_match.group(1))

    if case_type.get("category"):
        case_categories.add(_to_case_category_label(case_type["category"]))
    if case_type.get("level1"):
        case_reasons.add(str(case_type["level1"]))
    if case_type.get("level2"):
        case_reasons.add(str(case_type["level2"]))

    return {
        "source": source_label,
        "case_categories": sorted(case_categories),
        "case_reasons": sorted(case_reasons),
        "trial_levels": sorted(trial_levels),
        "procedures": list(procedures),
        "judgment_years": sorted(judgment_years, reverse=True),
        "publication_years": sorted(publication_years, reverse=True),
        # Backward-compatible aliases for older front-end code paths.
        "types": sorted(case_categories | case_reasons),
        "years": sorted(judgment_years | publication_years, reverse=True),
        "stats": _extract_static_case_stats(output),
    }


def _extract_static_case_meta(record: dict, source: str = "static") -> dict:
    output = (record or {}).get("output", {}) or {}
    input_meta = (record or {}).get("input", {}) or {}
    return _extract_case_meta_from_output(output, input_meta.get("web_name") or source)


def _find_static_case_record(row_id: str, version: str | None = None) -> tuple[dict | None, dict | None]:
    bundle = load_admin_static_bundle()
    all_graphs = bundle["all_graphs"]
    raw_data = bundle["raw_data"]

    matched = [item for item in all_graphs if str(item.get("row_id")) == str(row_id)]
    if not matched:
        return None, None

    if version is not None:
        summary = next((item for item in matched if str(item.get("version", 1)) == str(version)), None)
    else:
        summary = sorted(matched, key=lambda item: int(item.get("version", 1)), reverse=True)[0]

    if not summary:
        return None, None

    version_no = int(summary.get("version", 1) or 1)
    key = f"{row_id}__v{version_no}" if version_no > 1 else str(row_id)
    record = raw_data.get(key) or raw_data.get(str(row_id))
    return summary, record


def save_cases_index(index: list):
    CASES_INDEX.parent.mkdir(parents=True, exist_ok=True)
    with open(CASES_INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def append_to_jsonl(record: dict):
    MANUAL_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(MANUAL_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def upsert_jsonl_record(path: Path, key_field: str, record: dict):
    """Merge one record into JSONL by key_field, replacing older versions."""
    existing = []
    key_value = record.get(key_field)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if item.get(key_field) != key_value:
                    existing.append(item)
    existing.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for item in existing:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_save_target_info(target_layer: str) -> tuple[Path, str, str]:
    if target_layer == "extracted_candidate":
        return (
            EXTRACTED_CANDIDATE_JSONL,
            "manual_web_save_candidate",
            "backend/app.py:/api/save(extracted_candidate)",
        )
    return (
        MANUAL_JSONL,
        "manual_web_save",
        "backend/app.py:/api/save(manual)",
    )


def build_save_meta(row_id: str, text: str, json_result: dict, case_name: str, target_layer: str) -> dict:
    case_type = (json_result.get("case_type") or {}).get("category", "")
    prompt_path = Path(REPO_ROOT) / "ontology" / "prompts" / "auto_v5_civil.txt"
    prompt_sha1 = ""
    if prompt_path.exists():
        prompt_sha1 = hashlib.sha1(prompt_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    target_path, batch_label, entrypoint = get_save_target_info(target_layer)
    return {
        "schema_version": "extracted_record_meta_v1",
        "run_started_at": _utc_now_iso(),
        "run_id": f"{target_layer}-save-{row_id}",
        "generator": {
            "extractor": "backend/parser.py",
            "entrypoint": entrypoint,
            "batch_label": batch_label,
        },
        "input": {
            "path": "manual://web-terminal",
            "source": "web_terminal",
            "text_sha1": hashlib.sha1((text or "").encode("utf-8")).hexdigest(),
            "text_length": len(text or ""),
        },
        "output": {
            "path": str(target_path.relative_to(REPO_ROOT)),
        },
        "prompt": {
            "path": str(prompt_path.relative_to(REPO_ROOT)) if prompt_path.exists() else "",
            "version": "manual_web_v2",
            "sha1": prompt_sha1,
            "length": len(prompt_path.read_text(encoding="utf-8")) if prompt_path.exists() else 0,
        },
        "model": {
            "provider": "deepseek",
            "name": "deepseek-chat",
            "base_url": "https://api.deepseek.com/v1",
        },
        "record": {
            "row_id": row_id,
            "row_index": 0,
            "status": "saved",
            "generated_at": _utc_now_iso(),
            "case_name": case_name or "",
            "case_type": case_type or "",
            "target_layer": target_layer,
        },
    }


# ── Routes ──────────────────────────────────────────────────────────────────

TEST_DATA_PATH = REPO_ROOT / "visualization" / "data" / "test_data.json"

def _load_test_data() -> dict:
    if TEST_DATA_PATH.exists():
        try:
            with open(TEST_DATA_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
                json_result = payload.get("json_result") or {}
                has_graph = bool(payload.get("nodes")) and bool(payload.get("edges"))
                if json_result and not has_graph:
                    repaired_output = enrich_graph_output(json_result)
                    repaired_graph = kg_convert(repaired_output)
                    payload["json_result"] = repaired_output
                    payload["nodes"] = repaired_graph.get("nodes", [])
                    payload["edges"] = repaired_graph.get("edges", [])
                    payload["case_name"] = payload.get("case_name") or extract_case_name(repaired_output)
                    if payload.get("score") in (None, ""):
                        payload["score"] = evaluate_output(repaired_output, "manual_restore").get("score", 0)
                    if not payload.get("issues"):
                        payload["issues"] = evaluate_output(repaired_output, "manual_restore").get("issues", [])
                return payload
        except Exception:
            pass
    return {"text": "", "json_result": {}}

def _save_test_data(text: str, json_result: dict, extra: dict = None):
    TEST_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"text": text, "json_result": json_result}
    if extra:
        payload.update(extra)
    with open(TEST_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _patch_test_data(extra: dict):
    payload = _load_test_data()
    for key, value in (extra or {}).items():
        if value is not None:
            payload[key] = value
    TEST_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TEST_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/test-data", methods=["GET"])
def api_get_test_data():
    """Return the last saved test data (text + parse result)."""
    return jsonify(_load_test_data())


@app.route("/api/test-data", methods=["POST"])
def api_save_test_data():
    """Save the current text and parse result as test data."""
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    json_result = data.get("json_result", {})
    extra = {
        key: data.get(key)
        for key in (
            "nodes",
            "edges",
            "score",
            "issues",
            "case_name",
            "row_id",
            "term_quality_result",
            "term_eval_result",
            "term_enhancement_result",
            "active_tab",
        )
        if key in data
    }
    _save_test_data(text, json_result, extra=extra)
    return jsonify({"status": "ok"})


@app.route("/api/parse", methods=["POST"])
def api_parse():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    try:
        result = parse_text(text)
        # 自动保存解析结果作为测试数据，刷新页面后依然可见
        _save_test_data(text, result.get("json_result", {}),
                       extra={k: result.get(k) for k in ("nodes", "edges", "score", "issues", "case_name", "row_id")})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json(silent=True) or {}
    row_id = data.get("row_id", "")
    json_result = data.get("json_result", {})
    case_name = data.get("case_name", "")
    raw_text = data.get("text", "")
    target_layer = (data.get("target_layer") or "manual").strip()
    ontology_eval = data.get("ontology_eval")
    quality_result = data.get("quality_result")
    enhancement_result = data.get("enhancement_result")

    if not row_id:
        return jsonify({"error": "row_id is required"}), 400
    if target_layer not in {"manual", "extracted_candidate"}:
        return jsonify({"error": "target_layer must be manual or extracted_candidate"}), 400

    target_path, _, _ = get_save_target_info(target_layer)

    # Build record in extractor-compatible format
    record = {
        "row_id": row_id,
        "input": {"id": row_id, "text": raw_text},
        "output": json_result,
        "eval": {"row_id": row_id, "score": data.get("score", 0), "issues": data.get("issues", [])},
        "case_name": case_name or "",
        "source": target_layer,
        "_meta": build_save_meta(row_id, raw_text, json_result, case_name, target_layer),
    }
    if ontology_eval:
        record["ontology_eval"] = ontology_eval
    if quality_result:
        record["quality_result"] = quality_result
    if enhancement_result:
        record["enhancement_result"] = enhancement_result
    upsert_jsonl_record(target_path, "row_id", record)

    # Update cases_index
    index = load_cases_index()
    # Check if already exists (replace)
    index = [e for e in index if e.get("row_id") != row_id]
    meta = _extract_case_meta_from_output(json_result, target_layer)
    index.append({
        "row_id": row_id,
        "case_name": case_name or "未命名案例",
        "case_type": (json_result.get("case_type") or {}).get("category", "unknown"),
        "version": 1,
        "source": target_layer,
        "meta": meta,
    })
    save_cases_index(index)

    return jsonify({
        "status": "ok",
        "file": str(target_path),
        "row_id": row_id,
        "target_layer": target_layer,
        "merged_into": str(target_path.relative_to(REPO_ROOT)),
    })


@app.route("/api/cases", methods=["GET"])
def api_cases():
    """Return the full cases index (for admin_instances.html)."""
    index = load_cases_index()
    manual_records = load_manual_records()
    candidate_records = load_candidate_records()

    for item in index:
        meta = item.get("meta") or {}
        needs_meta_refresh = not meta or any(
            key not in meta
            for key in ("case_categories", "case_reasons", "trial_levels", "judgment_years", "publication_years")
        )
        row_id = str(item.get("row_id", ""))
        rec = manual_records.get(row_id) or candidate_records.get(row_id)
        if not needs_meta_refresh and meta:
            continue
        if not rec:
            continue
        item["meta"] = _extract_case_meta_from_output(
            (rec.get("output") or {}),
            rec.get("source") or item.get("source") or "manual"
        )
    return jsonify(index)


@app.route("/api/admin-static-cases", methods=["GET"])
def api_admin_static_cases():
    """Return the legacy admin_instances static case index with filter metadata."""
    bundle = load_admin_static_bundle()
    raw_data = bundle["raw_data"]
    result = []

    for summary in bundle["all_graphs"]:
      row_id = str(summary.get("row_id", ""))
      version = int(summary.get("version", 1) or 1)
      key = f"{row_id}__v{version}" if version > 1 else row_id
      record = raw_data.get(key) or raw_data.get(row_id) or {}
      meta = _extract_static_case_meta(record, source="static")
      result.append({
          "key": key,
          "row_id": row_id,
          "case_name": summary.get("case_name", ""),
          "case_type": summary.get("case_type", ""),
          "version": version,
          "source": summary.get("source", "static"),
          "meta": meta,
      })

    return jsonify(result)


@app.route("/api/admin-static-case/<row_id>", methods=["GET"])
def api_admin_static_case(row_id):
    """Return one legacy admin_instances static case detail."""
    version = request.args.get("version")
    summary, record = _find_static_case_record(row_id, version)
    if not summary or not record:
        return jsonify({"error": "static case not found"}), 404

    version_no = int(summary.get("version", 1) or 1)
    key = f"{row_id}__v{version_no}" if version_no > 1 else str(row_id)
    meta = _extract_static_case_meta(record, source="static")

    return jsonify({
        "key": key,
        "row_id": str(summary.get("row_id", row_id)),
        "case_name": summary.get("case_name", ""),
        "case_type": summary.get("case_type", ""),
        "version": version_no,
        "source": summary.get("source", "static"),
        "json_result": record.get("output", {}) or {},
        "raw_record": record,
        "meta": meta,
    })


@app.route("/api/saved-case/<row_id>", methods=["GET"])
def api_saved_case(row_id):
    """Return full graph data for a saved manual case."""
    from parser import kg_convert

    records = load_manual_records()
    candidate_records = load_candidate_records()
    rec = records.get(row_id) or candidate_records.get(row_id)
    if not rec:
        return jsonify({"error": "case not found"}), 404

    output = rec.get("output", {})
    graph = kg_convert(output)
    case_name = rec.get("case_name", "")
    if not case_name:
        from parser import extract_case_name
        case_name = extract_case_name(output)

    return jsonify({
        "row_id": row_id,
        "json_result": output,
        "nodes": graph["nodes"],
        "edges": graph["edges"],
        "case_name": case_name,
        "raw_text": ((rec.get("input") or {}).get("text") or ""),
        "parse_eval": rec.get("eval") or {},
        "ontology_eval": rec.get("ontology_eval") or None,
        "quality_result": rec.get("quality_result") or None,
        "enhancement_result": rec.get("enhancement_result") or None,
        "source": rec.get("source", "manual"),
        "meta": _extract_case_meta_from_output(output, rec.get("source", "manual")),
        "raw_record": rec,
        "_meta": rec.get("_meta") or {},
    })


@app.route("/api/parse-quality", methods=["POST"])
def api_parse_quality():
    """Local parse quality analysis — no LLM call, pure statistics."""
    data = request.get_json(silent=True) or {}
    json_result = data.get("json_result", {})
    raw_text = data.get("raw_text")
    row_id = data.get("row_id")

    if not json_result:
        return jsonify({"error": "json_result is required"}), 400

    try:
        from quality_analyzer import parse_quality
        result = parse_quality(json_result)
        _patch_test_data({
            "text": raw_text,
            "row_id": row_id,
            "json_result": json_result,
            "term_quality_result": result,
            "active_tab": "issues",
        })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ontology-evaluate", methods=["POST"])
def api_ontology_evaluate():
    """Evaluate LLM extraction quality against ontology."""
    data = request.get_json(silent=True) or {}
    raw_text = data.get("raw_text", "")
    json_result = data.get("json_result", {})
    row_id = data.get("row_id", "manual_eval")

    if not json_result:
        return jsonify({"error": "json_result is required"}), 400

    try:
        from evaluator import ontology_evaluate
        result = ontology_evaluate(raw_text, json_result, row_id, use_llm=True)
        _patch_test_data({
            "text": raw_text,
            "row_id": row_id,
            "json_result": json_result,
            "term_eval_result": result,
            "active_tab": "eval",
        })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/parse-enhancement", methods=["POST"])
def api_parse_enhancement():
    """Run targeted second-pass parsing for uncovered or weak ontology areas."""
    data = request.get_json(silent=True) or {}
    raw_text = (data.get("raw_text") or "").strip()
    json_result = data.get("json_result") or {}
    row_id = data.get("row_id", "manual_enhance")
    quality_result = data.get("quality_result") or {}
    ontology_eval = data.get("ontology_eval") or {}

    if not raw_text:
        return jsonify({"error": "raw_text is required"}), 400
    if not json_result:
        return jsonify({"error": "json_result is required"}), 400
    if not ontology_eval:
        return jsonify({"error": "ontology_eval is required"}), 400

    try:
        result = parse_enhancement(
            raw_text,
            json_result,
            row_id=row_id,
            quality_result=quality_result,
            ontology_eval=ontology_eval,
        )
        _patch_test_data({
            "text": raw_text,
            "row_id": row_id,
            "json_result": json_result,
            "term_quality_result": quality_result or None,
            "term_eval_result": ontology_eval or None,
            "term_enhancement_result": result,
            "active_tab": "enhance",
        })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9120)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--serve-files", action="store_true",
                        help="Also serve static files from visualization/ on the same port")
    args = parser.parse_args()

    # Load .env if available
    hermes_env = Path.home() / ".hermes" / ".env"
    if hermes_env.exists():
        from dotenv import load_dotenv
        load_dotenv(hermes_env)

    if args.serve_files:
        from flask import send_from_directory
        VIS_DIR = REPO_ROOT / "visualization"

        @app.route("/")
        def serve_index():
            return send_from_directory(VIS_DIR, "ontology_v2.2.html")

        @app.route("/<path:filename>")
        def serve_static(filename):
            resp = send_from_directory(VIS_DIR, filename)
            resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp.headers['Pragma'] = 'no-cache'
            resp.headers['Expires'] = '0'
            return resp

    # Try to free the port automatically
    import socket
    import subprocess
    import time
    import os
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((args.host, args.port)) == 0:
                print(f"Port {args.port} is in use. Attempting to free it...", flush=True)
                try:
                    out = subprocess.check_output(["lsof", "-t", f"-i:{args.port}"]).decode().strip()
                    if out:
                        for pid in out.split('\n'):
                            os.system(f"kill -9 {pid}")
                        time.sleep(1)
                except:
                    subprocess.run(["fuser", "-k", f"{args.port}/tcp"], check=False)
                    time.sleep(1)
    except Exception as e:
        pass

    print(f"Starting parse API on {args.host}:{args.port}", flush=True)
    app.run(host=args.host, port=args.port, debug=args.debug)
