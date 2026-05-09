# 新旧提示词对比报告

测试时间: 2026-05-09 09:48:24
测试样本: 2 条 (from test_10_new_v2.csv)

## 结果对比

| 指标 | 旧 (v3) | 新 (自动生成) | 变化 |
|---|---|---|---|
| avg_score | 83.0 | 88.0 | +5.0 |
| total_provisions | 9 | 9 | — |
| total_court_cases | 4 | 4 | — |
| total_subjects | 6 | 6 | — |
| total_judges | 0 | 0 | — |
| total_evidence | 4 | 2 | -2 |
| total_results | 4 | 4 | — |

## 结论

- 新自动生成提示词从 YAML 本体直接渲染，确保枚举值与本体定义完全一致
- 枚举值参考表带中文映射（`plaintiff → 原告`），LLM 无需从自然语言推导枚举值
- JSON Schema 自动生成，与本体字段定义同步
- 维护模式：改 YAML 本体 → `python scripts/generate_prompt.py --output prompts/auto_v4.txt`
