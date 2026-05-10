import csv, re

with open('/root/remote-test/data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

def clean_html(text):
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', text).strip()

# Let's check more data on specific candidates
# For criminal: the best ones are 故意伤害 with 鉴定, and insurance fraud
# Let's look at ID=12931 (故意伤害, 未成年人), ID=4999 (保险诈骗), ID=6316 (故意伤害, 有争议焦点)
# ID=1797 (故意伤害, 有群体), ID=2371 (受贿, 有鉴定+多金额)

# Also check if there are any 交通肇事 cases with insurance
for r in rows:
    if r.get('case_type', '').startswith('刑事-交通肇事'):
        rid = r.get('\ufeff"id"', r.get('id', ''))
        bf = clean_html(r.get('basic_facts', ''))
        jr = clean_html(r.get('judgment_reason', ''))
        all_text = bf + ' ' + jr
        print(f'=== ID={rid} | {r["case_type"]} | {r["storage_no"]} ===')
        print(f'  facts len: {len(bf)}, reason len: {len(jr)}')
        has_jianding = bool(re.search(r'鉴定|伤残', all_text))
        has_insurance = bool(re.search(r'保险公司|交强险', all_text))
        has_amount = bool(re.search(r'\d+[万]?元', all_text))
        print(f'  鉴定: {has_jianding}, 保险: {has_insurance}, 金额: {has_amount}')
        print(f'  Basic facts (first 300): {bf[:300]}')
        print()

print('='*60)
print('CHECKING SPECIFIC CANDIDATES DEEPLY')
print('='*60)

# Deep check criminal top picks
for rid_check in ['12931', '4999', '6316', '1797', '2371', '1835']:
    for r in rows:
        rid = r.get('\ufeff"id"', r.get('id', ''))
        if rid == rid_check:
            bf = clean_html(r.get('basic_facts', ''))
            jr = clean_html(r.get('judgment_reason', ''))
            je = clean_html(r.get('judgment_essence', ''))
            ri = clean_html(r.get('related_info', ''))
            print(f'\\n\\n===== ID={rid_check} | {r["case_type"]} | {r["storage_no"]} =====')
            print(f'basic_facts:\\n{bf[:600]}')
            print(f'\\n---判决理由 (first 600)---\\n{jr[:600]}')
            print(f'\\n---裁判要旨---\\n{je[:300] if je else "NONE"}')
            print(f'\\n---相关法条---\\n{ri[:300] if ri else "NONE"}')
            break
