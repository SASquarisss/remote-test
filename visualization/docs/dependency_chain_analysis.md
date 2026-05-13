# 法律知识图谱系统依赖链分析

## 核心数据流

```
legal_ontology_v2.yaml (本体定义源)
  │
  ├─→ ontology/ontology_data_gen.py → visualization/ontology_data.js (前端数据)
  │
  ├─→ ontology/generators/ontology_reader.py (本体读取器)
  │     │
  │     └─→ ontology/generators/prompt_renderer.py (自动生成prompt)
  │           │
  │           ├─→ EXTRACTION_ENTITY_CONFIG (字段白名单)
  │           │     手动维护，定义了LLM提取哪些实体和字段
  │           │
  │           ├─→ ENUM_ZH_MAP (枚举值中文映射)
  │           │     手动维护
  │           │
  │           ├─→ render_json_schema() → JSON Schema模板
  │           └─→ render_extraction_prompt() → 组装完整prompt
  │                 │
  │                 └─→ scripts/generate_prompt.py (CLI入口)
  │                       │
  │                       ├─→ --output → scripts/prompts/guiding_case_ontology_aligned_v3.txt
  │                       │                   ← 这个文件被多处引用
  │                       └─→ --few-shot 自动注入few-shot样本
  │
  ├─→ scripts/prompts/guiding_case_ontology_aligned_v3.txt (最终prompt文件)
  │     ← 被以下位置引用:
  │     1. backend/parser.py:17  (解析终端，直接读取)
  │     2. extraction/llm_extractors/guiding_case_extractor.py:39
  │     3. extraction/llm_extractors/guiding_case_extractor_v3.py:34
  │     4. scripts/compare3_test.py:50
  │     5. scripts/fewshot_cmp_test.py:107
  │
  ├─→ backend/parser.py (解析管线)
  │     ├─→ parse_text(): 读取prompt → 调LLM → enforce → kg_convert
  │     ├─→ kg_convert(): 将LLM输出转vis-network nodes/edges
  │     │     ← 需要消费: evidence.*, facts[], dispute_focuses[], relations[]
  │     └─→ evaluate_output(): 质量评估(score+issues)
  │           ← 需要评估新字段的完成度
  │
  └─→ backend/evaluator.py (本体论评估，LLM二次调用)
        ← 与prompt内容耦合：发送schema summary给LLM判断提取质量

visualization/ontology_v2.2.html (前端)
  ├─→ renderTermVis(): 渲染解析图
  │     ← 需要处理新的节点类型(Fact, DisputeFocus)
  ├─→ renderParseNode(): 右侧面板信息展示
  │     ← evidence中admission_status等需要特殊渲染
  └─→ quality_analyzer (前端解析质量分析)
        ← 需更新评估规则覆盖新字段

## 修改影响面

修改 prompt 需要同时修改以下位置的逻辑：

1. **prompt_renderer.py** (7处):
   - ENUM_ZH_MAP: 添加新枚举值中文映射
   - EXTRACTION_ENTITY_CONFIG: 添加/修改实体字段白名单
   - render_json_schema(): 添加新实体的JSON Schema
   - HEADER_TEMPLATE: 核心原则（如新增关系数组输出要求）
   - render_extraction_prompt() 或它的组装逻辑

2. **parser.py** (3处):
   - kg_convert(): 消费新LLM输出字段（evidence.*, facts, dispute_focuses, relations）
   - evaluate_output(): 评估新字段完成度
   - fill_empty_provision_content(): 如有新字段默认值逻辑

3. **前端** (2处):
   - ontology_v2.2.html:
     - 新增Fact/DisputeFocus的ENTITY_STYLES、ZONE_MAP、Y_LEVEL_MAP等
     - 解析图节点类型映射
     - 证据采信状态卡片展示(renderParseNode)
   - backend/quality_analyzer.py 或前端JS:
     - 解析质量分析中增加对facts/dispute_focuses/relations的评估

4. **generate_prompt.py**:
   - few-shot选取逻辑：如果新增实体类型，few-shot评分公式可能需要调整
   - 验证逻辑(--validate): 需检查新字段
