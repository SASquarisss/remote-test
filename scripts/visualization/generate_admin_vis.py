#!/usr/bin/env python3
"""Generate admin_instances shell HTML and external data bundle."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
JSONL_PATH = PROJECT / "data_lake/extracted_v2.2_admin_all.jsonl"
CSV_PATH = PROJECT / "data/raw/admin_cases_only.csv"
OUTPUT_PATH = PROJECT / "visualization/admin_instances.html"
DATA_OUTPUT_PATH = PROJECT / "visualization/data/admin_instances_data.js"
TEMPLATE_PATH = PROJECT / "visualization/templates/admin_instances_shell.html"


def load_admin_ids() -> set[str]:
    admin_ids: set[str] = set()
    with CSV_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rid = str(row.get("id") or "").strip()
            if rid:
                admin_ids.add(rid)
    return admin_ids


def load_admin_cases(admin_ids: set[str]) -> list[dict]:
    cases_raw: list[dict] = []
    with JSONL_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            rid = str(data.get("row_id") or "").strip()
            if not rid or rid not in admin_ids:
                continue
            output = data.get("output")
            if not isinstance(output, dict) or not output:
                continue
            fingerprint = hashlib.sha256(
                json.dumps(output, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            cases_raw.append(
                {
                    "row_id": rid,
                    "data": data,
                    "fingerprint": fingerprint,
                }
            )
    return cases_raw


def assign_versions(cases_raw: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    by_rid: dict[str, list[dict]] = defaultdict(list)
    for item in cases_raw:
        by_rid[item["row_id"]].append(item)

    versioned_cases: list[dict] = []
    raw_data: dict[str, dict] = {}
    for rid, entries in sorted(by_rid.items(), key=lambda item: int(item[0])):
        by_fp: dict[str, list[dict]] = defaultdict(list)
        for entry in entries:
            by_fp[entry["fingerprint"]].append(entry)

        ordered_groups = sorted(
            by_fp.items(),
            key=lambda item: json.dumps(item[1][0]["data"], ensure_ascii=False, sort_keys=True),
        )
        multiple_versions = len(ordered_groups) > 1
        for version, (_, fp_entries) in enumerate(ordered_groups, start=1):
            record = fp_entries[0]["data"]
            compound_key = f"{rid}__v{version}" if multiple_versions else rid
            versioned_cases.append(
                {
                    "row_id": rid,
                    "version": version,
                    "key": compound_key,
                    "data": record,
                }
            )
            raw_data[compound_key] = record
    return versioned_cases, raw_data


def build_case_summaries(cases: list[dict]) -> list[dict]:
    summaries: list[dict] = []
    for case in cases:
        output = case["data"].get("output") or {}
        guiding = output.get("guiding_case") or {}
        case_type = output.get("case_type") or {}
        case_name = (
            guiding.get("guiding_case_name")
            or case["data"].get("case_name")
            or f"Case {case['row_id']}"
        )
        summaries.append(
            {
                "row_id": case["row_id"],
                "case_name": case_name,
                "case_type": case_type.get("level2")
                or case_type.get("level1")
                or case_type.get("category")
                or "",
                "version": case["version"],
                "source": "static",
            }
        )
    return summaries


def write_data_file(case_summaries: list[dict], raw_data: dict[str, dict]) -> None:
    DATA_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = (
        "window.ALL_GRAPHS = "
        + json.dumps(case_summaries, ensure_ascii=False)
        + ";\nwindow.RAW_DATA = "
        + json.dumps(raw_data, ensure_ascii=False)
        + ";\n"
    )
    DATA_OUTPUT_PATH.write_text(payload, encoding="utf-8")


def write_html_shell() -> None:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")
    OUTPUT_PATH.write_text(TEMPLATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")


def main() -> None:
    admin_ids = load_admin_ids()
    cases_raw = load_admin_cases(admin_ids)
    versioned_cases, raw_data = assign_versions(cases_raw)
    case_summaries = build_case_summaries(versioned_cases)
    write_data_file(case_summaries, raw_data)
    write_html_shell()

    print(f"Admin ids: {len(admin_ids)}")
    print(f"Raw matched lines: {len(cases_raw)}")
    print(f"Versioned cases: {len(versioned_cases)}")
    print(f"Summary records: {len(case_summaries)}")
    print(f"HTML written: {OUTPUT_PATH}")
    print(f"Data written: {DATA_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
