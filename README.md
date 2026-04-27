# 中国司法知识图谱本体

生产级法律知识图谱（Legal Knowledge Graph, LKG）核心定义，面向 2 亿+ 裁判文书、100 万+ 法条、10 万+ 指导性案例的规模化构建与推理。

---

## 数据规模

| 数据类型 | 规模 | 消歧策略 |
|---|---|---|
| 裁判文书 | 2 亿 | 按案件隔离 |
| 法条 | 100 万 | `law_id + article` 全局唯一 |
| 指导性案例 | 10 万 | `guiding_case_number` 全局唯一 |
| 企业当事人 | — | `credit_code` 18 位统一代码跨案件全局关联 |
| 自然人 | — | 跨案件不关联，每案独立节点 |

---

## 技术栈

| 层级 | 选型 | 说明 |
|---|---|---|
| 热层存储 | Neo4j Community | 5,000 万节点以内 |
| 冷层/全量 | NebulaGraph | 超 20 亿节点时迁移 |
| 数据校验 | Pydantic v2 | Schema 即代码 |
| 数据源（MVP） | txt 裁判文书 + CSV 指导性案例 | 后续接入标准接口 |

---

## 本体架构

### 实体层

```
LegalNorm（规范顶层）
  ├── Law                    # 法律
  ├── LegalProvision         # 法条（当前生效版本）
  ├── LegalProvisionVersion  # 法条历史版本
  ├── CaseType               # 案由（对齐最高法案由规定）
  ├── GuidingCase            # 指导性案例
  └── SentencingStandard     # 量刑/赔偿标准

LegalSubject（主体顶层）
  ├── Person                 # 自然人（跨案件不消歧）
  │   ├── Judge
  │   ├── Attorney
  │   ├── Prosecutor
  │   └── Clerk
  └── Organization           # 组织机构（credit_code 全局关联）
      ├── Court
      ├── Procuratorate
      ├── LawFirm
      └── ExpertInstitution

JudicialEntity（司法实体顶层）
  ├── CourtCase              # 案件
  ├── TrialOrganization      # 审判组织
  ├── JudgmentResult         # 裁判结果
  ├── ExecutionInfo          # 执行信息
  ├── Evidence               # 证据
  ├── LegalDocument          # 法律文书
  └── District               # 辖区
```

### 关系层

| 关系 | 方向 | 说明 |
|---|---|---|
| `cites` | Case → Provision | 案件引用法条（含引用位置、目的） |
| `guides` | GuidingCase → CaseType | 指导性案例指导案由适用 |
| `plays_role` | Subject → LegalRole | 主体在案件中担任角色 |
| `represents` | Attorney → Subject | 律师代理（含授权范围、期限） |
| `has_jurisdiction_over` | Court → District | 法院管辖辖区 |
| `based_on` | Execution → Judgment | 执行依据裁判结果 |

### 约束层

- **案号正则**：`(YYYY)XX法院民初第N号` 等官方格式
- **统一社会信用代码**：18 位校验 `[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}`
- **时序约束**：`filing_date < judgment_date < effective_date`
- **脱敏规则**：个保法合规，`id_number`、`phone`、`address` 分级脱敏

---

## 项目结构

```
remote-test/
├── ontology/
│   ├── schemas/
│   │   └── legal_ontology_v2.yaml    # 核心 Schema（实体、关系、约束）
│   └── pydantic_models.py             # Pydantic 模型，运行时校验
├── legal_ontology_example.json        # 示例数据
└── README.md
```

---

## 置信度分层策略

| 层级 | 规则 | 处理流程 |
|---|---|---|
| 高置信度 | 规则明确、字段完整、校验通过 | 自动入库 |
| 中置信度 | 部分模糊、需上下文确认 | 采样审核（1 万样本起） |
| 低置信度 | 冲突严重、关键字段缺失 | 人工审核队列 |

---

## 判决推理输出

基于 KG 统计 + 指导性案例约束力权重：

- **概率区间**：`P(结果|案由, 法条, 历史案例)`
- **约束力分级**：`mandatory`（强制参照）/ `persuasive`（说服参照）/ `reference`（参考）
- **类案推荐**：按案由 + 争议焦点向量相似度排序

---

## 版本

**v2.0**
- 新增 `LegalProvisionVersion`（条文历史版本追溯）
- 新增 `SentencingStandard`（量刑/赔偿标准）
- 新增 `GuidingCase.binding_force`（约束力分级：强制/说服/参考）
- 修正 `Person` 分类（删除 `legal_person`，法人归入 `Organization`）
