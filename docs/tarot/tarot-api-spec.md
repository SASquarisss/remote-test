# 塔罗占卜 API 字段定义文档（Mock V1）

## 1. 文档说明

本文档用于约定塔罗占卜网站首版 Demo 的前后端接口字段定义，适用于以下前提：

1. 匿名单次体验
2. 不需要账号
3. 不记录历史
4. 暂不使用数据库
5. 后端会话仅保存在服务内存中

Mock 服务的目标不是完整业务实现，而是为前端联调提供稳定的请求、响应和错误码契约。

## 2. 通用约定

### 2.1 Base URL
默认前缀：

`/api/v1`

### 2.2 Content-Type

请求和响应默认使用：

`application/json`

### 2.3 时间格式

所有时间字段统一使用 ISO 8601 字符串，例如：

`2026-06-02T12:00:00Z`

### 2.4 统一错误结构

所有业务错误统一返回：

```json
{
  "error": {
    "code": "QUESTION_TOO_SHORT",
    "message": "问题至少需要 6 个字符"
  }
}
```

字段说明：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `error.code` | string | 是 | 稳定错误码，前端按此分支处理 |
| `error.message` | string | 是 | 可直接展示给用户的错误文案 |

### 2.5 通用状态枚举

| 枚举值 | 说明 |
| --- | --- |
| `drawing` | 抽牌进行中 |
| `draw_complete` | 已抽完所有牌 |
| `reading_ready` | 解读结果已生成 |
| `error` | 会话异常 |

### 2.6 通用正逆位枚举

| 枚举值 | 说明 |
| --- | --- |
| `upright` | 正位 |
| `reversed` | 逆位 |

## 3. 公共数据结构

### 3.1 SpreadSummary

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 牌阵 ID |
| `name` | string | 是 | 牌阵名称 |
| `subtitle` | string | 是 | 牌阵副标题 |
| `description` | string | 是 | 牌阵简介 |
| `card_count` | number | 是 | 所需抽牌数 |
| `premium_reserved` | boolean | 是 | 是否预留为高级功能 |

### 3.2 SpreadPosition

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `index` | number | 是 | 从 0 开始的牌位序号 |
| `key` | string | 是 | 牌位代码 |
| `name` | string | 是 | 牌位名称 |
| `description` | string | 是 | 牌位含义 |

### 3.3 TarotCardMeta

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 卡牌 ID |
| `name_cn` | string | 是 | 中文名 |
| `arcana_type` | string | 是 | `major` 或 `minor` |
| `suit` | string or null | 否 | 花色，主牌可为空 |
| `element` | string or null | 否 | 元素，如 `water` / `air` |

### 3.4 DrawnCard

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `position_index` | number | 是 | 当前牌位索引 |
| `position_name` | string | 是 | 当前牌位名称 |
| `card` | object | 是 | 牌基础信息，结构见 `TarotCardMeta` |
| `orientation` | string | 是 | `upright` 或 `reversed` |
| `cover_image_url` | string | 是 | 牌背图 URL |
| `face_image_url` | string | 是 | 牌面图 URL |

### 3.5 ReadingCard

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `position_name` | string | 是 | 牌位名称 |
| `card_name` | string | 是 | 卡牌名称 |
| `orientation` | string | 是 | 正逆位 |
| `core_meaning` | string | 是 | 核心关键词 |
| `analysis` | string | 是 | 结合问题的解读 |

## 4. 接口定义

### 4.1 获取牌阵列表

接口：

`GET /api/v1/spreads`

用途：

用于首页展示可选牌阵。

响应字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `items` | SpreadSummary[] | 是 | 牌阵列表 |

成功示例：

```json
{
  "items": [
    {
      "id": "three-card",
      "name": "三牌阵",
      "subtitle": "过去、现在、未来",
      "description": "最简单直接的牌阵，适合日常问题和快速指引",
      "card_count": 3,
      "premium_reserved": false
    }
  ]
}
```

错误码：

当前 mock 场景下无业务错误，异常时统一返回：

| HTTP 状态码 | 错误码 | 说明 |
| --- | --- | --- |
| 500 | `INTERNAL_ERROR` | 服务内部异常 |

### 4.2 获取牌阵详情

接口：

`GET /api/v1/spreads/{spreadId}`

路径参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `spreadId` | string | 是 | 牌阵 ID |

响应字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `id` | string | 是 | 牌阵 ID |
| `name` | string | 是 | 牌阵名称 |
| `subtitle` | string | 是 | 牌阵副标题 |
| `description` | string | 是 | 牌阵简介 |
| `card_count` | number | 是 | 抽牌数量 |
| `premium_reserved` | boolean | 是 | 是否预留付费 |
| `positions` | SpreadPosition[] | 是 | 牌位定义 |

错误码：

| HTTP 状态码 | 错误码 | 说明 |
| --- | --- | --- |
| 404 | `SPREAD_NOT_FOUND` | 牌阵不存在 |
| 500 | `INTERNAL_ERROR` | 服务内部异常 |

### 4.3 创建占卜会话

接口：

`POST /api/v1/divinations`

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `question` | string | 是 | 用户输入的问题 |
| `spread_id` | string | 是 | 牌阵 ID |

请求规则：

1. `question` 去除首尾空格后不能为空
2. `question` 最少 6 个字符
3. `question` 最多 120 个字符
4. `spread_id` 必须存在

响应字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | string | 是 | 本次匿名会话 ID |
| `status` | string | 是 | 固定为 `drawing` |
| `question` | string | 是 | 清洗后的问题文本 |
| `spread` | object | 是 | 当前牌阵摘要 |
| `positions` | SpreadPosition[] | 是 | 当前牌阵的牌位定义 |
| `remaining_count` | number | 是 | 剩余待抽牌数 |
| `expires_at` | string | 是 | 会话过期时间 |

成功示例：

```json
{
  "session_id": "div_12345678",
  "status": "drawing",
  "question": "我的感情发展会如何？",
  "spread": {
    "id": "three-card",
    "name": "三牌阵",
    "subtitle": "过去、现在、未来",
    "description": "最简单直接的牌阵，适合日常问题和快速指引",
    "card_count": 3,
    "premium_reserved": false
  },
  "positions": [
    {
      "index": 0,
      "key": "past",
      "name": "过去",
      "description": "影响现在的情况和经历"
    }
  ],
  "remaining_count": 3,
  "expires_at": "2026-06-02T12:30:00Z"
}
```

错误码：

| HTTP 状态码 | 错误码 | 说明 |
| --- | --- | --- |
| 400 | `QUESTION_EMPTY` | 问题为空 |
| 400 | `QUESTION_TOO_SHORT` | 问题少于 6 个字符 |
| 400 | `QUESTION_TOO_LONG` | 问题超过 120 个字符 |
| 400 | `QUESTION_UNSAFE` | 命中高风险敏感内容 |
| 404 | `SPREAD_NOT_FOUND` | 牌阵不存在 |
| 500 | `INTERNAL_ERROR` | 服务内部异常 |

### 4.4 执行一次抽牌

接口：

`POST /api/v1/divinations/{sessionId}/draw`

路径参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `sessionId` | string | 是 | 会话 ID |

请求字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `client_draw_index` | number | 否 | 前端当前认为的抽牌序号，用于调试与校验 |

响应字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | string | 是 | 会话 ID |
| `status` | string | 是 | `drawing` 或 `draw_complete` |
| `current_position_index` | number | 是 | 本次抽中的牌位索引 |
| `next_position_index` | number or null | 否 | 下一张待抽牌位索引 |
| `remaining_count` | number | 是 | 剩余待抽牌数 |
| `drawn_card` | DrawnCard | 是 | 本次抽中的卡牌 |
| `all_cards_drawn` | boolean | 是 | 是否已抽满 |

成功示例：

```json
{
  "session_id": "div_12345678",
  "status": "drawing",
  "current_position_index": 0,
  "next_position_index": 1,
  "remaining_count": 2,
  "drawn_card": {
    "position_index": 0,
    "position_name": "过去",
    "card": {
      "id": "cups-05",
      "name_cn": "圣杯五",
      "arcana_type": "minor",
      "suit": "cups",
      "element": "water"
    },
    "orientation": "reversed",
    "cover_image_url": "/cards/back/gold.png",
    "face_image_url": "/cards/cups-05.png"
  },
  "all_cards_drawn": false
}
```

错误码：

| HTTP 状态码 | 错误码 | 说明 |
| --- | --- | --- |
| 404 | `SESSION_NOT_FOUND` | 会话不存在或已过期 |
| 400 | `DRAW_ALREADY_COMPLETE` | 已抽完全部卡牌 |
| 500 | `INTERNAL_ERROR` | 服务内部异常 |

### 4.5 生成解读结果

接口：

`POST /api/v1/divinations/{sessionId}/reading`

路径参数：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `sessionId` | string | 是 | 会话 ID |

请求体：

空对象即可：

```json
{}
```

响应字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | string | 是 | 会话 ID |
| `status` | string | 是 | 固定为 `reading_ready` |
| `reading` | object | 是 | 解读结果对象 |
| `reading.title` | string | 是 | 解读标题 |
| `reading.opening_message` | string | 是 | 开场语 |
| `reading.question` | string | 是 | 用户问题 |
| `reading.cards` | ReadingCard[] | 是 | 单卡解读 |
| `reading.overall_analysis` | string | 是 | 总体分析 |
| `reading.energy_flow` | string | 是 | 能量流动分析 |
| `reading.conflict_and_harmony` | string | 是 | 冲突与和谐分析 |
| `reading.timing_hint` | string | 是 | 时机提醒 |
| `reading.action_advice` | string | 是 | 行动建议 |
| `reading.long_term_advice` | string | 是 | 长期建议 |

错误码：

| HTTP 状态码 | 错误码 | 说明 |
| --- | --- | --- |
| 404 | `SESSION_NOT_FOUND` | 会话不存在或已过期 |
| 400 | `DRAW_NOT_COMPLETE` | 尚未完成抽牌 |
| 500 | `AI_TIMEOUT` | 模拟 AI 超时 |
| 500 | `AI_INVALID_RESPONSE` | 模拟 AI 结果不合法 |
| 500 | `INTERNAL_ERROR` | 服务内部异常 |

### 4.6 获取当前会话状态

接口：

`GET /api/v1/divinations/{sessionId}`

用途：

页面刷新后恢复当前状态。

响应字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `session_id` | string | 是 | 会话 ID |
| `status` | string | 是 | 当前会话状态 |
| `question` | string | 是 | 用户问题 |
| `spread_id` | string | 是 | 牌阵 ID |
| `spread` | SpreadSummary | 是 | 牌阵摘要 |
| `positions` | SpreadPosition[] | 是 | 牌位定义 |
| `drawn_cards` | DrawnCard[] | 是 | 已抽出的牌 |
| `remaining_count` | number | 是 | 剩余待抽牌数 |
| `reading` | object or null | 是 | 已生成的解读 |
| `expires_at` | string | 是 | 过期时间 |

错误码：

| HTTP 状态码 | 错误码 | 说明 |
| --- | --- | --- |
| 404 | `SESSION_NOT_FOUND` | 会话不存在或已过期 |
| 500 | `INTERNAL_ERROR` | 服务内部异常 |

### 4.7 健康检查

接口：

`GET /api/v1/health`

响应字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `status` | string | 是 | 固定为 `ok` |
| `service` | string | 是 | 服务名称 |
| `mode` | string | 是 | 固定为 `mock` |

成功示例：

```json
{
  "status": "ok",
  "service": "tarot-api",
  "mode": "mock"
}
```

## 5. 错误码总表

| 错误码 | HTTP 状态码 | 说明 |
| --- | --- | --- |
| `QUESTION_EMPTY` | 400 | 问题为空 |
| `QUESTION_TOO_SHORT` | 400 | 问题过短 |
| `QUESTION_TOO_LONG` | 400 | 问题过长 |
| `QUESTION_UNSAFE` | 400 | 问题命中高风险内容 |
| `SPREAD_NOT_FOUND` | 404 | 牌阵不存在 |
| `SESSION_NOT_FOUND` | 404 | 会话不存在或已过期 |
| `DRAW_ALREADY_COMPLETE` | 400 | 抽牌已完成 |
| `DRAW_NOT_COMPLETE` | 400 | 尚未抽满，不能生成解读 |
| `AI_TIMEOUT` | 500 | AI 服务超时 |
| `AI_INVALID_RESPONSE` | 500 | AI 返回结构不合法 |
| `INTERNAL_ERROR` | 500 | 其他服务内部错误 |

## 6. 无数据库实现说明

当前 mock 版本不依赖数据库，约定如下：

1. 牌库与牌阵配置存放于后端代码文件。
2. 会话存在内存字典中。
3. 服务重启后，历史会话全部丢失。
4. 会话有过期时间，过期后返回 `SESSION_NOT_FOUND`。
