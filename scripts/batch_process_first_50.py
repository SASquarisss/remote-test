#!/usr/bin/env python3
"""
第一批50条数据处理主脚本
从CSV读取最早的50条 → LLM提取 → 正则fallback → 映射到Gold层CSV → batch_state.json
"""
import csv
import json
import os
import re
import sys
import time
import hashlib
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.text_compressor import compress_for_llm

# ============ 路径配置 ============
BASE_DIR = Path(__file__).parent.parent
RAW_CSV = BASE_DIR / "data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv"
GOLD_DIR = BASE_DIR / "data_lake/gold"
PROMPT_FILE = BASE_DIR / "scripts/prompts/guiding_case_ontology_aligned.txt"
BATCH_STATE_FILE = BASE_DIR / "data_lake/batch_state.json"
BATCH_SIZE = 50

# API配置
BASE_URL = "https://api.deepseek.com/v1"
MODEL = "deepseek-chat"
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# Also try loading from .env file
if not API_KEY:
    env_path = Path.home() / ".hermes" / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DEEPSEEK_API_KEY="):
                    API_KEY = line.split("=", 1)[1].strip()
                    break

# ============ 加载prompt模板 ============
def load_prompt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

PROMPT_TEMPLATE = load_prompt(PROMPT_FILE)

# ============ CSV列定义（Gold层输出） ============

GUIDING_CASE_COLS = ["id", "guiding_case_number", "name", "issuing_court_id", 
                     "publication_date", "guiding_points", "binding_force",
                     "source_url", "tags", "trial_procedure", "trial_level",
                     "source", "desensitize", "create_time", "update_time"]

COURT_COLS = ["id", "name", "org_type", "credit_code", "court_level", "district_id"]

CASE_TYPE_COLS = ["id", "code", "name", "category", "level1", "level2"]

LEGAL_PROVISION_COLS = ["id", "law_id", "article", "paragraph", "item", "content", "status"]

COURT_CASE_COLS = ["id", "case_number", "filing_date", "court_id", "case_type_id",
                   "trial_level", "status"]

PERSON_COLS = ["id", "name"]

ORG_COLS = ["id", "name", "org_type", "credit_code"]

EDGES_CITES_COLS = ["case_id", "provision_id", "citation_position", "citation_purpose"]
EDGES_GUIDES_CASE_TYPE_COLS = ["guiding_case_id", "case_type_id"]
EDGES_INVOLVES_COLS = ["case_id", "subject_id", "role_code", "role_name"]
EDGES_HAS_CASE_TYPE_COLS = ["case_id", "case_type_id"]
EDGES_HEARD_BY_COLS = ["case_id", "court_id"]

# ============ 正则fallback：法条提取 ============
LAW_PATTERNS = [
    # 《XXXX法》第XXX条
    r'《([^》]+)》第([一二三四五六七八九十百零\d]+)条(?:第([一二三四五六七八九十\d]+)款)?(?:第?[（(]([一二三四五六七八九十\d]+)[）)])?项?',
    # 第XXX条 of 《XXXX法》
    r'第([一二三四五六七八九十百零\d]+)条[之]?(?:第([一二三四五六七八九十\d]+)款)?(?:第?[（(]([一二三四五六七八九十\d]+)[）)])?项?[^。]*?《([^》]+)》',
    # 《XXXXX》第X条
    r'《([^》]+)》第([一二三四五六七八九十百零\d]+)条',
    # 依据《XXXX法》等
    r'根据[《]?([^》。]+?法[》]?)[》]?(?:第([一二三四五六七八九十百零\d]+)条)?',
    # 依照《XXXX法》
    r'依照[《]?([^》。]+?法[》]?)[》]?(?:第([一二三四五六七八九十百零\d]+)条)?',
]

def cn_num_to_arabic(s):
    """中文数字转阿拉伯数字"""
    mapping = {
        '零': '0', '一': '1', '二': '2', '三': '3', '四': '4',
        '五': '5', '六': '6', '七': '7', '八': '8', '九': '9',
        '十': '10', '百': '100', '千': '1000',
    }
    if s.isdigit():
        return s
    # Handle simple cases
    if s in mapping:
        return mapping[s]
    # Handle 十二, 二十, etc.
    if '十' in s:
        parts = s.split('十')
        if parts[0] == '' or parts[0] is None:
            tens = 1
        else:
            tens = int(cn_num_to_arabic(parts[0]))
        if parts[1] == '' or parts[1] is None:
            ones = 0
        else:
            ones = int(cn_num_to_arabic(parts[1]))
        return str(tens * 10 + ones)
    # Handle 百十
    if '百' in s:
        parts = s.split('百')
        if parts[1] and '十' in parts[1]:
            return str(int(cn_num_to_arabic(parts[0])) * 100 + int(cn_num_to_arabic(parts[1])))
        return str(int(cn_num_to_arabic(parts[0])) * 100)
    return s

def extract_provisions_regex(text):
    """正则提取法条引用"""
    provisions = []
    seen = set()
    
    for pattern in LAW_PATTERNS:
        for match in re.finditer(pattern, text):
            groups = match.groups()
            # Determine order based on pattern
            if len(groups) == 4:
                statute = re.sub(r'[《》]', '', (groups[0] or '')).strip()
                article_raw = groups[1] or ''
                paragraph_raw = groups[2] or ''
                item_raw = groups[3] or ''
            elif len(groups) == 2:
                statute = re.sub(r'[《》]', '', (groups[0] or '')).strip()
                article_raw = groups[1] or ''
                paragraph_raw = ''
                item_raw = ''
            else:
                continue
            
            article = cn_num_to_arabic(article_raw.strip()) if article_raw.strip() else ''
            paragraph = ''
            if paragraph_raw:
                paragraph = cn_num_to_arabic(paragraph_raw.strip())
            item = ''
            if item_raw:
                item = cn_num_to_arabic(item_raw.strip())
            
            key = (statute, article, paragraph, item)
            if key not in seen:
                seen.add(key)
                provisions.append({
                    "statute": statute,
                    "article": article,
                    "paragraph": paragraph,
                    "item": item
                })
    
    return provisions

def extract_all_law_text(row):
    """从CSV行的所有文本字段中提取法条"""
    text_fields = []
    for idx in [10, 11, 12, 13, 14]:  # basic_facts, judgment_reason, judgment_essence, related_info, related_law
        if idx < len(row) and row[idx] and row[idx] != '\\N':
            val = row[idx].replace('<p>', '\n').replace('</p>', '\n').replace('<br/>', '\n').replace('&nbsp;', ' ')
            text_fields.append(val)
    return extract_provisions_regex('\n'.join(text_fields))

# ============ LLM提取 ============
def parse_with_llm(row, api_key, base_url, model, prompt_template, max_retries=2):
    """单条LLM提取"""
    from openai import OpenAI
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    rid = row[0]
    case_type = row[3]
    basic_facts = row[10] if len(row) > 10 and row[10] and row[10] != '\\N' else ''
    judgment_reason = row[11] if len(row) > 11 and row[11] and row[11] != '\\N' else ''
    judgment_essence = row[12] if len(row) > 12 and row[12] and row[12] != '\\N' else ''
    related_law = row[14] if len(row) > 14 and row[14] and row[14] != '\\N' else ''
    
    # Compress text
    compressed_text, strategy = compress_for_llm(
        basic_facts, judgment_reason, judgment_essence, related_law
    )
    
    case_text = f"案件类型：{case_type}\n\n{compressed_text}"
    prompt = prompt_template.replace('{case_text}', case_text)
    
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一个专业的法律文本解析工具。请严格按照要求输出JSON。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4096,
            )
            content = response.choices[0].message.content
            
            # Extract JSON
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            result = json.loads(content)
            result['id'] = rid
            result['case_type_raw'] = case_type
            return result, strategy
            
        except (json.JSONDecodeError, Exception) as e:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            return {
                'id': rid,
                'case_type_raw': case_type,
                'error': str(e)
            }, strategy

# ============ ID生成 ============
def make_id(prefix, id_int):
    return f"{prefix}_{id_int:06d}"

def simple_hash(text):
    """短hash"""
    return hashlib.md5(text.encode()).hexdigest()[:8]

# ============ 解析案由分类 ============
def parse_case_type(case_type_str):
    """从case_type字段解析案由"""
    if not case_type_str or case_type_str == '\\N':
        return {'category': '', 'level1': '', 'level2': ''}
    
    category_map = {
        '民事': 'civil', '刑事': 'criminal', '行政': 'administrative',
        '执行': 'execution', '知识产权': 'ip', '国家赔偿': 'state_compensation'
    }
    
    parts = case_type_str.split('-', 1)
    level1 = parts[0].strip() if parts else ''
    level2 = parts[1].strip() if len(parts) > 1 else ''
    
    # Determine category
    category = ''
    for cn, en in category_map.items():
        if cn in level1 or cn in level2:
            category = en
            break
    
    return {'category': category, 'level1': level1, 'level2': level2}

# ============ 核心处理 ============
def main():
    print("=" * 60)
    print("第一批50条数据处理 - 开始")
    print("=" * 60)
    
    # 1. 读取CSV，取最早的50条（按ID排序）
    all_rows = []
    with open(RAW_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = next(reader)
        for row in reader:
            if row and row[0].strip():
                all_rows.append(row)
    
    # Sort by ID (numeric)
    all_rows.sort(key=lambda r: int(r[0]))
    batch_rows = all_rows[:BATCH_SIZE]
    
    id_start = batch_rows[0][0]
    id_end = batch_rows[-1][0]
    print(f"\n处理ID范围: {id_start} ~ {id_end} ({len(batch_rows)}条)")
    
    # 2. 逐条处理
    llm_results = []
    fallback_count = 0
    llm_success = 0
    llm_failed = 0
    
    for idx, row in enumerate(batch_rows):
        rid = row[0]
        print(f"\n[{idx+1}/{BATCH_SIZE}] 处理 ID={rid} ...", end=" ", flush=True)
        
        # LLM提取
        result, strategy = parse_with_llm(row, API_KEY, BASE_URL, MODEL, PROMPT_TEMPLATE)
        
        if 'error' not in result:
            llm_success += 1
            print(f"✓ LLM成功 (压缩策略: {strategy})", end="")
            
            # Check if legal_provisions is empty → fallback
            if not result.get('legal_provisions'):
                fallback_provisions = extract_all_law_text(row)
                if fallback_provisions:
                    result['legal_provisions'] = fallback_provisions
                    result['_fallback_used'] = True
                    fallback_count += 1
                    print(" [法条fallback]", end="")
                else:
                    result['_fallback_used'] = False
        else:
            llm_failed += 1
            print(f"✗ LLM失败: {result.get('error', 'unknown')[:60]}", end="")
            # Use fallback for provisions at least
            fallback_provisions = extract_all_law_text(row)
            result['legal_provisions'] = fallback_provisions
            result['_fallback_used'] = True
            if fallback_provisions:
                fallback_count += 1
                print(" [法条fallback OK]", end="")
        
        llm_results.append(result)
        print()
    
    print(f"\nLLM: 成功{llm_success}, 失败{llm_failed}, 法条fallback{fallback_count}")
    
    # 3. 映射到Gold层CSV
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    
    # Data containers
    guiding_cases = []
    courts = {}
    case_types = {}
    legal_provisions = {}
    court_cases = []
    persons = {}
    organizations = {}
    edges_cites = []
    edges_guides_case_type = []
    edges_involves = []
    edges_has_case_type = []
    edges_heard_by = []
    
    court_id_counter = 1
    case_type_id_counter = 1
    provision_id_counter = 1
    court_case_id_counter = 1
    person_id_counter = 1
    org_id_counter = 1
    
    for result in llm_results:
        rid = result['id']
        row_idx = None
        for i, r in enumerate(batch_rows):
            if r[0] == rid:
                row_idx = i
                break
        if row_idx is None:
            continue
        row = batch_rows[row_idx]
        
        guid_case_id = make_id('gc', int(rid))
        
        # --- GuidingCase ---
        gc = result.get('guiding_case', {})
        ct = result.get('case_type_raw', '')
        parsed_ct = parse_case_type(ct)
        
        # Extract key_words from row
        key_words_raw = row[6] if len(row) > 6 and row[6] and row[6] != '\\N' else ''
        
        guiding_cases.append({
            "id": guid_case_id,
            "guiding_case_number": gc.get('guiding_case_number', ''),
            "name": f"指导案例/{ct}",
            "issuing_court_id": '',
            "publication_date": gc.get('publication_date', ''),
            "guiding_points": gc.get('guiding_points', ''),
            "binding_force": gc.get('binding_force', 'reference'),
            "source_url": gc.get('source_url', ''),
            "tags": key_words_raw,
            "trial_procedure": gc.get('trial_procedure', row[7] if len(row) > 7 else ''),
            "trial_level": '',
            "source": '人民法院案例库',
            "desensitize": '0',
            "create_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "update_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })
        
        # --- CaseType ---
        ct_key = parsed_ct['category'] + '-' + parsed_ct['level1'] + '-' + parsed_ct['level2']
        if ct_key not in case_types:
            ct_id = make_id('ct', case_type_id_counter)
            case_types[ct_key] = {
                "id": ct_id,
                "code": f"CT_{case_type_id_counter:04d}",
                "name": ct,
                "category": parsed_ct['category'],
                "level1": parsed_ct['level1'],
                "level2": parsed_ct['level2'],
            }
            case_type_id_counter += 1
        
        # --- edges_GUIDES_CASE_TYPE ---
        edges_guides_case_type.append({
            "guiding_case_id": guid_case_id,
            "case_type_id": case_types[ct_key]["id"]
        })
        
        # --- Court + CourtCase ---
        court_cases_data = result.get('court_cases', [])
        if court_cases_data:
            for cc in court_cases_data:
                court_name = cc.get('court', {}).get('name', '')
                court_level = cc.get('court', {}).get('court_level', '')
                case_number = cc.get('case_number', '')
                
                if court_name and court_name not in courts:
                    courts[court_name] = {
                        "id": make_id('crt', court_id_counter),
                        "name": court_name,
                        "org_type": "court",
                        "credit_code": '',
                        "court_level": court_level,
                        "district_id": '',
                    }
                    court_id_counter += 1
                
                court_id = courts.get(court_name, {}).get('id', '')
                
                cc_id = make_id('cca', court_case_id_counter)
                court_cases.append({
                    "id": cc_id,
                    "case_number": case_number,
                    "filing_date": '',
                    "court_id": court_id,
                    "case_type_id": case_types[ct_key]["id"],
                    "trial_level": cc.get('trial_level', ''),
                    "status": cc.get('status', ''),
                })
                court_case_id_counter += 1
                
                # edges_HEARD_BY
                if court_id:
                    edges_heard_by.append({
                        "case_id": cc_id,
                        "court_id": court_id,
                    })
                
                # edges_HAS_CASE_TYPE
                edges_has_case_type.append({
                    "case_id": cc_id,
                    "case_type_id": case_types[ct_key]["id"]
                })
                
                # --- LegalProvision + edges_CITES ---
                provisions = result.get('legal_provisions', [])
                for prov in provisions:
                    statute = prov.get('statute', '')
                    article = prov.get('article', '')
                    paragraph = prov.get('paragraph', '')
                    item = prov.get('item', '')
                    
                    prov_key = f"{statute}|{article}|{paragraph}|{item}"
                    if prov_key not in legal_provisions:
                        prov_id = make_id('lp', provision_id_counter)
                        legal_provisions[prov_key] = {
                            "id": prov_id,
                            "law_id": '',
                            "article": article,
                            "paragraph": paragraph,
                            "item": item,
                            "content": f"{statute}第{article}条" + (f"第{paragraph}款" if paragraph else '') + (f"第{item}项" if item else ''),
                            "status": 'effective',
                        }
                        provision_id_counter += 1
                    
                    prov_id = legal_provisions[prov_key]["id"]
                    edges_cites.append({
                        "case_id": cc_id,
                        "provision_id": prov_id,
                        "citation_position": prov.get('citation_position', ''),
                        "citation_purpose": prov.get('citation_purpose', ''),
                    })
                
                # --- LegalSubject (person/organization) + edges_INVOLVES ---
                subjects = result.get('legal_subjects', [])
                for subj in subjects:
                    name = subj.get('name', '')
                    subj_type = subj.get('subject_type', '')
                    org_type = subj.get('org_type', '')
                    credit_code = subj.get('credit_code', '')
                    roles = subj.get('roles', [])
                    
                    subj_id = ''
                    if subj_type == 'organization' or org_type:
                        org_key = f"{name}|{credit_code}"
                        if org_key not in organizations:
                            org_id_str = make_id('org', org_id_counter)
                            organizations[org_key] = {
                                "id": org_id_str,
                                "name": name,
                                "org_type": org_type or 'company',
                                "credit_code": credit_code or '',
                            }
                            org_id_counter += 1
                        subj_id = organizations[org_key]["id"]
                    else:
                        person_key = f"{name}|{rid}"  # Per-case disambiguation
                        if person_key not in persons:
                            p_id = make_id('per', person_id_counter)
                            persons[person_key] = {
                                "id": p_id,
                                "name": name,
                            }
                            person_id_counter += 1
                        subj_id = persons[person_key]["id"]
                    
                    for role in roles:
                        edges_involves.append({
                            "case_id": cc_id,
                            "subject_id": subj_id,
                            "role_code": role.get('role_code', ''),
                            "role_name": role.get('role_name', ''),
                        })
    
    # 4. Write Gold layer CSV files
    def write_csv(filepath, cols, data_list):
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            for d in data_list:
                writer.writerow([d.get(c, '') for c in cols])
        print(f"  写入 {filepath.name}: {len(data_list)} 行")
    
    print("\n写入Gold层CSV文件...")
    
    write_csv(GOLD_DIR / "GuidingCase.csv", GUIDING_CASE_COLS, guiding_cases)
    write_csv(GOLD_DIR / "Court.csv", COURT_COLS, list(courts.values()))
    write_csv(GOLD_DIR / "CaseType.csv", CASE_TYPE_COLS, list(case_types.values()))
    write_csv(GOLD_DIR / "LegalProvision.csv", LEGAL_PROVISION_COLS, list(legal_provisions.values()))
    write_csv(GOLD_DIR / "CourtCase.csv", COURT_CASE_COLS, court_cases)
    write_csv(GOLD_DIR / "Person.csv", PERSON_COLS, list(persons.values()))
    write_csv(GOLD_DIR / "Organization.csv", ORG_COLS, list(organizations.values()))
    write_csv(GOLD_DIR / "edges_CITES.csv", EDGES_CITES_COLS, edges_cites)
    write_csv(GOLD_DIR / "edges_GUIDES_CASE_TYPE.csv", EDGES_GUIDES_CASE_TYPE_COLS, edges_guides_case_type)
    write_csv(GOLD_DIR / "edges_INVOLVES.csv", EDGES_INVOLVES_COLS, edges_involves)
    write_csv(GOLD_DIR / "edges_HAS_CASE_TYPE.csv", EDGES_HAS_CASE_TYPE_COLS, edges_has_case_type)
    write_csv(GOLD_DIR / "edges_HEARD_BY.csv", EDGES_HEARD_BY_COLS, edges_heard_by)
    
    # 5. 写入batch_state.json
    batch_state = {
        "batch_id": 1,
        "batch_size": BATCH_SIZE,
        "id_range": {"start": int(id_start), "end": int(id_end)},
        "processed_ids": [int(r[0]) for r in batch_rows],
        "status": "completed",
        "stats": {
            "total": BATCH_SIZE,
            "llm_success": llm_success,
            "llm_failed": llm_failed,
            "fallback_law_count": fallback_count,
        },
        "timestamp": datetime.now().isoformat(),
    }
    
    with open(BATCH_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(batch_state, f, ensure_ascii=False, indent=2)
    print(f"\n写入 {BATCH_STATE_FILE}: 完成")
    
    # 6. 输出处理报告
    total_provisions = len(legal_provisions)
    total_provision_refs = len(edges_cites)
    total_subjects = len(persons) + len(organizations)
    total_involves = len(edges_involves)
    total_courts = len(courts)
    
    # Count how many cases have at least one provision
    cases_with_provisions = set(e['case_id'] for e in edges_cites)
    provision_coverage = len(cases_with_provisions) / len(court_cases) * 100 if court_cases else 0
    
    # Count how many cases have at least one party
    cases_with_parties = set(e['case_id'] for e in edges_involves)
    party_extraction_rate = len(cases_with_parties) / len(court_cases) * 100 if court_cases else 0
    
    print("\n" + "=" * 60)
    print("处 理 报 告")
    print("=" * 60)
    print(f"ID范围:           {id_start} ~ {id_end}")
    print(f"处理总数:         {BATCH_SIZE}")
    print(f"LLM成功/失败:     {llm_success}/{llm_failed}")
    print(f"法条fallback:     {fallback_count}")
    print()
    print("--- 实体提取统计 ---")
    print(f"指导案例:         {len(guiding_cases)}")
    print(f"法院案件:         {len(court_cases)}")
    print(f"法院:             {total_courts}")
    print(f"案由分类:         {len(case_types)}")
    print(f"法条(唯一):       {total_provisions}")
    print(f"法条引用(边):     {total_provision_refs}")
    print(f"当事人(自然人):   {len(persons)}")
    print(f"当事人(组织):     {len(organizations)}")
    print(f"当事人参与(边):   {total_involves}")
    print()
    print("--- 关键指标 ---")
    print(f"法条覆盖率:       {provision_coverage:.1f}% ({len(cases_with_provisions)}/{len(court_cases)} 案件有法条)")
    print(f"当事人提取率:     {party_extraction_rate:.1f}% ({len(cases_with_parties)}/{len(court_cases)} 案件有当事人)")
    print(f"法条引用/案件:    {total_provision_refs / max(len(court_cases), 1):.1f}")
    print()
    print("--- 生成文件 ---")
    gold_files = list(GOLD_DIR.glob("*.csv"))
    for f in sorted(gold_files):
        with open(f, 'r', encoding='utf-8') as fh:
            line_count = sum(1 for _ in fh) - 1  # exclude header
        print(f"  {f.name}: {line_count} 行")
    print(f"  batch_state.json: 存在")
    print("=" * 60)


if __name__ == "__main__":
    main()
