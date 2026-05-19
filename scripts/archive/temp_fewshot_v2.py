def build_mlm_input(row: dict) -> str:
    """构造浓缩版案件文本（仅保留关键信息用于 few-shot 展示，非完整输入）"""
    # 只取少量关键字段 + 截断
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


def render_few_shot_block(row: dict, output: dict) -> str:
    """将一条样本渲染为精简版 few-shot 示例块"""
    text = build_mlm_input(row)
    
    # 输出精简：只保留核心字段
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
            for p in (output.get("legal_provisions") or [])[:5]  # 最多5条法条
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
        f"> 案由: {row.get('case_type', '')} | 入库编号: {row.get('storage_no', '')} | 来源: 历史最佳解析结果（score={best['score'] if 'best' in dir() else '?'}）",
        "",
        "### 输入案件文本",
        "```",
        text[:3000],
        "```",
        "",
        "### 期望输出",
        "```json",
        output_json,
        "```",
        "",
    ]
    return "\n".join(lines)
