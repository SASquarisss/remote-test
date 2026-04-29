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
                max_tokens=1000,
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


def process_record(record: dict, prompt_template: str, api_key: str,
                   base_url: str, model: str) -> dict:
    """处理单条记录，支持字段级容错"""
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
        # LLM调用完全失败，记录错误标记
        result = {"_llm_error": str(e)}

    # 确保必要字段存在（即使为空）
    safe_result = {
        "parties": [],
        "case_numbers": [],
        "courts": [],
        "law_refs": [],
        "case_summary": "",
    }
    for key, default in safe_result.items():
        val = result.get(key)
        if isinstance(val, list):
            safe_result[key] = val
        elif isinstance(val, str):
            safe_result[key] = val
        # 其他类型或缺失时保留默认值

    # 合并输出
    output = {
        "id": record.get('id', ''),
        "case_type": record.get('case_type', ''),
        **safe_result,
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
    # 保留错误标记
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
