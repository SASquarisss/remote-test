# 法律文本解析质量评估指标体系方案

## 1. 概述

本方案定义了一套多维度、可量化的评估指标体系，用于对 LLM 从法律文本中提取的结构化结果进行全面、科学的评分。与现有仅检查空字段的 `evaluate_output()` 函数不同，本体系结合本体论（ontology）约束、原文一致性和业务重要性进行综合评估。

**核心理念**：评估不仅看"字段是否为空"，更要看"提取的质量是否满足法律知识图谱的合规性要求"。

---

## 2. 评估维度定义

| 维度 | 名称 | 含义 | 权重 | 适用场景 |
|------|------|------|------|---------|
| D1 | 结构完整性 | 提取结果的 JSON 结构是否符合本体论 schema，是否有必填字段缺失 | 5% | 通用 |
| D2 | 实体完整性 | 提取的实体是否覆盖了文本中的关键信息，是否有重要实体遗漏 | 25% | LLM 提取 |
| D3 | 属性准确性 | 提取的字段值是否与原文一致，是否存在幻觉或错误值 | 25% | LLM 提取 |
| D4 | 本体论一致性 | 提取结果是否符合 ontology schema 的类型约束、枚举值约束和关系约束 | 20% | 通用 |
| D5 | 引用完整性 | 法条引用的准确性、完整性和上下文对应关系 | 15% | LLM 提取 |
| D6 | 语义连贯性 | 提取的文本字段（如案情摘要、裁判要旨）是否结构清晰、符合法律表达规范 | 10% | LLM 提取 |

**权重说明**：
- 结构完整性权重较低（5%）：因为这是一项基础检查，LLM 几乎不会完全漏掉 JSON 结构。
- 实体完整性和属性准确性各占 25%：这两项是评估提取质量的核心。
- 本体论一致性占 20%：确保提取结果能被 KG 正确吸收。
- 引用完整性占 15%：法条引用是法律文本的关键要素。
- 语义连贯性占 10%：评估文本质量而非仅字段存在性。

---

## 3. 子指标定义

### D1 — 结构完整性（权重 5%）

| 指标代码 | 指标名称 | 评分方法 | 分值 |
|----------|----------|----------|------|
| D1.1 | 顶层键是否存在 | 检查 `guiding_case`, `case_type`, `court_cases`, `legal_subjects`, `legal_provisions`, `case_summary` 等顶层 key 是否存在 | 40 |
| D1.2 | JSON 格式有效性 | 输出是否为合法 JSON（非截断、非 null） | 30 |
| D1.3 | 数组字段类型正确 | `court_cases`, `legal_subjects`, `legal_provisions` 等是否为数组类型 | 30 |

### D2 — 实体完整性（权重 25%）

| 指标代码 | 指标名称 | 评分方法 | 分值 |
|----------|----------|----------|------|
| D2.1 | 当事人提取覆盖率 | 从原始文本中识别出的人物/组织，在 `legal_subjects` 中是否全部覆盖 | 25 |
| D2.2 | 法官提取覆盖率 | 文本中出现的审判人员是否在 `judges` 中体现 | 15 |
| D2.3 | 律师提取覆盖率 | 文本中出现的律师/诉讼代理人是否在 `attorneys` 中体现 | 10 |
| D2.4 | 案号提取覆盖率 | 文本中出现的所有案号是否在 `court_cases` 中体现 | 20 |
| D2.5 | 法条覆盖率 | 文本中引用的法律条文是否在 `legal_provisions` 中体现 | 15 |
| D2.6 | 证据提取率 | 文本中提到的关键定案证据在 `evidence` 中的覆盖 | 5 |
| D2.7 | 案件摘要完整性 | `case_summary` 的 `key_facts`, `disputed_issues`, `conclusion` 三个子字段是否均非空 | 10 |

### D3 — 属性准确性（权重 25%）

| 指标代码 | 指标名称 | 评分方法 | 分值 |
|----------|----------|----------|------|
| D3.1 | 案号格式正确性 | `case_number` 是否符合中国法院案号格式 `(YYYY)XX字XX号` | 15 |
| D3.2 | 日期字段合理性 | `filing_date`, `judgment_date` 等是否为合理日期（不早于 1990，不晚于当前） | 15 |
| D3.3 | 法院名称准确性 | 提取的法院名称是否真实存在、层级映射是否正确 | 15 |
| D3.4 | 案件类型映射准确 | `case_type.category` 是否与原文案由一致（刑事→criminal 等） | 10 |
| D3.5 | 当事人角色准确 | `roles` 中的 `role_code` 是否与原文角色对应 | 10 |
| D3.6 | 法条条号格式 | `article` 是否为纯数字，不存在"第X条"类型的原始文本残留 | 10 |
| D3.7 | 审判层级判断 | `trial_level` 是否与案号/文本中的审级信息一致 | 10 |
| D3.8 | binding_force 正确性 | 根据 case_level 判断 binding_force 的映射是否正确 | 5 |
| D3.9 | 无幻觉检查 | 是否存在原文完全未提及但 LLM 编造的实体或数值 | 10 |

### D4 — 本体论一致性（权重 20%）

| 指标代码 | 指标名称 | 评分方法 | 分值 |
|----------|----------|----------|------|
| D4.1 | 枚举值合规 | 所有枚举字段（`category`, `trial_level`, `binding_force`, `evidence_type`, `role_code`, `result_type` 等）是否使用 ontology 定义的枚举值 | 30 |
| D4.2 | 必填字段非空 | 本体论中标记为 required 的字段是否有值 | 20 |
| D4.3 | 关系完整性 | 实体之间的关联是否正确（如 `legal_provisions` 有 `case_number` 关联到 `court_cases`） | 15 |
| D4.4 | 类型约束 | 每个对象中的字段类型是否与 schema 一致（字符串、数组、布尔等） | 10 |
| D4.5 | 实体 ID 唯一性 | 同一类实体中是否存在重复（如两个相同的案号、两个相同的当事人） | 10 |
| D4.6 | 时序约束 | `filing_date < judgment_date < effective_date` 逻辑是否成立 | 15 |

### D5 — 引用完整性（权重 15%）

| 指标代码 | 指标名称 | 评分方法 | 分值 |
|----------|----------|----------|------|
| D5.1 | 法条上下文合理性 | `content` 字段是否包含与原文一致的法条上下文片段 | 25 |
| D5.2 | 引用位置标注 | `citation_position` 是否准确对应文本中的引用位置 | 20 |
| D5.3 | 引用目的标注 | `citation_purpose` 是否合理（适用依据/说理依据/反驳依据） | 15 |
| D5.4 | 案号关联 | 每个法条是否通过 `case_number` 关联到具体的 `court_cases` | 20 |
| D5.5 | 法条引用覆盖 | 文本中明确标注的法条编号是否全部被提取到 `legal_provisions` | 20 |

### D6 — 语义连贯性（权重 10%）

| 指标代码 | 指标名称 | 评分方法 | 分值 |
|----------|----------|----------|------|
| D6.1 | 摘要结构性 | `case_summary` 的文本是否按"关键事实→争议焦点→裁判结论"的结构组织 | 30 |
| D6.2 | 事实客观性 | `key_facts` 是否仅陈述客观事实，不包含法院观点或 LLM 的推断评论 | 20 |
| D6.3 | 语言规范性 | 提取的文本字段是否存在语法错误、不通顺或明显机器翻译痕迹 | 20 |
| D6.4 | 信息密度 | 文本摘要是否过于冗余（>500字）或过于简略（<20字） | 15 |
| D6.5 | 裁判要旨准确性 | `guiding_points` 是否准确概括了裁判核心规则 | 15 |

---

## 4. 评分计算公式

### 4.1 分项得分

每个维度 D_i 的得分计算：

```
D_i_score = Σ(W_ij × S_ij) / 100 × 100
```

其中：
- W_ij = 子指标 j 在维度 i 中的权重（分值）
- S_ij = 子指标 j 的得分，归一化到 [0, 1]
- D_i_score ∈ [0, 100]

### 4.2 子指标评分方法

每个子指标 S_ij 有三种评分策略：

**A. 二值评分**（适用于 D1.x, D4.1, D4.4 等）：  
`S = 1.0` 满足条件，`S = 0.0` 不满足

**B. 比例评分**（适用于 D2.x 实体覆盖率）：  
`S = matched_entities / total_entities_in_text`，若 total = 0 则 S = 1.0

**C. 层级扣分**（适用于 D3.x, D4.6）：  
`S = 1.0 - (penalty_ratio)`，每发现一个错误扣减 0.2，最多扣到 0

### 4.3 综合总分

```
Total_Score = Σ(α_i × D_i_score)
```

其中 α_i 为维度权重（D1=0.05, D2=0.25, D3=0.25, D4=0.20, D5=0.15, D6=0.10）

最终总分 ∈ [0, 100]

### 4.4 置信度评估

除了总分外，还输出一个置信度标签：

| 总分范围 | 置信度 | 含义 |
|----------|--------|------|
| ≥ 90 | 优 | 可直接入库使用 |
| 70 – 89 | 良 | 轻微问题，可自动修正后入库 |
| 50 – 69 | 中 | 需人工审核修正 |
| < 50 | 差 | 建议重新提取 |

---

## 5. 评分分级示例

```
总分: 84.5 / 100
置信度: 良

分项得分:
  D1 结构完整性:     95 / 100  (权重 5%→4.75)
  D2 实体完整性:     78 / 100  (权重 25%→19.50)
  D3 属性准确性:     85 / 100  (权重 25%→21.25)
  D4 本体论一致性:   92 / 100  (权重 20%→18.40)
  D5 引用完整性:     70 / 100  (权重 15%→10.50)
  D6 语义连贯性:     88 / 100  (权重 10%→8.80)

详细报告:
  ✅ 结构完整，JSON 格式正确
  ✅ 所有枚举值符合 ontology 规范
  ⚠️ 实体完整性: 文本中出现了"某市人民检察院"但未提取到 prosecutors 中
  ⚠️ 引用完整性: 法条"民法典第1042条"的 content 字段缺失原文上下文片段
  ✅ 语义连贯性良好，摘要结构清晰
```

---

## 6. LLM Prompt 设计思路

### 6.1 总体架构

使用一个专用的评估 LLM 调用（而非复用提取 LLM），接收三个输入：

1. **原始法律文本**（raw_text）：用户输入的未经处理的文本
2. **LLM 提取结果**（extracted_json）：解析管线输出的结构化 JSON
3. **本体论 Schema**（ontology_schema）：legal_ontology_v2.yaml 中的实体/属性/约束定义

### 6.2 Prompt 模板结构

```
SYSTEM:
你是一个法律文本解析质量评估专家。你需要对 LLM 从法律文本中提取的结构化结果进行多维度的质量评分。
你的评估必须严格、客观，基于原文证据。

评估维度：
1. 结构完整性（权重5%）：JSON结构是否正确，顶层键是否存在
2. 实体完整性（权重25%）：关键实体是否全部覆盖
3. 属性准确性（权重25%）：字段值是否与原文一致
4. 本体论一致性（权重20%）：是否符合ontology schema约束
5. 引用完整性（权重15%）：法条引用是否准确完整
6. 语义连贯性（权重10%）：摘要文本是否清晰规范

评分规则：
- 每个维度满分100，按子指标加权
- 总分 = 各维度得分按权重求和
- 置信度分级：≥90优, 70-89良, 50-69中, <50差

输出必须是 JSON 格式。

USER INPUT:
===== 原始法律文本 =====
{raw_text}

===== LLM 提取结果 =====
{extracted_json}

===== 本体论 Schema =====
{ontology_schema_summary}

请对以上提取结果进行全面评估，输出 JSON 格式的评估报告。
```

### 6.3 关键引导策略

1. **原文证据引用**：强制 LLM 在每个扣分项中引用原文证据（"文本第X段原文为'...'，但提取字段为'...'"）
2. **枚举值对照**：将 ontology 的枚举值列表直接放入 prompt，让 LLM 逐一比对
3. **本体论约束检查**：将 ontology 中的 constraints（如时序约束、二审必须有一审案号）明确列出
4. **幻觉检测提示**：要求 LLM 标注"原文未提及的实体"作为幻觉标记
5. **阶段性评估**：先评估结构完整性 → 再评估内容，减少LLM认知负载

### 6.4 Model 参数建议

- Model: `deepseek-chat`
- Temperature: 0.1（低温度确保评估一致性）
- Max tokens: 4096
- Response format: `{"type": "json_object"}`

---

## 7. 输出格式 (JSON Schema)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "OntologyEvaluationResult",
  "type": "object",
  "required": [
    "summary",
    "dimension_scores",
    "total_score",
    "confidence",
    "detailed_report",
    "issues",
    "suggestions"
  ],
  "properties": {
    "summary": {
      "type": "object",
      "description": "评估摘要",
      "required": ["case_name", "evaluation_time", "total_score", "confidence"],
      "properties": {
        "case_name": {"type": "string", "description": "案例名称"},
        "evaluation_time": {"type": "string", "description": "评估时间 ISO8601"},
        "total_score": {"type": "number", "minimum": 0, "maximum": 100},
        "confidence": {"type": "string", "enum": ["优", "良", "中", "差"]}
      }
    },
    "dimension_scores": {
      "type": "array",
      "description": "各维度得分",
      "items": {
        "type": "object",
        "required": ["dimension_id", "dimension_name", "weight", "score", "sub_scores"],
        "properties": {
          "dimension_id": {"type": "string", "enum": ["D1", "D2", "D3", "D4", "D5", "D6"]},
          "dimension_name": {"type": "string"},
          "weight": {"type": "number", "minimum": 0, "maximum": 1},
          "score": {"type": "number", "minimum": 0, "maximum": 100},
          "sub_scores": {
            "type": "array",
            "items": {
              "type": "object",
              "required": ["indicator_id", "indicator_name", "score", "reason"],
              "properties": {
                "indicator_id": {"type": "string"},
                "indicator_name": {"type": "string"},
                "score": {"type": "number", "minimum": 0, "maximum": 100},
                "reason": {"type": "string", "description": "评分理由，引用原文证据"}
              }
            }
          }
        }
      }
    },
    "total_score": {"type": "number", "minimum": 0, "maximum": 100},
    "confidence": {"type": "string", "enum": ["优", "良", "中", "差"]},
    "detailed_report": {
      "type": "object",
      "description": "详细文本报告",
      "required": ["strengths", "weaknesses", "hallucination_warnings", "ontology_violations"],
      "properties": {
        "strengths": {
          "type": "array",
          "items": {"type": "string"},
          "description": "做得好的方面列表"
        },
        "weaknesses": {
          "type": "array",
          "items": {"type": "string"},
          "description": "需要改进的方面列表"
        },
        "hallucination_warnings": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "entity_path": {"type": "string"},
              "claimed_value": {"type": "string"},
              "evidence": {"type": "string", "description": "原文中未找到的证据"}
            }
          },
          "description": "幻觉警告——提取结果中存在但原文未提及的内容"
        },
        "ontology_violations": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["constraint", "violation_path", "description"],
            "properties": {
              "constraint": {"type": "string"},
              "violation_path": {"type": "string"},
              "description": {"type": "string"}
            }
          },
          "description": "本体论约束违反列表"
        }
      }
    },
    "issues": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["severity", "category", "field_path", "description", "suggestion"],
        "properties": {
          "severity": {"type": "string", "enum": ["critical", "major", "minor", "info"]},
          "category": {"type": "string", "description": "问题类别"},
          "field_path": {"type": "string", "description": "问题字段的 JSONPath"},
          "description": {"type": "string", "description": "问题描述，含原文对照"},
          "suggestion": {"type": "string", "description": "修复建议"}
        }
      }
    },
    "suggestions": {
      "type": "array",
      "items": {"type": "string"},
      "description": "改进建议汇总"
    }
  }
}
```

### 输出示例

```json
{
  "summary": {
    "case_name": "张三诉李四离婚纠纷案",
    "evaluation_time": "2026-05-12T18:30:00Z",
    "total_score": 84.5,
    "confidence": "良"
  },
  "dimension_scores": [
    {
      "dimension_id": "D1",
      "dimension_name": "结构完整性",
      "weight": 0.05,
      "score": 95.0,
      "sub_scores": [
        {"indicator_id": "D1.1", "indicator_name": "顶层键是否存在", "score": 100, "reason": "所有顶层键均存在"},
        {"indicator_id": "D1.2", "indicator_name": "JSON格式有效性", "score": 100, "reason": "JSON格式正确"},
        {"indicator_id": "D1.3", "indicator_name": "数组字段类型正确", "score": 85, "reason": "evidence 字段为 null 而非空数组"}
      ]
    },
    {
      "dimension_id": "D2",
      "dimension_name": "实体完整性",
      "weight": 0.25,
      "score": 78.0,
      "sub_scores": [
        {"indicator_id": "D2.1", "indicator_name": "当事人提取覆盖率", "score": 100, "reason": "原文中张三、李四均已提取"},
        {"indicator_id": "D2.2", "indicator_name": "法官提取覆盖率", "score": 60, "reason": "原文出现审判员王五、书记员赵六，但 judges 中只有王五"},
        {"indicator_id": "D2.5", "indicator_name": "法条覆盖率", "score": 70, "reason": "原文引用民法典第1042条已提取，但第1079条（感情破裂条款）未提取"}
      ]
    },
    {
      "dimension_id": "D3",
      "dimension_name": "属性准确性",
      "weight": 0.25,
      "score": 85.0,
      "sub_scores": [
        {"indicator_id": "D3.1", "indicator_name": "案号格式正确性", "score": 100, "reason": "案号格式正确"},
        {"indicator_id": "D3.9", "indicator_name": "无幻觉检查", "score": 90, "reason": "未发现明显幻觉，但 evidence[0].submitted_by='王五律师'，原文中王五为审判员，非律师"}
      ]
    },
    {
      "dimension_id": "D4",
      "dimension_name": "本体论一致性",
      "weight": 0.20,
      "score": 92.0,
      "sub_scores": [
        {"indicator_id": "D4.1", "indicator_name": "枚举值合规", "score": 90, "reason": "legal_subjects[1].subject_type='organization'但 org_type 为 'individual'，非枚举值"},
        {"indicator_id": "D4.6", "indicator_name": "时序约束", "score": 100, "reason": "filing_date < judgment_date < effective_date 成立"}
      ]
    },
    {
      "dimension_id": "D5",
      "dimension_name": "引用完整性",
      "weight": 0.15,
      "score": 70.0,
      "sub_scores": [
        {"indicator_id": "D5.1", "indicator_name": "法条上下文合理性", "score": 50, "reason": "legal_provisions[0].content 为空，缺少原文上下文片段"},
        {"indicator_id": "D5.4", "indicator_name": "案号关联", "score": 100, "reason": "所有法条均有 case_number 关联"}
      ]
    },
    {
      "dimension_id": "D6",
      "dimension_name": "语义连贯性",
      "weight": 0.10,
      "score": 88.0,
      "sub_scores": [
        {"indicator_id": "D6.1", "indicator_name": "摘要结构性", "score": 90, "reason": "结构清晰"},
        {"indicator_id": "D6.2", "indicator_name": "事实客观性", "score": 85, "reason": "存在少量推断性语句"}
      ]
    }
  ],
  "total_score": 84.5,
  "confidence": "良",
  "detailed_report": {
    "strengths": [
      "JSON 结构完整，所有顶层键均存在",
      "当事人提取完整，角色映射正确",
      "案号格式正确，日期字段合理",
      "本体论枚举值大部分合规",
      "摘要结构清晰，关键事实陈述客观"
    ],
    "weaknesses": [
      "法官提取不完整——缺少书记员赵六",
      "法条提取不完整——民法典第1079条被遗漏",
      "法条引用上下文缺失——content 字段为空",
      "evidence 字段类型为 null 而非空数组"
    ],
    "hallucination_warnings": [
      {
        "entity_path": "evidence[0].submitted_by",
        "claimed_value": "王五律师",
        "evidence": "原文中王五为审判员，未提及王五担任律师"
      }
    ],
    "ontology_violations": [
      {
        "constraint": "Organization.org_type 枚举值",
        "violation_path": "legal_subjects[1].org_type",
        "description": "org_type='individual' 不在枚举值 [company, government_agency, ngo, law_firm, expert_institution, court, procuratorate] 中"
      }
    ]
  },
  "issues": [
    {
      "severity": "major",
      "category": "实体遗漏",
      "field_path": "judges",
      "description": "原文裁判理由中出现'书记员赵六'但 judges 数组未包含",
      "suggestion": "补充 judges 条目：{\"name\":\"赵六\", \"role\":\"clerk\", \"case_number\":\"(2026)京0108民初12345号\"}"
    },
    {
      "severity": "minor",
      "category": "字段格式",
      "field_path": "evidence",
      "description": "evidence 为 null 而非 []",
      "suggestion": "将 null 替换为空数组[]"
    }
  ],
  "suggestions": [
    "建议在 prompt 中强调法官、书记员、检察官必须全部提取",
    "增加法条 content 字段的提取要求，强制提取原文上下文",
    "建议在 post-processing 中将 null 数组统一转换为空数组"
  ]
}
```

---

## 8. 复用性设计

### 8.1 评估 LLM 提取结果

这是主要使用场景。评估对象 = `extracted_json` (parser.py 的 parse_text 输出)，配合 `raw_text` 和 `ontology_schema_summary`。

### 8.2 评估本体论质量

本方案也可以用于评估 ontology schema 自身的质量：

| 维度 | 本体论评估的映射方式 |
|------|----------------------|
| D1 结构完整性 | 检查 ontology YAML 中各类型的 required/optional 定义是否完整、一致 |
| D2 实体完整性 | 评估 ontology 中的实体类型是否覆盖了法律领域的关键概念 |
| D4 本体论一致性 | 检查约束定义是否自洽（如引用关系是否有循环依赖） |
| D6 语义连贯性 | 检查命名规范、注释清晰度、enum 值命名一致性 |

使用时只需更换输入内容：将 extracted_json 替换为 ontology YAML/JSON，并调整评估 prompt 的描述文本。

### 8.3 评估 Pipeline

```
raw_text ─┐
          ├──→ LLM Evaluation Prompt ──→ DeepSeek API ──→ Evaluation Result JSON
extracted ─┘
ontology ─┘
```

---

## 9. 实现计划

### 9.1 优先级

1. **P0** — 实现 `ontology_evaluate()` 函数（替换/增强 `evaluate_output()`）
2. **P1** — 编写评估专用 prompt 并测试
3. **P2** — 实现输出 JSON 的后端 API 端点 `/api/ontology-evaluate`
4. **P3** — 前端加"本体论评估"按钮，展示评分仪表盘
5. **P4** — 批量评估功能（评估多个历史提取结果）

### 9.2 实现文件

- `backend/evaluator.py`：评估核心逻辑
- `scripts/prompts/ontology_evaluation_prompt_v1.txt`：评估专用 prompt
- `backend/app.py`：新增 `/api/ontology-evaluate` 路由
- `visualization/ontology_eval.html`：前端评估页面（或集成到现有页面）
