# 🏛️ 法律知识图谱 Gold层校验审计报告

**审计角色**: legal_pm  
**审计时间**: 2026-05-07  
**批次范围**: batch_state.json processed_ids (55条，含额外ID)  
**本体版本**: legal_ontology_v2.yaml (2026.04.v2)  

---

## 一、数据概览

| 节点/边类型 | 记录数 | 本体预期字段 | 填充率 |
|---|---|---|---|
| GuidingCase | 55 | 15 | 良好 |
| Court | 48 | 10 | 良好 |
| CaseType | 52 | 10 | 良好 |
| LegalProvision | 1 | 10 | 差（仅1条） |
| edges_GUIDES_CASE_TYPE | 55 | 2 | 100% |
| edges_CITES | 1 | 4 | 差（仅1条） |

**batch_state.json**: total_processed=55, 但 processed_ids 列表含55个ID，实际对应 GuidingCase 55条，完全匹配。  
**原始CSV**: 45条记录（含不同来源：人民法院案例库、多元解纷案例库、人民检察院案例）

---

## 二、字段一致性校验

### 2.1 GuidingCase 与本体 YAML 比对

| 字段 | 本体定义 | 实际数据 | 状态 |
|---|---|---|---|
| id | required, pattern `^[a-z]+_[0-9]{4}_[a-z_]+$` | 格式 `guiding_case_NNNN` ✓ | ✅ |
| name | required | 全部填充，格式 `案由分类-案由名-案号` | ✅ |
| guiding_case_number | required | 全部填充，如 `2024-12-3-021-005` | ✅ |
| issuing_court_id | required, FK→Court.id | 全部填充 ✓ | ✅ |
| publication_date | required, date | 54/55 (98.2%) | ⚠️ 1条缺失 |
| guiding_points | required | 55/55 (100%) | ✅ |
| binding_force | required, enum: mandatory/persuasive/reference | 54 mandatory, 1 persuasive | ✅ |
| source_url | optional | 55/55 (100%) | ✅ |
| tags | optional | 55/55 (100%) | ✅ |
| trial_procedure | optional | 54/55 (98.2%) | ✅ |
| trial_level | optional | **4/55 (7.3%)** | ❌ 严重缺失 |

### 2.2 Court 与本体 YAML 比对

| 字段 | 本体定义 | 实际数据 | 状态 |
|---|---|---|---|
| id | required | 全部填充，格式 `court_xxx` | ✅ |
| name | required | 全部填充，法院名称可识别 | ✅ |
| org_type | required (Organization) | 全部为 `court` | ✅ |
| court_level | required, enum: supreme/high/intermediate/basic/special | 全部分布正确 | ✅ |
| district_id | required | **48/48 全为空** | ❌ 严重问题 |
| credit_code | optional | 全部填充 `cc_xxx` 格式 | ⚠️ 非标准信用代码 |

### 2.3 CaseType 与本体 YAML 比对

| 字段 | 本体定义 | 实际数据 | 状态 |
|---|---|---|---|
| id | required | 全部填充 | ✅ |
| code | required | 全部填充 | ✅ |
| name | required | 全部填充 | ✅ |
| category | required, enum: civil/criminal/administrative/ip/execution/state_compensation | **中文值**：民事/刑事/行政/国家赔偿/执行/执行实施 | ❌ |
| level1 | required | 全部填充（中文） | ✅ |
| level2 | required | 全部填充（中文） | ✅ |

### 2.4 LegalProvision 与边

**⚠️ 严重不足**: 50个指导性案例仅解析出 **1条法律条文** 和 **1条 CITES 边**。  
- 从原始CSV看，每个案例的 `related_law` 字段都含有法律引用，但解析器未提取
- 仅 `guiding_case_20260421`（一个聚合ID，存在于edges_CITES但不存在于GuidingCase节点中）与 provision_22482bb67bc6 建立了关系
- **CITES边的case_id `guiding_case_20260421` 是孤立ID，不在GuidingCase节点中**

---

## 三、枚举值校验

### 3.1 binding_force ✓
- `mandatory`: 54条 ✓
- `persuasive`: 1条 ✓
- `reference`: 0条（本体接受，但无此值）

### 3.2 category ❌
CaseType的category字段全部使用**中文值**（民事、刑事、行政等），但本体YAML要求**英文枚举值**（civil、criminal、administrative等）。这是**中文数据映射到英文枚举的转换缺失问题**。

### 3.3 court_level ✓
枚举值分布完全合法：supreme(2), high(9), intermediate(20), basic(17), special(0)

---

## 四、原始CSV交叉验证（7条抽样）

| # | 原始ID | Gold ID | 原始案由 | Gold名称中案由 | 原始法院 | Gold法院名称 | 一致性 |
|---|---|---|---|---|---|---|---|
| 1 | 2292 | guiding_case_2292 | 行政-不履行XX职责 | 行政-不履行XX职责 | 江苏省高级人民法院 | 江苏省高级人民法院 | ✅ |
| 2 | 298 | guiding_case_298 | 民事-产品责任纠纷 | 民事-产品责任纠纷 | 江苏省泰州市中级人民法院 | 江苏省泰州市中级人民法院 | ✅ |
| 3 | 412 | guiding_case_412 | 民事-产品责任纠纷 | 民事-产品责任纠纷 | 贵州省黔东南苗族侗族自治州中级人民法院 | 贵州省黔东南苗族侗族自治州中级人民法院 | ✅ |
| 4 | 604 | guiding_case_604 | 民事-侵害商业秘密纠纷 | 民事-侵害商业秘密纠纷 | 最高人民法院 | 最高人民法院 | ✅ |
| 5 | 476 | guiding_case_476 | 刑事-非法采矿罪 | 刑事-非法采矿罪 | 东台市人民法院 | 东台市人民法院 | ✅ |
| 6 | 6379 | guiding_case_6379 | 民事-相邻关系纠纷 | 民事-相邻关系纠纷 | 鹤岗市工农区人民法院 | 鹤岗市工农区人民法院 | ✅ |
| 7 | 12931 | guiding_case_12931 | 刑事-故意伤害罪 | 刑事-故意伤害罪 | 湖南省湘西土家族苗族自治州中级人民法院 | 湖南省湘西土家族苗族自治州中级人民法院 | ✅ |

**结论**: 7条抽样记录解析完全正确，案由分类、法院名称、案号字段与原始CSV一致。

---

## 五、异常与问题检测

### 🔴 严重问题

1. **Court.district_id 全部为空 (48/48)**  
   - 影响：Court节点缺失地理位置信息，`has_jurisdiction_over` 关系无法正常建立  
   - 建议：从法院名称中提取辖区/地区代码，或从原始数据补充

2. **LegalProvision 提取严重不足 (仅1条)**  
   - 50个指导性案例至少应有50+条法律条文引用，但仅提取了1条  
   - 原始CSV的 `related_law` 字段含有丰富法律引用数据，未被充分解析  
   - CITES边连接到一个不存在的case_id (`guiding_case_20260421`)

3. **CaseType.category 使用中文而非英文枚举**  
   - YAML定义枚举值：civil, criminal, administrative, ip, execution, state_compensation  
   - 实际数据：民事, 刑事, 行政, 国家赔偿, 执行, 执行实施  
   - 新增值 `执行实施` 不在本体枚举中  
   - 新增值 `国家赔偿` 不在本体枚举中（对应 state_compensation）

### 🟡 中等问题

4. **guiding_case_476 缺失 publication_date**  
   - 原始CSV中该记录的 trial_year 为 `\N` 空值，解析器未处理

5. **trial_level 填充率仅 7.3% (4/55)**  
   - 本体定义为 optional，但此字段对二审/再审案件分析重要  
   - 原始CSV中 trial_procedure 字段有值（二审/一审等），但未映射到 trial_level

6. **Court 有重复ID：court_cc36c8792b01（最高人民法院）出现2次**  
   - 虽然是同一法院被多次引用，但图数据库中应使用唯一节点，边关联不应创建重复

### 🟢 轻微问题

7. **CaseType 无 description 和 typical_provision_ids 字段填充**  
   - 这两个字段为 optional，当前为空不会导致错误

8. **CaseType.level1 和 level2 设计含义混淆**  
   - 当前 `level1=大分类(如'行政')`、`level2=具体案由(如'不履行XX职责')`  
   - 本体预期的 level 层级结构与实际使用方式不一致

---

## 六、异常检测明细

| 异常类型 | 数量 | 严重程度 | 影响范围 |
|---|---|---|---|
| 必填字段缺失 (publication_date) | 1 | 高 | 1条记录无效日期 |
| 枚举值不匹配 (category中文) | 52 | 高 | 系统间数据交换 |
| district_id为空 | 48 | 高 | 地理关联缺失 |
| 法律条文提取缺失 | ~50 | 高 | 核心知识缺失 |
| trial_level低填充 | 51 | 中 | 审判层级分析受限 |
| 法院重复节点 | 1 | 中 | 图结构冗余 |
| CITES边孤立ID | 1 | 中 | 边失联 |

---

## 七、本体优化建议

### 建议1: CaseType.category 枚举值中文化
```yaml
# 当前定义
category_enum: [civil, criminal, administrative, ip, execution, state_compensation]

# 建议改为（或同时支持中文别名）
category_enum: [civil, criminal, administrative, ip, execution, state_compensation]
category_zh_label:
  civil: 民事
  criminal: 刑事
  administrative: 行政
  ip: 知识产权
  execution: 执行
  state_compensation: 国家赔偿
```
同时新增枚举值 `execution_enforcement` 对应原始数据中的 `执行实施`。

### 建议2: CaseType.level 结构澄清
在本体定义中补充说明 `level1` 和 `level2` 的层级含义：
```yaml
CaseType:
  required: [code, category, level1, level2]
  # level1: 大类（如民事、刑事、行政）
  # level2: 具体案由（如故意伤害罪、合同纠纷）
  # 当案由系统中只有单层分类时，level1=category中文名, level2=具体案由
```

### 建议3: Court.district_id 增加别名解析规则
从法院名称自动提取区域代码：
```yaml
engineering:
  entity_disambiguation:
    Court:
      name: "name + district.code"
  court_district_mapping:
    - pattern: "^(.*省|.*自治区|.*市)(.*中级人民法院|.*人民法院)$"
      district: "group(1)"
```
或添加一个数据处理步骤：根据法院名称反向推断district。

### 建议4: 法条解析增强
指导性案例的 `related_law` 字段含 `<p>《立法法》第96条第2项<br/>《社会保险法》第30条第1款</p>` 等结构化引用，建议：
- 增强正则解析以提取法条引用
- 每条指导性案例至少提取引用法条
- 正确建立 CITES 关系（case_id 使用实际 guiding_case_id 而非聚合ID）

### 建议5: 添加 trial_level 映射规则
从 `trial_procedure`（二审/一审/再审）自动映射到 `trial_level`（first_instance/second_instance/retrial）。

---

## 八、总结评分

| 维度 | 评分 | 说明 |
|---|---|---|
| **数据一致性** | ⭐⭐⭐⭐ (4/5) | GuidingCase/Court/CaseType节点一致性良好 |
| **字段填充率** | ⭐⭐⭐ (3/5) | 主节点填充率高，但 district_id 和 trial_level 缺失 |
| **解析准确性** | ⭐⭐⭐⭐⭐ (5/5) | 7条抽样验证全部正确 |
| **关系完整性** | ⭐⭐ (2/5) | 法条-案例关系严重缺失 |
| **本体一致性** | ⭐⭐⭐ (3/5) | 枚举值中英文不匹配，需处理 |

**整体评分**: ⭐⭐⭐⭐ (4/5) — 节点层数据质量高，关系层需大幅提升
