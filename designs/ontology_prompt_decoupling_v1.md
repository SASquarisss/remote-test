# 本体-提取管线解耦方案 v1

> **角色**: KG_Architect
> **目标**: YAML本体定义变更 → 自动生成/同步提取提示词，实现"改一次本体，全管线同步"
> **原则**: 轻量、纯 Python、不引入外部工具链

---

## 1. 问题分析 — 当前方案的 5 个具体痛点

### 痛点 1: 本体与提示词手写耦合（维护成本指数级增长）
本体 YAML（478行、20+实体、25关系、9约束、几十个枚举）和提示词 txt（272行）是两个独立文件。每次本体更新（如 2026.04.v2 新增 `CaseSummary`、`SentencingStandard`、扩展 `role_code_enum` 从 18 个到 26 个），都必须**人工逐行同步**到提示词。一次遗漏即导致提取字段缺失或枚举值不匹配。

### 痛点 2: 枚举值通过自然语言描述，LLM 理解偏差大
提示词中大量"自然语言 → 枚举值"映射规则（第67行: `"第30条"→"30"`、第135行: `"第二百六十六条"→"266"`）。LLM 需要**从中文自然语言推理出精确的枚举值**，这是模型幻觉的高发区。当前 116 条解析 avg ~82 分的瓶颈就在此处。

### 痛点 3: 没有覆盖率验证机制
无法自动检查生成的提示词是否覆盖了本体定义的所有实体、字段、关系和枚举值。测试一条样本后只能人工检查JSON输出，「漏提取枚举值」只能在批量跑完后在结果中事后发现。

### 痛点 4: 提示词中 JSON Schema 与本体定义的双重维护
提示词从第153行到第266行包含了一个**手写的完整 JSON 输出模板**。这个模板的字段名、嵌套结构、枚举值列表直接对应（但不完全一致）本体 YAML 中的定义。二者必须在三个地方保持一致：（1）本体 YAML、（2）提示词的实体映射规则描述、（3）提示词的 JSON 输出模板。**三处维护 = 三倍出错概率**。

### 痛点 5: 字段映射规则分散且不一致
例如 `role_code` 在中英两个版本 YAML 中枚举数量就不同（v2 26个 vs zh.yaml 18个），而提示词中又有一套 28 个的自定义角色列表。`result_type` 在提示词中包含了刑事/民事/行政/执行/检察监督 5 个分类下的 20+ 个值，远超本体 YAML 中定义的 14 个。**事实上的「本体」已经分裂成三个相互不一致的副本**。

---

## 2. 方案设计

### 2.1 推荐方案: YAML 本体 → Python 渲染器 → 结构化 Prompt

**核心思路**: 将 `legal_ontology_v2.yaml` 作为单一事实源（Single Source of Truth），通过一个 Python 渲染引擎自动生成结构化的提取提示词。

```
┌─────────────────────────┐     ┌──────────────────────┐     ┌───────────────────────┐
│   legal_ontology_v2.yaml│  →  │ ontology_prompt_gen.py│  →  │  提取提示词 (结构化)    │
│   (单一事实源)            │     │ (渲染引擎 + 模板)     │     │   - JSON Schema 表格    │
│                         │     │                      │     │   - 枚举值对照表        │
│                         │     │                      │     │   - 映射规则模板        │
└─────────────────────────┘     └──────────────────────┘     └───────────────────────┘
                                        │                              │
                                        │  → coverage_validate.py      │
                                        │    (验证覆盖率: 全部枚举值    │
                                        │     是否在渲染结果中出现)     │
                                        └──────────────────────────────┘
```

**渲染输出结构**: 不再用自然语言描述"第30条→30"，而是直接输出**表格 + JSON Schema**：

```markdown
## 枚举值约束（自动生成）
| 字段路径 | 枚举值列表 |
|---|---|
| guiding_case.binding_force | mandatory, persuasive, reference |
| case_type.category | civil, criminal, administrative, ip, execution, state_compensation |
| legal_subjects[].roles[].role_code | plaintiff, defendant, ..., class_representative |
| evidence[].evidence_type | documentary, physical, ..., inspection_record |

## 输出 JSON Schema（自动生成）
```json
{
  "guiding_case": {
    "binding_force": {"$enum": ["mandatory", "persuasive", "reference"]},
    ...
  },
  "court_cases": [...]
}
```

### 2.2 备选方案对比

| 维度 | 方案 A: YAML → 渲染引擎（推荐） | 方案 B: JSON Schema 本体 + 动态System Prompt | 方案 C: 预编译 Jinja2 模板 |
|---|---|---|---|
| **实现成本** | 1个py文件 ~300行 | 需要先将YAML转JSON Schema，外加运行时拼接 | 最低，仅升级模板引擎 |
| **维护成本** | 仅维护YAML | YAML + JSON Schema 两套定义 | 模板与YAML仍可能不一致 |
| **精确度提升** | 高 — 枚举值以表格形式直接给LLM | 中 — 通过 `$enum` 约束可被LLM遵守 | 低 — 仍然是自然语言描述 |
| **可验证性** | 强 — 可写单元测试验证枚举全覆盖 | 中 — 需写额外验证脚本 | 弱 — 同现状 |
| **可迁移性** | 好 — 渲染器可输出多种格式（LangChain Tool Schema, Neo4j约束，JSON Schema等） | 中 — 仅输出JSON Schema | 差 — 仅输出特定格式文本 |
| **与现有管线兼容度** | 高 — 替换 `load_prompt()` 调用即可 | 中 — 需修改API调用方式 | 高 — 最小改动 |

**推荐理由**: 方案 A 在「改一次本体，全管线同步」这个核心目标上胜出，同时提供了最好的可验证性和可扩展性。

---

## 3. 具体实现

### 3.1 文件路径建议

```
ontology/
├── schemas/
│   ├── legal_ontology_v2.yaml        # ← 单一事实源（不变）
│   └── legal_ontology_v2.zh.yaml     # ← 中英双语版（可保留，只做同步验证）
├── prompts/
│   ├── guiding_case_ontology_aligned_v3.txt  # ← 废弃，改为自动生成
│   └── templates/
│       ├── extraction_header.md.j2    # ← 核心原则、任务描述（静态模板）
│       ├── extraction_rules.yaml      # ← 映射规则（如 article 中文化解析规则）
│       └── coverage_whitelist.yaml    # ← 允许不一致的白名单（迁移期使用）
└── generators/
    ├── __init__.py
    ├── ontology_reader.py             # ← 读取并解析 YAML 本体
    ├── prompt_renderer.py             # ← 渲染引擎核心
    └── coverage_validator.py          # ← 覆盖率验证器

scripts/
├── parse_guiding_cases_llm_v2.py     # ← 修改：从自动生成提示词加载
└── generate_prompt.py                 # ← CLI入口：本体变动后一键生成
```

### 3.2 关键函数签名与流程

#### `ontology_reader.py` — 本体读取层

```python
def load_ontology(path: str) -> OntologySchema:
    """从 YAML 加载本体，返回结构化的 OntologySchema 对象
       OntologySchema = {
           entities: Dict[str, EntityDef],    # 实体名 → 定义
           relations: Dict[str, RelationDef],
           constraints: List[ConstraintDef],
           engineering: Dict
       }
    """

def get_entity_fields(entity_name: str) -> EntityFieldInfo:
    """返回一个实体的所有字段（required + optional），
       每个字段标注：type, enum_values (如有), description
    """

def get_all_enum_tables() -> Dict[str, List[str]]:
    """聚合所有实体的所有枚举字段，返回 {field_path: [values]} 
       例如: {"guiding_case.binding_force": ["mandatory","persuasive","reference"]}
    """
```

#### `prompt_renderer.py` — 渲染引擎

```python
def render_extraction_prompt(
    ontology: OntologySchema,
    header_template_path: str,
    rules_path: str = None,
    output_format: str = "markdown"
) -> str:
    """核心函数：从本体自动生成完整提取提示词
       1. 加载 header 静态模板
       2. 调用 render_entity_mapping_table() 生成实体字段表
       3. 调用 render_enum_reference() 生成枚举值表
       4. 调用 render_json_schema() 生成 JSON 输出模板
       5. 拼接返回
    """

def render_entity_mapping_table(ontology) -> str:
    """为每个实体渲染字段映射表（markdown表格）"""

def render_enum_reference(ontology) -> str:
    """渲染枚举值参考表（字段路径 | 允许值 | 中文说明）"""

def render_json_schema(ontology) -> str:
    """自动生成 JSON Schema 输出模板
       - 用 Pydantic 或纯 dict 构造
       - 枚举值直接在 schema 中标注
       - 可选字段标注注释
    """
```

#### `coverage_validator.py` — 覆盖率验证

```python
def validate_prompt_coverage(
    ontology: OntologySchema,
    generated_prompt: str
) -> ValidationReport:
    """验证生成的提示词是否覆盖了本体定义的所有：
       - 实体类型（所有 entity name 出现在提示词中）
       - 关系
       - 枚举字段的全部取值（每个枚举值都在提示词中有对应）
       返回 ValidationReport：{passed: bool, missing: List[str]}
    """

def validate_against_sample(
    ontology: OntologySchema,
    sample_text: str,
    llm_response: dict
) -> CoverageReport:
    """对一条 LLM 解析结果执行覆盖率检查：
       - 枚举值是否全部在 LLM 输出中出现（至少一次）
       - 必要字段是否全部提取
       - 输出结构是否符合 Schema
    """
```

#### 生成流程

```python
# CLI: python scripts/generate_prompt.py
def main():
    ontology = load_ontology("ontology/schemas/legal_ontology_v2.yaml")
    prompt = render_extraction_prompt(ontology, 
                                       header_template_path="ontology/prompts/templates/extraction_header.md.j2")
    report = validate_prompt_coverage(ontology, prompt)
    if not report.passed:
        print(f"警告: 以下枚举值未覆盖: {report.missing}")
    with open("ontology/prompts/auto_generated_v{version}.txt", "w") as f:
        f.write(prompt)
```

### 3.3 枚举值渲染核心逻辑（示意）

从 YAML 中读取 `role_code_enum: [plaintiff, ... , class_representative]` 后，渲染为：

```markdown
| 字段 | 允许值 | 中文映射说明 |
|---|---|---|
| `legal_subjects[].roles[].role_code` | `plaintiff`, `defendant`, ..., `class_representative` | 原告→plaintiff, 被告→defendant, ... |
```

**收益**: LLM 看到的不是"请把中文角色名映射到枚举值"（自然语言 → 模糊推理），而是**一张明确的映射表**（字符串匹配 → 查找）。这对 LLM 的准确率提升是立竿见影的。

---

## 4. 迁移路径 — 分 3 步，每步 1-2 天

### Phase 1: 基础设施搭建（Day 1-2）
1. ✅ 创建 `ontology/generators/` 目录和三核心文件
2. 实现 `ontology_reader.py`：解析 YAML，提取实体/字段/枚举/关系
3. 实现 `prompt_renderer.py` 的 `render_enum_reference()` — 这是最低成本最高收益的功能
4. 实现 `generate_prompt.py` CLI 入口
5. **交付**: `python scripts/generate_prompt.py --enum-only` 可输出枚举值参考表

### Phase 2: 核心功能上线（Day 3-4）
1. 实现 `render_json_schema()` — 自动从本体生成 JSON 输出模板
2. 实现 `render_entity_mapping_table()` — 实体字段映射表自动生成
3. 实现 `coverage_validator.py` — 提示词覆盖率检查
4. **交付**: 完整提示词自动生成，替换 `guiding_case_ontology_aligned_v3.txt`

### Phase 3: 集成与验证（Day 5-6）
1. 修改 `parse_guiding_cases_llm_v2.py` — 将 `load_prompt()` 替换为从 `generate_prompt()` 自动加载
2. 实现 `validate_against_sample()` — 对一条测试 case 做全覆盖检查
3. 跑 20 条对比测试：旧提示词 vs 自动生成提示词，对比 avg score
4. **交付**: 全管线跑通，对比报告输出

---

## 5. 预期收益

### 量化预估

| 指标 | 现状 | 预期 | 估算依据 |
|---|---|---|---|
| **本体变更同步时间** | 1次变更 30-60 分钟手写同步 | 10 秒自动生成 | 人工 vs `generate_prompt.py` |
| **枚举值提取准确率** | ~75% (116条 avg 82分中的主要丢分项) | 提升 8-12% | 枚举值从「自然语言推理」改为「查表匹配」 |
| **提示词维护成本** | 每次本体变更需改2-3处文件 | 仅改 YAML 1 处 | 手写/渲染/验证三处 → 单一事实源 |
| **新实体上线时间** | 2-3天（改YAML+改提示词+测试） | 0.5天（改YAML+自动生成+验证） | 去除了手动同步和手动测试环节 |
| **提示词覆盖率验证** | 无 | 100% 枚举值覆盖率自动检查 | `coverage_validator.py` 拦截遗漏 |
| **批量解析通过率** | ~75% (116/600) | 目标 90%+ | 更精确的枚举值 + 更少的提示词幻觉 |

### 非量化收益

- **知识传递**: 新开发者只需要理解 YAML 本体格式，不需要记忆提示词模板结构
- **多输出格式**: 渲染引擎可扩展输出 JSON Schema（用于 LangChain Tool）、图约束（用于 Neo4j）、API Schema（用于数据校验）
- **本体版本管理**: YAML 的每一次变更都对应一个可追踪的提示词版本，方便回滚和 A/B 测试

---

## 附录: 技术决策记录

1. **不使用 Jinja2/gotemplate 等模板引擎**: 文中的 `.j2` 仅用于标记静态头部模板的占位符格式。核心渲染逻辑在 Python 中完成，因为需要做 `OntologySchema` 的结构化遍历、枚举聚合、字段路径拼接等逻辑，模板引擎无法胜任。
2. **不引入 Pydantic**: 避免依赖膨胀。直接用 `dict` + `TypedDict` 做结构定义。
3. **渲染器输出不包含原始案件文本**: `{case_text}` 的注入由管线脚本（`parse_guiding_cases_llm_v2.py`）在运行时完成，渲染器只生成指令+Schema部分。
