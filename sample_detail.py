import csv, json
from collections import Counter

with open('data/raw/civil_cases_only.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    all_rows = list(reader)

csv_by_id = {}
for r in all_rows:
    csv_by_id[r['id']] = r

with open('data_lake/extracted_v5_civil_full.jsonl', 'r', encoding='utf-8') as f:
    records = {}
    for line in f:
        r = json.loads(line)
        records[r['row_id']] = r

successful = [(rid, r) for rid, r in records.items() if r.get('output') and r['output']]

# Pick diverse samples
# Strategy: diverse case_types, both web_names, high and low scores
# Find specific candidates
def get_score(rid, r):
    if 'eval' in r and r['eval']:
        return r['eval'].get('score', 0)
    return 100

# Group by web_name and score
court_samples = [r for r in successful if r[1]['input'].get('web_name') == '人民法院案例库']
duoyuan_samples = [r for r in successful if '多元解纷' in r[1]['input'].get('web_name', '')]

# Get high and low scored from each
def pick_diverse(records_list, n):
    # Pick diverse case_types
    seen_types = set()
    result = []
    for rid, r in records_list:
        ct = r['input'].get('case_type', '')
        if ct not in seen_types:
            result.append((rid, r))
            seen_types.add(ct)
            if len(result) >= n:
                break
    return result

court_diverse = pick_diverse(court_samples, 8)
duoyuan_diverse = pick_diverse(duoyuan_samples, 7)

# Also add low-scored
low_scored = sorted(successful, key=lambda x: get_score(x[0], x[1]))[:6]

all_chosen_ids = set()
samples = []

for rid, r in court_diverse + duoyuan_diverse:
    if rid not in all_chosen_ids:
        samples.append((rid, r))
        all_chosen_ids.add(rid)

for rid, r in low_scored:
    if rid not in all_chosen_ids:
        samples.append((rid, r))
        all_chosen_ids.add(rid)

# Print sample details
print(f"Selected {len(samples)} samples:")
for rid, r in samples:
    inp = r['input']
    out = r['output']
    gc = out.get('guiding_case', {})
    cs = out.get('case_summary', {})
    jrs = out.get('judgment_results', [])
    evs = out.get('evidence', [])
    provs = out.get('legal_provisions', [])
    lpes = out.get('legal_provision_elements', [])
    
    score = get_score(rid, r)
    csv_r = csv_by_id.get(rid, {})
    
    print(f"\n{'='*80}")
    print(f"row_id={rid}")
    print(f"  web_name: {inp.get('web_name')}")
    print(f"  case_type: {inp.get('case_type')}")
    print(f"  score: {score}")
    print(f"  case_level (raw): {csv_r.get('case_level')}")
    print(f"  guiding_case_name: {gc.get('guiding_case_name')}")
    print(f"  binding_force: {gc.get('binding_force')}")
    print(f"  trial_procedure: {gc.get('trial_procedure')}")
    print(f"  court_cases: {len(out.get('court_cases', []))} cases")
    for cc in out.get('court_cases', []):
        print(f"    - {cc.get('case_number')} | {cc.get('trial_level')} | {cc.get('court', {}).get('name')} | {cc.get('cause_of_action')}")
    print(f"  legal_subjects: {len(out.get('legal_subjects', []))}")
    print(f"  evidence: {len(evs)} items")
    print(f"  legal_provisions: {len(provs)} items")
    print(f"  LPEs: {len(lpes)} items")
    print(f"  judges: {len(out.get('judges', []))}")
    print(f"  attorneys: {len(out.get('attorneys', []))}")
    print(f"  trial_orgs: {len(out.get('trial_organizations', []))}")
    print(f"  amount_involved: {cs.get('amount_involved', '(empty)')}")
    print(f"  Source key fields (preview):")
    print(f"    basic_facts: {csv_r.get('basic_facts', '')[:150]}...")
    print(f"    judgment_reason: {csv_r.get('judgment_reason', '')[:150]}...")
    print(f"    related_info: {csv_r.get('related_info', '')[:150]}...")
    jm = csv_r.get('judgment_mean', '')
    jm_present = bool(jm and jm.strip() not in ['\\N', ''])
    print(f"    judgment_mean: {'[PRESENT]' if jm_present else '[EMPTY]'}")
    print(f"  Missing/Omitted items:")
    if not out.get('judges'):
        print(f"    [MISS] judges array empty")
    if not out.get('attorneys'):
        print(f"    [MISS] attorneys array empty")
    if not out.get('trial_organizations'):
        print(f"    [MISS] trial_organizations empty")
    if not evs:
        print(f"    [MISS] evidence array empty")
    if not provs:
        print(f"    [MISS] legal_provisions empty")
    monetary_kw = ['元', '赔偿', '标的']
    if not cs.get('amount_involved') and any(kw in (csv_r.get('basic_facts','') + csv_r.get('judgment_reason','')) for kw in monetary_kw):
        print(f"    [OMIT] amount_involved not extracted despite monetary info in source")
    # Check if reasoning covers key info
    for jr in jrs[:1]:
        if jr.get('reasoning', ''):
            print(f"    [OK] reasoning present ({len(jr['reasoning'])} chars)")
