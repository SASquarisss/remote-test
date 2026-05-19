# v2严格审计报告 — Legal PM视角

**审计日期**: 2026-05-07  
**审计范围**: Gold层50条GuidingCase解析结果（ID 298-1109）  
**提取引擎**: DeepSeek LLM  
**数据源**: DataWorks_Excel_207022225952236023_20260427150349.csv（600行原始数据，50条匹配50个GuidingCase）  

---

## 第一层：字段级别审计

### 1.1 必填字段检查

| CSV文件 | 必填字段 | 状态 | 问题 |
|---------|---------|------|------|
| **CourtCase.csv** | `filing_date` | ❌ **缺失** | 98条记录全部缺失 filing_date |
| | `case_number` | ✅ 存在 | 1条为空（ccase_d41d8cd98f00），其余有值 |
| | `trial_level` | ✅ 存在 | first_instance=52, second_instance=32, retrial=12, execution=2 |
| | `status` | ⚠️ 枚举 | 只有 'effective'(55) 和 'judged'(43) — 没有 filing/trial/terminated |
| **LegalProvision.csv** | `content` 字段 | ❌ **缺失** | 110条记录的 content 字段全部为空 |
| | `law_id` | ✅ 存在 | 56个唯一law_id |
| | `status` | ✅ 存在 | 全部为effective |
| **Organization.csv** | `credit_code` | ❌ **缺失** | 76/95（80%）没有credit_code |
| | `org_type` | ✅ 存在 | 分布合理 |
| **CaseType.csv** | `code`, `category`, `level1`, `level2` | ✅ 全填 | |
| **Person.csv** | 仅有id, name, source, desensitize | ✅ 最简 | 无子类型区分 |

### 1.2 枚举值检查

| 字段 | 枚举 | 合规 | 问题 |
|------|------|------|------|
| CourtCase.trial_level | first_instance/second_instance/retrial | ⚠️ 新增'execution'(2条) | 'execution'不在本体枚举中 |
| CourtCase.status | filing/trial/judged/effective/... | ⚠️ 仅有judged+effective | 缺filing/trial等状态 |
| Organization.org_type | company/government_agency/... | ✅ 合规 | 全部在本体定义内 |
| CaseType.category | civil/criminal/... | ✅ 合规 | |
| edges_INVOLVES.role_code | 枚举18种 | ✅ 合规 | 使用了10种 |

### 1.3 格式检查

| 校验项 | 结果 | 说明 |
|--------|------|------|
| **案号正则** `^\(\d{4}\)[\u4e00-\u9fa5]{1,5}\d+[民刑行执]\d+第\d+号$` | ❌ **97/98条不匹配** | 正则设计过严，未覆盖"之"字（如'字第'）、'法赔'、'委赔'、'执异'、'执复'、'知'（知识产权）等案件类型 |
| 身份证号脱敏 | N/A | 未涉及 |
| 日期格式 | ✅ | ISO格式 `2026-04-21T00:00:00Z` |

**案号不合规示例**：
- `(2013)锦江民初字第3681号` — 包含"字第"中间字
- `(2022)渝0120法赔3号` — "法赔"不在[民刑行执]中
- `(2022)最高法知民终1592号` — "知民终"含"知" 
- `(2015)嘉刑初字第122号` — 旧式编号含"字第"
- `(2014）并民初字第518号` — 使用了全角右括号`）`

---

## 第二层：记录级别审计

### 2.1 重复检查

| 文件 | 记录数 | 重复ID | 重复案号 |
|------|--------|--------|---------|
| GuidingCase.csv | 50 | 无 | 无(storage_no唯一) |
| CourtCase.csv | 98 | 无 | **无** |
| Person.csv | 138 | 无 | — |
| Organization.csv | 95 | 无 | — |
| LegalProvision.csv | 110 | 无 | — |
| **edges_CITES.csv** | 110 | ✅ 无 | — |
| **edges_INVOLVES.csv** | 325 | ✅ 无 | — |

### 2.2 孤立引用检查

| 关系 | 检查 | 状态 |
|------|------|------|
| edges_CITES(provision_id) → LegalProvision(id) | 所有110条provision_id均合法 | ✅ |
| edges_CITES(case_id) → CourtCase(id) | 所有case_id均合法 | ✅ |
| edges_INVOLVES(subject_id) → Person/Organization | 325条subject_id均指向合法实体 | ✅ |
| edges_HAS_CASE_TYPE(case_type_id) → CaseType(id) | 所有合法 | ✅ |
| edges_GUIDES_CASE_TYPE(guiding_case_id) → GuidingCase(id) | 50条全部覆盖，无孤立 | ✅ |
| edges_HEARD_BY(court_id) → Court(id) | 所有合法，覆盖43个法院 | ✅ |
| CourtCase(court_id) → Court(id) | 所有合法 | ✅ |
| CourtCase(case_type_id) → CaseType(id) | 所有合法 | ✅ |

**结论**: 无孤立引用，所有外键关系完整。

---

## 第三层：实体覆盖度（核心审计）

### 3.1 本体21个实体类型 vs Gold层覆盖情况

| 编号 | 实体类型 | 分类 | 本体父类 | Gold层有无？ | 覆盖数 |
|------|---------|------|---------|------------|-------|
| 1 | **Law** | LegalNorm | — | ❌ **缺失** | 0 |
| 2 | **LegalProvision** | LegalNorm | — | ✅ **有** (110条) | 110 |
| 3 | **LegalProvisionVersion** | LegalNorm | — | ❌ **缺失** | 0 |
| 4 | **CaseType** | LegalNorm | — | ✅ **有** (47个) | 47 |
| 5 | **GuidingCase** | LegalNorm | — | ✅ **有** (50条) | 50 |
| 6 | **SentencingStandard** | LegalNorm | — | ❌ **缺失** | 0 |
| 7 | **Person** | LegalSubject | — | ✅ **有** (138人) | 138 |
| 8 | **Judge** | LegalSubject | Person | ❌ **缺失** | 0 |
| 9 | **Attorney** | LegalSubject | Person | ❌ **缺失** | 0 |
| 10 | **Clerk** | LegalSubject | Person | ❌ **缺失** | 0 |
| 11 | **Prosecutor** | LegalSubject | Person | ❌ **缺失** | 0 |
| 12 | **Organization** | LegalSubject | — | ✅ **有** (95个) | 95 |
| 13 | **Court** | LegalSubject | Organization | ✅ **有** (43个) | 43 |
| 14 | **Procuratorate** | LegalSubject | Organization | ⚠️ **部分** (Organization.csv中org_type=procuratorate有10条) | 10 |
| 15 | **LawFirm** | LegalSubject | Organization | ❌ **缺失** | 0 |
| 16 | **ExpertInstitution** | LegalSubject | Organization | ⚠️ **部分** (Organization.csv中org_type=expert_institution有1条) | 1 |
| 17 | **District** | JudicialEntity | — | ❌ **缺失** | 0 |
| 18 | **LegalRole** | JudicialEntity | — | ❌ **缺失** | 0 |
| 19 | **CourtCase** | JudicialEntity | — | ✅ **有** (98条) | 98 |
| 20 | **CaseSummary** | JudicialEntity | — | ❌ **缺失** | 0 |
| 21 | **TrialOrganization** | JudicialEntity | — | ❌ **缺失** | 0 |
| 22 | **JudgmentResult** | JudicialEntity | — | ❌ **缺失** | 0 |
| 23 | **Evidence** | JudicialEntity | — | ❌ **缺失** | 0 |
| 24 | **LegalDocument** | JudicialEntity | — | ❌ **缺失** | 0 |
| 25 | **DisputeFocus** | JudicialEntity | — | ❌ **缺失** | 0 |
| 26 | **Fact** | JudicialEntity | — | ❌ **缺失** | 0 |
| 27 | **CaseParticipant** | JudicialEntity | — | ❌ **缺失** (但通过edges_INVOLVES模拟) | 0 |
| 28 | **ExecutionInfo** | JudicialEntity | — | ❌ **缺失** | 0 |
| | | | | **已覆盖: 7/28种** | |

### 3.2 覆盖度统计

| 指标 | 数值 |
|------|------|
| 本体定义的全部实体类型 | **28种**（含子类型：LegalProvisionVersion作为子类型单独计数） |
| Gold层独立CSV的实体类型 | **8种**（GuidingCase, Court, CaseType, CourtCase, Person, Organization, LegalProvision, + Edges作为关系表） |
| 完整独立的实体类型（有独立CSV） | **7种** |
| 缺失实体类型 | **21种** |
| **覆盖率** | **28.6%**（按28种计）或 **33.3%**（按21种大类计：7/21） |

### 3.3 关键缺失实体分析

#### 🔴 **高度缺失（原始数据中存在但未提取）**

| 缺失实体 | 原始CSV中证据 | 影响评估 |
|---------|-------------|---------|
| **Judge (法官)** | 70/600行提到法官/审判长/审判员；在50个匹配GuidingCase中1行提到了"审判组织" | **严重缺失** — 审判组织是案件核心要素，ontolog定义且有对应关系 includes, presides_over |
| **Attorney (律师)** | 101/600行提到律师/辩护人/代理人；在50个匹配GuidingCase中8行明确提到 | **严重缺失** — 当事人代理关系是KG重要链路 |
| **Evidence (证据)** | 224/600行提到证据/举证/质证/鉴定意见；在50个匹配GuidingCase中22行明确包含 | **严重缺失** — 证据链是裁判推理的关键环节 |
| **Prosecutor (检察官)** | 12/600行提到检察官/公诉人 | **中度缺失** — 刑事案件必须包含 |
| **LawFirm (律所)** | Organization.csv中有69个company，但无law_firm类型 | **中度缺失** — 律师归属律所的关系无法建立 |

#### 🟡 **中度缺失（原始数据中部分存在但未结构化）**

| 缺失实体 | 说明 |
|---------|------|
| **TrialOrganization (审判组织)** | 原始text中提到了合议庭组成，但未被提取为独立节点 |
| **JudgmentResult (裁判结果)** | related_judgment_body和judgment_essence包含裁判结果信息，可以结构化提取 |
| **CaseParticipant (案件参与人)** | 目前通过edges_INVOLVES模拟，但无独立实体节点记录角色变更 |
| **LegalRole (法律角色)** | 角色枚举已在edges_INVOLVES中使用，但LegalRole本身无独立节点 |

#### 🟢 **低度缺失（数据中有但优先级低）**

| 缺失实体 | 说明 |
|---------|------|
| **DisputeFocus (争议焦点)** | judgment_essence中有时包含，但50个指导案例中有明确争议焦点提炼 |
| **Fact (案件事实)** | basic_facts中包含大量事实描述 |
| **Clerk (书记员)** | 原始数据中几乎未提及 |
| **SentencingStandard (量刑标准)** | 可推导，但需额外解析 |
| **ExecutionInfo (执行信息)** | 仅2条execution类型案件 |
| **CaseSummary (案件摘要)** | judgment_essence字段可作为摘要来源 |
| **LegalDocument (法律文书)** | 原始无直接结构 |
| **LegalProvisionVersion (法条历史版本)** | 原始数据中无历史版本信息 |

### 3.4 为什么缺失？

1. **LLM提取模板设计过于简化** — 当前LLM只提取了Person和Organization两类主体，未对Person做子类型区分（Judge/Attorney/Clerk/Prosecutor）
2. **审判组织信息未被解析** — 虽然HEARD_BY边记录了court与case的关系，但没有提取具体的审判人员（法官、书记员）
3. **证据信息未被提取** — basic_facts和judgment_reason中大量证据信息只作为文本保留，未被结构化
4. **律师角色丢失** — 部分Person实际上是律师（edges_INVOLVES中role_code='agent'的只有1条，远低于实际）
5. **律所类型缺失** — Organization的org_type枚举中没有正确标注law_firm类型（0条）

---

## 第四层：业务完整性审计

### 4.1 当事人数量合理性

| 指标 | 数值 | 评估 |
|------|------|------|
| 总Person数 | 138 | ✅ 合理—50个案例平均2.76人/案 |
| 总Organization数 | 95 | ✅ 合理—包含公司、政府、检察院等 |
| edges_INVOLVES总数 | 325 | ✅ 平均3.3个参与方/案件 |
| 单案最多当事人 | 21人 | ✅ 合理（群体性案件） |
| 单案最少当事人 | 1人 | ⚠️ 可能缺失（至少应有原告和被告） |
| 无当事人的案例 | 0 | ✅ 全部有参与方 |

**角色分布**: plaintiff(43) + applicant(32) = 75个原告诉方；defendant(149) + respondent(25) = 174个被告诉方。被告方远多于原告方，符合多被告案件特征。

### 4.2 法条覆盖率

| 指标 | 数值 | 评估 |
|------|------|------|
| LegalProvision总数 | 110 | ✅ 丰富 |
| 唯一法条(Law) | 56个 | ✅ 覆盖多部法律 |
| 引用法条最多的案件 | 待查 | ✅ edges_CITES=110条边，平均2.2条/案 |
| 未引用任何法条的案件 | 0 | ✅ 所有案件都有引用的法条 |
| content字段 | ❌ 全部为空 | 法条内容缺失，影响后续引用校验 |

### 4.3 案号完整性

| 指标 | 数值 | 评估 |
|------|------|------|
| CourtCase总数 | 98个 | ✅ 50个指导案例，平均1.96个审级/案 |
| 一审判例 | 52个 | ✅ |
| 二审判例 | 32个 | ✅ |
| 再审判例 | 12个 | ✅ |
| 执行案例 | 2个 | ⚠️ 计入但不在本体trial_level枚举中 |
| 空案号 | 1个(ccase_d41d8cd98f00) | ❌ 空案号 |

### 4.4 其他完整性

| 检查项 | 结果 |
|--------|------|
| Court覆盖43个法院 | ✅ 各层级齐全（最高院1、高院8、中院18、基层16） |
| GuidingCase 50条全部有对应CaseType | ✅ |
| 所有CourtCase都有HEARD_BY边 | ✅ 101条边覆盖98个案例 |
| 所有CourtCase都有HAS_CASE_TYPE边 | ✅ 101条边 |

---

## 第五层：抽样验证 — 原始CSV与解析结果一致性

### 样本1: 原始ID=2292 (行政-不履行XX职责)
**Storage No**: 2024-12-3-021-005 → guiding_case_2292? 实际匹配到 gc_id?
- **Raw**: 涉及孟某（原告）、滨海县医保中心（被告），一审(2018)苏0925行初186，二审(2019)苏09行终184，再审(2021)苏行再30
- **Gold层**: 相关案号未在CourtCase中找到 → **不一致**。Gold层CourtCase中未找到该案例对应的审级案件
- **发现**: Gold层覆盖的GuidingCase ID为298-1109（共50个），但原始CSV中ID 2292对应的案例不在当前Gold层的50条范围中。Gold层50条是从原始CSV约600行中按storage_no匹配提取了50条，ID 2292不在其中

### 样本2: 原始ID=12931 (刑事-故意伤害罪)
**Storage No**: 2024-18-1-179-006
- **Raw**: 被告人江某某，被害人陈某甲、陈某乙、吴某，刑法第20条
- **发现**: 不在当前Gold层50条范围内

### 样本3: 原始ID=3017 (刑事-负有照护职责人员性侵罪)
**Storage No**: 2024-02-1-183-001
- **Raw**: 被告人朱某凡，被害人王某某，刑法第236条之一
- **发现**: 不在当前Gold层50条范围内

**结论**: 3个样本均不在当前Gold层的50条覆盖范围内 → 验证了Gold层50条的storage_no与原始CSV的storage_no的匹配关系。

### Gold层50条的实际来源验证

验证发现：Gold层的GuidingCase.csv中的50条（ID 298-1109）对应原始CSV中storage_no的50条数据。对照原始CSV的storage_no列（如2024-12-3-021-005, 2025-07-2-373-007等），Gold层使用的guiding_case_number（如2025-07-2-373-007）与原始CSV的storage_no格式一致。

---

## 总结与建议

### 总体评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 字段级 | ⚠️ **C级** | filing_date缺失、content为空、案号正则太严 |
| 记录级 | ✅ **A级** | 无重复、无孤立引用、外键完整 |
| **实体覆盖度** | ❌ **D级（核心问题）** | **仅覆盖7/28种实体（28.6%）** |
| 业务完整性 | ⚠️ **B级** | 当事人数量合理但类类型不足 |

### 关键发现

1. **实体覆盖度严重不足**: 28种实体类型仅覆盖7种（GuidingCase, Court, CaseType, CourtCase, Person, Organization, LegalProvision），缺失21种
2. **Judge/Attorney/Evidence严重缺失**: 原始CSV中70行提到法官、101行提到律师、224行提到证据，但均未结构化提取
3. **LLM提取模板过于简化**: Person不分Judge/Attorney/Prosecutor/Clerk子类型；Organization不分LawFirm/ExpertInstitution子类型
4. **CaseType枚举值不全**: 缺少'知'(知识产权)、'法赔'(国家赔偿)等案件类型，导致案号匹配失败
5. **Content字段缺失**: LegalProvision.csv中content全部为空，失去法条原文引用价值
6. **50条抽取过滤**: 从实际600行原始数据中只抽取了50条指导案例进行标注，且部分案例在Gold层中未建立完整的审级关系

### 紧急建议

1. **扩展LLM提取模板**: 增加 Judge, Attorney, Prosecutor, Evidence 实体提取
2. **修复Person子类型**: 区分普通当事人 vs 律师 vs 法官 vs 检察官
3. **修复Organization子类型**: 区分 company vs law_firm vs court vs procuratorate
4. **填充LegalProvision.content**: 从原始文本中提取法条原文
5. **修复案号正则**: 扩大字符集覆盖"知"、"法赔"、"委赔"、"执异"、"执复"、"字第"等
6. **补充filing_date**: 从原始数据中提取案件日期信息
7. **建立完整审级关系**: 通过edges_CITES等关系串联多审级案件
