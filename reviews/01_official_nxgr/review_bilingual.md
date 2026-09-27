# R1 — Official Review (`nXgR`) / 正式审稿意见

**Title:** An Interesting Execution-Layer Defense but Heavy Manual Configuration  
**中文标题：** 一个有趣的执行层防御方案，但人工配置负担较重  
**Posted:** 28 Aug 2026, 22:58  
**Modified:** 25 Sep 2026, 05:23  
**Rating:** 6 — Marginally above acceptance threshold / 略高于接收门槛  
**Confidence:** 4 — The reviewer is confident but not absolutely certain that the evaluation is correct / 审稿人较有信心，但不能完全确定评估是正确的

## R1.0 Paper Summary / 论文总结

### Original English

This paper addresses the execution-time safety of tool calls in LLM agents. A tool call may lack the evidence, authorization, or state support needed for execution. The authors propose DAFR, which maps each call and its supporting evidence to an action-evidence point. It then applies dynamic geometric constraints, specifically policy-defined halfspaces and joint-risk regions, to form a feasible region. Calls inside the region are executed, while calls outside are blocked or returned with feedback. The authors validate their method on AgentDojo and the Agent Security Benchmark.

### 中文翻译

本文研究大语言模型智能体中工具调用的执行时安全问题。某个工具调用可能缺少执行所需的证据、授权或状态支持。作者提出 DAFR，将每个调用及其支撑证据映射为一个“动作—证据”点，随后应用动态几何约束，具体包括由策略定义的半空间和联合风险区域，以构建可行域。位于可行域内的调用会被执行，而位于域外的调用则会被阻止或返回反馈。作者在 AgentDojo 和 Agent Security Benchmark 上验证了该方法。

## R1.S Strengths / 优点

### Original English

1. The problem formulation is well motivated and addresses a timely research direction.
2. The focus on relations among action, evidence, and state fills the gap in prior runtime defenses.
3. The authors evaluate their method on two established benchmarks, AgentDojo and Agent Security Benchmark, covering multiple tool suites and planner models. The experimental design includes comparisons with several representative defenses and ablations of key components.

### 中文翻译

1. 问题定义具有充分动机，且面向一个具有时效性的研究方向。
2. 方法聚焦动作、证据和状态之间的关系，填补了以往运行时防御方法中的空白。
3. 作者在 AgentDojo 和 Agent Security Benchmark 两个成熟基准上评估了该方法，覆盖多个工具套件和规划模型。实验设计包含与若干代表性防御方法的比较，以及对关键组件的消融实验。

## R1.1 Manual configuration and scalability / 人工配置与可扩展性

### Original English

The method appears to require substantial manual configuration, but the cost is not quantified. The role maps are defined per tool field. The policy templates have fixed coefficients and are specified before evaluation. This implies hand-written rules. The paper also does not state how the semantic lifting function and evidence projection rules are built. The Limitations section says new tools can be integrated by mapping fields and effects to shared roles. However, the paper does not report how many roles, templates, or coefficients were needed for AgentDojo and ASB. This makes the practical scalability of DAFR hard to judge.

### 中文翻译

该方法似乎需要大量人工配置，但论文没有量化这部分成本。角色映射是针对每个工具字段定义的；策略模板使用固定系数，并在评估前确定，这意味着其中包含手写规则。论文也未说明语义提升函数和证据投影规则是如何构建的。“局限性”部分称，可以通过将新工具的字段和作用映射到共享角色来完成集成。然而，论文没有报告 AgentDojo 和 ASB 分别需要多少角色、模板或系数，因此难以判断 DAFR 在实践中的可扩展性。

## R1.2 Geometry versus equivalent rules / 几何形式与等价规则

### Original English

The geometric machinery may be more formalism than mechanism. The underlying decision is a set of threshold checks over grounding, authorization, prerequisite, and risk scores. The checks could be implemented as plain rule-based predicates without any halfspace or norm formulation. The ablation section does not replace them with equivalent non-geometric predicates. Therefore, the paper does not show that the geometric machinery itself contributes to the results.

### 中文翻译

几何机制可能更像是一种形式化表达，而非真正发挥作用的机制。其底层决策实际上是对事实依据、授权、前置条件和风险分数进行一组阈值检查。这些检查可以用普通的基于规则的谓词实现，而不需要半空间或范数形式。消融实验也没有用等价的非几何谓词来替代这些约束。因此，论文尚未证明几何机制本身对结果有所贡献。

## R1.3 Adaptive attacks / 自适应攻击

### Original English

Lacks of evaluation against adaptive attacks. All reported results use fixed benchmark cases. My concern is whether an attacker who knows DAFR can craft observations to manipulate the evidence projection or source labels. The paper neither tests nor discusses such attacks.

### 中文翻译

论文缺少针对自适应攻击的评估。所有已报告结果均使用固定的基准案例。我担心了解 DAFR 的攻击者可能构造观测，以操纵证据投影或来源标签。论文既没有测试也没有讨论这类攻击。

## R1.4 Missing implementation details and sensitivity / 实现细节与敏感性缺失

### Original English

Important implementation details are missing from the main text. The paper does not provide the content of the coordinate blocks, the actual policy templates, or the coefficient values. It also omits the revision-path rule that decides between Clarify and Block. A reader cannot assess how sensitive the results are to these design choices.

### 中文翻译

正文缺少重要的实现细节。论文没有给出坐标分块的具体内容、实际使用的策略模板或系数取值，也省略了在 Clarify 与 Block 之间作出选择的修订路径规则。因此，读者无法评估结果对这些设计选择的敏感程度。

## R1.J Justification of Recommendation / 推荐理由

### Original English

The paper formulates an interesting problem in LLM agent execution safety, and the proposed DAFR framework is internally consistent with solid experimental validation across two benchmarks. The results demonstrate competitive security-utility trade-offs among existing defenses.

Regard to the weakness, I look forward to the authors' responses to the questions raised above.

### 中文翻译

论文围绕大语言模型智能体执行安全提出了一个有趣的问题；所提出的 DAFR 框架内部逻辑一致，并在两个基准上进行了扎实的实验验证。结果表明，相比现有防御方法，该方法具有有竞争力的安全性—效用权衡。

关于上述不足，我期待作者对前述问题作出回应。

## R1.F Specific Points of Feedback for Rebuttal / 供答辩回应的具体问题

### Original English

1. Quantify the manual configuration effort required for AgentDojo and ASB, including the number of roles, templates, and coefficients, as well as the time needed to integrate a new tool.
2. Clarify whether the geometric formulation provides any advantage over a plain rule-based implementation of the same checks.
3. Discuss whether DAFR remains effective against adaptive attackers who know the defense and can craft observations to manipulate evidence projection or source labels.
4. Report the sensitivity of results to the policy template coefficients, which were fixed before evaluation.

### 中文翻译

1. 量化 AgentDojo 和 ASB 所需的人工配置工作，包括角色、模板和系数的数量，以及集成一个新工具所需的时间。
2. 说明几何形式相对于实现相同检查的普通规则系统是否具有优势。
3. 讨论当自适应攻击者了解该防御方法，并能构造观测来操纵证据投影或来源标签时，DAFR 是否仍然有效。
4. 报告结果对策略模板系数的敏感性；这些系数是在评估前固定的。

