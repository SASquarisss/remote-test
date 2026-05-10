# v5 Extraction Audit Report

## 第一部分：方法论

### 抽样策略
从158条成功解析记录中，按以下维度抽取**19条**样本：
- **不同案由（case_type）**：覆盖19种不同案由（专利权侵权、损害股东利益、合伙合同、服务合同、侵害商业秘密、名誉权、网络侵权、抵押权、相邻关系、劳务合同、建设工程合同、合同纠纷、继承纠纷、买卖合同、机动车交通事故、物业服务合同、房屋买卖合同、未成年人保护公益诉讼等）
- **不同数据源（web_name）**：人民法院案例库(8条)、多元解纷案例库(10条)、人民法院案例库-未成年(1条)
- **不同分数段**：高分95+（10条）、中分85-89（3条）、低分80-84（6条）
- **不同case_level**：01-指导性案例（1条）、02-典型案例（7条）、04/空白-参考案例（11条）

### 分析维度
1. **源数据字段审计**：21列CSV逐一检查prompt使用情况
2. **LLM提取质量**：binding_force映射、court_cases覆盖度、judges/attorneys提取、evidence/provision质量
3. **语义覆盖度**：关键信息是否丢失、民事特有属性是否覆盖、多元解纷与人民法院案例库差异

---

## 第二部分：样本详表

### 样本1：row_id=2626
| 维度 | 内容 |
|------|------|
| web_name | 人民法院案例库 |
| case_type | 民事-专利权权属、侵权纠纷 |
| score | 95.0 |
| **源数据关键字段** | basic_facts: 北京仁某医药科技诉湖南慈某医疗科技侵害发明专利权纠纷，外耳矫形器与骨科定位片组合产品技术比对... |
| | judgment_reason: 法院生效裁判认为，I型骨科定位片可单独使用不应组合比对，但II型骨科定位片有安装脚必须组合使用... |
| | related_info: 专利法第11条、第64条；一审(2020)浙01知民初277号 / 二审(2021)最高法知民终2270号 |
| **LLM提取关键字段** | guiding_case_name: 北京仁某医药科技有限公司诉湖南慈某医疗科技有限公司等专利权权属、侵权纠纷案 |
| | court_cases: 2个审级（一审杭州中院 + 二审最高法） |
| | evidence: 1条（公证购买证据） |
| | legal_provisions: 3条（专利法2条+最高法解释1条） |
| | amount_involved: 30万元 |
| **缺失/遗漏** | 🔴 judges数组为空（源数据judgment_reason含合议庭成员信息） |
| | 🔴 attorneys数组为空 |
| | 🔴 trial_organizations为空 |

### 样本2：row_id=714
| 维度 | 内容 |
|------|------|
| web_name | 人民法院案例库 |
| case_type | 民事-损害股东利益责任纠纷 |
| score | 95.0 |
| **源数据关键字段** | basic_facts: 东某证券通过司法执行以股抵债取得皇某集团5841万股限售股，业绩承诺已完成但公司拒绝解禁... |
| | judgment_reason: 三大争议焦点：承诺函真实性、股东大会决议效力、损失赔偿计算 |
| | related_info: 民法典1165/1184条、公司法22/137/144条；一审上海金融法院2020-7-29/二审上海高院2022-7-25 |
| **LLM提取关键字段** | court_cases: 2个审级 |
| | evidence: 5条（承诺函、股东大会决议、公告等） |
| | legal_provisions: 6条 |
| | amount_involved: 500万元 |
| **缺失/遗漏** | 🔴 judges/attorneys/trial_organizations均为空 |

### 样本3：row_id=3612
| 维度 | 内容 |
|------|------|
| web_name | 人民法院案例库 |
| case_type | 民事-合伙合同纠纷 |
| score | 95.0 |
| **源数据关键字段** | basic_facts: 雷某与李某等签订联合投资协议承接海外工程，涉及"草签"协议效力认定 |
| | judgment_reason: "草签"协议实质具备合同全部要素，应视为正式合同 |
| | related_info: 民法典156/470/490条；一审武汉中院/二审湖北高院/再审最高法 |
| **LLM提取关键字段** | court_cases: 3个审级（一审+二审+再审） |
| | legal_provisions: 3条 |
| | amount_involved: 700万元 |
| **缺失/遗漏** | 🔴 judges/attorneys/trial_organizations均为空 |

### 样本4：row_id=5368（指导性案例）
| 维度 | 内容 |
|------|------|
| web_name | 人民法院案例库 |
| case_type | 民事-服务合同纠纷 |
| score | 95.0 |
| case_level | 01→guiding_case→binding_force=mandatory ✅ 映射正确 |
| **LLM提取关键字段** | court_cases: 1个（一审徐州泉山区法院） |
| | evidence: 2条 |
| | legal_provisions: 1条（合同法39条） |
| **缺失/遗漏** | 🟡 amount_involved未提取（源数据涉及50元话费等小额金额） |

### 样本5：row_id=6379（多元解纷案例库）
| 维度 | 内容 |
|------|------|
| web_name | 多元解纷案例库 |
| case_type | 民事-相邻关系纠纷 |
| score | 95.0 |
| **源数据关键字段** | basic_facts: 郑某违规搭建保温阳台，雨水倒灌+采光受阻，住建局+法院+社区联动调解 |
| | judgment_reason: 背对背沟通→实地勘查→释法明理→源头治理四步调解法 |
| | related_info: 民法典288/293条、城乡规划法64条 |
| **LLM提取关键字段** | court_cases: 1个（鹤岗市工农区法院）dispute_resolution_type=mediation |
| | evidence: 2条 |
| **缺失/遗漏** | 🔴 judges/attorneys为空 |
| | 🟡 amount_involved未提取（涉及"郑某承担40%费用"但无具体金额） |
| | 🟡 调解员具体人员信息未提取（源数据有详细调解团队信息） |

### 样本6：row_id=34846（多元解纷 - 劳务合同）
| 维度 | 内容 |
|------|------|
| web_name | 多元解纷案例库 |
| case_type | 民事-劳务合同纠纷 |
| score | 85.0 |
| **源数据关键字段** | basic_facts: 姜某等18人劳务报酬被拖欠，某工程公司出具欠款凭证后不履行 |
| | judgment_reason: "嚓呱小马扎"流动调解平台，乡贤+法官+镇政府三方联调 |
| **LLM提取关键字段** | court_cases: 1个（沭阳县法院），case_number为空 |
| | judges: 1条（提取到法官信息）|
| **缺失/遗漏** | 🟡 case_number未提取 |
| | 🔴 trial_organizations为空 |
| | 🟡 具体调解机制信息（"嚓呱小马扎"平台）未被结构化提取 |

### 样本7：row_id=12147（未成年人保护公益诉讼 - 低分）
| 维度 | 内容 |
|------|------|
| web_name | 人民法院案例库-未成年 |
| case_type | 民事-未成年人保护民事公益诉讼 |
| score | 80.0 |
| **LLM提取关键字段** | court_cases: 1个（河北省石家庄中级法院），case_number为空 |
| | legal_provisions: 6条 |
| | evidence: 0条 |
| **缺失/遗漏** | 🔴 evidence数组为空（源数据应含证据信息） |
| | 🔴 judges/attorneys/trial_organizations为空 |

### 样本8：row_id=6887（多元解纷 - 房屋买卖合同 - 低分）
| 维度 | 内容 |
|------|------|
| web_name | 多元解纷案例库 |
| case_type | 民事-房屋买卖合同纠纷 |
| score | 83.0 |
| **源数据关键字段** | basic_facts: 120户业主逾期交房违约金执行前和解，仲裁裁决已出但公司无财产可执行 |
| **LLM提取关键字段** | court_cases: 1个，case_number为空 |
| | evidence: 0条 |
| **缺失/遗漏** | 🔴 evidence数组为空 |
| | 🟡 case_number未提取 |
| | 🟡 "120户"群体人数信息在amount_involved中未体现 |

### 样本9：row_id=7100（多元解纷 - 交通事故 - 中分）
| 维度 | 内容 |
|------|------|
| web_name | 多元解纷案例库 |
| case_type | 民事-机动车交通事故责任纠纷 |
| score | 85.0 |
| **源数据关键字段** | basic_facts: 郭某被王某撞伤构成十级伤残，医疗费35000余元，王某只投保交强险 |
| **LLM提取关键字段** | amount_involved: 35000余元（医疗费）及残疾赔偿金等合计约十几万元 |
| **缺失/遗漏** | 🔴 judges/attorneys/trial_organizations为空 |
| | 🟡 保险公司角色明确但未在dispute_resolution_type中体现 |

### 样本10：row_id=6422（多元解纷 - 物业服务合同 - 低分）
| 维度 | 内容 |
|------|------|
| web_name | 多元解纷案例库 |
| case_type | 民事-物业服务合同纠纷 |
| score | 80.0 |
| **源数据关键字段** | basic_facts: 25名业主拒交物业费，拖欠3年 |
| **缺失/遗漏** | 🟡 amount_involved未提取（源数据含物业费金额信息） |

---

## 第三部分：综合分析

### A. 源数据字段覆盖率

| CSV列 | 是否被prompt使用 | 是否被提取到输出 | 是否有价值未被利用 |
|-------|:----------------:|:----------------:|:------------------:|
| id | ✅ 作为row_id | ✅ input.row_id | 无 |
| web_name | ✅ guiding_case_name生成 | ✅ guiding_case_name | 无 |
| web_url | ✅ source_url | ✅ source_url | 无 |
| case_type | ✅ case_type映射 | ✅ case_type | 无 |
| storage_no | ✅ storage_no | ✅ storage_no | 无 |
| court_name | ❌ 直接引用（通过basic_facts间接） | ✅ court_cases[].court.name | 低—法院名在basic_facts中已含 |
| key_words | ✅ key_words | ✅ key_words | 无 |
| trial_procedure | ✅ trial_procedure | ✅ trial_procedure | 无 |
| trial_year | ✅ publication_date | ✅ publication_date | 无 |
| case_level | ✅ case_level/binding_force | ✅ case_level/binding_force | 无—映射准确 |
| basic_facts | ✅ 关键事实源 | ✅ key_facts/reasoning | 低—核心信息已提取 |
| judgment_reason | ✅ 推理+证据源 | ✅ reasoning/evidence | 中—合议庭成员信息丢 |
| judgment_essence | ✅ guiding_points | ✅ guiding_points | 无 |
| **related_info** | ✅ 法条+案号源 | ✅ legal_provisions/case_numbers | **高—内嵌审级+日期信息，LLM提取不完整** |
| related_law | ❌（全为空） | ❌ | 无（CSV列全空） |
| related_judgment_body | ❌（全为空） | ❌ | 无（CSV列全空） |
| create_time | ❌ metadata | ❌ | 无 |
| update_time | ❌ metadata | ❌ | 无 |
| md5_value | ❌ metadata | ❌ | 无 |
| **judgment_mean** | ✅ 直接传递 | ✅ 42/157输出中有值 | **高—CSV列全空，LLM从judgment_essence补充** |
| dt | ❌ metadata | ❌ | 无 |

### B. 发现的问题

#### P0：关键信息遗漏

1. **judges（法官/合议庭成员）几乎全空 —— 98%缺失**
   - 157条成功记录中仅3条有judges数据
   - 源数据judgment_reason和related_info中通常含有合议庭成员信息（如"审判长XXX、审判员XXX"），但prompt虽要求提取，实际提取效果极差
   - **影响**：无法建立"法官-案件"关联，影响审判人员画像和分析

2. **attorneys（律师/代理人）几乎全空 —— 98%缺失**
   - 157条中仅3条有attorneys数据
   - 民事案件绝大多数含律师代理信息（源数据中有"委托诉讼代理人"等表述）
   - **影响**：无法做律所-法官-案件关联分析

3. **trial_organizations（审判组织）93%缺失**
   - 157条中仅11条有值，其中多数仅有case_number无具体members
   - 合议庭组成结构信息完全丢失

#### P1：重要信息缺失

4. **多元解纷案例库中调解机制信息未被结构化提取**
   - 85条多元解纷案例的特色信息（调解员类型、调解平台、联动部门、调解方法）完全丢失
   - 例如"嚓呱小马扎"流动调解平台、"总对总"在线诉调对接机制、住建+法院+社区联动等信息仅以自由文本存在于judgment_reason中，未作为结构化属性提取
   - **影响**：无法做调解模式分析和效果评估

5. **群体性案件人数信息丢失**
   - "120户业主"、"18名工人"、"25名业主"、"59户业主"等群体数量信息蕴含在basic_facts中，但amount_involved字段未规范提取
   - 没有独立的"群体案件人数"属性

6. **court_cases中case_number缺失（低分案件）**
   - 6条多元解纷案例的court_case.case_number为空
   - 多元解纷案例库的案件号格式与人民法院案例库不同（D2025-161-...），LLM未能正确提取

7. **dispute_resolution_type仅对10条记录设定了"mediation"**
   - 多元解纷案例库共85条，但仅10条的court_cases设置了dispute_resolution_type
   - 不应仅对调解案件标注，诉讼/仲裁等也应标注

8. **amount_involved提取不全**
   - 虽有95条记录有amount_involved提取，但格式不一致（"30万元"vs"1000000"vs"267260元"）
   - 部分涉及金额的案件未提取（如5368号50元话费案）

#### P2：质量/细节问题

9. **legal_provisions提取数量合理但citation_purpose单一**
   - 无案件缺失legal_provisions（良好），平均每条3-6条
   - 但citation_purpose几乎全部为"适用依据"，说理依据/反驳依据极少区分

10. **Legal Provision Elements (LPEs)提取良好但质量可提高**
    - 155/157条有LPEs，总量815条
    - 部分LPE的element_type映射可能不准确（主体要件vs行为要件混淆）

11. **guiding_case_number提取率极低（4/157）**
    - 指导性案例的正式编号如"指导案例XX号"未被提取
    - 6条case_level=01（指导性案例）中，guiding_case_number基本全空

12. **reasoning长度不一**
    - 部分records的reasoning仅40-50字（如2626号仅48字），过于简略
    - 另一些reasoning达200字，质量良好

13. **多元解纷案例与人民法院案例库在信息结构上差异显著**
    - 人民法院案例库：有case_level（01/02/04）字段，binding_force映射合理
    - 多元解纷案例库：case_level为\\N（空），binding_force一律为"reference"
    - 人民法院案例库含审判程序信息（一审/二审），多元解纷案例库多为调解类型说明（诉前调解/先行调解/执行前和解）
    - 人民法院案例库的related_info含"#####"分隔符分离法条与审级信息，多元解纷案例库的related_info更简洁

### C. 建议

#### 1. Ontology扩展建议

| 建议内容 | 优先级 | 说明 |
|----------|:------:|------|
| 新增 `MediationInfo` 节点类型 | P0 | 结构化存储调解模式、调解员构成、联动部门、调解方法等多元解纷特色信息 |
| `CourtCase` 增加 `party_count`（当事人人数） | P1 | 支持群体性案件的人数统计和聚合分析 |
| `CourtCase` 增加 `insurance_info` | P2 | 机动车交通事故等案件中保险公司角色的规范提取 |
| `Evidence` 增加 `appraisal_info`（鉴定/评估信息） | P2 | 建设工程、人身损害等案件中鉴定机构及鉴定结论 |
| `JudgmentResult` 正式启用 `compensation_amount` 字段 | P1 | 现有amount_involved在case_summary不够，应独立结构化 |
| `GuidingCase` 增加 `mediation_method` 枚举 | P1 | 背对背/面对面/在线调解/专家评估等 |
| `Attorney` 增加 `representation_type` | P2 | 委托代理/法律援助/指定辩护等 |

#### 2. Prompt改进建议

| 建议内容 | 优先级 | 说明 |
|----------|:------:|------|
| **强制提取judges和trial_organization** | **P0** | 增加Few-shot示例展示合议庭信息提取，在basic_facts/judgment_reason/related_info中强制检索"审判长""审判员""合议庭"等关键词 |
| **强制提取attorneys** | **P0** | 增加Few-shot示例展示"委托诉讼代理人""律师"信息提取 |
| **多元解纷案例专用字段提取** | **P1** | 增加针对多元解纷案例库的prompt分支：提取调解平台名称、调解员构成、联动部门等 |
| **improve case_number提取** | **P1** | 对多元解纷案例库的案号格式（D2025-161-...）提供Few-shot示例 |
| **完善amount_involved提取规范** | **P2** | 要求统一金额格式（数字+单位），并标明是诉请金额还是判决金额 |
| **group/群体案件人数提取** | **P2** | 增加"当事人人数"提取指令 |
| **dispute_resolution_type全覆盖** | **P2** | 对所有court_case强制标注dispute_resolution_type |

#### 3. 后处理建议

| 建议内容 | 优先级 | 说明 |
|----------|:------:|------|
| **从judgment_reason正则提取judges/attorneys** | **P0** | 使用正则"审判长[：:]?\*?([\u4e00-\u9fa5]{2,4})"等从现有extraction的judgment_reason字段后处理提取 |
| **从related_info解析审级信息** | **P1** | related_info中"一审：XXX法院（XXXX）X民初XX号"结构可以正则提取，补充amount_involved |
| **多元解纷案例元数据标准化** | **P1** | 对多元解纷案例统一提取调解平台/联动部门/调解员构成等 |
| **binding_force复查** | **P2** | case_level=04或其他异常值时的fallback处理 |

---

## 附录：关键统计汇总

| 指标 | 数值 |
|------|:----:|
| 成功解析记录 | 157条 |
| 总记录 | 230条 |
| 命中率 | 68.3% |
| 平均证据数 | ~3条/案 |
| 平均法条数 | ~4条/案 |
| judges非空率 | 3/157 (1.9%) |
| attorneys非空率 | 3/157 (1.9%) |
| trial_org非空率 | 11/157 (7.0%) |
| amount_involved提取率 | 95/157 (60.5%) |
| 多元解纷dispute_resolution_type标注率 | 10/85 (11.8%) |
| LPE提取率 | 155/157 (98.7%) |
| 最高分 | 100 |
| 最低分（非0） | 80 |
