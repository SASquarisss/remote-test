# 图谱可视化优化：最佳技术落地实现方案

为了将“分层、折叠、强控视图”的理念安全、高效地落地到现有的 `ParseGraph` 和 `DatabaseGraph` 中，我们必须在**“原始数据 (Raw JSON)”**与**“渲染引擎 (Vis.DataSet)”**之间，引入一个**“图谱数据转换管道 (Graph Transformation Pipeline)”**。

以下是具备高稳定性、高扩展性的技术实现方案。

## 1. 架构设计：数据处理管道化 (Pipeline)

不直接将后端的节点塞给 vis.js，而是通过纯函数管道进行处理，确保状态的不可变性（Immutability）和渲染的安全性。

```javascript
// 核心思想：Pipeline 模式
const rawData = getRawData(state);
const visData = pipeline(
  rawData,
  applyTypeFilter(state.graphConfig.visibleTypes), // 步骤1：按 T0-T3 过滤实体
  applySmartAggregation(state.graphConfig),        // 步骤2：执行同案同类实体折叠
  applyGlobalAnchors()                             // 步骤3：提取共性 T0 锚点
);
visNetwork.setData(visData); // 最终渲染
```

## 2. 状态管理扩展 (Store Extension)

在 `store` 中新增 `graphConfig` 命名空间，作为“图谱视野控制器”的数据源。这种设计天然支持响应式，UI 改变 -> Store 改变 -> 触发 Pipeline 重新计算 -> 图谱平滑更新。

```javascript
// src/shared/store/index.js 扩展
graphConfig: {
  // 实体显示开关 (T0-T3)
  visibleTypes: {
    LegalProvision: true, DisputeFocus: true, Fact: true,  // T0, T1 默认开
    Evidence: false, LegalSubject: false,                  // T2 默认关
    Person: false, Judge: false                            // T3 默认关
  },
  // 折叠控制
  aggregation: {
    enabled: true,
    evidenceThreshold: 1, // 大于1个证据即折叠为[证据组: N]
    factDepthThreshold: 2 // 事实树深度剪枝阈值
  },
  // 记录用户手动展开的聚合节点 ID
  expandedNodes: new Set() 
}
```

## 3. 核心算法落地：智能折叠与关系重定向 (Edge Re-routing)

这是最核心且容易出 Bug 的地方。当我们把 5 个证据折叠成 1 个“聚合节点”时，原来指向这 5 个证据的边，必须动态重定向到这个聚合节点上，否则图谱就会断裂。

### 3.1 聚合与重定向算法 (O(N) 复杂度，高效安全)
```javascript
function applySmartAggregation(nodes, edges, config, expandedNodes) {
  const finalNodes = [];
  const finalEdges = [];
  const edgeRedirectionMap = {}; // 记录 { 旧节点ID: 新聚合节点ID }
  
  // 1. 分组统计 (按 案件ID + 实体类型)
  const groupMap = groupByCaseAndType(nodes);
  
  // 2. 生成聚合节点
  for (const [groupKey, groupNodes] of Object.entries(groupMap)) {
    const [caseId, type] = groupKey.split('_');
    
    // 如果符合折叠条件（比如是证据，且数量>1，且用户没有手动展开它）
    if (type === 'Evidence' && groupNodes.length > config.evidenceThreshold && !expandedNodes.has(groupKey)) {
      const virtualNodeId = `agg_${groupKey}`;
      finalNodes.push({
        id: virtualNodeId,
        label: `📦 [证据组: ${groupNodes.length}]`,
        shape: 'box',
        color: '#f8fafc', border: '#94a3b8', font: { color: '#475569' },
        isAggregate: true, // 标记为聚合节点
        representedNodes: groupNodes.map(n => n.id) // 存储底层节点，用于双击展开
      });
      
      // 记录重定向映射
      groupNodes.forEach(n => { edgeRedirectionMap[n.id] = virtualNodeId; });
    } else {
      // 不折叠的节点直接保留
      finalNodes.push(...groupNodes);
    }
  }
  
  // 3. 安全重定向边 (Edge Re-routing)
  edges.forEach(edge => {
    const newFrom = edgeRedirectionMap[edge.from] || edge.from;
    const newTo = edgeRedirectionMap[edge.to] || edge.to;
    
    // 避免自环边 (聚合节点自己指向自己)
    if (newFrom !== newTo) {
      // 使用 Set 或 Map 去重，避免多条边折叠后变成多条重复的边
      const edgeId = `${newFrom}_${edge.label}_${newTo}`;
      if (!edgeExists(finalEdges, edgeId)) {
        finalEdges.push({ ...edge, id: edgeId, from: newFrom, to: newTo });
      }
    }
  });
  
  return { nodes: finalNodes, edges: finalEdges };
}
```

## 4. UI 组件：视野控制器 (View Controller)

开发一个独立的 Vanilla JS 组件 `GraphViewController.js`，通过绝对定位悬浮在图谱右上角。
*   **解耦设计**：它只负责两件事：1. 读取 `store.getState().graphConfig` 渲染多选框；2. 监听勾选事件并调用 `store.update('graphConfig', ...)`。
*   **无缝接入**：不需要修改现有的图谱 HTML 结构，直接作为子组件 `appendChild` 到 `termVisContainer` 中。

## 5. 交互落地：双击展开 (Double-click to Explode)

利用 vis.js 的 `doubleClick` 事件，实现聚合节点的平滑展开。

```javascript
network.on("doubleClick", function (params) {
  if (params.nodes.length > 0) {
    const nodeId = params.nodes[0];
    const nodeData = nodesDataSet.get(nodeId);
    
    // 如果双击的是聚合节点
    if (nodeData && nodeData.isAggregate) {
      const state = store.getState();
      const newExpanded = new Set(state.graphConfig.expandedNodes);
      
      // nodeId 即为 groupKey (如 agg_case1_Evidence)
      const groupKey = nodeId.replace('agg_', ''); 
      newExpanded.add(groupKey); // 记录为已展开
      
      // 更新 Store，触发 Pipeline 重新计算
      store.update('graphConfig', { expandedNodes: newExpanded });
    }
  }
});
```

## 6. 物理引擎极限调优 (Vis.js Tweaks)

为了防止多案渲染时的“爆炸”和“乱飞”，在 `DatabaseGraph.js` 的 `options.physics` 中应用以下配置：

```javascript
physics: {
  enabled: true,
  solver: 'forceAtlas2Based',
  forceAtlas2Based: {
    gravitationalConstant: -150, // 增加整体斥力，拉开岛屿间距
    centralGravity: 0.005,       // 极弱的全局重力，允许案件形成独立的岛屿
    springLength: 100,           // 默认弹簧长度
    springConstant: 0.08,
    damping: 0.4                 // 增加阻尼，让图谱更快停下来，防止无休止抖动
  },
  stabilization: {
    enabled: true,
    iterations: 200,             // 初始化时预计算 200 次，直接呈现稳定结果
    updateInterval: 25
  }
}
```

## 7. 实施路线图 (Action Plan)
*   **Step 1**: 在 `selectors.js` 或 `utils` 中实现纯函数的 Pipeline (过滤、聚合、重定向)。
*   **Step 2**: 在 `store` 中加入 `graphConfig`，并将 Pipeline 接入 `DatabaseGraph` 的 `updateVisData`。
*   **Step 3**: 实现右上角 UI 控制器组件。
*   **Step 4**: 绑定双击展开交互和物理引擎参数调优。

此方案代码低耦合，将复杂的图计算封装在纯函数中，不会破坏现有业务逻辑，且极易通过 Jest 等单元测试验证折叠逻辑的正确性。
