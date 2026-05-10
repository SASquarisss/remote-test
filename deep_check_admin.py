import csv, re

with open('/root/remote-test/data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

def clean_html(text):
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', text).strip()

# Deep check admin top picks
for rid_check in ['2171', '4017', '3960', '2504', '1660', '3966', '3169']:
    for r in rows:
        rid = r.get('\ufeff"id"', r.get('id', ''))
        if rid == rid_check:
            bf = clean_html(r.get('basic_facts', ''))
            jr = clean_html(r.get('judgment_reason', ''))
            je = clean_html(r.get('judgment_essence', ''))
            ri = clean_html(r.get('related_info', ''))
            rl = clean_html(r.get('related_law', ''))
            print(f'\n\n===== ID={rid_check} | {r["case_type"]} | {r["storage_no"]} =====')
            print(f'basic_facts (first 500):\n{bf[:500]}')
            print(f'\n---判决理由 (first 500)---\n{jr[:500]}')
            print(f'\n---裁判要旨 (first 300)---\n{je[:300] if je else "NONE"}')
            print(f'\n---相关法条---\n{ri[:300] if ri else "NONE"}')
            print(f'\n---related_law---\n{rl[:300] if rl else "NONE"}')
            break
