# 法律本体论与图谱解析可视化系统：前端重构设计文档

## 1. 重构背景与目标

原系统（`ontology_v2.2.html`）在长期迭代中演变为了一个近 6000 行的“大泥球（God Object）”，视图、状态、网络请求与图谱渲染逻辑深度耦合，带来了极高的维护成本和脆弱性。

**重构目标：**
*   **功能对齐**：完全保留原系统 100% 的界面交互与业务功能（双图联动、右侧抽屉面板、下方终端面板交互、后端长轮询、图谱拖拽与聚焦等）。
*   **架构现代化**：引入模块化、组件化、单向数据流与现代构建工具，解决当前架构的 5 大痛点。
*   **提升稳定性**：根除由于全局变量冲突、DOM 暴力覆盖、事件冒泡导致的各类假死和 TypeError。

---

## 2. 技术栈选型

考虑到原项目是基于原生 JavaScript 和 `vis-network` 构建的，为了降低重构难度并保持最大的灵活性，建议采用 **Vite + ES6 Modules (Vanilla JS) + Web Components / 纯函数组件** 的轻量级现代架构。

*   **构建工具**：[Vite](https://vitejs.dev/)（提供极速的本地开发体验、原生 ES 模块支持、按需打包）。
*   **核心库**：`vis-network` (独立通过 npm 引入，不再内嵌源码)。
*   **状态管理**：自研轻量级 Pub/Sub（发布订阅）状态机，取代 `window` 全局变量。
*   **CSS 方案**：分离为独立的 `.css` 模块，或使用简单的 CSS 变量主题化。

*(备选方案：如果团队熟悉 React/Vue，可将 UI 面板部分使用框架重写，但考虑到 `vis-network` 本身是高度操作 DOM 的命令式库，纯 Vanilla JS + 模块化通常在处理复杂图谱时性能更好且冲突更少。)*

---

## 3. 针对 5 大痛点的架构设计方案

### 3.1 解决“意大利面条式”代码：UI 与逻辑解耦（MVC 思想）
*   **视图层（View）**：负责 DOM 渲染和事件绑定。所有的 HTML 模板字符串将抽取到单独的模板文件或渲染类中。例如，将右侧面板的渲染抽象为 `PanelRenderer` 类，只接受数据对象并输出 DOM。
*   **逻辑层（Controller/Service）**：负责业务规则、数据转换。如 `GraphService` 负责处理节点过滤、高亮逻辑。
*   **模型层（Model）**：统一的数据结构定义。

### 3.2 解决“全局变量的野生动物园”：集中式状态管理（Store）
彻底废弃挂载在 `window` 上的 `isPanelLocked`, `currentSelection` 等变量。
设计一个单例的 `StateManager`：
```javascript
// store.js
class StateManager {
  constructor() {
    this.state = {
      activeGraph: 'ontology', // 'ontology' | 'parse'
      selectedNode: null,
      selectedEdge: null,
      panelMode: 'closed', // 'closed' | 'compact' | 'full'
      parseTaskStatus: 'idle'
    };
    this.listeners = [];
  }
  
  // 唯一修改状态的入口
  dispatch(action, payload) {
    // 根据 action 更新 state
    this._notify();
  }
  
  subscribe(listener) { ... }
}
export const store = new StateManager();
```
各组件通过订阅 `store` 的变化来更新自身 UI，实现单向数据流。

### 3.3 解决“巨无霸”文件：模块化与目录结构拆分
重构后的项目结构设计如下：
```text
/src
  ├── index.html               # 骨架 HTML，仅包含容器 div
  ├── main.js                  # 入口文件，初始化应用
  ├── /api
  │   └── backend.js           # 封装 fetch/长轮询请求
  ├── /store
  │   └── index.js             # 集中式状态管理器
  ├── /components
  │   ├── OntologyGraph.js     # 顶部主图谱组件 (封装 vis.js)
  │   ├── ParseGraph.js        # 底部解析结果图谱组件 (封装 vis.js)
  │   ├── DetailPanel.js       # 右侧详情面板抽屉组件
  │   └── TerminalPanel.js     # 底部终端与控制台面板组件
  ├── /utils
  │   ├── dom.js               # 安全的 DOM 操作工具函数
  │   └── formatter.js         # 文本转义、高亮等工具
  ├── /styles
  │   ├── main.css             # 全局样式
  │   ├── graph.css            # 图谱相关样式
  │   └── panels.css           # 面板 UI 样式
  └── /data
      └── schema.js            # 实体与关系静态配置表
```

### 3.4 解决“脆弱的事件机制”：事件委托与总线
*   **DOM 事件**：全局的点击（如点击空白处关闭面板）、拖拽事件统一在 `main.js` 或专用的 `InteractionManager` 中注册，通过 `e.target.closest` 进行事件委托分发。
*   **组件通信**：图谱组件与 UI 面板组件之间不再互相直接调用方法（如图谱不再直接调 `renderEntityPanel()`），而是：
    1. 图谱抛出 `nodeClicked` 事件 -> 
    2. 更新 `Store` 中的 `selectedNode` -> 
    3. `DetailPanel` 监听到状态变化 -> 
    4. 自动拉取数据并重新渲染。

### 3.5 解决“防御性编程不足”：建立错误边界机制
*   **安全的 DOM 更新**：彻底摒弃破坏性的 `container.innerHTML = 'error'`。封装专门的 `mount(container, content)` 函数，内部保证不会破坏固定的骨架。
*   **数据完整性校验**：在 `GraphService` 渲染前，严格校验节点数据是否在 `schema.js` 中存在。若缺失，提供优雅的 Fallback 渲染对象，而不让整个流程崩溃。

---

## 4. 实施与迁移路径 (Roadmap)

**Phase 1: 基础设施搭建 (Scaffolding)**
*   初始化 Vite 项目，配置 ESLint / Prettier 确保代码规范。
*   将原有的静态 CSS 抽离并组织为 CSS Modules。
*   将原有的 `ENTITY_DATA` 等静态数据抽取为独立的 ES Module。

**Phase 2: 核心状态与通信层 (Core & State)**
*   实现 `StateManager`，定义好所有的 actions（选择节点、开始解析、面板开关等）。
*   封装后端 API 请求（包括原有的长轮询逻辑），使其与 UI 彻底解耦。

**Phase 3: 图谱组件解耦重构 (Graph Components)**
*   封装 `OntologyGraph` 类：处理主图谱的初始化、布局、事件监听（转发为 State action）。
*   封装 `ParseGraph` 类：处理下方解析图的动态数据更新、瀑布流布局算法分离。

**Phase 4: UI 面板组件重构 (UI Panels)**
*   重构 `DetailPanel`：实现基于模板的纯函数渲染，区分实体 Tab、关联边 Tab。
*   重构 `TerminalPanel`：实现日志滚动、拖拽缩放功能，消除与图谱逻辑的纠缠。

**Phase 5: 集成、测试与对齐 (Integration & Parity Check)**
*   在 `main.js` 中将所有组件组装，挂载到真实的 DOM 容器上。
*   对照旧版 `ontology_v2.2.html`，进行功能特性的 1:1 回归测试，确保无遗漏。

---

## 5. 预期收益
*   **代码行数**：核心业务逻辑预期从 6000 行压缩/拆分至多个 300-500 行的易维护模块。
*   **调试体验**：借助单向数据流，任何 UI 异常都可以直接通过状态快照（State Snapshot）瞬间定位根源。
*   **扩展性**：未来新增图谱类型、新面板、新评估报表，只需增加对应的 Component 即可，不会再引发连锁崩溃。