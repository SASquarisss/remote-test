#!/usr/bin/env python3
"""Update batch_state.json with complete processed_ids list."""
import csv, json
from pathlib import Path

GOLD_DIR = Path("/root/.hermes/hermes-agent/remote-test/data_lake/gold")
BATCH_STATE = Path("/root/.hermes/hermes-agent/remote-test/data/processed/batch_state.json")

# Get all processed IDs from Gold
gc_path = GOLD_DIR / "GuidingCase.csv"
all_ids = []
with open(gc_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        gid = row.get("id", "").replace("guiding_case_", "")
        if gid.isdigit():
            all_ids.append(int(gid))

all_ids.sort()

# Read existing state
state = {}
if BATCH_STATE.exists():
    with open(BATCH_STATE, "r") as f:
        try:
            state = json.load(f)
        except json.JSONDecodeError:
            state = {}

state["total_processed"] = len(all_ids)
state["processed_ids"] = all_ids
state["pending_ids_count"] = 500 - len(all_ids)

BATCH_STATE.parent.mkdir(parents=True, exist_ok=True)
with open(BATCH_STATE, "w") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)

print(f"Updated batch_state.json: {len(all_ids)} processed, {state['pending_ids_count']} pending")
