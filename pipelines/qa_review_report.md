# QA Review Report — batch_process.py 审计分析

## 问题清单

---

### 🔴 P0: guiding_case_1089 和 1109 重复写入（严重）

**根因分析：**

`batch_process.py` 的 `overwrite_batch_csv()` 函数（第456-492行）设计为"覆盖式写入"而非"追加"，但它只对**当前批次ID**执行旧行删除（第471-476行），对历史遗留的重复行缺乏去重能力。

具体机制：
1. `load_existing_ids()`（第425-436行）读取 GuidingCase.csv 时，即使某ID出现两次，`set()` 也只会保留一个。所以 **existing_ids 本身是正确的**（无重复）。
2. 但是在 **overwrite 阶段**（第468-478行）：读取现有所有行，对 `name == "GuidingCase.csv"` 逐行判断 `f"guiding_case_{bid}" == row_id`。由于 1089/1109 不在当前 batch_ids 中，两行都会被保留。
3. 第481行 `new_ids` 是本次新产生的行ID集合，第484行 `merged` 中去掉了 `id in new_ids` 的行——但 1089/1109 也不在 new_ids 中。
4. **结果是**：两个副本都被保留了下来，永远不会被清理。

**根本原因追溯：** 
- 代码注释标明 v3.0 是"Post-audit fixes"版本（第6-10行）
- 推测 v1/v2 版本使用了简单的 **append** 模式，在脚本重启/重跑时 1089 和 1109 被追加写入两次
- v3.0 改为 overwrite 模式后，**仅防止了新的重复，未清除已有的重复行**

**影响范围：** GuidingCase.csv 中有 132 行（应有 130 行），edges_CITES.csv 中有 5 条重复边。

---

### 🔴 P0: 55 条 CITES 边指向不存在的 LegalProvision 节点（严重）

**根因分析：**

`overwrite_batch_csv()` 的**批次删除逻辑仅对 GuidingCase.csv 生效**（第471行 `if name == "GuidingCase.csv"`）。对于 LegalProvision.csv、Court.csv、CaseType.csv、edges_CITES.csv、edges_GUIDES_CASE_TYPE.csv，没有任何按 batch_id 删除旧行的机制。

具体问题链条：
1. **Batch 1**（IDs 298-1109）首次运行后，LegalProvision.csv 中有 71 条记录（所有 Batch 1 case 引用的法条）。
2. **Batch 2/3** 运行 `overwrite_batch_csv("LegalProvision.csv", ...)` 时（第743行）：
   - 读取 LegalProvision.csv 中所有现有行
   - **跳过**批次删除检查（因为不匹配 GuidingCase.csv）
   - `new_ids` = 当前批次新产生的 provision_id 集合
   - `merged = [r for r in existing if r['id'] not in new_ids] + new_data`
3. **关键问题**：如果 Batch 3 中某些 case 引用了**与 Batch 1 完全相同的法条**（同一部法律的同一条），`md5_id()` 生成相同的 provision_id。此时 Batch 1 的旧行会被替换（因为 id 相同），但内容可能不同（source/generated from 不同上下文）。
4. 更严重的是：如果 Batch 3 **没有引用某些 Batch 1 的法条**，那这些法条对应的 provision_id **不会出现在 new_ids 中**，所以它们本应被保留——但实际上它们丢失了。

**实际数据验证：**
- LegalProvision.csv 有 78 条记录（仅 Batch 2+3 的，Batch 1 的 55 条完全丢失）
- edges_CITES.csv 中 55 条边的 provision_id 在 LegalProvision.csv 中找不到
- 所有 55 条孤儿边都来自 Batch 1 的 case（IDs < 1300）

**根本原因：** `overwrite_batch_csv()` 的通用设计有缺陷——它假设所有数据文件都可以通过"id 去重"来合并，但 LegalProvision 等节点表的 id 生成策略是 content-hash 而非 batch-scoped，导致跨批次的数据没有正确的隔离机制。

---

### 🟡 P1: TRIAL_LEVEL_MAP 字典完整性不足（中等）

**问题：**
审计报告指出缺少 `\\N`、执行监督、委赔、执行异议、执行复议 这些值。当前字典（第62-74行）：

```python
TRIAL_LEVEL_MAP = {
    "一审": "first_instance",
    "二审": "second_instance",
    "再审": "retrial",
    "执行": "",
    "国家赔偿": "",
    "其他": "",
    "一审程序": "first_instance",
    "二审程序": "second_instance",
    "再审程序": "retrial",
    "重审": "retrial",
    "死刑复核": "",
}
```

子串回退逻辑（第303-305行）能覆盖部分缺失值：
- `"执行监督"` — 因 `"执行" in "执行监督"` → 匹配到 `"执行": ""`
- `"执行异议"` — 同样匹配 `"执行": ""`
- `"执行复议"` — 同样匹配 `"执行": ""`
- `"委赔"` — **不能匹配任何键**，落入 audit log
- `"\\\\N"` — **不能匹配**（strip 后是 `\\N`），落入 audit log

**实际运行结果验证：**
```
map_trial_level("执行监督") -> ""    # 通过子串回退
map_trial_level("委赔")     -> ""    # 通过 audit log fallback（返回 ""）
map_trial_level("\\N")      -> ""    # 通过空值检查（line 296-298 的 strip+空判断）
```

**影响评估**：功能上影响较小（子串回退 + audit log + 空值检查提供了三重保障），但字典缺失条目会导致 audit log 报警，影响运维体验。

---

### 🟡 P1: `\\u3000` 全角空格处理问题（中等）

**问题（第607行）：**
```python
essence = essence.replace("\\u3000", " ").replace("u3000", " ")
```

这段代码处理了两种字符串形式：
1. `"\\u3000"`（Python 源代码中的字面量）→ 匹配 6 字符 `\u3000`
2. `"u3000"` → 匹配 4 字符 `u3000`

**但是缺失了对实际 Unicode 全角空格字符 U+3000 的处理。** 当 CSV 源文件中实际含有 U+3000 全角空格字符时（在 repr 中显示为 `\u3000`，但它是单个字符），上述两个 replace 都无法命中。

**实际数据验证：** GuidingCase.csv 第61行（guiding_case_1593 的 guiding_points 字段）含有 `u3000u3000` 子串——这是两个连续出现的 `u3000`，看起来是原始数据中的标记。`essence.replace("u3000", " ")` 会处理到这种字符串模式。

**影响评估**：对于绝大多数从标准 CSV 读取的数据，`\u3000` 在 CSV 中会被转义为 6 字符字面量，当前代码可以处理。但如果数据源包含原生 U+3000 字符（如从某些数据库导出），就会漏掉。

---

## 修改建议

### 修复1：overwrite_batch_csv 增加全局去重（P0）

**文件：** `pipelines/batch_process.py`
**行号范围：** 第456-492行（`overwrite_batch_csv` 函数）

**修改方案：** 在 merge 之前对 existing_rows 按 id 去重，确保即使历史遗留了重复行也会被清理。

```python
def overwrite_batch_csv(name: str, data: List[Dict], batch_ids: set):
    # ... [existing loading code] ...
    
    # ★ FIX: 对 existing_rows 按 id 去重，保留最后一个出现的行
    seen_ids = set()
    deduped_rows = []
    for row in reversed(existing_rows):  # reversed = keep first occurrence
        rid = row.get("id", "")
        if rid and rid not in seen_ids:
            seen_ids.add(rid)
            deduped_rows.append(row)
    existing_rows = list(reversed(deduped_rows))  # restore original order
    
    # ... [rest of the function] ...
```

**或更简单的方案：** 在写文件前对所有 merged 行按 id 去重：

在第484行后添加：
```python
    # ★ FIX: 全局去重（清理历史遗留重复行），保留最后出现的版本
    seen = set()
    merged_deduped = []
    for row in reversed(merged):
        rid = row.get("id", "")
        if rid and rid not in seen:
            seen.add(rid)
            merged_deduped.append(row)
    merged = list(reversed(merged_deduped))
```

### 修复2：LegalProvision/edges 跨批次一致性保护（P0）

**文件：** `pipelines/batch_process.py`
**行号范围：** 第456-492行（`overwrite_batch_csv` 函数）

**方案A（推荐）：** 为所有表增加 batch_id 感知的删除逻辑。但 LegalProvision 的 id 不是 batch-scoped，所以需要用不同的策略。

**方案B（更优）：** 将 overwrite_batch_csv 改为 **只增不删的全量合并模式**——读取现有所有行，只基于 `id` 去重合并，不按 batch_id 删除任何行。

修改第471-476行，移除 GuidingCase only 的限制，改为对**所有表**按 id 去重：

```python
    # 移除或修改批次删除逻辑
    # if name == "GuidingCase.csv":  # 删除这层特殊判断
    # 改为：所有表统一通过 id 去重
    # 第471-476行保留仅用于 GuidingCase 的批次删除，但 LegalProvision 等表
    # 需要全量保留历史数据
```

**方案C（最终推荐）：** 创建独立的 `merge_csv_with_history()` 函数，对所有节点表（含 LegalProvision）使用**全量保留 + id 去重**策略，不再按 batch 删除：

```python
def merge_csv_with_history(name: str, new_data: List[Dict]):
    """合并写入CSV，保留所有历史行，仅按id去重（无批次删除）。"""
    if not new_data:
        return
    path = GOLD_DIR / name
    existing = {}
    if path.exists() and path.stat().st_size > 0:
        with open(path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing[row["id"]] = row
    for row in new_data:
        existing[row["id"]] = row  # 新数据覆盖旧数据
    merged = list(existing.values())
    keys = list(new_data[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(merged)
```

然后在第740-745行区分调用：
```python
overwrite_batch_csv("GuidingCase.csv", guiding_cases, batch_id_set)  # GuidingCase 用批次删除
merge_csv_with_history("LegalProvision.csv", list(provisions.values()))  # 其他节点表用全量合并
merge_csv_with_history("Court.csv", courts_deduped)
merge_csv_with_history("CaseType.csv", list(case_types.values()))
merge_csv_with_history("edges_CITES.csv", edges_cites)  # 边表也全量合并
merge_csv_with_history("edges_GUIDES_CASE_TYPE.csv", edges_guides)
```

### 修复3：TRIAL_LEVEL_MAP 字典补全（P1）

**文件：** `pipelines/batch_process.py`
**行号范围：** 第62-74行

在 `"死刑复核": ""` 后面添加：

```python
    "\\\\N": "",
    "执行监督": "",
    "委赔": "",
    "执行异议": "",
    "执行复议": "",
```

### 修复4：全角空格处理（P1）

**文件：** `pipelines/batch_process.py`
**行号范围：** 第607行

```python
# 修改前：
essence = essence.replace("\\\\u3000", " ").replace("u3000", " ")

# 修改后：增加对实际 U+3000 字符的处理
essence = essence.replace("\\\\u3000", " ").replace("u3000", " ")
essence = essence.replace("\u3000", " ")  # 实际 Unicde 全角空格
```

### 修复5：edges_CITES 去重（P0 连带）

**文件：** `pipelines/batch_process.py`
**行号范围：** 第672-677行和第702-707行（CITES 边的生成）

当前代码在生成 edges_cites 时没有对 `(case_id, provision_id)` 组合去重，如果同一个 provisioning 被 `parse_related_law()` 和 `regex_extract_legal_provisions()` 同时解析到，就会产生重复边。虽然当前数据中不存在这种情况（edges_CITES.csv 的 5 条重复来自同一数据被写两次），但应增加防御性去重：

在生成 edges_cites 后（约第728行前）增加：
```python
    # 去重 CITES 边（同名 defense）
    seen_edges = set()
    edges_cites_deduped = []
    for edge in edges_cites:
        key = (edge["case_id"], edge["provision_id"])
        if key not in seen_edges:
            seen_edges.add(key)
            edges_cites_deduped.append(edge)
    edges_cites = edges_cites_deduped
```

---

## 总结

| 严重等级 | 问题 | 建议修复优先级 |
|---------|------|------------|
| 🔴 P0 | 1089/1109 重复写入（GuidingCase + CITES 边） | 立即修复 |
| 🔴 P0 | 55 条 CITES 边指向不存在的 LegalProvision 节点 | 立即修复 |
| 🟡 P1 | TRIAL_LEVEL_MAP 字典缺失几个值 | 尽快修复 |
| 🟡 P1 | U+3000 全角空格处理遗漏 | 尽快修复 |
| 🔵 P2 | edges_CITES 缺少 (case_id, provision_id) 层级去重 | 防御性修复 |

**数据修复（自动执行脚本后附加）：**
1. 修复代码后，需要手动清除 GuidingCase.csv 中 1089 和 1109 的重复行
2. 需要重新运行 Batch 1-3 以重建 LegalProvision.csv （或手动从 edges_CITES 反推缺失的 provision 行）
