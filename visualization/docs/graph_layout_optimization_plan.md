# 知识图谱布局优化设计文档 (kg_architect)

> 项目: ontology_v2.2.html — 解析知识图谱 vis-network 渲染布局优化
> 作者: kg_architect
> 日期: 2026-05-13

---

## 1. 核心设计决策：隐式(Transparent) vs 显式(Explicit)

### 方案 A：隐式 (Transparent) — 首次生成直接优化

**做法**：用户解析文本 -> 渲染 graph 时，直接套用优化布局（分层 + 聚类 + 瀑布流），不额外施加手动操作的认知负担。

**优点**：
- 0 次点击操作，体验流畅
- 用户每次看到的就是"好"的布局，减少困惑
- 视觉一致性高，适合产品化

**缺点**：
- 分层布局需要 nodeType 有明确的层级映射（须提前配好 entity level 表）
- 如果 nodeType 覆盖不全，某些节点会掉到默认层造成错位
- 聚类折叠在首次渲染时可能让用户看不到完整详情（用户可能想先看全貌）

### 方案 B：显式 (Explicit) — 用户点按钮后优化

**做法**：首次渲染使用现有 `barnesHut` 物理引擎+随机种子布局（保持现状）；右上角或工具栏新增"⚡ 一键优化"按钮，点击后执行分层+聚类+瀑布流。

**优点**：
- 保留现有行为不变，风险最低
- 用户可以对比"原始"与"优化后"的效果
- 适合实验性功能验证

**缺点**：
- 多一次点击，用户可能不知道有这个按钮
- 首次看到的是混乱布局，对产品印象有影响

### 🔍 推荐：方案 A（隐式），但提供"恢复原始布局"回退

**理由**：
1. 法律知识图谱的实体类型是**固定的有限集合**（CourtCase, Person, LegalProvision, Evidence, Judge, Attorney 等），层级映射表可以完整覆盖
2. 当前 `ENTITY_STYLES` 已有完整的 type 定义，加一个 `level` 字段即可
3. 聚类折叠可通过"展开全部"按钮解决（加在 graph toolbar 上）
4. 优化的效果（分层瀑布流）对法律知识图谱有直观意义——用户能一眼看出"案件→当事人→证据/法条"的层次关系

**兜底**：在 graph tab footer 加一个"🔄 恢复原始布局"按钮，一键切回 `barnesHut` 物理引擎模式。

---

## 2. 布局引擎选择

### 2.1 核心方案：`hierarchicalRepulsion` + 人肉 level 标定

vis-network 的 `layout.hierarchical` 模式启用分层布局，但官方分层布局会强制树状结构，不适合法律知识图谱的多对多关系网络。

**替代方案**：**伪分层力导向**

- solver 仍然用 `barnesHut` 或 `forceAtlas2Based`
- 但给每个节点预设一个 **y 坐标固定值（level）** via node-level `y` property
- 通过 `physics: { enabled: true }` + 节点固定 x/y 来实现

实际上 vis-network 不支持直接固定 y 坐标同时让 x 自由浮动。所以推荐真正的方案：

### 2.2 推荐方案：`layout.randomSeed` + 后处理坐标修正

在 `stabilizationIterationsDone` 事件中，遍历所有节点，根据 `nodeType` 重新设定 y 坐标（level），然后再次启用 physics 进行微调，最终关闭 physics。

**执行步骤**：
1. 正常用 `barnesHut` solver 进行 stabilization（保留较好的 x 方向分散度）
2. `stabilizationIterationsDone` 后，调用 `network.moveNode(nodeId, x, targetY)` 将 y 坐标修正到对应 level
3. 短暂启用 physics（solver 换为 `repulsion`，damping 调高）让 x 方向自然微调
4. 最终关闭 physics + fit

**优势**：不依赖 vis-network 的 hierarchical mode（有边反转/重叠 bug），同时实现"瀑布流"视觉效果。

### 2.3 Entity Type → Level 映射表

| Level | Y 坐标范围 | Entity Types | 说明 |
|-------|-----------|--------------|------|
| 0 | 0 ~ 50 | CaseType, CourtCase | 案由层 |
| 1 | 120 ~ 170 | GuidingCase, CaseSummary, JudgmentResult | 案件层 |
| 2 | 240 ~ 290 | Person(原告/被告), LegalRole, Judge, Attorney | 当事人/诉讼角色层 |
| 3 | 360 ~ 410 | Evidence, LegalSubject | 证据层 |
| 4 | 480 ~ 530 | LegalProvision, Law, LegalNorm | 法条/法律依据层 |
| 5 | 600 ~ 650 | (其他未识别/兜底) | 最底层 |

**实现方式**：在 `renderTermVis` 函数内新增一个 `LEVEL_MAP` 对象：

```js
var LEVEL_MAP = {
  CaseType:        0,
  CourtCase:       0,
  GuidingCase:     1,
  CaseSummary:     1,
  JudgmentResult:  1,
  Person:          2,
  LegalRole:       2,
  Judge:           2,
  Attorney:        2,
  Evidence:        3,
  LegalSubject:    3,
  LegalProvision:  4,
  Law:             4,
  LegalNorm:       4,
};
var DEFAULT_LEVEL = 5;
```

---

## 3. 节点分组聚类 (Clustering)

### 3.1 聚类策略

对**同类型且同 level 的相邻节点**进行聚类折叠。具体：

- **Judge（法官）**：如果有 >= 3 个法官节点且相互有边连接到同一个案件，折叠为 1 个"法官组"节点
- **Attorney（律师）**：同上
- **Evidence（证据）**：如果同案件的证据 > 3 个，折叠为"证据组"

### 3.2 实现方式

利用 vis-network 的 `clusteringByGroup` 机制或手动 `cluster()` API。

**手动聚类**（推荐，可控性更强）：

```js
function applyClustering(network, nodes, edges) {
  var clusterTargets = ['Judge', 'Attorney', 'Evidence'];
  clusterTargets.forEach(function(type) {
    var sameTypeNodes = nodes.filter(function(n) {
      return (n.nodeType || n.group) === type;
    });
    if (sameTypeNodes.length >= 3) {
      network.clustering.cluster({
        joinCondition: function(nodeOptions) {
          return nodeOptions.nodeType === type;
        },
        clusterNodeProperties: {
          id: 'cluster_' + type,
          label: type + '组 (' + sameTypeNodes.length + ')',
          shape: 'box',
          color: { background: '#95a5a6', border: '#7f8c8d' },
        },
      });
    }
  });
}
```

### 3.3 展开聚类

用户双击聚类节点或点击节点上的"展开"按钮，展开聚类。vis-network 默认支持 `clusterNodeProperties.allowSingleNodeCluster: false`，双击会自动展开。

---

## 4. 瀑布流布局（层级 + 力导向混合）

### 4.1 瀑布流算法

```
稳定后修正 Y 坐标
     │
     ▼
遍历所有节点 node → 查 LEVEL_MAP[nodeType] → 计算 targetY
     │
     ├── Level 层内 Y 坐标添加 (±random*20) 微偏移，避免完全重叠
     │
     ▼
network.moveNode(nodeId, curX, targetY)
     │
     ▼
短暂启用 physics (repulsion, damping=0.9, iterations=30)
     │
     ▼
关闭 physics → fit()
```

### 4.2 伪代码

```js
termVisNetwork.on('stabilizationIterationsDone', function() {
  // ── Step 1: 关闭物理引擎 ──
  termVisNetwork.setOptions({ physics: { enabled: false } });

  // ── Step 2: 按 nodeType 固定 Y 坐标（瀑布流分层） ──
  visNodes.forEach(function(node) {
    var level = LEVEL_MAP[node.nodeType] !== undefined
      ? LEVEL_MAP[node.nodeType]
      : DEFAULT_LEVEL;
    var baseY = level * 130 + 30;
    var yOffset = (Math.random() - 0.5) * 20;  // 层内微偏移
    termVisNetwork.moveNode(node.id, null, baseY + yOffset);
  });

  // ── Step 3: 短暂启用 physics（repulsion 模式）让 X 方向自然展开 ──
  termVisNetwork.setOptions({
    physics: {
      enabled: true,
      solver: 'repulsion',
      repulsion: { nodeDistance: 150, centralGravity: 0.05, springLength: 200, damping: 0.9 },
      stabilization: { iterations: 30, fit: false },
    }
  });

  // ── Step 4: 等待二次稳定后再冻结 ──
  termVisNetwork.once('stabilizationIterationsDone', function() {
    termVisNetwork.setOptions({ physics: { enabled: false } });
    termVisNetwork.fit({ animation: true });
  });
});
```

### 4.3 如果采用显式方案（备选）

若出于风险评估选用方案 B（显式），则布局优化代码提取为独立函数：

```js
function optimizeGraphLayout() {
  if (!termVisNetwork) return;
  // 同上 Step 1~4 的逻辑
}
```

并将 `optimizeGraphLayout` 绑定到新增按钮 `btnLayoutOptimize`。

---

## 5. 详细技术实现方案

### 5.1 改动文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `ontology_v2.2.html` | **修改** | 仅改动此一个文件 |

### 5.2 具体改动点

#### 改动点 A：HTML 结构 — 按钮组 (约 +5 行)

位置：`line 2028~2030`（`term-tab-footer` 区域）

**当前**：
```html
<div class="term-tab-footer">
  <button class="btn-tab-regen" id="btnGraphRegen" onclick="regenGraph()" disabled style="display:none;">🔄 重新生成</button>
</div>
```

**改为**：
```html
<div class="term-tab-footer">
  <button class="btn-tab-regen" id="btnGraphRegen" onclick="regenGraph()" disabled style="display:none;">🔄 重新生成</button>
  <button class="btn-tab-regen" id="btnResetLayout" onclick="resetGraphLayout()" disabled style="display:none;">↩ 恢复原始布局</button>
</div>
```

若采用显式方案（方案 B），额外加：
```html
<button class="btn-tab-regen" id="btnLayoutOptimize" onclick="optimizeGraphLayout()" disabled style="display:none;">⚡ 一键优化</button>
```

#### 改动点 B：新增布局配置（~8 行）

在 `renderTermVis` 函数内（约 line 2287），构建 visNodes 之前，新增：

```js
// ── 布局层级映射（瀑布流 Y 坐标） ──
var LEVEL_MAP = {
  CaseType:        0,
  CourtCase:       0,
  GuidingCase:     1,
  CaseSummary:     1,
  JudgmentResult:  1,
  Person:          2,
  LegalRole:       2,
  Judge:           2,
  Attorney:        2,
  Evidence:        3,
  LegalSubject:    3,
  LegalProvision:  4,
  Law:             4,
  LegalNorm:       4,
};
var DEFAULT_LEVEL = 5;
```

#### 改动点 C：节点数据中注入 nodeType（~4 行）

当前 `renderTermVis` 的 `nodes.map()` 中（line 2290~2312），已从 `n.nodeType || n.group` 读取 nodeType。确保 nodeType 传递到 vis node 的 `nodeType` 属性（用于聚类判断）。

保留已有逻辑，仅需确认 `nodeType` 字段写入 visNode：

```js
// 已有这行，无需改动
nodeType: n.nodeType || n.group || '',
```

#### 改动点 D：stabilization 后处理逻辑（~25 行）

将 line 2337~2339 原有的简单冻结逻辑：

```js
termVisNetwork.on('stabilizationIterationsDone', function() {
  termVisNetwork.setOptions({ physics: { enabled: false } });
  termVisNetwork.fit({ animation: true });
});
```

替换为完整的瀑布流布局优化逻辑（详见 4.2 节伪代码）。

#### 改动点 E：恢复原始布局函数（~10 行）

新增 `resetGraphLayout()` 函数，通过重新初始化网络来恢复到原始的 barnesHut 布局：

```js
function resetGraphLayout() {
  if (!termLastResult) return;
  // 临时关闭布局优化标志，重新渲染
  var btn = document.getElementById('btnResetLayout');
  btn.disabled = true;
  __SKIP_LAYOUT_OPTIMIZE = true;
  renderTermVis(termLastResult.nodes, termLastResult.edges);
  __SKIP_LAYOUT_OPTIMIZE = false;
  setTimeout(function() { btn.disabled = false; }, 500);
}
```

在 `renderTermVis` 顶部加：

```js
if (typeof __SKIP_LAYOUT_OPTIMIZE === 'undefined') var __SKIP_LAYOUT_OPTIMIZE = false;
```

根据 `__SKIP_LAYOUT_OPTIMIZE` 标志决定是否执行瀑布流优化。

#### 改动点 F：启用按钮（~2 行）

在 `renderTermVis` 末尾（line 2342~2344），`btnGraphRegen` 启用之后：

```js
var resetBtn = document.getElementById('btnResetLayout');
resetBtn.disabled = false;
resetBtn.style.display = 'inline-block';
```

#### 改动点 G：聚类函数（~20 行）

新增 `applyClustering()` 函数，在 stabilization 优化完成后调用（可选，默认聚类）：

```js
function applyClustering(network, nodes) {
  var clusterTypes = ['Judge', 'Attorney', 'Evidence'];
  clusterTypes.forEach(function(type) {
    var count = nodes.filter(function(n) {
      return (n.nodeType || n.group) === type;
    }).length;
    if (count >= 3) {
      network.clustering.cluster({
        joinCondition: function(nodeOpts) {
          return nodeOpts.nodeType === type;
        },
        clusterNodeProperties: {
          id: 'cluster_' + type,
          label: type + '组 (' + count + ')',
          shape: 'box',
          color: { background: '#95a5a6', border: '#7f8c8d' },
          font: { size: 12, color: '#fff' },
        },
        processProperties: function(clusterProps, childNodes) {
          return clusterProps;
        }
      });
    }
  });
}
```

### 5.3 不改动的文件

| 文件 | 原因 |
|------|------|
| `admin_instances.html` | 管理界面，不涉及图谱渲染 |
| 后端 API 代码 | 布局优化纯前端，后端无改动 |
| CSS 样式文件 (无) | 所有样式内联在 `ontology_v2.2.html` 中 |

---

## 6. 预估工作量

| 改动项 | 预估行数 | 难度 |
|--------|---------|------|
| A: 按钮 HTML | +5 | 低 |
| B: LEVEL_MAP 配置 | +8 | 低 |
| C: nodeType 注入 | 0（已有） | 无 |
| D: stabilization 后处理 | -2 +25 = +23 | 中 |
| E: resetGraphLayout 函数 | +10 | 低 |
| F: 按钮启用逻辑 | +2 | 低 |
| G: 聚类函数 | +20 | 中 |
| **合计** | **~+68 行** （净增） | 低~中 |

**影响范围**：仅 `ontology_v2.2.html` 一个文件，改动集中在 ~2280~2400 行区间（renderTermVis 函数及周边），不波及 ontology 主图（~700~800 行区域）。

---

## 7. 验收标准

### 7.1 功能验收

| # | 验收项 | 通过条件 |
|---|--------|---------|
| 1 | 瀑布流分层 | 解析后的知识图谱节点按"案由→案件→当事人→证据→法条"在 Y 轴方向分层排列，同类节点在同一水平带 |
| 2 | 层内分散 | 同层节点在 X 方向自然分散，不重叠 |
| 3 | 边交叉减少 | 优化后图中边交叉数量较纯物理引擎布局**明显减少**（目测减少 > 50%） |
| 4 | 聚类折叠 | 法官/律师/证据节点 >= 3 个时自动折叠为组节点，组节点标签显示计数（如"法官组 (3)"） |
| 5 | 聚类展开 | 双击聚类节点展开为原始节点 |
| 6 | 恢复原始布局 | 点击"↩ 恢复原始布局"按钮后回到原始的 barnesHut 物理引擎布局 |
| 7 | 重新生成兼容 | 点击"🔄 重新生成"后，新图仍应用优化布局 |
| 8 | 自适应视口 | 布局优化后 fit() 正常工作，图完整可见 |
| 9 | 交互不破坏 | 优化后 hover/click/drag/zoom 等交互行为正常 |

### 7.2 性能验收

| # | 验收项 | 通过条件 |
|---|--------|---------|
| 1 | 首次渲染时间 | stabilization 总迭代次数不变（200 次）+ 二次微调 30 次，总延迟增加 < 500ms |
| 2 | 大图负载 | 100 节点 + 200 边的场景下，布局优化正常完成，不卡死 |
| 3 | 聚类性能 | 聚类操作不造成 vis-network 内部错误 |

### 7.3 视觉验收

```
期望效果（文本示意）：

  Level 0 [案由层]     ⬥CaseType         ⬥CourtCase
  Level 1 [案件层]         ⬛CaseSummary        ⬛GuidingCase
  Level 2 [当事人层]    ■Person(原告)  ■Person(被告)  ◆LegalRole  ●Judge  ●Attorney
  Level 3 [证据层]          ⬡Evidence           ⬡Evidence
  Level 4 [法条层]          ⬡LegalProvision      ⬡Law
```

---

## 8. 风险与备选方案

| 风险 | 影响 | 缓解/备选 |
|------|------|----------|
| `moveNode` 在 stabilization 期间调用可能被覆盖 | 布局错乱 | 在 stabilization 完成后（physics disabled 时）才调用 moveNode |
| 二次 stabilization 的 30 次迭代不够 x 方向展开 | 节点拥挤 | 增加 iterations 到 60，或改用 `solver: 'forceAtlas2Based'` |
| 聚类后节点详情查看不便 | 用户看不清子节点 | 双击展开 / 悬停显示 tooltip 显示子节点列表 |
| 部分实体 type 不在 LEVEL_MAP 中 | 掉到底层 | 兜底到 DEFAULT_LEVEL=5；在 console.warn 中提示缺失 type |

---

## 9. 迭代建议

1. **Phase 1（当前）**：实现瀑布流分层 + 恢复原始布局按钮（不含聚类）
2. **Phase 2**：加入聚类折叠功能
3. **Phase 3**：支持用户自定义 level 映射（通过配置面板拖拽）

---

*文档结束*
