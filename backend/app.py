"""Flask API for legal text parsing terminal."""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS

# Ensure backend/ is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parser import parse_text

# ── Paths ───────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]
MANUAL_JSONL = REPO_ROOT / "data_lake" / "manual_parsed.jsonl"
CASES_INDEX = REPO_ROOT / "visualization" / "data" / "cases_index.json"

# ── App ─────────────────────────────────────────────────────────────────────

app = Flask(__name__)
CORS(app)


# ── Helpers ─────────────────────────────────────────────────────────────────

def load_cases_index() -> list:
    if CASES_INDEX.exists():
        with open(CASES_INDEX, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def load_manual_records() -> list:
    """Load all manual records from JSONL into a dict keyed by row_id."""
    records = {}
    if MANUAL_JSONL.exists():
        with open(MANUAL_JSONL, "r", encoding="utf-8") as f:
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


def save_cases_index(index: list):
    CASES_INDEX.parent.mkdir(parents=True, exist_ok=True)
    with open(CASES_INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def append_to_jsonl(record: dict):
    MANUAL_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(MANUAL_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/parse", methods=["POST"])
def api_parse():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    try:
        result = parse_text(text)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json(silent=True) or {}
    row_id = data.get("row_id", "")
    json_result = data.get("json_result", {})
    case_name = data.get("case_name", "")

    if not row_id:
        return jsonify({"error": "row_id is required"}), 400

    # Build record in extractor-compatible format
    record = {
        "row_id": row_id,
        "input": {"id": row_id},
        "output": json_result,
        "eval": {"row_id": row_id, "score": data.get("score", 0), "issues": data.get("issues", [])},
        "source": "manual",
    }
    append_to_jsonl(record)

    # Update cases_index
    index = load_cases_index()
    # Check if already exists (replace)
    index = [e for e in index if e.get("row_id") != row_id]
    index.append({
        "row_id": row_id,
        "case_name": case_name or "未命名案例",
        "case_type": (json_result.get("case_type") or {}).get("category", "unknown"),
        "version": 1,
        "source": "manual",
    })
    save_cases_index(index)

    return jsonify({"status": "ok", "file": str(MANUAL_JSONL), "row_id": row_id})


@app.route("/api/cases", methods=["GET"])
def api_cases():
    """Return the full cases index (for admin_instances.html)."""
    index = load_cases_index()
    return jsonify(index)


@app.route("/api/saved-case/<row_id>", methods=["GET"])
def api_saved_case(row_id):
    """Return full graph data for a saved manual case."""
    from parser import kg_convert

    records = load_manual_records()
    rec = records.get(row_id)
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
    })


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
            return send_from_directory(VIS_DIR, filename)

    print(f"Starting parse API on {args.host}:{args.port}", flush=True)
    app.run(host=args.host, port=args.port, debug=args.debug)
