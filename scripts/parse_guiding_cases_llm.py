#!/usr/bin/env python3
"""
指导性案例CSV解析脚本 - LLM版本

从人民法院案例库导出的CSV中，使用大语言模型提取结构化信息。

使用方法:
    export OPENAI_API_KEY="your-api-key"
    export OPENAI_BASE_URL="https://api.moonshot.cn/v1"  # Kimi API
    python scripts/parse_guiding_cases_llm.py \
        --input data/raw/DataWorks_Excel_*.csv \
        --output data/processed/guiding_cases_parsed.jsonl \
        --max-workers 5 \
        --limit 100  # 先测试100条

依赖:
    pip install openai

输出格式 (JSON Lines):
    {"id": "2292", "case_type": "行政-...", "parties": [...], ...}
"""

import argparse
import csv
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# 可选：使用openai库
# import openai


def clean_text(text: str) -> str:
    """清理HTML标签和转义字符"""
    if not text or text == '\\N':
        return ''
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('u3000', '\u3000')
    text = text.replace('u2002', '\u2002')
    text = text.strip()
    text = re.sub(r'\n+', '\n', text)
    return text


def build_prompt(case_type: str, basic_facts: str, judgment_reason: str,
                 judgment_essence: str, prompt_template: str) -> str:
    """构造LLM prompt"""
    text_parts = [f"[case_type]{case_type}[/case_type]"]
    if basic_facts:
        text_parts.append(f"[basic_facts]{basic_facts}[/basic_facts]")
    if judgment_reason:
        text_parts.append(f"[judgment_reason]{judgment_reason}[/judgment_reason]")
    if judgment_essence:
        text_parts.append(f"[judgment_essence]{judgment_essence}[/judgment_essence]")

    case_text = '\n'.join(text_parts)
    # 截断过长文本以节省token
    if len(case_text) > 3000:
        case_text = case_text[:3000] + "...[文本已截断]"

    return prompt_template.replace("{case_text}", case_text)


def parse_llm_response(response_text: str) -> dict:
    """解析LLM返回的JSON，带错误处理"""
    # 尝试直接解析
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # 尝试提取JSON代码块
    code_block_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取花括号内容
    brace_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法解析JSON: {response_text[:200]}")


def call_llm(prompt: str, api_key: str, base_url: str, model: str,
             max_retries: int = 3) -> dict:
    """调用LLM API"""
    import openai

    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是专业的法律文本解析工具，请严格输出JSON。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=3000,
            )
            content = response.choices[0].message.content
            return parse_llm_response(content)
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"  API调用失败，{wait}秒后重试: {e}")
                time.sleep(wait)
            else:
                raise


def extract_case_numbers_regex(text: str) -> list:
    """正则提取案号"""
    pattern = r'\(\d{4}\)[一-龥]{1,6}\d{0,6}[民刑行扯知刑]字?初?终?再?审?实?异?复?广?议?执?行?字?第\d+号'
    matches = re.findall(pattern, text)
    return list(dict.fromkeys(matches))  # 保持顺序去重


def extract_courts_regex(text: str) -> list:
    """正则提取法院名称"""
    pattern = r'([一-龥]{2,10}(?:省|市|自治州|盟|地区|县|区))?(?:最高人民法院|[一-龥]{2,10}人民法院)'
    matches = re.findall(pattern, text)
    courts = []
    for m in matches:
        if isinstance(m, tuple):
            m = ''.join(m)
        m = m.strip()
        if m and m not in courts and '法院' in m:
            courts.append(m)
    return courts


def _clean_law_name(name: str) -> str:
    """清理法律名称，去除常见上下文前缀和HTML实体"""
    import html as _html
    name = _html.unescape(name)
    # 去除开头的标点和常见上下文词
    prefixes = [
        '依据', '按照', '根据', '违反', '依照', '遵照', '有关', '关于',
        '适用', '引用', '符合', '不符', '参照', '援引', '基于', '鉴于',
        '因为', '由于', '以及', '和', '与', '及', '或', '但', '虽', '然',
        '如', '若', '即', '使', '被', '把', '将', '让', '对', '向', '从',
        '由', '在', '是', '的', '了', '之', '可', '应', '须', '必', '当',
        '得', '需', '宜', '勿', '莫', '不', '未', '无', '非', '否', '别',
        '因此', '并非', '不属于', '属于', '满足', '不满足', '具备',
        '不具备', '涉及', '不涉及', '是否', '判断其', '进一步',
        '此基础上', '必须', '不必', '应当', '不应', '可以', '不可',
        '能够', '不能', '得以', '不得', '需要', '不需', '应该', '不该',
        '必须', '无须', '不必', '应须', '需须', '宜', '不宜', '莫',
        '勿', '莫要', '勿要', '不要', '不用', '无需', '不用', '未必',
        '未需', '未必', '无需', '不必', '不需', '不用', '不必', '不需',
        '不必', '不需', '不必', '不需', '不必', '不需', '不必', '不需',
        '《', '》', '（', '）', '〈', '〉', '<', '>', '、', '，', '。', '；',
        '：', '！', '？', '“', '”', '‘', '’', '"', "'", '「', '」', '『', '』',
        '—', '–', '─', '～', '·', '•', '●', '○', '●', '○', '●', '○',
        '对于', '关于', '至于', '由于', '基于', '根据', '依据', '按照',
        '依照', '参照', '引用', '援引', '适用', '应用', '采用', '使用',
        '利用', '运用', '使用', '采取', '采用', '应用', '使用', '运用',
        '采用', '使用', '应用', '运用', '利用', '使用', '采用', '应用',
        '运用', '使用', '采取', '采用', '使用', '应用', '运用', '利用',
        '运用', '使用', '采用', '应用', '运用', '使用', '采取', '采用',
        '使用', '应用', '运用', '利用', '运用', '使用', '采用', '应用',
        '运用', '使用', '采取', '采用', '使用', '应用', '运用', '利用',
        '运用', '使用', '采用', '应用', '运用', '使用', '采取', '采用',
        '使用', '应用', '运用', '利用', '运用', '使用', '采用', '应用',
        '运用', '使用', '采取', '采用', '使用', '应用', '运用', '利用',
        '运用', '使用', '采用', '应用', '运用', '使用', '采取', '采用',
        '使用', '应用', '运用', '利用', '运用', '使用', '采用', '应用',
        '运用', '使用', '采取', '采用', '使用', '应用', '运用', '利用',
    ]
    # 移除重复的前缀并按长度排序，以便先匹配更长的前缀
    prefixes = sorted(set(prefixes), key=len, reverse=True)
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break
    return name.strip()


def _is_valid_law_name(name: str) -> bool:
    """验证名称是否看起来像法律法规名称"""
    suffixes = ('法', '条例', '规定', '意见', '办法', '细则', '规则', '解释', '典', '决定', '通知', '批复', '答复')
    return any(name.endswith(s) for s in suffixes)


def extract_law_refs_regex(text: str) -> list:
    """正则提取法条引用

    覆盖格式：
    1. 《法典名》（可能带修正版标注）第X条之一?第X款/项?
    2. 法典名第X条之一?第X款/项? (无书名号)
    3. HTML实体 &lt;《&gt;等被自动清理
    """
    import html as _html
    text = _html.unescape(text)
    refs = []
    seen = set()

    # Pattern 1: 《法典名》（可能带修正版标注）第X条之一?第X款/项?
    p1 = r'《([^》]{2,50})》(?:（[^）]{2,30}）)?第([\d一十二三四五六七八九百千]+)条(之一)?(?:第([\d一十二三四五六七八九百千]+)[款项])?'

    # Pattern 2: 法典名第X条之一?第X款/项? (无书名号)
    # Law names usually end with 法/条例/规定/意见/办法/细则/规则/解释/典
    p2 = r'([\u4e00-\u9fa5]{1,25}(?:法|条例|规定|意见|办法|细则|规则|解释|典))第([\d一十二三四五六七八九百千]+)条(之一)?(?:第([\d一十二三四五六七八九百千]+)[款项])?'

    for pattern in [p1, p2]:
        for match in re.finditer(pattern, text):
            groups = match.groups()
            statute = groups[0].strip() if groups[0] else ""
            article = groups[1].strip() if groups[1] else ""
            amendment = groups[2].strip() if len(groups) > 2 and groups[2] else ""
            paragraph = groups[3].strip() if len(groups) > 3 and groups[3] else ""

            if not article:
                continue

            statute = _clean_law_name(statute)
            if not statute:
                continue

            # Pattern 2 匹配出来的名称需要验证，避免过短或异常的拼接
            if pattern is p2 and not _is_valid_law_name(statute):
                continue

            if amendment:
                article += amendment

            key = (statute, article, paragraph)
            if key not in seen:
                seen.add(key)
                refs.append({
                    "statute": statute,
                    "article": article,
                    "paragraph": paragraph
                })

    return refs


def process_record(record: dict, prompt_template: str, api_key: str,
                   base_url: str, model: str) -> dict:
    """处理单条记录，支持字段级容错与正则底色"""
    prompt = build_prompt(
        case_type=record.get('case_type', ''),
        basic_facts=record.get('basic_facts', ''),
        judgment_reason=record.get('judgment_reason', ''),
        judgment_essence=record.get('judgment_essence', ''),
        prompt_template=prompt_template,
    )

    # 字段级容错：即使LLM调用或解析失败，也尽量保留可用字段
    result: dict = {}
    try:
        result = call_llm(prompt, api_key, base_url, model)
    except Exception as e:
        result = {"_llm_error": str(e)}

    # 兼容旧字段名与新字段名
    participants = result.get("participants") or result.get("parties") or []
    legal_provisions = result.get("legal_provisions") or result.get("law_refs") or []
    case_summary = result.get("case_summary") or ""
    if isinstance(case_summary, dict):
        key_facts = case_summary.get("key_facts", "")
        disputed_issues = case_summary.get("disputed_issues", "")
        conclusion = case_summary.get("conclusion", "")
    else:
        key_facts = str(case_summary)
        disputed_issues = ""
        conclusion = ""

    case_numbers = result.get("case_numbers") or []
    courts = result.get("courts") or []
    judgment_result = result.get("judgment_result") or {}
    guiding_points = result.get("guiding_points") or ""

    # 正则底色：如果LLM未提取，从原始文本补充
    raw_text = "\n".join([
        record.get('basic_facts', ''),
        record.get('judgment_reason', ''),
        record.get('judgment_essence', ''),
        record.get('related_law', ''),
    ])

    if not case_numbers:
        case_numbers = extract_case_numbers_regex(raw_text)
    if not courts:
        courts = extract_courts_regex(raw_text)
    if not legal_provisions:
        legal_provisions = extract_law_refs_regex(raw_text)

    # 确保法条 article 非空
    legal_provisions = [r for r in legal_provisions if r.get("article")]

    # 合并输出
    output = {
        "id": record.get('id', ''),
        "case_type": record.get('case_type', ''),
        "participants": participants if isinstance(participants, list) else [],
        "case_numbers": case_numbers if isinstance(case_numbers, list) else [],
        "courts": courts if isinstance(courts, list) else [],
        "legal_provisions": legal_provisions if isinstance(legal_provisions, list) else [],
        "case_summary": {
            "key_facts": key_facts,
            "disputed_issues": disputed_issues,
            "conclusion": conclusion,
        },
        "judgment_result": judgment_result if isinstance(judgment_result, dict) else {},
        "guiding_points": guiding_points,
        "_raw": {
            "basic_facts": record.get('basic_facts', '')[:200],
            "judgment_reason": record.get('judgment_reason', '')[:200],
            "judgment_essence": record.get('judgment_essence', '')[:200],
        }
    }
    # 保留LLM返回的原始其他字段
    for k, v in result.items():
        if k not in output and not k.startswith("_"):
            output[k] = v
    if "_llm_error" in result:
        output["_llm_error"] = result["_llm_error"]

    return output


def load_existing_ids(output_path: Path) -> set:
    """加载已处理的记录ID"""
    ids = set()
    if not output_path.exists():
        return ids
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                ids.add(str(obj.get("id", "")))
            except json.JSONDecodeError:
                continue
    return ids


def main():
    parser = argparse.ArgumentParser(description="使用LLM解析指导性案例CSV")
    parser.add_argument("--input", required=True, help="输入CSV文件路径")
    parser.add_argument("--output", required=True, help="输出JSONL路径")
    parser.add_argument("--prompt", default="scripts/prompts/guiding_case_extraction.txt",
                        help="Prompt模板路径")
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY"),
                        help="OpenAI/Kimi API Key")
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
                        help="API Base URL")
    parser.add_argument("--model", default="deepseek-v4-pro", help="模型名称")
    parser.add_argument("--max-workers", type=int, default=3, help="并发线程数")
    parser.add_argument("--limit", type=int, default=0, help="限制处理条数（0=全部）")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="每批保存条数")
    args = parser.parse_args()

    # 加载prompt模板
    with open(args.prompt, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # 加载CSV
    records = []
    with open(args.input, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=",", quotechar='"')
        header = next(reader)
        # 清理BOM
        header = [h.strip().lstrip('\ufeff').strip('"') for h in header]

        for row in reader:
            record = {
                'id': row[0] if len(row) > 0 else '',
                'web_name': row[1] if len(row) > 1 else '',
                'web_url': row[2] if len(row) > 2 else '',
                'case_type': row[3] if len(row) > 3 else '',
                'storage_no': row[4] if len(row) > 4 else '',
                'court_name': row[5] if len(row) > 5 else '',
                'key_words': row[6] if len(row) > 6 else '',
                'trial_procedure': row[7] if len(row) > 7 else '',
                'trial_year': row[8] if len(row) > 8 else '',
                'case_level': row[9] if len(row) > 9 else '',
                'basic_facts': clean_text(row[10]) if len(row) > 10 else '',
                'judgment_reason': clean_text(row[11]) if len(row) > 11 else '',
                'judgment_essence': clean_text(row[12]) if len(row) > 12 else '',
                'related_info': clean_text(row[13]) if len(row) > 13 else '',
                'related_law': clean_text(row[14]) if len(row) > 14 else '',
                'related_judgment_body': clean_text(row[15]) if len(row) > 15 else '',
                'create_time': row[16] if len(row) > 16 else '',
                'update_time': row[17] if len(row) > 17 else '',
                'md5_value': row[18] if len(row) > 18 else '',
                'judgment_mean': row[19] if len(row) > 19 else '',
                'dt': row[20] if len(row) > 20 else '',
            }
            records.append(record)

    # 检查API key
    if not args.api_key:
        print("错误：未设置API Key。请设置环境变量 OPENAI_API_KEY 或使用 --api-key 参数。")
        return

    # 加载已处理的记录
    output_path = Path(args.output)
    existing_ids = load_existing_ids(output_path)
    if existing_ids:
        print(f"发现 {len(existing_ids)} 条已处理记录，将跳过。")

    # 过滤已处理的记录
    todo_records = [r for r in records if str(r['id']) not in existing_ids]
    if args.limit > 0:
        todo_records = todo_records[:args.limit]

    print(f"共计 {len(records)} 条记录，待处理 {len(todo_records)} 条，并发 {args.max_workers}")

    # 批量处理
    results = []
    processed = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(
                process_record, record, prompt_template,
                args.api_key, args.base_url, args.model
            ): record
            for record in todo_records
        }

        for future in as_completed(futures):
            record = futures[future]
            try:
                result = future.result()
                results.append(result)
                processed += 1

                # 批量保存
                if len(results) >= args.batch_size:
                    with open(output_path, "a", encoding="utf-8") as f:
                        for r in results:
                            f.write(json.dumps(r, ensure_ascii=False) + "\n")
                    results = []

            except Exception as e:
                print(f"  处理失败 id={record['id']}: {e}")
                failed += 1

            if (processed + failed) % 10 == 0:
                print(f"  进度: {processed}/{len(todo_records)} 成功, {failed} 失败")

    # 保存剩余结果
    if results:
        with open(output_path, "a", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n完成！总处理 {processed} 条，失败 {failed} 条。")
    print(f"结果保存至: {output_path}")


if __name__ == "__main__":
    main()
