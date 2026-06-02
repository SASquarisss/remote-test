# 塔罗资源 Schema 规范

## 1. 文档目标

本文档定义四类核心资源文件的正式规范：

1. `card.yaml`
2. `spread.yaml`
3. `position.yaml`
4. `manifest.yaml`

这三类 schema 用于支撑：

1. 图片资源包管理
2. 牌义资源包管理
3. 牌阵资源包管理
4. 后续自动构筑占卜 Prompt

## 2. 通用约定

### 2.1 文件格式

统一使用 YAML 1.2。

### 2.2 编码

统一使用 UTF-8。

### 2.3 命名规则

建议：

1. 文件名使用 kebab-case 或与 ID 一致
2. `card.yaml` 文件可直接以 `canonical_card_id` 命名
3. `spread.yaml` 文件可直接以 `spread_id` 命名
4. `manifest.yaml` 固定为包根目录下的 `manifest.yaml`

### 2.4 通用字段约束

1. 所有 `id` 字段必须全局稳定
2. 所有 `version` 字段使用语义化版本或 pack 版本标识
3. 所有 `locale` 字段使用 `zh-CN`、`en-US` 这类规范值
4. 可选字段若为空，建议直接省略，而不是写空字符串

## 3. `card.yaml` 正式 Schema

### 3.1 用途

`card.yaml` 用于定义一张牌在某一牌义体系下的结构化语义。

注意：

1. `card.yaml` 不保存图片二进制
2. `card.yaml` 不保存抽牌结果
3. `card.yaml` 不直接表达具体牌阵位置

### 3.2 必填字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema` | string | 固定值，建议 `tarot.card.v1` |
| `canonical_card_id` | string | 全局稳定卡牌 ID |
| `names` | object | 多语言名称 |
| `arcana` | string | `major` 或 `minor` |
| `order` | number | 牌在牌组中的排序 |
| `orientation_profiles` | object | 正位/逆位结构 |
| `prompt_fragments` | object | 可用于 Prompt 的文本片段 |

### 3.3 推荐字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `suit` | string | 小阿尔卡那花色 |
| `rank` | object | 数字或宫廷牌位阶 |
| `element` | string | 元素属性 |
| `astrology` | object | 占星信息 |
| `numerology` | object | 数字学信息 |
| `tags` | string[] | 标签索引 |
| `symbolism` | object | 视觉符号解释 |
| `domain_meanings` | object | 分主题含义 |
| `combinations` | object | 联动建议 |
| `source_refs` | object[] | 来源追踪 |

### 3.4 正式结构

```yaml
schema: tarot.card.v1
canonical_card_id: major.00.fool
pack_id: rws-core-v1
locale: zh-CN
version: 1

names:
  zh-CN:
    display: 愚者
    aliases:
      - 愚人
  en-US:
    display: The Fool
    aliases:
      - Fool

arcana: major
order: 0

rank:
  code: "00"
  label: fool

tags:
  - new_beginning
  - leap_of_faith
  - innocence

element: air

astrology:
  planet: uranus
  zodiac: null

numerology:
  number: 0
  notes:
    zh-CN: 象征无限可能与未定形状态

symbolism:
  visual_points:
    - id: cliff
      label: 悬崖
      meaning: 象征未知边界与跃迁
    - id: white_dog
      label: 白犬
      meaning: 本能提醒与陪伴
    - id: white_rose
      label: 白玫瑰
      meaning: 纯粹与开放

orientation_profiles:
  upright:
    keywords:
      - 开始
      - 自由
      - 冒险
    core_meaning:
      zh-CN: 新旅程即将展开，重点在于信任与尝试
    domain_meanings:
      love:
        zh-CN: 感情可能开启新的阶段，也可能遇见全新的连接
      career:
        zh-CN: 适合尝试新方向，但需要避免理想化
      growth:
        zh-CN: 你需要允许自己进入未知，并从经验中学习
    cautions:
      zh-CN:
        - 避免毫无准备地冲动决定
        - 留意理想化倾向

  reversed:
    keywords:
      - 冲动
      - 迷失
      - 逃避
    core_meaning:
      zh-CN: 开始的力量被犹豫、混乱或轻率所扭曲
    domain_meanings:
      love:
        zh-CN: 关系推进中可能存在不成熟与不稳定
      career:
        zh-CN: 需要先校准目标，再投入行动
      growth:
        zh-CN: 与其盲跳，不如先识别自己真正的恐惧
    cautions:
      zh-CN:
        - 不要把自由误当成逃避
        - 不要用冲动掩盖不确定

prompt_fragments:
  concise:
    zh-CN: 愚者象征开始、尝试、迈入未知
  mystical:
    zh-CN: 命运的门槛已经显现，你正站在跃入新旅程的边缘
  practical:
    zh-CN: 这是一个适合尝试但必须保持觉察的阶段

combinations:
  supports:
    - major.01.magician
    - major.17.star
  tensions:
    - major.15.devil
    - major.16.tower

source_refs:
  - source_id: rws-pictorial-key
    kind: public_domain_text
    notes: 基于公版原始资料整理

quality:
  reviewed: true
  confidence: high
```

### 3.5 校验规则

建议强校验：

1. `schema` 必须为 `tarot.card.v1`
2. `canonical_card_id` 不可为空
3. `arcana=major` 时，`suit` 必须省略或为 `null`
4. `arcana=minor` 时，`suit` 必填
5. `orientation_profiles.upright` 必填
6. `orientation_profiles.reversed` 必填
7. `keywords` 至少 1 个
8. `prompt_fragments.concise` 必填

## 4. `spread.yaml` 正式 Schema

### 4.1 用途

`spread.yaml` 用于定义一种牌阵的结构、牌位顺序、布局与综合分析策略。

### 4.2 必填字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema` | string | 固定值，建议 `tarot.spread.v1` |
| `spread_id` | string | 牌阵 ID |
| `pack_id` | string | 所属 spread pack |
| `name` | object | 多语言名称 |
| `card_count` | number | 抽牌数量 |
| `positions` | object[] | 牌位列表 |

### 4.3 推荐字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `subtitle` | object | 副标题 |
| `description` | object | 描述 |
| `tags` | string[] | 场景标签 |
| `layout` | object | 前端布局建议 |
| `reading_strategy` | object | 汇总与生成策略 |
| `availability` | object | 是否为高级牌阵 |

### 4.4 正式结构

```yaml
schema: tarot.spread.v1
spread_id: three-card
pack_id: core-v1
locale: zh-CN
version: 1

name:
  zh-CN: 三牌阵
  en-US: Three Card Spread

subtitle:
  zh-CN: 过去、现在、未来
  en-US: Past, Present, Future

description:
  zh-CN: 最适合日常问题和快速指引的基础牌阵
  en-US: A simple spread for daily questions and quick guidance

card_count: 3

tags:
  - beginner
  - daily
  - quick-guidance

availability:
  premium_reserved: false
  visible_by_default: true

layout:
  template: row-3
  slot_order:
    - 0
    - 1
    - 2

positions:
  - slot: 0
    position_id: past
    name:
      zh-CN: 过去
      en-US: Past
    description:
      zh-CN: 影响现在的情况和经历
      en-US: Influences and past experiences affecting the present
    interpretation_weight: 0.28

  - slot: 1
    position_id: present
    name:
      zh-CN: 现在
      en-US: Present
    description:
      zh-CN: 当前的状态和挑战
      en-US: Current state and challenge
    interpretation_weight: 0.40

  - slot: 2
    position_id: future
    name:
      zh-CN: 未来
      en-US: Future
    description:
      zh-CN: 可能的发展和建议
      en-US: Possible development and advice
    interpretation_weight: 0.32

reading_strategy:
  synthesis_template: linear-timeline
  recommend_sections:
    - card_readings
    - overall_analysis
    - action_advice
    - long_term_advice
  advice_weight: medium
  timing_enabled: true

ui_hints:
  animate_draw_order: true
  highlight_current_slot: true
```

### 4.5 校验规则

建议强校验：

1. `schema` 必须为 `tarot.spread.v1`
2. `spread_id` 不可为空
3. `card_count` 必须等于 `positions` 数量
4. `slot` 必须从 `0` 连续递增
5. `position_id` 不可重复
6. `interpretation_weight` 建议总和为 `1.0`

## 5. `position.yaml` 正式 Schema

### 5.1 用途

`position.yaml` 用于定义可复用的位置 archetype，例如：

1. `past`
2. `present`
3. `future`
4. `obstacle`
5. `outcome`

它解决的是“一个位置本身怎么解释”，而不是“一个牌阵如何排布”。

### 5.2 必填字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema` | string | 固定值，建议 `tarot.position.v1` |
| `position_id` | string | 位置 ID |
| `pack_id` | string | 所属 spread pack |
| `name` | object | 多语言名称 |
| `description` | object | 多语言描述 |
| `interpretation_role` | string | 位置语义角色 |

### 5.3 推荐字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `aliases` | string[] | 别名 |
| `keywords` | string[] | 关键词 |
| `focus` | object | 关注维度 |
| `prompt_fragments` | object | Prompt 片段 |
| `reading_hints` | object | 解读提示 |
| `ui_hints` | object | UI 展示提示 |
| `quality` | object | 质量标记 |

### 5.4 正式结构

```yaml
schema: tarot.position.v1
position_id: past
pack_id: core-v1
locale: zh-CN
version: 1

name:
  zh-CN: 过去
  en-US: Past

aliases:
  - background
  - prior_influence

description:
  zh-CN: 影响当前问题形成的背景、经历与既有能量
  en-US: Background, prior experience, and past influences shaping the question

interpretation_role: timeline_past

keywords:
  - 背景
  - 既往影响
  - 形成原因

focus:
  question_aspect: background
  time_dimension: past
  advice_weight: low

prompt_fragments:
  concise:
    zh-CN: 过去位用于说明问题的形成背景与残留影响
```

### 5.5 校验规则

建议强校验：

1. `schema` 必须为 `tarot.position.v1`
2. `position_id` 不可为空
3. `name.zh-CN` 至少存在一个主展示名称
4. `description.zh-CN` 不可为空
5. `interpretation_role` 必填
6. `prompt_fragments.concise` 建议必填

## 6. `manifest.yaml` 正式 Schema

### 6.1 用途

`manifest.yaml` 用于描述某个资源包的元信息。

它可用于：

1. `image_pack`
2. `meaning_pack`
3. `spread_pack`

### 6.2 必填字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema` | string | 固定值，建议 `tarot.manifest.v1` |
| `pack_type` | string | `image_pack` / `meaning_pack` / `spread_pack` |
| `pack_id` | string | 包 ID |
| `version` | string or number | 包版本 |
| `name` | object | 多语言名称 |
| `license` | object | 授权信息 |
| `source` | object | 来源信息 |

### 6.3 推荐字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `compatibility` | object | 与其他包的兼容性 |
| `stats` | object | 资源统计 |
| `build` | object | 导入或构建信息 |
| `locales` | string[] | 支持语言 |
| `tags` | string[] | 标签 |

### 6.4 正式结构

```yaml
schema: tarot.manifest.v1
pack_type: meaning_pack
pack_id: rws-core-v1
version: "1.0.0"

name:
  zh-CN: 韦特基础牌义包
  en-US: RWS Core Meaning Pack

description:
  zh-CN: 基于 RWS 体系整理的基础结构化牌义资源
  en-US: Structured core meanings based on the RWS system

locales:
  - zh-CN
  - en-US

tags:
  - rws
  - core
  - structured

license:
  license_type: mixed
  commercial_use_allowed: false
  attribution_required: true
  notes:
    zh-CN: 包内不同资源可能对应不同来源与授权，需结合 source_refs 使用

source:
  primary_source_id: rws-pictorial-key
  source_urls:
    - https://example.com/source-1
  provenance:
    zh-CN: 基于公版文本与人工结构化整理

compatibility:
  recommended_image_packs:
    - rws-public-domain
  recommended_spread_packs:
    - core-v1
  required_schema_versions:
    card: tarot.card.v1
    spread: tarot.spread.v1

stats:
  total_cards: 78
  major_arcana: 22
  minor_arcana: 56
  spreads: 0
  positions: 0

build:
  imported_at: "2026-06-02T10:00:00Z"
  built_by: manual-curation
  tool_version: "1.0.0"

quality:
  reviewed: true
  confidence: high
```

### 6.5 针对不同 pack 类型的补充字段

#### 6.5.1 `image_pack`

建议增加：

```yaml
asset_spec:
  file_format: jpg
  thumbnail_format: webp
  has_transparency: false
  full_dir: full/
  thumbnail_dir: thumbnails/
  naming_rule: "{canonical_card_id}.jpg"
```

#### 6.5.2 `meaning_pack`

建议增加：

```yaml
meaning_spec:
  card_schema: tarot.card.v1
  includes_symbolism: true
  includes_domain_meanings: true
  includes_prompt_fragments: true
```

#### 6.5.3 `spread_pack`

建议增加：

```yaml
spread_spec:
  spread_schema: tarot.spread.v1
  includes_layouts: true
  includes_position_templates: true
```

### 6.6 校验规则

建议强校验：

1. `schema` 必须为 `tarot.manifest.v1`
2. `pack_type` 必须是以下之一：
   - `image_pack`
   - `meaning_pack`
   - `spread_pack`
3. `pack_id` 必须全局唯一
4. `license` 必填
5. `source.primary_source_id` 必填

## 7. 推荐目录与文件对应关系

### 7.1 图片包

```text
resources/image_packs/rws-public-domain/
├── manifest.yaml
├── full/
│   ├── major.00.fool.jpg
│   └── ...
└── thumbnails/
    ├── major.00.fool.webp
    └── ...
```

### 7.2 牌义包

```text
resources/meaning_packs/rws-core-v1/
├── manifest.yaml
├── cards/
│   ├── major/
│   │   ├── major.00.fool.card.yaml
│   │   └── ...
│   └── minor/
│       └── ...
├── positions/
└── synthesis/
```

### 7.3 牌阵包

```text
resources/spread_packs/core-v1/
├── manifest.yaml
├── positions/
│   ├── past.yaml
│   ├── present.yaml
│   └── future.yaml
└── spreads/
    ├── three-card.spread.yaml
    └── celtic-cross.spread.yaml
```

## 8. 最小可行落地方案

如果你要尽快开始整理资源，建议先只做以下最小集合：

1. 一份 `image_pack manifest`
2. 一份 `meaning_pack manifest`
3. 一份 `spread_pack manifest`
4. `22` 张大阿尔卡那 `card.yaml`
5. `three-card.spread.yaml`

## 9. 推荐优先级

优先顺序建议：

1. 先定 `manifest.yaml`
2. 再定 `card.yaml`
3. 再定 `position.yaml`
4. 最后定 `spread.yaml`

原因：

1. `manifest.yaml` 决定包级别组织方式
2. `card.yaml` 决定资源主干
3. `position.yaml` 决定位置语义复用方式
4. `spread.yaml` 建立具体解读编排层

## 10. 后续延展

基于这套 schema，后续可以继续增加：

1. `reading_style.yaml`
2. `prompt_template.yaml`
3. `source_ref.yaml`

但在当前阶段，不建议过早增加文件种类，避免结构过重。
