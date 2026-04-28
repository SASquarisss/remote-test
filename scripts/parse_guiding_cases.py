#!/usr/bin/env python3
"""
指导性案例 CSV 解析脚本

功能:
- 自动检测分隔符（Tab 或逗号）
- 将 \N 转为 None
- 可选脱除 HTML 标签
- 字段校验与统计
- 输出 JSON + 清洗后 CSV

使用:
    python scripts/parse_guiding_cases.py data/raw/guiding_cases.csv
"""

import argparse
import csv
import json
import re
from pathlib import Path
from collections import Counter


HEADERS = [
    "id", "web_name", "web_url", "case_type", "storage_no", "court_name",
    "key_words", "trial_procedure", "trial_year", "case_level",
    "basic_facts", "judgment_reason", "judgment_essence", "related_info",
    "related_law", "related_judgment_body", "create_time", "update_time",
    "md5_value", "judgment_mean", "dt",
]

LONG_TEXT_FIELDS = {"basic_facts", "judgment_reason", "judgment_essence", "related_info"}


def detect_delimiter(file_path: Path) -> str:
    """检测 CSV 分隔符: 先试 Tab，再试逗号。"""
    text = file_path.read_text(encoding="utf-8", errors="replace")
    first_line = text.splitlines()[0] if text else ""
    tab_count = first_line.count("\t")
    comma_count = first_line.count(",")
    return "\t" if tab_count > comma_count else ","


def strip_html(text: str | None) -> str | None:
    """去除 HTML 标签，保留纯文本。"""
    if text is None:
        return None
    # 去掉所有标签
    text = re.sub(r"<[^>]+>", "", text)
    # 去掉 HTML 实体
    text = text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&amp;", "&")
    return text.strip()


def parse_record(row: dict) -> dict:
    """解析单行数据: 类型转换、空值处理。"""
    rec = {}
    for h in HEADERS:
        val = row.get(h, row.get(h.lower(), "")).strip()
        if val == r"\N" or val == "":
            rec[h] = None
        else:
            rec[h] = val

    # trial_year 统一格式
    if rec.get("trial_year"):
        rec["trial_year"] = rec["trial_year"].replace("/", ".")

    return rec


def validate(records: list[dict]) -> dict:
    """字段校验统计。"""
    total = len(records)
    stats = {"total": total, "null_counts": {}, "type_counts": {}}

    for h in HEADERS:
        null_count = sum(1 for r in records if r.get(h) is None)
        stats["null_counts"][h] = null_count

    # 案由统计
    case_types = Counter(r.get("case_type") for r in records if r.get("case_type"))
    stats["case_type_top5"] = case_types.most_common(5)

    # 审理程序统计
    procedures = Counter(r.get("trial_procedure") for r in records if r.get("trial_procedure"))
    stats["trial_procedure"] = dict(procedures)

    # 法院统计
    courts = Counter(r.get("court_name") for r in records if r.get("court_name"))
    stats["court_top5"] = courts.most_common(5)

    return stats


def export_json(records: list[dict], out_path: Path):
    out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[JSON] {len(records)} records -> {out_path}")


def export_csv(records: list[dict], out_path: Path):
    if not records:
        return
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        for r in records:
            writer.writerow({k: (v if v is not None else "") for k, v in r.items()})
    print(f"[CSV]  {len(records)} records -> {out_path}")


def main():
    parser = argparse.ArgumentParser(description="指导性案例 CSV 解析脚本")
    parser.add_argument("input", type=Path, help="输入 CSV 文件路径")
    parser.add_argument("--strip-html", action="store_true", help="去除 HTML 标签")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"), help="输出目录")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} 不存在")
        return

    delim = detect_delimiter(args.input)
    print(f"[检测] 分隔符: {'Tab' if delim == chr(9) else '逗号'}")

    records = []
    with args.input.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f, delimiter=delim)
        for row in reader:
            rec = parse_record(row)
            if args.strip_html:
                for h in LONG_TEXT_FIELDS:
                    rec[h] = strip_html(rec.get(h))
            records.append(rec)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    base_name = args.input.stem

    json_path = args.output_dir / f"{base_name}.json"
    csv_path = args.output_dir / f"{base_name}_clean.csv"

    export_json(records, json_path)
    export_csv(records, csv_path)

    # 校验统计
    stats = validate(records)
    print(f"\n━━━ 校验统计 ━━━")
    print(f"总记录数: {stats['total']}")
    print(f"案由 Top5: {stats['case_type_top5']}")
    print(f"审理程序: {stats['trial_procedure']}")
    print(f"法院 Top5: {stats['court_top5']}")
    print(f"\n空值率较高的字段:")
    for h, cnt in sorted(stats["null_counts"].items(), key=lambda x: -x[1]):
        if cnt > 0:
            print(f"  {h}: {cnt}/{stats['total']} ({cnt/stats['total']*100:.1f}%)")


if __name__ == "__main__":
    main()
