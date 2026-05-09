# V3 提取管线技术审查报告

## 审查结果与修复方案

---

### 发现 1：case_level/binding_force 映射逻辑问题

**优先级：P1**

#### 现状分析

在现有提取结果中，case_level 字段在 18 条数据中有 15 条与 CSV 正确对应。问题聚焦在以下几个场景：

| row_id | CSV case_level | 输出 case_level | 输出 binding_force | 问题类型 |
|--------|---------------|----------------|-------------------|---------|
| 4365 | 02 | typical_case ✅ | "typical_case" ❌ | binding_force 值错误（应为 persuasive） |
| 5354 | 01 | reference_case ❌ | reference ✅ | case_level 映射错误（应为 guiding_case） |
| 3731 | 02 | reference_case ❌ | reference ✅ | case_level 映射错误（应为 typical_case） |
| 1146 | 02 | typical_case ✅ | reference ❌ | binding_force 值错误（应为 persuasive） |
| 6316 | \N | typical_case ❌ | reference | CSV 无数据但 LLM 推断为 typical_case |
| 7906 | 1 | guiding_case ✅ | mandatory ✅ | case_level="1" 无前导零 |

#### Root Cause

**1. binding_force 枚举值命名冲突（P0 root cause）**

Prompt 第 70 行定义了：
```
"指导性案例"→"mandatory"，"典型案例"→"persuasive"
```
Prompt 第 73 行定义了 case_level 映射：
```
"01"→"guiding_case"，"02"→"typical_case"，其他→"reference_case"
```

但 LLM 有时将 `binding_force` 误解为可以直接取 `case_level` 的枚举值（"typical_case"、"reference_case"），而非使用正确的约束力枚举值（"mandatory"/"persuasive"/"reference"）。问题在于：
- Prompt 第 73 行的注释写的是"案例层级"而非"约束力"，LLM 容易混淆这两个字段的枚举空间
- 没有强调 `binding_force` 和 `case_level` 是不同的枚举体系
- 没有要求 **严格从文本中推断** binding_force（如根据"指导性案例"/"典型案例"字眼），而是允许 LLM 自行判断

**2. case_level="01" 被映射为 reference_case（row 5354）**

CSV 中 case_level="01"，预期映射为 "guiding_case"，但 LLM 输出为 "reference_case"。存储编号 "2017-18-2-184-001"（最高法案例），文本中没有明确的"指导性案例"标识。LLM 可能因为文本内容觉得它不够"指导性"，覆盖了 CSV 字段的硬映射。

**3. case_level 字段已正确传递到 prompt 输入中**

我在 `build_llm_input` 函数中确认：`case_level` 字段作为"【审级】"被传递（第 82 行：`("case_level", "审级")`）。字段名标注为"审级"（trial level）而非"案例层级"（case level），是误导性标签。LLM 收到 `【审级】\n02\n` 或 `【审级】\n01\n`，但 prompt 中 case_level 的映射是"01→guiding_case，02→typical_case"。LLM 可能会认为"审级"应该输出一审/二审，而不把它当作案例层级的硬约束。

#### 修复方案

##### 方案 A：在 prompt 中增加 case_level 的硬约束指令（推荐）

```patch
--- a/scripts/prompts/guiding_case_ontology_aligned_v3.txt
+++ b/scripts/prompts/guiding_case_ontology_aligned_v3.txt
@@ -71,6 +71,8 @@
 - `case_level`: 案例层级。"01"→"guiding_case"（指导性案例），"02"→"typical_case"（典型案例），其他→"reference_case"（参考案例）
+  **注意：case_level 是直接从输入字段【案例层级】映射而来，你必须严格按照映射规则，不能自行推断。**
+  **注意：binding_force 与 case_level 是不同的字段，使用不同的枚举值体系，不能混淆。binding_force 枚举值为 mandatory|persuasive|reference，case_level 枚举值为 guiding_case|typical_case|reference_case。**
```

##### 方案 B：在 `build_llm_input` 中将 case_level 标签改为"案例层级"而非"审级"（同样需要）

```patch
--- a/extraction/llm_extractors/guiding_case_extractor_v3.py
+++ b/extraction/llm_extractors/guiding_case_extractor_v3.py
@@ -82,7 +82,7 @@
         ("trial_procedure", "审判程序"),
         ("trial_year", "裁判年份"),
-        ("case_level", "审级"),
+        ("case_level", "案例层级"),
```

##### 方案 C (推荐)：**后处理硬映射** — 在 process_one 或 evaluate 之后直接覆盖

这是最终的保险方案——不管 LLM 输出什么，都用 CSV 的 case_level 值硬覆盖输出中的 case_level，然后根据 case_level 硬映射 binding_force。

```python
def enforce_case_level(row: Dict[str, str], output: Dict[str, Any]) -> Dict[str, Any]:
    """根据CSV的case_level列，强制覆盖LLM输出的case_level和binding_force"""
    csv_cl = row.get("case_level", "").strip()
    cl_map = {"01": "guiding_case", "02": "typical_case"}
    bf_map = {"01": "mandatory", "02": "persuasive"}
    
    enforced_cl = cl_map.get(csv_cl, "reference_case")
    enforced_bf = bf_map.get(csv_cl, "reference")
    
    if "guiding_case" in output:
        output["guiding_case"]["case_level"] = enforced_cl
        output["guiding_case"]["binding_force"] = enforced_bf
    
    return output
```

方案 C 在 `process_one` 中调用 `output = enforce_case_level(row, output)`。**此方案优先级最高**，因为它消除了 LLM 对于此字段的所有自由度。

---

### 发现 2：`build_llm_input` 遗漏 web_url / source_url 字段

**优先级：P0**

#### 现状

`build_llm_input` 函数共定义了 13 个字段（第 75-89 行），但：
- ❌ `web_url`（已存在于 CSV HEADER 第 3 列）**未被包含**
- ❌ `judgment_mean`（已存在于 CSV HEADER 第 20 列）**未被包含**
- ❌ `key_words`（已存在于 CSV HEADER 第 7 列）**未被包含**

Prompt 输出格式第 152 行要求输出 `source_url`，但没有输入数据告知 LLM 该 URL。同样，prompt 第 70 行要求 `judgment_mean`，第 72 行要求 `key_words`，但 LLM 输入中无对应数据。

#### 修复方案

```patch
--- a/extraction/llm_extractors/guiding_case_extractor_v3.py
+++ b/extraction/llm_extractors/guiding_case_extractor_v3.py
@@ -74,7 +74,7 @@
 def build_llm_input(row: Dict[str, str]) -> str:
     fields = [
         ("web_name", "案例来源"),
+        ("web_url", "来源URL"),
         ("case_type", "案由分类"),
         ("storage_no", "入库编号"),
         ("court_name", "审理法院"),
@@ -86,6 +86,8 @@
         ("related_info", "相关案情/关联案件"),
         ("related_law", "相关法条"),
         ("related_judgment_body", "关联裁判文书"),
+        ("key_words", "关键词"),
+        ("judgment_mean", "裁判意义"),
     ]
```

---

### 发现 3：source_url 字段传入后是否需要更新 prompt 指引？

**优先级：P1**

#### 分析

Prompt 第 76-77 行已有 `source_url` 字段定义（只是留空输入）。加入 `web_url` 输入后：
1. 应当将输入中的 URL 值直接映射到输出的 `source_url` 字段
2. 目前的 prompt 仅定义了字段但未说明映射规则

#### 修复方案

在 prompt 的 GuidingCase 定义中补充映射指令：

```patch
--- a/scripts/prompts/guiding_case_ontology_aligned_v3.txt
+++ b/scripts/prompts/guiding_case_ontology_aligned_v3.txt
@@ -75,7 +75,7 @@
 - `storage_no`: 案例库内部编号
- - `source_url`: 来源URL
+ - `source_url`: 来源URL（直接使用输入中的【来源URL】字段值，原样传递，不要修改或留空）
```

同时，建议在 `process_one` 中也做后处理兜底：

```python
# Post-processing: enforce source_url from input
input_url = row.get("web_url", "").strip()
if input_url and "guiding_case" in output:
    if not output["guiding_case"].get("source_url"):
        output["guiding_case"]["source_url"] = input_url
```

---

### 发现 4：legal_provision.content 5.4% 缺失原因分析

**优先级：P1**

#### Root Cause

在 18 条共 74 条 provision 中，有 4 条（5.4%）的 `content` 为空，全部集中在 **row_id=4446**。原因如下：

1. **数据质量问题**：CSV 中 `related_law` 列全部为 `\N`（空），法律条文引用实际上存储在 `related_info` 列中。`related_info` 在 prompt 中被标注为"相关案情/关联案件"，而非"相关法条"。

2. **条文在原文中只有引用无原文**：row 4446 的 `related_info` 中包含 5 条法律引用：
   - 《企业破产法》第21条 → 有 content（从 judgment_reason 中找到原文）
   - 《企业破产法规定（二）》第47条 → 无 content（仅纯引用）
   - 《民事诉讼法》第29条 → 无 content（仅纯引用）
   - 《民诉法解释》第24条 → 无 content（仅纯引用）
   - 《知识产权法庭规定》第14条 → 无 content（仅纯引用）

3. **Prompt 要求从文本中提取 50-100 字原文**，但这些条文在 `judgment_reason` 中没有被完整引用原文，LLM 无法找到原文。

4. **更根本的问题**：prompt 第 125 行要求 `content` 是"必填"且"不能为空"，但 LLM 在实在找不到原文时会留空。需要 **两阶段策略**：先尝试提取原文，如果找不到则使用条文标题+条款号作为 fallback。

#### 修复方案

##### 方案 A：在 prompt 中增加 content 的 fallback 规则

```patch
- `content`: **必填**，法条引用原文片段。从文本中找到该法条被引用的上下文，提取50-100字左右。不能为空。
+ `content`: **必填**，法条引用原文片段。从文本中找到该法条被引用的上下文，提取50-100字左右。如果文本中没有该法条的完整原文，则使用该法条的名称和条款号作为内容（如"《中华人民共和国企业破产法》第四十七条：……"的概括说明），不能为空。
```

##### 方案 B：后处理兜底

```python
for p in legal_provisions:
    if not p.get("content", "").strip():
        p["content"] = f"《{p['statute']}》第{p['article']}条（提取自相关法条引用）"
```

---

### 发现 5：extractor_v3.py 长时间运行稳定性评估

**优先级：P2**

#### 风险评估

| 风险点 | 现状 | 风险等级 |
|--------|------|---------|
| **并发异常处理** | `call_llm` 有 3 次重试（指数退避 2^0, 2^1, 2^2 秒） | 低 |
| **文件写入竞争** | `as_completed` 循环中每次 `open(path, "a")` + `write` + 隐式 close，Python 文件追加是原子的（单条写入 < PIPE_BUF），但并发无竞争问题因为主线程单线程写入 | 低 |
| **单线程瓶颈** | 虽然有 ThreadPoolExecutor，但写入和 eval 在主线程串行进行，worker 提交到 executor 后主线程等待 future。不存在写入竞争 | 低 |
| **超时重启** | `call_llm` 设置 `timeout=180` 秒但这是 requests 库的 http 超时参数。OpenAI SDK 的超时机制可靠，3次重试后 raise 到 `process_one` | 中 |
| **无断点续传** | 没有 checkpoint 机制。如果程序在中间崩溃（比如第 100/300 条），已完成的结果已写入文件（逐条追加），但未记录进度索引。重启会从指定 start 开始但无法跳过已处理的 | **高** |
| **无速率限制** | 没有对 API 调用进行速率限制（rate limiting），并发 workers=3 时 3 个请求同时发出。如果 API 有每分钟请求数限制，会触发 429 错误 | 中 |
| **内存管理** | 所有结果存储在 Python 进程空间，对大文件（如 10000 行）无流式处理。`load_csv` 一次性加载所有行到内存 | 中 |
| **日志缺失** | 使用 `print` 而非 logging 模块，无文件日志，重启后无法追溯历史错误 | **高** |

#### 修复方案

##### 1. 添加 checkpoint/断点续传（P1）

```python
def load_checkpoint(checkpoint_path: str) -> set:
    """加载已处理完成的 row_ids"""
    if not os.path.exists(checkpoint_path):
        return set()
    done = set()
    with open(checkpoint_path, "r") as f:
        for line in f:
            try:
                data = json.loads(line)
                done.add(data.get("row_id", ""))
            except:
                pass
    return done

def save_checkpoint(output_path: str, result: Dict[str, Any]):
    """追加写入并立即 flush"""
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())

# 在 main 中使用:
done_ids = load_checkpoint(str(output_path))
rows = [r for r in rows if r.get("id") not in done_ids]
print(f"Skipping {len(done_ids)} already processed rows, processing {len(rows)} remaining")
```

##### 2. 增加 API 速率限制（P2）

```python
import time
from threading import Lock

_api_lock = Lock()
_last_call_time = 0.0

def rate_limited_call_llm(prompt, text, config):
    global _last_call_time
    with _api_lock:
        now = time.time()
        elapsed = now - _last_call_time
        if elapsed < 0.5:  # 最多每秒2个请求
            time.sleep(0.5 - elapsed)
        result = call_llm(prompt, text, config)
        _last_call_time = time.time()
        return result
```

##### 3. 用 logging 替换 print（P2）

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(REPO_ROOT / "logs/extractor_v3.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
```

##### 4. 更好的异常恢复（P1）

```python
# process_one 中的更健壮的异常处理
try:
    output = call_llm(prompt, text, config)
except RuntimeError as e:
    # 3次重试全部失败
    output = None
    logger.error(f"[{idx}] All retries exhausted for {row_id}: {e}")
except json.JSONDecodeError as e:
    # LLM 返回了非 JSON
    output = None
    logger.error(f"[{idx}] JSON decode error for {row_id}: {e}")
except Exception as e:
    output = None
    logger.exception(f"[{idx}] Unexpected error for {row_id}: {e}")
```

---

## 优先级汇总

| # | 问题 | 优先级 | 影响范围 |
|---|------|--------|---------|
| 1 | case_level 映射不准确：prompt 需加强 + 后处理硬映射 | **P0** | 所有 case_level 字段 |
| 2 | build_llm_input 遗漏 web_url/judgment_mean/key_words | **P0** | source_url 字段全部留空；judgment_mean/key_words 推导依赖文本 |
| 3 | source_url 传入后 prompt 需明确映射说明 | **P1** | source_url 填充率 |
| 4 | legal_provision.content 5.4% 缺失：数据列错位 + 无 fallback | **P1** | content 字段完整性 |
| 5a | 无断点续传（checkpoint），长运行中断后需重跑 | **P1** | 大规模提取场景 |
| 5b | API 速率限制缺失 | **P2** | 大规模提取场景 |
| 5c | 日志系统缺失 | **P2** | 可观测性 |
