# remote-test

当前仓库已经不只是“本体定义”，而是一个围绕 `legal_ontology_v2.yaml` 运转的完整原型工程，包含：

- 本体 schema 与 prompt 自动生成
- few-shot 候选池与统一刷新脚本
- 离线抽取链与 `_meta` 追溯
- 前端可视化页面 `ontology_v2.2.html`
- Flask 后端解析 / 保存接口
- `data_lake` 分层与结构化候选池

这份 README 是当前会话和后续会话的默认入口文档。

## 开发约定

- 每次重启会话，先读本文件，再开始改动。
- 尽量不要在仓库根目录新增代码；优先放到 `scripts/`、`backend/`、`visualization/`、`docs/` 等已有目录。
- 用户要求“每次修改后都重新启动”时，默认重启当前前后端入口：

```bash
/root/.hermes/hermes-agent/venv/bin/python /root/remote-test/backend/app.py --serve-files --host 0.0.0.0 --port 9119
```

- 如果 `9119` 端口已被别的进程占用，先确认占用情况，再决定是否换端口或停止旧进程。
- 当前前端主页面部署目标是：
  `http://124.222.18.99:9119/ontology_v2.2.html`

## 当前主入口

### 前端

- 主页面：`visualization/ontology_v2.2.html`
- 主页面本体 schema 数据：`visualization/data/ontology_schema_data.js`
- 行政案例图谱页：`visualization/admin_instances.html`
- 静态本体可视化页：`visualization/ontology_viz.html`

### 后端

- Flask 入口：`backend/app.py`
- 解析主链：`backend/parser.py`
- 评估逻辑：`backend/evaluator.py`

### 本体与 prompt

- 本体主文件：`ontology/schemas/legal_ontology_v2.yaml`
- prompt 渲染器：`ontology/generators/prompt_renderer.py`
- 三类 prompt 快照：
  - `ontology/prompts/auto_v5_civil.txt`
  - `ontology/prompts/auto_v5_criminal.txt`
  - `ontology/prompts/auto_v5_admin.txt`

### 离线抽取

- 主 extractor：`extraction/llm_extractors/guiding_case_extractor_v3.py`
- 行政批处理 wrapper：`scripts/admin_batches/`
- 常用 prompt 生成 CLI：`scripts/generate_prompt.py`
- 统一刷新脚本：`scripts/refresh_prompt_snapshots.py`
- 结构化候选池沉淀脚本：`scripts/promote_structured_candidates.py`
- 行政实例页生成脚本：`scripts/visualization/generate_admin_vis.py`
- 本体页面 schema 数据生成脚本：`scripts/visualization/generate_ontology_schema_data.py`

## 目录说明

当前建议把根目录视为“项目壳层”，只保留高层配置、入口说明和少量基础文件。具体逻辑应放到子目录。

```text
remote-test/
├── README.md
├── Makefile
├── config.yaml
├── requirements.txt
├── docker-compose.yml
├── backend/                    # Flask API 与网页解析链
├── data/                       # 原始 CSV、处理结果、参考资料
├── data_lake/                  # 解析输出、人工保存、实验结果、gold
├── docs/                       # 说明文档、方案、历史报告
├── extraction/                 # 离线抽取器
├── ontology/                   # 本体 schema、prompt 模板、生成器
├── scripts/                    # 各类 CLI、审计、刷新、迁移与批处理脚本
├── tests/                      # 自动化测试
├── visualization/              # 前端页面与可视化资源
├── webui/                      # 另一套 WebUI 原型
├── api/                        # FastAPI 原型
└── pipelines/                  # 早期批处理 / 导入流水线
```

## 运行方式

### 1. 启动网页与 API

优先使用 Hermes venv：

```bash
/root/.hermes/hermes-agent/venv/bin/python /root/remote-test/backend/app.py --serve-files --host 0.0.0.0 --port 9119
```

说明：

- `--serve-files` 会让 Flask 同时托管 `visualization/` 下的静态页面。
- 根路径 `/` 默认返回 `ontology_v2.2.html`。
- 页面解析、保存、评估接口都走同一个 Flask 进程。

### 2. 仅运行离线抽取

```bash
python3 extraction/llm_extractors/guiding_case_extractor_v3.py \
  --input data/raw/test_20_new.csv \
  --output data_lake/extracted_v3.jsonl \
  --workers 3
```

常见可选参数：

- `--prompt-path`：直接指定 prompt 文件
- `--prompt-version`：使用旧版 prompt 分支
- `--meta-producer`：记录本次写出来源
- `--meta-batch-label`：记录批次标签

## Prompt 生成与刷新

### 设计原则

当前链路的目标是：

1. 只维护本体结构文件
2. prompt 由本体结构自动渲染
3. few-shot 从 `data_lake` 候选池自动选取
4. 当本体变化时，能看到“变化了什么”和“few-shot 是否覆盖”

### 单次生成 prompt

```bash
python3 scripts/generate_prompt.py --output /tmp/auto_prompt.txt
```

指定类别时，主要是为了匹配该类别的 few-shot 候选：

```bash
python3 scripts/generate_prompt.py \
  --output /tmp/auto_prompt_civil.txt \
  --case-type '民事-知识产权权属、侵权纠纷'
```

说明：

- 当前 `--case-type` 的核心作用是“把目标样本映射到民事 / 刑事 / 行政三大类”，从而选择对应 few-shot。
- 现在不是每次运行都需要重生成 prompt。
- 只有在本体结构变化、few-shot 候选池更新，或者你明确要刷新快照时，才建议重生成。

### 统一刷新三类 prompt

这是目前推荐的刷新方式：

```bash
python3 scripts/refresh_prompt_snapshots.py
```

它会做四件事：

1. 重新生成三类 prompt 快照
2. 对比当前本体与上次刷新时的本体摘要差异
3. 检查当前 few-shot 是否覆盖新增实体 / 字段 / 关系
4. 输出每类 prompt 的元数据与人类可读报告
5. 同步生成本体驱动的评估 prompt `ontology/prompts/auto_ontology_evaluation.txt`

刷新后会更新这些文件：

- `ontology/prompts/auto_v5_civil.txt`
- `ontology/prompts/auto_v5_criminal.txt`
- `ontology/prompts/auto_v5_admin.txt`
- `ontology/prompts/auto_ontology_evaluation.txt`
- `ontology/prompts/_meta/refresh_state.json`
- `ontology/prompts/_meta/refresh_report.md`
- `ontology/prompts/_meta/*.meta.json`

建议时机：

- 修改 `ontology/schemas/legal_ontology_v2.yaml` 后
- 新增或更新结构化 few-shot 候选后
- 需要确认本体变化是否已经被 few-shot 覆盖时

## Few-shot 候选池

### 当前数据来源

`scripts/generate_prompt.py` 当前不会扫描整个 `data_lake` 全量乱选，而是优先从以下层级选择：

1. `extracted_candidate_*`
2. `extracted_*`

不会参与 few-shot 候选的层：

- `fewshot_cmp_*`
- `compare*`
- `manual_*`

### 结构化候选池沉淀

把质量较高、图谱结构完整的结果沉到结构化候选池：

```bash
python3 scripts/promote_structured_candidates.py \
  data_lake/extracted_v5_civil_test.jsonl \
  --output data_lake/extracted_candidate_structured_v1.jsonl \
  --min-score 85
```

当前默认输出：

- `data_lake/extracted_candidate_structured_v1.jsonl`

入池条件的核心是：

- `eval.score` 达标
- 至少具备基本图谱可用性
- `facts / dispute_focuses / relations` 不再完全缺失

## data_lake 分层

当前最小分层由 `scripts/data_lake_layers.py` 统一定义。

| 层级 | 文件模式 | 作用 |
|---|---|---|
| `extracted_candidate` | `extracted_candidate_*` | 结构化 few-shot 候选池、网页可选候选保存层 |
| `extracted` | `extracted_*` | 历史正式候选池 / 主抽取产物 |
| `fewshot_cmp` / `compare` | `fewshot_cmp_*` / `compare*` | 实验输出，不参与 few-shot 候选 |
| `manual` | `manual_parsed.jsonl` / `manual_*` | 人工保存结果 |
| `gold` | `data_lake/gold/*` | 结构化 gold 层资产 |

## 网页解析与保存

### 解析

网页输入文本后，`backend/parser.py` 会：

1. 从原文里尽量提取案由等基础字段
2. 按民事 / 刑事 / 行政自动选择对应 prompt
3. 行政空输出时回退到 legacy prompt
4. 归一化图字段
5. 自动补足最小主链 `facts / dispute_focuses / relations`

### 保存

前端保存接口：`POST /api/save`

当前支持两个目标层：

| `target_layer` | 实际文件 | 含义 |
|---|---|---|
| `manual` | `data_lake/manual_parsed.jsonl` | 人工确认保存，不直接作为结构化 few-shot 候选 |
| `extracted_candidate` | `data_lake/extracted_candidate_manual_save_v1.jsonl` | 来自网页、但希望进入候选池体系的保存层 |

说明：

- `manual` 更偏人工编辑 / 人工留档。
- `extracted_candidate` 更偏“网页端补充的结构化候选样本”。
- 两者写入时都会补 `_meta`，便于后续追溯来源。

## 追溯与审计

### 追溯 extracted 产出链

```bash
python3 scripts/trace_extracted_lineage.py
```

优先级：

1. 先读记录内 `_meta`
2. 如果没有 `_meta`，再按文件名和仓内脚本规则推断

### 探查 data_lake 图谱覆盖

```bash
python3 scripts/probe_data_lake_graph_coverage.py
```

### 扫描正式候选池里是否有漏网样本

```bash
python3 scripts/audit_extracted_fewshot_pool.py
```

## 当前真实链路

### 本体驱动 prompt

```text
ontology/schemas/legal_ontology_v2.yaml
  -> ontology/generators/ontology_reader.py
  -> ontology/generators/prompt_renderer.py
  -> scripts/generate_prompt.py / scripts/refresh_prompt_snapshots.py
  -> ontology/prompts/auto_v5_*.txt
```

### 离线抽取链

```text
guiding_case_extractor_v3.py
  -> 调用 LLM
  -> 行政 fallback
  -> 归一化 / enrich_graph_output
  -> evaluate_output
  -> 写 data_lake/extracted_*.jsonl + _meta
```

### 网页链路

```text
ontology_v2.2.html
  -> backend/app.py:/api/parse
  -> backend/parser.py
  -> json_result / graph / score / issues
  -> /api/save
  -> manual 或 extracted_candidate
```

## 当前已知历史包袱

这些内容目前仍在仓库，但需要按“保留 / 归档 / 删除”继续治理：

- 根目录遗留的一次性脚本、旧页面、审计报告
- `data_lake` 中大量历史批次和实验 JSONL
- `remote-test/remote-test/` 下的疑似历史副本
- `api/`、`webui/`、`pipelines/` 中的旧原型和并行路线

处理原则：

- 先迁移出根目录
- 再判断是否归档
- 最后再决定是否删除

对应清理建议清单见：

- `docs/archive_cleanup_candidates.md`

## 环境提示

- 推荐 Python 环境：`/root/.hermes/hermes-agent/venv/bin/python`
- 依赖中会用到 `Flask`、`python-dotenv`、`openai`、`PyYAML`
- 如果要跑解析链，确保环境变量里有 `DEEPSEEK_API_KEY`

## 后续会话提醒

如果后续会话丢失上下文，默认先做三件事：

1. 读本 README
2. 确认 `backend/app.py`、`backend/parser.py`、`scripts/refresh_prompt_snapshots.py` 的当前状态
3. 再开始改代码，不要直接在根目录新增脚本
