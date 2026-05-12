# 行政案例可视化重构 — 实现任务看板

> 基于 `admin-vis-refactor-plan.md` 架构设计。按依赖顺序排列。
> 预估: 5-7 个任务点，总工作量约2-3天。

---

## 📋 任务总览

| 优先级 | 状态 | 任务 | 领域 | 预估工时 |
|--------|------|------|------|----------|
| P0 | ⬜ TODO | #1 更新 generate_admin_vis.py — 数据模型 + 去重 + 版本 + RAW_DATA | Python/数据 | 4h |
| P0 | ⬜ TODO | #2 更新 HTML 模板 — CSS 重构 + 新布局结构 | CSS/HTML | 2h |
| P0 | ⬜ TODO | #3 更新 HTML 模板 — Detail Panel (右侧悬停/点击面板) | JS | 3h |
| P0 | ⬜ TODO | #4 更新 HTML 模板 — Legend (左上角继承树形图例) | JS/CSS | 1.5h |
| P0 | ⬜ TODO | #5 更新 HTML 模板 — 颜色体系切换 (ROOT_COLORS 映射) | JS | 1h |
| P0 | ⬜ TODO | #6 版本感知下拉框 + 版本选择器 + 去重案例数据展示 | JS | 2.5h |
| P1 | ⬜ TODO | #7 原始数据面板 (左下角可折叠JSON展示) | JS/CSS | 2h |
| P1 | ⬜ TODO | #8 集成测试 + 数据验证 | 测试 | 1.5h |
| P1 | ⬜ TODO | #9 清理/空 row_id 过滤逻辑验证 | 数据 | 0.5h |

---

## 🔨 任务: #1 更新 generate_admin_vis.py — 数据模型升级

**领域**: Python / 数据处理
**依赖**: 无
**预估**: 4h

### 子步骤

#### 1.1 过滤空 row_id
- 当前 JSONL 中有 100 条 `row_id=""` 的记录
- 在读取循环中跳过 `if not data['row_id']: continue`
- ✅ 验证: 去重前记录数从 600 减少到 ~500

#### 1.2 按 row_id 分组
- 构建 `{row_id: [record1, record2, ...]}` 字典
- 每个 row_id 可能对应 1~2 条记录
- ✅ 验证: 31 个 row_id 有重复，其余唯一

#### 1.3 提取构建函数为独立方法
- 将现有的 graph-building 逻辑（L35-L185）提取为函数：
  ```python
  def build_graph(record: dict) -> dict:
      """Extract nodes/edges from a single JSONL record.
      Returns {'row_id': str, 'case_name': str, 'case_type': str, 'nodes': list, 'edges': list}
      """
  ```

#### 1.4 实现版本指纹去重
```python
import hashlib
def compute_fingerprint(nodes, edges):
    """SHA256 of normalized JSON"""
    normalized = json.dumps(nodes, sort_keys=True, ensure_ascii=False) + \
                 json.dumps(edges, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

def deduplicate_versions(records):
    """Group by row_id, deduplicate by fingerprint, assign version numbers."""
    groups = {}
    for r in records:
        rid = r['row_id']
        g = build_graph(r)
        fp = compute_fingerprint(g['nodes'], g['edges'])
        if rid not in groups:
            groups[rid] = {}
        if fp not in groups[rid]:
            groups[rid][fp] = {'version': len(groups[rid]) + 1, 'graph': g, 'raw_record': r}
    # Build versioned groups
    result = []
    for rid, fp_map in groups.items():
        versions = sorted(fp_map.values(), key=lambda x: x['version'])
        first_graph = versions[0]['graph']
        result.append({
            'row_id': rid,
            'case_name': first_graph['case_name'],
            'case_type': first_graph['case_type'],
            'versions': [
                {
                    'version': v['version'],
                    'fingerprint': fp,
                    'nodes': v['graph']['nodes'],
                    'edges': v['graph']['edges']
                }
                for fp, v in sorted(fp_map.items(), key=lambda x: x[1]['version'])
            ]
        })
    return result
```

#### 1.5 构建 VERSIONED_INDICES（下拉框索引）
```python
versioned_indices = []
for group in groups:
    if len(group['versions']) == 1:
        versioned_indices.append({
            'row_id': group['row_id'],
            'case_name': group['case_name'],
            'version': 1,
            'display': f"[{group['row_id']}] {group['case_name']}"
        })
    else:
        for v in group['versions']:
            versioned_indices.append({
                'row_id': group['row_id'],
                'case_name': group['case_name'],
                'version': v['version'],
                'display': f"[{group['row_id']}] {group['case_name']} v{v['version']}"
            })
```

#### 1.6 构建 RAW_DATA 映射
```python
# 每个去重后的版本对应一条原始 JSONL 行
raw_data = {}
for rid, fp_map in groups.items():
    raw_data[rid] = {}
    for fp, v in fp_map.items():
        raw_line = json.dumps(v['raw_record'], ensure_ascii=False)
        raw_data[rid][v['version']] = raw_line
```

#### 1.7 修改 HTML 生成逻辑
- 将 `html_parts` 中的常量改为嵌入三个变量：
  ```javascript
  const ALL_GRAPHS = {{groups_json}};
  const VERSIONED_INDICES = {{indices_json}};
  const RAW_DATA = {{raw_data_json}};
  ```
- 去除旧的 `getCaseColor()` 和朴素的颜色 palette 代码

#### 1.8 验证输出
- 运行 `python3 generate_admin_vis.py`
- 检查 `admin_instances.html` 是否生成成功
- 验证 ALL_GRAPHS 结构: 每个元素有 `versions[]`
- 验证 RAW_DATA 大小合理（不要超过 ~300KB）
- ✅ 输出文件大小对比: 原 ~379KB，新预计 ~500-700KB

---

## 🔨 任务: #2 HTML 模板 — CSS 重构 + 布局

**领域**: CSS / HTML
**依赖**: #1 (需要生成的文件测试)
**预估**: 2h

### 子步骤

#### 2.1 更新页面结构
```html
<body>
  <div class="header">...</div>
  <div class="control-bar">...</div>
  <div id="mynetwork">...</div>
  <div class="legend" id="legendPanel">  <!-- 左上角, 新样式 -->
  </div>
  <div id="detailPanel">  <!-- 右侧, 从 ontology 复制样式 -->
  </div>
  <div id="rawDataPanel">  <!-- 左下角, 新面板 -->
    <div class="raw-data-header" onclick="toggleRawData()">
      <span>📄 原始数据</span>
      <span class="raw-data-toggle">▶</span>
    </div>
    <div class="raw-data-body" id="rawDataBody">
      <pre><code id="rawDataContent">未选择案例</code></pre>
    </div>
  </div>
  <div class="case-list-panel" id="caseListPanel">...</div>
</body>
```

#### 2.2 从 ontology_v2.2.html 移植 Detail Panel CSS
- `#detailPanel` 及其子元素样式（position, transition, panel-header, panel-body, field-row, section-title, rel-item, inherit-chain, constraint-item 等）
- 保留 `.edge-mode` 变体
- 调整 top 值适配 admin 的 header 高度（44px vs admin 的 ~60px）

#### 2.3 从 ontology_v2.2.html 移植 Legend CSS
- `.legend` fixed positioning: top: 60px, left: 16px
- `.legend-root`, `.legend-children`, `.legend-child`, `.dot`, `.child-dot`
- 自定义滚动条样式

#### 2.4 新增 Raw Data Panel CSS
```css
#rawDataPanel {
  position: fixed; bottom: 20px; left: 20px; z-index: 5;
  background: rgba(255,255,255,0.96); border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.12);
  font-size: 12px; max-width: 45vw; max-height: 35vh;
  overflow: hidden;
}
#rawDataPanel .raw-data-header {
  padding: 8px 14px; cursor: pointer; display: flex;
  justify-content: space-between; align-items: center;
  background: #f5f5f5; border-radius: 8px 8px 0 0;
  font-weight: 600; font-size: 13px;
  user-select: none;
}
#rawDataPanel .raw-data-body {
  max-height: 300px; overflow-y: auto; padding: 8px 14px;
  display: none;
}
#rawDataPanel.open .raw-data-body { display: block; }
#rawDataPanel pre { margin: 0; white-space: pre-wrap; word-break: break-all; }
#rawDataPanel code { font-family: 'SFMono-Regular', Consolas, monospace; font-size: 11px; color: #333; line-height: 1.5; }
```

#### 2.5 版本选择器 UI
```html
<!-- 在 control-bar 中，caseSelect 旁边 -->
<select id="versionSelect" style="display:none;" onchange="filterByVersion(this.value)">
  <option value="1">版本 1</option>
</select>
```
- 默认隐藏，仅当选中多版本案例时显示
- label: "版本："

#### 2.6 调整网络区域高度
- `#mynetwork` height: `calc(100vh - 130px)` (header + control bar)
- 移除旧 case-list-panel 固定样式，保留暗色 header

---

## 🔨 任务: #3 Detail Panel (右侧悬停/点击面板)

**领域**: JavaScript
**依赖**: #2 (CSS 已就位)
**预估**: 3h

### 子步骤

#### 3.1 实现 Detail Panel 类/状态管理
```javascript
const detailPanel = document.getElementById('detailPanel');
const panelTitle = document.getElementById('panelTitle');
const panelBody = document.getElementById('panelBody');
const panelClose = document.getElementById('panelClose');
let isDetailLocked = false;
let currentDetailSelection = null;
```

#### 3.2 事件绑定（与 ontology 完全一致的行为）
```javascript
panelClose.addEventListener('click', (e) => { e.stopPropagation(); hideDetailPanel(); });
document.addEventListener('click', (e) => {
  if (isDetailLocked && !detailPanel.contains(e.target) && e.target !== panelClose) {
    hideDetailPanel();
  }
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && detailPanel.classList.contains('open')) hideDetailPanel();
});
detailPanel.addEventListener('mousedown', (e) => e.stopPropagation());
detailPanel.addEventListener('mouseup', (e) => e.stopPropagation());
detailPanel.addEventListener('click', (e) => e.stopPropagation());
```

#### 3.3 Hover 事件（预览，不锁定）
```javascript
network.on('hoverNode', (params) => {
  if (isDetailLocked) return;
  const key = 'node:' + params.node;
  if (key === currentDetailSelection) return;
  detailPanel.classList.remove('edge-mode');
  renderNodeDetail(params.node);
  detailPanel.classList.add('open');
  currentDetailSelection = key;
});
network.on('hoverEdge', (params) => {
  if (isDetailLocked) return;
  const key = 'edge:' + params.edge;
  if (key === currentDetailSelection) return;
  detailPanel.classList.add('edge-mode');
  renderEdgeDetail(params.edge);
  detailPanel.classList.add('open');
  currentDetailSelection = key;
});
```

#### 3.4 Click 事件（锁定）
```javascript
network.on('click', (params) => {
  if (params.nodes.length > 0) {
    detailPanel.classList.remove('edge-mode');
    renderNodeDetail(params.nodes[0]);
    detailPanel.classList.add('open');
    isDetailLocked = true;
    currentDetailSelection = 'node:' + params.nodes[0];
  } else if (params.edges.length > 0) {
    detailPanel.classList.add('edge-mode');
    renderEdgeDetail(params.edges[0]);
    detailPanel.classList.add('open');
    isDetailLocked = true;
    currentDetailSelection = 'edge:' + params.edges[0];
  } else {
    if (isDetailLocked) hideDetailPanel();
  }
});
```

#### 3.5 节点详细信息渲染
`renderNodeDetail(nodeId)` 显示:
- 节点类型 / 节点名称（完整 case_name，不截断）
- 从 node.title 解析 HTML 内容放入面板
- 关联的出边/入边列表（通过遍历 edgesDataset 查找所有连接该节点的边）
- 每个关联边可点击 → focus 目标节点

#### 3.6 边详细信息渲染
`renderEdgeDetail(edgeId)` 显示:
- 边 label（关系类型）
- from → to 方向
- 关系类型中文名

---

## 🔨 任务: #4 继承树形图例 (左上角)

**领域**: JavaScript / CSS
**依赖**: #2 (CSS 已就位)
**预估**: 1.5h

### 子步骤

#### 4.1 从 ontology 移植 buildLegend 逻辑
- 复制 `buildLegend()` 函数结构
- 适配 admin 实体类型（仅 7 种类型，非 ontology 的 ~28 种）
- 硬编码继承关系：

```javascript
const ADMIN_ROOT_COLORS = {
  'LegalNorm': { bg: '#2980b9', border: '#1a5276', label: '规范层' },
  'JudicialEntity': { bg: '#d35400', border: '#a04000', label: '司法实体层' },
  'LegalSubject': { bg: '#27ae60', border: '#1e8449', label: '主体层' }
};

// Entity → root type mapping
const ADMIN_TYPE_ROOT = {
  'GuidingCase': 'LegalNorm',
  'LegalProvision': 'LegalNorm',
  'CourtCase': 'JudicialEntity',
  'CaseSummary': 'JudicialEntity',
  'JudgmentResult': 'JudicialEntity',
  'Evidence': 'JudicialEntity',
  'LegalSubject': 'LegalSubject'
};

// Type to Chinese label
const ADMIN_ZH_LABELS = {
  'GuidingCase': '指导性案例/典型案例',
  'LegalProvision': '法律条文',
  'CourtCase': '法院案件',
  'CaseSummary': '案件类型摘要',
  'JudgmentResult': '裁判结果',
  'Evidence': '证据材料',
  'LegalSubject': '诉讼主体'
};
```

#### 4.2 生成图例 HTML
```javascript
function buildAdminLegend() {
  const roots = ['LegalNorm', 'JudicialEntity', 'LegalSubject'];
  // Group children under each root
  const children = { LegalNorm: [], JudicialEntity: [], LegalSubject: [] };
  for (const [type, root] of Object.entries(ADMIN_TYPE_ROOT)) {
    children[root].push(type);
  }
  let html = '<div class="legend-title">📋 继承树</div>';
  for (const root of roots) {
    const c = ADMIN_ROOT_COLORS[root];
    html += `<div class="legend-root"><span class="dot" style="background:${c.bg}"></span><span>${c.label} (${root})</span></div>`;
    html += '<div class="legend-children">';
    for (const child of children[root].sort()) {
      const zh = ADMIN_ZH_LABELS[child] || child;
      html += `<div class="legend-child"><span class="child-dot" style="background:${c.bg}"></span><span>${zh}</span></div>`;
    }
    html += '</div>';
  }
  html += '<div style="margin-top:8px;font-size:10px;color:#aaa;">🖱 悬停/点击查看详情</div>';
  document.getElementById('legendPanel').innerHTML = html;
}
```

#### 4.3 在 stabilizationIterationsDone 后调用

---

## 🔨 任务: #5 颜色体系切换 (ROOT_COLORS 映射)

**领域**: JavaScript
**依赖**: #2
**预估**: 1h

### 子步骤

#### 5.1 替换 TYPE_COLORS
- 删除旧的 `TYPE_COLORS`（固定的 e91e63/4caf50 等）
- 替换为基于 `ADMIN_TYPE_ROOT` + `ADMIN_ROOT_COLORS` 的颜色函数

```javascript
function getAdminNodeColor(type) {
  const root = ADMIN_TYPE_ROOT[type];
  if (!root || !ADMIN_ROOT_COLORS[root]) {
    return { background: '#7f8c8d', border: '#5d6d7e' };
  }
  return { background: ADMIN_ROOT_COLORS[root].bg, border: ADMIN_ROOT_COLORS[root].border };
}
```

#### 5.2 删除旧的 getCaseColor / lightenColor
- 不再需要按 row_id 分配颜色（全部案例用同一配色）
- 删除 `getCaseColor()`、`lightenColor()`、palette 数组

#### 5.3 更新 buildVisData
- 节点颜色逻辑改为：
```javascript
const nc = getAdminNodeColor(n.type);
const color = {
  background: nc.background,
  border: nc.border,
  highlight: { background: lightenColor(nc.background, 20), border: nc.border }
};
```
- 保留 lightenColor 但仅用于 highlight，不移除

#### 5.4 更新边颜色
- 删除旧的 `EDGE_COLORS` 映射
- 使用统一的灰色系 `#95a5a6` 或根据 from/to 节点类型的主色
- 建议: 保留 EDGE_COLORS 但统一为 `#7f8c8d` (ontology 风格)，去掉五彩缤纷

#### 5.5 删除旧图例
- 底部旧 `.legend` 删除
- 替换为左上角新图例

---

## 🔨 任务: #6 版本感知下拉框 + 版本选择器

**领域**: JavaScript
**依赖**: #1 (数据结构), #2 (UI 元素)
**预估**: 2.5h

### 子步骤

#### 6.1 重写 populateSelectors
```javascript
function populateSelectors() {
  const select = document.getElementById('caseSelect');
  const listScroll = document.getElementById('caseListScroll');
  
  // Clear
  select.innerHTML = '<option value="all">📌 全部案例</option>';
  
  // Build sorted unique groups (使用 ALL_GRAPHS 而非 VERSIONED_INDICES)
  const sorted = ALL_GRAPHS.slice().sort((a, b) => parseInt(a.row_id) - parseInt(b.row_id));
  
  for (const group of sorted) {
    const hasMultipleVersions = group.versions.length > 1;
    if (!hasMultipleVersions) {
      // Single version — normal option
      const opt = document.createElement('option');
      opt.value = group.row_id;
      opt.textContent = `[${group.row_id}] ${group.case_name}`;
      select.appendChild(opt);
    } else {
      // Multiple versions — use compound key
      for (const v of group.versions) {
        const opt = document.createElement('option');
        opt.value = `${group.row_id}__v${v.version}`;
        opt.textContent = `[${group.row_id}] ${group.case_name} v${v.version}`;
        opt.dataset.rowId = group.row_id;
        opt.dataset.version = v.version;
        select.appendChild(opt);
      }
    }
  }
}
```

#### 6.2 解析版本 selection
```javascript
function parseCaseSelection(value) {
  if (value === 'all') return { rowId: 'all', version: null };
  const match = value.match(/^(.+)__v(\d+)$/);
  if (match) return { rowId: match[1], version: parseInt(match[2]) };
  return { rowId: value, version: null };
}
```

#### 6.3 更新 filterByCase
```javascript
function filterByCase(value) {
  currentFilter = value;
  const sel = parseCaseSelection(value);
  const group = sel.rowId !== 'all' ? ALL_GRAPHS.find(g => g.row_id === sel.rowId) : null;
  
  // Show/hide version selector
  const versionSelect = document.getElementById('versionSelect');
  if (group && group.versions.length > 1 && sel.version === null) {
    // Show version selector, default to v1
    versionSelect.style.display = 'inline-block';
    populateVersionSelect(group, sel);
  } else if (group && group.versions.length > 1 && sel.version !== null) {
    versionSelect.style.display = 'inline-block';
    populateVersionSelect(group, sel);
  } else {
    versionSelect.style.display = 'none';
  }
  
  initNetwork(sel);
}
```

#### 6.4 版本选择器
```javascript
function populateVersionSelect(group, currentSel) {
  const sel = document.getElementById('versionSelect');
  sel.innerHTML = '';
  for (const v of group.versions) {
    const opt = document.createElement('option');
    opt.value = v.version;
    opt.textContent = `版本 ${v.version}`;
    sel.appendChild(opt);
  }
  sel.value = currentSel.version || 1;
}

function filterByVersion(version) {
  const sel = parseCaseSelection(currentFilter);
  const newValue = `${sel.rowId}__v${version}`;
  document.getElementById('caseSelect').value = newValue;
  filterByCase(newValue);
}
```

#### 6.5 更新 buildVisData 接受版本参数
```javascript
function buildVisData(selection) {
  // selection: { rowId: string|null, version: number|null }
  const visNodes = [];
  const visEdges = [];
  const nodeSet = new Set();
  const edgeSet = new Set();

  let filtered = ALL_GRAPHS;
  if (selection.rowId && selection.rowId !== 'all') {
    filtered = ALL_GRAPHS.filter(g => g.row_id === selection.rowId);
  }

  for (const group of filtered) {
    let versionsToRender = group.versions;
    if (selection.version) {
      versionsToRender = group.versions.filter(v => v.version === selection.version);
    }
    // ... rest unchanged but use versionsToRender[0].nodes/.edges
  }
}
```

#### 6.6 更新 initNetwork 签名
```javascript
function initNetwork(selection) {
  // selection: { rowId, version } or null (for 'all')
  ...
  const data = buildVisData(selection);
  ...
}
```

#### 6.7 更新 selectFromList
```javascript
function selectFromList(rowId) {
  const group = ALL_GRAPHS.find(g => g.row_id === rowId);
  if (group && group.versions.length > 1) {
    filterByCase(`${rowId}__v1`);  // Default to v1
  } else {
    filterByCase(rowId);
  }
  document.getElementById('caseListPanel').classList.remove('open');
}
```

---

## 🔨 任务: #7 原始数据面板 (左下角)

**领域**: JavaScript / CSS
**依赖**: #1 (RAW_DATA), #2 (CSS 已就位)
**预估**: 2h

### 子步骤

#### 7.1 面板 HTML 结构（已在任务 #2 中定义）

#### 7.2 面板 JS 逻辑
```javascript
let isRawDataOpen = false;

function toggleRawData() {
  isRawDataOpen = !isRawDataOpen;
  document.getElementById('rawDataPanel').classList.toggle('open', isRawDataOpen);
  const toggle = document.querySelector('.raw-data-toggle');
  if (toggle) toggle.textContent = isRawDataOpen ? '▼' : '▶';
}

function updateRawData(rowId, version) {
  const content = document.getElementById('rawDataContent');
  if (!rowId || rowId === 'all') {
    content.textContent = '请选择一个案例查看原始数据';
    return;
  }
  const rawVersions = RAW_DATA[rowId];
  if (!rawVersions) {
    content.textContent = `未找到 row_id=${rowId} 的原始数据`;
    return;
  }
  const line = rawVersions[version] || rawVersions[Object.keys(rawVersions)[0]];
  if (line) {
    try {
      const parsed = JSON.parse(line);
      content.textContent = JSON.stringify(parsed, null, 2);
    } catch {
      content.textContent = line;
    }
  } else {
    content.textContent = '无原始数据';
  }
}
```

#### 7.3 在 filterByCase 末尾调用 updateRawData
```javascript
// 在 initNetwork 之后:
updateRawData(sel.rowId, sel.version || 1);
```

#### 7.4 全部案例模式
- 选择"全部案例"时，显示 "多案例模式，请选择单个案例查看原始数据"
- 不自动展开面板

---

## 🔨 任务: #8 集成测试 + 数据验证

**领域**: 测试
**依赖**: #1 ~ #7
**预估**: 1.5h

### 子步骤

#### 8.1 生成测试
```bash
cd /root/remote-test && python3 generate_admin_vis.py
```
验证:
- ✅ 输出文件存在且非空
- ✅ HTML 文件大小合理（< 1MB）
- ✅ ALL_GRAPHS 中每个元素含有 `versions` 数组

#### 8.2 去重逻辑验证
```python
# 验证: 31 个重复 row_id 正确处理
# 验证: fingerprints computed correctly
# 验证: version numbers assigned correctly
```

#### 8.3 RAW_DATA 完整性验证
```python
# 验证: 每个 row_id 在 RAW_DATA 中有对应条目
# 验证: RAW_DATA 内容为有效 JSON
```

---

## 🔨 任务: #9 空 row_id 过滤验证

**领域**: 数据
**依赖**: #1
**预估**: 0.5h

### 子步骤

#### 9.1 确认过滤逻辑
- `generate_admin_vis.py` 中加入: `if not data['row_id']: continue`
- 验证: 不再生成空 row_id 的案例
- 验证: 不影响其他正常案例

#### 9.2 验证过滤后的总数
- 过滤前 600 条，过滤后 ~500 条
- 37 个 admin row_ids 全部保留

---

## 📐 组件接口定义

### ALL_GRAPHS 结构
```typescript
interface CaseVersionGroup {
  row_id: string;
  case_name: string;
  case_type: string;
  versions: CaseVersion[];
}

interface CaseVersion {
  version: number;        // 1, 2, 3...
  fingerprint: string;    // SHA256 hex
  nodes: Node[];
  edges: Edge[];
}
```

### RAW_DATA 结构
```typescript
type RawDataMap = Record<string, Record<number, string>>;
// RAW_DATA['3358'] = { 1: '{"row_id":"3358",...}', 2: '{"row_id":"3358",...}' }
```

### 内部状态
```typescript
interface AppState {
  currentFilter: string;                  // 'all' | row_id | 'row_id__vN'
  isDetailLocked: boolean;
  isRawDataOpen: boolean;
  network: vis.Network | null;
  nodesDataset: vis.DataSet | null;
  edgesDataset: vis.DataSet | null;
}
```

---

## ⚡ 常见陷阱

1. **双重版本**: 注意不要在下拉框同时显示 row_id 和 row_id__v1（多版本时只显示 v1/v2...，单版本时显示 row_id）
2. **RAW_DATA 过载**: 原始 JSONL 每行可能很大（案件描述有 HTML），注意在 JS 中截断显示而非截断数据
3. **面板互斥**: 右侧 DetailPanel 和左侧 RawDataPanel 各自独立，不要互相影响
4. **vis-network 事件冒泡**: DetailPanel 必须阻止事件冒泡，否则点击面板会触发 network 的 blur 事件
5. **颜色一致性**: 确认蓝色 `#2980b9` 与 ontology 完全一致（复制而非肉眼判断）
6. **图例滚动**: 如果 legend 内容超过可视高度，启用 `overflow-y: auto; max-height: calc(100vh - 80px)`
