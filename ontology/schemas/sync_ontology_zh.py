#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本体论 YAML 中英文同步脚本
用法: python sync_ontology_zh.py
功能: 读取 legal_ontology_v2.yaml，生成 legal_ontology_v2.zh.yaml
注意: 修改本体论后，请运行此脚本同步中文版本
"""

import re
import sys
from pathlib import Path

# ============== 翻译字典 ==============
TRANS = {
    "LegalNorm": "法律规范（顶层父类）",
    "JudicialEntity": "司法实体（顶层父类）",
    "LegalSubject": "法律主体（顶层父类）",
    "Law": "法律（法典）",
    "LegalProvision": "法律条文（当前生效版本）",
    "LegalProvisionVersion": "法律条文历史版本",
    "CaseType": "案由类型",
    "GuidingCase": "指导性案例",
    "SentencingStandard": "量刑/赔偿标准",
    "Person": "自然人",
    "Judge": "法官",
    "Attorney": "律师",
    "Clerk": "书记员",
    "Prosecutor": "检察官",
    "Organization": "组织机构",
    "Court": "法院",
    "Procuratorate": "检察院",
    "LawFirm": "律师事务所",
    "ExpertInstitution": "鉴定机构",
    "District": "辖区",
    "LegalRole": "法律角色",
    "CourtCase": "法院案件",
    "CaseSummary": "案件摘要",
    "TrialOrganization": "审判组织",
    "JudgmentResult": "裁判结果",
    "ExecutionInfo": "执行信息",
    "LegalDocument": "法律文书",
    "Evidence": "证据",
    "DisputeFocus": "争议焦点",
    "Fact": "案件事实",
    "LitigationClaim": "诉求/请求",
    "ProceduralOpinion": "意见表达",
    "ArgumentPoint": "理由点",
    "JudicialAssessment": "法院评判",
    "CaseParticipant": "案件参与人",
    "belongs_to": "归属于",
    "has_version": "具有版本",
    "superseded_by": "被替代",
    "guides_case_type": "指导案由",
    "cites_guiding_case": "引用指导性案例",
    "applies_standard": "适用标准",
    "has_summary": "具有摘要",
    "tried_by": "由...审理",
    "presides_over": "主持",
    "undertakes": "承办",
    "plays_role": "担任角色",
    "has_jurisdiction_over": "管辖",
    "prosecutes": "公诉",
    "based_on": "基于",
    "signed_by": "由...签署",
    "has_case_type": "具有案由",
    "cites": "引用",
    "judgment_cites": "裁判依据",
    "represents": "代理",
    "employs": "雇佣",
    "employs_attorney": "雇佣律师",
    "submitted_for": "提交给",
    "proves_fact": "证明事实",
    "includes": "包含",
    "includes_clerk": "配备书记员",
    "appeals_to": "上诉至",
    "retries_from": "再审源自",
    "has_dispute_focus": "具有争议焦点",
    "has_fact": "具有事实",
    "participates_in_case": "参与案件",
    "raises_claim": "提出诉求",
    "expresses_opinion": "表达意见",
    "supports_claim": "支撑诉求",
    "supports_opinion": "支撑意见",
    "targets_subject": "指向主体",
    "claims_focus": "诉求对应焦点",
    "opines_on_focus": "意见围绕焦点",
    "assesses_focus": "评判焦点",
    "responds_to_claim": "回应诉求",
    "responds_to_opinion": "回应意见",
    "evaluates_argument": "评价理由",
    "based_on_fact": "基于事实",
    "based_on_provision": "基于法条",
    "supports_result": "支撑裁判结果",
    "concerns_focus": "关联争点",
    "relates_to_fact": "关联事实",
    "receives_judgment": "对应裁判",
    "matches_element": "匹配法条要件",
    "resolved_by": "由法条解决",
    "leads_to": "导向裁判",
    "LegalProvisionElement": "法条构成要件",
    "typically_applies": "典型适用（案由-法条映射）",
    "id": "唯一标识", "name": "名称", "source": "来源",
    "desensitize": "脱敏标记", "create_time": "创建时间", "update_time": "更新时间",
    "law_level": "法律位阶", "document_number": "文号", "status": "状态",
    "enactment_date": "颁布日期", "effective_date": "生效日期",
    "legislative_purpose": "立法目的", "repealed_date": "废止日期",
    "article": "条号", "paragraph": "款号", "item": "项号",
    "content": "内容", "related_provisions": "关联条文",
    "provision_id": "条文标识", "version_date": "版本日期",
    "superseded_by_version_id": "被替代版本标识", "amendment_reason": "修正原因",
    "code": "编码", "category": "大类", "level1": "一级分类", "level2": "二级分类",
    "description": "描述", "typical_provision_ids": "典型适用条文",
    "guiding_case_number": "指导案例编号", "issuing_court_id": "发布法院标识",
    "publication_date": "发布日期", "guiding_points": "指导要点",
    "binding_force": "约束力", "guiding_points_vector": "指导要点向量",
    "related_case_type_ids": "关联案由", "case_type_id": "案由标识",
    "applicable_provision_id": "适用条文标识", "standard_type": "标准类型",
    "sentence_range_min": "量刑下限", "sentence_range_max": "量刑上限", "sentence_unit": "量刑单位",
    "circumstance_levels": "情节等级", "measurement_formula": "计算公式",
    "region_id": "地区标识", "valid_from": "有效期起", "valid_to": "有效期止",
    "court_id": "法院标识", "position": "职位", "judge_level": "法官等级",
    "appointment_date": "任命日期", "license_number": "执业证号",
    "law_firm_id": "律所标识", "specialization": "专业领域", "bar_association": "律协",
    "procuratorate_id": "检察院标识", "org_type": "机构类型",
    "credit_code": "统一社会信用代码", "legal_representative": "法定代表人",
    "registered_capital": "注册资本", "business_scope": "经营范围",
    "legal_name_alias": "曾用名/别名", "court_level": "法院级别",
    "district_id": "辖区标识", "chambers": "审判庭", "jurisdiction_area": "管辖区域",
    "procuratorate_level": "检察院级别", "departments": "内设部门",
    "firm_type": "律所类型", "partners": "合伙人", "practice_areas": "执业领域",
    "expertise_fields": "专业领域", "accreditation_number": "资质编号",
    "accreditation_authority": "资质认定机关", "validity_period": "有效期",
    "administrative_level": "行政级别", "parent_district_id": "上级辖区标识",
    "role_code": "角色编码", "permissions": "权限",
    "case_number": "案号", "filing_date": "立案日期", "claim_amount": "诉讼标的额",
    "cause_of_action": "案由/诉讼请求", "summary": "摘要", "related_cases": "关联案件",
    "first_instance_case_number": "一审案号", "source_text_hash": "原文哈希",
    "source_text_path": "原文路径", "dispute_resolution_type": "纠纷解决方式",
    "key_facts": "关键事实", "disputed_issues": "争议焦点", "conclusion": "结论",
    "fact_vector": "事实向量", "issue_tags": "争议标签", "amount_involved": "涉案金额",
    "sentencing_referral_id": "量刑参照标识", "organization_type": "组织类型",
    "judge_ids": "法官标识列表", "presiding_judge_id": "审判长标识",
    "clerk_id": "书记员标识", "result_type": "结果类型",
    "judgment_date": "裁判日期", "sentence_term": "刑期",
    "compensation_amount": "赔偿金额", "reasoning": "裁判理由",
    "sentencing_standard_id": "量刑标准标识", "execution_status": "执行状态",
    "execution_court_id": "执行法院标识", "execution_amount": "执行标的额",
    "execution_measures": "执行措施", "completion_date": "完成日期",
    "document_type": "文书类型", "creation_date": "制作日期",
    "signed_by_judge_id": "签署法官标识", "content_hash": "内容哈希",
    "file_path": "文件路径", "evidence_type": "证据类型",
    "submitter_id": "提交人标识", "submission_date": "提交日期",
    "examination_status": "质证状态", "admission_status": "采信状态",
    "chain_of_custody": "保管链", "focus_category_id": "焦点分类标识",
    "canonical_template_id": "规范模板标识", "fact_type": "事实类型",
    "claim_text": "诉求内容", "claim_type": "诉求类型", "requested_outcome": "请求结果",
    "subject_name": "主体名称", "target_subject_id": "目标主体标识",
    "target_subject_name": "目标主体名称", "legal_basis_summary": "法律依据摘要",
    "opinion_type": "意见类型", "stance": "立场", "related_claim_ids": "关联诉求标识列表",
    "argument_text": "理由内容", "argument_basis_type": "理由类型",
    "supports_claim_id": "支撑诉求标识", "supports_opinion_id": "支撑意见标识",
    "related_fact_ids": "关联事实标识列表", "related_provision_ids": "关联法条标识列表",
    "assessment_text": "评判内容", "issue_type": "评判对象类型",
    "assessment_outcome": "评判结论", "responds_to_claim_ids": "回应诉求标识列表",
    "responds_to_opinion_ids": "回应意见标识列表", "responds_to_argument_ids": "回应理由标识列表",
    "based_on_fact_ids": "依据事实标识列表", "based_on_provision_ids": "依据法条标识列表",
    "supports_judgment_result_ids": "支撑裁判结果标识列表",
    "proven_by_evidence_ids": "证明证据标识", "subject_id": "主体标识",
    "trial_level": "审级", "role_name": "角色名称",
    "from": "起始实体", "to": "目标实体", "cardinality": "基数",
    "attributes": "属性", "optional_attributes": "可选属性", "acyclic": "无环",
    "type": "类型", "rule": "规则", "enforcement": "强制程度", "global": "全局",
    "required": "必填字段", "optional": "可选字段", "is_a": "继承自",
    "types": "类型定义", "relations": "关系定义", "constraints": "约束",
    "engineering": "工程配置", "unique_identifier_pattern": "唯一标识模式",
    "foreign_key_mapping": "外键映射", "entity_disambiguation": "实体消歧",
    "data_version": "数据版本", "incremental_update": "增量更新",
    "graph_storage": "图存储", "node_prefix": "节点前缀",
    "relation_prefix": "关系前缀", "index_enabled": "启用索引",
    "hot_layer_criteria": "热层条件", "document_source": "文书来源",
    # law_level enum
    "constitution": "宪法", "basic_law": "基本法律", "ordinary_law": "普通法律",
    "administrative_regulation": "行政法规", "local_regulation": "地方性法规",
    "self_governing_regulation": "自治条例", "military_regulation": "军事法规",
    "judicial_interpretation": "司法解释", "department_rule": "部门规章",
    "normative_document": "规范性文件",
    # status enum
    "effective": "有效/生效", "amended": "已修正", "repealed": "已废止",
    # case_type category
    "civil": "民事", "criminal": "刑事", "administrative": "行政",
    "ip": "知识产权", "execution": "执行", "state_compensation": "国家赔偿",
    # binding_force
    "mandatory": "强制参照", "persuasive": "具有说服力", "reference": "仅供参考",
    # standard_type
    "criminal_sentence": "刑事处罚", "civil_compensation": "民事赔偿",
    "administrative_penalty": "行政处罚",
    # sentence_unit
    "month": "月", "year": "年", "yuan": "元", "percent": "百分比",
    # org_type
    "company": "公司", "government_agency": "政府机构", "ngo": "非政府组织",
    "individual_business": "个体工商户", "partnership": "合伙企业",
    "sole_proprietorship": "个人独资企业",
    # court_level
    "supreme": "最高", "high": "高级", "intermediate": "中级",
    "basic": "基层", "special": "专门",
    # procuratorate_level
    "provincial": "省级", "municipal": "市级", "district": "区级",
    # firm_type
    "limited_liability": "有限责任", "sole_practitioner": "个人执业",
    # role enum
    "plaintiff": "原告", "defendant": "被告", "third_party": "第三人",
    "witness": "证人", "agent": "代理人", "expert_witness": "鉴定人",
    "interpreter": "翻译", "applicant": "申请人", "respondent": "被申请人",
    "relator": "关联人", "appellant": "上诉人", "appellee": "被上诉人",
    "retrial_applicant": "再审申请人", "retrial_respondent": "再审被申请人",
    "mediator": "调解员", "arbitrator": "仲裁员", "beneficiary": "受益人",
    # trial_level
    "first_instance": "一审", "second_instance": "二审", "retrial": "再审",
    # case status
    "filing": "立案", "trial": "审理中", "judged": "已裁判",
    "appealed": "已上诉", "retried": "已再审", "executing": "执行中",
    "terminated": "已终结",
    # dispute_resolution
    "litigation": "诉讼", "mediation": "调解", "arbitration": "仲裁",
    "judicial_aid": "司法救助", "administrative_review": "行政复议",
    # execution_status
    "pending": "待执行", "in_progress": "执行中", "completed": "已完成",
    # document_type
    "judgment": "判决书", "ruling": "裁定书", "order": "命令/令",
    "notice": "通知书", "indictment": "起诉书", "petition": "诉状/申请书",
    # evidence_type
    "document": "书证", "physical": "物证", "digital": "电子证据",
    "testimony": "证言", "expert_opinion": "鉴定意见",
    # examination_status
    "not_examined": "未质证", "examined": "已质证",
    # admission_status
    "admitted": "已采信", "not_admitted": "未采信",
    # probative_force
    "valid": "有效", "invalid": "无效",
    # fact_type
    "undisputed": "无争议", "disputed": "有争议", "to_be_proven": "待证明",
    "appeal_claim": "上诉请求", "defense_claim": "辩护/答辩请求",
    "prosecution_claim": "公诉/抗诉请求", "civil_claim": "民事实体诉求",
    "counterclaim": "反诉请求", "procedural_request": "程序性申请",
    "sentencing_request": "量刑请求", "compensation_request": "赔偿请求",
    "appeal_opinion": "上诉意见", "defense_opinion": "辩护意见",
    "agent_opinion": "代理意见", "prosecution_opinion": "公诉/抗诉意见",
    "objection_opinion": "异议/反对意见", "procedural_opinion": "程序性意见",
    "support": "支持", "oppose": "反对", "partial_support": "部分支持",
    "neutral": "中立", "unknown": "未知",
    "fact_based": "事实理由", "evidence_based": "证据理由",
    "legal_based": "法律理由", "procedural_based": "程序理由",
    "policy_based": "政策理由", "sentencing_based": "量刑理由",
    "mixed": "混合类型", "other": "其他",
    "claim": "诉求", "opinion": "意见", "argument": "理由",
    "fact": "事实", "provision": "法条", "sentencing": "量刑", "procedure": "程序",
    "adopted": "采纳", "rejected": "不采纳", "partially_adopted": "部分采纳",
    "not_addressed": "未回应", "unclear": "不明确",
    # trial_org_type
    "sole_judge": "独任审判", "collegiate_bench": "合议庭",
    "judicial_committee": "审判委员会",
    # judgment result
    "guilty": "有罪", "not_guilty": "无罪", "liable": "责任成立",
    "not_liable": "责任不成立", "dismissed": "驳回起诉",
    "withdrawn": "撤诉", "mediation_agreement": "调解协议",
    "arbitration_award": "仲裁裁决", "administrative_decision": "行政决定",
    # other attributes
    "applicability_score": "适用度评分", "citation_purpose": "引用目的",
    "similarity_score": "相似度评分", "context": "上下文",
    "citation_position": "引用位置", "start_time": "开始时间",
    "end_time": "结束时间", "role_description": "角色描述",
    "authorization_scope": "授权范围", "authorization_period_start": "授权开始日期",
    "authorization_period_end": "授权结束日期", "block": "强制阻止",
    "soft": "软约束（警告）",
}


def translate_yaml(input_path: Path, output_path: Path):
    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    output_lines = []
    current_block = None

    for line in lines:
        stripped = line.rstrip('\n')

        # Track current block for context-aware translation
        if stripped.strip() and not stripped.strip().startswith('#'):
            m = re.match(r'^(\s+)([A-Z][a-zA-Z_]+)\s*:\s*$', stripped)
            if m:
                current_block = m.group(2)
            m2 = re.match(r'^(\s+)([a-z_][a-z0-9_]*)\s*:\s*$', stripped)
            if m2 and m2.group(1) == '  ':
                current_block = m2.group(2)

        if not stripped.strip() or stripped.strip().startswith('#'):
            output_lines.append(stripped)
            continue

        translations = []
        words = re.findall(r'\b[a-z_][a-z0-9_]*\b', stripped)

        for word in words:
            if word in ('is', 'a', 'to', 'from', 'and', 'or', 'not', 'in',
                        'all', 'where', 'implies', 'true', 'false', 'null'):
                continue

            if word == 'is_primary':
                if current_block == 'CaseParticipant':
                    translations.append("is_primary（是否主要当事人）")
                elif current_block == 'typically_applies':
                    translations.append("is_primary（是否主要适用）")
                else:
                    translations.append("is_primary（是否主要）")
                continue

            if word in TRANS:
                translations.append(f"{word}（{TRANS[word]}）")

        seen = set()
        unique_trans = []
        for t in translations:
            base = t.split('（')[0]
            if base not in seen:
                seen.add(base)
                unique_trans.append(t)

        if unique_trans:
            comment = "  # " + "; ".join(unique_trans[:8])
            if '#' not in stripped:
                output_lines.append(stripped + comment)
            else:
                output_lines.append(stripped + " | " + "; ".join(unique_trans[:5]))
        else:
            output_lines.append(stripped)

    with open(output_path, 'w', encoding='utf-8') as f:
        for line in output_lines:
            f.write(line + '\n')

    print(f"[✓] 已生成: {output_path} ({len(output_lines)} 行)")


if __name__ == "__main__":
    base_dir = Path(__file__).parent
    src = base_dir / "legal_ontology_v2.yaml"
    dst = base_dir / "legal_ontology_v2.zh.yaml"

    if not src.exists():
        print(f"[✗] 源文件不存在: {src}")
        sys.exit(1)

    translate_yaml(src, dst)
