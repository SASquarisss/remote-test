#!/usr/bin/env python3
"""
正则解析效果评估脚本
用于评估从指导性案例中提取当事人、案号、法条的正则表达式效果。
"""

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


def clean_text(text: str) -> str:
    if not text or text == '\\N':
        return ''
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('u3000', '\u3000')
    text = text.replace('u2002', '\u2002')
    return text.strip()


def extract_parties(text: str) -> dict:
    """使用正则提取当事人"""
    if not text:
        return {}
    parties = {}

    patterns = [
        (r'\u539f\u544a([^\uff0c\u3002\uff1b\uff1a\u3001\n]{2,50}?)(?:\u8bc9\u79f0|\u6307\u51fa|\u5411|\u7ecf|\u63d0\u4f9b|\u8fa9\u79f0|\u786e\u8ba4|\u4e3b\u5f20|\u63d0\u8d77|\u63d0\u51fa)', '\u539f\u544a'),
        (r'\u88ab\u544a([^\uff0c\u3002\uff1b\uff1a\u3001\n]{2,50}?)(?:\u7ecf|\u63d0\u4f9b|\u8fa9\u79f0|\u786e\u8ba4|\u4e3b\u5f20|\u63d0\u4ea4|\u4e3a|\u88ab)', '\u88ab\u544a'),
        (r'\u88ab\u544a\u4eba([^\uff0c\u3002\uff1b\uff1a\u3001\n]{2,30}?)(?:\u7ecf|\u4e3a|\u7cfb|\u88ab)', '\u88ab\u544a\u4eba'),
        (r'\u4e0a\u8bc9\u4eba(?:\([^)]*\))?([^\uff0c\u3002\uff1b\uff1a\u3001\n]{2,50}?)(?:\u4e0a\u8bc9|\u4e0d\u670d|\u63d0\u8d77|\u7ecf|\u5411)', '\u4e0a\u8bc9\u4eba'),
        (r'\u88ab\u4e0a\u8bc9\u4eba(?:\([^)]*\))?([^\uff0c\u3002\uff1b\uff1a\u3001\n]{2,50}?)(?:\u7ecf|\u63d0\u4f9b|\u8fa9\u79f0|\u4e3a)', '\u88ab\u4e0a\u8bc9\u4eba'),
        (r'\u7533\u8bf7\u4eba(?:\([^)]*\))?([^\uff0c\u3002\uff1b\uff1a\u3001\n]{2,50}?)(?:\u5411|\u7533\u8bf7|\u63d0\u51fa|\u7ecf|\u4e3a)', '\u7533\u8bf7\u4eba'),
        (r'\u88ab\u7533\u8bf7\u4eba(?:\([^)]*\))?([^\uff0c\u3002\uff1b\uff1a\u3001\n]{2,50}?)(?:\u7ecf|\u88ab|\u4e3a)', '\u88ab\u7533\u8bf7\u4eba'),
        (r'\u7532\u65b9([^\uff0c\u3002\uff1b\uff1a\u3001\n]{2,50}?)(?:\u4e0e|\u548c|\u8bc9|\u7ecf)', '\u7532\u65b9'),
        (r'\u4e59\u65b9([^\uff0c\u3002\uff1b\uff1a\u3001\n]{2,50}?)(?:\u7ecf|\u63d0\u4f9b|\u8fa9\u79f0|\u786e\u8ba4|\u4e3b\u5f20)', '\u4e59\u65b9'),
        (r'\u88ab\u5bb3\u4eba([^\uff0c\u3002\uff1b\uff1a\u3001\n]{2,30}?)(?:\u7ecf|\u4e3a|\u88ab)', '\u88ab\u5bb3\u4eba'),
    ]

    for pat, role in patterns:
        m = re.search(pat, text)
        if m:
            parties[role] = m.group(1).strip()

    # 无标签模式
    if not parties:
        m = re.match(r'^([^\u4e0e\u548c]{2,30}?)(?:\u4e0e|\u548c)([^\uff0c\u3002\uff1b\uff1a\u3001\n]{2,30}?)(?:\u4e3a|\u7ecf)', text)
        if m:
            parties['\u7532\u65b9'] = m.group(1).strip()
            parties['\u4e59\u65b9'] = m.group(2).strip()

    if not parties:
        m = re.match(r'^([^\uff0c\u3002\uff1b\uff1a\u3001\n]{2,50}?)(?:\u8bc9\u79f0|\u8fab\u79f0|\u6307\u51fa)', text)
        if m:
            parties['\u539f\u544a'] = m.group(1).strip()

    return parties


def evaluate(csv_path: Path):
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=",", quotechar='"')
        header = next(reader)
        rows = list(reader)

    success = 0
    fail_reasons = Counter()
    case_type_success = defaultdict(lambda: [0, 0])

    for row in rows:
        case_type = row[3] if len(row) > 3 else ''
        case_type_success[case_type][1] += 1

        facts = clean_text(row[10]) if len(row) > 10 else ''
        reason = clean_text(row[11]) if len(row) > 11 else ''
        essence = clean_text(row[12]) if len(row) > 12 else ''

        found = False
        for text in [facts, reason, essence]:
            parties = extract_parties(text)
            if parties:
                found = True
                break

        if found:
            success += 1
            case_type_success[case_type][0] += 1
        else:
            fail_reasons[case_type] += 1

    total = len(rows)
    print(f"=== 正则提取评估结果（{total}条）===")
    print(f"成功提取: {success}/{total} ({success/total*100:.1f}%)")
    print(f"失败: {total - success}")

    print(f"\n=== 按案由分类成功率 ===")
    for ct, (s, t) in sorted(case_type_success.items(), key=lambda x: -x[1][1])[:20]:
        if t > 0:
            ratio = s / t * 100
            print(f"  {ct}: {s}/{t} ({ratio:.0f}%)")

    print(f"\n=== 失败案例分布 ===")
    for ct, cnt in fail_reasons.most_common(10):
        print(f"  {ct}: {cnt}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="CSV文件路径")
    args = parser.parse_args()
    evaluate(Path(args.input))
