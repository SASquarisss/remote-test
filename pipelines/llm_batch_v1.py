#!/usr/bin/env python3
"""
LLM提取版批量解析脚本 v1
先用本地逻辑提取结构化信息（案号、法院、案由等），
再调用LLM提取法条和当事人信息。
"""
import csv, json, re, hashlib, os, sys, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from extract_legal_provisions_regex import extract_legal_provisions as regex_extract

REPO = Path(__file__).resolve().parent.parent
SOURCE_CSV = REPO / "data/raw/DataWorks_Excel_207022225952236023_20260427150349.csv"
GOLD_DIR = REPO / "data_lake/gold"
BATCH_STATE = REPO / "data/processed/batch_state.json"
BATCH_SIZE = 50

HEADER = ["id","web_name","web_url","case_type","storage_no","court_name","key_words","trial_procedure","trial_year","case_level","basic_facts","judgment_reason","judgment_essence","related_info","related_law","related_judgment_body","create_time","update_time","md5_value","judgment_mean","dt"]

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"

CATEGORY_MAP = {"民事":"civil","刑事":"criminal","行政":"administrative","知识产权":"ip","执行":"execution","执行实施":"execution","国家赔偿":"state_compensation"}
TRIAL_LEVEL_MAP = {"一审":"first_instance","二审":"second_instance","再审":"retrial","一审程序":"first_instance","二审程序":"second_instance","再审程序":"retrial","重审":"retrial","死刑复核":"","执行":"","国家赔偿":"","其他":"","执行监督":"","执行异议":"","执行复议":"","委赔":"","\\\\N":""}

def md5_id(prefix, *parts):
    return f"{prefix}_{hashlib.md5('|'.join(str(p) for p in parts).encode()).hexdigest()[:12]}"

def clean_tags(raw):
    raw = (raw or "").strip()
    raw = re.sub(r'^[：:\s,，]+', '', raw)
    raw = re.sub(r'[：:\s,，]+$', '', raw)
    raw = raw.strip('"').strip("'").strip()
    return re.sub(r'\s+', ' ', raw)

def map_category(cat): return CATEGORY_MAP.get(cat, "")
def map_trial_level(tp):
    tp = (tp or "").strip()
    if not tp or tp == "\\N": return ""
    if tp in TRIAL_LEVEL_MAP: return TRIAL_LEVEL_MAP[tp]
    for k, v in TRIAL_LEVEL_MAP.items():
        if k in tp: return v
    return ""

def extract_district_id(name):
    if not name: return ""
    if name == "最高人民法院": return "CN"
    for kw, code in [("北京","CN-11"),("上海","CN-31"),("天津","CN-12"),("重庆","CN-50"),
                     ("河北","CN-13"),("山西","CN-14"),("辽宁","CN-21"),("吉林","CN-22"),
                     ("黑龙江","CN-23"),("江苏","CN-32"),("浙江","CN-33"),("安徽","CN-34"),
                     ("福建","CN-35"),("江西","CN-36"),("山东","CN-37"),("河南","CN-41"),
                     ("湖北","CN-42"),("湖南","CN-43"),("广东","CN-44"),("海南","CN-46"),
                     ("四川","CN-51"),("贵州","CN-52"),("云南","CN-53"),("陕西","CN-61"),
                     ("甘肃","CN-62"),("青海","CN-63"),("广西","CN-45"),("内蒙古","CN-15"),
                     ("西藏","CN-54"),("宁夏","CN-64"),("新疆","CN-65")]:
        if kw in name: return code
    return ""

def parse_date(raw):
    raw = raw.strip()
    if not raw or raw in ("\\N",""): return ""
    raw = raw.replace("/","-").replace(".","-")
    parts = raw.split("-")
    if len(parts)==3:
        try: return f"{int(parts[0])}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        except: return ""
    return ""

def extract_case_category(case_type):
    case_type = (case_type or "").strip()
    if "-" in case_type: return case_type.split("-", 1)
    return case_type, ""

def normalize_court_name(name):
    return (name or "").strip() or "未知法院"

# ============ LLM提取（异步+并发） ============
def call_llm_for_record(row, prompt_template, max_retries=2):
    """调用DeepSeek API提取一条记录的结构化信息"""
    rid = row[0]
    case_type = row[3] if len(row) > 3 else ""
    basic_facts = row[10] if len(row) > 10 else ""
    judgment_reason = row[11] if len(row) > 11 else ""
    judgment_essence = row[12] if len(row) > 12 else ""
    related_law = row[14] if len(row) > 14 else ""
    
    # 压缩长文本
    text_parts = []
    for label, text in [("基本事实", basic_facts), ("裁判理由", judgment_reason), ("裁判要旨", judgment_essence), ("适用法条", related_law)]:
        if text and text != "\\N":
            clean = re.sub(r'<[^>]+>', '', text)[:3000]
            text_parts.append(f"【{label}】{clean}")
    case_text = f"案件类型：{case_type}\n\n" + "\n\n".join(text_parts)
    
    prompt = prompt_template.replace("{case_text}", case_text)
    
    for attempt in range(max_retries + 1):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
            response = client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个专业的法律文本解析工具。请严格按照要求输出JSON，不要任何额外解释。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4096,
                timeout=120
            )
            content = response.choices[0].message.content
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            result = json.loads(content)
            result["id"] = rid
            result["case_type"] = case_type
            return result
        except Exception as e:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            return {"id": rid, "case_type": case_type, "error": str(e)}

def main():
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    
    # 读取主CSV
    all_rows = []
    with open(SOURCE_CSV, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader)
        for parts in reader:
            if not parts or not parts[0].strip().isdigit(): continue
            all_rows.append(parts)
    all_rows.sort(key=lambda r: int(r[0]))
    
    # 取前50条（从零开始）
    batch = all_rows[:BATCH_SIZE]
    batch_ids = [int(r[0]) for r in batch]
    print(f"Batch 0 (LLM): IDs {batch_ids[0]} ~ {batch_ids[-1]}, 共{len(batch)}条")
    
    # 加载LLM提示词
    prompt_path = REPO / "scripts/prompts" / "guiding_case_ontology_aligned.txt"
    prompt_template = prompt_path.read_text(encoding="utf-8")
    
    # ============ 阶段1: LLM提取 ============
    print("\n=== 阶段1: LLM提取 ===")
    llm_results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(call_llm_for_record, r, prompt_template): r[0] for r in batch}
        for future in as_completed(futures):
            result = future.result()
            rid = result.get("id", "?")
            llm_results[rid] = result
            if "error" in result:
                print(f"  ❌ ID {rid}: {result['error'][:80]}")
            else:
                lp_count = len(result.get("legal_provisions", []))
                subjects = len(result.get("legal_subjects", []))
                cases = len(result.get("court_cases", []))
                print(f"  ✅ ID {rid}: {lp_count}法条, {subjects}当事人, {cases}案号")
    
    success = sum(1 for v in llm_results.values() if "error" not in v)
    print(f"LLM提取: {success}/{len(batch)} 成功")
    
    # ============ 阶段2: 正则fallback（对LLM法条为空的记录）============
    print("\n=== 阶段2: 正则fallback法条 ===")
    regex_fallback_count = 0
    for parts in batch:
        rid = parts[0]
        llm_r = llm_results.get(rid, {})
        if llm_r.get("legal_provisions"):
            continue
        judgment_text = ""
        for idx in [11, 12, 14]:
            if idx < len(parts) and parts[idx] and parts[idx] != "\\N":
                judgment_text += parts[idx] + "\n"
        if judgment_text.strip():
            try:
                provisions = regex_extract(judgment_text)
                if provisions:
                    llm_r["legal_provisions"] = provisions
                    regex_fallback_count += 1
                    print(f"  🔄 ID {rid}: 正则补充{len(provisions)}条法条")
            except Exception as e:
                pass
    
    print(f"正则fallback补充了{regex_fallback_count}条记录的法条")
    
    # ============ 阶段3: 映射到Gold层CSV ============
    print("\n=== 阶段3: 映射到Gold层CSV ===")
    
    guiding_cases = []
    courts = {}
    case_types = {}
    provisions = {}
    court_cases = {}
    persons = {}
    organizations = {}
    edges_cites = []
    edges_guides = []
    edges_involves = []
    edges_has_ct = []
    edges_heard_by = []
    
    for parts in batch:
        rid = parts[0]
        llm_r = llm_results.get(rid, {})
        if "error" in llm_r or not llm_r:
            # 全部走正则fallback
            llm_r = {}
        
        gc_id = f"guiding_case_{rid}"
        case_type_raw = parts[3] if len(parts) > 3 else "unknown"
        if not case_type_raw or case_type_raw == "\\N":
            case_type_raw = "unknown"
        category, sub_type = extract_case_category(case_type_raw)
        ct_id = md5_id("case_type", category, sub_type)
        
        # CaseType
        if ct_id not in case_types:
            case_types[ct_id] = {
                "id": ct_id, "code": ct_id.replace("case_type_", ""),
                "name": sub_type or category, "category": map_category(category) or category,
                "level1": category, "level2": sub_type or "",
                "source": "指导案例库分类", "desensitize": "false",
                "create_time": "2026-04-21T00:00:00Z", "update_time": "2026-04-21T00:00:00Z"
            }
        
        # Court
        court_name = normalize_court_name(parts[5] if len(parts) > 5 else "")
        court_id = md5_id("court", court_name)
        if court_id not in courts:
            level = "supreme" if "最高" in court_name else "high" if "高级" in court_name else "intermediate" if "中级" in court_name else "basic"
            courts[court_id] = {
                "id": court_id, "name": court_name, "org_type": "court",
                "credit_code": md5_id("cc", court_name)[-18:],
                "court_level": level, "district_id": extract_district_id(court_name),
                "source": "指导案例库", "desensitize": "false",
                "create_time": "2026-04-21T00:00:00Z", "update_time": "2026-04-21T00:00:00Z"
            }
        
        # GuidingCase
        pub_date = parse_date(parts[8] if len(parts) > 8 else "")
        case_level_raw = (parts[9] if len(parts) > 9 else "").strip()
        web_name = (parts[1] if len(parts) > 1 else "").strip()
        binding = "mandatory" if "案例库" in web_name else "persuasive"
        essence = re.sub(r'<[^>]+>', '', (parts[12] if len(parts) > 12 else "") or "")
        essence = essence.replace('\u3000',' ').replace('\n',' ').replace('\r',' ')[:2000]
        trial_proc = (parts[7] if len(parts) > 7 else "").strip()
        tl = map_trial_level(trial_proc)
        tags_raw = clean_tags(parts[6] if len(parts) > 6 else "")
        storage_no = (parts[4] if len(parts) > 4 else "").strip()
        
        guiding_cases.append({
            "id": gc_id,
            "guiding_case_number": storage_no,
            "name": f"{case_type_raw}-{storage_no}" if storage_no else case_type_raw,
            "issuing_court_id": court_id,
            "publication_date": pub_date,
            "guiding_points": essence,
            "binding_force": binding,
            "source_url": (parts[2] if len(parts) > 2 else "").strip(),
            "tags": tags_raw,
            "trial_procedure": trial_proc,
            "trial_level": tl,
            "source": web_name,
            "desensitize": "false",
            "create_time": "2026-04-21T00:00:00Z",
            "update_time": "2026-04-21T00:00:00Z"
        })
        edges_guides.append({"guiding_case_id": gc_id, "case_type_id": ct_id})
        
        # CourtCase（从LLM提取或从基本信息生成）
        llm_cases = llm_r.get("court_cases", [])
        if llm_cases:
            for cc in llm_cases:
                cc_id = md5_id("ccase", cc.get("case_number", gc_id))
                if cc_id not in court_cases:
                    court_cases[cc_id] = {
                        "id": cc_id,
                        "case_number": cc.get("case_number", ""),
                        "court_id": court_id,
                        "case_type_id": ct_id,
                        "trial_level": cc.get("trial_level", tl),
                        "status": cc.get("status", "effective"),
                        "source": "llm_extraction",
                        "desensitize": "false",
                        "create_time": "2026-04-21T00:00:00Z",
                        "update_time": "2026-04-21T00:00:00Z"
                    }
                edges_has_ct.append({"case_id": cc_id, "case_type_id": ct_id})
                edges_heard_by.append({"case_id": cc_id, "court_id": court_id})
        else:
            # fallback: 从基本信息生成一个CourtCase
            cc_id = md5_id("ccase", gc_id)
            if cc_id not in court_cases:
                court_cases[cc_id] = {
                    "id": cc_id,
                    "case_number": "",
                    "court_id": court_id,
                    "case_type_id": ct_id,
                    "trial_level": tl,
                    "status": "effective",
                    "source": "basic_extraction",
                    "desensitize": "false",
                    "create_time": "2026-04-21T00:00:00Z",
                    "update_time": "2026-04-21T00:00:00Z"
                }
            edges_has_ct.append({"case_id": cc_id, "case_type_id": ct_id})
            edges_heard_by.append({"case_id": cc_id, "court_id": court_id})
        
        # LegalSubjects（从LLM提取）
        llm_subjects = llm_r.get("legal_subjects", [])
        for subj in llm_subjects:
            sname = subj.get("name", "").strip()
            if not sname:
                continue
            stype = subj.get("subject_type", "")
            if stype == "organization" or stype == "company":
                org_id = md5_id("org", sname)
                if org_id not in organizations:
                    organizations[org_id] = {
                        "id": org_id, "name": sname,
                        "org_type": subj.get("org_type", "company"),
                        "credit_code": subj.get("credit_code", ""),
                        "source": "llm_extraction", "desensitize": "false",
                        "create_time": "2026-04-21T00:00:00Z", "update_time": "2026-04-21T00:00:00Z"
                    }
                subj_id = org_id
            else:
                p_id = md5_id("person", gc_id, sname)
                if p_id not in persons:
                    persons[p_id] = {
                        "id": p_id, "name": sname,
                        "source": "llm_extraction", "desensitize": "false",
                        "create_time": "2026-04-21T00:00:00Z", "update_time": "2026-04-21T00:00:00Z"
                    }
                subj_id = p_id
            
            for role in subj.get("roles", []):
                role_case_num = role.get("case_number", "")
                # 找到对应的court_case_id
                target_cc_id = cc_id
                if role_case_num:
                    for ccid, ccdata in court_cases.items():
                        if ccdata.get("case_number") == role_case_num:
                            target_cc_id = ccid
                            break
                edges_involves.append({
                    "case_id": target_cc_id,
                    "subject_id": subj_id,
                    "role_code": role.get("role_code", ""),
                    "role_name": role.get("role_name", "")
                })
        
        # LegalProvisions（从LLM提取 + 正则fallback）
        all_provisions = llm_r.get("legal_provisions", [])
        if not all_provisions:
            try:
                jt = ""
                for idx in [11, 12, 14]:
                    if idx < len(parts) and parts[idx] and parts[idx] != "\\N":
                        jt += parts[idx] + "\n"
                if jt.strip():
                    all_provisions = regex_extract(jt)
            except:
                pass
        
        # 找到第一个court_case_id用于CITES边
        first_cc_id = list(court_cases.keys())[0] if court_cases else gc_id
        
        for prov in all_provisions:
            statute = prov.get("statute", prov.get("law_name", ""))
            article = prov.get("article", prov.get("article_number", ""))
            if not article:
                # 尝试从正则输出提取
                article = prov.get("article", "")
            if not statute and not article:
                continue
            para = prov.get("paragraph", prov.get("clause", ""))
            item = prov.get("item", prov.get("sub_clause", ""))
            prov_id = md5_id("provision", statute, str(article), str(para), str(item))
            if prov_id not in provisions:
                provisions[prov_id] = {
                    "id": prov_id, "law_id": md5_id("law", statute) if statute else "",
                    "article": str(article), "paragraph": str(para), "item": str(item),
                    "content": "", "status": "effective",
                    "source": statute or "unknown",
                    "desensitize": "false",
                    "create_time": "2026-04-21T00:00:00Z", "update_time": "2026-04-21T00:00:00Z"
                }
            cite_key = (first_cc_id, prov_id)
            if cite_key not in [(e["case_id"], e["provision_id"]) for e in edges_cites]:
                edges_cites.append({
                    "case_id": first_cc_id,
                    "provision_id": prov_id,
                    "citation_position": prov.get("citation_position", "裁判理由"),
                    "citation_purpose": prov.get("citation_purpose", "法律依据")
                })
    
    # ============ 写入CSV ============
    def write_csv(name, data):
        if not data: return
        path = GOLD_DIR / name
        keys = list(data[0].keys())
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(data)
        print(f"  ✅ Wrote {len(data)} rows to {name}")
    
    write_csv("GuidingCase.csv", guiding_cases)
    write_csv("Court.csv", list(courts.values()))
    write_csv("CaseType.csv", list(case_types.values()))
    write_csv("LegalProvision.csv", list(provisions.values()))
    write_csv("CourtCase.csv", list(court_cases.values()))
    write_csv("Person.csv", list(persons.values()))
    write_csv("Organization.csv", list(organizations.values()))
    write_csv("edges_CITES.csv", edges_cites)
    write_csv("edges_GUIDES_CASE_TYPE.csv", edges_guides)
    write_csv("edges_INVOLVES.csv", edges_involves)
    write_csv("edges_HAS_CASE_TYPE.csv", edges_has_ct)
    write_csv("edges_HEARD_BY.csv", edges_heard_by)
    
    # ============ 统计报告 ============
    print("\n" + "="*60)
    print(f"Batch 0 (LLM) 处理报告")
    print("="*60)
    print(f"ID范围: {batch_ids[0]} ~ {batch_ids[-1]}")
    print(f"解析数: {len(batch)}")
    print(f"LLM成功: {success}/{len(batch)}")
    print(f"正则fallback法条: {regex_fallback_count}条记录")
    print(f"\n实体统计:")
    print(f"  GuidingCase: {len(guiding_cases)}")
    print(f"  Court: {len(courts)}")
    print(f"  CaseType: {len(case_types)}")
    print(f"  LegalProvision: {len(provisions)}")
    print(f"  CourtCase: {len(court_cases)}")
    print(f"  Person: {len(persons)}")
    print(f"  Organization: {len(organizations)}")
    print(f"\n边统计:")
    print(f"  CITES: {len(edges_cites)}")
    print(f"  GUIDES: {len(edges_guides)}")
    print(f"  INVOLVES: {len(edges_involves)}")
    print(f"  HAS_CASE_TYPE: {len(edges_has_ct)}")
    print(f"  HEARD_BY: {len(edges_heard_by)}")
    
    # 法条覆盖率
    gc_with_lp = len(set(e["case_id"] for e in edges_cites))
    print(f"\n法条覆盖率: {gc_with_lp}/{len(guiding_cases)} ({gc_with_lp/len(guiding_cases)*100:.1f}%)")
    # 当事人覆盖率
    gc_with_subj = len(set(e["case_id"] for e in edges_involves))
    print(f"当事人覆盖率: {gc_with_subj}/{len(guiding_cases)} ({gc_with_subj/len(guiding_cases)*100:.1f}%)")
    
    # 写入batch_state
    state = {
        "batches": [{"batch": 0, "count": len(batch), "ids": batch_ids}],
        "total_processed": len(batch),
        "last_id": batch_ids[-1]
    }
    with open(BATCH_STATE, "w") as f:
        json.dump(state, f, indent=2)
    print(f"\nbatch_state写入: {BATCH_STATE}")

if __name__ == "__main__":
    main()
