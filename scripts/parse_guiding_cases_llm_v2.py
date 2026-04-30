#!/usr/bin/env python3
"""
指导性案例 LLM 解析 v2（长文本优化版）

与 v1 的区别：
- 在送入 LLM 之前，先用 text_compressor 对文本进行结构化压缩
- 保留核心信息，减少噪声干扰
- 适用于 judgment_reason > 3000 字的长文本案件

使用：
    python3 scripts/parse_guiding_cases_llm_v2.py \
        --input data/raw/test_20_subset_v2.csv \
        --output data/processed/test_v2.jsonl \
        --api-key $DEEPSEEK_API_KEY \
        --limit 5 \
        --ids 3692,3538
"""

import argparse
import csv
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.text_compressor import compress_for_llm


def load_prompt(template_path: str) -> str:
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def parse_record(row: list, api_key: str, base_url: str, model: str, prompt_template: str, max_retries: int = 2) -> dict:
    """对单条记录进行 LLM 解析，使用压缩后的文本。"""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError('请先安装 openai: pip install openai')

    client = OpenAI(api_key=api_key, base_url=base_url)

    rid = row[0]
    case_type = row[3]
    basic_facts = row[10]
    judgment_reason = row[11]
    judgment_essence = row[12]
    related_law = row[14]

    # Compress text before sending to LLM
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
                    {"role": "system", "content": "你是一个专业的法律文本解析工具。请严格按照要求输出 JSON。"},
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
            # 强制写入 case_type，不依赖 LLM 推断
            result['case_type'] = case_type
            result['_compression_strategy'] = strategy
            result['_compressed_chars'] = len(compressed_text)
            result['_original_chars'] = len(basic_facts) + len(judgment_reason) + len(judgment_essence) + len(related_law)
            
            # Fallback: if LLM didn't extract legal provisions, use rule-based extractor
            if not result.get('legal_provisions'):
                try:
                    from scripts.legal_provision_extractor import extract_provisions_from_record
                    provisions = extract_provisions_from_record(row)
                    if provisions:
                        # 格式标准化：从 legal_provision_extractor 格式转为本体论标准格式
                        result['legal_provisions'] = [
                            {
                                'statute': p.get('law_name', ''),
                                'article': p.get('article_number', ''),
                                'paragraph': p.get('clause', '') or p.get('sub_clause', '')
                            }
                            for p in provisions
                        ]
                except Exception:
                    pass
            
            return result

        except json.JSONDecodeError as e:
            if attempt < max_retries:
                time.sleep(1)
                continue
            return {
                'id': rid,
                'case_type': case_type,
                'error': f'JSON decode failed after {max_retries} retries: {str(e)}',
                '_compression_strategy': strategy
            }
        except Exception as e:
            if attempt < max_retries:
                time.sleep(2 ** attempt)
                continue
            return {
                'id': rid,
                'case_type': case_type,
                'error': str(e),
                '_compression_strategy': strategy
            }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--api-key', default=os.getenv('DEEPSEEK_API_KEY'))
    parser.add_argument('--base-url', default='https://api.deepseek.com/v1')
    parser.add_argument('--model', default='deepseek-v4-pro')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--ids', help='Comma-separated IDs to process')
    parser.add_argument('--max-workers', type=int, default=2)
    parser.add_argument('--prompt', default='scripts/prompts/guiding_case_extraction.txt')
    args = parser.parse_args()

    if not args.api_key:
        raise ValueError('API key required')

    prompt_template = load_prompt(args.prompt)

    # Load records
    records = []
    with open(args.input, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader)
        for row in reader:
            records.append(row)

    # Filter
    if args.ids:
        target_ids = set(args.ids.split(','))
        records = [r for r in records if r[0] in target_ids]

    if args.limit > 0:
        records = records[:args.limit]

    total = len(records)
    print(f"共计 {total} 条记录，待处理 {total} 条，并发 {args.max_workers}")

    results = []
    success = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(parse_record, r, args.api_key, args.base_url, args.model, prompt_template): r
            for r in records
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if 'error' not in result:
                success += 1
            else:
                failed += 1
                print(f"  错误: {result['id']} - {result['error']}")

    with open(args.output, 'w', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    print(f"\n完成！总处理 {total} 条，成功 {success} 条，失败 {failed} 条。")
    print(f"结果保存至: {args.output}")


if __name__ == '__main__':
    main()
