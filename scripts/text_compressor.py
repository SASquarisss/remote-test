#!/usr/bin/env python3
"""
指导性案例文本压缩器

目标：在不丢失关键信息的前提下，将长文本压缩至 LLM 最佳输入长度。

策略分类：
- 短文本 (< 3000 字)：全文输入，无需压缩
- 中文本 (3000-6000 字)：结构化压缩（保留关键段落）
- 长文末 (> 6000 字)：摘要后输入（仅保留精华）
"""

import re
from typing import Dict, List, Tuple

# 关键结构标记
CONCLUSION_MARKERS = [
    r'法院生效裁判认为',
    r'本院认为',
    r'一审法院认为',
    r'二审法院认为',
    r'再审法院认为',
]

DISPUTE_MARKERS = [
    r'本案争议焦点',
    r'争议焦点',
    r'主要争议',
]

SUMMARY_MARKERS = [
    r'综上',
    r'综合上述',
    r'综合全案',
    r'综觀全案',
]

CRIMINAL_SENTENCING_MARKERS = [
    r'被告人[^\u3002]{0,50}罪[^。]{0,100}判处',
    r'决定[^\u3002]{0,30}判处[^\u3002]{0,100}有期徒刑',
]


def clean_html(text: str) -> str:
    return text.replace('<p>', '\n').replace('</p>', '\n').replace('<br/>', '\n').replace('&nbsp;', ' ')


def extract_section(text: str, patterns: List[str], max_chars: int = 500) -> str:
    """根据正则模式提取文本区段"""
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            start = m.start()
            return text[start:start + max_chars].strip()
    return ''


def extract_disputed_issues(text: str) -> List[str]:
    """提取争议焦点（支持编号和无编号格式）"""
    issues = []
    
    # 模式1: "本案争议焦点为：一、XXX；二、XXX"
    dispute_header = re.search(r'本案争议焦点为：?(.{10,300}?)(?:二、|三、|四、|五、|本院)', text)
    if dispute_header:
        issues_text = dispute_header.group(1)
        parts = re.split(r'[；;]', issues_text)
        for p in parts:
            p = p.strip().lstrip('一二三四五六七八九十、')
            if len(p) > 5 and len(p) < 100:
                issues.append(p)
    
    # 模式2: "一、关于XXX的认定"作为段落标题
    section_titles = re.findall(r'[一二三四五六七八九十、]{1,5}([^\n]{5,60}?)(?:。|；)', text)
    for t in section_titles:
        t = t.strip()
        if any(kw in t for kw in ['认定', '确定', '责任', '因果', '过错', '违约', '是否', '构成']):
            if t not in issues:
                issues.append(t)
    
    # 模式3: 无编号格式 - "关于XXX的认定"、"是否XXX"
    # 使用更宽松的模式捕捉无编号争议焦点
    unnumbered_patterns = [
        r'关于([一-龥]{5,40}?)的认定',
        r'是否([一-龥]{5,40}?)[，；]',
        r'([一-龥]{5,40}?)是否成立',
        r'([一-龥]{5,40}?)应否支持',
    ]
    for pat in unnumbered_patterns:
        for match in re.finditer(pat, text):
            issue = match.group(1).strip()
            if issue and issue not in issues and 5 < len(issue) < 60:
                issues.append(issue)
    
    return issues[:5]


def compress_for_llm(
    basic_facts: str,
    judgment_reason: str,
    judgment_essence: str,
    related_law: str = '',
    max_input_chars: int = 4000
) -> str:
    """
    将案件文本压缩至 LLM 最佳输入长度。
    
    压缩策略：
    1. 优先保留 judgment_essence（最精炼的指导要点）
    2. 其次保留结论标记段落
    3. 然后保留争议焦点
    4. 最后根据剩余空间填充基本事实和理由
    """
    bf = clean_html(basic_facts)
    jr = clean_html(judgment_reason)
    je = clean_html(judgment_essence)
    rl = clean_html(related_law)
    
    total_len = len(bf) + len(jr) + len(je) + len(rl)
    
    # 短文本：直接返回全文
    if total_len <= 3000:
        parts = []
        if bf.strip():
            parts.append(f"## 基本事实\n{bf.strip()}")
        if jr.strip():
            parts.append(f"## 裁判理由\n{jr.strip()}")
        if je.strip():
            parts.append(f"## 裁判要旨\n{je.strip()}")
        if rl.strip():
            parts.append(f"## 相关法条\n{rl.strip()}")
        return '\n\n'.join(parts), 'full'
    
    # 中长文本：结构化压缩
    parts = []
    current_len = 0
    
    # Tier 1: judgment_essence (最高优先级)
    if je.strip():
        essence_part = f"## 裁判要旨\n{je.strip()}"
        parts.append(essence_part)
        current_len += len(essence_part)
    
    # Tier 2: conclusion header from judgment_reason
    conclusion = extract_section(jr, CONCLUSION_MARKERS, max_chars=300)
    if conclusion:
        conc_part = f"## 法院结论\n{conclusion}"
        parts.append(conc_part)
        current_len += len(conc_part)
    
    # Tier 3: disputed issues
    issues = extract_disputed_issues(jr)
    if issues:
        issues_text = '\n'.join(f"{i+1}. {issue}" for i, issue in enumerate(issues))
        issue_part = f"## 争议焦点\n{issues_text}"
        parts.append(issue_part)
        current_len += len(issue_part)
    
    # Tier 4: summary paragraph
    summary = extract_section(jr, SUMMARY_MARKERS, max_chars=400)
    if summary:
        sum_part = f"## 理由摘要\n{summary}"
        parts.append(sum_part)
        current_len += len(sum_part)
    
    # Tier 5: basic facts (truncated based on remaining space)
    remaining = max_input_chars - current_len
    if remaining > 500 and bf.strip():
        bf_lines = [l.strip() for l in bf.split('\n') if l.strip()]
        bf_condensed = '\n'.join(bf_lines[:3])
        if len(bf_condensed) > remaining * 0.6:
            bf_condensed = bf_condensed[:int(remaining * 0.6)] + '...'
        bf_part = f"## 基本事实（摘要）\n{bf_condensed}"
        parts.append(bf_part)
        current_len += len(bf_part)
    
    # Tier 6: judgment_reason head and tail (if still have space)
    remaining = max_input_chars - current_len
    if remaining > 800 and jr.strip():
        jr_lines = [l.strip() for l in jr.split('\n') if l.strip()]
        if len(jr_lines) > 1:
            head = jr_lines[0][:400]
            tail = jr_lines[-1][:400] if len(jr_lines) > 1 else ''
            jr_part = f"## 裁判理由（开头与结尾）\n{head}"
            if tail and tail != head:
                jr_part += f"\n...\n{tail}"
            parts.append(jr_part)
    
    return '\n\n'.join(parts), 'compressed'


def get_compression_stats(
    basic_facts: str,
    judgment_reason: str,
    judgment_essence: str,
    related_law: str = ''
) -> Dict:
    """返回压缩统计信息"""
    original = len(basic_facts) + len(judgment_reason) + len(judgment_essence) + len(related_law)
    compressed, strategy = compress_for_llm(basic_facts, judgment_reason, judgment_essence, related_law)
    
    return {
        'original_chars': original,
        'compressed_chars': len(compressed),
        'compression_ratio': len(compressed) / original if original > 0 else 0,
        'strategy': strategy,
        'compressed_text': compressed
    }


if __name__ == '__main__':
    # 简单测试
    test_bf = "原告贴某云诉称..."
    test_jr = "法院生效裁判认为：本案争议焦点为：一、是否构成侵权；二、赔偿金额确定。综上，法院认定被告应承担侵权责任。"
    test_je = "对于网络侵权行为，应当根据实际损害确定赔偿金额。"
    
    result = get_compression_stats(test_bf, test_jr, test_je)
    print(f"压缩率: {result['compression_ratio']:.1%}")
    print(f"策略: {result['strategy']}")
