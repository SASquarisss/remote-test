# 行政案例可视化重构方案 — 架构设计文档

## 1. 概述

**目标**: 重构 `admin_instances.html`，对齐 `ontology_v2.2.html` 的交互范式、配色体系和图例设计，同时新增案例去重/版本管理、原始数据展示等能力。

**范围**: 
- `generate_admin_vis.py` — 生成逻辑升级（版本感知、去重、原始数据嵌入）
- `admin_instances.html` — 全新前端（颜色体系、交互面板、图例、版本选择、原始数据面板）

**约束**:
- 单HTML自包含（ALL_GRAPHS 数据内联，新增 VERSION_MAP 和 RAW_DATA）
- 不能修改 `ontology_v2.2.html`
- 颜色严格复用 `ontology_v2.2.html` 的 `ROOT_COLORS` 方案

---

## 2. 颜色体系映射

### 2.1 ROOT_COLORS（来自 ontology_v2.2.html）

| 根父类 | 背景色 | 边框色 | 分组名称 |
|--------|--------|--------|----------|
| LegalNorm | `#2980b9` | `#1a5276` | LegalNorm系 |
| JudicialEntity | `#d35400` | `#a04000` | JudicialEntity系 |
| LegalSubject | `#27ae60` | `#1e8449` | LegalSubject系 |
| Person | `#16a085` | `#0e6655` | Person系 |

### 2.2 行政案例实体 -> 根父类映射

| 管理实例实体类型 | 对应 ontology 类型 | 根父类 | 颜色 |
|-----------------|-------------------|--------|------|
| GuidingCase | GuidingCase → LegalNorm | LegalNorm | `#2980b9`/`#1a5276` |
| LegalProvision | LegalProvision → LegalNorm | LegalNorm | `#2980b9`/`#1a5276` |
| CaseSummary | CaseSummary → JudicialEntity | JudicialEntity | `#d35400`/`#a04000` |
| CourtCase | CourtCase → JudicialEntity | JudicialEntity | `#d35400`/`#a04000` |
| JudgmentResult | JudgmentResult → JudicialEntity | JudicialEntity | `#d35400`/`#a04000` |
| Evidence | Evidence → JudicialEntity | JudicialEntity | `#d35400`/`#a04000` |
| LegalSubject | LegalSubject | LegalSubject | `#27ae60`/`#1e8449` |

### 2.3 节点形状（保留现有 shape 以保障视觉区分度）

| 实体类型 | Shape | 说明 |
|---------|-------|------|
| GuidingCase | `hexagon` | 核心节点，size=35 |
| CourtCase | `box` | 法院案件，size=28 |
| LegalSubject | `ellipse` | 诉讼主体，size=22 |
| LegalProvision | `ellipse` | 法律条文，size=20 |
| JudgmentResult | `diamond` | 裁判结果，size=24 |
| Evidence | `ellipse` | 证据，size=20 |
| CaseSummary | `ellipse` | 案件类型，size=20 |

---

## 3. 数据模型升级

### 3.1 生成侧（generate_admin_vis.py）

新增概念：
- **版本聚合**: 同一 `row_id` 的所有 JSONL 行聚合成一个 `CaseVersionGroup`
- **版本指纹**: 对 `(nodes, edges)` 做规范化 JSON 序列化 → SHA256 指纹
- **去重合并**: 指纹相同 → 合并为一个版本；指纹不同 → 各自独立版本

### 3.2 数据嵌入格式

```javascript
// 1. ALL_GRAPHS — 去重后的案例版本组列表
const ALL_GRAPHS = [
  {
    row_id: '3358',
    case_name: '法国某某某兄弟股份有限公司...',
    case_type: '商标相关行政案件',
    versions: [
      {
        version: 1,
        fingerprint: 'sha256...',
        nodes: [...],
        edges: [...]
      }
    ]
  },
  ...
];

// 2. VERSIONED_INDICES — 下拉框用的带版本标识条目
const VERSIONED_INDICES = [
  { row_id: '3358', case_name: '法国某某某兄弟股份有限公司...', version: 1 },
  { row_id: '3358', case_name: '法国某某某兄弟股份有限公司...', version: 2 },
  ...
];

// 3. RAW_DATA — row_id → 原始 JSONL lines（用于左下方面板）
const RAW_DATA = {
  '3358': '{"row_id":"3358","input":{...},"output":{...},"eval":{...}}',
  ...
};
```

### 3.3 版本去重算法

```
输入：JSONL 中同一 row_id 的所有行列表
输出：CaseVersionGroup

1. 对每行数据，按 generate_admin_vis.py 的 build_graph 逻辑生成 (nodes, edges)
2. 计算指纹：JSON.stringify(nodes) + JSON.stringify(edges) → SHA256
3. 建立一个 Map<fingerprint, version_number>
4. 遍历每行：
   a. 如果指纹已存在 → 跳过（合并）
   b. 如果指纹不存在 → 分配下一个 version number
5. 版本号从1开始递增
6. 如仅一个版本 → 下拉显示不带版本后缀
7. 如多个版本 → 下拉显示 "[row_id] case_name v{version}"
```

---

## 4. 前端架构

### 4.1 页面布局

```
┌──────────────────────────────────────────────────┐
│  Header Bar (title, stats, case list toggle)     │
├──────────────────────────────────────────────────┤
│  Control Bar (case select, layout buttons, fit)  │
├─────────────────────┬────────────────────────────┤
│                     │                            │
│                     │   ● Detail Panel           │
│                     │   (悬停预览, 点击锁定)      │
│   Network Area      │   right: 0 on open         │
│   (vis-network)     │   width: 400px             │
│                     │   height: calc(100vh-130px) │
│                     │                            │
├─────────────────────┴────────────────────────────┤
│  ● Legend (左上角, tree hierarchy)               │
│  ● Raw Data Panel (左下角, 可折叠)               │
└──────────────────────────────────────────────────┘
```

### 4.2 组件树

```
Page
├── Header (title + stats + toggleCaseList button)
├── ControlBar
│   ├── CaseSelect (version-aware dropdown)
│   ├── VersionSelect (如果当前选中案例有多版本)
│   ├── LayoutToggle (force / hierarchical)
│   └── FitView button
├── NetworkArea (vis-network container)
├── DetailPanel (右侧，400px)
│   ├── PanelHeader (title + close)
│   └── PanelBody
│       ├── Section: 节点基本属性 (type, label, 完整名称)
│       ├── Section: 原始数据字段 (key-value)
│       └── Section: 关联关系 (出边/入边)
├── LegendPanel (左上角，树形继承图例)
├── CaseListPanel (右侧滑动面板，案件列表)
└── RawDataPanel (左下角，折叠式)
    ├── PanelHeader (toggle button)
    └── PanelBody (pre-formatted JSON 文本)
```

### 4.3 Detail Panel 交互逻辑（与 ontology_v2.2.html 一致）

```
状态机:
- 空闲: 面板隐藏
- 悬停预览: hoverNode/hoverEdge → 打开面板，不锁定
  - 不锁定时，再次悬停其他节点 → 内容切换
  - 移开后不清空（用户可阅读）
- 点击锁定: click node/edge → 打开面板，锁定
  - 锁定后悬停无效
  - 点击空白区域 → 解锁并关闭
  - 点击关闭按钮 (✕) → 解锁并关闭
  - 按 Escape → 解锁并关闭
  - 点击面板外部 → 解锁并关闭
  - 点击另一节点 → 切换到新节点，保持锁定
```

### 4.4 Legend 设计

左上角树形继承图例，与 ontology_v2.2.html 的 `buildLegend()` 一致：

```
📋 继承树
● LegalNorm系 (蓝色 #2980b9)
  ├─ GuidingCase
  └─ LegalProvision
● JudicialEntity系 (橙色 #d35400)
  ├─ CourtCase
  ├─ CaseSummary
  ├─ JudgmentResult
  └─ Evidence
● LegalSubject系 (绿色 #27ae60)
  └─ LegalSubject
```

### 4.5 原始数据面板

位置: 左下方（或图下方）
行为:
- 默认未选择案例时折叠，显示 "未选择案例"
- 选择案例后，显示该案例对应的原始 JSONL 行
- 基于 `RAW_DATA[row_id]` 查找原始 JSON 字符串
- 可折叠/展开（点击 toggle 按钮）
- 内容用 `<pre>` + `<code>` 格式化展示，适度截断（默认显示前 2000 字符，可展开全部）
- 高度限制 max-height: 300px，内部滚动

---

## 5. 数据流

```
┌─────────────────────────────────────────────────────┐
│                 generate_admin_vis.py                │
│                                                     │
│  JSONL (600行) ──▶ 按 row_id 分组 ──▶ 逐个 build    │
│  ├─ 去重合并 (指纹去重)                              │
│  ├─ 版本编号 (v1/v2/...)                            │
│  └─ 生成 RAW_DATA (原始 JSON 保留)                  │
│                                                     │
│  输出: admin_instances.html (自包含)                 │
│    ├── const ALL_GRAPHS (去重后版本组)               │
│    ├── const RAW_DATA (原始 JSON 映射)               │
│    └── 完整 HTML/CSS/JS                              │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                 frontend (admin_instances.html)      │
│                                                     │
│  页面加载 ──▶ populateSelectors()                    │
│    ├── 构建版本感知下拉框                             │
│    ├── 构建案件列表                                  │
│    └── 初始化网络 (全部或指定案例)                    │
│                                                     │
│  选择案例 ──▶ filterByCase(row_id, version?)         │
│    ├── 从 ALL_GRAPHS 查找对应版本                    │
│    ├── 重建 vis-network 数据                         │
│    ├── 更新统计                                     │
│    └── 更新原始数据面板                               │
│                                                     │
│  悬停/点击节点 ──▶ DetailPanel.show(nodeData)        │
│    ├── 显示节点类型、属性、关联关系                    │
│    └── 悬停不锁定 / 点击锁定                          │
└─────────────────────────────────────────────────────┘
```

---

## 6. 关键决策记录 (ADR)

### ADR-1: 版本信息编码方式

**决策**: 下拉框 `value` 改为 `"{row_id}__v{version}"` 格式，解析时 split 得到 row_id 和 version。

**替代方案**: 使用 row_id 后加 data attributes。被否定因为 select option 的 value 必须字符串。

### ADR-2: 去重算法位置

**决策**: 在 Python 生成器脚本中完成去重和版本分配，前端只消费结果。

**理由**: 
- 避免前端加载 600 条数据再做去重（性能）
- 版本指纹计算基于结构化 Python 对象比 JSON.stringify 可靠
- RAW_DATA 保留全部原始行，即使去重后的版本数据是合并的

### ADR-3: RAW_DATA 嵌入方式

**决策**: `const RAW_DATA = { '3358': '{"row_id":"3358",...}', ... }` — 按 row_id 聚合，仅保留首次出现的行。

**替代方案**: 按 row_id+version 保留所有原始行。被否定因为增加 HTML 体积（~5MB），且用户主要需要查看"这个 row_id 的原始数据长什么样"，版本差异可后续在 DetailPanel 展示。

**修正**: 应保留所有版本的原始数据，但仅首次出现的行较大。实际保留所有去重后每条记录对应的原始 JSONL 行，即 `RAW_DATA[row_id] = [line1, line2, ...]`，版本选择后展示对应原始行。

### ADR-4: 颜色方案 — 使用 ROOT_COLORS 映射

**决策**: 建立 `ADMIN_TYPE_TO_ROOT` 映射表，每个 admin 节点类型映射到 ontology 根父类，再查 `ROOT_COLORS`。

**理由**: 
- 保证与 ontology_v2.2.html 完全一致的色值
- 当 ontology 颜色调整时，只需更新映射表（未来可抽取公共配置）

### ADR-5: 空 row_id 处理

**决策**: row_id 为空的 100 条记录视为无效数据，在生成阶段过滤掉。

**理由**: 这些记录无法用于去重和版本管理，且没有有效标识。

---

## 7. 性能注意事项

| 关注点 | 方案 |
|--------|------|
| ALL_GRAPHS 体积 | 去重后约 471+31 个版本组 → 约 500 组，预估仍然 < 400KB |
| RAW_DATA 体积 | 按 row_id 聚合原始行，约 500KB JSON → minify 后 < 300KB |
| 网络渲染 | 全部案例模式可能 ~5000 节点，vis-network 可承受但需 stabilization |
| 版本切换 | 切换版本时重建 DataSet，不需要保留历史数据 |
| 原始数据大文本 | 预格式化截断，默认展示前 2000 字符，点击"展开全部" |

---

## 8. 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `generate_admin_vis.py` | 重写 | 新增版本聚合、去重、RAW_DATA 嵌入 |
| `admin_instances.html` | 重写 | 全新前端，保留自包含格式 |
| `visualization/ontology_v2.2.html` | 不变 | 不能修改 |
| `.hermes/plans/admin-vis-refactor-plan.md` | 新增 | 本文档 |
