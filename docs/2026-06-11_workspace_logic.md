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