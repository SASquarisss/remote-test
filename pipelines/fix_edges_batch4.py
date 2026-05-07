#!/usr/bin/env python3
"""Regenerate edges files that were lost due to overwrite_batch_csv edge case."""
import sys, csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import batch_process as bp

GOLD_DIR = Path("/root/.hermes/hermes-agent/remote-test/data_lake/gold")
SOURCE_CSV = Path("/root/.hermes/hermes-agent/remote-test/data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv")
BATCH_IDS = [2229, 2266, 2287, 2292, 2294, 2325, 2337, 2362, 2371, 2428, 2441, 2444, 2449, 2473, 2478, 2482, 2485, 2490, 2495, 2504, 2654, 2668, 2692, 2705, 2720, 2731, 2737, 2751, 2771, 2800, 2803, 2819, 2831, 2843, 2847, 2870, 2878, 2893, 2920, 2955, 2960, 2964, 2976, 2980, 2986, 3003, 3017, 3024, 3026, 3030]
BATCH_ID_SET = set(BATCH_IDS)

# Read source data
all_rows = bp.read_source_csv()
batch_rows = [r for r in all_rows if int(r["id"]) in BATCH_ID_SET]
batch_rows.sort(key=lambda r: int(r["id"]))

# Regenerate edges
edges_guides = []
edges_cites = []
provisions = {}
case_types = {}

for row in batch_rows:
    row_id_int = int(row["id"])
    gc_id = f"guiding_case_{row_id_int}"
    
    case_type_raw = row.get("case_type") or "unknown"
    category, sub_type = bp.extract_case_category(case_type_raw)
    category_en = bp.map_category(category)
    
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
    
    edges_guides.append({
        "guiding_case_id": gc_id,
        "case_type_id": ct_id,
    })
    
    # Legal provisions
    from extract_legal_provisions_regex import extract_legal_provisions as regex_extract
    related_law = row.get("related_law") or ""
    related_law_provisions = bp.parse_related_law(related_law)
    judgment_reason = row.get("judgment_reason") or ""
    judgment_essence = row.get("judgment_essence") or ""
    combined_text = f"{judgment_reason}\n{judgment_essence}\n{related_law}"
    regex_provisions = regex_extract(combined_text)
    
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

# Dedup CITES
seen_edges = set()
edges_cites_deduped = []
for edge in edges_cites:
    key = (edge["case_id"], edge["provision_id"])
    if key not in seen_edges:
        seen_edges.add(key)
        edges_cites_deduped.append(edge)
edges_cites = edges_cites_deduped

# Filter orphans
gc_ids_in_batch = {f"guiding_case_{i}" for i in BATCH_IDS}
edges_cites = [edge for edge in edges_cites if edge["case_id"] in gc_ids_in_batch]

print(f"Edges GUIDES: {len(edges_guides)}")
print(f"Edges CITES: {len(edges_cites)}")
print(f"CaseTypes: {len(case_types)}")
print(f"Provisions: {len(provisions)}")

# Now write using overwrite_batch_csv
bp.overwrite_batch_csv("edges_GUIDES_CASE_TYPE.csv", edges_guides, BATCH_ID_SET)
bp.overwrite_batch_csv("edges_CITES.csv", edges_cites, BATCH_ID_SET)
bp.overwrite_batch_csv("CaseType.csv", list(case_types.values()), BATCH_ID_SET)
bp.overwrite_batch_csv("LegalProvision.csv", list(provisions.values()), BATCH_ID_SET)

print("\nDone! Edge files regenerated.")
