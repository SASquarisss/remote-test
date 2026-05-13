"""
Legal text parser — simplified standalone version.
Reuses logic patterns from guiding_case_extractor_v3.py without importing it.
"""
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

import yaml

# ── Config ──────────────────────────────────────────────────────────────────

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PROMPT_PATH = os.path.join(REPO_ROOT, "scripts/prompts", "guiding_case_ontology_aligned_v3.txt")

# ── Prompt Loading ──────────────────────────────────────────────────────────

def load_prompt() -> str:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()

# ── Input Builder ───────────────────────────────────────────────────────────

def build_row_from_text(raw_text: str) -> Dict[str, str]:
    """
    Convert arbitrary user text into a dict that mimics a CSV row.
    Tries to extract known fields via pattern matching; the rest goes to basic_facts.
    """
    row: Dict[str, str] = {
        "id": "",
        "web_name": "",
        "web_url": "",
        "case_type": "",
        "storage_no": "",
        "court_name": "",
        "key_words": "",
        "trial_procedure": "",
        "trial_year": "",
        "case_level": "",
        "basic_facts": "",
        "judgment_reason": "",
        "judgment_essence": "",
        "related_info": "",
        "related_law": "",
        "related_judgment_body": "",
        "create_time": "",
        "update_time": "",
        "md5_value": "",
        "judgment_mean": "",
        "dt": "",
    }

    patterns = {
        "storage_no": r"(?:入库编号|案例库编号)[：:]\s*(\S+)",
        "web_name": r"(?:案例名称|案件名称)[：:]\s*(.+?)(?:\n|$)",
        "court_name": r"(?:审理法院|法院)[：:]\s*(.+?)(?:\n|$)",
        "trial_procedure": r"(?:审判程序|程序)[：:]\s*(.+?)(?:\n|$)",
        "trial_year": r"(?:裁判年份|年份)[：:]\s*(\d{4})",
        "case_type": r"(?:案由分类|案由)[：:]\s*(.+?)(?:\n|$)",
        "key_words": r"(?:关键词)[：:]\s*(.+?)(?:\n|$)",
        "case_level": r"(?:案例层级|层级)[：:]\s*(.+?)(?:\n|$)",
        "judgment_mean": r"(?:裁判意义|意义)[：:]\s*(.+?)(?:\n|$)",
    }

    # Try to extract structured fields
    for field, pat in patterns.items():
        m = re.search(pat, raw_text)
        if m:
            row[field] = m.group(1).strip()

    # Extract multi-line content sections
    section_patterns = {
        "basic_facts": r"(?:基本案情|基本事实)[：:]\s*([\s\S]*?)(?=\n(?:裁判理由|相关法条|裁判要旨|关键词))",
        "judgment_reason": r"(?:裁判理由)[：:]\s*([\s\S]*?)(?=\n(?:裁判要旨|基本案情|相关法条|关键词))",
        "judgment_essence": r"(?:裁判要旨)[：:]\s*([\s\S]*?)(?=\n(?:基本案情|裁判理由|相关法条|关键词))",
        "related_law": r"(?:相关法条)[：:]\s*([\s\S]*?)(?=\n(?:基本案情|裁判理由|裁判要旨|关键词))",
    }
    for field, pat in section_patterns.items():
        m = re.search(pat, raw_text)
        if m:
            row[field] = m.group(1).strip()

    # If no basic_facts extracted, use whole text
    if not row["basic_facts"] and not row["judgment_reason"]:
        row["basic_facts"] = raw_text.strip()

    # If no case_name, use first meaningful line
    if not row["web_name"]:
        first_line = raw_text.strip().split("\n")[0][:100]
        row["web_name"] = first_line

    return row


def build_llm_input(row: Dict[str, str]) -> str:
    """Build LLM input from a row dict, same logic as extractor_v3."""
    fields = [
        ("web_name", "案例来源"),
        ("web_url", "来源URL"),
        ("case_type", "案由分类"),
        ("storage_no", "入库编号"),
        ("court_name", "审理法院"),
        ("trial_procedure", "审判程序"),
        ("trial_year", "裁判年份"),
        ("case_level", "案例层级"),
        ("basic_facts", "基本案情"),
        ("judgment_reason", "裁判理由"),
        ("judgment_essence", "裁判要旨"),
        ("related_info", "相关案情/关联案件"),
        ("related_law", "相关法条"),
        ("related_judgment_body", "关联裁判文书"),
        ("key_words", "关键词"),
        ("judgment_mean", "裁判意义"),
    ]
    lines = []
    for key, label in fields:
        val = row.get(key, "") or ""
        val = re.sub(r"<[^>]+>", "", val)
        val = val.replace("\\N", "").strip()
        if val:
            lines.append(f"【{label}】\n{val}\n")
    return "\n".join(lines)


# ── Safe JSON parsing ──────────────────────────────────────────────────────

def _safe_json_parse(content: str) -> dict:
    """Tolerant JSON parser — tries to extract last complete JSON object if truncated."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        if start == -1:
            raise
        depth, end = 0, start
        for i in range(start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
            if depth == 0 and i > start:
                end = i + 1
                break
        if end > start:
            return json.loads(content[start:end])
        raise


# ── LLM Call ────────────────────────────────────────────────────────────────

def call_llm(prompt: str, text: str) -> Dict[str, Any]:
    """Single LLM call with retry. Uses deepseek-chat."""
    from openai import OpenAI

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not set")

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")

    last_error = None
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                max_tokens=4096,
                temperature=0.1,
                response_format={"type": "json_object"},
                timeout=180,
            )
            content = resp.choices[0].message.content or "{}"
            return _safe_json_parse(content)
        except Exception as e:
            last_error = e
            print(f"  [retry {attempt+1}] {e}", flush=True)
            time.sleep(2 ** attempt)

    raise RuntimeError(f"All 3 LLM attempts failed: {last_error}")


# ── Post-Processing ─────────────────────────────────────────────────────────

def enforce_case_level(row: Dict[str, str], output: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(output, dict):
        return output
    csv_cl = row.get("case_level", "").strip().replace("\\N", "").strip()
    cl_map = {"01": "guiding_case", "02": "typical_case"}
    bf_map = {"01": "mandatory", "02": "persuasive"}
    enforced_cl = cl_map.get(csv_cl, "reference_case")
    enforced_bf = bf_map.get(csv_cl, "reference")
    if "guiding_case" in output and isinstance(output["guiding_case"], dict):
        output["guiding_case"]["case_level"] = enforced_cl
        output["guiding_case"]["binding_force"] = enforced_bf
    return output


def enforce_source_url(row: Dict[str, str], output: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(output, dict):
        return output
    input_url = row.get("web_url", "").strip()
    if input_url and "guiding_case" in output and isinstance(output["guiding_case"], dict):
        GENERIC_URLS = {"https://rmfyalk.court.gov.cn", "https://rmfyalk.court.gov.cn/"}
        existing = output["guiding_case"].get("source_url", "").strip()
        if existing in GENERIC_URLS or not existing:
            output["guiding_case"]["source_url"] = input_url
    return output


def fill_empty_provision_content(output: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(output, dict):
        return output
    provisions = output.get("legal_provisions") or []
    for p in provisions:
        if not p.get("content", "").strip():
            statute = p.get("statute", "").strip()
            article = p.get("article", "").strip()
            if statute and article:
                p["content"] = f"《{statute}》第{article}条（提取自相关法条引用）"
            elif statute:
                p["content"] = f"《{statute}》（提取自相关法条引用）"
            else:
                p["content"] = "法条引用（提取自相关法条引用）"
    return output


def extract_case_name(output: Dict[str, Any]) -> str:
    """Extract a human-readable case name from LLM output."""
    gc = output.get("guiding_case") or {}
    name = gc.get("guiding_case_name", "")
    if name:
        return name
    court_cases = output.get("court_cases") or []
    if court_cases:
        return court_cases[0].get("case_number", "")
    return "未命名案例"


# ── KG Conversion ──────────────────────────────────────────────────────────

def kg_convert(output: Dict[str, Any]) -> Dict[str, List[Dict]]:
    """
    Convert LLM output JSON into vis-network nodes/edges.
    Reuses the same shape/color scheme as admin_instances.html.
    Entities are correctly associated to their court instance via case_number.
    Labels use Chinese.
    """
    # ── Chinese label mapping tables ──────────────────────────────────────
    CASE_TYPE_MAP = {
        "civil": "民事",
        "criminal": "刑事",
        "administrative": "行政",
    }
    BINDING_FORCE_MAP = {
        "reference": "参考案例",
        "mandatory": "指导性案例",
        "persuasive": "典型案例",
    }
    RESULT_TYPE_MAP = {
        "dismissed": "驳回",
        "upheld": "维持",
        "reversed": "撤销",
        "partially_upheld": "部分维持",
        "remanded": "发回重审",
        "accepted": "支持",
        "rejected": "驳回",
    }

    nodes: List[Dict] = []
    edges: List[Dict] = []
    node_set: set = set()
    edge_set: set = set()

    def add_node(nid: str, label: str, ntype: str, group: str, level: int = 1, title: str = ""):
        if nid in node_set:
            return
        node_set.add(nid)
        nodes.append({
            "id": nid,
            "label": label,
            "title": title,
            "shape": ADMIN_SHAPES.get(ntype, "ellipse"),
            "size": 35 if level == 0 else (26 if level == 1 else 20),
            "color": ROOT_COLORS.get(group, {"bg": "#7f8c8d", "border": "#5d6d7e"}),
            "font": {"color": "#fff", "size": 14 if level == 0 else 12},
            "borderWidth": 2,
            "group": group,
            "nodeType": ntype,
            "level": level,
        })

    def add_edge(fr: str, to: str, label: str):
        key = f"{fr}|{to}|{label}"
        if key in edge_set:
            return
        edge_set.add(key)
        edges.append({
            "from": fr, "to": to, "label": label,
            "color": {"color": "#7f8c8d", "highlight": "#333", "hover": "#333", "opacity": 0.7},
            "font": {"size": 10, "color": "#555", "strokeWidth": 2, "strokeColor": "#fff"},
            "width": 1.5, "smooth": {"type": "continuous"},
            "arrows": {"to": {"enabled": True, "scaleFactor": 0.6}},
        })

    # ── Build case_number → cc_id mapping ────────────────────────────────
    court_cases = output.get("court_cases") or []
    cn_to_cc = {}  # "(2024)沪73知民初164号" -> "cc_0"
    first_cc_id = None
    for i, cc in enumerate(court_cases):
        cn = cc.get("case_number", "")
        nid = f"cc_{i}"
        if first_cc_id is None:
            first_cc_id = nid
        if cn:
            cn_to_cc[cn] = nid

    # ── GuidingCase ──────────────────────────────────────────────────────
    gc = output.get("guiding_case") or {}
    if gc.get("guiding_case_name"):
        # Translate binding_force to Chinese
        bf_raw = gc.get("binding_force", "")
        bf_cn = BINDING_FORCE_MAP.get(bf_raw, bf_raw)
        add_node("gc", gc["guiding_case_name"], "GuidingCase", "LegalNorm", 0,
                 f"案号: {gc.get('guiding_case_number', '')}<br>效力: {bf_cn}")
        cn = gc.get("guiding_case_number", "")
        if cn:
            add_node("gc_num", cn, "GuidingCase", "LegalNorm", 1)
            add_edge("gc", "gc_num", "案号")

        # GuidingCase 关联边 — 如果有 trial_procedure="二审" 或无 case_number，关联到 cc_1
        gc_cn = gc.get("guiding_case_number", "")
        gc_trial = gc.get("trial_procedure", "")
        gc_target = first_cc_id  # default to first cc
        if not gc_cn or gc_trial == "二审":
            # 优先找二审案 (cc_1)
            for i, cc in enumerate(court_cases):
                if cc.get("trial_level") == "second_instance" or cc.get("trial_procedure") == "二审":
                    gc_target = f"cc_{i}"
                    break
            if not gc_cn:
                add_edge(gc_target, "gc", "关联")
            else:
                add_edge(gc_target, "gc", "关联")
        else:
            # 有 guiding_case_number，找匹配
            matched = cn_to_cc.get(gc_cn, first_cc_id)
            add_edge(matched, "gc", "关联")

    # ── CaseType ─────────────────────────────────────────────────────────
    ct = output.get("case_type") or {}
    ct_category_raw = ct.get("category", "")
    ct_category_cn = CASE_TYPE_MAP.get(ct_category_raw, ct_category_raw)
    if ct_category_raw:
        add_node("ct", ct_category_cn, "CaseType", "JudicialEntity", 0)
        for lv_key, lv_label in [("level1", "一级案由"), ("level2", "二级案由")]:
            val = ct.get(lv_key)
            if val:
                nid = f"ct_{lv_key}_{val}"
                add_node(nid, val, "CaseType", "JudicialEntity", 1)
                add_edge("ct", nid, lv_label)

    # ── CourtCases — 创建审级节点 ───────────────────────────────────────
    for i, cc in enumerate(court_cases):
        cn = cc.get("case_number", f"case_{i}")
        nid = f"cc_{i}"
        label = cn[:60]
        add_node(nid, label, "CourtCase", "JudicialEntity", 0,
                 f"案号: {cn}<br>立案日期: {cc.get('filing_date', '')}")
        # CaseType 关联到所有 court_cases
        if ct.get("category"):
            add_edge("ct", nid, "案由")

    # ── 审级间关联边 ────────────────────────────────────────────────────
    if len(court_cases) >= 2:
        # 按 trial_level 排序：一审在前，二审在后
        # 简单地按顺序连接：cc_0 → cc_1 → cc_2...
        for i in range(len(court_cases) - 1):
            fr = f"cc_{i}"
            to = f"cc_{i+1}"
            add_edge(fr, to, "上诉")

    # ── LegalSubjects — 按 role 中的 case_number 关联 ────────────────────
    subjects = output.get("legal_subjects") or output.get("parties") or []
    # First pass: create all subject nodes
    for i, subj in enumerate(subjects):
        name = subj.get("name", f"当事人_{i}")
        nid = f"subj_{i}"
        add_node(nid, name[:40], "LegalSubject", "LegalSubject", 0)

    # Second pass: create edges per role with correct cc
    for i, subj in enumerate(subjects):
        nid = f"subj_{i}"
        roles = subj.get("roles") or []
        if roles:
            for role in roles:
                case_num = role.get("case_number", "")
                role_name = role.get("role_name", "当事人")
                if case_num and case_num in cn_to_cc:
                    add_edge(cn_to_cc[case_num], nid, role_name)
                elif court_cases:
                    # fallback to first cc
                    add_edge(first_cc_id, nid, role_name)
        elif court_cases:
            # No roles at all — fallback
            add_edge(first_cc_id, nid, "当事人")

    # ── Judges — 按 case_number 关联 ────────────────────────────────────
    judges = output.get("judges") or []
    for i, j in enumerate(judges):
        name = j.get("name", f"法官_{i}")
        nid = f"judge_{i}"
        add_node(nid, name, "Judge", "LegalSubject", 1)
        case_num = j.get("case_number", "")
        if case_num and case_num in cn_to_cc:
            add_edge(cn_to_cc[case_num], nid, "审判")
        elif court_cases:
            add_edge(first_cc_id, nid, "审判")

    # ── Attorneys — 按 case_number 关联 ─────────────────────────────────
    attorneys = output.get("attorneys") or []
    for i, a in enumerate(attorneys):
        name = a.get("name", f"律师_{i}")
        nid = f"atty_{i}"
        add_node(nid, name, "Attorney", "LegalSubject", 1)
        case_num = a.get("case_number", "")
        if case_num and case_num in cn_to_cc:
            add_edge(cn_to_cc[case_num], nid, "代理")
        elif court_cases:
            add_edge(first_cc_id, nid, "代理")

    # ── LegalProvisions — 按 case_number 关联 ───────────────────────────
    provisions = output.get("legal_provisions") or []
    for i, p in enumerate(provisions):
        statute = p.get("statute", "法规")
        article = p.get("article", f"{i}")
        label = f"{statute}第{article}条"
        nid = f"prov_{i}"
        add_node(nid, label[:60], "LegalProvision", "LegalNorm", 1,
                 p.get("content", ""))
        case_num = p.get("case_number", "")
        if case_num and case_num in cn_to_cc:
            add_edge(cn_to_cc[case_num], nid, "引用")
        elif court_cases:
            add_edge(first_cc_id, nid, "引用")

    # ── Evidence — 按 case_number 或 submitted_by 关联 ──────────────────
    evids = output.get("evidence") or []
    for i, e in enumerate(evids):
        content = e.get("content", f"证据_{i}")
        label = content[:40]
        nid = f"evid_{i}"
        add_node(nid, label, "Evidence", "JudicialEntity", 1,
                 f"类型: {e.get('evidence_type', '')}<br>提交: {e.get('submitted_by', '')}<br>关键证据: {'是' if e.get('is_key_evidence') else '否'}<br>采信: {e.get('admission_status', '')}<br>理由: {e.get('admission_reason', '')[:40]}<br>证明力: {e.get('probative_force', '')}")
        case_num = e.get("case_number", "")
        if case_num and case_num in cn_to_cc:
            add_edge(cn_to_cc[case_num], nid, "证据")
        elif court_cases:
            # Try to find via submitted_by — look for a subject with that name
            submitted_by = e.get("submitted_by", "")
            if submitted_by and len(court_cases) > 1:
                # Find subject with matching name, get their first role's cc
                target_cc = None
                for subj in subjects:
                    if subj.get("name") == submitted_by:
                        roles = subj.get("roles") or []
                        # Get the first role's case_number
                        for role in roles:
                            rcn = role.get("case_number", "")
                            if rcn and rcn in cn_to_cc:
                                target_cc = cn_to_cc[rcn]
                                break
                        break
                if target_cc:
                    add_edge(target_cc, nid, "证据")
                else:
                    add_edge(first_cc_id, nid, "证据")
            else:
                add_edge(first_cc_id, nid, "证据")

    # ── JudgmentResults — 按 case_number 关联 ───────────────────────────
    jrs = output.get("judgment_results") or []
    for i, jr in enumerate(jrs):
        rtype_raw = jr.get("result_type", "裁判结果")
        rtype_cn = RESULT_TYPE_MAP.get(rtype_raw, rtype_raw)
        nid = f"jr_{i}"
        add_node(nid, rtype_cn, "JudgmentResult", "JudicialEntity", 0)
        case_num = jr.get("case_number", "")
        if case_num and case_num in cn_to_cc:
            add_edge(cn_to_cc[case_num], nid, "裁判")
        elif court_cases:
            add_edge(first_cc_id, nid, "裁判")

    # ── Facts ─────────────────────────────────────────────────────────────
    facts = output.get("facts") or []
    for i, f in enumerate(facts):
        fid = f.get("id", f"fact_{i}")
        label = f.get("content", "")[:40]
        add_node(fid, label, "Fact", "JudicialEntity", 1,
                 f"类型: {f.get('fact_type', '')}<br>案号: {f.get('case_number', '')}")
        case_num = f.get("case_number", "")
        if case_num and case_num in cn_to_cc:
            add_edge(cn_to_cc[case_num], fid, "事实")
        elif court_cases:
            add_edge(first_cc_id, fid, "事实")

    # ── DisputeFocuses ─────────────────────────────────────────────────────
    focuses = output.get("dispute_focuses") or []
    for i, df in enumerate(focuses):
        dfid = df.get("id", f"focus_{i}")
        label = df.get("content", "")[:40]
        add_node(dfid, label, "DisputeFocus", "JudicialEntity", 0,
                 f"类型: {df.get('focus_type', '')}<br>案号: {df.get('case_number', '')}")
        case_num = df.get("case_number", "")
        if case_num and case_num in cn_to_cc:
            add_edge(cn_to_cc[case_num], dfid, "争议焦点")
        elif court_cases:
            add_edge(first_cc_id, dfid, "争议焦点")

    # ── Relations — 显式关系边 ──────────────────────────────────────────
    rels = output.get("relations") or []
    for r in rels:
        src = r.get("source_id", "")
        tgt = r.get("target_id", "")
        rtype = r.get("relation_type", "")
        rlabel = r.get("label", rtype)
        if src and tgt:
            source_id = cn_to_cc.get(src, src)
            target_id = cn_to_cc.get(tgt, tgt)
            add_edge(str(source_id), str(target_id), rlabel)

    # ── CaseSummary — 如果有多个审级，优先关联到终审案 ──────────────────
    cs = output.get("case_summary") or {}
    if cs.get("disputed_issues"):
        issues = cs["disputed_issues"]
        if isinstance(issues, list):
            issues = "; ".join(issues)
        add_node("summary", issues[:60], "CaseSummary", "JudicialEntity", 1,
                 issues)
        if court_cases:
            if len(court_cases) == 1:
                add_edge(first_cc_id, "summary", "审理")
            else:
                # Multiple instances: try to find final (终审) instance
                summary_target = first_cc_id
                for i, cc in enumerate(court_cases):
                    tl = cc.get("trial_level", "")
                    if tl in ("second_instance", "retrial", "final"):
                        summary_target = f"cc_{i}"
                        break
                add_edge(summary_target, "summary", "审理")

    return {"nodes": nodes, "edges": edges}


# ── Ontology Colors (mirrors admin_instances.html constants) ────────────────

ROOT_COLORS = {
    "LegalNorm": {"bg": "#2980b9", "border": "#1a5276"},
    "JudicialEntity": {"bg": "#d35400", "border": "#a04000"},
    "LegalSubject": {"bg": "#27ae60", "border": "#1e8449"},
    "Person": {"bg": "#16a085", "border": "#0e6655"},
}

ADMIN_SHAPES = {
    "GuidingCase": "hexagon",
    "CourtCase": "box",
    "CaseType": "diamond",
    "LegalProvision": "hexagon",
    "LegalSubject": "ellipse",
    "Evidence": "database",  # 圆柱体，比 diamond 紧凑
    "Judge": "ellipse",
    "Attorney": "ellipse",
    "JudgmentResult": "box",
    "CaseSummary": "box",
    "Fact": "ellipse",
    "DisputeFocus": "star",
}


# ── Evaluation ──────────────────────────────────────────────────────────────

def evaluate_output(output: Dict[str, Any], row_id: str) -> Dict[str, Any]:
    """Lightweight evaluation — scores 0-100."""
    issues = []
    score = 100.0

    gc = output.get("guiding_case") or output
    for field in ["guiding_case_number", "guiding_case_name", "binding_force"]:
        val = gc.get(field) if isinstance(gc, dict) else output.get(field)
        if not val:
            issues.append(f"{field} 为空")
            score -= 5

    ct = output.get("case_type") or {}
    if not ct.get("category"):
        issues.append("case_type.category 为空")
        score -= 5

    court_cases = output.get("court_cases") or []
    if not court_cases:
        issues.append("court_cases 为空")
        score -= 35
    else:
        for i, cc in enumerate(court_cases):
            if not cc.get("case_number"):
                issues.append(f"court_cases[{i}].case_number 为空")
                score -= 10
            if not cc.get("filing_date"):
                issues.append(f"court_cases[{i}].filing_date 为空")
                score -= 5

    provisions = output.get("legal_provisions") or []
    if not provisions:
        issues.append("legal_provisions 为空")
        score -= 15
    else:
        for i, p in enumerate(provisions):
            if not p.get("article"):
                issues.append(f"legal_provisions[{i}].article 为空")
                score -= 5

    evidence = output.get("evidence") or []
    if not evidence:
        issues.append("evidence 为空")
        score -= 2
    else:
        for i, e in enumerate(evidence):
            if not e.get("admission_status"):
                issues.append(f"evidence[{i}].admission_status 为空")
                score -= 2

    facts = output.get("facts") or []
    if not facts:
        issues.append("facts 为空")
        score -= 5

    dispute_focuses = output.get("dispute_focuses") or []
    if not dispute_focuses:
        issues.append("dispute_focuses 为空")
        score -= 5

    judgment_results = output.get("judgment_results") or []
    if not judgment_results:
        issues.append("judgment_results 为空")
        score -= 3

    cs = output.get("case_summary") or {}
    if not cs.get("disputed_issues"):
        issues.append("case_summary.disputed_issues 为空")
        score -= 10

    return {
        "row_id": row_id,
        "score": max(0, score),
        "issues": issues,
    }


# ── Main Entry Point ───────────────────────────────────────────────────────

def parse_text(raw_text: str) -> Dict[str, Any]:
    """
    Full pipeline: text → row dict → LLM input → LLM → post-process → KG convert.
    Returns everything the frontend needs.
    """
    row = build_row_from_text(raw_text)
    prompt = load_prompt()
    llm_input = build_llm_input(row)

    print(f"  LLM input: {len(llm_input)} chars", flush=True)
    t0 = time.time()
    output = call_llm(prompt, llm_input)
    elapsed = time.time() - t0

    output = enforce_case_level(row, output)
    output = enforce_source_url(row, output)
    output = fill_empty_provision_content(output)

    case_name = extract_case_name(output)
    eval_result = evaluate_output(output, "manual")
    graph = kg_convert(output)

    print(f"  Done in {elapsed:.0f}s score={eval_result['score']:.0f}", flush=True)

    return {
        "row_id": f"manual_{int(time.time())}",
        "json_result": output,
        "nodes": graph["nodes"],
        "edges": graph["edges"],
        "score": eval_result["score"],
        "issues": eval_result["issues"],
        "case_name": case_name,
    }
