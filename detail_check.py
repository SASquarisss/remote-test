"""
Detailed quality check - re-run with correct category comparison
"""
import json, os

files = [
    ('CRIMINAL', '/root/remote-test/data_lake/fewshot_candidates/v2.2_criminal_4999.json'),
    ('CRIMINAL', '/root/remote-test/data_lake/fewshot_candidates/v2.2_criminal_2371.json'),
    ('CRIMINAL', '/root/remote-test/data_lake/fewshot_candidates/v2.2_criminal_6316.json'),
    ('ADMIN', '/root/remote-test/data_lake/fewshot_candidates/v2.2_admin_2171.json'),
    ('ADMIN', '/root/remote-test/data_lake/fewshot_candidates/v2.2_admin_2504.json'),
    ('ADMIN', '/root/remote-test/data_lake/fewshot_candidates/v2.2_admin_3169.json'),
]

for label, path in files:
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    
    output = data['output']
    expected_cat = 'criminal' if 'CRIMINAL' == label else 'administrative'
    actual_cat = output.get('case_type', {}).get('category', '')
    
    print(f'\n{"="*60}')
    print(f'{label}: {os.path.basename(path)}')
    print(f'  Case: {output.get("guiding_case",{}).get("guiding_case_name","?")}')
    print(f'  Category: {actual_cat} (expected: {expected_cat}) → {"✅" if actual_cat == expected_cat else "❌"}')
    
    # Court cases detail
    for cc in output.get('court_cases', []):
        print(f'  Case: {cc.get("case_number","?")}')
        print(f'    Filing: {cc.get("filing_date","?")} | Status: {cc.get("status","?")}')
        print(f'    Trial: {cc.get("trial_level","?")}/{cc.get("trial_procedure","?")}')
        print(f'    Court: {cc.get("court",{}).get("name","?")} ({cc.get("court",{}).get("court_level","?")})')
        print(f'    DR type: {cc.get("dispute_resolution_type","?")} | Cause: {cc.get("cause_of_action","?")}')
        print(f'    Party count: {cc.get("party_count","?")}')
    
    # Provisions
    lps = output.get('legal_provisions', [])
    print(f'  Provisions ({len(lps)}):')
    for lp in lps:
        a = lp.get('article','')
        s = lp.get('statute','')
        c = lp.get('content','')[:60]
        print(f'    - {s} art.{a} ..."{c}..." purpose={lp.get("citation_purpose","?")}')
    
    # Evidence
    evs = output.get('evidence', [])
    print(f'  Evidence ({len(evs)}):')
    for ev in evs:
        print(f'    - type={ev.get("evidence_type","?")} admission={ev.get("admission_status","?")} exam={ev.get("examination_status","?")} key={ev.get("is_key_evidence","?")} expert_inst={ev.get("expert_institution","")}')
    
    # Subjects
    subs = output.get('legal_subjects', [])
    print(f'  Subjects ({len(subs)}):')
    for sub in subs:
        roles_str = ','.join([f"{r.get('role_code','?')}({r.get('role_name','?')})" for r in sub.get('roles',[])])
        print(f'    - {sub.get("name","?")} [{sub.get("subject_type","?")}] roles: {roles_str}')
    
    # Judgment results
    jrs = output.get('judgment_results', [])
    print(f'  Judgment results ({len(jrs)}):')
    for jr in jrs:
        print(f'    - type={jr.get("result_type","?")} case={jr.get("case_number","?")}')
        print(f'      cost: {jr.get("cost_allocation","?")}')
        print(f'      reasoning: {jr.get("reasoning","")[:100]}...')
        print(f'      specific: {jr.get("specific_judgment","")[:100]}...')
    
    # Summary
    cs = output.get('case_summary', {})
    print(f'  Summary:')
    print(f'    Amount: {cs.get("amount_involved","?")} | Claim: {cs.get("claim_amount","?")} | Judgment: {cs.get("judgment_amount","?")}')
    print(f'    Key facts: {cs.get("key_facts","")[:100]}...')
    print(f'    Disputed issues: {cs.get("disputed_issues","")[:100]}...')
    
    # Legal provision elements
    lpe = output.get('legal_provision_elements', [])
    print(f'  Provision elements ({len(lpe)}):')
    for el in lpe:
        print(f'    - provision_index={el.get("provision_index","?")} type={el.get("element_type","?")} art={el.get("article","?")}')
    
    # Prosecutors / Judges / Attorneys / Trial orgs
    print(f'  Judges: {len(output.get("judges",[]))}')
    print(f'  Prosecutors: {len(output.get("prosecutors",[]))}')
    print(f'  Attorneys: {len(output.get("attorneys",[]))}')
    print(f'  Trial orgs: {len(output.get("trial_organizations",[]))}')
