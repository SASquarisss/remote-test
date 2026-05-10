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

# =========================================
# Semantic Coverage Analysis
# =========================================

# 1. Check what's in related_info besides laws/case references
print("="*80)
print("SEMANTIC COVERAGE ANALYSIS")
print("="*80)

# Check related_info content patterns
print("\n=== related_info content patterns ===")
law_refs = 0
case_refs = 0
both = 0
for r in all_rows:
    ri = r.get('related_info', '')
    if ri and ri.strip() not in ['\\N', '']:
        has_law = ('法' in ri or '条例' in ri or '规则' in ri)
        has_case = ('号' in ri and ('审' in ri or '判决' in ri))
        if has_law and has_case:
            both += 1
        elif has_law:
            law_refs += 1
        elif has_case:
            case_refs += 1
print(f"  Only laws: {law_refs}")
print(f"  Only case references: {case_refs}")
print(f"  Both laws and cases: {both}")
print(f"  Total non-null: {law_refs + case_refs + both}")

# 2. What the prompt uses from CSV fields
print("\n=== Prompt usage of CSV fields ===")
print("""
Used in prompt:
  - id (row_id)
  - web_name (guiding_case_name generation)
  - case_type (case_type mapping) 
  - storage_no (storage_no)
  - court_name (via basic_facts)
  - key_words (key_words)
  - trial_procedure (trial_procedure)
  - trial_year (publication_date)
  - case_level (case_level, binding_force)
  - basic_facts (fact extraction)
  - judgment_reason (reasoning, evidence, causes)
  - judgment_essence (guiding_points)
  - related_info (laws, case numbers)
  - judgment_mean (direct pass-through)
  - web_url (source_url)

NOT used directly:
  - related_law (nearly all empty)
  - related_judgment_body (all empty)
  - create_time (metadata)
  - update_time (metadata)  
  - md5_value (metadata)
  - dt (metadata partition)
""")

# 3. Check multi-source case: what info is embedded in related_info
print("\n=== related_info depth analysis (sample 5) ===")
for r in all_rows[:5]:
    ri = r.get('related_info', '')
    if ri and ri.strip() not in ['\\N', '']:
        print(f"\n  id={r['id']}:")
        print(f"  Content preview: {ri[:400]}")

# 4. Check dispute_resolution_type usage (mediation cases)
print("\n=== dispute_resolution_type usage ===")
drt_counts = Counter()
for rid, r in successful:
    for cc in r['output'].get('court_cases', []):
        drt = cc.get('dispute_resolution_type', None)
        if drt:
            drt_counts[drt] += 1
print(f"  dispute_resolution_type distribution: {dict(drt_counts)}")

# 5. Check for mediation-specific info that's lost
print("\n=== Mediation/多元解纷 cases special analysis ===")
multi_resolve = [r for r in all_rows if '多元解纷' in r.get('web_name', '')]
print(f"  Total 多元解纷 cases: {len(multi_resolve)}")
for r in multi_resolve[:3]:
    print(f"\n  id={r['id']}, case_type={r['case_type']}")
    print(f"  trial_procedure={r['trial_procedure']}, trial_year={r['trial_year']}")
    bf = r.get('basic_facts', '')[:150]
    jr = r.get('judgment_reason', '')[:150]
    print(f"  basic_facts: {bf}...")
    print(f"  judgment_reason: {jr}...")
    # Check what the LLM extracted
    rec = records.get(r['id'], {})
    if rec.get('output'):
        cs = rec['output'].get('case_summary', {})
        print(f"  LLM key_facts: {cs.get('key_facts', '')[:150]}...")

# 6. Check for amount_involved in source data vs extracted
print("\n\n=== Amount/赔偿金额 in source data ===")
amount_in_source = 0
for r in all_rows:
    bf = r.get('basic_facts', '')
    jr = r.get('judgment_reason', '')
    if any(kw in bf+jr for kw in ['元', '赔偿', '标的额', '金额']):
        amount_in_source += 1
print(f"  Cases mentioning amounts in source: ~{amount_in_source}/{len(all_rows)}")

# 7. Check judgment_date / judgment_date mapping
print("\n=== judgment_date extraction ===")
has_jd = 0
no_jd = 0
for rid, r in successful:
    for cc in r['output'].get('court_cases', []):
        if cc.get('judgment_date'):
            has_jd += 1
        else:
            no_jd += 1
print(f"  court_cases with judgment_date: {has_jd}")
print(f"  court_cases without judgment_date: {no_jd}")

# 8. Check guiding_case_number extraction (指导性案例编号)
print("\n=== guiding_case_number ===")
has_gcn = 0
no_gcn = 0
for rid, r in successful:
    gcn = r['output'].get('guiding_case', {}).get('guiding_case_number', '')
    if gcn and gcn.strip():
        has_gcn += 1
    else:
        no_gcn += 1
print(f"  With guiding_case_number: {has_gcn}")
print(f"  Without: {no_gcn}")

# Check what JSON output schema elements are always present
print("\n=== Key output fields always extracted ===")
fields_to_check = ['guiding_case', 'case_type', 'court_cases', 'legal_subjects', 
                   'legal_provisions', 'judgment_results', 'case_summary']
for fld in fields_to_check:
    present = sum(1 for rid, r in successful if r['output'].get(fld))
    print(f"  {fld}: {present}/{len(successful)}")

flds_often_empty = ['attorneys', 'judges', 'prosecutors', 'trial_organizations', 
                    'legal_provision_elements', 'evidence']
for fld in flds_often_empty:
    non_empty = sum(1 for rid, r in successful if r['output'].get(fld) and len(r['output'][fld]) > 0)
    print(f"  {fld} (non-empty): {non_empty}/{len(successful)}")

# 9. Check specific judgment details - amount_in_source vs amount_in_output
print("\n=== Judgment result types ===")
result_types = Counter()
for rid, r in successful:
    for jr in r['output'].get('judgment_results', []):
        result_types[jr.get('result_type', 'MISSING')] += 1
print(f"  Result types: {dict(result_types)}")

# 10. Check if specific_judgment has compensation info
print("\n=== specific_judgment compensation info ===")
comp_patterns = ['赔偿', '元', '支付', '返还']
comp_count = 0
no_comp = 0
for rid, r in successful:
    for jr in r['output'].get('judgment_results', []):
        sj = jr.get('specific_judgment', '')
        if any(p in sj for p in comp_patterns):
            comp_count += 1
        else:
            no_comp += 1
print(f"  With compensation info: {comp_count}")
print(f"  Without: {no_comp}")

# 11. Check dispute_resolution_type - only mediation cases get it?
print("\n=== dispute_resolution_type per web_name ===")
drt_by_web = Counter()
for rid, r in successful:
    web = r['input'].get('web_name', '')
    for cc in r['output'].get('court_cases', []):
        drt = cc.get('dispute_resolution_type', 'NOT_SET')
        if drt:
            drt_by_web[(web[:10], drt)] += 1
print(f"  dispute_resolution_type by source: {dict(drt_by_web)}")

# 12. Check for civil-specific attributes in ontology
print("\n=== Ontology civil-specific attributes check ===")
print("""
Ontology has these civil-relevant fields:
- CourtCase.claim_amount (optional) - NOT in LLM output schema
- CaseSummary.amount_involved (optional) - IN output schema, used
- JudgmentResult.compensation_amount (optional) - NOT in LLM output schema
- JudgmentResult.reasoning - IN output schema, used
- DisputeFocus - mapped via disputed_issues in case_summary
- Evidence - IN output schema
- SentencingStandard.standard_type = civil_compensation - NOT used

Missing from ontology:
- 调解具体情况 (mediation details, mediator info)
- 执行情况 (enforcement status/details)
- Multi-party dispute counts (群体性案件人数)
- 审级对应关联关系 explicit link (appeals_to relation in ontology but not in output)
- Insurance info (保险公司参与情况)
- 鉴定/评估信息 (appraisal/evaluation info)
""")

# 13. Check LPE (legal_provision_elements) coverage
print("\n=== Legal Provision Elements ===")
lpe_total = 0
lpe_records = 0
for rid, r in successful:
    lpes = r['output'].get('legal_provision_elements', [])
    if lpes:
        lpe_records += 1
        lpe_total += len(lpes)
print(f"  Records with LPEs: {lpe_records}/{len(successful)}")
print(f"  Total LPEs: {lpe_total}")
