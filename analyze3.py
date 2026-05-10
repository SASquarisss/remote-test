import csv, json
from collections import Counter

with open('data/raw/civil_cases_only.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    all_rows = list(reader)

csv_by_id = {}
for r in all_rows:
    csv_by_id[r['id']] = r

# Check which CSV columns are actually USED by the prompt
print("="*80)
print("FIELD COVERAGE MATRIX")
print("="*80)
print(f"{'CSV Column':<30} {'In Prompt?':<15} {'In Output?':<15} {'Has Value?':<15}")
print("-"*75)

prompt_used = {
    'id': True, 'web_name': True, 'web_url': True, 'case_type': True, 
    'storage_no': True, 'court_name': False, 'key_words': True, 
    'trial_procedure': True, 'trial_year': True, 'case_level': True,
    'basic_facts': True, 'judgment_reason': True, 'judgment_essence': True,
    'related_info': True, 'related_law': False, 'related_judgment_body': False,
    'create_time': False, 'update_time': False, 'md5_value': False,
    'judgment_mean': True, 'dt': False
}

output_fields = {
    'id': True, 'web_name': True, 'case_type': True, 'storage_no': True,
    'key_words': True, 'trial_year': True
}

for col in list(all_rows[0].keys()):
    in_prompt = 'YES' if prompt_used.get(col, False) else 'NO'
    
    # Check if CSV column has values
    null_vals = ['\\N', '', None]
    non_null = sum(1 for r in all_rows if r.get(col) and r[col].strip() not in null_vals)
    has_val = f'{non_null}/{len(all_rows)}'
    
    # Map to output fields
    output_mapping = {
        'id': 'row_id in input', 'web_name': 'guiding_case_name', 
        'web_url': 'source_url', 'case_type': 'case_type', 
        'storage_no': 'storage_no', 'court_name': 'court_cases[].court.name',
        'key_words': 'key_words', 'trial_procedure': 'trial_procedure',
        'trial_year': 'publication_date', 'case_level': 'case_level/binding_force',
        'basic_facts': 'key_facts/reasoning', 'judgment_reason': 'reasoning/evidence',
        'judgment_essence': 'guiding_points', 'related_info': 'legal_provisions/case_numbers',
        'related_law': '(ignored)', 'related_judgment_body': '(ignored)',
        'judgment_mean': 'judgment_mean', 
        'create_time': '(metadata)', 'update_time': '(metadata)',
        'md5_value': '(metadata)', 'dt': '(metadata)'
    }
    in_output = output_mapping.get(col, '(ignored)')
    
    print(f"{col:<30} {in_prompt:<15} {in_output:<15} {has_val:<15}")

# Count records that have evidence info in judgment_reason but NOT extracted
print("\n\n=== Lost mediation-specific info in 多元解纷 cases ===")
multi = [r for r in all_rows if '多元解纷' in r.get('web_name', '')]
for r in multi[:5]:
    jr = r.get('judgment_reason', '')
    # Check what rich info is in the judgment_reason but lost
    key_info_types = []
    if '调解员' in jr or '调解小组' in jr:
        key_info_types.append('调解员信息')
    if '赔偿' in jr:
        key_info_types.append('赔偿金额/方式')
    if '鉴定' in jr:
        key_info_types.append('鉴定/评估')
    if '总对总' in jr:
        key_info_types.append('总对总调解机制')
    if '社区' in jr or '住建' in jr:
        key_info_types.append('多部门联动')
    if '期' in jr and ('护理' in jr or '误工' in jr):
        key_info_types.append('三期鉴定')
    if '人数' in jr or '户' in jr or '位' in jr:
        key_info_types.append('群体人数')
    if key_info_types:
        print(f"  id={r['id']}: {', '.join(key_info_types)}")

# Check what judgment_mean looks like (all null vs some present)
print("\n\n=== judgment_mean actual content search ===")
jm_count = 0
for r in all_rows:
    jm = r.get('judgment_mean', '')
    if jm and jm.strip() not in ['\\N', '']:
        jm_count += 1
        print(f"  id={r['id']}: {jm[:200]}")
print(f"Total with judgment_mean: {jm_count}")
