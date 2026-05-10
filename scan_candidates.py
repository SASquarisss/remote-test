import csv, re

with open('/root/remote-test/data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

def clean_html(text):
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', text).strip()

def count_signals(text):
    if not text:
        return 0
    signals = 0
    if re.search(r'鉴定|伤残|评估|鉴定机构', text):
        signals += 1
    if re.search(r'\d+[户人]', text):
        signals += 1
    if re.search(r'案件受理费|诉讼费', text):
        signals += 1
    if re.search(r'保险公司|交强险', text):
        signals += 1
    amounts = re.findall(r'\d+[万]?元', text)
    if len(amounts) >= 3:
        signals += 1
    if re.search(r'争议焦点|本案争议', text):
        signals += 1
    return signals

# Check top candidates in detail
top_ids = ['12931', '6316', '1797', '4999', '2955', '2371', '4527', '1835']

for r in rows:
    rid = r.get('\ufeff"id"', r.get('id', ''))
    if rid in top_ids:
        bf = clean_html(r.get('basic_facts', ''))
        jr = clean_html(r.get('judgment_reason', ''))
        je = clean_html(r.get('judgment_essence', ''))
        ri = clean_html(r.get('related_info', ''))
        all_text = ' '.join([bf, jr, je, ri])
        has_jianding = bool(re.search(r'鉴定|伤残|评估', all_text))
        has_insurance = bool(re.search(r'保险公司|交强险', all_text))
        has_feiyong = bool(re.search(r'案件受理费|诉讼费', all_text))
        has_qunti = bool(re.search(r'\d+[户人]', all_text))
        has_issue = bool(re.search(r'争议焦点|本案争议', all_text))
        amounts = re.findall(r'\d+[万]?元', all_text)
        
        print(f'=== ID={rid} | {r["case_type"]} | {r["storage_no"]} ===')
        print(f'  basic_facts len: {len(bf)}')
        print(f'  judgment_reason len: {len(jr)}')
        print(f'  Has 鉴定: {has_jianding}')
        print(f'  Has 保险: {has_insurance}')
        print(f'  Has 诉讼费: {has_feiyong}')
        print(f'  Has 群体: {has_qunti}')
        print(f'  Has 争议焦点: {has_issue}')
        print(f'  Amount patterns sample: {amounts[:10]}...' if len(amounts) > 10 else f'  Amount patterns: {amounts}')
        print(f'  Basic facts (first 200): {bf[:200]}')
        print()

# Now scan admin cases
print('=' * 60)
print('ADMIN CASES')
print('=' * 60)

admins = []
for r in rows:
    if r.get('case_type', '').startswith('行政'):
        rid = r.get('\ufeff"id"', r.get('id', ''))
        bf = clean_html(r.get('basic_facts', ''))
        jr = clean_html(r.get('judgment_reason', ''))
        je = clean_html(r.get('judgment_essence', ''))
        ri = clean_html(r.get('related_info', ''))
        all_text = ' '.join([bf, jr, je, ri])
        score = count_signals(all_text)
        
        ct = r.get('case_type', '')
        bonus = 0
        if '行政处罚' in ct: bonus += 2
        if '行政登记' in ct: bonus += 2
        if '行政赔偿' in ct: bonus += 2
        if '不履行' in ct: bonus += 1
        
        admins.append({
            'id': rid,
            'case_type': ct,
            'storage_no': r.get('storage_no', ''),
            'score': score,
            'bonus': bonus,
            'total': score + bonus,
            'bf_len': len(bf),
            'jr_len': len(jr),
        })

admins.sort(key=lambda x: -x['total'])

print('=== TOP ADMIN CANDIDATES ===')
for c in admins[:20]:
    print(f"ID={c['id']} | score={c['score']}+bonus={c['bonus']}={c['total']} | {c['case_type'][:50]} | {c['storage_no']} | facts={c['bf_len']}")

# Also check admin sub-types
print('\n=== ALL ADMIN SUB-TYPES ===')
from collections import Counter
ct_admin = Counter()
for r in rows:
    if r.get('case_type', '').startswith('行政'):
        ct_admin[r['case_type']] += 1
for k, v in ct_admin.most_common():
    print(f'  {k}: {v}')
