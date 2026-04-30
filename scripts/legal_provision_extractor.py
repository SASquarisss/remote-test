#!/usr/bin/env python3
"""
法律条文提取器

支持格式：
- 《中华人民共和国XXX法》第XXX条
- XXX法第XXX条第XXX款
- XXX法第三百三十八条之一
- 第XXX条第XXX项
- 无书号名称：刑法第338条

输出格式：
    [
        {"law_name": "刑法", "article_number": "338", "clause": "", "sub_clause": ""},
        ...
    ]
"""

import re
from typing import List, Dict

# 中文数字到阿拉伯数字映射
CHINESE_NUMBERS = {
    '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
    '百': 100, '千': 1000
}


def chinese_to_arabic(s: str) -> str:
    """将中文数字转换为阿拉伯数字。"""
    if not s:
        return ""
    # 如果已经是阿拉伯数字，直接返回
    if s.isdigit():
        return s
    
    result = 0
    temp = 0
    for char in s:
        if char in CHINESE_NUMBERS:
            num = CHINESE_NUMBERS[char]
            if num >= 10:
                if temp == 0:
                    temp = 1
                result += temp * num
                temp = 0
            else:
                temp = temp * 10 + num if temp > 0 else num
        else:
            continue
    result += temp
    return str(result) if result > 0 else ""


# 法律名称白名单（简称 -> 全称映射）
LAW_NAME_WHITELIST = {
    '刑法': '中华人民共和国刑法',
    '民法典': '中华人民共和国民法典',
    '民事诉讼法': '中华人民共和国民事诉讼法',
    '行政诉讼法': '中华人民共和国行政诉讼法',
    '刑事诉讼法': '中华人民共和国刑事诉讼法',
    '商标法': '中华人民共和国商标法',
    '专利法': '中华人民共和国专利法',
    '著作权法': '中华人民共和国著作权法',
    '合同法': '中华人民共和国合同法',
    '广告法': '中华人民共和国广告法',
    '反垄断法': '中华人民共和国反垄断法',
    '公司法': '中华人民共和国公司法',
    '审判监督程序规则': '人民检察院刑事诉讼规则',
    '涉外民事关系法律适用法': '中华人民共和国涉外民事关系法律适用法',
    '海商法': '中华人民共和国海商法',
    '环境保护法': '中华人民共和国环境保护法',
    '消费者权益保护法': '中华人民共和国消费者权益保护法',
    '房地产管理法': '中华人民共和国城市房地产管理法',
    '建筑法': '中华人民共和国建筑法',
    '土地管理法': '中华人民共和国土地管理法',
    '劳动法': '中华人民共和国劳动法',
    '社会保险法': '中华人民共和国社会保险法',
    '婚姻家庭编绡法': '中华人民共和国婚姻家庭编绡法',
    '继承法': '中华人民共和国继承法',
    '物权法': '中华人民共和国物权法',
    '侵权责任法': '中华人民共和国侵权责任法',
    '保险法': '中华人民共和国保险法',
    '幸运票条例': '中华人民共和国幸运票条例',
    '人民检察院刑事诉讼规则': '人民检察院刑事诉讼规则',
}


def normalize_law_name(name: str) -> str:
    """法律名称归一化：补充为全称。"""
    name = name.strip()
    # 去除《》
    name = name.strip('《》')
    
    # 先检查白名单（简称映射）
    if name in LAW_NAME_WHITELIST:
        return LAW_NAME_WHITELIST[name]
    
    # 已是全称的直接返回
    if name.startswith('中华人民共和国'):
        return name
    
    # 其他情况：尝试补充前缀
    if name.endswith(('法', '规则', '条例', '规定', '办法', '通知')):
        return f'中华人民共和国{name}'
    
    return name


def extract_provisions(text: str) -> List[Dict]:
    """
    从文本中提取法律条文引用。"""
    if not text or text == '\\N':
        return []
    
    provisions = []
    seen = set()
    
    # 模式1: 《法律名称》第三百三十八条之一第二款第四项
    pattern1 = re.compile(
        r'《([^》]{2,30}?)》第([一二三四五六七八九十百零\d]+)条(?:之([一二三四五六七八九十\d]+))?(?:第([一二三四五六七八九十\d]+)款)?(?:第([一二三四五六七八九十\d]+)项)?'
    )
    
    # 模式2: 法律名称第三百三十八条（无书号名，但名称不含"条"、"款"、"项"等）
    # 法律名称通常是"法"、"规定"、"条例"等结尾
    pattern2 = re.compile(
        r'(?<!《)(?<![条款项之第\d])([一-龥]{2,15}(?:法|规定|条例|解释|通知|办法))第([一二三四五六七八九十百零\d]+)条(?:之([一二三四五六七八九十\d]+))?(?:第([一二三四五六七八九十\d]+)款)?(?:第([一二三四五六七八九十\d]+)项)?'
    )
    
    # 模式3: 第338条第2款（无法律名称，仅条号）
    pattern3 = re.compile(
        r'第(《?)(二?百?三?十?八?九?七?六?五?四?一?十?零?百?千?)(》?)条(?:之([一二三四五六七八九十\d]+))?(?:第([一二三四五六七八九十\d]+)款)?(?:第([一二三四五六七八九十\d]+)项)?'
    )
    
    for pattern in [pattern1, pattern2, pattern3]:
        for match in pattern.finditer(text):
            if pattern == pattern3:
                # 模式3没有法律名称，跳过（无法确定属于哪部法律）
                continue
            
            law_name = normalize_law_name(match.group(1))
            article = chinese_to_arabic(match.group(2))
            amendment = chinese_to_arabic(match.group(3)) if match.group(3) else ""
            clause = chinese_to_arabic(match.group(4)) if match.group(4) else ""
            sub_clause = chinese_to_arabic(match.group(5)) if match.group(5) else ""
            
            if not article:
                continue
            
            # 构建唯一键去重
            key = f"{law_name}_{article}_{amendment}_{clause}_{sub_clause}"
            if key in seen:
                continue
            seen.add(key)
            
            provisions.append({
                "law_name": law_name,
                "article_number": article,
                "amendment": amendment,
                "clause": clause,
                "sub_clause": sub_clause,
                "raw": match.group(0)
            })
    
    return provisions


def extract_provisions_from_record(row: list) -> List[Dict]:
    """
    从 CSV 记录的多个字段中提取法条。
    优先级：related_law > related_info > judgment_reason > judgment_essence > basic_facts
    """
    fields = []
    if len(row) > 14 and row[14] and row[14] != '\\N':
        fields.append(("related_law", row[14]))
    if len(row) > 13 and row[13] and row[13] != '\\N':
        fields.append(("related_info", row[13]))
    if len(row) > 11 and row[11] and row[11] != '\\N':
        fields.append(("judgment_reason", row[11]))
    if len(row) > 12 and row[12] and row[12] != '\\N':
        fields.append(("judgment_essence", row[12]))
    if len(row) > 10 and row[10] and row[10] != '\\N':
        fields.append(("basic_facts", row[10]))
    
    all_provisions = []
    seen = set()
    
    for field_name, text in fields:
        provisions = extract_provisions(text)
        for p in provisions:
            key = f"{p['law_name']}_{p['article_number']}_{p['amendment']}_{p['clause']}_{p['sub_clause']}"
            if key not in seen:
                seen.add(key)
                p['source_field'] = field_name
                all_provisions.append(p)
    
    return all_provisions


if __name__ == '__main__':
    # Test
    test_text = "《中华人民共和国刑法》第三百三十八条之一第二款第四项、民事诉讼法第二百三十六条、商标法第四十四条第四项"
    result = extract_provisions(test_text)
    print(f"测试: {test_text}")
    for r in result:
        print(f"  提取到: {r}")
