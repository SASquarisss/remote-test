"""
法条引用正则提取器

用途：作为 LLM 提取的第一道防线，从原始文本中提取显式法条引用。
对于隐式引用（法官未明确写出法条名称和条号），需依赖 LLM 推理或案件类型映射补充。

支持格式：
- 《中华人民共和国XX法》第一百二十条之一第三款第四项
- XX法第一百二十条（简写）
- 最高人民法院关于...的解释/规定/批复
- 依据/根据/按照《XX法》（无条号时仅提取法名）
"""

import re
from typing import List, Dict

# 中文数字
_CN_NUMS = '一二三四五六七八九十百千万'
_CN_NUM_PATTERN = f'[{_CN_NUMS}\\d]+'

# 核心正则模式集
_PATTERNS = [
    # A. 完整格式：《中华人民共和国XXX法》第一百二十条(之一)(第三款)(第四项)
    (
        re.compile(
            r'《(中华人民共和国[^》《]{2,35}?)》'
            r'笭(' + _CN_NUM_PATTERN + r')条'
            r'(之一)?'
            r'(?:笭([' + _CN_NUMS + r']+)款)?'
            r'(?:笭([' + _CN_NUMS + r']+)项)?'
        ),
        'full'
    ),
    # B. 简写格式：XX法第一百二十条(之一)(第三款)(第四项)
    # 排除已匹配完整格式的前缀
    (
        re.compile(
            r'(?<!中华人民共和国)([一-龥]{1,8}法)'
            r'笭(' + _CN_NUM_PATTERN + r')条'
            r'(之一)?'
            r'(?:笭([' + _CN_NUMS + r']+)款)?'
            r'(?:笭([' + _CN_NUMS + r']+)项)?'
        ),
        'short'
    ),
    # C. 司法解释/规定：最高人民法院/最高检 关于...的解释/规定/批复
    (
        re.compile(
            r'《(最高人民(?:法院|检察院)[^》《]{5,55}?)》'
            r'(?:笭(' + _CN_NUM_PATTERN + r')条)?'
        ),
        'judicial_interp'
    ),
    # D. 无书名号的司法解释：最高人民法院关于...的解释
    (
        re.compile(
            r'(最高人民(?:法院|检察院)关于'
            r'[^，。、]{5,50}?的(?:解释|规定|批复))'
        ),
        'judicial_interp_naked'
    ),
    # E. 依据式引用（无条号）：依据/根据/按照《XX法》
    (
        re.compile(r'[依根按照]《([^》《]{3,35}?)》'),
        'citation_no_article'
    ),
]


def _normalize_statute_name(name: str) -> str:
    """标准化法典名称"""
    name = name.strip()
    # 如果已经有《》则不加
    if name.startswith('《') and name.endswith('》'):
        return name
    # 补全《中华人民共和国》前缀
    if not name.startswith('中华人民共和国'):
        # 短名如 刑法、民法典 等保留原样
        return name
    return f'《{name}》'


def extract_legal_provisions(text: str) -> List[Dict[str, str]]:
    """
    从文本中提取法条引用。

    Args:
        text: 原始文本（可包含 HTML 标签）

    Returns:
        List[{"statute": str, "article": str, "paragraph": str}]
        article 和 paragraph 可能为空字符串（对于无条号的司法解释或泛指引用）
    """
    if not text:
        return []

    # 清理 HTML
    clean = text.replace('<p>', '').replace('</p>', '\n') \
                .replace('<br/>', '\n').replace('&nbsp;', ' ')

    results = []
    seen = set()

    for pattern, ptype in _PATTERNS:
        for match in pattern.finditer(clean):
            if ptype == 'full':
                statute = match.group(1).strip()
                article = match.group(2) + (match.group(3) or '')
                paragraph = f'笭{match.group(4)}款' if match.group(4) else ''
                item = f'笭{match.group(5)}项' if match.group(5) else ''
                para_full = paragraph + (f',{item}' if item and paragraph else item)

                key = (statute, article, para_full)
                if key not in seen and article:
                    seen.add(key)
                    results.append({
                        'statute': f'《中华人民共和国{statute}》',
                        'article': article,
                        'paragraph': para_full
                    })

            elif ptype == 'short':
                statute = match.group(1).strip()
                article = match.group(2) + (match.group(3) or '')
                paragraph = f'笭{match.group(4)}款' if match.group(4) else ''
                item = f'笭{match.group(5)}项' if match.group(5) else ''
                para_full = paragraph + (f',{item}' if item and paragraph else item)

                key = (statute, article, para_full)
                if key not in seen and article:
                    seen.add(key)
                    results.append({
                        'statute': statute,
                        'article': article,
                        'paragraph': para_full
                    })

            elif ptype == 'judicial_interp':
                name = match.group(1).strip()
                article = match.group(2) or ''
                key = (name, article, '')
                if key not in seen:
                    seen.add(key)
                    results.append({
                        'statute': f'《{name}》',
                        'article': article,
                        'paragraph': ''
                    })

            elif ptype == 'judicial_interp_naked':
                name = match.group(1).strip()
                key = (name, '', '')
                if key not in seen:
                    seen.add(key)
                    results.append({
                        'statute': name,
                        'article': '',
                        'paragraph': ''
                    })

            elif ptype == 'citation_no_article':
                statute = match.group(1).strip()
                key = (statute, '', '')
                if key not in seen:
                    seen.add(key)
                    results.append({
                        'statute': f'《{statute}》',
                        'article': '',
                        'paragraph': ''
                    })

    return results


def merge_provisions(llm_provisions: List[Dict], regex_provisions: List[Dict]) -> List[Dict]:
    """
    合并 LLM 提取结果与正则提取结果，去重。

    策略：
    - 以 LLM 结果为主（它更准确）
    - 正则结果作为补充，仅添加 LLM 未覆盖的条目
    - 去重键：(statute, article, paragraph) 三元组
    """
    if not llm_provisions:
        return regex_provisions
    if not regex_provisions:
        return llm_provisions

    merged = list(llm_provisions)
    seen = {
        (p.get('statute', ''), p.get('article', ''), p.get('paragraph', ''))
        for p in llm_provisions
    }

    for p in regex_provisions:
        key = (p.get('statute', ''), p.get('article', ''), p.get('paragraph', ''))
        if key not in seen:
            seen.add(key)
            merged.append(p)

    return merged


if __name__ == '__main__':
    # 简单测试
    test_text = (
        '根据《中华人民共和国刑法》第二百三十六条之一第三款的规定，'
        '以及《最高人民法院关于处理自首和立功若干具体问题的意见》第四条的规定，'
        '同时参照民法典第五百零五条第二款。'
    )
    provisions = extract_legal_provisions(test_text)
    for p in provisions:
        print(f"{p['statute']} 第{p['article']}条{p['paragraph']}")
