# v5 Ontology Gap Analysis Report

## 第一部分：样本方法

### 抽样策略
从157条成功解析记录中，按以下维度抽取**20条**样本进行深度分析：

| 维度 | 覆盖情况 |
|------|---------|
| **不同案由** | 20种（专利权侵权、损害股东利益、合伙合同、服务合同、侵害商业秘密、建设工程合同、名誉权、网络侵权、抵押权、合同纠纷、著作权侵权、商标权侵权、继承纠纷、买卖合同、机动车交通事故、房屋买卖合同、产品责任、劳务合同、相邻关系、提供劳务者受害） |
| **不同数据源** | 人民法院案例库（96条）、多元解纷案例库（58条）、人民法院案例库-未成年（3条） |
| **不同分数段** | 高分段95+（115条）、中分段85-94（33条）、低分段80-84（9条） |
| **不同case_level** | guiding_case（6条）、typical_case（91条）、reference_case（60条） |

### 分析方法
1. **源数据字段审计**：逐一检查21列CSV字段在prompt中的使用情况和LLM提取完整性
2. **输出结构完整性检查**：逐字段核对LLM output中每个字段是否被ontology覆盖
3. **全量统计**：对157条记录进行全量关键词搜索，量化各类「未被结构化提取」信息的出现频率
4. **深度样本分析**：对20条代表样本进行手工逐字段核查

---

## 第二部分：每个被忽略的信息维度（按优先级排序）

### P0级：核心推理链路缺失环节

#### P0-1：诉讼费/案件受理费的分担信息（Litigation Cost Allocation）

- **现象描述**：在judgment_results的specific_judgment中，部分判决明确写有「案件受理费由XX负担」的信息（如row_id=3282: "案件受理费由化工公司负担"）。这是判决主文的重要组成部分，但在LLM output中仅存在于自由文本中，未被结构化提取。全量搜索发现仅1条记录在judgment中明确提及受理费，但实际源数据中应更多（CSV的judgment_reason字段含相关表述）。
  
- **是否可通过现有ontology复用表达？** 可以。
  - `JudgmentResult`已含`reasoning`字段，可以承载费用分担说理
  - 但「费用由谁承担、金额多少」是判决主文的结论性信息，与推理过程不同
  - **方案**：在`JudgmentResult`中新增一个可选字段`cost_allocation`（字符串），格式如"案件受理费12800元，由原告承担30%，被告承担70%"

- **复用方案**：`JudgmentResult`新增字段`cost_allocation: str`，无需新实体

- **优先级**：**P1**（注：仅1/157条明确出现，频率低但法律意义大）

---

### P1级：有价值的关联分析丢失

#### P1-1：群体性案件人数/当事人人数（Party Count）

- **现象描述**：27/157条（17.2%）记录的关键事实中包含群体人数信息，如"120户业主"（row_id=6887）、"59户"（row_id=6014）、"653人"（row_id=13420）、"935户"（row_id=6622）、"40名员工"（row_id=6114）、"33名业主"（row_id=6188）等。这些信息用于识别群体性纠纷、示范诉讼和批量调解，具有高分析价值。当前LLM已提取到key_facts文本中，但未被结构化为独立字段。

- **是否可通过现有ontology复用表达？** 可以。
  - **方案A**：在`CaseSummary`中新增`party_count: int`（当事人/群体人数）
  - **方案B**：在`CourtCase`中新增`party_count: int`（案件涉及当事人总数）
  - 推荐方案B，因为群体人数属于案件层面的属性

- **复用方案**：`CourtCase`新增可选字段`party_count: int`

- **优先级**：**P1**

#### P1-2：保险公司角色信息的结构化不足（虽有提取但未标记角色）

- **现象描述**：10/157条（6.4%）记录明确提及保险信息。保险公司虽被提取到legal_subjects中（如row_id=7100中"保险公司"出现在legal_subjects），但缺乏统一标记机制：
  - 保险公司的`org_type`被设为"company"（正确），但缺乏区分保险公司与普通企业的标识
  - 缺少保险类型信息（交强险/商业险/三者险等）
  - 缺少保险赔付金额信息

- **是否可通过现有ontology复用表达？** 可以。
  - 上次审计已确定：保险公司通过`Organization.org_type="company"` + `CaseParticipant.role_code`复用即可，无需新增实体
  - 但当前的`role_code`枚举中没有`insurer`（保险人）角色
  - **方案**：在`LegalRole.role_code_enum`中增加`insurer`角色编码，保险角色用`role_code="insurer"`表示

- **复用方案**：`LegalRole.role_code_enum`增加`"insurer"`；同时在Evidence中鼓励提取保险单等证据

- **优先级**：**P1**

#### P1-3：鉴定/评估信息的结构化提取（Appraisal/Expert Conclusion）

- **现象描述**：10/157条（6.4%）记录的关键事实中包含鉴定信息，如"经鉴定构成十级伤残"（row_id=7100）、评估费用等。虽然LLM提取了`evidence_type="expert_opinion"`的证据项（如row_id=7100的"鉴定机构出具的伤残鉴定意见"），但：
  - 鉴定机构名称未被提取到`organization`或`expert_institution`
  - 鉴定结论摘要未被独立提取
  - 鉴定费用（如"评估费8万元"）未被结构化
  - 鉴定日期未被提取

- **是否可通过现有ontology复用表达？** 可以。
  - **方案**：在`Evidence`中，已有`evidence_type="expert_opinion"`枚举值。在此基础上：
    - 在`Evidence`中新增可选字段`expert_institution: str`（鉴定机构名称）
    - 在`Evidence`中新增可选字段`expert_conclusion: str`（鉴定结论摘要）
  - 鉴定机构作为Organization（ExpertInstitution子类型）也已被ontology覆盖

- **复用方案**：`Evidence`新增可选字段`expert_institution: str, expert_conclusion: str`

- **优先级**：**P1**

#### P1-4：多元解纷案例中调解机制信息的结构化缺失

- **现象描述**：58条多元解纷案例中，大量调解特色信息仅存在于key_facts/ conclusion的自由文本中：
  - **调解平台名称**："嚓呱小马扎"流动调解平台（row_id=34846）、"总对总"在线诉调对接机制（row_id=6086）、商会调解（row_id=7148/6064/12321）、行业调解（row_id=6295/6105/6422）
  - **调解方法**：背对背沟通、实地勘查、联动调解（row_id=6379）
  - **联动部门**：住建+法院+社区联动的信息（row_id=6379）
  - **特邀调解员**信息（row_id=6461/6114）
  - **调解组织类型**：人民调解委员会、行业调解委员会（row_id=6147/6937）
  
  当前仅trial_procedure粗略标记了"调解""诉前调解""先行调解"等类型，但调解平台名称、调解方法、联动部门等信息完全丢失。

- **是否可通过现有ontology复用表达？** 可以——通过现有实体复用即可，无需新增节点类型。
  - `trial_procedure`可以扩展为更规范的枚举值
  - `CourtCase.dispute_resolution_type`已有`mediation`枚举值，但仅10/58条被设置
  - **方案A（轻量）**：修复`dispute_resolution_type`的标注率（对所有调解案件强制设为`mediation`）
  - **方案B（推荐）**：在`CaseSummary`中新增可选字段`mediation_detail: dict`，包含：
    - `platform`: 调解平台名称
    - `mediators`: 调解员列表
    - `method`: 调解方法
    - `departments`: 联动部门
  - 方案B不引入新节点，仅扩展CaseSummary的属性

- **复用方案**：`CaseSummary`新增可选字段`mediation_detail: dict`（轻量结构体，非独立节点）

- **优先级**：**P1**

#### P1-5：amount_involved格式规范化与判决金额/诉请金额区分

- **现象描述**：95/157条（60.5%）有amount_involved，但格式严重不一致：
  - "30万元"（row_id=2626）
  - "1000000"（row_id=4483，纯数字无单位）
  - "局部维修费用约10万元"（row_id=14654，带描述）
  - "3万元及维权费用36,400元"（row_id=4070，多金额混合）
  - "请求赔偿100000元，判决赔偿4000元"（row_id=3772，诉请与判决混合）
  - "1115000美元"（row_id=5973，外币标的）
  
  无法区分是**诉请金额**还是**判决金额**，无法做诉请/判决对比分析。

- **是否可通过现有ontology复用表达？** 可以。
  - `CaseSummary.amount_involved`已有，但缺乏规范化
  - **方案**：在`CaseSummary`中新增：
    - `claim_amount: str`（诉请金额）
    - `judgment_amount: str`（判决金额）
    - 并对现有`amount_involved`进行规范化（统一为"数字+单位"格式）
  - 也可以在`JudgmentResult`的`compensation_amount`字段中记录判决金额

- **复用方案**：`CaseSummary`新增`claim_amount, judgment_amount`字段；`JudgmentResult.compensation_amount`正式启用

- **优先级**：**P1**

---

### P2级：增强信息

#### P2-1：保全措施信息（Preservation Measures）

- **现象描述**：3/157条（1.9%）记录涉及保全措施（查封、冻结等），如row_id=3619的"房屋被查封"、row_id=3082的"证券公司冻结账户"、row_id=2692的"公证保全证据"。这些信息存在于key_facts文本中但未被结构化提取。对于知识产权、合同纠纷等案件，保全措施是重要程序信息。

- **是否可通过现有ontology复用表达？** 可以。
  - **方案**：在`CourtCase`中新增可选字段`preservation_info: dict`，包含：
    - `preservation_type`: 保全类型（财产保全/证据保全/行为保全）
    - `preservation_status`: 保全状态（已保全/已解除）
    - `preservation_object`: 保全对象
  - 或在`ExecutionInfo`中扩展（执行与保全有部分重叠）

- **复用方案**：`CourtCase`新增可选字段`preservation_info: dict`

- **优先级**：**P2**

#### P2-2：在线诉讼/远程调解标记（Online Trial Flag）

- **现象描述**：6/157条（3.8%）的记录明确提及在线或远程审理方式，如"在线调解"（row_id=7148）、"在线诉调对接"（row_id=7009/6086）。这些信息分散在key_facts和conclusion的自由文本中，无独立标记位。

- **是否可通过现有ontology复用表达？** 可以。
  - **方案**：在`CourtCase`中新增可选布尔字段`is_online: bool`（是否在线审理），在`dispute_resolution_type`为mediation的配合场景下也可反映远程调解特征

- **复用方案**：`CourtCase`新增可选字段`is_online: bool`

- **优先级**：**P2**

#### P2-3：执行信息的部分丢失（Execution Info）

- **现象描述**：7/157条（4.5%）记录涉及执行信息（如"申请强制执行"、"执行完毕"），但：
  - 部分执行信息存在于key_facts中（如row_id=6887的"业主申请法院强制执行"）
  - `ExecutionInfo`实体已在ontology中存在，但当前prompt未要求提取执行信息
  - 提示词v3的`result_type`枚举中包含执行类型（`execution_upheld`等），但实际提取中未见使用

- **是否可通过现有ontology复用表达？** 可以——现有`ExecutionInfo`实体和`JudgmentResult.result_type`的执行枚举已就位。
  - **方案**：在prompt中增加执行信息提取指令，为涉及执行的案件填充`result_type`的执行枚举值和`ExecutionInfo`实体
  - 无需新字段，仅需prompt改进

- **复用方案**：利用既有`ExecutionInfo`实体和`JudgmentResult.result_type`枚举（`execution_upheld`, `execution_revoked`, `execution_terminated`, `added_executor`）

- **优先级**：**P2**

#### P2-4：管辖权争议信息（Jurisdiction Info）

- **现象描述**：4/157条（2.5%）记录涉及管辖权问题。管辖权是诉讼程序的重要前置问题，影响案件分析和类案推荐。

- **是否可通过现有ontology复用表达？** 可以。
  - **方案**：在`DisputeFocus`中已有`content`字段可以记录管辖权争议，或在`CourtCase`中新增可选字段`jurisdiction_info: str`（管辖权争议摘要）

- **复用方案**：`CourtCase`新增可选字段`jurisdiction_info: str`

- **优先级**：**P2**

#### P2-5：related_info中「其他程序」类型案件的处理（如破产确认）

- **现象描述**：14/157条（8.9%）的related_info包含non-standard court level标记，如"其他程序"（row_id=5523中的破产申请）、"再审审查"（多个案例）、"指令再审"等。LLM通常将这些映射到court_cases数组，但在trial_level映射上存在偏差（例如将再审审查`retrial_review`映射为`retrial`）。此外，破产程序等特殊程序类型在trial_level枚举中无对应项。

- **是否可通过现有ontology复用表达？** 可以。
  - **方案**：在`CourtCase.trial_level_enum`中增加`"special_proceeding"`（特别程序）、`"retrial_review"`（再审审查）枚举值
  - 当前枚举值：`first_instance, second_instance, retrial`
  - 建议增加：`retrial_review, special_proceeding, execution`

- **复用方案**：`CourtCase.trial_level_enum`扩展3个枚举值

- **优先级**：**P2**

#### P2-6：关键日期推断精度不足（Filing Date）

- **现象描述**：143/157条（91.1%）的filing_date被默认推断为YYYY-01-01（案号年份的第一天），说明LLM无法从文本中提取精确立案日期。related_info中的日期信息（如"一审：XXX法院（XXXX）X民初XX号民事判决（XXXX年X月X日）"）已被提取为judgment_date，但filing_date缺乏独立来源。

- **是否可通过现有ontology复用表达？** 可以。
  - **方案**：无需新增字段，而是改进prompt策略：
    - 从basic_facts中提取"受理"、"起诉"等关键词后的日期作为filing_date
    - 从案号年份+合理推定（如年中）替代YYYY-01-01
  - 短期建议：用judgment_date前推合理期限替代YYYY-01-01

- **复用方案**：prompt改进，不涉及ontology变更

- **优先级**：**P2**

---

## 第三部分：汇总建议表

| 信息维度 | 复用方案 | 需修改 | 优先级 |
|----------|---------|--------|:------:|
| **群体案件人数** | `CourtCase`新增`party_count: int` | ontology扩展 + prompt | P1 |
| **保险公司角色** | `LegalRole.role_code_enum`增加`"insurer"` | ontology枚举扩展 | P1 |
| **鉴定/评估信息** | `Evidence`新增`expert_institution: str, expert_conclusion: str` | ontology扩展 + prompt | P1 |
| **调解机制信息** | `CaseSummary`新增`mediation_detail: dict`（调解平台/方法/联动部门） | ontology扩展 + prompt | P1 |
| **诉请/判决金额区分** | `CaseSummary`新增`claim_amount, judgment_amount`；启用`JudgmentResult.compensation_amount` | ontology扩展 + prompt | P1 |
| **诉讼费分担** | `JudgmentResult`新增`cost_allocation: str` | ontology扩展 | P1 |
| **保全措施** | `CourtCase`新增`preservation_info: dict` | ontology扩展 + prompt | P2 |
| **在线诉讼标记** | `CourtCase`新增`is_online: bool` | ontology扩展 + prompt | P2 |
| **执行信息** | 利用既有`ExecutionInfo`实体 + `JudgmentResult.result_type`执行枚举 | prompt改进（无ontology变更） | P2 |
| **管辖权争议** | `CourtCase`新增`jurisdiction_info: str` | ontology扩展 + prompt | P2 |
| **特别程序/再审审查** | `CourtCase.trial_level_enum`增加`special_proceeding, retrial_review, execution` | ontology枚举扩展 | P2 |
| **立案日期精度** | 改进filing_date提取策略（从basic_facts提取或合理推定） | prompt改进（无ontology变更） | P2 |
| **dispute_resolution_type全覆盖** | 强制对所有court_case标注dispute_resolution_type | prompt改进（无ontology变更） | P2 |
| **amount_involved格式规范化** | 统一为"数字+单位"格式，标注金额类型 | prompt改进（无ontology变更） | P2 |

---

## 附录：关键发现详情

### 附录A：源数据字段利用情况更新表

| CSV列 | 当前利用状态 | 未被利用的高价值信息 |
|-------|:----------:|:------------------:|
| related_info | ✅ 法条和案号已提取 | 内嵌的前身法版本信息（如"本案适用的是2009年施行的..."）未被版本化标记 |
| related_law | ❌ 全为`\\N` | 无（列空） |
| related_judgment_body | ❌ 全为`\\N` | 无（列空） |
| judgment_mean | ❌ 全为`\\N`（CSV空，但LLM从judgment_essence补充42/157条） | 可通过prompt改进提升补充率 |
| court_name | ❌ 直接引用 | 2条仲裁案件中CSV court_name="最高人民法院"与实际仲裁审理机构不一致，但可作为信息校验源 |

### 附录B：奥卡姆剃刀应用记录

以下曾被建议为新实体，经评估后否决：

| 被否决的建议 | 否决理由 |
|-------------|---------|
| 新增`InsuranceInfo`节点 | 保险公司通过`Organization.org_type="company"` + `LegalRole.role_code="insurer"`复用表达 |
| 新增`MediationInfo`节点 | 调解平台/方法/联动部门作为`CaseSummary.mediation_detail`字典属性，无需独立节点类型 |
| 新增`AppraisalInfo`节点 | 鉴定信息作为`Evidence`的属性扩展（expert_institution + expert_conclusion）即可 |
| 新增`GroupCase`节点 | 群体案件通过`CourtCase.party_count`属性标记，无需新节点 |
| 新增`OnlineTrial`标记 | 单一布尔字段`is_online`即可，无需新实体 |
