# remote-test (Ontology Refactored)

当前仓库是一个围绕 `legal_ontology_v2.yaml` 运转的完整原型工程。该工程经历了前后端架构的重构，现在由 Vite 构建的现代前端应用和 Flask 后端服务组成。

包含以下核心模块：
- 本体 schema 与 prompt 自动生成
- few-shot 候选池与统一刷新脚本
- 离线抽取链与 `_meta` 追溯
- 基于 Vite 的前端可视化页面 (组件化架构)
- Flask 后端解析 / 保存接口
- `data_lake` 分层与结构化候选池

这份 README 是当前会话和后续会话的默认入口文档。

## 开发约定

- 每次重启会话，先读本文件，再开始改动。
- 尽量不要在仓库根目录新增代码；优先放到 `scripts/`、`backend/`、`visualization/`、`docs/` 等已有目录。
- 前端已重构为模块化应用，位于 `visualization/ontology-refactored`。
- 后端 Python 服务位于 `backend/`。

## 当前主入口

### 前端 (Vite App)

重构后的前端项目位于 `visualization/ontology-refactored` 目录下。

- 入口页面：`visualization/ontology-refactored/index.html`
- 主逻辑入口：`visualization/ontology-refactored/src/main.js`
- 组件库：`visualization/ontology-refactored/src/components/` (如 `OntologyGraph.js`, `ParseGraph.js`, `TerminalPanel.js` 等)
- 全局状态管理：`visualization/ontology-refactored/src/store/index.js`
- 接口请求：`visualization/ontology-refactored/src/api/backend.js`

### 后端 (Flask)

- Flask 入口：`backend/app.py`
- 解析主链：`backend/parser.py`
- 评估逻辑：`backend/evaluator.py`
- 质量分析：`backend/quality_analyzer.py`

### 本体与 prompt

- 本体主文件：`ontology/schemas/legal_ontology_v2.yaml`
- prompt 渲染器：`ontology/generators/prompt_renderer.py`
- 三类 prompt 快照：
  - `ontology/prompts/auto_v5_civil.txt`
  - `ontology/prompts/auto_v5_criminal.txt`
  - `ontology/prompts/auto_v5_admin.txt`

## 运行方式

### 1. 启动后端 API 服务

使用本仓库专属的 `ontology` 虚拟环境启动后端服务。后端运行在 `9120` 端口。

```bash
cd /home/sxc/wendao/remote-test/backend
../ontology/bin/python app.py
```
*(注意：重构后的前端不再依赖 Flask 托管静态文件，所以不需要 `--serve-files` 参数，端口默认为 9120)*

### 2. 启动前端可视化服务

前端 `ontology-refactored` 目录是基于 Vite 的现代前端工程。

**安装依赖（首次或依赖丢失时）：**
```bash
export PATH=/home/sxc/wendao/remote-test/node-v20.12.2-linux-x64/bin:$PATH
cd /home/sxc/wendao/remote-test/visualization/ontology-refactored
npm install
```

**启动开发服务器：**
```bash
export PATH=/home/sxc/wendao/remote-test/node-v20.12.2-linux-x64/bin:$PATH
cd /home/sxc/wendao/remote-test/visualization/ontology-refactored
npm run dev
```
前端开发服务器将运行在 `5174` 端口。你可以通过 `http://<your-ip>:5174` 访问重构后的可视化页面。

### 3. 仅运行离线抽取

```bash
python3 extraction/llm_extractors/guiding_case_extractor_v3.py \
  --input data/raw/test_20_new.csv \
  --output data_lake/extracted_v3.jsonl \
  --workers 3
```

## Prompt 生成与刷新

### 设计原则

当前链路的目标是：
1. 只维护本体结构文件
2. prompt 由本体结构自动渲染
3. few-shot 从 `data_lake` 候选池自动选取
4. 当本体变化时，能看到“变化了什么”和“few-shot 是否覆盖”

### 统一刷新三类 prompt

修改本体、补充候选样本或手动调整提示词细节后，必须运行以下命令刷新：

```bash
python3 scripts/refresh_prompt_snapshots.py
```

它会做四件事：
1. 重新生成三类 prompt 快照
2. 对比当前本体与上次刷新时的本体摘要差异
3. 检查当前 few-shot 是否覆盖新增实体 / 字段 / 关系
4. 输出每类 prompt 的元数据与人类可读报告
5. 同步生成本体驱动的评估 prompt `ontology/prompts/auto_ontology_evaluation.txt`

## 当前真实链路

### 本体驱动 prompt

```text
ontology/schemas/legal_ontology_v2.yaml
  -> ontology/generators/ontology_reader.py
  -> ontology/generators/prompt_renderer.py
  -> scripts/generate_prompt.py / scripts/refresh_prompt_snapshots.py
  -> ontology/prompts/auto_v5_*.txt
```

### 网页链路

```text
网页 (Vite 5174 端口) -> 触发解析/评估
  -> 代理转发至 backend/app.py (Flask 9120 端口)
  -> backend/parser.py (LLM 抽取)
  -> 返回 json_result / graph / score / issues 
  -> 前端 store 更新 -> 组件响应 (TerminalPanel, ParseGraph)
  -> /api/save 写入 data_lake 候选池
```

## 目录说明

```text
remote-test/
├── README.md                   # 本文件 (Refactored)
├── README_back.md              # 重构前旧版 README
├── backend/                    # Flask API 与网页解析链
├── data/                       # 原始 CSV、处理结果、参考资料
├── data_lake/                  # 解析输出、人工保存、实验结果、gold
├── docs/                       # 说明文档、方案、历史报告
├── extraction/                 # 离线抽取器
├── ontology/                   # 本体 schema、prompt 模板、生成器
├── scripts/                    # 各类 CLI、审计、刷新、迁移与批处理脚本
├── visualization/
│   ├── ontology-refactored/    # ★重构后的现代前端工程 (Vite + 组件化)
│   └── ...                     # 旧版前端文件和生成脚本
└── ...
```

## 后续会话提醒

如果后续会话丢失上下文，默认先做三件事：
1. 读本 README
2. 确认 `backend/app.py`、`backend/parser.py`、`scripts/refresh_prompt_snapshots.py` 的当前状态
3. 确认前端项目位于 `visualization/ontology-refactored/`，采用 Vite 构建。
4. 再开始改代码，不要直接在根目录新增脚本。
