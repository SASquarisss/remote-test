#!/usr/bin/env python3
"""
自动迭代测试与优化脚本
============================
每次运行时：
1. 从主CSV中抽取10条未测试数据
2. LLM提取
3. 分析结果，识别问题
4. 记录问题，尝试自动修复低风险问题
5. 生成汇报

使用：
    python scripts/auto_iterative_test.py
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.text_compressor import compress_for_llm

REPO = Path(__file__).parent.parent
MASTER_CSV = next((REPO / "data/raw").glob("*.csv"), REPO / "data/raw/default.csv")
STATE_FILE = REPO / "data/processed/auto_test_state.json"
REPORT_FILE = REPO / "data/processed/auto_test_report.md"
PROMPT_FILE = REPO / "scripts/prompts/guiding_case_extraction.txt"
BATCH_SIZE = 10

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"tested_ids": [], "batch_count": 0, "cumulative_stats": {}}

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def get_untested_ids():
    state = load_state()
    tested = set(str(x) for x in state.get("tested_ids", []))
    
    # 也检查其他已有的jsonl中的id
    for path in REPO.glob("data/processed/*.jsonl"):
        if "auto_test" in path.name:
            continue
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    rid = obj.get('id') or obj.get('case_id')
                    if rid:
                        tested.add(str(rid))
                except:
                    pass
    
    all_ids = []
    with open(MASTER_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('id'):
                all_ids.append(row['id'])
    
    untested = [i for i in all_ids if i not in tested]
    return untested, tested, all_ids

def extract_batch(untested_ids, batch_size=BATCH_SIZE):
    batch = untested_ids[:batch_size]
    rows = []
    with open(MASTER_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['id'] in batch:
                rows.append(row)
    return rows

def run_llm_extraction(rows, api_key, base_url, model):
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
        prompt_template = f.read()
    
    results = []
    for row in rows:
        rid = row['id']
        case_type = row['case_type']
        basic_facts = row.get('basic_facts', '')
        judgment_reason = row.get('judgment_reason', '')
        judgment_essence = row.get('judgment_essence', '')
        related_law = row.get('related_law', '')
        
        compressed_text, strategy = compress_for_llm(
            basic_facts, judgment_reason, judgment_essence, related_law
        )
        
        case_text = f"案件类型：{case_type}\n\n{compressed_text}"
        prompt = prompt_template.replace('{case_text}', case_text)
        
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一个专业的法律文本解析工具。请严格按照要求输出 JSON。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=4096,
                timeout=60,
            )
            content = response.choices[0].message.content
            
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            result = json.loads(content)
            result['id'] = rid
            result['case_type'] = case_type
            result['_compression_strategy'] = strategy
            result['_compressed_chars'] = len(compressed_text)
            result['_original_chars'] = len(basic_facts) + len(judgment_reason) + len(judgment_essence) + len(related_law)
            results.append(result)
            
        except Exception as e:
            results.append({
                'id': rid,
                'case_type': case_type,
                'error': str(e),
                '_compression_strategy': strategy
            })
        
        time.sleep(1)  # 防止限流
    
    return results

def analyze_results(results, rows):
    """分析结果，识别问题和优化空间"""
    issues = []
    stats = {
        'total': len(results),
        'success': 0,
        'failed': 0,
        'has_parties': 0,
        'has_case_numbers': 0,
        'has_legal_provisions': 0,
        'has_guiding_points': 0,
        'has_judgment_result': 0,
        'compression_full': 0,
        'compression_compressed': 0,
        'result_types': Counter(),
        'case_types': Counter(),
        'provision_sources': Counter(),
    }
    
    for r in results:
        if 'error' in r:
            stats['failed'] += 1
            continue
        stats['success'] += 1
        
        if r.get('parties'):
            stats['has_parties'] += 1
        else:
            issues.append(f"ID {r['id']}: 当事人提取为空")
        
        if r.get('case_numbers'):
            stats['has_case_numbers'] += 1
        else:
            issues.append(f"ID {r['id']}: 案号提取为空")
        
        if r.get('legal_provisions'):
            stats['has_legal_provisions'] += 1
            # 检查是否来自 fallback
            if r.get('_provision_source') == 'fallback':
                stats['provision_sources']['fallback'] += 1
            else:
                stats['provision_sources']['llm'] += 1
        else:
            issues.append(f"ID {r['id']}: 法条提取为空")
            stats['provision_sources']['none'] += 1
        
        if r.get('guiding_points'):
            stats['has_guiding_points'] += 1
        
        if r.get('judgment_result', {}).get('result_type'):
            stats['has_judgment_result'] += 1
            rt = r['judgment_result']['result_type']
            stats['result_types'][rt] += 1
            
            # 检查 dismissed 误用
            if rt == 'dismissed':
                case_type = r.get('case_type', '')
                if '刑事' in case_type:
                    issues.append(f"ID {r['id']}: 刑事案件误用 dismissed，应为 acquitted/remanded")
                elif '民事' in case_type and '驳回' not in str(r.get('judgment_result',{}).get('reasoning_summary','')):
                    issues.append(f"ID {r['id']}: 民事案件 dismissed 可能误用，应检查是否为程序性驳回")
        else:
            issues.append(f"ID {r['id']}: 裁判结果缺失")
        
        if r.get('_compression_strategy') == 'full':
            stats['compression_full'] += 1
        else:
            stats['compression_compressed'] += 1
        
        stats['case_types'][r.get('case_type', 'unknown')] += 1
    
    # 汇总级别分析
    if stats['success'] > 0:
        parties_rate = stats['has_parties'] / stats['success']
        case_num_rate = stats['has_case_numbers'] / stats['success']
        provision_rate = stats['has_legal_provisions'] / stats['success']
        result_rate = stats['has_judgment_result'] / stats['success']
        
        if parties_rate < 0.7:
            issues.append(f"[汇总] 当事人提取率仅{parties_rate:.0%}，prompt中当事人提取说明可能不足")
        if case_num_rate < 0.5:
            issues.append(f"[汇总] 案号提取率仅{case_num_rate:.0%}，案号示例或变体覆盖不足")
        if provision_rate < 0.5:
            issues.append(f"[汇总] 法条提取率仅{provision_rate:.0%}，fallback/正则/提示词需优化")
        if result_rate < 0.7:
            issues.append(f"[汇总] 裁判结果提取率仅{result_rate:.0%}，可能是文本压缩丢失关键信息")
    
    return issues, stats

def try_auto_fix(issues):
    """尝试自动修复低风险问题，返回已执行的修复列表"""
    fixes = []
    
    # 检查是否有案号提取问题
    case_num_issues = [i for i in issues if '案号' in i]
    if len(case_num_issues) >= 3:
        # 低风险：在prompt中增加案号变体说明
        fixes.append("案号提取率低，已记录需增加变体示例")
    
    # 检查是否有当事人问题
    party_issues = [i for i in issues if '当事人' in i]
    if len(party_issues) >= 3:
        fixes.append("当事人提取率低，已记录需优化当事人识别逻辑")
    
    # 检查 dismissed 误用
    dismissed_issues = [i for i in issues if 'dismissed' in i]
    if len(dismissed_issues) >= 2:
        # 检查 prompt 中是否已有足够的反例说明
        with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
            prompt_content = f.read()
        if 'not_liable' in prompt_content and 'dismissed' in prompt_content:
            fixes.append(f"发现{len(dismissed_issues)}条dismissed误用，prompt已包含反例，可能需要更强制的模型或训练")
        else:
            fixes.append("发现dismissed误用，prompt反例说明不足（待确认修复）")
    
    return fixes

def save_batch(results, batch_num, id_range):
    batch_file = REPO / f"data/processed/auto_test_batch_{batch_num}.jsonl"
    with open(batch_file, 'w', encoding='utf-8') as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    return batch_file

def update_report(batch_num, id_range, stats, issues, fixes):
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    report_lines = []
    if not REPORT_FILE.exists():
        report_lines.append("# 自动迭代测试报告\n\n")
    
    report_lines.append(f"## 第{batch_num}批 | {now}\n")
    report_lines.append(f"数据ID范围: {id_range}\n\n")
    
    report_lines.append("### 统计\n")
    report_lines.append(f"- 总数: {stats['total']}\n")
    report_lines.append(f"- 成功: {stats['success']} | 失败: {stats['failed']}\n")
    report_lines.append(f"- 当事人提取: {stats['has_parties']}/{stats['success']}\n")
    report_lines.append(f"- 案号提取: {stats['has_case_numbers']}/{stats['success']}\n")
    report_lines.append(f"- 法条提取: {stats['has_legal_provisions']}/{stats['success']}\n")
    report_lines.append(f"- 裁判结果: {stats['has_judgment_result']}/{stats['success']}\n")
    report_lines.append(f"- 压缩策略: full={stats['compression_full']}, compressed={stats['compression_compressed']}\n")
    report_lines.append(f"- result_type 分布: {dict(stats['result_types'])}\n\n")
    
    if issues:
        report_lines.append("### 发现的问题\n")
        for issue in issues:
            report_lines.append(f"- {issue}\n")
        report_lines.append("\n")
    
    if fixes:
        report_lines.append("### 自动修复/记录\n")
        for fix in fixes:
            report_lines.append(f"- {fix}\n")
        report_lines.append("\n")
    
    with open(REPORT_FILE, 'a', encoding='utf-8') as f:
        f.writelines(report_lines)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api-key', default=os.getenv('DEEPSEEK_API_KEY'))
    parser.add_argument('--base-url', default='https://api.deepseek.com/v1')
    parser.add_argument('--model', default='deepseek-chat')
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE)
    args = parser.parse_args()
    
    if not args.api_key:
        print("ERROR: API key required")
        sys.exit(1)
    
    state = load_state()
    untested, tested, all_ids = get_untested_ids()
    
    print(f"[总数据] {len(all_ids)} | [已测试] {len(tested)} | [未测试] {len(untested)}")
    
    if len(untested) == 0:
        print("所有数据已测试完毕")
        return
    
    batch = extract_batch(untested, args.batch_size)
    batch_ids = [r['id'] for r in batch]
    id_range = f"{batch_ids[0]} ~ {batch_ids[-1]}" if len(batch_ids) > 1 else batch_ids[0]
    
    print(f"\n本批测试ID范围: {id_range}")
    print(f"抽取数据: {len(batch)} 条")
    
    # LLM提取
    print("\n[步骤1/4] 运行 LLM 提取...")
    results = run_llm_extraction(batch, args.api_key, args.base_url, args.model)
    
    # 分析
    print("[步骤2/4] 分析结果...")
    issues, stats = analyze_results(results, batch)
    
    # 尝试自动修复
    print("[步骤3/4] 尝试自动修复...")
    fixes = try_auto_fix(issues)
    
    # 保存
    print("[步骤4/4] 保存结果...")
    batch_num = state.get("batch_count", 0) + 1
    batch_file = save_batch(results, batch_num, id_range)
    
    # 更新状态
    state["tested_ids"].extend(batch_ids)
    state["batch_count"] = batch_num
    state["last_run"] = datetime.now().isoformat()
    save_state(state)
    
    # 更新报告
    update_report(batch_num, id_range, stats, issues, fixes)
    
    print(f"\n✅ 第{batch_num}批完成")
    print(f"   批次文件: {batch_file}")
    print(f"   报告文件: {REPORT_FILE}")
    print(f"   发现问题: {len(issues)} 条")
    print(f"   自动修复: {len(fixes)} 条")

if __name__ == '__main__':
    main()
