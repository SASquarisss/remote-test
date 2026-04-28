# 指导性案例解析脚本

## 文件说明

| 文件 | 说明 |
|------|------|
| `evaluate_regex.py` | 正则提取效果评估，输出覆盖率和按案由分布 |
| `parse_guiding_cases_llm.py` | LLM解析主脚本，支持断点续传、并发、批量保存 |
| `prompts/guiding_case_extraction.txt` | LLM解析提示词模板 |

## 使用步骤

### 1. 评估正则效果（已完成，仅供参考）

```bash
python scripts/evaluate_regex.py \
    --input data/raw/DataWorks_Excel_*.csv
```

**7u6b63则评估结论**：覆盖率约45%，精度严重不足。主要问题：
- 案由多样导致称谓体系混乱
- 大量民事案件无明确角色标签（"某某与某某"开头）
- 正则误提取正文内容为当事人名

### 2. LLM解析

设置API环境变量：

```bash
export OPENAI_API_KEY="your-kimi-api-key"
export OPENAI_BASE_URL="https://api.moonshot.cn/v1"
```

先小批量测试（100条）：

```bash
python scripts/parse_guiding_cases_llm.py \
    --input data/raw/DataWorks_Excel_*.csv \
    --output data/processed/guiding_cases_parsed.jsonl \
    --max-workers 3 \
    --limit 100
```

评估效果后全量运行：

```bash
python scripts/parse_guiding_cases_llm.py \
    --input data/raw/DataWorks_Excel_*.csv \
    --output data/processed/guiding_cases_parsed.jsonl \
    --max-workers 5
```

## 输出格式

JSON Lines，每行一个对象：

```json
{
  "id": "2292",
  "case_type": "行政-不履行XX职责",
  "parties": [
    {"name": "孟某", "role": "原告", "type": "自然人"},
    {"name": "滨海县医疗保险基金管理中心", "role": "被告", "type": "机关"}
  ],
  "case_numbers": ["(2018)苏0925行则186号"],
  "courts": ["江苏省建湖县人民法院"],
  "law_refs": [
    {"statute": "社会保险法", "article": "30", "paragraph": "1"}
  ],
  "case_summary": "孟某因交通事故受伤申请医保补偿被拒...",
  "_raw": { "basic_facts": "...", "judgment_reason": "..." }
}
```

## 参数说明

- `--input`: 输入CSV路径，支持通配符
- `--output`: 输出JSONL路径
- `--max-workers`: 并发线程数（建议3-5，避免触发频率限制）
- `--limit`: 限制处理条数（0=全部）
- `--batch-size`: 每多少条保存一次（默认50）
- `--model`: LLM模型名（默认kimi-k2-6）
