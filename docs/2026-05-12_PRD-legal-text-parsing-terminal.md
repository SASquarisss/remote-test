# PRD: 法律文本解析终端面板

> **项目**: 法律本体论知识图谱系统  
> **文档版本**: v1.0  
> **关联页面**: `ontology_v2.2.html`, `admin_instances.html`  
> **关联模块**: `guiding_case_extractor_v3.py`, `scripts/visualization/generate_admin_vis.py`

---

## 1. 产品概述

### 1.1 问题陈述

当前法律本体论知识图谱系统 `ontology_v2.2.html` 仅展示静态的预定义本体结构图。用户（法律研究人员/数据管理员）无法直接在页面上对任意的法律文本进行即时解析和可视化探索。现有解析流程依赖离线脚本（`guiding_case_extractor_v3.py`），需要操作 CSV 文件和命令行，使用门槛高、反馈周期长。

### 1.2 解决方案

在 `ontology_v2.2.html` 页面底部添加**可伸缩的任务终端面板**，允许用户：
1. 直接粘贴任意法律文本
2. 一键调用 LLM 进行结构化解析
3. 即时查看解析结果（格式化 JSON + 知识图谱图）
4. 将结果保存到数据湖，自动出现在 `admin_instances.html` 的选择列表中

### 1.3 目标用户

- 法律数据管理员: 快速验证新案例的解析质量
- 法律研究员: 对特定文本片段进行试验性解析
- 系统运维人员: 测试 LLM 解析管线的可用性

### 1.4 成功指标

- 一次解析全流程（输入 → LLM → 展示）在 30 秒内完成
- 保存后 `admin_instances.html` 可立即选择新案例
- LLM 解析失败时给出明确的错误提示和容错路径

---

## 2. 功能详细描述

### 2.1 终端面板基础交互

| 需求 ID | 描述 | 优先级 |
|---------|------|--------|
| F-1.1 | 面板初始状态下缩小为页面底部的窄条（32px 高度），类似 Mac Dock 的收起效果 | P0 |
| F-1.2 | 窄条显示提示文字 "📋 法律文本解析终端 | 点击展开" | P0 |
| F-1.3 | 鼠标单击窄条 → 面板向上展开为 60vh 高度的三栏面板（CSS transition 动画） | P0 |
| F-1.4 | 展开面板的标题栏有收缩按钮，点击后收回底部 | P0 |
| F-1.5 | 面板展开时，原 ontology 图谱的高度自适应缩小（flex 布局调整） | P1 |

### 2.2 三栏布局

```
┌─────────────────────────────────────────────────────┐
│ 📋 法律文本解析终端                          [✕]  │ ← 深色标题栏 (#1a1a2e)
├────────────┬──────────────────┬─────────────────────┤
│  左栏 30%  │   中栏 35%       │   右栏 35%          │
│            │                  │                     │
│ textarea   │ pre (格式化JSON) │ div#visContainer    │
│ 输入文本   │ 只读展示         │ vis-network KG展示   │
│            │                  │                     │
│ [一键解析] │                  │                     │
│            │                  │                     │
│ 状态提示   │                  │                     │
├────────────┴──────────────────┴─────────────────────┤
│ [💾 保存]  (解析完成后出现)   状态: 就绪           │
└─────────────────────────────────────────────────────┘
```

#### F-2.1 左栏 — 输入区
- **textarea**: 多行文本输入框，占左栏大部分空间
  - placeholder: "在此粘贴法律文本（原始案件信息、裁判文书等任意文本）"
  - 高度自适应，最小 120px，建议 ~40 行可见
- **"一键解析"按钮**: 蓝色主题 (#2980b9)，hover 加深
  - 点击后禁用按钮，显示 "正在解析..." + 旋转加载动画
  - 如果 textarea 为空，按钮不可用并提示 "请先输入文本"
- **状态提示行**: 显示 "就绪" / "正在解析..." / "解析完成" / "解析失败" / "保存成功"

#### F-2.2 中栏 — JSON 结果展示
- `<pre>` 标签展示格式化的 JSON 字符串
- 只读模式，自动缩进 2 空格
- 行号可选（纯视觉辅助）
- 初始显示 "等待解析结果..."
- 支持 < 100KB JSON（正常解析结果 ~5-20KB）
- **重要**: 使用与 ontology 一致的字体（monospace: SFMono-Regular, Consolas）

#### F-2.3 右栏 — 知识图谱可视化
- `vis-network` 渲染容器，与 ontology 布局一致
- 初始显示 "等待解析结果" 居中提示
- 配色复用 ontology ROOT_COLORS 和 ADMIN_SHAPES
- 节点交互（hover 显示 title tooltip，点击弹出 detailPanel）
- 物理引擎: forceAtlas2Based（与 admin_instances.html 一致）
- 解析成功后自动渲染，失败后显示错误信息

### 2.3 解析流程

```
用户输入文本
     │
     ▼
前端 POST /api/parse  { text: "..." }
     │
     ▼ (后端)
┌─────────────────────────────────────────┐
│  1. 将输入文本构建为字典格式              │
│     (模拟 CSV 行结构，填充到相关字段)      │
│                                         │
│  2. build_llm_input(dict_row)           │
│     → 拼接 LLM 输入文本                  │
│                                         │
│  3. call_llm(prompt, input_text, config) │
│     → LLM 返回结构化 JSON                │
│                                         │
│  4. 后处理管线:                          │
│     enforce_case_level()                 │
│     enforce_source_url()                 │
│     fill_empty_provision_content()       │
│                                         │
│  5. evaluate_output()                   │
│     → score + issues                     │
│                                         │
│  6. KG 转换:                             │
│     复用 kg_convert() 逻辑               │
│     → nodes[] + edges[]                 │
└─────────────────────────────────────────┘
     │
     ▼
返回: { row_id, json_result, nodes, edges, score, issues, case_name }
     │
     ▼ (前端)
┌─────────────────────────────────────────┐
│  中栏: 展示格式化 JSON                    │
│  右栏: vis-network 渲染 nodes/edges      │
│  底部: 显示 score 和 issues 提示          │
│  底部: 出现 [保存] 按钮                   │
└─────────────────────────────────────────┘
```

### 2.4 保存与持久化

#### F-4.1 保存按钮
- 仅解析成功后才显示
- 位置: 面板最底部（三栏下方）
- 点击后 POST /api/save

#### F-4.2 存储结构
- **主数据文件**: `data_lake/manual_parsed.jsonl`
  - 追加模式，每行一个完整 JSON 对象
  - 格式与 `extracted_v2.2_admin_all.jsonl` 兼容
  - 每条记录的字段: `{row_id, input, output, eval, source: "manual"}`
- **row_id 生成规则**: `manual_{timestamp}`（如 `manual_20260512_173000`）
- **案例名称**: 从 LLM 输出的 `guiding_case.guiding_case_name` 提取

#### F-4.3 索引同步
- **索引文件**: `visualization/data/cases_index.json`
  - 格式: `[{row_id, case_name, case_type, version}]`
  - 每次保存后自动追加，覆盖写入完整索引
- **admin_instances.html 加载**:
  - 从 cases_index.json 加载案例列表（新增 fetch 逻辑）
  - 与已有的 ALL_GRAPHS 合并显示

#### F-4.4 索引文件格式 (cases_index.json)
```json
[
  {
    "row_id": "manual_20260512_173000",
    "case_name": "某某公司与某某局行政纠纷案",
    "case_type": "administrative",
    "version": 1,
    "source": "manual"
  },
  {
    "row_id": "3358",
    "case_name": "法国某某某兄弟股份有限公司等与李某某等商标撤销复审行政纠纷案",
    "case_type": "administrative",
    "version": 1,
    "source": "batch"
  }
]
```

---

## 3. API 接口定义

### 3.1 POST /api/parse

解析用户输入的法律文本。

**Request**:
```json
{
  "text": "人民法院案例库入库编号: 2023-09-3-029-028\n案例名称: 法国某某某兄弟股份有限公司等与李某某等商标撤销复审行政纠纷案\n案由: 行政-商标相关行政案件\n基本案情: 某某某公司系第G某某号注册商标专用权人...\n裁判理由: ...\n相关法条: 《中华人民共和国商标法》第四十四条第四项..."
}
```

**Response (200)**:
```json
{
  "row_id": "manual_20260512_173000",
  "case_name": "法国某某某兄弟股份有限公司等与李某某等商标撤销复审行政纠纷案",
  "json_result": {
    "guiding_case": { ... },
    "case_type": { ... },
    "court_cases": [...],
    "legal_subjects": [...],
    "legal_provisions": [...],
    ...
  },
  "nodes": [
    { "id": "gc_manual_20260512_173000", "label": "...", "type": "GuidingCase", "group": "manual_20260512_173000", "title": "...", "level": 0 },
    { "id": "courtcase_manual_20260512_173000_0", ... },
    { "id": "subj_manual_20260512_173000_0", ... }
  ],
  "edges": [
    { "from": "gc_manual_20260512_173000", "to": "ct_manual_20260512_173000", "label": "classified_as" },
    { "from": "gc_manual_20260512_173000", "to": "courtcase_manual_20260512_173000_0", "label": "has_court_case" }
  ],
  "score": 85.0,
  "issues": [
    "legal_provisions[0].content 为空",
    "evidence 为空"
  ]
}
```

**Response (4xx/5xx)**:
```json
{
  "error": "LLM 调用失败: ...",
  "detail": "在第 3 次重试后放弃"
}
```

### 3.2 POST /api/save

保存解析结果。

**Request**:
```json
{
  "row_id": "manual_20260512_173000",
  "json_result": { ... },
  "case_name": "某某公司与某某局行政纠纷案"
}
```

**Response (200)**:
```json
{
  "status": "ok",
  "file": "data_lake/manual_parsed.jsonl",
  "case_index_updated": true
}
```

### 3.3 GET /api/health

健康检查。

**Response (200)**:
```json
{
  "status": "ok",
  "api_key_configured": true,
  "prompt_loaded": true,
  "data_dir_exists": true
}
```

### 3.4 GET /api/cases（新增）

获取所有可用案例列表（供 admin_instances.html 加载）。

**Response (200)**:
```json
{
  "cases": [
    { "row_id": "3358", "case_name": "...", "case_type": "...", "source": "batch", "version": 1 },
    { "row_id": "manual_20260512_173000", "case_name": "...", "case_type": "...", "source": "manual", "version": 1 }
  ]
}
```

---

## 4. 数据流图

```
┌──────────────┐     ┌─────────────────────┐     ┌──────────────┐
│  ontology_   │     │  Backend Flask API   │     │  LLM         │
│  v2.2.html   │────▶│  (port 9120)         │────▶│  (DeepSeek)  │
│              │     │                      │     │              │
│  1. 用户输入  │     │  POST /api/parse     │     │  7. call_llm │
│    文本      │     │  build_llm_input()   │◀────│  返回 JSON   │
│  2. 点击解析  │     │  process_one()       │     └──────────────┘
│  3. 显示结果  │◀────│  kg_convert()        │
│  4. 点击保存  │────▶│  POST /api/save      │
└──────────────┘     │  → man_parsed.jsonl  │
                     │  → cases_index.json │
                     └─────────────────────┘
                              │
                              ▼
                     ┌──────────────────────┐
                     │  admin_instances.html │
                     │  GET /api/cases       │
                     │  → 下拉框出现新案例   │
                     └──────────────────────┘
```

---

## 5. 存储结构

### 5.1 文件布局

```
remote-test/
├── backend/                          # 新增：后端服务
│   ├── app.py                        # Flask 主入口
│   ├── parser.py                     # 解析逻辑（复用 extractor）
│   └── requirements.txt              # 依赖
├── data_lake/
│   ├── extracted_v2.2_admin_all.jsonl # 已有：批量解析结果
│   └── manual_parsed.jsonl           # 新增：手动解析结果（追加）
├── visualization/
│   ├── ontology_v2.2.html            # 修改：添加终端面板
│   ├── admin_instances.html          # 修改：从索引加载案例
│   └── data/
│       └── cases_index.json          # 新增：案例索引（admin 加载用）
├── scripts/prompts/
│   └── guiding_case_ontology_aligned_v3.txt  # 已有 prompt
├── extraction/llm_extractors/
│   └── guiding_case_extractor_v3.py  # 已有：被复用的核心逻辑
└── config.yaml                       # 已有：LLM 配置
```

### 5.2 manual_parsed.jsonl 格式（每行一个 JSON）

```json
{
  "row_id": "manual_20260512_173000",
  "source": "manual",
  "input": {
    "raw_text": "用户输入的原始文本（截断到前 200 字符）",
    "timestamp": "2026-05-12T17:30:00"
  },
  "output": {
    "guiding_case": { ... },
    "case_type": { ... },
    "court_cases": [...],
    "legal_subjects": [...],
    "legal_provisions": [...],
    "attorneys": [...],
    "judges": [...],
    "prosecutors": [...],
    "trial_organizations": [...],
    "evidence": [...],
    "judgment_results": [...],
    "case_summary": { ... }
  },
  "eval": {
    "score": 85.0,
    "issues": ["..."],
    "court_case_count": 3,
    "provision_count": 5
  },
  "timestamp": "2026-05-12T17:30:00"
}
```

### 5.3 cases_index.json 格式

```json
[
  {
    "row_id": "manual_20260512_173000",
    "case_name": "某某公司与某某局行政纠纷案",
    "case_type": "administrative",
    "version": 1,
    "source": "manual"
  },
  {
    "row_id": "3358",
    "case_name": "法国某某某兄弟股份有限公司等与李某某等商标撤销复审行政纠纷案",
    "case_type": "administrative",
    "version": 1,
    "source": "batch"
  }
]
```

---

## 6. 前端集成方案

### 6.1 嵌入方式

在 `ontology_v2.2.html` 的 `</body>` 前插入终端面板的 HTML 结构 + CSS 样式 + JS 逻辑。

**HTML 结构**（插在 `</body>` 之前）:
```html
<!-- Terminal Panel (collapsed) -->
<div id="terminalBar" onclick="toggleTerminal()">
  📋 法律文本解析终端 | 点击展开
</div>

<!-- Terminal Panel (expanded) -->
<div id="terminalPanel">
  <div class="tp-header">
    <span>📋 法律文本解析终端</span>
    <button class="tp-close" onclick="toggleTerminal()">✕</button>
  </div>
  <div class="tp-body">
    <div class="tp-left">
      <textarea id="tpInput" placeholder="在此粘贴法律文本..."></textarea>
      <button id="tpParseBtn" onclick="startParse()">⚡ 一键解析</button>
      <div id="tpStatus">就绪</div>
    </div>
    <div class="tp-middle">
      <pre id="tpJsonOutput">等待解析结果...</pre>
    </div>
    <div class="tp-right">
      <div id="tpVisContainer"><div class="tp-empty">等待解析结果</div></div>
    </div>
  </div>
  <div class="tp-footer">
    <button id="tpSaveBtn" onclick="saveResult()" style="display:none">💾 保存</button>
    <span id="tpScore"></span>
  </div>
</div>
```

### 6.2 关键交互逻辑

```javascript
// 面板展开/收起
function toggleTerminal() { ... }  // CSS transition on height

// 解析
async function startParse() {
  const text = document.getElementById('tpInput').value.trim();
  if (!text) return alert('请先输入文本');
  setStatus('正在解析...', 'loading');
  
  const res = await fetch('http://localhost:9120/api/parse', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text })
  });
  const data = await res.json();
  
  // 展示 JSON
  document.getElementById('tpJsonOutput').textContent = 
    JSON.stringify(data.json_result, null, 2);
  
  // 渲染 vis-network
  renderVisNetwork(data.nodes, data.edges);
  
  // 保存结果到全局变量
  window._lastParseResult = data;
  document.getElementById('tpSaveBtn').style.display = 'inline-block';
}

// 保存
async function saveResult() {
  const result = window._lastParseResult;
  const res = await fetch('http://localhost:9120/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      row_id: result.row_id,
      json_result: result.json_result,
      case_name: result.case_name
    })
  });
  setStatus('保存成功', 'success');
}
```

### 6.3 vis-network 渲染

- **配色**: 复用 ontology 的 `ROOT_COLORS` 和 `ADMIN_SHAPES`
- **交互**: hover 显示 title tooltip，点击选中节点
- **布局**: forceAtlas2Based，物理引擎 150 次迭代后冻结
- **尺寸**: 节点大小按 level 分级（0: 35px, 1: 26px, 2: 20px）
- **连接**: 箭头指向，标签显示关系类型

### 6.4 admin_instances.html 集成方案

**方案**: 新增 `GET /api/cases` API，admin 页面通过 fetch 获取所有案例

修改 `admin_instances.html` 的 `<script>` 逻辑:

```javascript
// 原来: const ALL_GRAPHS = [...];  // 硬编码
// 改为:
let ALL_GRAPHS = [];
async function loadCaseIndex() {
  // 1. 先加载已有的批量案例（从索引文件）
  const idxRes = await fetch('data/cases_index.json');
  const index = await idxRes.json();
  
  // 2. 从 /api/cases 获取每个案例的完整图数据
  const casesRes = await fetch('http://localhost:9120/api/cases');
  const casesData = await casesRes.json();
  
  // 3. 合并
  ALL_GRAPHS = casesData.cases.filter(c => c.source === 'batch')
    .concat(casesData.cases.filter(c => c.source === 'manual'));
  
  // 4. 初始化
  populateSelectors();
  initNetwork(null);
}
```

**简化方案**（优先推荐）:
- `POST /api/save` 时同时追加写入 `visualization/data/cases_index.json`
- `admin_instances.html` 在 `<script>` 中通过 `fetch('data/cases_index.json')` 读取索引
- 然后对每个 batch 案例（已有完整数据嵌入页面）和 manual 案例（调用 API 获取）分别处理

---

## 7. 后端技术方案

### 7.1 技术选型

| 组件 | 选择 | 理由 |
|------|------|------|
| Web 框架 | Flask | 轻量，单机够用，无异步需求 |
| LLM SDK | openai | 复用已有集成 |
| 配置 | python-dotenv + yaml | 复用已有 config.yaml |
| CORS | flask-cors | 前端跨域调用 |
| 端口 | 9120 | 避免与已有服务冲突 |

### 7.2 代码复用策略

| 复用的函数 | 来源文件 | 复用方式 |
|-----------|---------|---------|
| `build_llm_input()` | `guiding_case_extractor_v3.py` | 复制到 parser.py |
| `call_llm()` | `guiding_case_extractor_v3.py` | 复制到 parser.py，简化参数 |
| `enforce_case_level()` | `guiding_case_extractor_v3.py` | 复制到 parser.py |
| `enforce_source_url()` | `guiding_case_extractor_v3.py` | 复制到 parser.py |
| `fill_empty_provision_content()` | `guiding_case_extractor_v3.py` | 复制到 parser.py |
| `evaluate_output()` | `guiding_case_extractor_v3.py` | 复制到 parser.py |
| `load_prompt()` | `guiding_case_extractor_v3.py` | 复制到 parser.py |
| KG 转换逻辑 | `scripts/visualization/generate_admin_vis.py` | 实现 `kg_convert()` 函数 |
| ROOT_COLORS | `ontology_v2.2.html` | 前端 JS 复用 |
| ADMIN_SHAPES | `admin_instances.html` | 前端 JS 复用 |

### 7.3 错误处理

| 场景 | 处理方式 |
|------|---------|
| LLM 超时 (180s) | 自动重试 3 次（指数退避） |
| JSON 解析失败 | 尝试截取最后一个完整 JSON 对象 |
| API Key 未配置 | 返回 500 + "API key not configured" |
| 文件写入失败 | 返回 500 + "Storage write failed" |
| 输入文本为空 | 前端拦截，不发送请求 |
| 输入过长 (>100KB) | 返回 413 Payload Too Large |

---

## 8. 非功能需求

### 8.1 性能
- API 响应时间: 典型 LLM 解析 ~15s，最长 180s（超时）
- 前端渲染: JSON 和 vis-network 渲染应在 500ms 内完成
- 面板展开/收起动画: 300ms ease

### 8.2 安全性
- API Key 仅从环境变量读取，不硬编码
- 服务仅监听 localhost + NGINX 反向代理（如需要）
- 输入文本长度限制: 100KB

### 8.3 兼容性
- 存储格式与 `extracted_v2.2_admin_all.jsonl` 完全兼容
- `admin_instances.html` 的图数据接口与现有 ALL_GRAPHS 兼容
- HTML/CSS/JS 无外部依赖（除 vis-network CDN）

### 8.4 可维护性
- `parser.py` 独立模块，与 `guiding_case_extractor_v3.py` 解耦
- 前端终端面板代码集中在 `</body>` 前，与主体逻辑隔离
- 注释标注 "=== Terminal Panel ===" 分隔线

---

## 9. 部署要求

### 9.1 启动方式

```bash
# 后端启动（端口 9120）
cd /root/remote-test
pip install -r backend/requirements.txt
python3 backend/app.py --port 9120

# 或使用 gunicorn（生产）
gunicorn -w 1 -b 0.0.0.0:9120 backend.app:app
```

### 9.2 环境变量

| 变量 | 来源 | 说明 |
|------|------|------|
| DEEPSEEK_API_KEY | `~/.hermes/.env` | DeepSeek API Key |
| REMOTE_TEST_ROOT | 自动检测 | 项目根路径 |

### 9.3 防火墙

```bash
ufw allow 9120/tcp  # 如需远程访问
```

---

## 10. 注意事项与风险

1. **LLM 成本**: 每次解析消耗 ~5K-15K tokens（input）+ ~2K-5K tokens（output），注意 API 费用
2. **并行冲突**: 手动解析和批量解析同时写 JSONL 时注意文件锁定
3. **端口冲突**: 确保 9120 端口未被占用
4. **CORS 问题**: 前端 localhost:8080 请求 localhost:9120 需要 CORS 支持
5. **大文本**: 超过 LLM context window 的输入需要先截断或摘要

---

## 附录 A: ontology_v2.2.html 的配色常量

```javascript
// ROOT_COLORS（复用）
var ROOT_COLORS = {
  LegalNorm:      { bg: '#2980b9', border: '#1a5276', group: 'LegalNorm系' },
  JudicialEntity: { bg: '#d35400', border: '#a04000', group: 'JudicialEntity系' },
  LegalSubject:   { bg: '#27ae60', border: '#1e8449', group: 'LegalSubject系' },
  Person:         { bg: '#16a085', border: '#0e6655', group: 'Person系' }
};

// ADMIN_SHAPES（复用）
const ADMIN_SHAPES = {
  'GuidingCase':    'hexagon',
  'CourtCase':      'box',
  'CaseSummary':    'ellipse',
  'JudgmentResult': 'diamond',
  'Evidence':       'ellipse',
  'LegalSubject':   'ellipse',
  'LegalProvision': 'ellipse',
};
```

## 附录 B: 文本到 CSV 行映射（服务器端）

当用户输入任意文本时，后端将其包装成类 CSV 行的结构：

```python
def text_to_csv_row(raw_text: str) -> dict:
    """将任意文本转换为 build_llm_input 所需的类似 CSV 行的字典"""
    row = {field: "" for field in HEADER_FIELDS}
    
    # 尝试从文本中提取结构化字段
    row["id"] = f"manual_{int(time.time())}"
    
    # 模式匹配提取
    if "入库编号" in raw_text:
        row["storage_no"] = extract_after(raw_text, "入库编号")
    if "案例名称" in raw_text:
        row["web_name"] = extract_after(raw_text, "案例名称")
    if "案由" in raw_text:
        row["case_type"] = extract_after(raw_text, "案由")
    if "基本案情" in raw_text:
        row["basic_facts"] = extract_section(raw_text, "基本案情")
    if "裁判理由" in raw_text:
        row["judgment_reason"] = extract_section(raw_text, "裁判理由")
    
    # 如果没有结构化标识，将全文放到 basic_facts
    if not any(row.values()):
        row["basic_facts"] = raw_text
        row["web_name"] = f"手动解析 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    
    return row
```

---

*文档版本: v1.0 | 最后更新: 2026-05-12 | 审批人: TBD*
