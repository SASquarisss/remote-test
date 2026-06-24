# Workspace (解析工作台) 业务逻辑文档

## 1. 模块定位
- **入口文件**: `visualization/ontology-refactored/index.html`
- **核心前端文件**:
  - `src/components/TerminalPanel.js`: 处理控制台、检索资产 (Bundle) 面板、子图 (Sub-graph) 的渲染与 UI 交互。
  - `src/components/ParseGraph.js`: 负责主画布知识图谱的渲染、布局分层（事实区、证据区、法条区等）以及节点交互。
- **职责**: 针对单篇法律文书（判决书），利用大模型进行实体与关系解析，构建法律本体图谱，支持多智能体 (Multi-Agent) 互动、增量解析，以及最终将图谱打包导出为“检索资产”。

## 2. 核心图谱布局 (Main Graph)
- **渲染引擎**: `vis-network`
- **分层布局 (Hierarchical Lanes)**:
  - 节点根据本体类型被分配到不同的纵列 (Lanes)，从左至右（或从上至下）展现案件事实的推导过程。
  - **核心区域划分**:
    - **主体区 (Subject)**: `LegalSubject`, `Attorney` 等
    - **证据区 (Evidence)**: `Evidence` 等
    - **事实区 (Fact)**: `Fact` 等
    - **诉求区 (Claim)**: (介于证据与事实下方) `ProceduralOpinion`, `LitigationClaim`, `ArgumentPoint`, `JudicialAssessment`
    - **法条元素区 (Element)**: `LegalProvisionElement` 等
    - **法条区 (Law)**: `LegalProvision`
    - **裁判区 (Result)**: `DisputeFocus`, `JudgmentResult`
- **已知防坑点**:
  - `vis-network` 的 `zone-hidden` 判断在缩放时容易导致区域名称（背景分层）消失。已在 `renderZoneOverlay` 中取消强行把 X 坐标 clamp 在边界内（否则会导致移出屏幕的标签在屏幕边缘互相重叠），并放宽了 `within` 的判定边界 (`domPos.x > -500` 等)。
  - `renderZoneOverlay` 随着拖拽会每秒被调用 60 次，必须使用 `if (currentKeys !== newKeys)` 避免重复覆盖 `innerHTML`，否则会导致严重的 DOM 闪烁和重新渲染丢失。

## 2.1 本体悬浮窗 (Ontology Floating Window)
- **核心文件**:
  - `visualization/ontology-refactored/index.html`
  - `visualization/ontology-refactored/src/components/OntologyGraph.js`
- **当前定位**: 不再把悬浮窗视为“静态本体小图”，而是升级为 `本体总览 + 继承树 + 运行时子图(迁移中)` 的复合导航器。
- **Tab 职责**:
  - `本体总览`: 以业务域（法源规范、主体组织、案件骨架、事实论证、裁判执行）组织本体类型，默认降噪展示，只保留核心关系，支持中文/双语/英文切换、搜索、当前案件高亮、当前推理高亮、隐藏无实例类型。
  - `继承树`: 以 `is_a` 技术继承为主，同时支持切换到“业务分组”视图；树节点统一显示中文短名，英文类型名降级为副标题，长版本说明不再直接塞进树节点正文。
  - `运行时子图`: 明确标记为过渡期容器，用于承接“检索链路”和“知识发现”两类运行时业务子图，并通过来源徽标/说明文案提醒用户该视图后续将迁出本体悬浮窗。
  - 第三个 Tab 内部现已重构为 `运行时子图 / 全案映射 / 增量映射` 三个平级视图：
    - `运行时子图` 继续承接当前检索链路与知识发现子图的过渡展示。
    - `运行时子图` 已补齐统一动态图容器结构：来源切换条、独立画布区、摘要说明区、统一操作区。
    - 当检索链路和知识发现都存在时，可在 `运行时子图` 中主动切换来源，而不再只是被“最后一次更新”覆盖。
    - `全案映射` 只保留 `类型热力`：它只看当前全案已经存在的本体实例分布，不再挂在 `检索链路 / 知识发现` 来源体系下。
    - 当第三块区域切换到 `全案映射 / 增量映射` 时，顶部不再沿用 `检索链路 / 知识发现` 的运行时来源语境，也不会继续保留子图容器的主动作按钮；此时主内容应完全回到热力卡片 + 详情面板。
    - `全案映射` 现已支持 `类型热力 / 业务域热力` 两种子视角：
      - `类型热力` 看具体本体类型实例分布。
      - `业务域热力` 按五大业务域（法源规范、主体组织、案件骨架、事实论证、裁判执行）汇总当前全案实例，并支持驱动主图按业务域聚焦。
      - `业务域热力` 的详情区支持“域内类型展开”，可从业务域直接下钻到具体类型卡片联动主图。
    - `增量映射` 只保留 `推理映射 / 版本变化` 两种模式：
      - `推理映射` 只展示当前链式思考步骤命中或新增的本体类型。
      - `版本变化` 只展示近期新增或更新过的本体类型，不再混入全量类型热力；卡片和详情已区分 `新增` 与 `更新`，不再只给一个总变更数。
      - `版本变化` 的详情已进一步拆分来源：区分 `知识发现新增 / 版本新增 / 版本更新`，避免把不同来源的增量混成一个笼统计数。
    - `全案映射` 与 `增量映射` 都已接通主图联动：悬停类型卡片会预高亮主图同类型节点；点击类型卡片会回写 `selectedGraph = 'ontology'`、`locateTarget` 和 `ontologySelectionScope`，从而让主图区分“看全量实例”还是“优先看增量实例”。
    - 映射视图点击卡片后还会向主图发送 `parse-analysis-mode-request`，按类型自动切换到更合适的分析模式：例如 `Evidence / Fact / JudicialAssessment` 优先切 `evidence_chain`，`LegalProvision / LegalProvisionElement / JudgmentResult / DisputeFocus / SentencingStandard` 优先切 `judgment_basis`。
    - 当链式思考的 `activeDiscoveryIdx` 发生变化时，如果当前正在查看 `增量映射` 且不处于 `版本变化`，会自动回到 `推理映射`，突出当前步骤对应的本体类型。
    - `运行时子图` 里的“在主工作区查看”入口已经升级为显式主按钮，不再只放在底部弱提示区域。
- **最小化交互**:
  - 悬浮窗右上角原“关闭”语义已改为“最小化”。
  - 点击后不会彻底隐藏，而是折叠为主图左上角的圆形浮窗入口。
  - 再次点击圆形入口后，会恢复到最小化前的窗口模式（全屏本体主视图或悬浮窗模式）。
- **关键联动**:
  - 悬浮窗会统计 `parseGraphData.nodes` 中当前案件命中的本体类型数量，并在头部状态栏展示。
  - 悬浮窗会读取 `discoveryHistory` 和 `activeDiscoveryIdx`，高亮当前链式思考步骤涉及的本体类型。
  - 从主图谱点击节点时，悬浮窗会自动锁定对应本体类型；从悬浮窗点击类型时，也会同步回写 `selectedGraph = 'ontology'` 以维持联动。
  - `运行时子图` 通过 `ontology-runtime-meta` / `ontology-runtime-select` 事件与 `TerminalPanel` 双向同步，使悬浮窗可以主动请求切换到“检索链路”或“知识发现”来源。
- **迁移策略**:
  - `ontologySubGraphHost` 目前仍保留，但内部已重构为“运行时子图壳子 + 独立画布”。
  - 检索链路子图当前仍在终端右侧 `termSubGraphContainer` 保持原位展示，同时镜像到悬浮窗用于过渡。
  - 知识发现 Tab 空间有限，当前不再承载知识发现子图；该 Tab 只保留“思考过程 + 核心结论 + JSON 补充数据”的轻面板结构。
  - 知识发现子图继续保留在悬浮窗的 `ontologyRuntimeCanvas` 中，由 `运行时子图` 统一承接展示。
  - 悬浮窗运行时子图底部已加入“在主工作区查看”入口，用于按当前来源类型跳转：
    - `检索链路` -> `termSubGraphTabContent`
    - `知识发现` -> `termDiscoveryTabContent`
  - 当前第三个 Tab 已不再朝“大一统案件映射”继续扩张，而是明确拆成 `运行时子图 / 全案映射 / 增量映射` 三块，避免检索链路、类型热力、增量结果继续混在一起。

## 3. 检索资产 (Retrieval Bundle)
- **概念**: 解析完成后的整案图谱会被后端拆解/重组为不同“视角”的子图资产（如事实链视角、争点视角、当事人视角、上诉人视角等）。
- **前端渲染**:
  - **左侧列表**: 列出所有生成的资产条目 (`entries`)。
  - **右侧面板**: 包含资产文本说明和 **子图 (Sub-graph)**。
- **子图 (Sub-graph) 逻辑**:
  - **数据结构陷阱**: 后端传来的 `chain_edges` 数据通常是线性数组，**不包含明确的 `source` 和 `target` ID**。前端在 `TerminalPanel.js` 中必须通过数组索引隐式推导：`from: chain_nodes[index].id, to: chain_nodes[index+1].id`。
  - **排版规范**: 子图统一采用垂直排版 (`direction: 'UD'`)，节点文字过长需截断换行 (30字)，边文字需保持水平阅读 (`align: 'horizontal'`)。
  - **全量展示**: 检索资产的链路说明和图谱文本**绝对不允许做数组切片或长度截断**，必须全量展示给用户。

## 4. 前后端交互与常见问题
- **解析 API**: 后端大模型解析常涉及庞大的 JSON 输出。如果报错 500，优先检查 `.env` 中的大模型 API Key (`DEEPSEEK_API_KEY` 等) 是否已通过 `load_dotenv` 加载。
- **多智能体开关**: 架构目前支持 `linear` 和 `multi_agent` 两种 RAG_MODE，路由受此环境变量影响。
- **实体对齐丢失**: 如果发现连线断裂（例如当事人与律师之间无“代理”关系），需检查后端 `parser.py` 中的 `alias_map` 白名单是否漏加了该实体（例如 `attorneys`），以及 Prompt 模板是否要求大模型生成了 `"id"` 字段。

## 5. 数据增强 (Data Augmentation) 与 深度思考 (Deep Thinking)
- **数据增强 (法条补充)**:
  - 功能：遍历图谱中的所有法条，通过调用 Milvus 的 HTTP API 精确查找完整原文，并替换进图谱内容中。
  - 注意事项：Milvus 存储的格式通常是“第一百五十三条”，而大模型提取的可能是阿拉伯数字“153”。后端 `app.py` 中有 `_normalize_article_to_chinese` 进行转换。
- **深度思考 (Deep Thinking) 与 知识发现**:
  - 功能：允许用户对已有图谱进行“法条适用分析”、“构成要件分析”等高阶推演。
  - **SSE 流式渲染**：后端 `app.py` (`/api/deep-think`) 采用 `text/event-stream` 输出。为了优化 UI 体验，Prompt 设计为“先输出纯 Markdown 推理过程，最后包裹一个 ```json 包含要增补的图谱结构”。
  - 前端通过 `lastIndexOf('```json')` 分离 Markdown 与 JSON，并利用 `vis-network` 在独立 Tab 下渲染“局部子图 (Sub-graph)”。
  - **合并至主图谱**：知识发现新增的 `virtual_nodes` 和 `relations`，通过前端的版本管理直接写入 `json_result` 的 `virtual_nodes`，生成快照并重绘画布。
