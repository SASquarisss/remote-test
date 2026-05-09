#!/usr/bin/env python3
"""
对比测试：旧 v3 prompt vs 新自动生成 prompt 的提取效果。

直接复用 guiding_case_extractor_v3.process_one。
测试 5 条样本，输出两份 JSONL + 对比报告。
"""

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path("/root/remote-test")
sys.path.insert(0, str(REPO_ROOT))

from extraction.llm_extractors.guiding_case_extractor_v3 import (
    load_csv, load_config, load_prompt, process_one
)


def run_serial(rows, prompt, config, label=""):
    """串行跑（避免并发可能导致的 API 错误交叉）"""
    print(f"\n{'='*60}")
    print(f"🏃 测试: {label}")
    print(f"   记录数: {len(rows)}")
    print(f"{'='*60}")

    results = []
    successes = 0
    total_score = 0.0
    t0 = time.time()

    for idx, row in enumerate(rows):
        result = process_one(idx, row, prompt, config)
        results.append(result)
        if result["output"] is not None and "error" not in result.get("eval", {}):
            successes += 1
            total_score += result["eval"].get("score", 0)

    total_time = time.time() - t0
    avg = total_score / max(successes, 1)

    print(f"\n📊 汇总 ({label}):")
    print(f"   成功: {successes}/{len(results)}, 平均分: {avg:.1f}, 耗时: {total_time:.0f}s")

    return results, avg


def main():
    config = load_config()

    csv_path = REPO_ROOT / "data/raw/test_10_new_v2.csv"
    rows = load_csv(str(csv_path))
    test_rows = rows[:2]
    print(f"加载 {len(rows)} 条，取前 {len(test_rows)} 条测试")

    # === 旧 v3 prompt ===
    v3_prompt = load_prompt("v3")
    v3_results, v3_avg = run_serial(test_rows, v3_prompt, config, label="旧 v3 提示词")

    v3_out = REPO_ROOT / "data_lake/compare_test_v3.jsonl"
    with open(v3_out, "w", encoding="utf-8") as f:
        for r in v3_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  输出: {v3_out}")

    # === 新 prompt ===
    v4_prompt_path = REPO_ROOT / "ontology/prompts/auto_generated_v4.txt"
    v4_prompt = v4_prompt_path.read_text(encoding="utf-8")
    v4_results, v4_avg = run_serial(test_rows, v4_prompt, config, label="新自动生成提示词")

    v4_out = REPO_ROOT / "data_lake/compare_test_v4.jsonl"
    with open(v4_out, "w", encoding="utf-8") as f:
        for r in v4_results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  输出: {v4_out}")

    # === 对比报告 ===
    print(f"\n{'='*60}")
    print("📊 新旧提示词对比报告")
    print(f"{'='*60}")

    # 聚合统计
    def aggregate(results):
        totals = {"provisions": 0, "court_cases": 0, "subjects": 0,
                   "judges": 0, "attorneys": 0, "evidence": 0, "judgment_results": 0}
        scores = []
        for r in results:
            out = r.get("output") or {}
            ev = r.get("eval") or {}
            scores.append(ev.get("score", 0))
            totals["provisions"] += len(out.get("legal_provisions") or [])
            totals["court_cases"] += len(out.get("court_cases") or [])
            totals["subjects"] += len(out.get("legal_subjects") or [])
            totals["judges"] += len(out.get("judges") or [])
            totals["attorneys"] += len(out.get("attorneys") or [])
            totals["evidence"] += len(out.get("evidence") or [])
            totals["judgment_results"] += len(out.get("judgment_results") or [])
        return {
            "avg_score": round(sum(scores) / max(len(scores), 1), 1),
            "total_provisions": totals["provisions"],
            "total_court_cases": totals["court_cases"],
            "total_subjects": totals["subjects"],
            "total_judges": totals["judges"],
            "total_evidence": totals["evidence"],
            "total_results": totals["judgment_results"],
        }

    ag3 = aggregate(v3_results)
    ag4 = aggregate(v4_results)

    print(f"\n| 指标 | 旧 (v3) | 新 (自动生成) | 变化 |")
    print(f"|---|---|---|---|")
    for metric in ["avg_score", "total_provisions", "total_court_cases",
                    "total_subjects", "total_judges", "total_evidence", "total_results"]:
        v3v = ag3[metric]
        v4v = ag4[metric]
        diff = round(v4v - v3v, 1)
        sign = "+" if diff > 0 else ""
        diff_str = f"{sign}{diff}" if diff != 0 else "—"
        print(f"| {metric} | {v3v} | {v4v} | {diff_str} |")

    report_path = REPO_ROOT / "data_lake/compare_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"""# 新旧提示词对比报告

测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
测试样本: {len(test_rows)} 条 (from test_10_new_v2.csv)

## 结果对比

| 指标 | 旧 (v3) | 新 (自动生成) | 变化 |
|---|---|---|---|
""")
        for metric in ["avg_score", "total_provisions", "total_court_cases",
                        "total_subjects", "total_judges", "total_evidence", "total_results"]:
            v3v = ag3[metric]
            v4v = ag4[metric]
            diff = round(v4v - v3v, 1)
            sign = "+" if diff > 0 else ""
            diff_str = f"{sign}{diff}" if diff != 0 else "—"
            f.write(f"| {metric} | {v3v} | {v4v} | {diff_str} |\n")
        f.write("""
## 结论

- 新自动生成提示词从 YAML 本体直接渲染，确保枚举值与本体定义完全一致
- 枚举值参考表带中文映射（`plaintiff → 原告`），LLM 无需从自然语言推导枚举值
- JSON Schema 自动生成，与本体字段定义同步
- 维护模式：改 YAML 本体 → `python scripts/generate_prompt.py --output prompts/auto_v4.txt`
""")

    print(f"\n报告: {report_path}")
    print("✅ 对比测试完成")


if __name__ == "__main__":
    main()
