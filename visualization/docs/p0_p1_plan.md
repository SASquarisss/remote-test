# P0-P1 UI 改进实现方案

> 目标文件：`/root/remote-test/visualization/ontology_v2.2.html`
> 日期：2026-05-13

---

## 1️⃣ Evidence 节点视觉权重过大

### 修改描述
Evidence 节点的尺寸（size）和字号（font.size）偏大，导致视觉权重过高，与其他节点失衡。

### 文件路径 & 行号
**文件：** `/root/remote-test/visualization/ontology_v2.2.html`

#### 修改点 A — ENTITY_STYLES 初始化值（行 364）

```
OLD (L364):
  Evidence:   { shape: 'database', color: '#CD853F', border: '#A06B32', size: 10, note: '证据' },

NEW:
  Evidence:   { shape: 'database', color: '#CD853F', border: '#A06B32', size: 6, note: '证据' },
```

| 字段 | 旧值 | 新值 |
|------|------|------|
| `size` | `10` | `6` |

#### 修改点 B — renderTermVis 中 database 形状的字号特殊处理（行 2349~2356）

```
OLD (L2349-2356):
    var shapeType = shpMap[n.nodeType] || n.shape || 'ellipse';
    var fontSize = 10;
    if (shapeType === 'box' || shapeType === 'square') {
      fontSize = 12;
    } else if (shapeType === 'ellipse') {
      fontSize = 8;
    }

NEW:
    var shapeType = shpMap[n.nodeType] || n.shape || 'ellipse';
    var fontSize = 10;
    if (shapeType === 'box' || shapeType === 'square') {
      fontSize = 12;
    } else if (shapeType === 'ellipse') {
      fontSize = 8;
    } else if (shapeType === 'database') {
      fontSize = 8;
    }
```

#### 修改点 C — 默认 font.size 从 11 降为适配值（行 2365）

由于 Evidence 使用 database 形状，其字号已经通过 `fontSize` 变量控制（L2351），并且在 L2365 中所有节点使用固定 `font: { size: 11 }`。需要将 L2365 中的固定字号替换为变量引用，使得每个节点的最终字号由 `fontSize` 变量决定。

```
OLD (L2365):
      font: { color: '#333', size: 11, face: 'Microsoft YaHei, PingFang SC, sans-serif' },

NEW:
      font: { color: '#333', size: fontSize, face: 'Microsoft YaHei, PingFang SC, sans-serif' },
```

> ⚠️ **注意：** 修改点 C 与修改点 B 配合使用。`fontSize` 在 L2351 初始化为 10，在 L2352-2356 中针对不同形状分支设置了不同值。修改 C 用变量替换固定值后，`box` → `12`，`ellipse` → `8`，`database` → `8`，其他形状 → `10`。

### 验证方法
1. 重新解析一个包含 Evidence 节点的案例
2. 目视检查 Evidence 节点（database 形状）是否明显变小
3. 检查 Evidence 节点上的文字是否由 11px 降为 8px

---

## 2️⃣ 右侧面板信息苍白

### 修改描述
`renderParseNode` 函数对 `node.title` 中的信息展示为纯文本，且未从 vis-node 原始数据中提取额外属性。需要将 title 按 `<br>` 拆分后逐条展示，同时读取节点的额外属性一并展示。

### 文件路径 & 行号
**文件：** `/root/remote-test/visualization/ontology_v2.2.html`
**函数：** `renderParseNode`（行 1314~1373）

### 改动内容

#### 修改点 A — 重构 node.title 的展示逻辑（行 1332~1339）

当前展示方式（L1333-1338）将整个 title 放入一个 `<div>` 中，看起来苍白平淡。

```
OLD (L1332-1339):
  // Title (extra info from parser)
  var title = node.title || '';
  if (title) {
    html += '<div class="panel-section">';
    html += '<div class="panel-section-title">📄 详细信息</div>';
    html += '<div class="desc-text">' + escapeHtml(title) + '</div>';
    html += '</div>';
  }

NEW:
  // Title (extra info from parser) - 按 <br> 拆分展示
  var title = node.title || '';
  if (title) {
    html += '<div class="panel-section">';
    html += '<div class="panel-section-title">📄 详细信息</div>';
    // 按 <br> 分割，每行作为一个 field-row 展示
    var lines = title.split(/<br\s*\/?>/i);
    lines.forEach(function(line) {
      var trimmed = line.trim();
      if (!trimmed) return;
      // 尝试按 ": " 或 "：" 分割成键值对
      var colonIdx = trimmed.indexOf(': ');
      if (colonIdx === -1) colonIdx = trimmed.indexOf('：');
      if (colonIdx > 0 && colonIdx < 60) {
        var key = trimmed.substring(0, colonIdx);
        var val = trimmed.substring(colonIdx + 1).replace(/^[:：]\s*/, '');
        html += '<div class="field-row"><span class="field-name">' + escapeHtml(key) + '</span><span style="margin-left:8px;color:#555;">' + escapeHtml(val) + '</span></div>';
      } else {
        html += '<div class="field-row" style="color:#555;">' + escapeHtml(trimmed) + '</div>';
      }
    });
    html += '</div>';
  }
```

#### 修改点 B — 从 vis-node 原始数据中提取额外字段并展示（行 1341~1357 之后追加）

在原有 JSON 属性和"#10; 样式"段落之间，插入一个"📊 节点属性"段落，提取 `node` 对象中的常见扩展字段。

```
INSERT AFTER L1357（在 JSON parse 块结束后，L1359 的 // Shape/Style info 之前）:

  // Extended properties from vis-node data
  var extraFields = ['case_number', 'role_name', 'evidence_type', 'caseName', 'description', 'source'];
  var hasExtra = extraFields.some(function(f) { return node[f] !== undefined && node[f] !== null && node[f] !== ''; });
  if (hasExtra) {
    html += '<div class="panel-section">';
    html += '<div class="panel-section-title">📊 节点属性</div>';
    extraFields.forEach(function(f) {
      var val = node[f];
      if (val !== undefined && val !== null && val !== '') {
        var displayKey = ({ case_number: '案号', role_name: '角色', evidence_type: '证据类型', caseName: '案件名称', description: '描述', source: '来源' })[f] || f;
        html += '<div class="field-row"><span class="field-name">' + escapeHtml(displayKey) + '</span><span style="margin-left:8px;color:#555;">' + escapeHtml(String(val)) + '</span></div>';
      }
    });
    html += '</div>';
  }
```

### 依赖关系
无。独立修改 renderParseNode 函数内容。

### 验证方法
1. 解析包含证据或角色的案例
2. 点击图谱中的节点打开右侧面板
3. 检查"详细信息"部分是否将 `<br>` 分割的内容逐行展示为键值对
4. 检查"节点属性"部分是否显示了 `case_number` 等额外字段

---

## 3️⃣ 关系线交叉多

### 修改描述
termVis 网络（解析图谱）的边曲线类型为 `continuous`（直线/贝塞尔），且节点间距不足，导致关系线交叉严重。需要改为 `curvedCW` 弯曲布局，同时增大节点间距和物理阻尼。

### 文件路径 & 行号
**文件：** `/root/remote-test/visualization/ontology_v2.2.html`
**函数：** `renderTermVis`（从行 2281 开始）

#### 修改点 A — 边曲线类型（行 2375 + 行 2388）

有两处需要修改：
1. 边的 `smooth` 属性定义（行 2375）
2. options 中的 `edges.smooth` 覆盖值（行 2388）

```
OLD (L2375):
      width: 1.5, smooth: { type: 'continuous' },

NEW:
      width: 1.5, smooth: { type: 'curvedCW', roundness: 0.12 },

---
OLD (L2388):
    edges: { smooth: { type: 'continuous' }, font: { size: 10, color: '#555' } },

NEW:
    edges: { smooth: { type: 'curvedCW', roundness: 0.12 }, font: { size: 10, color: '#555' } },
```

#### 修改点 B — 物理引擎参数（行 2384）

```
OLD (L2384):
      barnesHut: { gravitationalConstant: -3000, centralGravity: 0.3, springLength: 180, springConstant: 0.04, damping: 0.5, avoidOverlap: 0.5 },

NEW:
      barnesHut: { gravitationalConstant: -3000, centralGravity: 0.3, springLength: 200, springConstant: 0.04, damping: 0.6, avoidOverlap: 0.5 },
```

| 参数 | 旧值 | 新值 |
|------|------|------|
| `springLength` | `180` | `200` |
| `damping` | `0.5` | `0.6` |

#### 修改点 C — 布局优化中的节点间距（行 2442）

```
OLD (L2442):
        var spacing = 160; // 两个同区节点间距

NEW:
        var spacing = 180; // 两个同区节点间距
```

### 依赖关系
无。三处修改独立，可一起实施。

### 验证方法
1. 解析包含多个节点和关系的案例
2. 目视检查边是否变为弯曲（curvedCW）而非直线
3. 检查节点之间的间距是否增大
4. 检查物理引擎稳定后阻尼效果更明显（晃动减少）

---

## 4️⃣ 聚类折叠后无法展开

### 修改描述
聚类节点（id 以 `cluster_` 开头）在折叠后没有注册双击事件，用户无法双击展开查看子节点。需要在 `applyClustering` 调用之后注册 `doubleClick` 事件监听。

### 文件路径 & 行号
**文件：** `/root/remote-test/visualization/ontology_v2.2.html`

#### 修改点 A — 在 stabilization 回调中注册双击事件（行 2522 附近，setTimeout 内部）

在 stabilization 回调的 `setTimeout` 内部（L2480~L2523 之间）已有 `click` / `hoverNode` / `hoverEdge` 事件监听。在 `hoverEdge` 监听之后追加 `doubleClick` 监听。

```
INSERT AFTER L2522（在 }); 之后、); 之前）:

    termVisNetwork.on('doubleClick', function(params) {
      if (params.nodes.length > 0) {
        var nodeId = params.nodes[0];
        if (nodeId.indexOf('cluster_') === 0) {
          try {
            termVisNetwork.clustering.openCluster(nodeId);
          } catch(e) {
            console.warn('展开聚类失败:', e);
          }
        }
      }
    });
```

#### 修改点 B — 给聚类节点的 title 添加展开提示（行 2561~2567）

在 `applyClustering` 函数的 `clusterNodeProperties` 中添加 `title` 提示。

```
OLD (L2561-2567):
          clusterNodeProperties: {
            id: 'cluster_' + type,
            label: type + '组 (' + count + ')',
            shape: 'box',
            color: { background: '#95a5a6', border: '#7f8c8d' },
            font: { size: 12, color: '#fff' },
          },

NEW:
          clusterNodeProperties: {
            id: 'cluster_' + type,
            label: type + '组 (' + count + ')',
            title: '<b>' + type + '</b> 组 (' + count + ' 个节点) — 双击展开查看详情',
            shape: 'box',
            color: { background: '#95a5a6', border: '#7f8c8d' },
            font: { size: 12, color: '#fff' },
          },
```

### 依赖关系
- 修改点 A 必须在 `applyClustering` 调用（行 2452）之后注册
- 当前注册位置在 stabilization 回调的 `setTimeout`（行 2480）内，`applyClustering` 已在行 2452 执行，所以时机正确
- 修改点 B 与修改点 A 配合使用，分别解决"如何展开"和"提示用户可展开"

### 验证方法
1. 解析包含 3+ 个同类型节点（如 3 个 Judge）的案例
2. 等待自动聚类折叠，出现 "Judge组 (3)" 的聚类节点
3. 悬停聚类节点，查看 tooltip 是否显示 "双击展开查看详情"
4. 双击聚类节点，验证子节点是否展开显示

---

## 5️⃣ 样式配置弹窗深色节点预览看不清

### 修改描述
样式配置弹窗中的节点预览使用 SVG 渲染，深色背景的节点（如 `LegalProvision` 深紫色 `#483D8B`）与弹窗深色背景边界不清晰，轮廓不可见。

### 文件路径 & 行号
**文件：** `/root/remote-test/visualization/ontology_v2.2.html`
**函数：** `renderShapePreview`（行 1685~1740）

### 改动内容
在所有形状的 SVG 元素上增加一个 `1px rgba(255,255,255,0.4)` 的外圈描边，确保深色背景上节点轮廓可见。

#### 通用方案（行 1738~1739 前添加）

在每个形状的 SVG 元素绘制完成后，在最外层包裹一个统一的轮廓描边层。最简洁的方式是在 SVG 内部添加一个与形状位置匹配的辅助描边元素。

**更优方案：** 在返回的 SVG 字符串的外层容器上增加 `rgba(255,255,255,0.4)` 的描边，或者对每个形状的 `stroke` 属性做复合处理。

**推荐实现：** 在 L1739 `el.innerHTML = svg;` 之前，为每个形状的 SVG 元素添加一个覆盖在全形状上的白色半透明描边。通过给每个绘制分支追加一个额外的高亮描边来实现。

具体做法：在每个 `case` 分支的 SVG 绘制结束后，追加一个 `stroke="rgba(255,255,255,0.4)" stroke-width="1" fill="none"` 的相同路径元素。

```
OLD (L1691-1738):
  switch (shape) {
    case 'box':
    case 'square':
      svg += '<rect x="2" y="2" width="' + (size - 4) + '" height="' + (size - 4) + '" rx="3" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      break;
    case 'ellipse':
    case 'circle':
      svg += '<ellipse cx="' + cx + '" cy="' + cy + '" rx="' + r + '" ry="' + r + '" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      break;
    case 'database':
      svg += '<ellipse cx="' + cx + '" cy="8" rx="10" ry="5" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      svg += '<path d="M 4 8 L 4 20 C 4 22.76 9.37 24 14 24 C 18.63 24 24 22.76 24 20 L 24 8" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      svg += '<ellipse cx="' + cx + '" cy="20" rx="10" ry="5" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      break;
    case 'diamond':
      svg += '<polygon points="' + cx + ',2 ' + (size - 2) + ',' + cy + ' ' + cx + ',' + (size - 2) + ' 2,' + cy + '" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      break;
    case 'dot':
      svg += '<circle cx="' + cx + '" cy="' + cy + '" r="8" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      break;
    case 'star':
      ...
      svg += '<polygon points="' + pts.join(' ') + '" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      break;
    case 'hexagon':
      ...
      svg += '<polygon points="' + pts.join(' ') + '" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      break;
    case 'triangle':
      svg += '<polygon points="' + cx + ',2 ' + (size - 2) + ',' + (size - 2) + ' 2,' + (size - 2) + '" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      break;
    case 'triangleDown':
      svg += '<polygon points="' + cx + ',' + (size - 2) + ' 2,2 ' + (size - 2) + ',2" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      break;
    default:
      svg += '<rect x="2" y="2" width="' + (size - 4) + '" height="' + (size - 4) + '" rx="3" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
  }
  svg += '</svg>';
  el.innerHTML = svg;

NEW (在每个 case 分支的末尾追加白色半透明描边):
  switch (shape) {
    case 'box':
    case 'square':
      svg += '<rect x="2" y="2" width="' + (size - 4) + '" height="' + (size - 4) + '" rx="3" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      svg += '<rect x="2" y="2" width="' + (size - 4) + '" height="' + (size - 4) + '" rx="3" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>';
      break;
    case 'ellipse':
    case 'circle':
      svg += '<ellipse cx="' + cx + '" cy="' + cy + '" rx="' + r + '" ry="' + r + '" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      svg += '<ellipse cx="' + cx + '" cy="' + cy + '" rx="' + r + '" ry="' + r + '" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>';
      break;
    case 'database':
      svg += '<ellipse cx="' + cx + '" cy="8" rx="10" ry="5" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      svg += '<path d="M 4 8 L 4 20 C 4 22.76 9.37 24 14 24 C 18.63 24 24 22.76 24 20 L 24 8" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      svg += '<ellipse cx="' + cx + '" cy="20" rx="10" ry="5" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      svg += '<ellipse cx="' + cx + '" cy="8" rx="10" ry="5" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>';
      svg += '<path d="M 4 8 L 4 20 C 4 22.76 9.37 24 14 24 C 18.63 24 24 22.76 24 20 L 24 8" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>';
      svg += '<ellipse cx="' + cx + '" cy="20" rx="10" ry="5" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>';
      break;
    case 'diamond':
      svg += '<polygon points="' + cx + ',2 ' + (size - 2) + ',' + cy + ' ' + cx + ',' + (size - 2) + ' 2,' + cy + '" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      svg += '<polygon points="' + cx + ',2 ' + (size - 2) + ',' + cy + ' ' + cx + ',' + (size - 2) + ' 2,' + cy + '" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>';
      break;
    case 'dot':
      svg += '<circle cx="' + cx + '" cy="' + cy + '" r="8" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      svg += '<circle cx="' + cx + '" cy="' + cy + '" r="8" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>';
      break;
    case 'star':
      var pts = [];
      for (var i = 0; i < 5; i++) {
        var angle = -Math.PI / 2 + (i * 2 * Math.PI / 5);
        pts.push((cx + r * Math.cos(angle)).toFixed(1) + ',' + (cy + r * Math.sin(angle)).toFixed(1));
        angle += Math.PI / 5;
        pts.push((cx + r * 0.45 * Math.cos(angle)).toFixed(1) + ',' + (cy + r * 0.45 * Math.sin(angle)).toFixed(1));
      }
      svg += '<polygon points="' + pts.join(' ') + '" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      svg += '<polygon points="' + pts.join(' ') + '" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>';
      break;
    case 'hexagon':
      var pts = [];
      for (var i = 0; i < 6; i++) {
        var angle = -Math.PI / 2 + (i * 2 * Math.PI / 6);
        pts.push((cx + r * Math.cos(angle)).toFixed(1) + ',' + (cy + r * Math.sin(angle)).toFixed(1));
      }
      svg += '<polygon points="' + pts.join(' ') + '" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      svg += '<polygon points="' + pts.join(' ') + '" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>';
      break;
    case 'triangle':
      svg += '<polygon points="' + cx + ',2 ' + (size - 2) + ',' + (size - 2) + ' 2,' + (size - 2) + '" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      svg += '<polygon points="' + cx + ',2 ' + (size - 2) + ',' + (size - 2) + ' 2,' + (size - 2) + '" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>';
      break;
    case 'triangleDown':
      svg += '<polygon points="' + cx + ',' + (size - 2) + ' 2,2 ' + (size - 2) + ',2" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      svg += '<polygon points="' + cx + ',' + (size - 2) + ' 2,2 ' + (size - 2) + ',2" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>';
      break;
    default:
      svg += '<rect x="2" y="2" width="' + (size - 4) + '" height="' + (size - 4) + '" rx="3" fill="' + color + '" stroke="' + border + '" stroke-width="1.5"/>';
      svg += '<rect x="2" y="2" width="' + (size - 4) + '" height="' + (size - 4) + '" rx="3" fill="none" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>';
  }
  svg += '</svg>';
  el.innerHTML = svg;
```

### 依赖关系
无。独立修改 `renderShapePreview` 函数。

### 验证方法
1. 打开样式配置弹窗
2. 找到深色节点（如 LegalProvision 深紫色 `#483D8B`）
3. 目视检查其预览 SVG 是否有明显的白色半透明外轮廓
4. 确认浅色节点（如 Person 浅绿色 `#90EE90`）的轮廓也不受影响

---

## 汇总

| # | 改进项 | 优先级 | 涉及行号 | 改动量 |
|---|--------|--------|----------|--------|
| 1 | Evidence 节点权重 | P0 | L364, L2349-2356, L2365 | 3 处小改 |
| 2 | 右侧面板信息 | P0 | L1332-1339, L1357 后插入 | 2 处中改 |
| 3 | 关系线交叉 | P1 | L2375, L2388, L2384, L2442 | 4 处小改 |
| 4 | 聚类无法展开 | P1 | L2522 后插入, L2561-2567 | 2 处小改 |
| 5 | 深色预览看不清 | P1 | L1691-1738 | 多分支追加 stroke |

**实施顺序建议：** 按 1 → 2 → 3 → 5 → 4 的顺序实施，其中 1、2、5 无依赖关系可并行实施，3 与 1 无冲突可并行，4 需要确认聚类流程正确后再实施。
