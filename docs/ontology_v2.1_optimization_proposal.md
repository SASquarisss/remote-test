# 法律知识图谱本体 v2.1 优化方案

>基于大剑评审意见及回复意见中的遗漏补充，形成可落地的优化方案。

---

## 一、已执行修改（同意部分）

| 修改项 | 文件 | 状态 |
|---------|------|------|
| 移除 `legal_person`，归入 Organization | `ontology/schemas/legal_ontology_v2.yaml` + `pydantic_models.py` | ✅ |
| 补充上诉/再审角色编码：`appellant`/`appellee`/`retrial_applicant`/`retrial_respondent` | schema + pydantic + prompt | ✅ |
| 增加非法人组织：`individual_business`/`partnership`/`sole_proprietorship` | schema + pydantic | ✅ |
| 扩展法律源层级：`judicial_interpretation`/`department_rule`/`normative_document` | schema + pydantic | ✅ |
| 字段级错误恢复（解析脚本） | `parse_guiding_cases_llm.py` | ✅ |
| Prompt 增加角色编码表与容错规则 | `scripts/prompts/guiding_case_extraction.txt` | ✅ |

---

## 二、遗漏补充优化方案

### 2.1 证据实体建模（已存在，但抽取流程未覆盖）

**现实问题**：当前 `Evidence` 节点已定义（`document`/`physical`/`digital`/`testimony`/`expert_opinion`），但 LLM 抽取 Prompt 中未要求提取证据信息，导致该节点在实际 KG 中空置。

**落地方案**

```yaml
# 在 ontology 中增加 Evidence 与案件理由的关联强度
Evidence:
  evidence_type_enum: [document, physical, digital, testimony, expert_opinion, audio_visual, electronic_data]
  # 新增：音视频证据、电子数据
```

**抽取层改动**
- 在 `guiding_case_extraction.txt` 中增加第 7 条规则：
  > 如文本中提及"证据"、"质证"、"认证"、"鉴定意见"，请提取证据名称、类型、提交人、质证结果。
- 新增 `evidence_refs` 输出字段，结构与 `law_refs` 对齐。

**KG 建模层改动**
- `Evidence.submitter_id` 关联 `LegalSubject`，支持自然人/组织提交。
- 增加 `proves_fact` 边关系，将证据与 `Fact`/`DisputeFocus` 关联（已存在，但需要在导入时填充）。

---

### 2.2 非法人组织枚举（已执行）

**现状**：已在 `Organization.org_type_enum` 中增加：
- `individual_business` — 个体工商户（有字号，无法人资格）
- `partnership` — 合伙企业（含普通/有限合伙）
- `sole_proprietorship` — 个人独资企业

**后续注意**
- 这些组织的 `credit_code` 可能为空或采用特殊格式（如个体工商户注册号），建议将 `credit_code` 的 `enforcement: block` 改为 `soft`，或允许填写空值并在 `constraints` 中增加个体工商户注册号校验。

---

### 2.3 次生法律源（已执行）

**现状**：已在 `Law.law_level_enum` 中扩展：
- `judicial_interpretation` — 最高法/最高检司法解释
- `department_rule` — 国务院部门规章
- `normative_document` — 规范性文件

**后续建议**
- 在 `LegalProvision` 中增加 `issuer` 字段（发布机关），以区分同一条文但不同司法解释版本的引用场景。
- 在 `cites` 关系中增加 `citation_type` 属性，区分“直接引用法条”与“引用司法解释”，影响绑定力权重计算。

---

### 2.4 脱敏规则验证机制与审计日志

**现状**：当前仅有正则校验约束（身份证号、手机号替换规则），无审计追溯能力。

**落地方案**

**阶段1：脱敏处理器增强（即刻实施）**
```python
class DesensitizationEngine:
    """分级脱敏引擎"""
    RULES = {
        "id_number": {
            "pattern": r"(\d{6})\d{8}(\d{4})",
            "replacement": r"\1********\2",
            "level": "strict"      # 严格必须脱敏
        },
        "phone": {
            "pattern": r"(\d{3})\d{4}(\d{4})",
            "replacement": r"\1****\2",
            "level": "strict"
        },
        "bank_account": {
            "pattern": r"(\d{4})\d+(\d{4})",
            "replacement": r"\1****\2",
            "level": "strict"
        },
        "name": {
            "pattern": r"([一-龥]{1})([一-龥]{1,2})",
            "replacement": r"\1**或替换为“某某”",
            "level": "contextual"  # 根据上下文决定
        },
        "address": {
            "pattern": r"([一-龥]{2,5}省|[一-龥]{2,5}市)([一-龥]{2,10}区|县)(.*)",
            "replacement": r"\1\2***",
            "level": "contextual"
        }
    }

    def process(self, text: str, case_type: str) -> tuple[str, list[dict]]:
        """返回 (脱敏后文本, 审计日志列表)"""
        audit_logs = []
        for field, rule in self.RULES.items():
            matches = list(re.finditer(rule["pattern"], text))
            for m in matches:
                original = m.group(0)
                masked = re.sub(rule["pattern"], rule["replacement"], original)
                text = text.replace(original, masked, 1)
                audit_logs.append({
                    "field_type": field,
                    "position_start": m.start(),
                    "position_end": m.end(),
                    "strategy": rule["level"],
                    "timestamp": datetime.utcnow().isoformat(),
                })
        return text, audit_logs
```

**阶段2：审计日志实体（本体论增加）**
```yaml
DesensitizationAuditLog:
  is_a: JudicialEntity
  required: [case_id, processor_version, processed_at, sensitivity_score]
  optional: [audit_entries, reviewer_id, approved_at]
  description: "脱敏审计日志"

AuditEntry:
  is_a: JudicialEntity
  required: [log_id, field_type, position_start, position_end, strategy]
  optional: [original_hash, masked_hash]  # 存储哈希而非明文，支持验证
  description: "单条脱敏操作记录"
```

**阶段3：抽样验证流程**
- 每日随机抽取 0.1% 已脱敏文书，交人工检查：
  - 是否存在漏脱敏？
  - 是否过度脱敏导致意义丧失？
  - 是否满足个保法第 51/52 条要求？
- 验证结果写入 `DesensitizationAuditLog`，形成闭环。

**阶段4：安全准入**
- 脱敏处理器放入单独微服务，通过内部 API 调用，避免与数据库直接同层。
- 审计日志存储于独立安全层（与业务数据物理隔离），保留 180 天。

---

## 三、建议优先级与时间线

| 优先级 | 事项 | 预估工时 | 依赖 |
|-------|------|---------|------|
| P0 | 本体论枚举修正（已完成） | 0.5h | 无 |
| P0 | 字段级错误恢复（已完成） | 1h | 无 |
| P1 | 证据抽取规则落地 | 2h | Prompt 调试 |
| P1 | 次生法律源引用类型区分 | 1h | schema 升级 |
| P2 | 脱敏引擎 + 审计日志 | 1d | 安全审评 |
| P2 | 抽样验证流程 | 4h | 人工审核队列 |

---

## 四、风险提示

1. **角色编码增加导致旧数据不一致**：建议在 `CaseParticipant` 增加 `role_code_version` 字段，标记使用的角色编码版本，便于后续清洗。
2. **个体工商户 credit_code 空值**：如果强制校验，可能导致一批数据无法导入。建议先跑 1w 样本验证空值率，再决定是否放宽约束。
3. **脱敏审计日志存储成本**：2亿文书 × 平均 5 条/文书 = 10亿条审计记录，需要独立存储方案（如分表 + TTL）。
