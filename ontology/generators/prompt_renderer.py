"""
prompt_renderer.py — 从本体自动生成结构化提取提示词。

核心功能：
1. render_enum_reference() — 枚举值参考表（markdown表格），让LLM直接查表而非自然语言推理
2. render_json_schema() — JSON输出Schema模板，自动从本体字段生成
3. render_entity_mapping_table() — 实体字段映射说明
4. render_extraction_prompt() — 组装完整提示词
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional

from ontology.generators.ontology_reader import (
    OntologySchema,
    get_all_enum_tables,
    get_entity_for_extraction,
    load_ontology,
)


# ========== 中文映射表：枚举值 → 中文说明 ==========
# 这些是手动维护但集中管理的映射，介于本体和提示词之间
# 优势：改一处即可同步所有枚举值的中文说明

ENUM_ZH_MAP: Dict[str, Dict[str, str]] = {
    # GuidingCase binding_force
    "GuidingCase.binding_force": {
        "mandatory": "强制参照（指导性案例）",
        "persuasive": "参考效力（典型案例）",
        "reference": "一般参考（其他案例）",
    },
    # CaseType category
    "CaseType.category": {
        "civil": "民事",
        "criminal": "刑事",
        "administrative": "行政",
        "ip": "知识产权",
        "execution": "执行",
        "state_compensation": "国家赔偿",
    },
    # CourtCase trial_level
    "CourtCase.trial_level": {
        "first_instance": "一审",
        "second_instance": "二审",
        "retrial": "再审",
    },
    # CourtCase status
    "CourtCase.status": {
        "filing": "立案中",
        "trial": "审理中",
        "judged": "已判决",
        "effective": "已生效",
        "appealed": "已上诉",
        "retried": "再审中",
        "executing": "执行中",
        "terminated": "已终结",
    },
    # CourtCase dispute_resolution_type
    "CourtCase.dispute_resolution_type": {
        "litigation": "诉讼",
        "mediation": "调解",
        "arbitration": "仲裁",
        "judicial_aid": "司法救助",
        "administrative_review": "行政复议",
    },
    # CaseParticipant / LegalRole role_code
    "CaseParticipant.role_code": {
        "plaintiff": "原告",
        "defendant": "被告",
        "third_party": "第三人",
        "witness": "证人",
        "agent": "诉讼代理人",
        "expert_witness": "鉴定人",
        "interpreter": "翻译人员",
        "prosecutor": "公诉人/检察机关",
        "applicant": "申请人",
        "respondent": "被申请人",
        "relator": "利害关系人",
        "appellant": "上诉人",
        "appellee": "被上诉人",
        "retrial_applicant": "再审申请人",
        "retrial_respondent": "再审被申请人",
        "mediator": "调解员",
        "arbitrator": "仲裁员",
        "beneficiary": "受益人/被救助人",
        "victim": "被害人",
        "criminal_defendant": "刑事被告人",
        "enforcement_applicant": "执行申请人",
        "enforcement_respondent": "执行被申请人",
        "judicial_review_applicant": "司法复核申请人",
        "insolvency_debtor": "破产债务人",
        "surety": "担保人",
        "class_representative": "诉讼代表人",
    },
    # Evidence types
    "Evidence.evidence_type": {
        "documentary": "书证",
        "physical": "物证",
        "audio_visual": "视听资料",
        "electronic_data": "电子数据",
        "witness_testimony": "证人证言",
        "party_statement": "当事人陈述",
        "expert_opinion": "鉴定意见",
        "inspection_record": "勘验笔录",
    },
    # JudgmentResult result_type
    "JudgmentResult.result_type": {
        "guilty": "有罪判决（刑事）",
        "not_guilty": "无罪判决（刑事）",
        "liable": "承担责任（民事）",
        "not_liable": "不承担责任（民事）",
        "dismissed": "驳回起诉/上诉",
        "withdrawn": "撤诉",
        "partially_upheld": "部分维持",
        "remanded": "发回重审",
        "punitive_damages": "惩罚性赔偿",
        "procedural_ruling": "程序性裁定",
        "bankruptcy_declared": "宣告破产",
        "mediation_agreement": "调解书",
        "arbitration_award": "仲裁裁决",
        "administrative_decision": "行政决定",
    },
    # Organization org_type
    "Organization.org_type": {
        "company": "企业",
        "government_agency": "政府机关/事业单位",
        "ngo": "非政府组织",
        "law_firm": "律师事务所",
        "expert_institution": "鉴定机构",
        "court": "法院",
        "procuratorate": "检察院",
        "individual_business": "个体工商户",
        "partnership": "合伙企业",
        "sole_proprietorship": "个人独资企业",
    },
    # Court court_level
    "Court.court_level": {
        "supreme": "最高人民法院",
        "high": "高级人民法院",
        "intermediate": "中级人民法院",
        "basic": "基层人民法院",
        "special": "专门法院",
    },
    # Evidence examination/admission status
    "Evidence.examination_status": {
        "not_examined": "未经质证",
        "examined": "已质证",
    },
    "Evidence.admission_status": {
        "admitted": "已采信",
        "not_admitted": "未采信",
    },
    # TrialOrganization
    "TrialOrganization.organization_type": {
        "sole_judge": "独任审判",
        "collegiate_bench": "合议庭",
        "judicial_committee": "审判委员会",
    },
    # Fact
    "Fact.fact_type": {
        "undisputed": "无争议事实",
        "disputed": "有争议事实",
        "to_be_proven": "待证事实",
    },
    # Law
    "Law.law_level": {
        "constitution": "宪法",
        "basic_law": "基本法律",
        "ordinary_law": "普通法律",
        "administrative_regulation": "行政法规",
        "local_regulation": "地方性法规",
        "self_governing_regulation": "自治条例",
        "military_regulation": "军事法规",
        "judicial_interpretation": "司法解释",
        "department_rule": "部门规章",
        "normative_document": "规范性文件",
    },
    "Law.status": {
        "effective": "现行有效",
        "amended": "已被修改",
        "repealed": "已被废止",
    },
    # LegalProvision / LegalProvisionVersion status (same values)
    "LegalProvision.status": {
        "effective": "现行有效",
        "amended": "已被修改",
        "repealed": "已被废止",
    },
    # SentencingStandard
    "SentencingStandard.standard_type": {
        "criminal_sentence": "刑事量刑",
        "civil_compensation": "民事赔偿",
        "administrative_penalty": "行政处罚",
    },
    "SentencingStandard.sentence_unit": {
        "month": "月",
        "year": "年",
        "yuan": "元",
        "percent": "百分比",
    },
    # LegalDocument
    "LegalDocument.document_type": {
        "judgment": "判决书",
        "ruling": "裁定书",
        "mediation": "调解书",
        "order": "决定书",
        "notice": "通知书",
        "indictment": "起诉书",
        "petition": "申请书",
    },
    # ExecutionInfo
    "ExecutionInfo.execution_status": {
        "pending": "待执行",
        "in_progress": "执行中",
        "completed": "执行完毕",
        "terminated": "终结执行",
    },
    # LawFirm
    "LawFirm.firm_type": {
        "partnership": "合伙制",
        "limited_liability": "有限责任公司制",
        "sole_practitioner": "个人所",
    },
    # Procuratorate
    "Procuratorate.procuratorate_level": {
        "supreme": "最高人民检察院",
        "provincial": "省级检察院",
        "municipal": "市/分院",
        "district": "区县级检察院",
    },
}


def _get_enum_zh(enum_path: str, value: str) -> str:
    """获取枚举值的中文说明"""
    mapping = ENUM_ZH_MAP.get(enum_path, {})
    return mapping.get(value, value)


def render_enum_reference(ontology: OntologySchema) -> str:
    """渲染枚举值参考表（字段路径 | 允许值 | 中文说明）"""
    enums = get_all_enum_tables(ontology)

    # 只保留提取管线关心的枚举
    extraction_enums = {
        k: v for k, v in enums.items()
        if any(k.startswith(prefix) for prefix in [
            "GuidingCase.", "CaseType.", "CourtCase.", "CaseParticipant.",
            "LegalRole.", "Evidence.", "JudgmentResult.", "LegalProvision.",
            "Court.", "TrialOrganization.", "Fact.", "CaseSummary.",
        ])
    }

    lines = ["## 枚举值约束（自动生成 - 必须严格遵守）",
             "以下枚举值用于本体的全部字段。**所有输出值必须严格匹配下表，不得自创值或使用中文作为输出。**",
             "",
             "| 字段路径 | 允许值 | 中文说明 |",
             "|---|---|---|"]

    for path, info in sorted(extraction_enums.items()):
        values = info["values"]
        # 检查是否有中文映射
        if path in ENUM_ZH_MAP:
            zh_parts = []
            for v in values:
                zh = _get_enum_zh(path, v)
                zh_parts.append(f"`{v}` → {zh}")
            zh_str = "; ".join(zh_parts)
        else:
            zh_str = ", ".join(f"`{v}`" for v in values)

        # 缩写长路径
        short_path = path
        lines.append(f"| `{short_path}` | {', '.join(f'`{v}`' for v in values)} | {zh_str} |")

    lines.append("")
    return "\n".join(lines)


# ========== 提取管线关心的实体及其字段映射 ==========

EXTRACTION_ENTITY_CONFIG = [
    {
        "name": "GuidingCase",
        "display_name": "指导性案例/典型案例",
        "fields": [
            ("guiding_case_number", "指导案例编号", "如'指导案例XX号'，从storage_no或文本推断; 如无则留空"),
            ("guiding_case_name", "案例名称", "必须填写，从web_name或当事人信息拼接生成"),
            ("publication_date", "发布日期", "格式YYYY-MM-DD，从trial_year字段推断"),
            ("binding_force", "约束力", "指导性案例→mandatory，典型案例→persuasive，其他→reference"),
            ("guiding_points", "裁判要旨/指导要点", "从judgment_essence提取"),
            ("key_words", "关键词列表", "字符串数组，从key_words字段提取（逗号分隔）"),
            ("case_level", "案例层级", "由输入字段【案例层级】直接映射：01→guiding_case，02→typical_case，其他→reference_case"),
            ("trial_procedure", "审判程序", "一审/二审/再审/执行等"),
            ("storage_no", "案例库内部编号", "直接使用输入字段【案例库编号】"),
            ("source_url", "来源URL", "直接使用输入字段【来源URL】，原样传递"),
            ("judgment_mean", "裁判意义", "直接使用输入字段【裁判意义】"),
        ],
    },
    {
        "name": "CaseType",
        "display_name": "案件类型",
        "fields": [
            ("category", "大类", "见枚举值表映射"),
            ("level1", "一级案由", "case_type中'-'前的部分"),
            ("level2", "二级案由", "case_type中'-'后的部分"),
        ],
    },
    {
        "name": "CourtCase",
        "display_name": "法院案件",
        "fields": [
            ("case_number", "案号", "格式：(YYYY)地区简称+案由+第N号。**从basic_facts/related_info/related_judgment_body全面提取**"),
            ("filing_date", "立案日期", "**必填**，格式YYYY-MM-DD。从案号年份或文本中'受理'/'立案'关键词推断"),
            ("judgment_date", "判决日期", "格式YYYY-MM-DD"),
            ("trial_level", "案件审级", "一审→first_instance，二审→second_instance，再审→retrial"),
            ("trial_procedure", "审判程序", "中文名称，如'一审'、'二审'、'再审'"),
            ("court", "法院信息", "含name（法院完整名称）和court_level（法院层级，见枚举值表）"),
            ("status", "案件状态", "已判决且生效→effective，刚判决→judged，见枚举值表"),
        ],
    },
    {
        "name": "LegalSubject",
        "display_name": "法律主体 + 法律角色",
        "fields": [
            ("name", "当事人名称", ""),
            ("subject_type", "主体类型", "自然人→natural_person，企业/机关/组织→organization"),
            ("org_type", "组织类型", "仅subject_type=organization时填写，见枚举值表"),
            ("credit_code", "统一社会信用代码", "如有则填写，通常企业才有"),
            ("roles", "角色列表", "每个角色含role_code（枚举值）、role_name（中文原词）、case_number（关联案号）"),
        ],
    },
    {
        "name": "LegalProvision",
        "display_name": "法律条文引用",
        "fields": [
            ("case_number", "关联案号", "**必填**，该法条被哪个案号的案件引用"),
            ("statute", "法典名称", "去掉书名号，保留核心名称，如'刑法'、'民法典'"),
            ("article", "条号", "**必填**，纯数字。第30条→30，第二百六十六条→266，第二十条之一→236之一"),
            ("paragraph", "款号", "第1款→1，如未明确提及则留空"),
            ("item", "项号", "第(一)项→1，如未明确提及则留空"),
            ("content", "法条原文片段", "**必填**，从文本中找到该法条被引用上下文，提取50-100字"),
            ("citation_position", "引用位置", "basic_facts/judgment_reason/judgment_essence/related_info/related_law"),
            ("citation_purpose", "引用目的", "适用依据/说理依据/反驳依据"),
        ],
    },
    {
        "name": "Evidence",
        "display_name": "关键证据",
        "fields": [
            ("content", "证据内容摘要", ""),
            ("evidence_type", "证据类型", "见枚举值表，documentary/physical/audio_visual等"),
            ("submitted_by", "提交方名称", ""),
            ("is_key_evidence", "是否关键定案证据", "true/false"),
        ],
    },
    {
        "name": "JudgmentResult",
        "display_name": "判决结果/裁判主文",
        "fields": [
            ("result_type", "结果类型", "见枚举值表。刑事：guilty/not_guilty/remanded；民事：liable/dismissed/withdrawn等"),
            ("specific_judgment", "具体判决内容", "如刑期、赔偿金额等"),
            ("case_number", "关联案号", ""),
        ],
    },
    {
        "name": "CaseSummary",
        "display_name": "案件结构化摘要",
        "fields": [
            ("key_facts", "关键事实", "200字以内，客观陈述，不含法院观点"),
            ("disputed_issues", "争议焦点", "**必填**，100字以内，从judgment_reason提炼"),
            ("conclusion", "裁判结论", "**必填**，100字以内，概述法院最终裁判结果"),
            ("amount_involved", "标的金额", "如有则填写，如'335049元'"),
            ("guiding_points", "指导要点", "仅指导性案例填写"),
        ],
    },
    {
        "name": "Judge",
        "display_name": "法官/审判人员",
        "fields": [
            ("name", "法官姓名", ""),
            ("role", "角色", "审判长→presiding_judge，审判员→judge，代理审判员→acting_judge，人民陪审员→people_juror，书记员→clerk"),
            ("case_number", "关联案号", ""),
        ],
    },
    {
        "name": "Attorney",
        "display_name": "律师/诉讼代理人",
        "fields": [
            ("name", "律师或代理人姓名", ""),
            ("law_firm", "所属律所", "如是律师则填写"),
            ("representation_for", "代理哪方当事人", "如'原告'、'被告'、'再审申请人'"),
            ("case_number", "关联案号", ""),
        ],
    },
    {
        "name": "ProsecutorInfo",
        "display_name": "出庭检察人员",
        "fields": [
            ("name", "检察人员姓名", ""),
            ("role", "角色", "public_prosecutor(公诉人)/procurator(检察员)/protest_organ(抗诉机关)"),
            ("unit", "所属检察院", ""),
            ("case_number", "关联案号", ""),
        ],
    },
    {
        "name": "TrialOrganization",
        "display_name": "合议庭组成",
        "fields": [
            ("case_number", "关联案号", ""),
            ("members", "合议庭成员列表", "含审判长、审判员、人民陪审员等"),
            ("summary", "合议庭组成描述原文", ""),
        ],
    },
]


def render_entity_mapping_table(ontology: OntologySchema) -> str:
    """渲染实体字段映射表（markdown表格）"""
    lines = ["## 本体论实体映射（自动生成）"]
    lines.append("")

    for config in EXTRACTION_ENTITY_CONFIG:
        name = config["name"]
        display_name = config["display_name"]
        fields = config["fields"]

        lines.append(f"### {i+1 if False else ''}{display_name}（`{name}`）")
        lines.append("")
        lines.append("| 字段 | 说明 |")
        lines.append("|---|---|")
        for fname, fdesc, fnote in fields:
            # 检查是否有枚举约束
            enum_info = ""
            if name == "GuidingCase" and fname == "binding_force":
                enum_info = " [枚举值见参考表]"
            elif fname.endswith("_type") or fname in ("category", "trial_level", "role_code",
                                                       "evidence_type", "result_type", "status",
                                                       "court_level", "binding_force",
                                                       "dispute_resolution_type"):
                enum_info = " [枚举值见参考表]"
            note = fnote or ""
            lines.append(f"| `{fname}` | {note}{enum_info} |")
        lines.append("")

    return "\n".join(lines)


def render_json_schema(ontology: OntologySchema) -> str:
    """渲染 JSON Schema 输出模板（包含枚举约束）"""
    enums = get_all_enum_tables(ontology)
    P = chr(124)  # pipe character for f-strings

    lines = ["## 输出 JSON Schema（自动生成 — 严格遵循此结构）",
             "",
             "```json",
             "{"]

    # GuidingCase
    lines.append('  "guiding_case": {')
    for f in ["guiding_case_number", "guiding_case_name", "publication_date"]:
        lines.append(f'    "{f}": "",')
    e = enums.get("GuidingCase.binding_force", {}).get("values", ["mandatory", "persuasive", "reference"])
    lines.append(f'    "binding_force": "{P.join(e)}",')
    lines.append(f'    "guiding_points": "",')
    lines.append(f'    "key_words": [],')
    lines.append(f'    "case_level": "guiding_case{P}typical_case{P}reference_case",')
    for f in ["trial_procedure", "storage_no", "source_url"]:
        lines.append(f'    "{f}": "",')
    lines.append(f'    "judgment_mean": ""')
    lines.append('  },')

    # CaseType
    lines.append('  "case_type": {')
    e_cat = enums.get("CaseType.category", {}).get("values", ["civil", "criminal"])
    lines.append(f'    "category": "{P.join(e_cat)}",')
    lines.append(f'    "level1": "",')
    lines.append(f'    "level2": ""')
    lines.append('  },')

    # court_cases
    lines.append('  "court_cases": [')
    lines.append('    {')
    for f in ["case_number", "filing_date", "judgment_date"]:
        lines.append(f'      "{f}": "",')
    e_tl = enums.get("CourtCase.trial_level", {}).get("values", ["first_instance", "second_instance", "retrial"])
    lines.append(f'      "trial_level": "{P.join(e_tl)}",')
    lines.append(f'      "trial_procedure": "",')
    lines.append('      "court": {')
    lines.append(f'        "name": "",')
    e_clvl = enums.get("Court.court_level", {}).get("values", ["supreme", "high", "intermediate", "basic", "special"])
    lines.append(f'        "court_level": "{P.join(e_clvl)}"')
    lines.append('      },')
    e_st = enums.get("CourtCase.status", {}).get("values", ["effective", "judged"])
    lines.append(f'      "status": "{P.join(e_st)}"')
    lines.append('    }')
    lines.append('  ],')

    # legal_subjects
    lines.append('  "legal_subjects": [')
    lines.append('    {')
    lines.append(f'      "name": "",')
    lines.append(f'      "subject_type": "natural_person{P}organization",')
    e_org = enums.get("Organization.org_type", {}).get("values", ["company", "government_agency"])
    lines.append(f'      "org_type": "{P.join(e_org)}",')
    lines.append(f'      "credit_code": null,')
    lines.append('      "roles": [')
    lines.append('        {')
    e_role = enums.get("CaseParticipant.role_code", {}).get("values", ["plaintiff", "defendant"])
    lines.append(f'          "role_code": "{P.join(e_role)}",')
    lines.append(f'          "role_name": "",')
    lines.append(f'          "case_number": ""')
    lines.append('        }')
    lines.append('      ]')
    lines.append('    }')
    lines.append('  ],')

    for arr_name, arr_fields in [
        ("attorneys", [("name", '""'), ("law_firm", '""'), ("representation_for", '""'), ("case_number", '""')]),
        ("judges", [("name", '""'), ("role", '"presiding_judge|judge|acting_judge|people_juror|clerk"'), ("case_number", '""')]),
        ("prosecutors", [("name", '""'), ("role", '"public_prosecutor|procurator|protest_organ"'), ("unit", '""'), ("case_number", '""')]),
        ("trial_organizations", [("case_number", '""'), ("members", "[]"), ("summary", '""')]),
    ]:
        lines.append(f'  "{arr_name}": [')
        lines.append('    {')
        for fname, default in arr_fields:
            lines.append(f'      "{fname}": {default},')
        lines[-1] = lines[-1].rstrip(",")
        lines.append('    }')
        lines.append('  ],')

    # legal_provisions
    lines.append('  "legal_provisions": [')
    lines.append('    {')
    for f in ["case_number", "statute", "article", "paragraph", "item", "content"]:
        lines.append(f'      "{f}": "",')
    lines.append(f'      "citation_position": "basic_facts{P}judgment_reason{P}judgment_essence{P}related_info{P}related_law",')
    lines.append(f'      "citation_purpose": "适用依据{P}说理依据{P}反驳依据"')
    lines.append('    }')
    lines.append('  ],')

    # evidence
    lines.append('  "evidence": [')
    lines.append('    {')
    lines.append(f'      "content": "",')
    e_ev = enums.get("Evidence.evidence_type", {}).get("values",
        ["documentary", "physical", "audio_visual", "electronic_data",
         "witness_testimony", "party_statement", "expert_opinion", "inspection_record"])
    lines.append(f'      "evidence_type": "{P.join(e_ev)}",')
    lines.append(f'      "submitted_by": "",')
    lines.append(f'      "is_key_evidence": true')
    lines.append('    }')
    lines.append('  ],')

    # judgment_results
    lines.append('  "judgment_results": [')
    lines.append('    {')
    e_jr = enums.get("JudgmentResult.result_type", {}).get("values",
        ["guilty", "not_guilty", "liable", "not_liable", "dismissed",
         "withdrawn", "partially_upheld", "remanded", "punitive_damages",
         "procedural_ruling", "bankruptcy_declared"])
    lines.append(f'      "result_type": "{P.join(e_jr)}",')
    lines.append(f'      "specific_judgment": "",')
    lines.append(f'      "case_number": ""')
    lines.append('    }')
    lines.append('  ],')

    # case_summary
    lines.append('  "case_summary": {')
    for f in ["key_facts", "disputed_issues", "conclusion", "amount_involved", "guiding_points"]:
        lines.append(f'    "{f}": "",')
    lines[-1] = lines[-1].rstrip(",")
    lines.append('  }')

    lines.append("}")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


# ========== 静态头部模板（任务描述） ==========

HEADER_TEMPLATE = """你是一个专业的法律文本解析工具。你的任务是从人民法院案例库的案件文本中提取结构化信息，输出必须与法律本体论结构高度对齐。

## 核心原则
1. 严格输出JSON，不要任何额外解释
2. 使用本体论定义的枚举值，不要自创
3. 尽量从文本中提取完整信息，不要遗漏
4. 案件摘要必须结构化：关键事实、争议焦点、裁判结论
5. 法条引用必须标注引用位置和引用目的
6. 当事人角色必须映射到标准枚举值
7. **所有缺失字段必须尽力从其他文本源推断，不能留空**
8. 从related_info / related_judgment_body中提取所有审判组织的成员信息

## 强制提取要点
- **法条提取（LegalProvision）必须从以下源头全面提取**：judgment_reason、basic_facts、judgment_essence、related_law中的每一个法条引用都要提取。即使是司法解释、行政规章等，只要被引用就必须提取。**平均每个案例应提取 3-10 条法条，如果只提取到 0-1 条说明有遗漏，请重新检查文本。**
- **案号提取**：一个指导性案例往往包含多个审级，你必须从 basic_facts、related_info、related_judgment_body 中找出所有案号，为每个案号生成一个 court_case。**注意多个审级的案号不同**。
- **filing_date必须填写**：从案号年份、文本中"受理"、"立案"等关键词推断。实在无法推断则使用案号年份的第一天（如案号(2020)xxx则filing_date为"2020-01-01"）。
- **角色映射**：每个 party 的 role_code 和 role_name 都必须有值。遇到非标准角色，使用"other"+原文名称。
- **法条article必须为纯数字**：如"第30条"→"30"，"第二百六十六条"→"266"，"第二十条之一"→"236之一"。
"""


def render_extraction_prompt(
    ontology: OntologySchema,
    output_format: str = "markdown",
) -> str:
    """从本体自动生成完整提取提示词"""
    parts = [
        HEADER_TEMPLATE.strip(),
        "",
        render_enum_reference(ontology),
        "",
        render_entity_mapping_table(ontology),
        "",
        render_json_schema(ontology),
        "",
        "## 案件文本",
        "{case_text}",
        "",
        "## JSON输出",
    ]
    return "\n".join(parts)


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="从本体生成结构化提取提示词")
    parser.add_argument("--ontology", default="ontology/schemas/legal_ontology_v2.yaml",
                        help="本体YAML路径")
    parser.add_argument("--output", default=None,
                        help="输出文件路径（默认stdout）")
    parser.add_argument("--output-format", choices=["markdown"], default="markdown",
                        help="输出格式")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    onto_path = repo_root / args.ontology
    ontology = load_ontology(str(onto_path))
    prompt = render_extraction_prompt(ontology, args.output_format)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(prompt, encoding="utf-8")
        print(f"提示词已生成: {output_path}")
        print(f"长度: {len(prompt)} 字符, {len(prompt.splitlines())} 行")
    else:
        print(prompt)


if __name__ == "__main__":
    main()
