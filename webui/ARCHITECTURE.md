# 法律知识图谱 WebUI 架构设计

## 目标
- 左侧输入案例文本，右侧实时渲染知识图谱
- 支持节点点击详情、缩放、搜索、筛选
- 易于从 MVP 扩展到生产级（Neo4j + React）

## 技术栈

| 层级 | 选型 | 理由 |
|------|------|------|
| 后端 | FastAPI | 与现有 Pydantic 模型天然契合，自动 API 文档 |
| 前端 | 纯 HTML + JS | 零构建工具，即时生效；后续可平滑迁移到 Vite+React |
| 图引擎 | Cytoscape.js | 专业图可视化库，力导向布局成熟，性能优于 D3（中等规模图） |
| 数据流 | JSON over HTTP | LLM 解析结果 → 后端序列化 → 前端渲染 |

## 数据流

```
用户输入文本
    ↓
[POST /api/parse]  FastAPI 复用 iterative_parse_eval.py 调用 LLM
    ↓
返回结构化 JSON (GuidingCase / CourtCase / LegalProvision / Person / Organization...)
    ↓
后端 kg_builder.py: JSON → Cytoscape elements (nodes[] + edges[])
    ↓
前端 Cytoscape.js 渲染力导向图
    ↓
用户交互: 点击查看属性面板、拖拽、缩放、按类型筛选
```

## 节点/边设计

### 节点分组（按本体论层次着色）
- 🔵 规范层: Law / LegalProvision / GuidingCase / CaseType / SentencingStandard
- 🟢 主体层: Person / Organization / Court / Judge / Attorney
- 🟠 案件层: CourtCase / CaseSummary / TrialOrganization / JudgmentResult / Evidence / DisputeFocus / Fact

### 边类型
- `BELONGS_TO` — 实体归属（Provision→Law, Case→CaseType）
- `INVOLVES` — 案件涉及主体（Case→Person/Org）
- `CITES` — 引用法条（Case→Provision, GuidingCase→Provision）
- `HAS_SUMMARY` — 案件摘要（Case→CaseSummary）
- `HAS_FOCUS` — 争议焦点（Case→DisputeFocus）
- `HAS_RESULT` — 判决结果（Case→JudgmentResult）

## 扩展路线

| 阶段 | 工作 | 触发条件 |
|------|------|----------|
| MVP (现在) | FastAPI + HTML/JS + Cytoscape，内存模式，单条解析 | 验证交互体验 |
| Phase 2 | 前端迁移 Vite+React，接入 Neo4j 做案例库查询 | 数据量 > 1万条 |
| Phase 3 | 增量更新（WebSocket推送）、协作标注、图谱对比 | 多用户场景 |

## 文件结构

```
webui/
├── backend/
│   ├── main.py          # FastAPI 入口，/api/parse /api/cases
│   ├── kg_builder.py    # JSON → Cytoscape elements
│   └── parser_bridge.py # 复用现有 LLM 解析逻辑
├── frontend/
│   ├── index.html       # 单页应用结构
│   ├── app.js           # Cytoscape 初始化 + 交互逻辑
│   └── styles.css       # 布局 + 节点样式
├── requirements.txt
└── ARCHITECTURE.md      # 本文档
```

## 启动方式

```bash
cd webui/backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# 浏览器打开 http://localhost:8000/static/index.html
```
