#!/usr/bin/env python3
"""
Final comprehensive audit report output for Batch 3.
"""
print("""
================================================================================
              第三批（Batch 3）数据校验审计报告
                ID Range: 1300-2208 | 50条新增
              审计时间: 2026-05-07 | 审计人: legal_pm
================================================================================

一、数据概览
────────────────────────────────────────────────────────────────────────────────
Gold层当前累计数据：
  - GuidingCase.csv: 132 行（累积 82 + 50，实际含2条重复 → 130条唯一）
  - Court.csv:          97 行
  - CaseType.csv:      133 行
  - LegalProvision.csv: 78 行
  - edges_CITES.csv:   140 行
  - edges_GUIDES_CASE_TYPE.csv: 82 行

Batch 3在GuidingCase中对应 58 行（含重复，唯一ID 56个）。

二、字段填充率 (Batch 3, 58条记录)
────────────────────────────────────────────────────────────────────────────────
字段                        填充率
─────────────────────────────────────────────────────
id                          100.0%  (58/58)
guiding_case_number         100.0%  (58/58)
name                        100.0%  (58/58)
issuing_court_id            100.0%  (58/58)
publication_date            100.0%  (58/58)
guiding_points              100.0%  (58/58)
binding_force               100.0%  (58/58)
source_url                  100.0%  (58/58)
tags                        100.0%  (58/58)
trial_procedure             100.0%  (58/58)
trial_level                  75.9%  (44/58) ← 14条为空（含意置空）
source                      100.0%  (58/58)
desensitize                 100.0%  (58/58)

三、CaseType.category 枚举值校验
────────────────────────────────────────────────────────────────────────────────
本体定义：civil, criminal, administrative, ip, execution, state_compensation
Batch 3涉及的CaseType: 50条

✅ 所有50条category枚举值全部有效
   分布：civil=16, criminal=18, administrative=6, execution=6, state_compensation=4

四、trial_level 映射校验
────────────────────────────────────────────────────────────────────────────────
映射规则：
  first_instance（一审） → 13条
  second_instance（二审） → 24条
  retrial（再审）          →  7条
  置空（非审级枚举）      → 14条
    - 执行:         4条
    - 国家赔偿:     1条
    - 委赔:         1条
    - 其他:         2条
    - 执行复议:     1条
    - 执行异议:     1条
    - 执行监督:     2条
    - 死刑复核:     1条
    - \\N (CSV null): 1条

⚠️  审计发现：以下5个trial_procedure值不在 TRIAL_LEVEL_MAP 字典中：
    - '\\N'       → CSV空值标记，应映射为""
    - '执行监督'  → 执行子类，应映射为""（已确认规则）
    - '委赔'      → 国家赔偿子类，应映射为""（已确认规则）
    - '执行异议'  → 执行子类，应映射为""（已确认规则）
    - '执行复议'  → 执行子类，应映射为""（已确认规则）

    这些值在batch_process.py中通过子串匹配回退逻辑（substring fallback）
    被正确处理为""，但由于不是精确匹配，会被审计日志标记。

    建议：将 '执行监督', '委赔', '执行异议', '执行复议', '\\N' 加入
    TRIAL_LEVEL_MAP 字典以提高精确匹配覆盖率和可维护性。

五、tags 清洗质量
────────────────────────────────────────────────────────────────────────────────
✅ 全部58条tags已正确清洗，无前导/尾随冒号、引号或多余空白。

六、LegalProvision 提取质量
────────────────────────────────────────────────────────────────────────────────
Batch 3产生 CITES 边：62条
Batch 3命中 LegalProvision：62条（均无content内容——占位符模式）
平均每案引用法条数：62/58 ≈ 1.1条

Batch 3内部的CITES边引用完整性：✅ 全部62条provision_id均有对应LegalProvision节点
（跨批次孤儿边均来自Batch 1/2的旧数据，非本批问题）

七、重复数据检测
────────────────────────────────────────────────────────────────────────────────
❌ 发现2条重复记录：
  1. guiding_case_1089 × 2 → ID 1089（属于Batch 2范围，非本批新增）
     重复导致 edges_CITES 中 provision_62b80ad03769 也被重复写入

  2. guiding_case_1109 × 2 → ID 1109（属于Batch 2范围，非本批新增）
     重复导致 edges_CITES 中4条边被重复写入（共8条，正常应为4条）

  原因分析：batch_process.py的overwrite_batch_csv()在Batch 3执行时，
  对GuidingCase.csv执行了"先移除旧批ID再写新数据"的覆盖逻辑，但
  1089和1109两ID同时在Batch 2（原始CSV中）和edges_CITES中均有引用，
  导致Batch 3追加时被重复写入。

  建议：
    - 在overwrite_batch_csv()中增加更严格的防重复写入逻辑
    - 对已存在的ID执行UPDATE而非INSERT
    - 或通过主键唯一性约束在写入前检查

八、抽样一致性验证（5条）
────────────────────────────────────────────────────────────────────────────────
✅ guiding_case_1300 (抚养纠纷)     — 全部通过
✅ guiding_case_1306 (强制猥亵罪)    — 全部通过
⚠️  guiding_case_1351 (重大责任事故罪) — guiding_points轻微格式差异
   （HTML <br/>后的全角空格\\u3000处理差异，语义一致）
✅ guiding_case_1360 (污染环境罪)    — 全部通过
✅ guiding_case_1366 (著作权合同纠纷) — 全部通过

九、referential integrity 引用完整性
────────────────────────────────────────────────────────────────────────────────
- GUIDES_CASE_TYPE边引用情况：
  ✅ 所有guiding_case_id存在于GuidingCase.csv
  ✅ 所有case_type_id存在于CaseType.csv

- CITES边引用情况：
  ✅ 所有case_id存在于GuidingCase.csv（含重复行）
  ✅ Batch 3范围内所有provision_id存在于LegalProvision.csv
  ⚠️  全库范围有55条孤儿CITES边（provision_id无对应的LegalProvision节点）
      → 这些来自Batch 1/2的遗留问题，需要在LegalProvision.csv中补充

十、总体评价与建议
────────────────────────────────────────────────────────────────────────────────
✅ 总体质量良好，核心数据完整，枚举值正确。

优先修复（高优先级）：
  1. 修复 guiding_case_1089 和 guiding_case_1109 的重复记录
  2. 补充55条孤儿LegalProvision节点（跨批次问题）

建议改进（中优先级）：
  3. 将 '\\N', '执行监督', '委赔', '执行异议', '执行复议' 加入TRIAL_LEVEL_MAP
  4. 改进 HTML实体处理，处理全角空格 \\u3000 的Python字符串转义问题
  5. overwrite_batch_csv() 增加UPSERT语义防止重复写入

================================================================================
""")
