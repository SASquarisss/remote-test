#!/usr/bin/env python3
"""
多案由 few-shot 对比测试：
对刑事/民事/行政各 2 条样本，跑三路（v3 / v4 / v4+类别few-shot）。
测试案由匹配的 few-shot 能否提升质量。
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

# 测试样本配置：每类 2 条
TEST_SAMPLES = {
    "civil": {
        "rows": [5286, 4070],  # 开设赌场案(刑事) / 名誉权纠纷(民事) — wait, 5286 is 刑事
        "prompt": "ontology/prompts/auto_v4_civil.txt",
    },
    "criminal": {
        "rows": [5286, 3287],  # 开设赌场案 / 开设赌场案
        "prompt": "ontology/prompts/auto_v4_criminal.txt",
    },
    "administrative": {
        "rows": [1611, 699],  # 行政确认(工伤) / 行政确认
        "prompt": "ontology/prompts/auto_v4_admin.txt",
    },
}

# 实际加载所有行，按 id 索引
csv_path = REPO_ROOT / "data/raw/test_10_new_v2.csv"
all_rows = {r.get("id", ""): r for r in load_csv(str(csv_path))}


def run_serial(rows, label, prompt, config):
    print(f"\n{'='*60}")
    print(f"🏃 {label}")
    print(f"{'='*60}")
    results = []
    successes = total_score = 0
    t0 = time.time()
    for idx, row in enumerate(rows):
        result = process_one(idx, row, prompt, config)
        results.append(result)
        if result["output"] and "error" not in result.get("eval", {}):
            successes += 1
            total_score += result["eval"].get("score", 0)
    dt = time.time() - t0
    avg = total_score / max(successes, 1)
    print(f"\n📊 汇总: 成功={successes}/{len(results)}, 平均分={avg:.1f}, 耗时={dt:.0f}s")
    return results, avg


def aggregate(results):
    scores = []
    prov = cases = subs = evids = ress = attys = judgs = 0
    for r in results:
        out = r.get("output") or {}
        ev = r.get("eval") or {}
        scores.append(ev.get("score", 0))
        prov += len(out.get("legal_provisions") or [])
        cases += len(out.get("court_cases") or [])
        subs += len(out.get("legal_subjects") or [])
        evids += len(out.get("evidence") or [])
        ress += len(out.get("judgment_results") or [])
        attys += len(out.get("attorneys") or [])
        judgs += len(out.get("judges") or [])
    return {
        "avg_score": round(sum(scores)/max(len(scores),1), 1),
        "provisions": prov, "cases": cases, "subjects": subs,
        "evidence": evids, "results": ress, "attorneys": attys, "judges": judgs,
    }


# 更合理的样本配置：用 test_10_new_v2.csv 中的
# 5286=刑事-开设赌场罪, 3287=刑事-开设赌场罪, 1611=行政-行政确认, 4070=民事-名誉权纠纷
# 但 5286 和 3287 都是刑事，没有民事。让我们找合适的
# 检查 test_10_new_v2.csv 的全部 case_type

def main():
    config = load_config()
    
    # 从CSV中按案由分组取样本
    samples = {"criminal": [], "civil": [], "administrative": []}
    for rid, row in sorted(all_rows.items()):
        ct = row.get("case_type", "")
        if ct.startswith("刑事") and len(samples["criminal"]) < 2:
            samples["criminal"].append(row)
        elif ct.startswith("民事") and len(samples["civil"]) < 2:
            samples["civil"].append(row)
        elif ct.startswith("行政") and len(samples["administrative"]) < 2:
            samples["administrative"].append(row)
        if all(len(v) >= 2 for v in samples.values()):
            break
    
    print("测试样本分配:")
    for cat, rows in samples.items():
        for r in rows:
            print(f"  {cat}: id={r.get('id','')} {r.get('case_type','')}")
    
    v3_prompt_path = REPO_ROOT / "scripts/prompts/guiding_case_ontology_aligned_v3.txt"
    v3_prompt = v3_prompt_path.read_text(encoding="utf-8")
    v4_prompt_path = REPO_ROOT / "ontology/prompts/auto_generated_v4.txt"
    v4_prompt = v4_prompt_path.read_text(encoding="utf-8")
    
    report_lines = ["# 多案由 few-shot 对比报告\n", f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"]
    
    all_summaries = {}
    
    for cat, cat_rows in samples.items():
        ct_label = {"criminal": "刑事", "civil": "民事", "administrative": "行政"}[cat]
        print(f"\n{'#'*60}")
        print(f"# 【{ct_label}案】对比")
        print(f"{'#'*60}")
        
        # 1) v3
        r1, a1 = run_serial(cat_rows, f"{ct_label} | v3", v3_prompt, config)
        out1 = REPO_ROOT / f"data_lake/fewshot_cmp_{cat}_v3.jsonl"
        with open(out1, "w") as f: 
            for r in r1: f.write(json.dumps(r, ensure_ascii=False) + "\n")
        
        # 2) v4 (无 few-shot)
        r2, a2 = run_serial(cat_rows, f"{ct_label} | v4", v4_prompt, config)
        out2 = REPO_ROOT / f"data_lake/fewshot_cmp_{cat}_v4.jsonl"
        with open(out2, "w") as f: 
            for r in r2: f.write(json.dumps(r, ensure_ascii=False) + "\n")
        
        # 3) v4 + 类别 few-shot
        v4fs_path = REPO_ROOT / f"ontology/prompts/auto_v4_{cat[:4]}.txt"
        v4fs_prompt = v4fs_path.read_text(encoding="utf-8")
        r3, a3 = run_serial(cat_rows, f"{ct_label} | v4+{cat} few-shot", v4fs_prompt, config)
        out3 = REPO_ROOT / f"data_lake/fewshot_cmp_{cat}_v4fs.jsonl"
        with open(out3, "w") as f: 
            for r in r3: f.write(json.dumps(r, ensure_ascii=False) + "\n")
        
        ag1, ag2, ag3 = aggregate(r1), aggregate(r2), aggregate(r3)
        all_summaries[cat] = (ag1, ag2, ag3)
        
        # 打印对比表
        print(f"\n📊 【{ct_label}案】对比:")
        print(f"| 指标 | v3 | v4 | v4+{cat} few-shot |")
        print(f"|---|---|---|---|")
        for m in ["avg_score", "provisions", "cases", "subjects", "evidence", "results", "attorneys", "judges"]:
            print(f"| {m} | {ag1[m]} | {ag2[m]} | {ag3[m]} |")
        
        report_lines.append(f"\n## 【{ct_label}案】对比\n")
        report_lines.append(f"| 指标 | v3 | v4 | v4+{cat} few-shot |")
        report_lines.append(f"|---|---|---|---|")
        for m in ["avg_score", "provisions", "cases", "subjects", "evidence", "results", "attorneys", "judges"]:
            report_lines.append(f"| {m} | {ag1[m]} | {ag2[m]} | {ag3[m]} |")
    
    # 整体汇总
    print(f"\n{'='*60}")
    print("📊 整体汇总")
    print(f"{'='*60}")
    header = f"| 类别 | v3 avg | v4 avg | v4+fs avg | v3→v4 | v3→v4+fs |"
    sep = f"|---|---|---|---|---|---|"
    print(f"\n{header}\n{sep}")
    report_lines.extend(["\n## 整体汇总\n", header, sep])
    for cat, (ag1, ag2, ag3) in all_summaries.items():
        cl = {"criminal": "刑事", "civil": "民事", "administrative": "行政"}[cat]
        d1 = round(ag2["avg_score"] - ag1["avg_score"], 1)
        d2 = round(ag3["avg_score"] - ag1["avg_score"], 1)
        s1 = f"+{d1}" if d1 > 0 else str(d1)
        s2 = f"+{d2}" if d2 > 0 else str(d2)
        print(f"| {cl} | {ag1['avg_score']} | {ag2['avg_score']} | {ag3['avg_score']} | {s1} | {s2} |")
        report_lines.append(f"| {cl} | {ag1['avg_score']} | {ag2['avg_score']} | {ag3['avg_score']} | {s1} | {s2} |")
    
    report_path = REPO_ROOT / "data_lake/fewshot_cmp_report.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\n报告: {report_path}")
    print("✅ 完成")


if __name__ == "__main__":
    main()
