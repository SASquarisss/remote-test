#!/usr/bin/env python3
"""
Batch 4 runner — bypasses incompatible batch_state.json,
uses batch_process.py's parsing logic directly.
"""
import sys, csv, json
from pathlib import Path

# Import batch_process module
sys.path.insert(0, str(Path(__file__).resolve().parent))
import batch_process as bp

# === Step 1: Identify the 50 unprocessed IDs ===
SOURCE_CSV = Path("/root/.hermes/hermes-agent/remote-test/data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv")
GOLD_DIR = Path("/root/.hermes/hermes-agent/remote-test/data_lake/gold")
BATCH_SIZE = 50

# Load existing IDs from Gold CSV
existing_ids = bp.load_existing_ids()
print(f"Existing IDs in Gold: {len(existing_ids)}")
print(f"Existing ID set: {sorted(existing_ids)}")

# Read all source rows
all_rows = bp.read_source_csv()
print(f"Source CSV total rows: {len(all_rows)}")

# Find unprocessed, sorted by ID
unprocessed = [r for r in all_rows if int(r["id"]) not in existing_ids]
unprocessed.sort(key=lambda r: int(r["id"]))

print(f"Unprocessed rows: {len(unprocessed)}")

# Take next 50
batch = unprocessed[:BATCH_SIZE]
batch_ids = [int(r["id"]) for r in batch]

print(f"Batch 4 IDs: {batch_ids[0]} .. {batch_ids[-1]} ({len(batch)} records)")
print(f"Batch IDs list: {batch_ids}")

# === Step 2: Run parsing logic (copied from process_batch) ===
from typing import Dict, List

guiding_cases: List[Dict] = []
courts: Dict[str, Dict] = {}
case_types: Dict[str, Dict] = {}
provisions: Dict[str, Dict] = {}
edges_cites: List[Dict] = []
edges_guides: List[Dict] = []

success_count = 0
skip_count = 0
field_stats = {"with_court": 0, "with_type": 0, "with_law": 0, "with_essence": 0}

# Reset audit log
bp.AUDIT_LOG_UNMAPPED["category"] = set()
bp.AUDIT_LOG_UNMAPPED["trial_level"] = set()

for row in batch:
    row_id = (row.get("id") or "").strip()
    if not row_id or not row_id.isdigit():
        skip_count += 1
        continue

    row_id_int = int(row_id)
    gc_id = f"guiding_case_{row_id_int}"

    # Belt-and-suspenders
    if row_id_int in existing_ids:
        skip_count += 1
        continue

    case_type_raw = row.get("case_type") or "unknown"
    category, sub_type = bp.extract_case_category(case_type_raw)
    category_en = bp.map_category(category)

    # CaseType
    ct_id = bp.md5_id("case_type", category_en, sub_type)
    if ct_id not in case_types:
        case_types[ct_id] = {
            "id": ct_id,
            "code": ct_id.replace("case_type_", ""),
            "name": sub_type or category,
            "category": category_en,
            "level1": category,
            "level2": sub_type,
            "source": "指导案例库分类",
            "desensitize": "false",
            "create_time": "2026-04-21T00:00:00Z",
            "update_time": "2026-04-21T00:00:00Z",
        }

    # Court
    court_name = bp.normalize_court_name(row.get("court_name"))
    court_id = bp.md5_id("court", court_name)
    if court_id not in courts:
        level = "supreme" if "最高" in court_name else "high" if "高级" in court_name else "intermediate" if "中级" in court_name else "basic"
        district_id = bp.extract_district_from_court(court_name)
        courts[court_id] = {
            "id": court_id,
            "name": court_name,
            "org_type": "court",
            "credit_code": bp.md5_id("cc", court_name)[-18:],
            "court_level": level,
            "district_id": district_id,
            "source": "指导案例库",
            "desensitize": "false",
            "create_time": "2026-04-21T00:00:00Z",
            "update_time": "2026-04-21T00:00:00Z",
        }

    # GuidingCase
    pub_date = bp.parse_date(row.get("trial_year") or "")
    case_level = (row.get("case_level") or "").strip()
    CASE_LEVEL_MAP = {"1": "first_instance", "2": "second_instance", "": ""}
    trial_level = CASE_LEVEL_MAP.get(case_level, "")

    if not trial_level:
        trial_procedure = (row.get("trial_procedure") or "").strip()
        trial_level = bp.map_trial_level(trial_procedure)

    import re
    web_name = (row.get("web_name") or "").strip()
    binding = "mandatory" if "人民法院案例库" in web_name else "persuasive"

    essence = (row.get("judgment_essence") or "").strip()
    essence = re.sub(r'<[^>]+>', '', essence)
    essence = essence.replace("\\\\u3000", " ").replace("u3000", " ")
    essence = essence.replace("\u3000", " ")
    essence = essence.replace("\\n", " ").replace("\\r", " ")
    essence = re.sub(r'\s+', ' ', essence).strip()
    essence = essence[:2000]

    guiding_cases.append({
        "id": gc_id,
        "guiding_case_number": (row.get("storage_no") or "").strip(),
        "name": f"{case_type_raw}-{(row.get('storage_no') or '').strip()}",
        "issuing_court_id": court_id,
        "publication_date": pub_date,
        "guiding_points": essence,
        "binding_force": binding,
        "source_url": (row.get("web_url") or "").strip(),
        "tags": bp.clean_tags(row.get("key_words") or ""),
        "trial_procedure": (row.get("trial_procedure") or "").strip(),
        "trial_level": trial_level,
        "source": web_name,
        "desensitize": "false",
        "create_time": "2026-04-21T00:00:00Z",
        "update_time": "2026-04-21T00:00:00Z",
    })

    edges_guides.append({
        "guiding_case_id": gc_id,
        "case_type_id": ct_id,
    })

    # LegalProvision extraction
    from extract_legal_provisions_regex import extract_legal_provisions as regex_extract_legal_provisions
    related_law = row.get("related_law") or ""
    related_law_provisions = bp.parse_related_law(related_law)
    judgment_reason = row.get("judgment_reason") or ""
    judgment_essence = row.get("judgment_essence") or ""
    combined_text = f"{judgment_reason}\n{judgment_essence}\n{related_law}"
    regex_provisions = regex_extract_legal_provisions(combined_text)

    seen_provision_keys = set()
    for law in related_law_provisions:
        prov_id = bp.md5_id("provision", law["law_name"], law["article"], law["item"])
        key = (law["law_name"], law["article"], law["item"])
        if key not in seen_provision_keys:
            seen_provision_keys.add(key)
            if prov_id not in provisions:
                provisions[prov_id] = {
                    "id": prov_id,
                    "law_id": bp.md5_id("law", law["law_name"]),
                    "article": law["article"],
                    "paragraph": law["paragraph"],
                    "item": law["item"],
                    "content": "",
                    "status": "effective",
                    "source": law["law_name"],
                    "desensitize": "false",
                    "create_time": "2026-04-21T00:00:00Z",
                    "update_time": "2026-04-21T00:00:00Z",
                }
            edges_cites.append({
                "case_id": gc_id,
                "provision_id": prov_id,
                "citation_position": "裁判要旨",
                "citation_purpose": "法律依据"
            })

    for prov in regex_provisions:
        statute = prov.get("statute", "")
        article = prov.get("article", "")
        paragraph = prov.get("paragraph", "")
        item = ""
        key = (statute, article, item)
        if key not in seen_provision_keys and article:
            seen_provision_keys.add(key)
            prov_id = bp.md5_id("provision", statute, article, item)
            if prov_id not in provisions:
                provisions[prov_id] = {
                    "id": prov_id,
                    "law_id": bp.md5_id("law", statute),
                    "article": article,
                    "paragraph": paragraph,
                    "item": item,
                    "content": "",
                    "status": "effective",
                    "source": statute,
                    "desensitize": "false",
                    "create_time": "2026-04-21T00:00:00Z",
                    "update_time": "2026-04-21T00:00:00Z",
                }
            edges_cites.append({
                "case_id": gc_id,
                "provision_id": prov_id,
                "citation_position": "裁判要旨",
                "citation_purpose": "法律依据"
            })

    success_count += 1
    existing_ids.add(row_id_int)

    if court_name != "未知法院":
        field_stats["with_court"] += 1
    if case_type_raw not in ("unknown", ""):
        field_stats["with_type"] += 1
    if related_law not in ("\\\\N", "\\N", ""):
        field_stats["with_law"] += 1
    if essence:
        field_stats["with_essence"] += 1

# Dedup Courts
courts_deduped = list(courts.values())

# Dedup CITES edges
seen_edges = set()
edges_cites_deduped = []
for edge in edges_cites:
    key = (edge["case_id"], edge["provision_id"])
    if key not in seen_edges:
        seen_edges.add(key)
        edges_cites_deduped.append(edge)
edges_cites = edges_cites_deduped

# Filter orphan CITES edges
gc_ids_in_batch = {gc["id"] for gc in guiding_cases}
edges_cites = [edge for edge in edges_cites if edge["case_id"] in gc_ids_in_batch]

# === Step 3: Append to Gold CSVs ===
GOLD_DIR.mkdir(parents=True, exist_ok=True)
batch_id_set = set(batch_ids)

print(f"\n=== Writing to Gold CSVs ===")
bp.overwrite_batch_csv("GuidingCase.csv", guiding_cases, batch_id_set)
bp.overwrite_batch_csv("Court.csv", courts_deduped, batch_id_set)
bp.overwrite_batch_csv("CaseType.csv", list(case_types.values()), batch_id_set)
bp.overwrite_batch_csv("LegalProvision.csv", list(provisions.values()), batch_id_set)
bp.overwrite_batch_csv("edges_GUIDES_CASE_TYPE.csv", edges_guides, batch_id_set)
bp.overwrite_batch_csv("edges_CITES.csv", edges_cites, batch_id_set)

# === Step 4: Update batch_state.json ===
BATCH_STATE = Path("/root/.hermes/hermes-agent/remote-test/data/processed/batch_state.json")
state = {}
if BATCH_STATE.exists():
    with open(BATCH_STATE, "r") as f:
        try:
            state = json.load(f)
        except json.JSONDecodeError:
            state = {}

state["batch_count"] = state.get("batch_count", 0) + 1
state["last_batch_range"] = f"{batch_ids[0]}-{batch_ids[-1]}"
state["total_processed"] = len(existing_ids)
all_processed_ids = sorted(set(state.get("processed_ids", []) + batch_ids))
state["processed_ids"] = all_processed_ids
state["note"] = f"Batch 4: {len(batch_ids)} records (IDs {batch_ids[0]}-{batch_ids[-1]}). Total distinct: {len(existing_ids)}."
state["pending_ids_count"] = len(unprocessed) - len(batch)
state["audit_trial_level_unmapped"] = sorted(bp.AUDIT_LOG_UNMAPPED["trial_level"])
state["audit_category_unmapped"] = sorted(bp.AUDIT_LOG_UNMAPPED["category"])
state["audit_notes"] = "执行类/委赔/国家赔偿/死刑复核不属于一审/二审/再审枚举范围，故意置空"

BATCH_STATE.parent.mkdir(parents=True, exist_ok=True)
with open(BATCH_STATE, "w") as f:
    json.dump(state, f, indent=2, ensure_ascii=False)

# === Step 5: Report ===
print(f"\n{'='*60}")
print(f"BATCH 4 PROCESSING REPORT")
print(f"{'='*60}")
print(f"ID Range:          {batch_ids[0]} - {batch_ids[-1]} ({len(batch_ids)} records)")
print(f"Successfully parsed: {success_count}")
print(f"Skipped (belt-and-suspenders): {skip_count}")
print(f"Total processed (cumulative): {len(existing_ids)}")
print(f"")
print(f"Entities created:")
print(f"  GuidingCase:     {len(guiding_cases)}")
print(f"  Court:           {len(courts_deduped)} (unique)")
print(f"  CaseType:        {len(case_types)} (unique)")
print(f"  LegalProvision:  {len(provisions)} (unique)")
print(f"  Edges GUIDES:    {len(edges_guides)}")
print(f"  Edges CITES:     {len(edges_cites)}")
print(f"")
print(f"Field coverage (among parsed):")
print(f"  With court name:     {field_stats['with_court']}/{success_count}")
print(f"  With case type:      {field_stats['with_type']}/{success_count}")
print(f"  With related law:    {field_stats['with_law']}/{success_count}")
print(f"  With guiding points: {field_stats['with_essence']}/{success_count}")
if bp.AUDIT_LOG_UNMAPPED["category"]:
    print(f"")
    print(f"⚠️  AUDIT: Unmapped category values:")
    for v in sorted(bp.AUDIT_LOG_UNMAPPED["category"]):
        print(f"    - '{v}'")
if bp.AUDIT_LOG_UNMAPPED["trial_level"]:
    print(f"")
    print(f"⚠️  AUDIT: Unmapped trial_level values:")
    for v in sorted(bp.AUDIT_LOG_UNMAPPED["trial_level"]):
        print(f"    - '{v}'")
print(f"{'='*60}")
