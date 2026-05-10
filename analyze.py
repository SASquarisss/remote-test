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
print(f"Total successful: {len(successful)}")

# binding_force
bf_counts = Counter()
cl_counts = Counter()
for rid, r in successful:
    gc = r['output'].get('guiding_case', {})
    bf_counts[gc.get('binding_force', 'MISSING')] += 1
    cl_counts[gc.get('case_level', 'MISSING')] += 1
print("binding_force:", dict(bf_counts))
print("case_level:", dict(cl_counts))

# Check case_level -> binding_force mapping
print("\n=== case_level -> binding_force mapping ===")
for rid, r in successful:
    gc = r['output'].get('guiding_case', {})
    cl = gc.get('case_level', '')
    bf = gc.get('binding_force', '')
    csv_r = csv_by_id.get(rid, {})
    raw_cl = csv_r.get('case_level', '')
    if cl == 'guiding_case' and bf != 'mandatory':
        print(f"  MISMATCH: row_id={rid}, cl={cl}, bf={bf}, raw={raw_cl}")
    if cl == 'typical_case' and bf != 'persuasive':
        print(f"  MISMATCH: row_id={rid}, cl={cl}, bf={bf}, raw={raw_cl}")

# Judges & Attorneys
je = sum(1 for rid, r in successful if not r['output'].get('judges', []))
jn = len(successful) - je
ae = sum(1 for rid, r in successful if not r['output'].get('attorneys', []))
an = len(successful) - ae
print(f"\njudges empty: {je}, non-empty: {jn}")
print(f"attorneys empty: {ae}, non-empty: {an}")

# Trial organizations
to_empty = sum(1 for rid, r in successful if not r['output'].get('trial_organizations', []))
print(f"trial_organizations empty: {to_empty}")

# Evidence
no_ev = sum(1 for rid, r in successful if not r['output'].get('evidence', []))
print(f"No evidence: {no_ev}")

# Provisions
no_prov = sum(1 for rid, r in successful if not r['output'].get('legal_provisions', []))
print(f"No provisions: {no_prov}")

# Court cases
cc_counts = Counter()
for rid, r in successful:
    cc_counts[len(r['output'].get('court_cases', []))] += 1
print(f"Court cases per record: {dict(sorted(cc_counts.items()))}")

# cause_of_action missing
no_coa = sum(1 for rid, r in successful if any(not cc.get('cause_of_action') for cc in r['output'].get('court_cases', [])))
print(f"Missing cause_of_action: {no_coa}")

# reasoning missing
no_reas = sum(1 for rid, r in successful if any(not jr.get('reasoning') for jr in r['output'].get('judgment_results', [])))
print(f"Missing reasoning: {no_reas}")

# Evidence admission/examination
no_ad = sum(1 for rid, r in successful for ev in r['output'].get('evidence', []) if not ev.get('admission_status'))
no_ex = sum(1 for rid, r in successful for ev in r['output'].get('evidence', []) if not ev.get('examination_status'))
print(f"Evidence missing admission_status: {no_ad}")
print(f"Evidence missing examination_status: {no_ex}")

# case_summary
no_kf = sum(1 for rid, r in successful if not r['output'].get('case_summary', {}).get('key_facts'))
no_di = sum(1 for rid, r in successful if not r['output'].get('case_summary', {}).get('disputed_issues'))
no_co = sum(1 for rid, r in successful if not r['output'].get('case_summary', {}).get('conclusion'))
has_am = sum(1 for rid, r in successful if r['output'].get('case_summary', {}).get('amount_involved'))
print(f"Missing key_facts: {no_kf}")
print(f"Missing disputed_issues: {no_di}")
print(f"Missing conclusion: {no_co}")
print(f"Has amount_involved: {has_am}")

# amount_involved values
print("\n=== amount_involved values ===")
for rid, r in successful:
    amt = r['output'].get('case_summary', {}).get('amount_involved', '')
    if amt:
        print(f"  row_id={rid}: {amt}")

# prosecutors
pe = sum(1 for rid, r in successful if not r['output'].get('prosecutors', []))
print(f"\nEmpty prosecutors: {pe}")

# Check how many cases have related_info with ##### (which often contains case level info)
print("\n=== related_info structure ===")
for r in all_rows[:5]:
    ri = r.get('related_info', '')
    if '#####' in ri:
        parts = ri.split('#####')
        print(f"  id={r['id']}: contains ##### (separator), {len(parts)} parts")
    else:
        print(f"  id={r['id']}: no separator, length={len(ri)}")
