#!/usr/bin/env python3
"""
三路对比测试：旧 v3 vs 新 v4 vs 新 v4+few-shot

复用 guiding_case_extractor_v3.process_one 串行跑。
测试 2 条样本，输出三份 JSONL + 对比报告。
"""

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path("/root/remote-test")
sys.path.insert(0, str(REPO_ROOT))

from extraction.llm_extractors.guiding_case_extractor_v3 import (
    load_csv, load_config, process_one
)


def run_serial(rows, prompt, config, label=""):
    print(f"\n{'='*60}")
    print(f"🏃 {label}")
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
    total = time.time() - t0
    avg = total_score / max(successes, 1)
    print(f"\n📊 汇总: 成功={successes}/{len(results)}, 平均分={avg:.1f}, 耗时={total:.0f}s")
    return results, avg


def main():
    config = load_config()
    csv_path = REPO_ROOT / "data/raw/test_10_new_v2.csv"
    rows = load_csv(str(csv_path))[:2]
    print(f"样本: {len(rows)} 条")

    # 准备三份 prompt
    prompts = [
        ("v3", REPO_ROOT / "scripts/prompts/guiding_case_ontology_aligned_v3.txt", ""),
        ("v4", REPO_ROOT / "ontology/prompts/auto_generated_v4.txt", ""),
        ("v4+fewshot", REPO_ROOT / "ontology/prompts/auto_v4_fewshot.txt", ""),
    ]
    all_results = {}

    for label, path, _ in prompts:
        prompt = path.read_text(encoding="utf-8")
        results, avg = run_serial(rows, prompt, config, label=label)
        out_path = REPO_ROOT / f"data_lake/compare3_{label}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        all_results[label] = (results, avg, out_path)

    # 聚合
    def aggregate(results):
        scores = []
        prov, cases, subs, evids, ress = 0, 0, 0, 0, 0
        for r in results:
            out = r.get("output") or {}
            ev = r.get("eval") or {}
            scores.append(ev.get("score", 0))
            prov += len(out.get("legal_provisions") or [])
            cases += len(out.get("court_cases") or [])
            subs += len(out.get("legal_subjects") or [])
            evids += len(out.get("evidence") or [])
            ress += len(out.get("judgment_results") or [])
        return {
            "avg_score": round(sum(scores)/max(len(scores),1), 1),
            "provisions": prov, "court_cases": cases,
            "subjects": subs, "evidence": evids, "results": ress,
        }

    print(f"\n{'='*60}")
    print("📊 三路对比报告")
    print(f"{'='*60}")
    metrics = ["avg_score", "provisions", "court_cases", "subjects", "evidence", "results"]
    header = "| 指标 | v3 | v4 | v4+fewshot |"
    sep = "|---|---|---|---|"
    print(f"\n{header}\n{sep}")
    for m in metrics:
        vs = {l: aggregate(r)[m] for l, (r, _, _) in all_results.items()}
        row = " | ".join(str(vs.get(l, "—")) for l in ["v3", "v4", "v4+fewshot"])
        print(f"| {m} | {row} |")
    print(f"\n结果文件:")
    for label, _, path in prompts:
        out = all_results[label][2]
        print(f"  {label}: {out}")

    # 保存报告
    report = [
        f"# 三路对比报告\n",
        f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"样本: {len(rows)} 条\n",
        header, sep,
    ]
    for m in metrics:
        vs = {l: aggregate(r)[m] for l, (r, _, _) in all_results.items()}
        row = " | ".join(str(vs.get(l, "—")) for l in ["v3", "v4", "v4+fewshot"])
        report.append(f"| {m} | {row} |")
    report.append("\n## 结论")
    rpt = REPO_ROOT / "data_lake/compare3_report.md"
    rpt.write_text("\n".join(report), encoding="utf-8")
    print(f"\n报告: {rpt}")
    print("✅ 完成")


if __name__ == "__main__":
    main()
