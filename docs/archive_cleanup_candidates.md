# 根目录与 data_lake 清理建议

本文档只做“清理建议”，不直接代表可以无风险删除。

判断标准：

- `保留`：当前运行链明确依赖
- `疑似废弃`：名称、用途和引用关系都显示为历史实验或中间产物
- `谨慎删除`：大概率是历史文件，但当前代码仍可能把它们当回退候选读取

## 根目录

### 本轮已移出根目录

以下文件已从根目录迁走，避免继续把具体逻辑堆在仓库顶层：

- `scripts/admin_batches/`
  - `run_admin_extraction.py`
  - `run_admin_part1.py`
  - `run_admin_part2.py`
  - `check_admin_batch1.py`
- `scripts/visualization/`
  - `generate_admin_vis.py`
- `scripts/verification/`
  - `verify_fixes.py`
- `scripts/archive/`
  - `temp_fewshot_v2.py`
  - `audit_raw.py`
  - `audit_legal.py`
  - `audit_batch3.py`
  - `audit_report_batch3.py`
  - `server.py`
- `visualization/`
  - `ontology_viz.html`
- `visualization/sandbox/`
  - `test_vis.html`
- `docs/archive/`
  - `fixes_v3_audit_report.md`
  - `audit_v2_report.md`
  - `audit_report_legal_pm.md`

### 根目录建议保留

- `README.md`
- `Makefile`
- `config.yaml`
- `requirements.txt`
- `docker-compose.yml`

### 根目录疑似废弃 / 待确认

#### 1. `remote-test/remote-test/`

- 现状：内部只有极少量 `ontology/generators/*` 和 `scripts/generate_prompt.py`
- 判断：高度像历史拷贝残留，不像当前主链的一部分
- 建议：优先人工确认是否还有外部脚本引用；若无，可整目录删除

#### 2. `legal_ontology_example.json`

- 现状：像早期示例文件，不在当前 Flask / prompt / extractor 主链中
- 判断：大概率是静态示例，不是运行依赖
- 建议：如果近期没人手工查看，可移到 `docs/archive/` 或删除

### 根目录并行原型目录

以下目录不是当前主运行入口，但也不建议现在直接删：

- `api/`
- `webui/`
- `pipelines/`

原因：

- 它们更像并行原型或旧路线，不属于当前 `backend/app.py + visualization/ontology_v2.2.html` 主链
- 但仓内仍有一定结构，可能还承载历史思路或备用实现

建议：

- 先保留
- 若要删，先单独做一次“目录级依赖审查”

## data_lake

## 明确保留

这些是当前活跃层或直接运行依赖：

- `manual_parsed.jsonl`
- `extracted_candidate_manual_save_v1.jsonl`
- `extracted_candidate_structured_v1.jsonl`
- `gold/`

说明：

- `manual_parsed.jsonl` 是网页保存到 `manual` 层的目标文件
- `extracted_candidate_manual_save_v1.jsonl` 是网页保存到 `extracted_candidate` 的目标文件
- `extracted_candidate_structured_v1.jsonl` 是当前结构化 few-shot 候选池

## 基本可视为实验产物，可优先考虑删除

这些文件已被当前分层规则排除在 few-shot 候选池之外：

- `fewshot_cmp_administrative_v3.jsonl`
- `fewshot_cmp_administrative_v4.jsonl`
- `fewshot_cmp_administrative_v4fs.jsonl`
- `fewshot_cmp_civil_v3.jsonl`
- `fewshot_cmp_civil_v4.jsonl`
- `fewshot_cmp_civil_v4fs.jsonl`
- `fewshot_cmp_criminal_v3.jsonl`
- `fewshot_cmp_criminal_v4.jsonl`
- `fewshot_cmp_criminal_v4fs.jsonl`
- `compare3_v3.jsonl`
- `compare3_v4.jsonl`
- `compare3_v4+fewshot.jsonl`
- `compare_test_v3.jsonl`
- `compare_test_v4.jsonl`
- `compare3_report.md`
- `compare_report.md`

判断依据：

- `scripts/data_lake_layers.py` 明确把 `fewshot_cmp_*` 和 `compare*` 归为实验层
- 当前 prompt 选样不会使用它们

## 明显异常，可优先删除

- `extracted_v3_DataWorks_44.jsonl`

判断依据：

- 当前是 0 字节空文件
- 看起来是失败或中断后遗留产物

## 高概率历史中间件，但删除前要先确认

这一组文件大多是历史批次、拆分文件、重试文件、合并文件或旧版候选结果：

- `extracted_guiding_cases.jsonl`
- `extracted_test_v3_1.jsonl`
- `extracted_v2.2_admin_all.jsonl`
- `extracted_v2.2_admin_batch1_first10.jsonl`
- `extracted_v2.2_admin_batch1_remaining.jsonl`
- `extracted_v2.2_admin_full.jsonl`
- `extracted_v2.2_admin_full_part1.jsonl`
- `extracted_v2.2_admin_full_part2.jsonl`
- `extracted_v2.2_admin_remaining.jsonl`
- `extracted_v2.2_fewshots.jsonl`
- `extracted_v3_10_new_v2.jsonl`
- `extracted_v3_18_complete.jsonl`
- `extracted_v3_18_merged.jsonl`
- `extracted_v3_50.jsonl`
- `extracted_v3_7906_only.jsonl`
- `extracted_v3_all_merged.jsonl`
- `extracted_v3_batch2.jsonl`
- `extracted_v3_batch3.jsonl`
- `extracted_v3_dw_batch1.jsonl`
- `extracted_v3_dw_batch2.jsonl`
- `extracted_v3_dw_retry_1538.jsonl`
- `extracted_v3_dw_retry_4089.jsonl`
- `extracted_v3_dw_retry_5973.jsonl`
- `extracted_v3_dw_retry_bad.jsonl`
- `extracted_v3_dw_retry_bad2.jsonl`
- `extracted_v3_fix_verify.jsonl`
- `extracted_v3_full_batch1.jsonl`
- `extracted_v3_missing.jsonl`
- `extracted_v4_civil_batch1.jsonl`
- `extracted_v4_civil_batch2.jsonl`
- `extracted_v4_civil_batch3.jsonl`
- `extracted_v4_civil_verify.jsonl`
- `extracted_v5_714_as_fewshot.jsonl`
- `extracted_v5_best_shots.jsonl`
- `extracted_v5_civil_batch0.jsonl`
- `extracted_v5_civil_full.jsonl`
- `extracted_v5_civil_test.jsonl`

### 为什么这批不能直接删

因为当前 `scripts/generate_prompt.py` 的 few-shot 候选来源仍是：

1. `extracted_candidate_*`
2. `extracted_*`

也就是说，只要文件名仍是 `extracted_*`，它就可能被当作回退候选扫描。

### 更稳妥的清理顺序

1. 先确认后续是否只保留 `extracted_candidate_*` 作为 few-shot 候选
2. 如果确认，是的话，把 `scripts/generate_prompt.py` 改成默认只扫描 `extracted_candidate_*`
3. 再删除这批历史 `extracted_*`

### 其中最像“中间产物”的子集

如果必须先从这批里挑最像废弃物的，优先考虑：

- `extracted_v2.2_admin_batch1_first10.jsonl`
- `extracted_v2.2_admin_batch1_remaining.jsonl`
- `extracted_v2.2_admin_full_part1.jsonl`
- `extracted_v2.2_admin_full_part2.jsonl`
- `extracted_v3_18_complete.jsonl`
- `extracted_v3_18_merged.jsonl`
- `extracted_v3_all_merged.jsonl`
- `extracted_v3_dw_retry_1538.jsonl`
- `extracted_v3_dw_retry_4089.jsonl`
- `extracted_v3_dw_retry_5973.jsonl`
- `extracted_v3_dw_retry_bad.jsonl`
- `extracted_v3_dw_retry_bad2.jsonl`
- `extracted_v3_fix_verify.jsonl`
- `extracted_v4_civil_verify.jsonl`
- `extracted_v5_civil_test.jsonl`
- `extracted_v5_best_shots.jsonl`
- `extracted_v5_714_as_fewshot.jsonl`

这些名字本身就带有明显的中间态特征：

- `part`
- `batch`
- `retry`
- `verify`
- `merged`
- `complete`
- `test`
- `fewshot`

## 建议结论

### 可以先删的一组

- 所有 `fewshot_cmp_*`
- 所有 `compare*`
- `extracted_v3_DataWorks_44.jsonl`

### 先别删的一组

- `manual_parsed.jsonl`
- `extracted_candidate_manual_save_v1.jsonl`
- `extracted_candidate_structured_v1.jsonl`
- `gold/`

### 删除前先改代码的一组

- 大部分 `extracted_*`

因为当前 few-shot 逻辑仍会扫描它们，直接删除会改变 prompt 选样行为。
