#!/usr/bin/env python3
"""
generate_prompt.py — CLI入口：本体变动后一键生成结构化提取提示词

用法：
    python scripts/generate_prompt.py                                          # 输出到 stdout
    python scripts/generate_prompt.py --output prompts/auto_v4.txt             # 输出到文件
    python scripts/generate_prompt.py --output prompts/auto_v4.txt --few-shot  # 自动注入按案由匹配的 few-shot
    python scripts/generate_prompt.py --validate                               # 仅验证覆盖率

Few-shot 自动选取逻辑：
  1. 从 data_lake 所有 extracted_*.jsonl 中扫描
  2. 按刑事/民事/行政分类，分别用质量评分公式选取最佳样本
  3. 生成时根据目标样本案由注入对应类别的 few-shot

质量评分 = eval.score + provisions×3 + cases×2 + subjects + evidence + results
            - (case_summary 缺失 key_facts/disputed_issues/conclusion 各扣5分)
"""

import csv as csv_mod
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ontology.generators.ontology_reader import load_ontology, get_all_enum_tables
from ontology.generators.prompt_renderer import render_extraction_prompt
from scripts.data_lake_layers import (
    OFFICIAL_CANDIDATE_LAYER,
    STRUCTURED_CANDIDATE_LAYER,
    get_fewshot_candidate_files,
    summarize_data_lake_layers,
)


# ==================== 案由分类 ====================

CASE_CATEGORIES = ["civil", "criminal", "administrative"]

def classify_case_type(case_type: str) -> str:
    ct = (case_type or "").strip()
    if ct.startswith("刑事"): return "criminal"
    if ct.startswith("民事"): return "civil"
    if ct.startswith("行政"): return "administrative"
    return "other"


def summarize_graph_coverage(output: dict) -> dict:
    """统计 few-shot 样本中的图谱结构覆盖度。"""
    facts = output.get("facts") or []
    focuses = output.get("dispute_focuses") or []
    relations = output.get("relations") or []
    nonempty_relations = [r for r in relations if (r.get("relation_type") or "").strip()
                          and (r.get("source_id") or "").strip()
                          and (r.get("target_id") or "").strip()]
    relation_types = sorted({(r.get("relation_type") or "").strip() for r in nonempty_relations if (r.get("relation_type") or "").strip()})
    return {
        "facts": len(facts),
        "focuses": len(focuses),
        "relations": len(nonempty_relations),
        "relation_types": relation_types,
        "graph_ready": bool(nonempty_relations) and (len(facts) > 0 or len(focuses) > 0),
        "rich_graph": bool(nonempty_relations) and len(facts) > 0 and len(focuses) > 0,
    }


# ==================== Few-shot 数据加载 ====================

CSV_HEADER = [
    "id", "web_name", "web_url", "case_type", "storage_no", "court_name",
    "key_words", "trial_procedure", "trial_year", "case_level",
    "basic_facts", "judgment_reason", "judgment_essence",
    "related_info", "related_law", "related_judgment_body",
    "create_time", "update_time", "md5_value", "judgment_mean", "dt"
]


def build_fewshot_input_text(row: dict) -> str:
    """构造浓缩版 few-shot 输入文本"""
    parts = []
    for key, label in [("case_type", "案由分类"), ("storage_no", "入库编号"),
                       ("trial_procedure", "审判程序"), ("case_level", "案例层级")]:
        val = row.get(key, "") or ""
        val = val.replace("\\N", "").strip()
        if val:
            parts.append(f"【{label}】{val}")
    bf = re.sub(r"<[^>]+>", "", row.get("basic_facts", "") or "")
    bf = bf.replace("\\N", "").strip()
    if bf:
        bf_short = bf[:600]
        if len(bf) > 600:
            bf_short += "\n...（案情较长，已截断）"
        parts.append(f"【基本案情】\n{bf_short}")
    jr = re.sub(r"<[^>]+>", "", row.get("judgment_reason", "") or "")
    jr = jr.replace("\\N", "").strip()
    if jr:
        jr_short = jr[:400]
        if len(jr) > 400:
            jr_short += "\n...（裁判理由较长，已截断）"
        parts.append(f"【裁判理由】\n{jr_short}")
    return "\n\n".join(parts)


def load_best_few_shots(data_lake_dir: str = None) -> dict:
    """
    扫描 data_lake，返回 {category: {记录信息}}。
    每个类别选取质量最高的1条。
    """
    if data_lake_dir is None:
        data_lake_dir = str(REPO_ROOT / "data_lake")
    dl = Path(data_lake_dir)
    jsonls = get_fewshot_candidate_files(dl)

    # 按类别收集
    candidates: dict = defaultdict(list)

    for f in jsonls:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line: continue
                    r = json.loads(line)
                    ev = r.get("eval") or {}
                    out = r.get("output") or {}
                    if not out or not ev: continue
                    raw = ev.get("score", 0)
                    if not isinstance(raw, (int, float)) or raw <= 0: continue

                    inp = r.get("input") or {}
                    ct = inp.get("case_type", "")
                    cat = classify_case_type(ct)
                    if cat == "other": continue

                    provisions = len(out.get("legal_provisions") or [])
                    cases = len(out.get("court_cases") or [])
                    subjects = len(out.get("legal_subjects") or [])
                    evidence = len(out.get("evidence") or [])
                    results = len(out.get("judgment_results") or [])
                    elements = len(out.get("legal_provision_elements") or [])
                    cs = out.get("case_summary") or {}
                    has_kf = bool((cs.get("key_facts") or "").strip())
                    has_di = bool((cs.get("disputed_issues") or "").strip())
                    has_con = bool((cs.get("conclusion") or "").strip())

                    quality = raw + provisions*3 + cases*2 + subjects + evidence + results + elements*2
                    if not has_kf: quality -= 5
                    if not has_di: quality -= 5
                    if not has_con: quality -= 5
                    # v2.2: 新字段覆盖加分
                    for cc in (out.get("court_cases") or []):
                        if cc.get("dispute_resolution_type"): quality += 5
                        if cc.get("party_count"): quality += 10
                    for e in (out.get("evidence") or []):
                        if e.get("expert_institution"): quality += 5
                        if e.get("admission_status"): quality += 3
                    for jr in (out.get("judgment_results") or []):
                        if jr.get("cost_allocation"): quality += 5
                        if jr.get("reasoning"): quality += 3
                    cs = out.get("case_summary") or {}
                    if cs.get("claim_amount"): quality += 5
                    if cs.get("judgment_amount"): quality += 5
                    # v3: 新实体加分
                    graph_cov = summarize_graph_coverage(out)
                    facts = graph_cov["facts"]
                    focuses = graph_cov["focuses"]
                    rels = graph_cov["relations"]
                    rel_type_count = len(graph_cov["relation_types"])
                    quality += facts * 2 + focuses * 3 + rels * 4 + rel_type_count * 5
                    if graph_cov["graph_ready"]:
                        quality += 18
                    if graph_cov["rich_graph"]:
                        quality += 15

                    candidates[cat].append({
                        "quality": quality, "score": raw,
                        "row_id": r.get("row_id") or inp.get("id", "?"),
                        "file": f.name,
                        "case_type": ct,
                        "output": out,
                        "input_meta": inp,
                        "details": {"provisions": provisions, "cases": cases,
                                    "subjects": subjects, "evidence": evidence, "results": results,
                                    "key_facts": has_kf, "disputed": has_di, "conclusion": has_con,
                                    "facts": facts, "focuses": focuses, "relations": rels,
                                    "relation_types": rel_type_count,
                                    "graph_ready": graph_cov["graph_ready"],
                                    "rich_graph": graph_cov["rich_graph"]},
                    })
        except Exception:
            continue

    # 每类取 top1
    best = {}
    for cat in CASE_CATEGORIES:
        items = candidates.get(cat, [])
        if not items:
            print(f"  ⚠️  {cat}: 无可用样本")
            continue
        relation_ready_items = [x for x in items if x["details"].get("graph_ready")]
        rich_graph_items = [x for x in items if x["details"].get("rich_graph")]
        if rich_graph_items:
            pool = rich_graph_items
        elif relation_ready_items:
            pool = relation_ready_items
        else:
            pool = items
        pool.sort(key=lambda x: (
            1 if x["details"].get("rich_graph") else 0,
            1 if x["details"].get("graph_ready") else 0,
            x["details"].get("relations", 0),
            x["details"].get("relation_types", 0),
            x["details"].get("focuses", 0),
            x["details"].get("facts", 0),
            x["quality"],
        ), reverse=True)
        best[cat] = pool[0]
        d = pool[0]["details"]
        print(f"  ✅ {cat}: id={pool[0]['row_id']}, quality={pool[0]['quality']}, "
              f"score={pool[0]['score']}, provisions={d['provisions']}, "
              f"cases={d['cases']}, subjects={d['subjects']}, "
              f"facts={d['facts']}, focuses={d['focuses']}, relations={d['relations']} "
              f"({pool[0]['case_type']})")
    return best


def load_raw_row(row_id: str, raw_dir: str = None) -> Optional[dict]:
    """从原始 CSV 中找对应 id 的行"""
    if raw_dir is None:
        raw_dir = str(REPO_ROOT / "data/raw")
    for csv_file in sorted(Path(raw_dir).glob("*.csv")):
        try:
            with open(csv_file, "r", encoding="utf-8-sig") as f:
                reader = csv_mod.reader(f, delimiter=",", quotechar='"')
                for parts in reader:
                    if not parts: continue
                    rid = parts[0].strip().strip('"')
                    if rid == str(row_id):
                        if len(parts) < len(CSV_HEADER):
                            parts += [""] * (len(CSV_HEADER) - len(parts))
                        return dict(zip(CSV_HEADER, parts[:len(CSV_HEADER)]))
        except Exception:
            continue
    return None


def clean_fewshot_output(output: dict) -> dict:
    """精简输出为字段骨架，用于 few-shot 示例"""
    gc = output.get("guiding_case") or {}
    return {
        "guiding_case": {
            k: gc.get(k, "") for k in ["guiding_case_name", "publication_date",
                                        "binding_force", "guiding_points", "case_level", "storage_no"]
        },
        "case_type": output.get("case_type", {}),
        "court_cases": [
            {k: cc.get(k, "") for k in ["case_number", "filing_date", "trial_level", "trial_procedure",
                                          "dispute_resolution_type", "party_count"]}
            for cc in (output.get("court_cases") or [])
        ],
        "legal_subjects": [
            {"name": s.get("name", ""), "subject_type": s.get("subject_type", ""),
             "roles": [{k: r.get(k, "") for k in ["role_code", "role_name", "case_number"]}
                       for r in (s.get("roles") or [])]}
            for s in (output.get("legal_subjects") or [])
        ],
        "legal_provisions": [
            {k: p.get(k, "") for k in ["statute", "article", "paragraph", "item",
                                         "citation_position", "citation_purpose"]}
            for p in (output.get("legal_provisions") or [])[:5]
        ],
        "evidence": [
            {k: e.get(k, "") for k in ["content", "evidence_type", "submitted_by", "is_key_evidence",
                                       "admission_status", "examination_status",
                                       "expert_institution", "expert_conclusion"]}
            for e in (output.get("evidence") or [])[:3]
        ],
        "judgment_results": [
            {k: jr.get(k, "") for k in ["result_type", "specific_judgment", "reasoning",
                                          "cost_allocation"]}
            for jr in (output.get("judgment_results") or [])[:2]
        ],
        "case_summary": {
            k: (output.get("case_summary") or {}).get(k, "")
            for k in ["key_facts", "disputed_issues", "conclusion", "claim_amount", "judgment_amount"]
        },
        "legal_provision_elements": [
            {k: el.get(k, "") for k in ["statute", "article", "element_type", "provision_index"]}
            for el in (output.get("legal_provision_elements") or [])[:5]
        ],
        "facts": [
            {k: f.get(k, "") for k in ["id", "content", "fact_type", "case_number"]}
            for f in (output.get("facts") or [])[:4]
        ],
        "dispute_focuses": [
            {k: df.get(k, "") for k in ["id", "content", "focus_type", "case_number"]}
            for df in (output.get("dispute_focuses") or [])[:3]
        ],
        "relations": [
            {k: r.get(k, "") for k in ["source_id", "target_id", "relation_type", "description"]}
            for r in (output.get("relations") or [])[:6]
        ],
    }


def render_few_shot_block(row: dict, output: dict, meta: dict) -> str:
    """渲染一条 few-shot 示例"""
    text = build_fewshot_input_text(row)
    cleaned = clean_fewshot_output(output)
    output_json = json.dumps(cleaned, ensure_ascii=False, indent=2)

    cat_label = {"civil": "民事", "criminal": "刑事", "administrative": "行政"}.get(
        classify_case_type(row.get("case_type", "")), "其他")
    return f"""
## Few-shot 示例（{cat_label}案）

> 案由: {row.get('case_type', '')} | 入库编号: {row.get('storage_no', '')} | 来源: 历史最佳解析（score={meta.get('score', '?')}）

### 输入案件文本
```
{text[:3000]}
```

### 期望输出（示例，仅展示字段格式）
```json
{output_json}
```
"""


# ==================== 将 few-shot 注入 prompt ====================

def inject_few_shots(prompt: str, target_case_type: str = None,
                     data_lake_dir: str = None, raw_dir: str = None) -> str:
    """
    自动加载三案由的 few-shot，根据目标案由选择性地注入。
    
    策略：
    - 如果 target_case_type 不为空，只注入对应案由的 few-shot
    - 如果 target_case_type 为空，默认注入民事 few-shot（最大众化）
    """
    print("📚 加载案由分类 few-shot 样本...")
    best_shots = load_best_few_shots(data_lake_dir)

    if not best_shots:
        print("⚠️  无可用 few-shot 样本，跳过")
        return prompt

    # 确定注入哪个 few-shot
    target_cat = classify_case_type(target_case_type) if target_case_type else "civil"
    if target_cat not in best_shots:
        # fallback 到民事
        target_cat = "civil"
    if target_cat not in best_shots:
        # 真没样本
        print("⚠️  目标案由无样本，跳过")
        return prompt

    shot = best_shots[target_cat]
    row = load_raw_row(shot["row_id"], raw_dir)
    if not row:
        print("⚠️  原始 CSV 中未找到对应行，使用元数据")
        row = shot["input_meta"]

    few_shot_block = render_few_shot_block(row, shot["output"], shot)
    print(f"✅ 注入 {target_cat} few-shot（约 {len(few_shot_block)} 字符）")

    placeholder = "## 案件文本"
    if placeholder in prompt:
        prompt = prompt.replace(placeholder, few_shot_block + "\n\n" + placeholder)
    else:
        prompt += few_shot_block

    return prompt


def extract_prompt_json_block(prompt: str) -> Optional[str]:
    """提取 prompt 中第一个 json fenced block。"""
    m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", prompt)
    if not m:
        return None
    return m.group(1)


def validate_generated_prompt(prompt: str) -> tuple[bool, str]:
    """对生成的 prompt 做最小结构校验。"""
    json_block = extract_prompt_json_block(prompt)
    if not json_block:
        return False, "未找到 JSON fenced block"
    try:
        parsed = json.loads(json_block)
    except Exception as exc:
        return False, f"JSON 示例不可解析: {exc}"

    required_top_keys = {
        "guiding_case", "case_type", "court_cases", "legal_subjects",
        "legal_provisions", "evidence", "judgment_results", "case_summary",
        "legal_provision_elements", "facts", "dispute_focuses", "relations",
    }
    missing = sorted(required_top_keys - set(parsed.keys()))
    if missing:
        return False, f"JSON 示例缺少顶层字段: {', '.join(missing)}"
    return True, "ok"


# ==================== 主入口 ====================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="从本体自动生成结构化提取提示词")
    parser.add_argument("--ontology", default="ontology/schemas/legal_ontology_v2.yaml")
    parser.add_argument("--output", default=None)
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--few-shot", nargs="?", const=True, default=False,
                        help="注入案由匹配的 few-shot（可指定 data_lake 目录）")
    parser.add_argument("--case-type", default=None,
                        help="目标案件案由，用于匹配 few-shot（如 '刑事-开设赌场罪'）")
    parser.add_argument("--show-shots", action="store_true",
                        help="仅显示各案由的最佳 few-shot 信息，不生成 prompt")
    args = parser.parse_args()

    # 仅显示 few-shot 信息
    if args.show_shots:
        print(f"{'案由类别':<15} {'row_id':<8} {'quality':<8} {'score':<6} {'provisions':<10} {'cases':<6} {'subjects':<8} 案由")
        print("-"*80)
        shots = load_best_few_shots()
        for cat in CASE_CATEGORIES:
            if cat in shots:
                s = shots[cat]
                d = s["details"]
                print(f"{cat:<15} {s['row_id']:<8} {s['quality']:<8} {s['score']:<6} "
                      f"{d['provisions']:<10} {d['cases']:<6} {d['subjects']:<8} {s['case_type']}")
        return

    onto_path = REPO_ROOT / args.ontology
    if not onto_path.exists():
        print(f"错误: 本体文件未找到: {onto_path}")
        sys.exit(1)

    ontology = load_ontology(str(onto_path))

    if args.validate:
        enums = get_all_enum_tables(ontology)
        print(f"✅ 本体加载成功: 实体{len(ontology['entities'])} 关系{len(ontology['relations'])} 约束{len(ontology['constraints'])} 枚举{len(enums)}")
        return

    prompt = render_extraction_prompt(ontology)

    if args.case_type and not args.few_shot:
        print("ℹ️ --case-type 当前只用于 few-shot 样本匹配；未启用 --few-shot 时该参数会被忽略")

    if args.few_shot:
        dl_dir = str(args.few_shot) if isinstance(args.few_shot, str) else None
        data_lake_path = Path(dl_dir) if dl_dir else (REPO_ROOT / "data_lake")
        layer_counts = summarize_data_lake_layers(data_lake_path)
        print("ℹ️ data_lake 分层: " + ", ".join(f"{k}={v}" for k, v in sorted(layer_counts.items())))
        print(
            "ℹ️ few-shot 候选池当前使用 `"
            + STRUCTURED_CANDIDATE_LAYER
            + "_*` 与 `"
            + OFFICIAL_CANDIDATE_LAYER
            + "_*`；`fewshot_cmp_*` / `compare*` / `manual_*` 不参与候选"
        )
        prompt = inject_few_shots(prompt, target_case_type=args.case_type, data_lake_dir=dl_dir)

    ok, msg = validate_generated_prompt(prompt)
    if not ok:
        print(f"❌ Prompt 校验失败: {msg}")
        sys.exit(2)
    print("✅ Prompt JSON 示例校验通过")

    if args.output:
        output_path = REPO_ROOT / args.output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(prompt, encoding="utf-8")
        print(f"✅ 提示词已生成: {output_path}")
        print(f"   长度: {len(prompt)} 字符, {len(prompt.splitlines())} 行")

        if args.compare:
            v3_path = REPO_ROOT / "scripts/prompts/guiding_case_ontology_aligned_v3.txt"
            if v3_path.exists():
                v3c = v3_path.read_text(encoding="utf-8")
                print(f"\n📊 对比: 旧v3 {len(v3c)}字/{len(v3c.splitlines())}行 → 新 {len(prompt)}字/{len(prompt.splitlines())}行")
    else:
        print(prompt)


if __name__ == "__main__":
    main()
