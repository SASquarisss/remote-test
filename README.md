# 法律知识图谱本体（Legal Knowledge Graph Ontology）

生产级司法领域本体定义，支撑类案预判、判决推理与增量知识图谱构建。

## 文件说明

| 文件 | 说明 |
|---|---|
| `ontology/schemas/legal_ontology_v2.yaml` | 核心本体 Schema（实体、关系、约束） |
| `ontology/pydantic_models.py` | Pydantic v2 数据模型，用于运行时校验 |
| `legal_ontology_example.json` | 示例数据（民法典、案由、法院、当事人等） |

## 核心设计

- **规范层**：Law / LegalProvision / LegalProvisionVersion / CaseType / GuidingCase / SentencingStandard
- **主体层**：Person（自然人，跨案件不消歧）、Organization（企业按 `credit_code` 全局关联）
- **案件层**：CourtCase / TrialOrganization / JudgmentResult / ExecutionInfo / Evidence
- **关系层**：cites / plays_role / represents / guides 等 20+ 条关系
- **约束层**：案号正则、统一社会信用代码 18 位校验、时序约束、脱敏规则

## 版本

v2.0 — 新增条文历史版本、量刑标准、指导性案例约束力分级。
