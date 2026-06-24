# 20260624_给智能体阅读_Workspace写入Neo4j实现总结与接手说明

## 1. 文档用途

本文是当前 `Workspace -> 写入 Neo4j` 阶段的技术备份文档，目标是让后续接手的智能体在**没有历史上下文**的情况下，也能尽快理解：

- 当前功能已经做到哪里
- 现有代码是如何组织的
- 过去踩过哪些坑、已经修掉了哪些问题
- 接下来如果继续开发，应该从哪里接手

本文同时覆盖：

- 业务逻辑
- 代码逻辑
- 数据模型逻辑
- 当前边界与后续入口

## 2. 当前目标已经演变成什么

这一阶段最初只是“给现有项目接上 Neo4j”，但在多轮联调后，目标已经演变为：

1. `base` 层写入要稳定
2. `retrieval` 层允许在非完美条件下继续写入
3. `discovery` 层不再无差别复制节点
4. `base / retrieval / discovery` 三层尽量共用同一套 canonical 实体
5. Database 页面对 discovery 的统计口径要更贴近真实业务语义

因此，当前实现不能再简单理解为“把三份 JSON 写进图数据库”，而应理解为：

- `base`：正式实体层
- `retrieval`：检索资产对正式实体的引用层
- `discovery`：发现记录基于正式实体形成的推理补充层

## 3. 当前代码的关键文件

### 3.1 `backend/neo4j_models.py`

这是当前最核心的 payload 构建文件。

它负责：

- `base` 实体 / 关系 payload
- `retrieval` 层 payload
- `discovery` 层 payload

当前最重要的逻辑已经集中在这里：

- retrieval 的“实体引用优先”
- discovery 的“实体引用优先”
- `LegalProvisionElement` 分流
- `SentencingCircumstance / EvidenceChain` 的文书级 canonical 派生节点 id
- `ArgumentOutcome` 降级为关系属性

如果后续继续接 discovery / retrieval 的建模收口，优先先看这个文件。

### 3.2 `backend/neo4j_service.py`

这个文件负责：

- 组装写入流程
- 获取 base 实体索引
- 调用 payload 构建
- 执行 upsert
- 返回写入摘要

当前 `write_retrieval_layer()` 和 `write_discovery_layer()` 已经不是简单地“直接写 payload”，而是包含了：

- base lookup 注入
- summary 字段聚合
- discovery / retrieval 的写入摘要解释

### 3.3 `backend/neo4j_repository.py`

这个文件负责：

- 读写 Neo4j
- `case_status`
- `case_detail`
- `case_subgraph`

当前这里已经补过一轮 discovery 的新 summary 口径：

- `实体引用`
- `文书级派生节点`
- `枚举锚点`

它不再只是把 discovery 解释成：

- `DiscoveryNode`
- `DiscoveryAnchor`

### 3.4 `backend/app.py`

这个文件承担两类事情：

1. `Workspace` / `Database` 的 API 路由
2. 本地摘要 / diff 摘要的构建

当前这里最关键的点是：

- retrieval 本地摘要
- discovery 本地摘要
- diff-case

尤其 discovery 的本地摘要已经不再是“直接数原始 `new_nodes` / `new_edges`”，而是复用了当前 discovery 映射规则做估算，保证：

- 本地 diff 口径
- 实际写入口径

尽量一致。

### 3.5 `visualization/ontology-refactored/src/components/TerminalPanel.js`

这是 `Workspace` 页写入 Neo4j 的主要前端逻辑入口。

当前这里已经处理过的关键问题：

- retrieval 写入前校验
- embedding `pending/stale/failed` 从硬阻塞改成非阻塞提醒
- retrieval 兼容模式写入
- discovery / retrieval 成功提示状态

如果后续继续改 Workspace 提示文案或前端交互，优先从这里接。

### 3.6 `visualization/ontology-refactored/src/database/components/DatabaseBottomPanel.js`

这是 Database 页面对图数据库状态、diff、重同步等能力的主要展示入口。

当前这里已经做过一轮 discovery 口径切换：

- discovery 卡片显示新的 summary 口径
- discovery diff 显示新的 summary 对比

## 4. 当前三层的实际语义

### 4.1 base

`base` 是正式实体层。

语义上：

- 它承载正式本体实体
- 是 retrieval / discovery 优先复用的对象来源

当前已确认写入的对象包括：

- `Fact`
- `DisputeFocus`
- `LitigationClaim`
- `ArgumentPoint`
- `JudicialAssessment`
- `Evidence`
- `JudgmentResult`
- `LegalProvision`
- `LegalProvisionElement`
- 以及前面补齐过的 `CourtCase / TrialOrganization / Judge`

### 4.2 retrieval

`retrieval` 不是另一份正式本体。

当前正确理解应为：

- `RetrievalEntry` 表示某条检索资产
- 检索资产优先引用 `base` 里的正式实体
- 只有无法稳定对齐时，才保留兜底 `RetrievalGraphNode`

### 4.3 discovery

`discovery` 不是“把推理结果再复制成一张新图”。

当前正确理解应为：

- `DiscoveryRecord` 表示一条发现记录
- 它优先引用 `base` 实体
- 对于真正属于推理层的对象，保留文书级派生节点
- 对于不应继续当实体的对象，进一步降级

## 5. 当前 retrieval 已修复的问题

### 5.1 向量状态误阻塞

最初 retrieval 前端校验把：

- `pending`
- `stale`
- `failed`

这些 embedding 状态也当成了硬阻塞，导致请求在发出前就被前端拦下。

现在已修复为：

- 这些状态只提醒
- 不阻止 Neo4j 写入

### 5.2 真正的链路问题仍保留阻塞

仍然继续阻塞的情况主要是：

- 检索正文为空
- 当前资产未形成有效实体关系链

但后续又进一步改成了兼容模式：

- 可写项继续写
- 阻塞项跳过
- 并返回 `skipped_entries`

### 5.3 retrieval 重复造节点问题

原本 retrieval 会把很多本应复用 `base` 的对象继续写成 `RetrievalGraphNode`。

已经补过一轮复用规则，覆盖过的对象包括：

- `Fact`
- `DisputeFocus`
- `LegalSubject`
- 部分可按文本唯一命中的对象

当前 retrieval 仍允许兜底节点存在，但不再默认复制。

## 6. 当前 discovery 已修复的问题

### 6.1 与 base 重复的 discovery 节点

已经收掉一批本来就应复用 `base` 的对象，例如：

- `ArgumentPoint`
- `DisputeFocus`
- `LitigationClaim`

### 6.2 discovery 记录之间重复造同语义节点

已经引入文书级 canonical id 规则来收口一部分派生节点，当前已覆盖：

- `SentencingCircumstance`
- `EvidenceChain`

当前它们仍使用 `DiscoveryNode` 标签，但已通过以下属性标明语义：

- `canonical_scope = document`
- `node_role = document_canonical_derived`
- `derived_type = <type>`

### 6.3 `LegalProvisionElement` 一刀切问题

当前已不再把 discovery 里的 `LegalProvisionElement` 简单理解成和 `base` 完全相同。

处理方式改成：

- 能强匹配 `base` 的，复用 `base LegalProvisionElement`
- 不能强匹配、或本质上是个案适用表达的，保留为：
  - `DiscoveryNode`
  - `node_type = AppliedLegalProvisionElement`

### 6.4 `ArgumentOutcome` 作为节点的问题

这是最近一轮的重点修复。

当前已经不再把 `ArgumentOutcome` 写成：

- `DiscoveryNode`
- `DiscoveryAnchor`

现在做法是：

- 直接把 outcome 写到关系属性上

例如关系属性中会出现：

- `outcome_code`
- `outcome_text`

这意味着：

- discovery 图中不再为“采纳 / 驳回”这种结果值单独造节点

## 7. 当前 discovery 统计口径

### 7.1 旧口径

旧口径主要是看：

- `DiscoveryNode`
- `DiscoveryAnchor`
- `DiscoveryRecord`

这在早期接入阶段有用，但业务解释力已经不够。

### 7.2 新口径

现在 discovery 在 Database 页和 diff 里，重点口径已经切换为：

- `实体引用数`
- `文书级派生节点数`
- `枚举锚点数`

说明：

- `实体引用数`
  - 指当前 discovery 层实际复用了多少正式实体
- `文书级派生节点数`
  - 指保留为文书级 canonical 推理对象的 discovery node 数量
- `枚举锚点数`
  - 指保留为受控值类锚点的数量
  - 当前由于 `ArgumentOutcome` 已降为关系属性，这个数可能为 `0`

### 7.3 当前状态

当前文书 `CASE:manual_1780383896` 经重写验证后，最新结果为：

- `entity_ref_count = 15`
- `document_derived_node_count = 18`
- `enum_anchor_count = 0`

并且确认：

- `ArgumentOutcome` 实体数已经为 `0`

## 8. 当前实现的关键技术策略

### 8.1 保守复用，不做激进误绑

当前所有“复用 base”逻辑都偏保守：

- 直接 id 命中优先
- 文本唯一匹配才复用
- 多候选时宁可保留兜底，也不强行并错

### 8.2 兼容优先，不强行推翻旧 schema

当前没有大规模引入新标签体系，而是尽量在原有结构上做兼容式收口：

- `DiscoveryNode` 继续存在
- `RetrievalGraphNode` 继续存在

但它们已经不再是默认主路径。

### 8.3 先改写入语义，再改展示语义

这一阶段是先把：

- payload 生成
- 写入路径
- 复用逻辑

改对，然后再把：

- status
- diff
- Database 展示

同步改过来。

因此当前显示口径已经基本追上了实际写入语义。

## 9. 当前哪些功能可视为已完成

如果从 `Workspace 写入 Neo4j` 这一阶段看，以下能力可视为已完成：

1. `base` 正式写入
2. `retrieval` 正式写入
3. `discovery` 正式写入
4. retrieval 写入前阻塞逻辑修正
5. retrieval 兼容模式写入
6. retrieval 与 base 的重复节点收口
7. discovery 与 base 的重复节点收口
8. discovery 内部同语义节点收口
9. `ArgumentOutcome` 降级
10. discovery 统计口径切换

## 10. 当前仍然存在的边界

### 10.1 retrieval 仍保留少量兜底节点

对无法安全对齐的 retrieval 对象，仍会保留兜底 `RetrievalGraphNode`。

这是有意保留的保守策略。

### 10.2 discovery 仍使用兼容标签

虽然语义上 `SentencingCircumstance / EvidenceChain / AppliedLegalProvisionElement` 已有更清晰角色，但当前仍挂在 `DiscoveryNode` 标签下。

这意味着：

- 语义已收口
- schema 还没有完全独立化

### 10.3 Workspace 的提示文案还有进一步优化空间

例如：

- discovery 成功提示目前仍以 `record_count` 为主

这不影响落库结果，但从产品解释角度仍可继续优化。

## 11. 如果后续继续接手，建议优先顺序

### 11.1 第一优先

如果要继续完善当前阶段，优先考虑：

- 优化 `Workspace` 中 discovery 成功提示文案
- 继续完善 Database 页展示
- 补充更清晰的子图查询语义

### 11.2 第二优先

如果要继续走结构优化，可考虑：

- 进一步引入 revision 模型
- 统一 `document_uid`
- 继续收紧 discovery derived node 的正式 schema

### 11.3 第三优先

如果要继续做深层图建模，可考虑：

- `DiscoveryNode` 向更明确的 `DiscoveryDerivedNode` / `DiscoveryTextAnchor` 演进
- retrieval / discovery 更彻底的 revision 化

## 12. 当前接手时的推荐阅读顺序

如果后续智能体需要接手，建议按这个顺序看：

1. 本文
2. `docs/20260624_给你阅读_Workspace写入Neo4j阶段总结备份.md`
3. `backend/neo4j_models.py`
4. `backend/neo4j_service.py`
5. `backend/neo4j_repository.py`
6. `backend/app.py`
7. `visualization/ontology-refactored/src/components/TerminalPanel.js`
8. `visualization/ontology-refactored/src/database/components/DatabaseBottomPanel.js`

## 13. 本文结论

当前 `Workspace -> 写入 Neo4j` 已经从“初步接入”推进到“核心语义基本稳定”的状态。

它当前不是完美终局，但已经具备以下特征：

- 功能能跑
- 多轮联调已做过
- 关键阻塞问题已修
- 关键重复节点问题已收口
- discovery 的统计解释已升级

因此，后续智能体如果没有历史上下文，可以直接把当前状态理解为：

- `Workspace 写入 Neo4j` 阶段已基本完成
- 后续工作主要是继续做语义收紧、更新模型和展示优化
