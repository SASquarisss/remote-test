#!/usr/bin/env python3
"""
法条引用补提管道

三层补提策略：
1. LLM 提取（最准确）
2. 正则补提（捕获显式引用）
3. 案由映射补提（后置，仅当文本中无显式引用时使用）

使用：
    python3 scripts/enrich_provisions.py \
        --input data/processed/test_20_v3.jsonl \
        --mapping data/reference/case_type_to_provisions.json \
        --output data/processed/test_20_v3_enriched.jsonl
"""

import json
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.extract_legal_provisions_regex import extract_legal_provisions, merge_provisions


def load_mapping(mapping_path: str) -> dict:
    with open(mapping_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def enrich_record(record: dict, mapping: dict, raw_text: str = "", use_mapping: bool = False) -> dict:
    """
    对单条记录进行法条补提。

    Args:
        record: LLM 提取结果
        mapping: 案由→法条映射表
        raw_text: 原始文本（用于正则补提）
        use_mapping: 是否使用案由映射补提（默认不使用，
                     mapping 结果仅作为候选存入 _candidate_provisions）
    """
    # Layer 1: LLM 提取
    llm_provisions = record.get('legal_provisions', [])

    # Layer 2: 正则补提
    regex_provisions = []
    if raw_text:
        regex_provisions = extract_legal_provisions(raw_text)

    merged = merge_provisions(llm_provisions, regex_provisions)

    # Layer 3: 案由映射补提（仅当 use_mapping=True 时写入 legal_provisions）
    candidate_provisions = []
    if not merged:
        case_type = record.get('case_type', '')
        if case_type and case_type in mapping:
            mapped = mapping[case_type]
            candidate_provisions = [
                {
                    'statute': p['statute'],
                    'article': p['article'],
                    'paragraph': p['paragraph'],
                    'source': 'case_type_mapping',
                    'applicability_score': p.get('applicability_score', 0.5)
                }
                for p in mapped
            ]
            if use_mapping:
                merged = candidate_provisions

    record['legal_provisions'] = merged
    if candidate_provisions and not use_mapping:
        record['_candidate_provisions'] = candidate_provisions

    record['_enrichment_meta'] = {
        'llm_count': len(llm_provisions),
        'regex_count': len(regex_provisions),
        'mapping_count': len(candidate_provisions),
        'final_count': len(merged),
        'source': 'llm' if llm_provisions else ('regex' if regex_provisions else ('mapping' if use_mapping and candidate_provisions else 'none'))
    }
    return record


def main():
    parser = argparse.ArgumentParser(description='Enrich legal provisions with regex + case-type mapping')
    parser.add_argument('--input', required=True, help='Input JSONL path')
    parser.add_argument('--mapping', default='data/reference/case_type_to_provisions.json', help='CaseType to provisions mapping JSON')
    parser.add_argument('--output', required=True, help='Output JSONL path')
    parser.add_argument('--raw-csv', help='Optional raw CSV for regex extraction text source')
    parser.add_argument('--use-mapping', action='store_true', help='Use case-type mapping as fallback for empty provisions')
    args = parser.parse_args()

    mapping = load_mapping(args.mapping)

    # Load raw records if CSV provided
    raw_map = {}
    if args.raw_csv:
        import csv
        with open(args.raw_csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for row in reader:
                rid = row[0]
                texts = [row[10], row[11], row[12], row[14], row[18]]  # basic_facts, judgment_reason, judgment_essence, related_law, judgment_mean
                raw_map[rid] = ' '.join(
                    t.replace('<p>', '').replace('</p>', '\n').replace('<br/>', '\n').replace('&nbsp;', ' ')
                    for t in texts if t and t != '\\N'
                )

    with open(args.input, 'r', encoding='utf-8') as fin, open(args.output, 'w', encoding='utf-8') as fout:
        for line in fin:
            if not line.strip():
                continue
            record = json.loads(line)
            raw_text = raw_map.get(record.get('id', ''), '')
            enriched = enrich_record(record, mapping, raw_text, use_mapping=args.use_mapping)
            fout.write(json.dumps(enriched, ensure_ascii=False) + '\n')

    print(f"Enrichment complete. Output: {args.output}")


if __name__ == '__main__':
    main()
