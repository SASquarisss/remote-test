# `position.yaml` 正式 Schema

## 1. 目标

`position.yaml` 用于定义“牌阵中的一个位置 archetype”，例如：

1. `past`
2. `present`
3. `future`
4. `obstacle`
5. `outcome`

它的作用是把“位置语义”从具体牌阵里抽离出来，便于多个牌阵复用同一位置规则。

## 2. 为什么单独拆 `position.yaml`

如果把所有位置说明都直接写死在 `spread.yaml` 中，会出现三个问题：

1. 同义位置在不同牌阵中重复维护
2. 后续做多语言或多风格解读时难以统一
3. Prompt 构建时无法稳定复用位置语义

因此建议：

1. `spread.yaml` 负责“牌阵结构和顺序”
2. `position.yaml` 负责“位置本身的解释规则”

## 3. 文件位置建议

推荐目录：

```text
tarot/resources/spread_packs/<spread_pack_id>/positions/
```

例如：

```text
tarot/resources/spread_packs/core-v1/positions/past.position.yaml
tarot/resources/spread_packs/core-v1/positions/present.position.yaml
tarot/resources/spread_packs/core-v1/positions/future.position.yaml
```

## 4. 正式 Schema

### 4.1 必填字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `schema` | string | 固定值，建议 `tarot.position.v1` |
| `position_id` | string | 位置 ID |
| `pack_id` | string | 所属 spread pack |
| `name` | object | 多语言名称 |
| `description` | object | 多语言描述 |
| `interpretation_role` | string | 位置语义角色 |

### 4.2 推荐字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `aliases` | string[] | 同义位置别名 |
| `keywords` | string[] | 位置关键词 |
| `focus` | object | 当前位置关注点 |
| `prompt_fragments` | object | Prompt 片段 |
| `reading_hints` | object | 解读提示 |
| `ui_hints` | object | 前端展示提示 |
| `quality` | object | 质量标记 |

## 5. 字段说明

### 5.1 `position_id`

要求：

1. 全局稳定
2. 使用英文小写 slug
3. 与具体牌阵无关

推荐示例：

1. `past`
2. `present`
3. `future`
4. `obstacle`
5. `foundation`
6. `outcome`
7. `self`
8. `environment`

### 5.2 `interpretation_role`

推荐枚举：

1. `timeline_past`
2. `timeline_present`
3. `timeline_future`
4. `challenge`
5. `root_cause`
6. `guidance`
7. `external_influence`
8. `outcome`

它的作用是帮助 Prompt 构建器识别这个位置在解读中的功能。

### 5.3 `focus`

建议拆为：

1. `question_aspect`
2. `time_dimension`
3. `advice_weight`

例如：

1. `question_aspect: background`
2. `time_dimension: past`
3. `advice_weight: low`

## 6. 正式示例

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

reading_hints:
  emphasize:
    zh-CN:
      - 用于解释现状是如何发展而来
      - 强调已发生事件对当下的残留影响
  avoid:
    zh-CN:
      - 不要把过去位直接解读成未来结论
      - 不要过度放大单一事件的绝对影响

prompt_fragments:
  concise:
    zh-CN: 过去位用于说明问题的形成背景与残留影响
  mystical:
    zh-CN: 过去的能量并未完全散去，它仍在今天的局势中投下阴影

ui_hints:
  icon: hourglass
  theme_tone: reflective

quality:
  reviewed: true
  confidence: high
```

## 7. 校验规则

建议强校验：

1. `schema` 必须为 `tarot.position.v1`
2. `position_id` 不可为空
3. `name.zh-CN` 至少存在一个主展示名称
4. `description.zh-CN` 不可为空
5. `interpretation_role` 必填
6. `prompt_fragments.concise` 建议必填

## 8. 与 `spread.yaml` 的关系

推荐在 `spread.yaml` 中只保留：

1. `slot`
2. `position_id`
3. 可选覆盖字段

例如：

```yaml
positions:
  - slot: 0
    position_id: past
    interpretation_weight: 0.28
  - slot: 1
    position_id: present
    interpretation_weight: 0.40
  - slot: 2
    position_id: future
    interpretation_weight: 0.32
```

运行时由后端根据 `position_id` 读取对应 `position.yaml`，再合并进 `reading_context`。

## 9. 最小建议集合

在 `core-v1` 里，建议优先建立以下位置文件：

1. `past`
2. `present`
3. `future`
4. `obstacle`
5. `outcome`

这 5 个位置足够支撑首批常见牌阵。
