# 法律本体 v2.0 可视化——产品功能建议书

> **作者**: Hermes Agent  
> **日期**: 2026-05-12  
> **目标**: 基于现有 vis-network 力导向布局页面，提出可落地的产品级功能改进  
> **参考**: `legal_ontology_v2.zh.yaml` (32 实体, 34 关系), `ontology_v2.2.html`

---

## 目录

1. [P0-1：右侧信息面板 —— 结构化属性+关系展示面板](#p0-1-右侧信息面板--结构化属性关系展示面板)
2. [P0-2：关系边的完整信息浮层+高亮联动](#p0-2-关系边的完整信息浮层高亮联动)
3. [P1-1：继承树可折叠层级渲染](#p1-1-继承树可折叠层级渲染)
4. [P1-2：搜索/筛选工具栏](#p1-2-搜索筛选工具栏)
5. [P2-1：全局约束/索引工程信息面板](#p2-1-全局约束索引工程信息面板)
6. [P2-2：未来扩展方向](#p2-2-未来扩展方向)

---

## P0-1：右侧信息面板 —— 结构化属性+关系展示面板

### 做什么

在页面右侧固定一个可折叠/可收起的侧边面板（`<div id="detailPanel">`），当用户**鼠标悬停**（或**点击切换为锁定模式**）实体节点时，面板展示该实体的完整结构化信息：

```
┌─ [实体名称] ──────────────────────┐
│ 📋 CourtCase 法院案件            │
│ ──────────────────────────────── │
│ 📌 描述                           │
│   法院案件（精简节点）            │
│ 📌 必填字段（5）                   │
│   ✅ case_type_id   案由标识      │
│   ✅ filing_date    立案日期      │
│   ✅ court_id       法院标识      │
│   ✅ status         状态          │
│   ✅ trial_level    审级          │
│ 📌 可选字段（8）                   │
│   ⬜ case_number    案号          │
│   ⬜ claim_amount   诉讼标的额    │
│   ⬜ ...                          │
│ 📌 枚举约束                        │
│   🔘 trial_level ∈ {first_instance│
│      second_instance, retrial}    │
│   🔘 status ∈ {filing, trial, ...│
│   🔘 dispute_resolution_type ∈ {...│
│ 📌 参与的关系（5个出边+3个入边）   │
│   → 具有案由        CaseType      │
│   → 引用法条        LegalProvision│
│   → 具有摘要        CaseSummary   │
│   ← 由…审理        TrialOrg.     │
│   ← 公诉            Procuratorate │
│ 📌 继承链                          │
│   CourtCase → JudicialEntity      │
└────────────────────────────────────┘
```

**数据来源解析逻辑**（从 `legal_ontology_v2.zh.yaml` 中按类型名读取）：

1. **字段分组**：`required` → 必填字段（绿色✅标记），`optional` → 可选字段（灰色⬜标记）
2. **枚举值**：扫描所有 `*_enum` 后缀的键（如 `status_enum`, `trial_level_enum`），匹配到字段名时展示可枚举值列表
3. **约束**：匹配 `constraints` 段的全局规则（如 CourtCase 的时序约束 `filing_date < judgment_date`）
4. **关系**：遍历 `relations` 段，筛选出 `from == typeName` 的出边 和 `to == typeName` 的入边，使用 YAML 中的 `description` 和 `cardinality` 做展示

**交互细节**：

- 悬停自动展示，移出面板区域后延迟 800ms 收起（防抖）
- 面板内部可**点击固定**（锁定模式，鼠标离开不消失），再次点击关闭按钮或按 Escape 解除
- 关系条目可点击，点击后**定位并高亮**目标节点（`network.focus(targetId, { animation: true })`）

### 为什么好

| 问题 | 解决 |
|------|------|
| 当前仅悬停 tooltip 显示简短描述，无属性信息 | 用户可一次性看到类型全貌，理解"这个节点能存什么数据" |
| 关系边太多，无法快速知道某节点有哪些出边/入边 | 面板聚合所有相关关系，一目了然 |
| 开发者和业务方需要理解数据模型约束 | 枚举值和约束内联展示，降低沟通成本 |

### 优先级

**P0** — 这是用户明确提出的核心需求（需求1+3），也是本体浏览的基础交互。无此功能页面只有拓扑图而无"信息"。

### 实施要点

- 面板宽度建议 320–380px，可拖拽调整宽度
- 使用 `position: fixed; right: 0; top: 44px; height: calc(100vh - 44px);` 对齐顶部导航
- 关系列表中的每个条目用 `<a>` 标签 + `network.focus()` 实现跳转
- YAML 数据在 JS 中硬编码为一个常量对象（与现有 `ZH_LABELS` 同层），避免每次加载都请求网络

---

## P0-2：关系边的完整信息浮层 + 高亮联动

### 做什么

当前关系边悬停显示的是 `title` 属性（简单文本 `<b>relName</b><br>desc`）。升级为**两点改进**：

**a) 悬停浮层升级**：浮层展示关系的完整元信息：

```
┌─ belongs_to ─────────────────────┐
│ 📌 描述                           │
│   法律条文归属法律                │
│ 📌 基数                           │
│   many_to_one (多对一)           │
│ 📌 方向                           │
│   LegalProvision ──→ Law         │
│ 📌 属性（如有）                    │
│   （cites 关系有：citation_position│
│    citation_purpose, context）   │
│ 📌 约束                           │
│   无环: false                     │
└───────────────────────────────────┘
```

**b) 悬停高亮联动**：悬停某条关系边时：

- **高亮**该边（加粗、变色）
- **弱化**其他所有边（opacity → 0.15）
- **高亮**该边的 from/to 两个节点（放大边框/发光效果）
- **弱化**其他所有节点（opacity → 0.3）
- 移出后恢复

**c) 关系类型筛选模式**：点击图例区域的"关系类型"时，切换一种**模式视图**：

- 只展示某一类关系（如仅显示"案件层关系"或仅显示"规范层关系"）
- 未被筛选的关系边以极低透明度显示（`opacity: 0.05`），指示"存在但当前未关注"

**分组建议**：

| 关系分组 | 包含的关系 |
|----------|-----------|
| 规范层 | belongs_to, has_version, superseded_by, typically_applies |
| 案件引用层 | cites, judgment_cites, cites_guiding_case, applies_standard |
| 案件结构层 | has_summary, tried_by, has_case_type, has_dispute_focus, has_fact |
| 诉讼参与层 | plays_role, represents, undertakes, prosecutes, employs, employs_attorney |
| 审判组织层 | includes, includes_clerk, presides_over, signed_by |
| 执行/证据层 | based_on, submitted_for, proves_fact, proves_focus |
| 案件流程层 | appeals_to, retries_from |

### 为什么好

- 关系边是知识图谱的"骨架"，展示基数、属性、约束能让开发者理解数据模型约束
- 高亮联动解决"多条边重叠看不清"的问题——当前所有边都是灰色实线，悬停时聚焦一对节点
- 关系分组筛选解决"34条边太密"的问题，让用户按领域聚焦

### 优先级

**P0** — 用户明确提出"显示关系属性、基数、from→to"（需求2）。高亮联动虽未明确说，但这是解决密集图形可读性的基础手段。

### 实施要点

- vis-network 支持 `edge.hover` 事件和 `network.on('hoverEdge', callback)`
- 高亮通过 `network.setOptions({ edges: { ... } })` 动态更新样式，或对单个 edge/node 调用 `{ update: ... }` 实现
- 关系分组可以使用 `<select>` 下拉框放在右上角或图例区

---

## P1-1：继承树层级折叠 / 按域展开

### 做什么

当前页面将所有节点（包括抽象顶层类 + 具体实体类 + `LegalProvisionElement` 等辅助节点）全部展示，32 个节点铺满画面。建议引入**层级折叠机制**：

**a) 继承树折叠（默认收起顶层）**

默认只展示**具体实体节点**（Law, LegalProvision, CourtCase, Judge 等），**抽象顶层节点**（LegalNorm, JudicialEntity, LegalSubject, Person）默认收起为一行小标签。

用户展开方式：
- 点击小标签 → 展开为该根类的所有子节点
- 或者点击图例中的"展开全部"按钮

**b) 领域视角切换**

在顶部导航栏增加 3 个视角按钮：

```
[ 全貌 ] [ 规范层 ] [ 主体层 ] [ 案件层 ]
```

- **规范层**：只显示 LegalNorm 系节点 + 相关关系
- **主体层**：只显示 LegalSubject/Person 系节点 + 相关关系
- **案件层**：只显示 JudicialEntity 系中 CaseSummary 以下的具体节点 + 相关关系
- **全貌**：显示全部

切换时用动画淡入淡出（`network.setData()` 动态增减节点/边）。

**c) 节点尺寸层级编码**

- 抽象顶层类（LegalNorm 等）：**六边形大节点**（保留）
- 具体实体类（Law, Court 等）：**矩形中等节点**（当前）
- 细分类/构成要素（LegalProvisionElement, CaseParticipant 等）：**圆形小节点**，降低视觉权重

### 为什么好

- 32 个节点 + 继承边 + 关系边 = 视觉负载较高，信息密度大。按域折叠让用户有"钻入/钻出"的控制感
- 法律团队通常关心某个领域（如"案件层"），不需要看到规范层结构
- 层级编码让视觉层次清晰——"重要"的节点更大更醒目

### 优先级

**P1** — 核心需求已有右侧面板（P0）覆盖基本的信息获取，层级折叠是第二步的视觉优化。但建议放在第一轮开发（Sprint 1）的末尾实施，因为涉及数据分组逻辑的重构。

### 实施要点

- 在 JS 中维护节点分组映射（已在 `INHERITANCE_CHAIN` 中有继承链信息，可推导）
- 切换视角时，使用 `network.setData({ nodes: filteredNodes, edges: filteredEdges })` 动态更新
- 动画使用 `physics: { stabilization: false }` 避免每次切换重复力导向稳定

---

## P1-2：搜索/筛选工具栏

### 做什么

在顶部导航栏右侧增加一个搜索输入框（`<input type="text" placeholder="🔍 搜索类型名称或描述...">`），功能包括：

**a) 按名称/中文标注搜索**

输入关键词后：

- 匹配的节点**高亮**（脉冲动画 2 次）
- 不匹配的节点**半透明**（opacity 0.2）
- 匹配的边保留，不匹配的边半透明
- 如果命中了某关系名，高亮该关系的所有边

**b) 按字段/枚举值搜索（进阶）**

搜索语法扩展（可选）：

```
字段名:case_type_id     → 搜索所有包含 case_type_id 字段的类型
枚举值:guilty           → 搜索所有枚举值中包含 guilty 的类型
基数:many_to_many      → 搜索所有多对多关系
```

**c) 搜索结果列表**

搜索框下方弹出下拉列表，列出所有匹配的节点/关系，点击直接定位：

```
┌─ 🔍 搜索: 法 ──────────────────┐
│ 📄 Law                法律      │
│ 📄 LegalProvision     法律条文  │
│ 📄 LegalProvisionVer. 法律条文历史│
│ 🔗 cites              引用法条  │
│ 🔗 judgment_cites     裁判依据  │
└─────────────────────────────────┘
```

### 为什么好

- 当前只有"看图"，没有"找东西"。搜索是最低成本的导航手段
- 32 个节点虽然不多，但名称混合英文（LegalProvisionVersion）和中文（法律条文历史版本），用户不一定知道全名
- 字段/枚举搜索对数据建模者和开发者极其有用——"我想知道哪些类型用到了 `status` 字段"

### 优先级

**P1** — 搜索是效率工具，但不是拦路虎。发布第一版可以没有搜索，但有了之后用户体验提升明显。

### 实施要点

- 输入框监听 `input` 事件，300ms 防抖
- 高亮通过 `network.body.nodes[nodeId].options.color` 临时覆盖
- 搜索下拉用绝对定位放在输入框下方，Z-index 1000
- 可以用 Fuse.js 做模糊匹配（轻量，~10KB）

---

## P2-1：全局约束 / 工程信息面板

### 做什么

在右侧面板新增一个"全局信息"标签页（或顶栏右侧第二个按钮），展示 YAML 中的非类型数据：

**a) 约束一览表**

将 YAML 的 `constraints` 段渲染为表格：

| 类型 | 规则 | 强制程度 | 描述 |
|------|------|----------|------|
| CourtCase | `case_number =~ /^\(\d{4}\)...$/` | block | 案号校验 |
| Organization | `credit_code =~ /^[0-9A-H]...$/` | block | 信用代码校验 |
| CourtCase | `filing_date < judgment_date` | block | 时序约束 |
| Evidence | `admitted ⇒ examined` | block | 证据未经质证不得采信 |
| CourtCase | `cites.status == 'effective'` | soft | 仅引用有效法条 |
| — 全局 — | 脱敏规则 | block | 个保法分级脱敏 |

**b) 工程元信息**

- 数据版本：`2026.04.v2`
- 增量更新：`true`
- 图存储前缀：`LEGAL_` / `REL_`
- 热层条件：`filing_date >= 2023-01-01 OR ...`
- 实体消歧策略：Court → `name + district.code`, Organization → `credit_code`
- 索引启用：`true`

**c) 外键映射表**（开发者关心）

展示 `foreign_key_mapping` 中的映射关系。

### 为什么好

- 约束是本体定义的"业务规则"，展示出来让用户理解数据质量要求和业务逻辑
- 工程信息对开发者调试、理解数据版本和索引策略至关重要
- 目前这些信息在图上看不到，但 YAML 中有丰富的业务逻辑

### 优先级

**P2** — 这是"锦上添花"功能。布局正常跑起来、右侧面板展示属性关系后，下一轮迭代可以加。适合开发者在第一轮迭代间隙完成。

### 实施要点

- 在 JS 中同样硬编码 `CONSTRAINTS`, `ENGINEERING_INFO` 等常量
- 面板中增加标签页切换：`[ 属性 ] [ 约束 ] [ 工程信息 ]`
- 约束表格中，block 用红色标记、soft 用橙色标记

---

## P2-2：未来扩展方向（本轮不实现）

### 1. 数据实例预览模式

**做什么**：点击类型节点后，右侧面板底部显示"查看实例数据"按钮，对接后端 API 返回该类型的 3–5 条真实数据样本（如 Law 类型的 3 条法律记录），以内联 JSON 或卡片展示。

**为什么好**：建模者看到"这个字段是必填的"不如看到"一个实际的 Law 记录长什么样"有说服力。这是从 schema 到真实数据的桥梁。

**预计**：需后端配合，属于中远期。

### 2. 关系路径查询

**做什么**：在搜索框旁增加"路径查询"模式。用户选择两个节点（如 CourtCase → LegalProvision），系统计算并高亮最短路径/所有路径。

**为什么好**：知识图谱的核心价值之一是"发现间接关联"。比如"一个案子的当事人和另一个案子通过同一个律师产生关联"。

**预计**：依赖后端路径查找 API，前端需展示多路径叠加。

### 3. 导出/快照功能

**做什么**：右上角增加"导出"按钮，支持：
- 导出当前视图为 PNG（canvas.toDataURL）
- 导出本体定义子集为 YAML/JSON（仅展示的节点和关系）

**为什么好**：团队评审时可以直接截取当前视角的图谱，或导出子本体给其他微服务使用。

**预计**：前端独立可实现，但导出 YAML 子集需做过滤逻辑。

### 4. 对比模式（Diff View）

**做什么**：当 YAML 升级到 v2.1 时，提供一个"对比模式"，新旧版本并排显示（或同一张图但用颜色标记新增/删除/变更的节点和边）。

**为什么好**：法律本体持续演进，团队需要快速了解"这次改了什么"。

**预计**：版本管理 + 在线对比，需要元版本控制机制。

### 5. 暗色模式

**做什么**：右上角增加 🌙/☀️ 切换按钮，切换深色背景配色方案。

**为什么好**：开发者和法务团队经常长时间查看图表，暗色模式减少眼部疲劳。

**预计**：纯 CSS 变量切换，实现成本低但属于视觉润色。

---

## 附录 A：YAML 数据结构统计（供开发参考）

| 类别 | 数量 | 说明 |
|------|------|------|
| 顶层父类 | 4 | LegalNorm, JudicialEntity, LegalSubject, Person |
| 规范层实体 | 6 | Law, LegalProvision, LegalProvisionVersion, CaseType, GuidingCase, SentencingStandard |
| 主体层实体 | 9 | Organization, Court, Procuratorate, LawFirm, ExpertInstitution, Judge, Attorney, Clerk, Prosecutor |
| 案件层实体 | 12 | CourtCase, CaseSummary, TrialOrganization, JudgmentResult, ExecutionInfo, LegalDocument, Evidence, DisputeFocus, Fact, CaseParticipant, LegalRole, District |
| 辅助节点 | 1 | LegalProvisionElement |
| **合计节点** | **32** | |
| 继承边 (is_a) | 27 | 从 subtype 指向 supertype |
| 关系边 | 34 | 从 YAML relations 段提取 |
| **合计边** | **61** | |
| 全局约束 | 9 | 包含正则校验、时序约束、业务规则 |
| 枚举定义 | ~20 | 分布在各个类型的 `*_enum` 字段 |
| 外键映射 | 18 | `foreign_key_mapping` |

## 附录 B：实现优先级汇总

| 序号 | 功能 | 优先级 | 预估工时 | 依赖 |
|------|------|--------|----------|------|
| 1 | 右侧信息面板（节点） | P0 | 1–2 天 | YAML 数据 JS 化 |
| 2 | 关系边信息浮层 + 高亮联动 | P0 | 1–1.5 天 | vis-network hover API |
| 3 | 继承树折叠 / 域视角 | P1 | 1.5–2 天 | 节点分组重构 |
| 4 | 搜索/筛选工具栏 | P1 | 1 天 | 无 |
| 5 | 全局约束/工程信息面板 | P2 | 1 天 | 右面板标签页机制 |
