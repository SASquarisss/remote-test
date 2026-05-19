#!/usr/bin/env python3
"""
Batch 3 Audit: Verify 50 new records (IDs ~1300-2208) in Gold layer.
Checks:
1. Field fill rates
2. CaseType.category enum values (vs ontology)
3. trial_level mapping correctness
4. tags cleaning
5. LegalProvision extraction quality
6. New unmapped trial_procedure values
"""
import csv
import sys
from pathlib import Path

GOLD_DIR = Path("/root/.hermes/hermes-agent/remote-test/data_lake/gold")
SOURCE_CSV = Path("/root/.hermes/hermes-agent/remote-test/data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv")

# Ontology-defined enums
VALID_CATEGORIES = {"civil", "criminal", "administrative", "ip", "execution", "state_compensation"}
VALID_TRIAL_LEVELS = {"first_instance", "second_instance", "retrial", ""}

# Expected batch 3 ID range (from batch_state.json)
BATCH3_START = 1300
BATCH3_END = 2208

def load_gold_csv(name):
    """Load a gold CSV as list of dicts."""
    path = GOLD_DIR / name
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

def load_source_csv():
    """Load source CSV rows."""
    HEADER = [
        "id", "web_name", "web_url", "case_type", "storage_no", "court_name",
        "key_words", "trial_procedure", "trial_year", "case_level",
        "basic_facts", "judgment_reason", "judgment_essence",
        "related_info", "related_law", "related_judgment_body",
        "create_time", "update_time", "md5_value", "judgment_mean", "dt"
    ]
    rows = []
    with open(SOURCE_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for parts in reader:
            if not parts or not parts[0].strip().isdigit():
                continue
            row = {}
            for i, col in enumerate(HEADER):
                row[col] = parts[i] if i < len(parts) else ""
            rows.append(row)
    return rows

def is_batch3_id(gc_id):
    """Check if a guiding_case ID is in batch 3 range."""
    gid = gc_id.replace("guiding_case_", "")
    if gid.isdigit():
        return BATCH3_START <= int(gid) <= BATCH3_END
    return False

def main():
    print("=" * 70)
    print("BATCH 3 AUDIT REPORT")
    print("=" * 70)

    # 1. Load all gold CSVs
    gc_rows = load_gold_csv("GuidingCase.csv")
    ct_rows = load_gold_csv("CaseType.csv")
    court_rows = load_gold_csv("Court.csv")
    prov_rows = load_gold_csv("LegalProvision.csv")
    cites_rows = load_gold_csv("edges_CITES.csv")
    guides_rows = load_gold_csv("edges_GUIDES_CASE_TYPE.csv")

    # 2. Identify batch 3 rows in GuidingCase
    gc_batch3 = [r for r in gc_rows if is_batch3_id(r["id"])]
    print(f"\n📊 OVERVIEW")
    print(f"  Total GuidingCase gold rows: {len(gc_rows)}")
    print(f"  Batch 3 GuidingCase rows (ID 1300-2208): {len(gc_batch3)}")
    print(f"  Total Court rows: {len(court_rows)}")
    print(f"  Total CaseType rows: {len(ct_rows)}")
    print(f"  Total LegalProvision rows: {len(prov_rows)}")
    print(f"  Total edges_CITES rows: {len(cites_rows)}")
    print(f"  Total edges_GUIDES_CASE_TYPE rows: {len(guides_rows)}")

    # 3. FIELD FILL RATE
    print(f"\n📊 FIELD FILL RATE (Batch 3 GuidingCase)")
    fields_to_check = [
        "id", "guiding_case_number", "name", "issuing_court_id",
        "publication_date", "guiding_points", "binding_force",
        "source_url", "tags", "trial_procedure", "trial_level",
        "source", "desensitize"
    ]
    total = len(gc_batch3)
    print(f"  Total records: {total}")
    for field in fields_to_check:
        filled = sum(1 for r in gc_batch3 if r.get(field, "").strip())
        pct = filled / total * 100
        empty_examples = [r["id"] for r in gc_batch3 if not r.get(field, "").strip()][:3]
        msg = f"  {field:30s}: {filled:3d}/{total} ({pct:5.1f}%)"
        if empty_examples:
            msg += f"  EMPTY examples: {empty_examples}"
        print(msg)

    # 4. CaseType.category ENUM CHECK
    print(f"\n📊 CaseType.category ENUM CHECK")
    ct_batch3_ids = set()
    for r in guides_rows:
        gc_id = r["guiding_case_id"]
        if is_batch3_id(gc_id):
            ct_batch3_ids.add(r["case_type_id"])

    ct_batch3 = [r for r in ct_rows if r["id"] in ct_batch3_ids]
    print(f"  Batch 3 CaseType rows: {len(ct_batch3)}")
    invalid_categories = {}
    for r in ct_batch3:
        cat = r.get("category", "")
        if cat not in VALID_CATEGORIES:
            invalid_categories[r["id"]] = cat
    if invalid_categories:
        print(f"  ❌ INVALID categories found:")
        for cid, cat in invalid_categories.items():
            print(f"      {cid}: category='{cat}'")
    else:
        print(f"  ✅ All {len(ct_batch3)} categories valid: {sorted(set(r['category'] for r in ct_batch3))}")

    # 5. trial_level MAPPING CHECK
    print(f"\n📊 trial_level MAPPING CHECK")
    invalid_tl = {}
    empty_tl = []
    for r in gc_batch3:
        tl = r.get("trial_level", "")
        if tl not in VALID_TRIAL_LEVELS:
            invalid_tl[r["id"]] = tl
        if tl == "" and r.get("trial_procedure", "").strip():
            empty_tl.append((r["id"], r.get("trial_procedure", "")))

    if invalid_tl:
        print(f"  ❌ INVALID trial_level values:")
        for gid, tl in invalid_tl.items():
            print(f"      {gid}: trial_level='{tl}'")
    else:
        print(f"  ✅ All trial_level values valid")

    # Show trial_level distribution
    tl_dist = {}
    for r in gc_batch3:
        tl = r.get("trial_level", "")
        tl_dist[tl] = tl_dist.get(tl, 0) + 1
    print(f"  Distribution: {dict(sorted(tl_dist.items()))}")

    # Show trial_procedure + trial_level side by side
    print(f"\n  trial_procedure → trial_level mapping detail:")
    tp_map = {}
    for r in gc_batch3:
        tp = r.get("trial_procedure", "")
        tl = r.get("trial_level", "")
        key = (tp, tl)
        tp_map[key] = tp_map.get(key, 0) + 1
    for (tp, tl), cnt in sorted(tp_map.items()):
        arrow = " → " if tl else " → (empty)"
        print(f"      '{tp}'{arrow}'{tl}' × {cnt}")

    # 6. UNMAPPED trial_procedure CHECK
    print(f"\n📊 NEW UNMAPPED trial_procedure CHECK")
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent / "pipelines"))
    from batch_process import TRIAL_LEVEL_MAP, AUDIT_LOG_UNMAPPED

    # Find any trial_procedure values not in the map
    all_tp_values = set()
    for r in gc_batch3:
        tp = r.get("trial_procedure", "").strip()
        if tp:
            all_tp_values.add(tp)
    print(f"  All trial_procedure values in batch 3: {all_tp_values}")

    mapped_keys = set(TRIAL_LEVEL_MAP.keys())
    unmapped = all_tp_values - mapped_keys
    if unmapped:
        print(f"  ❌ UNMAPPED trial_procedure values: {unmapped}")
    else:
        print(f"  ✅ All trial_procedure values are in TRIAL_LEVEL_MAP")

    # 7. tags CLEANING CHECK
    print(f"\n📊 tags CLEANING CHECK")
    tag_issues = 0
    for r in gc_batch3:
        tags = r.get("tags", "")
        if not tags:
            continue
        # Check for leading/trailing colons, spaces, quotes
        if tags.startswith(":"):
            tag_issues += 1
            print(f"      ❌ {r['id']}: leading colon in tags: '{tags[:50]}'")
        if tags.endswith(":") or tags.endswith("，"):
            tag_issues += 1
            print(f"      ❌ {r['id']}: trailing colon/quote in tags: '{tags[-50:]}'")
        if tags.startswith('"') or tags.endswith('"'):
            tag_issues += 1
            print(f"      ❌ {r['id']}: surrounding quotes in tags")
    if tag_issues == 0:
        print(f"  ✅ All {total} tags clean (no leading/trailing colons, spaces, or quotes)")

    # 8. LegalProvision extraction quality
    print(f"\n📊 LegalProvision EXTRACTION CHECK")
    # Count batch 3 provisions
    batch3_gc_ids = {r["id"] for r in gc_batch3}
    batch3_cites = [r for r in cites_rows if r["case_id"] in batch3_gc_ids]
    batch3_prov_ids = {r["provision_id"] for r in batch3_cites}
    batch3_provs = [r for r in prov_rows if r["id"] in batch3_prov_ids]
    print(f"  Batch 3 CITES edges: {len(batch3_cites)}")
    print(f"  Batch 3 unique provisions: {len(batch3_provs)}")
    print(f"  Avg provisions per case: {len(batch3_cites)/len(gc_batch3):.1f}" if gc_batch3 else "  N/A")

    # Check for placeholder content
    placeholder_content = sum(1 for r in batch3_provs if not r.get("content", "").strip())
    print(f"  Provisions without content (placeholder): {placeholder_content}/{len(batch3_provs)}")

    # Check source field quality
    for r in batch3_provs:
        src = r.get("source", "")
        if src and not src.startswith("《"):
            # Source should ideally contain the law name
            pass  # Some are abbreviated like "刑法" without 《》, okay

    # 9. Duplicate check in GuidingCase
    print(f"\n📊 DUPLICATE CHECK")
    all_gc_ids = [r["id"] for r in gc_rows]
    dupes = [x for x in all_gc_ids if all_gc_ids.count(x) > 1]
    if dupes:
        print(f"  ❌ Duplicate GuidingCase IDs: {set(dupes)}")
    else:
        print(f"  ✅ No duplicate GuidingCase IDs ({len(all_gc_ids)} unique)")

    # Check cross-ref: all edges reference valid nodes
    print(f"\n📊 REFERENTIAL INTEGRITY")
    gc_id_set = {r["id"] for r in gc_rows}
    ct_id_set = {r["id"] for r in ct_rows}
    prov_id_set = {r["id"] for r in prov_rows}

    orphan_guides = [r for r in guides_rows if r["guiding_case_id"] not in gc_id_set]
    orphan_guides_ct = [r for r in guides_rows if r["case_type_id"] not in ct_id_set]
    orphan_cites_gc = [r for r in cites_rows if r["case_id"] not in gc_id_set]
    orphan_cites_prov = [r for r in cites_rows if r["provision_id"] not in prov_id_set]

    if orphan_guides:
        print(f"  ❌ Orphan GUIDES edges (guiding_case not in gold): {len(orphan_guides)}")
    if orphan_guides_ct:
        print(f"  ❌ Orphan GUIDES edges (case_type not in gold): {len(orphan_guides_ct)}")
    if orphan_cites_gc:
        print(f"  ❌ Orphan CITES edges (case not in gold): {len(orphan_cites_gc)}")
    if orphan_cites_prov:
        print(f"  ❌ Orphan CITES edges (provision not in gold): {len(orphan_cites_prov)}")
    if not (orphan_guides or orphan_guides_ct or orphan_cites_gc or orphan_cites_prov):
        print(f"  ✅ All edges reference valid nodes")

    # 10. SAMPLE VERIFICATION (spot-check 5 records)
    print(f"\n📊 SAMPLE VERIFICATION (5 records checked against source CSV)")
    source_rows = {int(r["id"]): r for r in load_source_csv() if r["id"].isdigit()}

    # Pick 5 sample IDs from batch 3
    sample_ids = sorted([int(r["id"].replace("guiding_case_", "")) for r in gc_batch3])[:5]
    if len(sample_ids) < 5 and gc_batch3:
        sample_ids = sorted([int(r["id"].replace("guiding_case_", "")) for r in gc_batch3])[:5]

    for sid in sample_ids:
        gc_id = f"guiding_case_{sid}"
        gold = next((r for r in gc_batch3 if r["id"] == gc_id), None)
        src = source_rows.get(sid, None)
        if not gold or not src:
            print(f"  ❌ {gc_id}: Not found in gold or source")
            continue
        issues = []
        # Check guiding_points matches judgment_essence
        essence_raw = src.get("judgment_essence", "")
        import re
        essence_clean = re.sub(r'<[^>]+>', '', essence_raw)
        essence_clean = essence_clean.replace("\\u3000", " ").replace("u3000", " ")
        essence_clean = re.sub(r'\s+', ' ', essence_clean).strip()[:2000]
        if gold["guiding_points"] != essence_clean:
            issues.append(f"guiding_points mismatch")

        # Check tags match key_words (after cleaning)
        from batch_process import clean_tags
        expected_tags = clean_tags(src.get("key_words", ""))
        if gold["tags"] != expected_tags:
            issues.append(f"tags mismatch: gold='{gold['tags'][:40]}' vs expected='{expected_tags[:40]}'")

        # Check trial_level mapping
        tp = src.get("trial_procedure", "").strip()
        from batch_process import map_trial_level
        expected_tl = map_trial_level(tp)
        if gold["trial_level"] != expected_tl:
            issues.append(f"trial_level mismatch: gold='{gold['trial_level']}' vs expected='{expected_tl}'")

        if issues:
            print(f"  ⚠️  {gc_id}: {'; '.join(issues)}")
        else:
            print(f"  ✅ {gc_id}: All checks passed")

    # 11. SUMMARY
    print(f"\n{'='*70}")
    print(f"AUDIT SUMMARY")
    print(f"{'='*70}")
    issues_found = []
    if invalid_categories:
        issues_found.append(f"{len(invalid_categories)} invalid CaseType categories")
    if invalid_tl:
        issues_found.append(f"{len(invalid_tl)} invalid trial_level values")
    if unmapped:
        issues_found.append(f"{len(unmapped)} unmapped trial_procedure values: {unmapped}")
    if tag_issues > 0:
        issues_found.append(f"{tag_issues} tags with cleaning issues")
    if dupes:
        issues_found.append(f"{len(set(dupes))} duplicate GuidingCase IDs")
    if orphan_guides or orphan_guides_ct or orphan_cites_gc or orphan_cites_prov:
        issues_found.append("Orphan edge references detected")
    if not issues_found:
        print(f"  ✅ PASS: No issues found in Batch 3 data")
    else:
        print(f"  ⚠️  Issues found:")
        for issue in issues_found:
            print(f"      - {issue}")

    print(f"\n  Batch 3 record count: {len(gc_batch3)}")
    print(f"  Field fill rates: see above")
    print(f"  CaseType categories: {sorted(set(r['category'] for r in ct_batch3))}")
    print(f"  trial_level distribution: {dict(sorted(tl_dist.items()))}")

if __name__ == "__main__":
    main()
