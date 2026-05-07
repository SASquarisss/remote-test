#!/usr/bin/env python3
"""Legal PM audit script for batch #1 Gold layer data."""
import csv
import json
import re
from collections import Counter, defaultdict

BASE = "/root/.hermes/hermes-agent/remote-test"

print("=" * 70)
print("📋 LEGAL PM AUDIT REPORT — Batch #1 (50 Gold Records)")
print("=" * 70)

# ===== 1. Load batch_state =====
with open(f"{BASE}/data/processed/batch_state.json") as f:
    batch = json.load(f)
print(f"\n📌 batch_state.json:")
print(f"   processed_ids count: {len(batch['processed_ids'])} (including extra: {batch['total_processed']})")
print(f"   IDs: {batch['processed_ids']}")

# ===== 2. Load all Gold CSVs =====
gold_files = {
    'GuidingCase': f"{BASE}/data_lake/gold/GuidingCase.csv",
    'Court': f"{BASE}/data_lake/gold/Court.csv",
    'CaseType': f"{BASE}/data_lake/gold/CaseType.csv",
    'LegalProvision': f"{BASE}/data_lake/gold/LegalProvision.csv",
    'edges_GUIDES_CASE_TYPE': f"{BASE}/data_lake/gold/edges_GUIDES_CASE_TYPE.csv",
    'edges_CITES': f"{BASE}/data_lake/gold/edges_CITES.csv",
}

data = {}
for name, path in gold_files.items():
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        data[name] = rows

# ===== 3. GuidingCase Audit =====
print(f"\n{'='*70}")
print("🔍 SECTION A: GUIDING CASE AUDIT")
print(f"{'='*70}")
gc = data['GuidingCase']
print(f"   Total records: {len(gc)}")

# Required fields per ontology
req_fields_gc = ['id', 'guiding_case_number', 'name', 'issuing_court_id', 'publication_date', 'guiding_points', 'binding_force']

# Field fill-rate
fill_rate = defaultdict(lambda: {'filled': 0, 'total': len(gc)})
for row in gc:
    for key in row:
        if key not in fill_rate:
            fill_rate[key] = {'filled': 0, 'total': len(gc)}
        if row[key].strip():
            fill_rate[key]['filled'] += 1

print(f"\n   📊 FIELD FILL RATE:")
for field in ['id', 'guiding_case_number', 'name', 'issuing_court_id', 'publication_date', 'guiding_points', 'binding_force', 'source_url', 'tags', 'trial_procedure', 'trial_level', 'source', 'desensitize', 'create_time', 'update_time']:
    info = fill_rate.get(field, {'filled': 0, 'total': len(gc)})
    pct = info['filled'] / info['total'] * 100 if info['total'] > 0 else 0
    status = "✅" if pct >= 90 else ("⚠️" if pct >= 50 else "❌")
    print(f"   {status} {field}: {info['filled']}/{info['total']} ({pct:.1f}%)")

# Binding force distribution
bf_dist = Counter(r.get('binding_force', '').strip() for r in gc)
print(f"\n   📊 BINDING FORCE DISTRIBUTION (expected: mandatory|persuasive|reference):")
for bf, cnt in bf_dist.most_common():
    print(f"      - '{bf}': {cnt}")

# Missing required fields
print(f"\n   ⚠️  MISSING REQUIRED FIELDS:")
for row in gc:
    rid = row.get('id', '?')
    for field in req_fields_gc:
        if field == 'id': continue
        if not row.get(field, '').strip():
            print(f"      - {rid}: missing {field}")

# publication_date specifically
empty_pub = [r for r in gc if not r.get('publication_date', '').strip()]
if empty_pub:
    print(f"\n   ❌ EMPTY publication_date ({len(empty_pub)} records):")
    for r in empty_pub:
        print(f"      - {r['id']} ({r.get('name','?')})")

# guiding_case_number check
print(f"\n   📊 GUIDING CASE NUMBER SAMPLES:")
for r in gc[:3]:
    print(f"      {r['id']}: {r.get('guiding_case_number','?')}")

# ===== 4. Court Audit =====
print(f"\n{'='*70}")
print("🔍 SECTION B: COURT AUDIT")
print(f"{'='*70}")
ct = data['Court']
print(f"   Total records: {len(ct)}")

court_names = [r.get('name', '') for r in ct]
court_levels = Counter(r.get('court_level', '') for r in ct)
print(f"\n   📊 COURT LEVELS (expected: supreme|high|intermediate|basic|special):")
for lv, cnt in court_levels.most_common():
    valid = "✓" if lv in ['supreme', 'high', 'intermediate', 'basic', 'special'] else "✗"
    print(f"      {valid} {lv}: {cnt}")

# district_id check
empty_dist = sum(1 for r in ct if not r.get('district_id', '').strip())
print(f"\n   ⚠️  Empty district_id: {empty_dist}/{len(ct)}")

# Duplicate court check
court_ids = [r.get('id','') for r in ct]
court_dup = [id for id, c in Counter(court_ids).items() if c > 1]
if court_dup:
    print(f"\n   ⚠️  DUPLICATE COURT IDs: {court_dup}")
    for did in court_dup:
        for r in ct:
            if r['id'] == did:
                print(f"      - {did}: {r['name']}, level={r['court_level']}")

# ===== 5. CaseType Audit =====
print(f"\n{'='*70}")
print("🔍 SECTION C: CASE TYPE AUDIT")
print(f"{'='*70}")
casetype = data['CaseType']
print(f"   Total records: {len(casetype)}")

# Category distribution
cat_dist = Counter(r.get('category', '') for r in casetype)
valid_cats = {'civil', 'criminal', 'administrative', 'ip', 'execution', 'state_compensation'}
print(f"\n   📊 CATEGORY DISTRIBUTION:")
for cat, cnt in cat_dist.most_common():
    valid = "✓" if cat in valid_cats else "✗ NOT IN ONTOLOGY"
    print(f"      {valid} '{cat}': {cnt}")

# level1 == level2 pattern
l1l2_same = sum(1 for r in casetype if r.get('level1','') == r.get('level2',''))
l1l2_diff = sum(1 for r in casetype if r.get('level1','') != r.get('level2',''))
print(f"\n   📊 LEVEL STRUCTURE:")
print(f"      level1 == level2: {l1l2_same}")
print(f"      level1 != level2: {l1l2_diff}")
if l1l2_diff > 0:
    print(f"      Cases where level1 != level2:")
    for r in casetype:
        if r.get('level1','') != r.get('level2',''):
            print(f"         - {r['id']}: {r['name']} | l1={r['level1']} l2={r['level2']}")

# ===== 6. LegalProvision Audit =====
print(f"\n{'='*70}")
print("🔍 SECTION D: LEGAL PROVISION AUDIT")
print(f"{'='*70}")
lp = data['LegalProvision']
print(f"   Total records: {len(lp)}")

for r in lp:
    print(f"\n   ID: {r['id']}")
    print(f"      law_id: {r.get('law_id', '❌ EMPTY')}")
    print(f"      article: {r.get('article', '❌ EMPTY')}")
    print(f"      paragraph: {r.get('paragraph', '') or '(empty)'}")
    print(f"      item: {r.get('item', '') or '(empty)'}")
    print(f"      content: {(r.get('content','') or '')[:100]}...")
    print(f"      status: {r.get('status', '(empty)')}")

# ===== 7. Edge Consistency =====
print(f"\n{'='*70}")
print("🔍 SECTION E: EDGE CONSISTENCY AUDIT")
print(f"{'='*70}")

gc_nodes = set(r['id'] for r in data['GuidingCase'])
ct_nodes = set(r['id'] for r in data['CaseType'])
lp_nodes = set(r['id'] for r in data['LegalProvision'])

# GUIDES_CASE_TYPE
edges_gct = data['edges_GUIDES_CASE_TYPE']
gct_gc_ids = set(r['guiding_case_id'] for r in edges_gct)
gct_ct_ids = set(r['case_type_id'] for r in edges_gct)

print(f"\n   📊 GUIDES_CASE_TYPE edges: {len(edges_gct)}")
print(f"      Unique guiding_case_ids: {len(gct_gc_ids)}")
print(f"      Unique case_type_ids: {len(gct_ct_ids)}")
print(f"      GuidingCase nodes: {len(gc_nodes)}")
print(f"      CaseType nodes: {len(ct_nodes)}")

orphan_gc = gct_gc_ids - gc_nodes
orphan_ct = gct_ct_ids - ct_nodes
no_edge_gc = gc_nodes - gct_gc_ids

if orphan_gc:
    print(f"      ❌ ORPHAN guiding_case_ids (no node): {orphan_gc}")
if orphan_ct:
    print(f"      ❌ ORPHAN case_type_ids (no node): {orphan_ct}")
if no_edge_gc:
    print(f"      ⚠️  GuidingCase nodes with no edge: {no_edge_gc}")
else:
    print(f"      ✅ All GuidingCase nodes have GUIDES_CASE_TYPE edges")

# CITES
edges_cites = data['edges_CITES']
print(f"\n   📊 CITES edges: {len(edges_cites)}")
for r in edges_cites:
    print(f"      case_id={r['case_id']}, provision_id={r.get('provision_id','?')}")
    case_in_nodes = r['case_id'] in gc_nodes
    prov_in_nodes = r.get('provision_id','') in lp_nodes
    print(f"         case exists in GuidingCase: {case_in_nodes}")
    print(f"         provision exists in LegalProvision: {prov_in_nodes}")

# ===== 8. Sample Cross-Validation from Raw CSV =====
print(f"\n{'='*70}")
print("🔍 SECTION F: RAW CSV CROSS-VALIDATION (5 SAMPLES)")
print(f"{'='*70}")

# We already read raw CSV data above - extract specific records
raw_path = f"{BASE}/data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv"
with open(raw_path, 'r', encoding='utf-8-sig') as f:
    raw_content = f.read()

# Parse raw CSV properly
raw_lines = raw_content.split('\r"')
# Reconstruct: first line is header
header_line = raw_lines[0].strip('"').split('","')
header_cols = [h.strip('"') for h in header_line]

samples_to_check = [
    ('2292', 'guiding_case_2292', '行政-不履行XX职责'),
    ('298', 'guiding_case_298', '民事-产品责任纠纷'),
    ('412', 'guiding_case_412', '民事-产品责任纠纷'),
    ('604', 'guiding_case_604', '民事-侵害商业秘密纠纷'),
    ('12931', 'guiding_case_12931', '刑事-故意伤害罪'),
]

for raw_id, gold_id, expected_type in samples_to_check:
    print(f"\n   🔎 Record: raw_id={raw_id} → gold_id={gold_id}")
    
    # Find in raw CSV
    found = None
    for entry in raw_lines:
        if entry.startswith(f'"{raw_id}"'):
            found = entry
            break
    
    if found:
        fields = found.split('","')
        # fields[0] = "2292, fields[3] = case_type
        raw_case_type = fields[3].strip('"') if len(fields) > 3 else '?'
        raw_court = fields[5].strip('"') if len(fields) > 5 else '?'
        raw_storage_no = fields[4].strip('"') if len(fields) > 4 else '?'
        print(f"      Raw case_type: {raw_case_type}")
        print(f"      Raw court: {raw_court}")
        print(f"      Raw storage_no: {raw_storage_no}")
    else:
        print(f"      ⚠️  NOT FOUND in raw CSV")
        raw_case_type = '?'
        raw_court = '?'
    
    # Find in Gold
    gold_row = None
    for r in data['GuidingCase']:
        if r['id'] == gold_id:
            gold_row = r
            break
    
    if gold_row:
        gold_name = gold_row.get('name', '?')
        gold_case_no = gold_row.get('guiding_case_number', '?')
        gold_court_id = gold_row.get('issuing_court_id', '?')
        gold_bf = gold_row.get('binding_force', '?')
        gold_pub = gold_row.get('publication_date', '?')
        
        # Find court name
        court_name = '?'
        for r in data['Court']:
            if r['id'] == gold_court_id:
                court_name = r.get('name', '?')
                break
        
        print(f"      Gold name: {gold_name}")
        print(f"      Gold guiding_case_no: {gold_case_no}")
        print(f"      Gold issuing_court: {court_name} ({gold_court_id})")
        print(f"      Gold binding_force: {gold_bf}")
        print(f"      Gold publication_date: {gold_pub}")
        
        # Verify
        issues = []
        if expected_type not in gold_name:
            issues.append(f"Case type mismatch: expected '{expected_type}' in name, got '{gold_name}'")
        if raw_court not in court_name and court_name != '?':
            issues.append(f"Court mismatch: raw='{raw_court}', gold='{court_name}'")
        if raw_storage_no != '?' and raw_storage_no != gold_case_no:
            issues.append(f"Storage_no mismatch: raw='{raw_storage_no}', gold='{gold_case_no}'")
        
        if issues:
            print(f"      ❌ ISSUES:")
            for iss in issues:
                print(f"         - {iss}")
        else:
            print(f"      ✅ Verified OK")

# ===== 9. Missing name field check =====
print(f"\n{'='*70}")
print("🔍 SECTION G: SUMMARY STATISTICS")
print(f"{'='*70}")

# Count how many processed batch IDs appear in Gold GuidingCase
batch_processed = set(str(i) for i in batch['processed_ids'])
gold_ids_short = set()
for r in data['GuidingCase']:
    # Extract numeric ID from guiding_case_NNNN
    m = re.search(r'guiding_case_(\d+)', r['id'])
    if m:
        gold_ids_short.add(m.group(1))

overlap = batch_processed & gold_ids_short
only_batch = batch_processed - gold_ids_short
only_gold = gold_ids_short - batch_processed

print(f"\n   Batch processed IDs: {len(batch_processed)}")
print(f"   Gold GuidingCase IDs (numeric): {len(gold_ids_short)}")
print(f"   Overlap: {len(overlap)}")
print(f"   In batch but not in Gold: {only_batch}")
print(f"   In Gold but not in batch: {only_gold}")

print(f"\n{'='*70}")
print("✅ AUDIT COMPLETE")
print(f"{'='*70}")
