# 深度思考 (Deep Thinking) 接力推理架构设计方案

## 一、 背景与痛点分析

当前“知识发现”面板提供了 5 种预设的深度思考类型：法条适用分析、构成要件分析、证据采信分析、裁判尺度分析、诉求抗辩分析。
然而，在当前的单点调用模式下存在以下痛点：
1. **上下文割裂**：每种分析都是独立基于基础解析图谱（`json_result`）发起的。例如，“构成要件分析”无法看到“证据采信分析”中刚刚建立的证据印证关系。
2. **ID 冲突与不一致**：因为是分别生成，不同分析任务可能会对同一个案件事实生成不同 ID 的补充节点（如 `virtual_fact_1`），导致合并到主图谱时出现逻辑冗余或连边失败。
3. **资源浪费**：如果缺乏依赖控制，大模型会在每个分析任务中重复梳理案件事实，消耗大量 Token。

## 二、 核心思想：接力推理 (Relay Reasoning)

将 5 个深度思考任务串联成一条有向无环图 (DAG) 逻辑流。
**核心机制**：前一个节点的输出结果（推理结论与图谱补充 JSON）必须被持久化（或暂存在上下文中），并作为后一个节点 Prompt 的 `<前置推理结果>` 输入。这保证了后续任务可以直接引用前面已经生成的节点 ID，实现本体论知识的完美接力与嵌套。

## 三、 逻辑先后顺序与 I/O 设计

根据法律人审查案件的常规思维（从事实到证据，从证据到定性，从定性到量刑），最佳的接力顺序设计如下：

### 环节 1：证据采信分析 (Evidence & Admissibility Analysis)
*   **定位**：事实查明的基石，构建案件的“证据网络”。
*   **输入 (Input)**：
    *   基础解析图谱 (`json_result`)：包含原始提取的 `Fact`, `Evidence`, `Person`。
*   **处理逻辑**：
    *   寻找证据与证据之间的关系（`corroborates` 印证 / `contradicts` 矛盾）。
    *   梳理证据链条 (`EvidenceChain`)。
    *   判断证据是否被法庭采信 (`JudicialAssessment`)。
*   **输出 (Output)**：
    *   新增实体：`EvidenceChain`, `JudicialAssessment`。
    *   新增关系：证据间的相互印证/矛盾边。

### 环节 2：诉求抗辩分析 (Claim & Defense Analysis)
*   **定位**：明确争议焦点，构建控辩对抗网络。
*   **输入 (Input)**：
    *   基础图谱 + **环节1的输出（证据采信网络）**。
*   **处理逻辑**：
    *   将原告/公诉人的指控 (`LitigationClaim`) 与被告/辩护人的抗辩 (`ArgumentPoint`) 对应起来。
    *   结合环节1的证据链，指出各方的诉求/抗辩分别有什么证据支撑。
    *   归纳出本案的核心争议焦点 (`DisputeFocus`)。
*   **输出 (Output)**：
    *   新增实体：`ArgumentPoint`, `DisputeFocus`。
    *   新增关系：`opposes` (对抗边), `supports` (支撑边)。

### 环节 3：构成要件分析 (Constitutive Elements Analysis)
*   **定位**：法律定性分析，将事实映射到法律概念。
*   **输入 (Input)**：
    *   基础图谱 + 环节1(证据网络) + **环节2(争议焦点网络)**。
*   **处理逻辑**：
    *   针对提取出的事实和焦点，分析其是否符合特定罪名/案由的构成要件（如：主体要件、主观要件、客观行为）。
    *   必须引用前置生成的 `Fact` 和 `EvidenceChain` ID，来说明“某要件已满足”。
*   **输出 (Output)**：
    *   新增实体：`LegalProvisionElement` (法条元素/要件)。
    *   新增关系：`matches_element` (事实符合要件边)。

### 环节 4：法条适用分析 (Legal Application & Interpretation)
*   **定位**：法律寻法与法理阐释。
*   **输入 (Input)**：
    *   基础图谱 + 环节1 + 环节2 + **环节3(要件网络)**。
*   **处理逻辑**：
    *   根据环节3确定的构成要件，寻找并匹配具体的法律条文 (`LegalProvision`)。
    *   针对本案争议焦点，提供法官对该法条的特定解释 (`LegalInterpretation`)。
*   **输出 (Output)**：
    *   新增实体：`LegalInterpretation`, 补充缺失的 `LegalProvision`。
    *   新增关系：`element_of_provision` (要件从属法条边)。

### 环节 5：裁判尺度分析 (Sentencing & Judgment Scale Analysis)
*   **定位**：最终裁决的合理性与量刑考量。
*   **输入 (Input)**：
    *   包含前 4 个环节所有成果的完整上下文图谱。
*   **处理逻辑**：
    *   总结全案，提取影响最终判决的法定/酌定量刑情节 (`SentencingCircumstance`)。
    *   例如：自首、立功、退赃、认罪认罚、主从犯等。
    *   将这些情节与最终的裁判结果 (`JudgmentResult`) 关联。
*   **输出 (Output)**：
    *   新增实体：`SentencingCircumstance`。
    *   新增关系：`mitigates` (减轻), `aggravates` (加重)。

## 四、 架构优化建议

1. **状态流转 (State Context)**：
   不需要一次性跑完 5 个环节，但前端的 `store` 应该维护一个 `DeepThinkingContext` 对象。当用户点击“构成要件分析”时，前端会自动将当前已合并的图谱（包含之前合并过的“证据采信”子图）作为 Payload 发给后端，实现隐式的“接力”。
2. **多智能体 (Multi-Agent) 协同**：
   未来在 LangGraph 架构下，可以将这 5 个环节设计为由 Supervisor 路由给 `EvidenceAnalyzer`, `DefenseAnalyzer`, `ElementAnalyzer`, `LawApplicator`, `SentencingJudge` 这 5 个不同的专职 Agent 顺序执行，实现全自动的案件深度解剖。
3. **ID 生成规范**：
   在 Prompt 中强制规定生成虚拟节点的 ID 规范（如 `evidence_chain_xxx`, `focus_xxx`），严禁大模型生成与基础解析可能重叠的 ID。