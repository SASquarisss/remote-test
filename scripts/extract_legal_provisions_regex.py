"""
法条引用正则提取器 v2.2

与 v1 的关键改进：
1. 修复 typo：笭 → 第
2. 支持同法多条：《XX法》第A条、第B条
3. 扩大法名匹配范围到 80 字符（应对未清理干净的 HTML 标签）
4. 全面清理 HTML 标签
5. 排除法条代词（本法、该法、此法等）
6. 支持公约/条例/规定等后缀识别
7. 修复 Unicode 范围字面量（一-龥）

用途：作为 LLM 提取的第一道防线，从原始文本中提取显式法条引用。
对于隐式引用（法官未明确写出法条名称和条号），需依赖 LLM 推理或案件类型映射补充。

支持格式：
- 《中华人民共和国XX法》第一百二十条之一第三款第四项
- XX法第一百二十条（简写）
- 最高人民法院关于...的解释/规定/批复
- 依据/根据/按照《XX法》（无条号时仅提取法名）
- 《XX公约》《XX条例》
"""

import re
from typing import List, Dict

# 中文数字
_CN_NUMS = '零一二三四五六七八九十百千万'
_CN_NUM_PATTERN = f'[{_CN_NUMS}\\d]+'

# 需要排除的法条代词（避免误匹配）
_PRONOUN_LAWS = {'本法', '该法', '此法', '其法', '某法', '上法', '前法', '后法'}

# 核心正则模式集
_PATTERNS = [
    # A. 完整格式：《中华人民共和国XXX法/条例/规定》第...条...
    #    支持同法多条
    (
        re.compile(
            r'《(中华人民共和国[^》《]{2,80}?)》'
            r'((?:第' + _CN_NUM_PATTERN + r'条(?:之一)?'
            r'(?:第[' + _CN_NUMS + r']+款)?'
            r'(?:第[' + _CN_NUMS + r']+项)?'
            r'[、，,；;]*'
            r'[《》]*第?)*)'
        ),
        'full_multi'
    ),
    # B. 简写格式：XX法/法典/条例 第...条...
    #    排除法条代词和"中华人民共和国"前缀
    #    修复： statute 前加非中文字符限制，避免"参照民法典"误匹配"照民法典"
    (
        re.compile(
            r'(?:^|[^\u4e00-\u9fa5])(?<!中华人民共和国)([^条款项' + _CN_NUMS + r'\d照参根依按]{1,20}?(?:法典|条例|规定|公约|办法|法))(?!院)'
            r'((?:第?' + _CN_NUM_PATTERN + r'条(?:之一)?'
            r'(?:第[' + _CN_NUMS + r']+款)?'
            r'(?:第[' + _CN_NUMS + r']+项)?'
            r'[、，,；;]*第?)*)'
        ),
        'short_multi'
    ),
    # C. 司法解释/规定：最高人民法院/最高检 关于...的解释/规定/批复/纪要
    #    修复：允许《》与条号之间有最多40个非《》字符（应对"该解释第十七条"）
    (
        re.compile(
            r'《(最高人民(?:法院|检察院)[^》《]{5,80}?)》'
            r'[^《》]{0,40}?(?:第(' + _CN_NUM_PATTERN + r')条(?:规定)?)'
        ),
        'judicial_interp'
    ),
    # D. 无书名号的司法解释：最高人民法院关于...的解释
    #    通过 seen 去重处理与 C 的重叠
    (
        re.compile(
            r'(最高人民(?:法院|检察院)关于'
            r'[^，。、]{5,50}?的(?:解释|规定|批复|纪要))'
        ),
        'judicial_interp_naked'
    ),
    # E. 依据式引用（无条号）：依据/根据/按照《XX法》
    (
        re.compile(r'[依根按照适用]《([^》《]{3,45}?)》'),
        'citation_no_article'
    ),
]


def _parse_multi_articles(text: str, statute: str) -> List[Dict[str, str]]:
    """
    从同法多条字符串中拆出单条。
    输入如："第69条、第223条、第385条第1款"
    """
    results = []
    parts = re.split(r'[、，,；;]', text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.search(r'第(' + _CN_NUM_PATTERN + r')条(之一)?', part)
        if not m:
            continue
        article = m.group(1) + ('条之一' if m.group(2) else '')
        para_m = re.search(r'第([' + _CN_NUMS + r']+)款', part)
        paragraph = f'第{para_m.group(1)}款' if para_m else ''
        item_m = re.search(r'第([' + _CN_NUMS + r']+)项', part)
        item = f'第{item_m.group(1)}项' if item_m else ''
        para_full = paragraph + (f'，{item}' if item and paragraph else item)
        results.append({
            'statute': statute,
            'article': article,
            'paragraph': para_full
        })
    return results


def extract_legal_provisions(text: str) -> List[Dict[str, str]]:
    """
    从文本中提取法条引用。

    Args:
        text: 原始文本（可包含 HTML 标签）

    Returns:
        List[{"statute": str, "article": str, "paragraph": str}]
        article 和 paragraph 可能为空字符串
    """
    if not text:
        return []

    # 全面清理 HTML 标签
    clean = re.sub(r'<[^>]+>', '', text)
    clean = clean.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>')
    clean = clean.replace('&amp;', '&')

    results = []
    seen = set()

    for pattern, ptype in _PATTERNS:
        for match in pattern.finditer(clean):
            if ptype == 'full_multi':
                statute_raw = match.group(1).strip()
                # 避免重复前缀
                if statute_raw.startswith('中华人民共和国'):
                    statute = f'《{statute_raw}》'
                else:
                    statute = f'《中华人民共和国{statute_raw}》'
                articles_text = match.group(2) or ''
                for p in _parse_multi_articles(articles_text, statute):
                    key = (p['statute'], p['article'], p['paragraph'])
                    if key not in seen and p['article']:
                        seen.add(key)
                        results.append(p)

            elif ptype == 'short_multi':
                statute = match.group(1).strip()
                # 清洗：去掉开头标点、去掉"的"前缀
                statute = re.sub(r'^[^\w\u4e00-\u9fa5]+', '', statute)
                if statute.startswith('的'):
                    statute = statute[1:]
                if not statute or len(statute) < 2:
                    continue
                # 排除法条代词（支按带前缀如"有本法"、"对于本法"）
                if any(statute.endswith(p) for p in _PRONOUN_LAWS):
                    continue
                articles_text = match.group(2) or ''
                for p in _parse_multi_articles(articles_text, statute):
                    key = (p['statute'], p['article'], p['paragraph'])
                    if key not in seen and p['article']:
                        seen.add(key)
                        results.append(p)

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
                # 跳过被《》包围的匹配，避免与模式 C 重叠
                if '《' in name or '》' in name:
                    continue
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
                # 排除司法解释类，应由模式 C/D 处理
                if statute.endswith(('解释', '规定', '纪要', '批复')):
                    continue
                key = (statute, '', '')
                if key not in seen:
                    seen.add(key)
                    results.append({
                        'statute': f'《{statute}》',
                        'article': '',
                        'paragraph': ''
                    })

    # 后处理去重：对于同一法条的带《》与不带《》版本，优先保留带条号和带书名号的
    results = _deduplicate_provisions(results)
    return results


def _deduplicate_provisions(results: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    后处理去重。
    对于 statute 除去《》后相同的条目，优先保留：
    1. 带条号的
    2. 带书名号的
    此外，如果一个不带《》的 statute 被某个带《》的 statute 包含，则删除。
    """
    best = {}
    for r in results:
        norm_statute = r['statute'].replace('《', '').replace('》', '')
        key = (norm_statute, r['article'], r['paragraph'])
        if key not in best:
            best[key] = r
            continue
        existing = best[key]
        # 保留带书名号的
        if '《' not in existing['statute'] and '《' in r['statute']:
            best[key] = r

    # 第二轮：删除被带《》版本包含的不带《》版本
    final = []
    c_statutes = [
        r['statute'].replace('《', '').replace('》', '')
        for r in best.values() if '《' in r['statute']
    ]
    for r in best.values():
        if '《' not in r['statute']:
            if any(r['statute'] in c for c in c_statutes):
                continue
        final.append(r)
    return final


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
