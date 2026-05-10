"""
Try one more criminal candidate with more provisions - 受贿罪 is a bit sparse.
Let's check if 故意伤害 with more content works better, or try ID=1797 which has more content.
Also try a 诈骗 case with amounts.
"""
import csv, re, json, os
from dotenv import load_dotenv

load_dotenv(os.path.expanduser('~/.hermes/.env'))
from openai import OpenAI

client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")

def clean_html(text):
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', text).strip()

def build_input(row):
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
        
        print(f"[{label}] ✓ Saved")
        print(f"  case_number: {[c.get('case_number','') for c in result.get('court_cases',[])]}")
        print(f"  provisions: {len(result.get('legal_provisions',[]))}")
        print(f"  evidence: {len(result.get('evidence',[]))}")
        return result
        
    except Exception as e:
        print(f"[{label}] ✗ Error: {e}")
        return None

with open('/root/remote-test/data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))

row_by_id = {}
for r in rows:
    rid = r.get('\ufeff"id"', r.get('id', ''))
    row_by_id[rid] = r

# Try criminal_1797 (故意伤害, 有鉴定, 群体, 金额) as a better candidate
# Already extracted: 4999 (保险诈骗 - good), 2371 (受贿 - only 1 provision), 6316 (故意伤害 - has X in case number)

outdir = '/root/remote-test/data_lake/fewshot_candidates'
criminal_prompt = '/root/remote-test/ontology/prompts/auto_v5_criminal.txt'

# Try 1797 which has 鉴定, 群体(X人), and explicit amounts
extract_case(row_by_id['1797'], criminal_prompt, f'{outdir}/v2.2_criminal_1797.json', 'CRIMINAL-1797')
