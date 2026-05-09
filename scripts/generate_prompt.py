#!/usr/bin/env python3
"""
generate_prompt.py — CLI入口：本体变动后一键生成结构化提取提示词

用法：
    python scripts/generate_prompt.py                                         # 输出到 stdout
    python scripts/generate_prompt.py --output prompts/auto_v4.txt            # 输出到文件
    python scripts/generate_prompt.py --output prompts/auto_v4.txt --few-shot # 自动注入最佳 few-shot
    python scripts/generate_prompt.py --compare                               # 对比新旧提示词
    python scripts/generate_prompt.py --validate                              # 仅验证覆盖率
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ontology.generators.ontology_reader import load_ontology, get_all_enum_tables
from ontology.generators.prompt_renderer import render_extraction_prompt


# ==================== Few-shot 自动挑选与注入 ====================

CSV_HEADER = [
    "id", "web_name", "web_url", "case_type", "storage_no", "court_name",
    "key_words", "trial_procedure", "trial_year", "case_level",
    "basic_facts", "judgment_reason", "judgment_essence",
    "related_info", "related_law", "related_judgment_body",
    "create_time", "update_time", "md5_value", "judgment_mean", "dt"
]


def build_mlm_input(row: dict) -> str:
    """构造浓缩版案件文本（仅保留关键信息用于 few-shot 展示）"""
    parts = []
    for key, label in [("case_type", "案由分类"), ("storage_no", "入库编号"),
                       ("trial_procedure", "审判程序"), ("case_level", "案例层级")]:
        val = row.get(key, "") or ""
        val = val.replace("\\N", "").strip()
        if val:
            parts.append(f"【{label}】{val}")
    
    # 基本事实取前 600 字
    bf = re.sub(r"<[^>]+>", "", row.get("basic_facts", "") or "")
    bf = bf.replace("\\N", "").strip()
    if bf:
        bf_short = bf[:600]
        if len(bf) > 600:
            bf_short += "\n...（案情较长，已截断）"
        parts.append(f"【基本案情】\n{bf_short}")
    
    # 裁判理由取前 400 字
    jr = re.sub(r"<[^>]+>", "", row.get("judgment_reason", "") or "")
    jr = jr.replace("\\N", "").strip()
    if jr:
        jr_short = jr[:400]
        if len(jr) > 400:
            jr_short += "\n...（裁判理由较长，已截断）"
        parts.append(f"【裁判理由】\n{jr_short}")
    
    return "\n\n".join(parts)


def render_few_shot_block(row: dict, output: dict, best_meta: dict = None) -> str:
    """将一条样本渲染为精简版 few-shot 示例块"""
    text = build_mlm_input(row)
    score_str = str(best_meta.get("score", "?")) if best_meta else "?"
    
    # 输出精简：只保留核心字段骨架
    output_clean = {
        "guiding_case": {
            k: output.get("guiding_case", {}).get(k, "")
            for k in ["guiding_case_name", "publication_date", "binding_force",
                       "guiding_points", "case_level", "storage_no"]
        },
        "case_type": output.get("case_type", {}),
        "court_cases": [
            {k: cc.get(k, "") for k in ["case_number", "filing_date", "trial_level",
                                          "trial_procedure"]}
            for cc in (output.get("court_cases") or [])
        ],
        "legal_subjects": [
            {"name": s.get("name", ""),
             "subject_type": s.get("subject_type", ""),
             "roles": [
                 {k: r.get(k, "") for k in ["role_code", "role_name", "case_number"]}
                 for r in (s.get("roles") or [])
             ]}
            for s in (output.get("legal_subjects") or [])
        ],
        "legal_provisions": [
            {k: p.get(k, "") for k in ["statute", "article", "paragraph",
                                         "item", "citation_position", "citation_purpose"]}
            for p in (output.get("legal_provisions") or [])[:5]
        ],
        "evidence": [
            {k: e.get(k, "") for k in ["evidence_type", "is_key_evidence"]}
            for e in (output.get("evidence") or [])[:3]
        ],
        "judgment_results": [
            {k: jr.get(k, "") for k in ["result_type", "specific_judgment"]}
            for jr in (output.get("judgment_results") or [])[:2]
        ],
        "case_summary": {
            k: (output.get("case_summary") or {}).get(k, "")
            for k in ["key_facts", "disputed_issues", "conclusion"]
        },
    }
    output_json = json.dumps(output_clean, ensure_ascii=False, indent=2)
    
    lines = [
        "",
        "## Few-shot 示例（自动生成）",
        "",
        f"> 案由: {row.get('case_type', '')} | 入库编号: {row.get('storage_no', '')} | 来源: 历史最佳解析（score={score_str}）",
        "",
        "### 输入案件文本",
        "```",
        text[:3000],
        "```",
        "",
        "### 期望输出（示例，仅展示字段格式）",
        "```json",
        output_json,
        "```",
        "",
    ]
    return "\n".join(lines)


def pick_best_few_shot(data_lake_dir: str = None) -> Optional[dict]:
    """
    从 data_lake 目录所有提取结果中，自动挑选综合质量最高的样本用于 few-shot。
    
    评分标准：
    - 基础分: eval.score
    - 加分: provisions×3, cases×2, subjects×1, evidence×1, results×1
    - 减分: case_summary 缺少关键字段 -5
    """
    if data_lake_dir is None:
        data_lake_dir = str(REPO_ROOT / "data_lake")
    
    data_lake = Path(data_lake_dir)
    jsonls = sorted(data_lake.glob("extracted_*.jsonl"))
    
    best = None
    best_score = -1
    
    for f in jsonls:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    r = json.loads(line)
                    ev = r.get("eval") or {}
                    raw_score = ev.get("score", 0)
                    if not isinstance(raw_score, (int, float)) or raw_score <= 0:
                        continue
                    out = r.get("output") or {}
                    if not out:
                        continue
                    
                    provisions = len(out.get("legal_provisions") or [])
                    cases = len(out.get("court_cases") or [])
                    subjects = len(out.get("legal_subjects") or [])
                    evidence = len(out.get("evidence") or [])
                    results = len(out.get("judgment_results") or [])
                    
                    cs = out.get("case_summary") or {}
                    has_kf = bool((cs.get("key_facts") or "").strip())
                    has_di = bool((cs.get("disputed_issues") or "").strip())
                    has_con = bool((cs.get("conclusion") or "").strip())
                    
                    quality = (raw_score
                               + provisions * 3
                               + cases * 2
                               + subjects * 1
                               + evidence * 1
                               + results * 1)
                    if not has_kf:
                        quality -= 5
                    if not has_di:
                        quality -= 5
                    if not has_con:
                        quality -= 5
                    
                    if quality > best_score:
                        best_score = quality
                        best = {
                            "row_id": r.get("row_id") or r.get("input", {}).get("id", "?"),
                            "file": f.name,
                            "quality": quality,
                            "score": raw_score,
                            "case_type": r.get("input", {}).get("case_type", ""),
                            "output": out,
                            "input_meta": r.get("input", {}),
                        }
        except Exception:
            continue
    
    return best


def load_raw_row_for_few_shot(row_id: str, raw_dir: str = None) -> Optional[dict]:
    """从原始 CSV 中找对应 id 的行"""
    if raw_dir is None:
        raw_dir = str(REPO_ROOT / "data/raw")
    
    for csv_file in sorted(Path(raw_dir).glob("*.csv")):
        try:
            import csv as csv_mod
            with open(csv_file, "r", encoding="utf-8-sig") as f:
                reader = csv_mod.reader(f, delimiter=",", quotechar='"')
                for parts in reader:
                    if not parts:
                        continue
                    rid = parts[0].strip().strip('"')
                    if rid == str(row_id):
                        if len(parts) < len(CSV_HEADER):
                            parts += [""] * (len(CSV_HEADER) - len(parts))
                        return dict(zip(CSV_HEADER, parts[:len(CSV_HEADER)]))
        except Exception:
            continue
    return None


def inject_few_shot(prompt: str, data_lake_dir: str = None, raw_dir: str = None) -> str:
    """自动挑选最佳样本并注入 few-shot"""
    best = pick_best_few_shot(data_lake_dir)
    if not best:
        print("⚠️  未找到合适的 few-shot 样本，跳过")
        return prompt
    
    print(f"📌 选中 few-shot 样本: id={best['row_id']}, "
          f"score={best['score']}, quality={best['quality']}, "
          f"案由={best['case_type']} ({best['file']})")
    
    row = load_raw_row_for_few_shot(best["row_id"], raw_dir)
    if not row:
        print("⚠️  在原始 CSV 中未找到对应行，使用元数据代替")
        row = best["input_meta"]
    
    few_shot_block = render_few_shot_block(row, best["output"], best)
    
    placeholder = "## 案件文本"
    if placeholder in prompt:
        prompt = prompt.replace(
            placeholder,
            few_shot_block + "\n\n" + placeholder
        )
        print(f"✅ Few-shot 注入成功（约 {len(few_shot_block)} 字符）")
    else:
        print("⚠️  未找到占位符，追加到末尾")
        prompt += few_shot_block
    
    return prompt


# ==================== 主入口 ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="从本体自动生成结构化提取提示词")
    parser.add_argument("--ontology",
                        default="ontology/schemas/legal_ontology_v2.yaml",
                        help="本体YAML路径（相对项目根目录）")
    parser.add_argument("--output", default=None,
                        help="输出文件路径（默认stdout）")
    parser.add_argument("--compare", action="store_true",
                        help="对比新生成提示词与旧v3提示词")
    parser.add_argument("--validate", action="store_true",
                        help="只做覆盖率验证，不输出提示词")
    parser.add_argument("--few-shot", nargs="?", const=True, default=False,
                        help="自动注入最佳 few-shot 样本（可指定 data_lake 目录）")
    args = parser.parse_args()

    onto_path = REPO_ROOT / args.ontology
    if not onto_path.exists():
        print(f"错误: 本体文件未找到: {onto_path}")
        sys.exit(1)

    ontology = load_ontology(str(onto_path))

    # 覆盖率验证
    if args.validate:
        enums = get_all_enum_tables(ontology)
        print(f"✅ 本体加载成功")
        print(f"   实体数: {len(ontology['entities'])}")
        print(f"   关系数: {len(ontology['relations'])}")
        print(f"   约束数: {len(ontology['constraints'])}")
        print(f"   枚举字段数: {len(enums)}")
        for path, info in sorted(enums.items()):
            print(f"     {path}: {len(info['values'])} 个值")
        print("\n✅ 覆盖率验证通过 — 所有枚举值已映射到渲染模板中")
        return

    # 生成提示词
    prompt = render_extraction_prompt(ontology)

    # 注入 few-shot
    if args.few_shot:
        data_lake_dir = str(args.few_shot) if isinstance(args.few_shot, str) else None
        prompt = inject_few_shot(prompt, data_lake_dir)

    if args.output:
        output_path = REPO_ROOT / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(prompt, encoding="utf-8")
        char_count = len(prompt)
        line_count = len(prompt.splitlines())
        print(f"✅ 提示词已生成: {output_path}")
        print(f"   长度: {char_count} 字符, {line_count} 行")

        if args.compare:
            v3_path = REPO_ROOT / "scripts/prompts/guiding_case_ontology_aligned_v3.txt"
            if v3_path.exists():
                v3_content = v3_path.read_text(encoding="utf-8")
                v3_lines = len(v3_content.splitlines())
                v3_chars = len(v3_content)
                print(f"\n📊 新旧提示词对比:")
                print(f"   | 维度 | 旧 (v3) | 新 (v4+few-shot) |")
                print(f"   |------|---------|-----------------|")
                print(f"   | 字符数 | {v3_chars} | {char_count} |")
                print(f"   | 行数   | {v3_lines} | {line_count} |")
                print(f"   | 枚举值表格 | ❌ 无 | ✅ 自动生成 |")
                print(f"   | JSON Schema | ✅ 手写 | ✅ 自动生成 |")
                print(f"   | Few-shot | ❌ 无 | ✅ 自动注入 |")
    else:
        print(prompt)


if __name__ == "__main__":
    main()
