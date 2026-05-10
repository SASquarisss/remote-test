"""
Check the raw related_info for criminal_2371 to see what provisions are available
"""
import csv, re

with open('/root/remote-test/data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

def clean_html(text):
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', text).strip()

for rid_check in ['2371']:
    for r in rows:
        rid = r.get('\ufeff"id"', r.get('id', ''))
        if rid == rid_check:
            print(f'=== ID={rid_check} | {r["case_type"]} ===')
            ri = clean_html(r.get('related_info', ''))
            rl = clean_html(r.get('related_law', ''))
            print(f'related_info:\n{ri}')
            print(f'\nrelated_law:\n{rl}')
            break

# Check what the extracted output looks like for 2371
print('\n\n=== Looking for provisions in judgment_reason ===')
for r in rows:
    rid = r.get('\ufeff"id"', r.get('id', ''))
    if rid == '2371':
        jr = clean_html(r.get('judgment_reason', ''))
        # Find all law references
        law_refs = re.findall(r'《[^》]+》[^，。]*[条款项]', jr)
        print(f'Law references in judgment_reason:')
        for lr in law_refs:
            print(f'  - {lr}')
        break
