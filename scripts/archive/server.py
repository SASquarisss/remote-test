"""Simple dev server: serves static files from visualization/ + API."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

# Re-export the app and add static routes
from backend.app import app
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

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9119)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    print(f"Starting dev server on {args.host}:{args.port}", flush=True)
    app.run(host=args.host, port=args.port, debug=args.debug)
