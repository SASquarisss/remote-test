#!/usr/bin/env python3
"""
迭代式案例解析与本体论对齐评估脚本

流程:
1. 加载原始CSV数据（10条测试样本）
2. 对每条数据调用LLM解析（使用本体论对齐的prompt）
3. 评估解析结果：
   - 完整性：是否提取了所有关键信息
   - 准确性：与原始数据对比是否有解析错误
   - 本体论一致性：枚举值、实体类型是否符合本体论定义
   - 本体论完备性：原始数据中的信息是否有未被本体论覆盖的
4. 生成评估报告
5. 根据评估结果生成优化建议

使用:
    export OPENAI_API_KEY="***"
    export OPENAI_BASE_URL="https://api.moonshot.cn/v1"
    python scripts/iterative_parse_eval.py \
        --input data/raw/DataWorks_Excel_*.csv \
        --output data/processed/iterative_eval_results.json \
        --limit 10
"""

import argparse
import csv
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path


# ============ 配置 ============
DEFAULT_PROMPT_PATH = Path(__file__).parent / "prompts" / "guiding_case_ontology_aligned.txt"

# 本体论定义的枚举值（用于校验）
ONTOLOGY_ENUMS = {
    "binding_force": {"mandatory", "persuasive", "reference"},
    "case_level": {"guiding_case", "typical_case", "reference_case"},
    "category": {"civil", "criminal", "administrative", "ip", "execution", "state_compensation"},
    "trial_level": {"first_instance", "second_instance", "retrial", "execution"},
    "trial_procedure": {"一审", "二审", "再审", "执行", "保全", "强制执行"},
    "court_level": {"supreme", "high", "intermediate", "basic", "special"},
    "subject_type": {"natural_person", "organization"},
    "org_type": {"company", "government_agency", "ngo", "law_firm", "expert_institution", "court", "procuratorate"},
    "role_code": {"plaintiff", "defendant", "third_party", "witness", "agent", "expert_witness", "interpreter", "prosecutor", "applicant", "respondent", "relator"},
    "citation_position": {"basic_facts", "judgment_reason", "judgment_essence", "related_info"},
    "citation_purpose": {"适用依据", "说理依据", "反驳依据"},
    "fact_type": {"undisputed", "disputed", "to_be_proven"},
    "status": {"filing", "trial", "judged", "effective", "appealed", "retried", "executing", "terminated"},
}

# 必填字段检查映射
REQUIRED_FIELDS = {
    "guiding_case": ["binding_force", "case_level"],
    "case_type": ["category", "level1", "level2"],
    "court_cases": ["case_number", "trial_level", "court"],
    "legal_subjects": ["name", "subject_type", "roles"],
    "legal_provisions": ["statute", "article"],
    "case_summary": ["key_facts", "disputed_issues", "conclusion"],
}


def clean_text(text: str) -> str:
    """清理HTML标签和转义字符"""
    if not text or text == '\\N':
        return ''
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('u3000', '\u3000')
    text = text.replace('u2002', '\u2002')
    text = text.strip()
    text = re.sub(r'\n+', '\n', text)
    return text


def load_csv_records(csv_path: str, limit: int = 0) -> list:
    """加载CSV数据"""
    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=",", quotechar='"')
        header = next(reader)
        header = [h.strip().lstrip('\ufeff').strip('"') for h in header]

        for row in reader:
            record = {
                'id': row[0] if len(row) > 0 else '',
                'web_name': row[1] if len(row) > 1 else '',
                'web_url': row[2] if len(row) > 2 else '',
                'case_type': row[3] if len(row) > 3 else '',
                'storage_no': row[4] if len(row) > 4 else '',
                'court_name': row[5] if len(row) > 5 else '',
                'key_words': row[6] if len(row) > 6 else '',
                'trial_procedure': row[7] if len(row) > 7 else '',
                'trial_year': row[8] if len(row) > 8 else '',
                'case_level': row[9] if len(row) > 9 else '',
                'basic_facts': clean_text(row[10]) if len(row) > 10 else '',
                'judgment_reason': clean_text(row[11]) if len(row) > 11 else '',
                'judgment_essence': clean_text(row[12]) if len(row) > 12 else '',
                'related_info': clean_text(row[13]) if len(row) > 13 else '',
                'related_law': clean_text(row[14]) if len(row) > 14 else '',
                'related_judgment_body': clean_text(row[15]) if len(row) > 15 else '',
                'create_time': row[16] if len(row) > 16 else '',
                'update_time': row[17] if len(row) > 17 else '',
                'md5_value': row[18] if len(row) > 18 else '',
                'judgment_mean': row[19] if len(row) > 19 else '',
                'dt': row[20] if len(row) > 20 else '',
            }
            records.append(record)
            if limit > 0 and len(records) >= limit:
                break
    return records


def build_prompt(record: dict, prompt_template: str) -> str:
    """构造LLM prompt"""
    # 构建案件文本
    text_parts = []

    # 元数据
    text_parts.append(f"[case_type]{record.get('case_type', '')}[/case_type]")
    text_parts.append(f"[key_words]{record.get('key_words', '')}[/key_words]")
    text_parts.append(f"[trial_procedure]{record.get('trial_procedure', '')}[/trial_procedure]")
    text_parts.append(f"[trial_year]{record.get('trial_year', '')}[/trial_year]")
    text_parts.append(f"[case_level]{record.get('case_level', '')}[/case_level]")
    text_parts.append(f"[storage_no]{record.get('storage_no', '')}[/storage_no]")
    text_parts.append(f"[court_name]{record.get('court_name', '')}[/court_name]")
    text_parts.append(f"[judgment_mean]{record.get('judgment_mean', '')}[/judgment_mean]")

    if record.get('basic_facts'):
        text_parts.append(f"[basic_facts]{record['basic_facts']}[/basic_facts]")
    if record.get('judgment_reason'):
        text_parts.append(f"[judgment_reason]{record['judgment_reason']}[/judgment_reason]")
    if record.get('judgment_essence'):
        text_parts.append(f"[judgment_essence]{record['judgment_essence']}[/judgment_essence]")
    if record.get('related_info'):
        text_parts.append(f"[related_info]{record['related_info']}[/related_info]")
    if record.get('related_law'):
        text_parts.append(f"[related_law]{record['related_law']}[/related_law]")

    case_text = '\n'.join(text_parts)

    # 截断过长文本以节省token（保留元数据字段，仅截断正文内容）
    if len(case_text) > 8000:
        # 保留前5000字符，尽量保留基本事实和裁判理由
        case_text = case_text[:5000] + "\n\n...[文本已截断保留元数据字段]" + case_text[-2000:]

    return prompt_template.replace("{case_text}", case_text)


def parse_llm_response(response_text: str) -> dict:
    """解析LLM返回的JSON"""
    # 尝试直接解析
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # 尝试提取JSON代码块
    code_block_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取花括号内容
    brace_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法解析JSON: {response_text[:200]}")


def call_llm(prompt: str, api_key: str, base_url: str, model: str,
             max_retries: int = 3) -> dict:
    """调用LLM API"""
    import openai

    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是专业的法律文本解析工具，请严格输出JSON。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000,
            )
            content = response.choices[0].message.content
            return parse_llm_response(content)
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"  API调用失败，{wait}秒后重试: {e}")
                time.sleep(wait)
            else:
                raise


def evaluate_completeness(parsed: dict) -> dict:
    """评估解析结果的完整性"""
    issues = []
    score = 100

    for section, fields in REQUIRED_FIELDS.items():
        if section not in parsed:
            issues.append(f"缺少顶级字段: {section}")
            score -= 10
            continue

        section_data = parsed[section]
        if isinstance(section_data, list):
            if not section_data:
                issues.append(f"{section}: 空列表")
                score -= 5
            else:
                for idx, item in enumerate(section_data):
                    for field in fields:
                        if field not in item or item[field] is None or item[field] == '':
                            issues.append(f"{section}[{idx}].{field}: 缺少或为空")
                            score -= 2
        elif isinstance(section_data, dict):
            for field in fields:
                if field not in section_data or section_data[field] is None or section_data[field] == '':
                    issues.append(f"{section}.{field}: 缺少或为空")
                    score -= 3

    # 检查关键字段是否有内容
    if not parsed.get("legal_provisions"):
        issues.append("未提取到任何法条引用")
        score -= 5

    if not parsed.get("legal_subjects"):
        issues.append("未提取到任何当事人")
        score -= 10

    if not parsed.get("court_cases"):
        issues.append("未提取到案号信息")
        score -= 5

    return {
        "score": max(0, score),
        "issues": issues,
        "total_issues": len(issues)
    }


def evaluate_ontology_consistency(parsed: dict) -> dict:
    """评估解析结果与本体论的一致性"""
    issues = []
    score = 100

    def check_enum(path: str, value: str, enum_name: str):
        if not value:
            return
        valid_values = ONTOLOGY_ENUMS.get(enum_name, set())
        if valid_values and value not in valid_values:
            issues.append(f"{path}: 非法枚举值 '{value}'，应在 {valid_values} 中")
            nonlocal score
            score -= 3

    # GuidingCase
    gc = parsed.get("guiding_case", {})
    if gc:
        check_enum("guiding_case.binding_force", gc.get("binding_force"), "binding_force")
        check_enum("guiding_case.case_level", gc.get("case_level"), "case_level")

    # CaseType
    ct = parsed.get("case_type", {})
    if ct:
        check_enum("case_type.category", ct.get("category"), "category")

    # CourtCases
    for idx, cc in enumerate(parsed.get("court_cases", [])):
        check_enum(f"court_cases[{idx}].trial_level", cc.get("trial_level"), "trial_level")
        court = cc.get("court", {})
        if court:
            check_enum(f"court_cases[{idx}].court.court_level", court.get("court_level"), "court_level")
        check_enum(f"court_cases[{idx}].status", cc.get("status"), "status")

    # LegalSubjects
    for idx, ls in enumerate(parsed.get("legal_subjects", [])):
        check_enum(f"legal_subjects[{idx}].subject_type", ls.get("subject_type"), "subject_type")
        check_enum(f"legal_subjects[{idx}].org_type", ls.get("org_type"), "org_type")
        for ridx, role in enumerate(ls.get("roles", [])):
            check_enum(f"legal_subjects[{idx}].roles[{ridx}].role_code", role.get("role_code"), "role_code")

    # LegalProvisions
    for idx, lp in enumerate(parsed.get("legal_provisions", [])):
        check_enum(f"legal_provisions[{idx}].citation_position", lp.get("citation_position"), "citation_position")
        check_enum(f"legal_provisions[{idx}].citation_purpose", lp.get("citation_purpose"), "citation_purpose")

    # Facts
    for idx, fact in enumerate(parsed.get("facts", [])):
        check_enum(f"facts[{idx}].fact_type", fact.get("fact_type"), "fact_type")

    return {
        "score": max(0, score),
        "issues": issues,
        "total_issues": len(issues)
    }


def evaluate_accuracy(record: dict, parsed: dict) -> dict:
    """评估解析结果的准确性（与原始数据对比）"""
    issues = []
    score = 100

    # 1. 案件类型对比
    raw_case_type = record.get("case_type", "")
    parsed_level1 = parsed.get("case_type", {}).get("level1", "")
    parsed_level2 = parsed.get("case_type", {}).get("level2", "")
    if raw_case_type:
        parts = raw_case_type.split("-", 1)
        expected_level1 = parts[0] if len(parts) > 0 else ""
        expected_level2 = parts[1] if len(parts) > 1 else ""
        if parsed_level1 != expected_level1:
            issues.append(f"case_type.level1 不匹配: 解析='{parsed_level1}' vs 原始='{expected_level1}'")
            score -= 3
        if parsed_level2 != expected_level2:
            issues.append(f"case_type.level2 不匹配: 解析='{parsed_level2}' vs 原始='{expected_level2}'")
            score -= 3

    # 2. 案号检查：检查解析的案号是否在原始文本中存在
    raw_text = " ".join([
        record.get("basic_facts", ""),
        record.get("judgment_reason", ""),
        record.get("related_info", ""),
        record.get("related_judgment_body", ""),
    ])
    parsed_cases = parsed.get("court_cases", [])
    for idx, cc in enumerate(parsed_cases):
        case_num = cc.get("case_number", "")
        if case_num and case_num not in raw_text:
            issues.append(f"court_cases[{idx}].case_number '{case_num}' 在原始文本中未找到")
            score -= 2

    # 3. 法院名称检查
    raw_court_name = record.get("court_name", "")
    if raw_court_name:
        court_found = False
        for cc in parsed_cases:
            court = cc.get("court", {})
            if court and raw_court_name in court.get("name", ""):
                court_found = True
                break
        if not court_found:
            issues.append(f"未提取到发布法院 '{raw_court_name}'")
            score -= 3

    # 4. 关键词检查
    raw_keywords = record.get("key_words", "")
    if raw_keywords:
        parsed_keywords = parsed.get("guiding_case", {}).get("key_words", [])
        if not parsed_keywords:
            issues.append("未提取关键词")
            score -= 2

    # 5. 审判程序检查
    raw_procedure = record.get("trial_procedure", "")
    if raw_procedure:
        parsed_procedure = parsed.get("guiding_case", {}).get("trial_procedure", "")
        if not parsed_procedure:
            issues.append("未提取审判程序")
            score -= 2

    # 6. 当事人数量对比（仅作为警示，不扣分）
    # 检查是否有明显遗漏当事人

    return {
        "score": max(0, score),
        "issues": issues,
        "total_issues": len(issues)
    }


def evaluate_ontology_coverage(record: dict, parsed: dict) -> dict:
    """评估原始数据中的信息是否被本体论覆盖"""
    issues = []
    uncovered = []

    # 检查原始数据中有但解析未覆盖的关键信息
    if record.get("related_law") and not parsed.get("legal_provisions"):
        uncovered.append("原始数据有related_law但未解析出法条")

    if record.get("related_info") and not parsed.get("court_cases"):
        uncovered.append("原始数据有related_info但未解析出案号")

    if record.get("judgment_mean") and not parsed.get("guiding_case", {}).get("judgment_mean"):
        uncovered.append("原始数据有judgment_mean但未解析出来")

    # 检查本体论可能缺少的字段
    if record.get("related_judgment_body"):
        issues.append("本体论缺少 'related_judgment_body' 字段映射（裁判主文）")

    if record.get("related_info"):
        # related_info通常包含关联案件的案号和法院，但本体论中没有明确字段
        pass

    return {
        "uncovered_fields": uncovered,
        "ontology_gaps": issues
    }


def generate_report(results: list) -> dict:
    """生成整体评估报告"""
    total = len(results)
    completeness_scores = [r["eval_completeness"]["score"] for r in results]
    consistency_scores = [r["eval_consistency"]["score"] for r in results]
    accuracy_scores = [r["eval_accuracy"]["score"] for r in results]

    report = {
        "summary": {
            "total_samples": total,
            "avg_completeness": round(sum(completeness_scores) / total, 2) if total > 0 else 0,
            "avg_consistency": round(sum(consistency_scores) / total, 2) if total > 0 else 0,
            "avg_accuracy": round(sum(accuracy_scores) / total, 2) if total > 0 else 0,
            "overall_score": round(
                (sum(completeness_scores) + sum(consistency_scores) + sum(accuracy_scores)) / (3 * total), 2
            ) if total > 0 else 0,
        },
        "samples": results,
        "recommendations": []
    }

    # 生成优化建议
    all_issues = []
    for r in results:
        all_issues.extend(r["eval_completeness"]["issues"])
        all_issues.extend(r["eval_consistency"]["issues"])
        all_issues.extend(r["eval_accuracy"]["issues"])

    # 统计问题频次
    from collections import Counter
    issue_counts = Counter(all_issues)
    top_issues = issue_counts.most_common(10)

    if top_issues:
        report["recommendations"].append("常见问题：")
        for issue, count in top_issues:
            report["recommendations"].append(f"  - {issue} (出现{count}次)")

    if report["summary"]["avg_completeness"] < 80:
        report["recommendations"].append("建议：解析完整性不足，需要强化prompt中对必填字段的强调。")
    if report["summary"]["avg_consistency"] < 80:
        report["recommendations"].append("建议：本体论一致性不足，需要在prompt中更明确地列出所有枚举值。")
    if report["summary"]["avg_accuracy"] < 80:
        report["recommendations"].append("建议：解析准确性不足，需要增加原始数据与解析结果的对照验证。")

    return report


def main():
    parser = argparse.ArgumentParser(description="迭代式案例解析与本体论对齐评估")
    parser.add_argument("--input", required=True, help="输入CSV文件路径")
    parser.add_argument("--output", required=True, help="输出JSON评估报告路径")
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT_PATH), help="Prompt模板路径")
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY"), help="API Key")
    parser.add_argument("--base-url", default=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1"), help="API Base URL")
    parser.add_argument("--model", default="deepseek-v4-pro", help="模型名称")
    parser.add_argument("--limit", type=int, default=10, help="处理条数")
    parser.add_argument("--dry-run", action="store_true", help="仅进行评估，不调用LLM")
    args = parser.parse_args()

    print(f"加载 prompt: {args.prompt}")
    with open(args.prompt, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    print(f"加载 CSV: {args.input}")
    records = load_csv_records(args.input, limit=args.limit)
    print(f"加载了 {len(records)} 条记录")

    results = []

    for i, record in enumerate(records):
        print(f"\n[{i+1}/{len(records)}] 处理 id={record['id']} case_type={record['case_type']}")

        if args.dry_run:
            print("  [dry-run] 跳过LLM调用")
            parsed = {}
        else:
            if not args.api_key:
                print("错误：未设置API Key")
                return

            prompt = build_prompt(record, prompt_template)
            try:
                parsed = call_llm(prompt, args.api_key, args.base_url, args.model)
                print(f"  解析成功，提取了 {len(parsed.get('legal_subjects', []))} 个当事人, {len(parsed.get('legal_provisions', []))} 条法条")
            except Exception as e:
                print(f"  解析失败: {e}")
                parsed = {"_error": str(e)}

        # 评估
        eval_completeness = evaluate_completeness(parsed)
        eval_consistency = evaluate_ontology_consistency(parsed)
        eval_accuracy = evaluate_accuracy(record, parsed)
        eval_coverage = evaluate_ontology_coverage(record, parsed)

        print(f"  完整性: {eval_completeness['score']}/100, 一致性: {eval_consistency['score']}/100, 准确性: {eval_accuracy['score']}/100")

        results.append({
            "id": record["id"],
            "case_type": record["case_type"],
            "parsed": parsed,
            "eval_completeness": eval_completeness,
            "eval_consistency": eval_consistency,
            "eval_accuracy": eval_accuracy,
            "eval_coverage": eval_coverage,
        })

        # 每3条保存一次中间结果
        if (i + 1) % 3 == 0:
            temp_path = args.output + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump({"partial": True, "results": results}, f, ensure_ascii=False, indent=2)
            print(f"  中间结果已保存: {temp_path}")

    # 生成报告
    report = generate_report(results)
    report["metadata"] = {
        "prompt_file": str(args.prompt),
        "model": args.model,
        "timestamp": datetime.now().isoformat(),
        "total_samples": len(records)
    }

    # 保存报告
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"评估完成！")
    print(f"总体得分: {report['summary']['overall_score']}/100")
    print(f"完整性: {report['summary']['avg_completeness']}/100")
    print(f"一致性: {report['summary']['avg_consistency']}/100")
    print(f"准确性: {report['summary']['avg_accuracy']}/100")
    print(f"结果保存至: {output_path}")
    if report["recommendations"]:
        print(f"\n优化建议:")
        for rec in report["recommendations"]:
            print(f"  {rec}")


if __name__ == "__main__":
    main()
