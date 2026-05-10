import csv, re

with open('/root/remote-test/data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

def clean_html(text):
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', text).strip()

for rid_check in ['4078', '3790', '547']:
    for r in rows:
        rid = r.get('\ufeff"id"', r.get('id', ''))
        if rid == rid_check:
            bf = clean_html(r.get('basic_facts', ''))
            jr = clean_html(r.get('judgment_reason', ''))
            all_text = bf + ' ' + jr
            has_jianding = bool(re.search(r'鉴定|伤残|评估', all_text))
            has_insurance = bool(re.search(r'保险公司|交强险', all_text))
            amounts = len(re.findall(r'\d+[万]?元', all_text))
            has_qunti = bool(re.search(r'\d+[户人]', all_text))
            has_feiyong = bool(re.search(r'案件受理费|诉讼费', all_text))
            
            print(f'ID={rid} | {r["case_type"]} ')
            print(f'  Has 鉴定: {has_jianding}')
            print(f'  Has 保险: {has_insurance}')
            print(f'  Amount count: {amounts}')
            print(f'  Has 群体: {has_qunti}')
            print(f'  Has 诉讼费: {has_feiyong}')
            print(f'  bf_len: {len(bf)}, jr_len: {len(jr)}')
            print(f'  basic_facts[:200]: {bf[:200]}')
            print()
            break
