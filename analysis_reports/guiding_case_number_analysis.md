# 字段定义与映射问题分析报告：`guiding_case_number`

**报告人**: legal_pm  
**日期**: 2026-05-10  
**项目**: 法律知识图谱  

---

## 1. 字段定义溯源

### 1.1 Ontology 中的语义

根据 `legal_ontology_v2.yaml`（第48-53行）：

```yaml
GuidingCase:
  required: [guiding_case_number, issuing_court_id, publication_date, guiding_points, binding_force]
```

`guiding_case_number` 是 `GuidingCase`（指导性案例）节点的 **必填字段**。其目标语义是：**最高人民法院正式发布的指导性案例的官方编号**。

在中国法律实践中，"指导案例XX号"（如"指导案例24号"）是由最高人民法院审判委员会审议通过、统一编号发布的正式指导性案例编号体系。截至2026年，最高法已发布约1-25批指导性案例，其中民商事方向仅数十个。

### 1.2 Prompt 中的定义

在 `auto_v5_civil.txt`（第54行）中，prompt 对该字段的说明为：

```
guiding_case_number | 如'指导案例XX号'，从storage_no或文本推断; 如无则留空
```

### 1.3 歧义信号

Prompt 中的指引本身存在歧义：
- 建议"从storage_no推断" → 但这暗示 LLM 将 `storage_no` 视为 `guiding_case_number` 的备选来源
- 但 `storage_no` 的值如 `2024-13-2-160-011` 或 `D2025-161-1-053-677` 明显不是"指导案例XX号"格式
- 最终判定："如无则留空" → 正确的语义是让 LLM 输出空字符串

---

## 2. 源数据审计

### 2.1 CSV 字段结构

CSV `civil_cases_only.csv` 共230条记录，包含以下相关字段：

| 字段名 | 示例值 | 说明 |
|--------|--------|------|
| `storage_no` | `2024-13-2-160-011`, `D2025-161-1-053-677` | 案例库内部编号 |
| `web_name` | `人民法院案例库`, `多元解纷案例库` | 来源标识 |
| `case_level` | `01`, `02`, `\N`, `04` | 案例层级 |
| `title` | (空) | 所有记录为空 |

### 2.2 关键发现

**源数据中不存在"指导案例XX号"信息。**

- 在230条记录中，**0条**包含"指导案例XX号"文本（正则搜索 `指导案例\d+号` 无任何匹配）
- 仅 **1条** 在 `judgment_reason` 中提及"指导性案例"（属于裁判文书正文引用，非案例编号字段）
- `storage_no` 的格式统一为 `YYYY-XX-X-XXX-XXX`（人民法院案例库）或 `DYYYY-XXX-X-XXX-XXX`（多元解纷案例库），**并非**指导性案例编号格式
- `case_level` 分布：`01`（指导性案例）= 10条，`02`（典型案例）= 133条，`\N`（缺失）= 85条，`04` = 2条

### 2.3 `storage_no` 应该映射到什么字段？

`storage_no` 是案例库的**内部归档编号**，而非最高法发布的指导性案例编号。在 Ontology 中它已有独立字段：

```yaml
GuidingCase.storage_no  # 已在prompt和schema中定义
```

在实际提取结果中，`storage_no` 被 LLM **正确提取**了（230条中有230条非空），说明 LLM 理解 `storage_no` 是一个独立的字段。

---

## 3. 问题根因判定

经过全面审计，`guiding_case_number` 字段154/158为空（实际是230条全部为空）的根因判定如下：

### 根因级别：**数据本身不存在 ≠ 代码/模型问题**

| 根因 | 贡献度 | 详细说明 |
|------|--------|----------|
| **源数据缺失** | **80%** | CSV中没有任何字段包含"指导案例XX号"格式的信息。这不是LLM提取失败，而是源数据中本身就没有这个信息。 |
| **Prompt表述不够明确** | **15%** | Prompt说"如无则留空"是正确的兜底策略，但"从storage_no或文本推断"容易让人误以为storage_no可以转换为guiding_case_number。事实上两者是不同的编号体系。实际上 LLM 正确地判断了 storage_no 不是"指导案例XX号"格式并留空了。 |
| **Ontology设计问题** | **5%** | `GuidingCase` 节点要求 `guiding_case_number` 为必填字段（`required`），但230条数据中只有10条的 `case_level='01'`（指导性案例），其余均为典型案例或普通参考案例——这些案例本就不应该有"指导案例XX号"。将 `guiding_case_number` 设为必填字段的设计与数据实际分布不匹配。 |

### 补充：LLM 实际行为正确

验证确认：
- LLM 在输出中**正确提取了** `storage_no`（如 `2024-13-2-160-011`）
- LLM 正确地将 `storage_no` 放入了 `guiding_case.storage_no` 字段而非 `guiding_case_number`
- `guiding_case_number` 被置空是因为 LLM 判断源数据中没有"指导案例XX号"格式的信息
- **没有任何一条输出包含非空的 `guiding_case_number`**，因为源数据中确实不存在

### 关于 "154/158" 统计口径

用户提到的"154/158为空"是基于当时部分数据处理的结果。全量230条验证显示 **230条中0条有 `guiding_case_number`**，比例更极端。

---

## 4. 修复建议

### 方案一：区分两种场景，按 `case_level` 处理（推荐）

**策略**：
- `case_level='01'`（指导性案例）：从 `storage_no` 所在年份和序列号，或者从裁判文书中是否有"本院系最高人民法院...指导案例..."等文本推断
- `case_level='02'` / `04` / `\N`（典型案例/其他）：`guiding_case_number` 应输出 `""`（空），因为典型案例没有最高法发布的指导性案例编号

**Prompt 修改**（`auto_v5_civil.txt` 第54行）：

```
guiding_case_number | 仅当case_level='01'（指导性案例）时填写，格式如'指导案例XX号'；从文本（如"指导案例第XX号"）推断；典型案例/普通案例留空
```

**优点**：
- 语义清晰，区分了两类案例的编号体系
- 与数据实际情况匹配
- 只需修改 prompt，无需代码改动
- LLM 行为可预测

**缺点**：
- 对于真正需填充的指导性案例（230条中仅10条），仍需从文本推断具体编号（如"指导案例24号"），可能需要额外的后处理规则

### 方案二：修改 Ontology，将 `guiding_case_number` 由 required 改为 optional

**策略**：
- 在 `legal_ontology_v2.yaml` 中将 `GuidingCase` 的 `required` 列表移除 `guiding_case_number`
- 在 `prompt_renderer.py` 的 JSON schema 中将 `guiding_case_number` 设为可选

**优点**：
- 消除必填约束与数据实际的矛盾
- 无需对每个案例强制要求不存在的字段

**缺点**：
- 与"指导性案例"节点的语义定义不完全一致（真正指导性案例应该有编号）
- 治标不治本，仍需要方案一中的处理逻辑

### 推荐组合方案

**短期（立即）**：实施方案一（修改 prompt），让 LLM 明确只对 `case_level='01'` 填充。
**中期**：若需要真正填充"指导案例XX号"，增加后处理逻辑：根据 `storage_no` 的年份匹配最高法发布的指导性案例批次表，从外部映射表注入。
**长期**：方案二可作为备选，降低字段约束的紧耦合度。

### 额外发现：`case_level='01'` 的10条数据的后续处理

当前这10条 `case_level='01'` 的 `storage_no` 格式为 `2016-18-2-137-001` 等，实际上这10条是**人民法院案例库**中标记为"指导性案例"层级的记录。如需填充 `guiding_case_number`，需要建立从 `storage_no` 到"指导案例XX号"的映射表，或从案例文本中提取。

---

## 5. 总结

| 维度 | 结论 |
|------|------|
| 问题表现 | `guiding_case_number` 230条全部为空 |
| 根因 | **数据本身不存在该信息** + Prompt措辞模糊 + Ontology必填约束过强 |
| LLM行为 | **正确**：LLM 判断 storage_no 不是"指导案例XX号"格式，合理留空 |
| 建议措施 | 修改 prompt 按 `case_level` 分场景处理（方案一）；长远可放宽 ontology 约束（方案二） |
