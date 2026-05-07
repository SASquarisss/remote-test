#!/usr/bin/env python3
"""Regenerate ALL edges from the complete GuidingCase gold layer.
This fixes prior edge data lost due to overwrite_batch_csv bug."""
import sys, csv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import batch_process as bp

GOLD_DIR = Path("/root/.hermes/hermes-agent/remote-test/data_lake/gold")
SOURCE_CSV = Path("/root/.hermes/hermes-agent/remote-test/data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv")

# Step 1: Get all processed GC IDs from gold
gc_path = GOLD_DIR / "GuidingCase.csv"
processed_ids = set()
with open(gc_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        gid = row.get("id", "").replace("guiding_case_", "")
        if gid.isdigit():
            processed_ids.add(int(gid))

print(f"Total processed GCs: {len(processed_ids)}")

# Step 2: Read source data for all processed IDs
all_rows = bp.read_source_csv()
batch_rows = [r for r in all_rows if int(r["id"]) in processed_ids]
batch_rows.sort(key=lambda r: int(r["id"]))

print(f"Matched source rows: {len(batch_rows)}")

# Step 3: Regenerate edges
edges_guides = []
edges_cites = []

for row in batch_rows:
    row_id_int = int(row["id"])
    gc_id = f"guiding_case_{row_id_int}"
    
    case_type_raw = row.get("case_type") or "unknown"
    category, sub_type = bp.extract_case_category(case_type_raw)
    category_en = bp.map_category(category)
    ct_id = bp.md5_id("case_type", category_en, sub_type)
    
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
            prov_id_r = bp.md5_id("provision", statute, article, item)
            edges_cites.append({
                "case_id": gc_id,
                "provision_id": prov_id_r,
                "citation_position": "裁判要旨",
                "citation_purpose": "法律依据"
            })

# Dedup CITES by (case_id, provision_id)
seen = set()
edges_cites_deduped = []
for edge in edges_cites:
    key = (edge["case_id"], edge["provision_id"])
    if key not in seen:
        seen.add(key)
        edges_cites_deduped.append(edge)
edges_cites = edges_cites_deduped

# Filter orphan CITES edges
gc_ids_set = {f"guiding_case_{i}" for i in processed_ids}
edges_cites = [e for e in edges_cites if e["case_id"] in gc_ids_set]

print(f"Edges GUIDES to write: {len(edges_guides)}")
print(f"Edges CITES to write: {len(edges_cites)}")

# Step 4: Write edges (full overwrite, not append — we're regenerating everything)
def write_edges_full(name, data, fieldnames):
    path = GOLD_DIR / name
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"Wrote {len(data)} rows to {name}")

write_edges_full("edges_GUIDES_CASE_TYPE.csv", edges_guides, ["guiding_case_id", "case_type_id"])
write_edges_full("edges_CITES.csv", edges_cites, ["case_id", "provision_id", "citation_position", "citation_purpose"])

print("\nDone! All edges regenerated covering all 180 processed GCs.")
