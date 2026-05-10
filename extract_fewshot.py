"""
Extract few-shot candidates for v2.2 ontology using deepseek-chat.
Run for criminal and admin cases.
"""
import csv, json, os, re, sys
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/.hermes/.env'))
from openai import OpenAI

client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")

def clean_html(text):
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', text).strip()

def build_input(row):
    """Build input text from CSV row"""
    parts = [
        f"【案由分类】{row.get('case_type', '')}",
        f"【入库编号】{row.get('storage_no', '')}",
        f"【审判程序】{row.get('trial_procedure', '')}",
        f"【案例层级】{row.get('case_level', '')}",
        f"【关键词】{row.get('key_words', '')}",
        f"【基本案情】{clean_html(row.get('basic_facts', ''))}",
        f"【裁判理由】{clean_html(row.get('judgment_reason', ''))}",
        f"【裁判要旨】{clean_html(row.get('judgment_essence', ''))}",
        f"【相关法条和审级】{clean_html(row.get('related_info', ''))}",
    ]
    return '\n\n'.join(parts)

def extract_case(row, prompt_path, output_path, label):
    """Run extraction using the v2.2 prompt"""
    with open(prompt_path, encoding='utf-8') as f:
        prompt = f.read()
    
    text = build_input(row)
    rid = row.get('\ufeff"id"', row.get('id', ''))
    
    print(f"[{label}] Extracting ID={rid} ({row['case_type']})...")
    
    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": text}],
            max_tokens=8192,
            temperature=0.1,
            response_format={"type": "json_object"},
            timeout=240,
        )
        
        result = json.loads(resp.choices[0].message.content or "{}")
        
        # Save result
        save_record = {
            'id': rid,
            'case_type': row.get('case_type', ''),
            'storage_no': row.get('storage_no', ''),
            'court_name': row.get('court_name', ''),
            'input': text,
            'output': result,
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(save_record, f, ensure_ascii=False, indent=2)
        
        print(f"[{label}] ✓ Saved to {output_path}")
        print(f"  case_number: {[c.get('case_number','') for c in result.get('court_cases',[])]}")
        print(f"  provisions count: {len(result.get('legal_provisions',[]))}")
        print(f"  evidence count: {len(result.get('evidence',[]))}")
        print(f"  subjects count: {len(result.get('legal_subjects',[]))}")
        return result
        
    except Exception as e:
        print(f"[{label}] ✗ Error: {e}")
        return None

# Read CSV
with open('/root/remote-test/data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

# Build lookup by id
row_by_id = {}
for r in rows:
    rid = r.get('\ufeff"id"', r.get('id', ''))
    row_by_id[rid] = r

# Selected candidates
criminal_ids = ['4999', '2371', '6316']  # 保险诈骗, 受贿(有鉴定), 故意伤害(有鉴定+争议焦点)
admin_ids = ['2171', '2504', '3169']     # 行政赔偿, 行政处罚, 不履行XX职责(有鉴定)

criminal_outdir = '/root/remote-test/data_lake/fewshot_candidates'
admin_outdir = '/root/remote-test/data_lake/fewshot_candidates'
criminal_prompt = '/root/remote-test/ontology/prompts/auto_v5_criminal.txt'
admin_prompt = '/root/remote-test/ontology/prompts/auto_v5_admin.txt'

results = {}

# Extract criminal cases
print('\n' + '='*60)
print('EXTRACTING CRIMINAL CASES')
print('='*60)
for rid in criminal_ids:
    if rid in row_by_id:
        outpath = f'{criminal_outdir}/v2.2_criminal_{rid}.json'
        result = extract_case(row_by_id[rid], criminal_prompt, outpath, 'CRIMINAL')
        results[f'criminal_{rid}'] = result
    else:
        print(f'[CRIMINAL] ID={rid} not found in CSV')

# Extract admin cases
print('\n' + '='*60)
print('EXTRACTING ADMIN CASES')
print('='*60)
for rid in admin_ids:
    if rid in row_by_id:
        outpath = f'{admin_outdir}/v2.2_admin_{rid}.json'
        result = extract_case(row_by_id[rid], admin_prompt, outpath, 'ADMIN')
        results[f'admin_{rid}'] = result
    else:
        print(f'[ADMIN] ID={rid} not found in CSV')

print('\n' + '='*60)
print('EXTRACTION COMPLETE')
print('='*60)
