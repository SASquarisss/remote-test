"""
Quality check on extracted results
"""
import json, re, os

criminal_files = [
    '/root/remote-test/data_lake/fewshot_candidates/v2.2_criminal_4999.json',
    '/root/remote-test/data_lake/fewshot_candidates/v2.2_criminal_2371.json',
    '/root/remote-test/data_lake/fewshot_candidates/v2.2_criminal_6316.json',
]

admin_files = [
    '/root/remote-test/data_lake/fewshot_candidates/v2.2_admin_2171.json',
    '/root/remote-test/data_lake/fewshot_candidates/v2.2_admin_2504.json',
    '/root/remote-test/data_lake/fewshot_candidates/v2.2_admin_3169.json',
]

def quality_check(path, label):
    print(f'\n{"="*60}')
    print(f'QUALITY CHECK: {label} ({os.path.basename(path)})')
    print(f'{"="*60}')
    
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    
    output = data.get('output', {})
    errors = []
    notes = []
    
    # 1. Check guiding_case
    gc = output.get('guiding_case', {})
    case_name = gc.get('guiding_case_name', '')
    if not case_name:
        errors.append('MISSING: guiding_case_name')
    elif '某' in case_name:
        notes.append(f'case_name contains "某": {case_name}')
    
    # 2. Check case_type
    ct = output.get('case_type', {})
    expected_cat = 'criminal' if 'criminal' in label else 'administrative'
    actual_cat = ct.get('category', '')
    if actual_cat != expected_cat:
        errors.append(f'WRONG category: {actual_cat} != {expected_cat}')
    
    # 3. Check court_cases
    court_cases = output.get('court_cases', [])
    if not court_cases:
        errors.append('MISSING: court_cases array is empty')
    else:
        for i, cc in enumerate(court_cases):
            cn = cc.get('case_number', '')
            if not cn:
                errors.append(f'MISSING: court_cases[{i}].case_number')
            elif '某' in cn:
                notes.append(f'court_cases[{i}].case_number contains "某": {cn}')
            
            fd = cc.get('filing_date', '')
            if not fd:
                errors.append(f'MISSING: court_cases[{i}].filing_date')
            
            drt = cc.get('dispute_resolution_type', '')
            if not drt:
                errors.append(f'MISSING: court_cases[{i}].dispute_resolution_type')
            
            coa = cc.get('cause_of_action', '')
            if not coa:
                errors.append(f'MISSING: court_cases[{i}].cause_of_action')
    
    # 4. Check legal_provisions
    lps = output.get('legal_provisions', [])
    if len(lps) < 2:
        errors.append(f'TOO FEW provisions: {len(lps)} (expected >= 2)')
    for i, lp in enumerate(lps):
        if not lp.get('article', ''):
            errors.append(f'MISSING article in provision[{i}]')
        if not lp.get('content', ''):
            errors.append(f'MISSING content in provision[{i}]')
        if not lp.get('citation_purpose', ''):
            errors.append(f'MISSING citation_purpose in provision[{i}]')
    
    # 5. Check evidence
    evs = output.get('evidence', [])
    if not evs:
        notes.append('No evidence extracted')
    for i, ev in enumerate(evs):
        if not ev.get('admission_status', ''):
            errors.append(f'MISSING admission_status in evidence[{i}]')
        if not ev.get('evidence_type', ''):
            errors.append(f'MISSING evidence_type in evidence[{i}]')
    
    # 6. Check judgment_results
    jrs = output.get('judgment_results', [])
    if not jrs:
        errors.append('MISSING: judgment_results is empty')
    for i, jr in enumerate(jrs):
        if not jr.get('reasoning', ''):
            errors.append(f'MISSING reasoning in judgment_results[{i}]')
        if not jr.get('case_number', ''):
            notes.append(f'judgment_results[{i}] missing case_number')
    
    # 7. Check case_summary
    cs = output.get('case_summary', {})
    if not cs.get('key_facts', ''):
        errors.append('MISSING: case_summary.key_facts')
    if not cs.get('disputed_issues', ''):
        errors.append('MISSING: case_summary.disputed_issues')
    if not cs.get('conclusion', ''):
        errors.append('MISSING: case_summary.conclusion')
    
    # 8. Check legal_subjects have roles
    subjects = output.get('legal_subjects', [])
    for i, sub in enumerate(subjects):
        if not sub.get('roles'):
            errors.append(f'MISSING roles for legal_subjects[{i}]: {sub.get("name","")}')
        for ri, role in enumerate(sub.get('roles', [])):
            if not role.get('role_code', ''):
                errors.append(f'MISSING role_code in legal_subjects[{i}].roles[{ri}]')
    
    # 9. Check legal_provision_elements
    lpe = output.get('legal_provision_elements', [])
    if not lpe:
        notes.append('No legal_provision_elements extracted')
    else:
        for i, el in enumerate(lpe):
            if el.get('provision_index', -1) < 0:
                errors.append(f'MISSING provision_index in legal_provision_elements[{i}]')
    
    print(f'  case_name: {case_name}')
    print(f'  case_type category: {actual_cat}')
    print(f'  court_cases: {len(court_cases)} cases')
    for cc in court_cases:
        print(f'    - {cc.get("case_number","?")} ({cc.get("trial_level","?")})')
    print(f'  provisions: {len(lps)}')
    print(f'  evidence: {len(evs)}')
    print(f'  subjects: {len(subjects)}')
    print(f'  judgment_results: {len(jrs)}')
    print(f'  legal_provision_elements: {len(lpe)}')
    
    if errors:
        print(f'\n  ❌ ERRORS ({len(errors)}):')
        for e in errors:
            print(f'    - {e}')
    else:
        print(f'\n  ✅ No errors!')
    
    if notes:
        print(f'\n  📝 Notes ({len(notes)}):')
        for n in notes:
            print(f'    - {n}')
    
    return len(errors) == 0

all_pass = True
for f in criminal_files:
    if not quality_check(f, 'CRIMINAL'):
        all_pass = False

for f in admin_files:
    if not quality_check(f, 'ADMIN'):
        all_pass = False

print(f'\n\n{"="*60}')
if all_pass:
    print('✅ ALL QUALITY CHECKS PASSED')
else:
    print('❌ SOME QUALITY CHECKS FAILED — review above')
print(f'{"="*60}')
