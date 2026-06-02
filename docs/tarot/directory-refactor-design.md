# `tarot/` 目录重构设计文档

## 1. 目标

本设计文档用于将当前仓库内零散的塔罗前端、后端、资源、文档与脚本，收敛到统一的 `tarot/` 目录下，形成一套可持续扩展的塔罗产品工程结构。

本次设计重点解决以下问题：

1. 塔罗相关代码与现有仓库其他业务解耦。
2. 图片、牌义、牌阵规则三类资源分层管理。
3. 为后续自动构筑占卜 Prompt 提供稳定的数据结构。
4. 为多牌风、多牌义体系、多语言扩展预留空间。
5. 为资源版权、来源追踪和版本管理建立基础规范。

## 2. 重构原则

### 2.1 资源与代码解耦

业务代码不直接硬编码牌图、牌义、牌阵内容。

所有静态知识统一进入 `resources/`：

1. `image_packs` 负责图片资源。
2. `meaning_packs` 负责解牌规则。
3. `spread_packs` 负责牌阵与牌位规则。

### 2.2 稳定主键优先

所有图片、牌义、牌阵、提示词构建都围绕稳定 ID 组织：

1. `canonical_card_id`
2. `image_pack_id`
3. `meaning_pack_id`
4. `spread_pack_id`
5. `spread_id`
6. `position_id`

### 2.3 多体系组合，而非强耦合

图片风格、牌义体系、牌阵体系必须可自由组合，不应彼此绑定。

例如：

1. `rws-public-domain` 图片包 + `rws-core-v1` 牌义包 + `core-v1` 牌阵包
2. `rws-public-domain` 图片包 + `rws-love-v1` 恋爱专题牌义包 + `core-v1` 牌阵包
3. 未来 `marseille-classic` 图片包 + `marseille-core-v1` 牌义包 + `classic-v1` 牌阵包

### 2.4 来源可追溯

所有导入资源都必须记录：

1. 来源 URL
2. 授权信息
3. 导入时间
4. 导入脚本版本
5. 是否允许商用
6. 是否需要署名

### 2.5 先中间层，后 Prompt

不直接用原始资源拼接模型提示词。

推荐流程：

1. 读取资源文件
2. 构建结构化 `reading_context`
3. 再由 `prompt_builder` 输出模型提示词

## 3. 目标目录结构

建议未来统一迁移到如下结构：

```text
tarot/
├── README.md
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── styles.css
│   ├── tarot-api.js
│   ├── tarot-api-types.d.ts
│   └── components/
├── backend/
│   ├── app.py
│   ├── api/
│   │   ├── routes/
│   │   │   ├── health.py
│   │   │   ├── spreads.py
│   │   │   ├── divinations.py
│   │   │   └── readings.py
│   │   └── schemas/
│   │       ├── requests.py
│   │       └── responses.py
│   ├── services/
│   │   ├── resource_loader.py
│   │   ├── session_store.py
│   │   ├── draw_service.py
│   │   ├── reading_service.py
│   │   ├── reading_context_builder.py
│   │   └── prompt_builder.py
│   ├── domain/
│   │   ├── card_ids.py
│   │   ├── enums.py
│   │   ├── errors.py
│   │   └── validators.py
│   └── tests/
├── resources/
│   ├── image_packs/
│   │   └── <image_pack_id>/
│   │       ├── manifest.yaml
│   │       ├── full/
│   │       └── thumbnails/
│   ├── meaning_packs/
│   │   └── <meaning_pack_id>/
│   │       ├── manifest.yaml
│   │       ├── cards/
│   │       │   ├── major/
│   │       │   └── minor/
│   │       ├── positions/
│   │       └── synthesis/
│   ├── spread_packs/
│   │   └── <spread_pack_id>/
│   │       ├── manifest.yaml
│   │       ├── positions/
│   │       └── spreads/
│   └── source_manifests/
│       ├── licenses/
│       ├── imports/
│       └── attribution/
├── scripts/
│   ├── import_images/
│   ├── import_meanings/
│   ├── build_context/
│   ├── validate_resources/
│   └── generate_prompt_assets/
├── docs/
│   ├── prd/
│   ├── api/
│   ├── resources/
│   └── architecture/
└── examples/
    ├── reading_context/
    └── prompt_outputs/
```

## 4. 各层职责

### 4.1 `frontend/`

负责：

1. 首页、抽牌页、结果页呈现
2. 用户输入与流程控制
3. 调用后端接口
4. UI 状态与本地临时会话恢复

不负责：

1. 牌义解释规则的硬编码
2. 随机抽牌核心逻辑
3. Prompt 拼接

### 4.2 `backend/`

负责：

1. 资源读取与装配
2. 抽牌逻辑与会话状态管理
3. `reading_context` 构建
4. Prompt 构建
5. AI 解读接口
6. 风控和异常处理

### 4.3 `resources/image_packs/`

负责：

1. 不同体系或风格的牌图资源
2. 缩略图、全尺寸图、多格式导出
3. 图片包元数据与授权记录

### 4.4 `resources/meaning_packs/`

负责：

1. 每张牌的结构化牌义
2. 正位/逆位含义
3. 多领域语义
4. 符号学说明
5. Prompt 片段

### 4.5 `resources/spread_packs/`

负责：

1. 牌阵定义
2. 位置定义
3. 牌阵布局
4. 结果汇总策略

### 4.6 `resources/source_manifests/`

负责：

1. 版权来源记录
2. 采集批次记录
3. 资源导入日志
4. attribution 信息

## 5. 主键设计

### 5.1 `canonical_card_id`

建议采用如下规则：

```text
major.00.fool
major.01.magician
major.02.high_priestess
...
minor.cups.01.ace
minor.cups.02.two
minor.swords.11.page
minor.swords.12.knight
minor.swords.13.queen
minor.swords.14.king
```

要求：

1. 全局唯一
2. 与画风无关
3. 与语言无关
4. 不包含正逆位
5. 长期稳定，不随文案变化而变化

### 5.2 其他关键 ID

建议：

1. `image_pack_id`: `rws-public-domain`
2. `meaning_pack_id`: `rws-core-v1`
3. `spread_pack_id`: `core-v1`
4. `spread_id`: `three-card`
5. `position_id`: `past`

## 6. 资源分层模型

### 6.1 图片层

图片层只回答一个问题：

“这张牌显示成什么样子？”

该层不承担：

1. 牌义文本
2. 牌阵规则
3. 占卜语义

### 6.2 牌义层

牌义层回答：

“这张牌在某个体系下意味着什么？”

该层可包含：

1. 通用含义
2. 正逆位含义
3. 分主题含义
4. 符号学解释
5. Prompt 片段

### 6.3 牌阵层

牌阵层回答：

“这张牌落在这个位置时，应该如何解释？”

该层可包含：

1. 位置语义
2. 牌位顺序
3. 布局信息
4. 汇总策略

### 6.4 汇总层

由后端在运行时构建：

1. 用户问题
2. 牌阵规则
3. 卡牌基础牌义
4. 牌位语义
5. 正逆位修正
6. 文风策略

最后生成 `reading_context`

## 7. 推荐运行链路

```text
用户输入问题
  -> 选择 spread_id
  -> 抽牌得到 card_id + orientation + slot
  -> 读取 spread_pack
  -> 读取 position rules
  -> 读取 meaning_pack
  -> 选取 image_pack
  -> 构建 reading_context.json
  -> prompt_builder 输出 prompt
  -> AI 生成解读
  -> 前端渲染结果
```

## 8. `reading_context` 中间层

这是整个系统最关键的中间数据结构，推荐长期稳定维护。

建议结构：

```json
{
  "question": "我的感情发展会如何？",
  "locale": "zh-CN",
  "tone": "mystical",
  "spread": {
    "spread_pack_id": "core-v1",
    "spread_id": "three-card",
    "name": "三牌阵"
  },
  "resources": {
    "image_pack_id": "rws-public-domain",
    "meaning_pack_id": "rws-core-v1"
  },
  "cards": [
    {
      "slot": 0,
      "position_id": "past",
      "position_name": "过去",
      "canonical_card_id": "minor.cups.05.five",
      "orientation": "reversed"
    }
  ]
}
```

## 9. 版本化策略

### 9.1 必须版本化的内容

1. `meaning_pack`
2. `spread_pack`
3. Prompt 模板
4. 导入脚本

### 9.2 可选版本化的内容

1. `image_pack`
2. 缩略图尺寸策略
3. 资源压缩格式

建议约定：

1. `rws-core-v1`
2. `rws-core-v2`
3. `core-v1`
4. `core-v2`

## 10. 来源与版权策略

### 10.1 图片资源

图片资源建议区分：

1. 公版资源
2. 商业授权资源
3. 自制或委托绘制资源

### 10.2 牌义资源

牌义资源建议区分：

1. 公版原始资料
2. 明确授权资料
3. 自研结构化整理内容

### 10.3 为什么必须保留 `source_manifests`

因为后续你需要回答：

1. 这张图从哪里来的？
2. 这份牌义能不能商用？
3. 是否需要署名？
4. 这份内容是原文摘录、改写还是 AI 生成？

## 11. 从当前仓库迁移的建议

### 11.1 当前建议迁移对象

建议未来迁入 `tarot/` 的现有文件：

1. 当前塔罗前端页面与样式
2. 当前塔罗 API mock
3. 当前塔罗类型定义与 API client
4. 当前塔罗 PRD 与 API 文档

### 11.2 迁移目标映射

建议映射如下：

```text
webui/frontend/index.html              -> tarot/frontend/index.html
webui/frontend/app.js                  -> tarot/frontend/app.js
webui/frontend/styles.css              -> tarot/frontend/styles.css
webui/frontend/tarot-api.js            -> tarot/frontend/tarot-api.js
webui/frontend/tarot-api-types.d.ts    -> tarot/frontend/tarot-api-types.d.ts
webui/backend/tarot_mock_api.py        -> tarot/backend/api/routes/mock.py
docs/tarot-prd.md                      -> tarot/docs/prd/tarot-prd.md
docs/tarot-api-spec.md                 -> tarot/docs/api/tarot-api-spec.md
```

## 12. 分阶段实施建议

### 阶段 1：目录清理

目标：

1. 建立 `tarot/` 根目录
2. 迁移前后端代码
3. 迁移文档
4. 不改业务逻辑，只改组织结构

### 阶段 2：资源规范化

目标：

1. 建立 `image_packs`
2. 建立 `meaning_packs`
3. 建立 `spread_packs`
4. 确定 ID 规范和 schema

### 阶段 3：自动上下文构建

目标：

1. 实现 `resource_loader`
2. 实现 `reading_context_builder`
3. 实现 `prompt_builder`

### 阶段 4：正式 AI 解读

目标：

1. 替换 mock 解读
2. 加入正式资源包
3. 加入主题化解读能力

## 13. 潜在风险

### 13.1 资源版权风险

如果资源来源、授权和导入日志不清晰，未来产品上线存在版权风险。

### 13.2 ID 不稳定风险

如果一开始没有统一的 `canonical_card_id`，后续图片、牌义、牌阵将难以关联。

### 13.3 语义与文案混用风险

如果把原始牌义、产品文案和 Prompt 片段混成一层，后续维护会非常困难。

## 14. 最终建议

这套重构方案的核心不是“把文件移到一个新目录”，而是先建立一个稳定的塔罗资源系统。

建议你后续按以下顺序推进：

1. 定 `canonical_card_id`
2. 定 `card.yaml / spread.yaml / manifest.yaml` schema
3. 建 `resources/` 三层目录
4. 导入第一套 `RWS` 图片包
5. 整理第一套基础牌义包
6. 构建 `reading_context`
7. 再接正式 AI 解读
