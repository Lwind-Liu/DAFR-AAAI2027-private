# R2 — Official Review (`Nr4b`) / 正式审稿意见

**Title:** Review / 审稿意见  
**Posted:** 10 Aug 2026, 04:37  
**Modified:** 25 Sep 2026, 05:23  
**Rating:** 5 — Marginally below acceptance threshold / 略低于接收门槛  
**Confidence:** 4 — The reviewer is confident but not absolutely certain that the evaluation is correct / 审稿人较有信心，但不能完全确定评估是正确的

## R2.0 Paper Summary / 论文总结

### Original English

This paper proposes DAFR, which maps each proposed action and its evidence into interpretable coordinates before every tool call, then constructs state dependent halfspaces and joint risk regions to decide feasibility. Putting authorization, grounding, and effect support at the execution boundary is an important problem, and signed margin feedback could be interpretable.

The claimed geometric contribution is also not adequately isolated. The role map, deterministic semantic lifting, policy templates, active halfspaces, and joint risk regions are all authored by the paper. It does not explain who writes these rules, how much work is required per benchmark, how role ambiguity or new tool fields are handled, or how much changes across suites. The results may therefore primarily reflect a carefully designed symbolic policy rather than the dynamic geometric representation. The paper should report policy authoring cost, frozen policy transfer across domains, and equivalent rule based, flat threshold, and no geometry controls using the same rule set.

Zero observed attack success across 585 attacked AgentDojo cases and 204 ASB cases for selected settings does not mean that the true attack success rate is zero. Denominators by attack category, suite, and model, confidence intervals, and adaptive attacker tests are not adequately reported. Because DAFR conditions on tool, task, and state relations, an attacker aware of its policy templates may construct a call that superficially satisfies provenance and authorization. Static attacks in the existing benchmarks do not validate this threat model.

The motivation for safe execution and the attempt to expose why constraints fire is interesting. The reduction in observed ASR while retaining utility on two benchmarks is also empirically meaningful. But the current work combines manual safety policy, representation design, and geometric decision making in a way the experiments cannot separate.

### 中文翻译

本文提出 DAFR：在每次工具调用之前，将拟执行动作及其证据映射为可解释坐标，随后构造依赖状态的半空间和联合风险区域来判断可行性。将授权、事实依据和作用支持放在执行边界进行检查，是一个重要问题；带符号间隔反馈也可能具有可解释性。

但论文所声称的几何贡献并未得到充分隔离。角色映射、确定性语义提升、策略模板、激活半空间和联合风险区域均由论文作者设计。论文没有解释由谁编写这些规则、每个基准需要多少工作、如何处理角色歧义或新工具字段，以及不同工具套件之间需要做多大改动。因此，实验结果可能主要反映的是精心设计的符号策略，而不是动态几何表示。论文应报告策略编写成本、冻结策略的跨域迁移情况，并在使用同一套规则的条件下比较等价的规则方法、平坦阈值方法和无几何方法。

在选定设置下，585 个 AgentDojo 攻击案例和 204 个 ASB 案例中观察到零次攻击成功，并不意味着真实攻击成功率为零。论文没有充分报告按攻击类别、工具套件和模型划分的分母、置信区间以及自适应攻击测试。由于 DAFR 依赖工具、任务与状态之间的关系，了解其策略模板的攻击者可能构造表面上满足来源和授权条件的调用。现有基准中的静态攻击不能验证这一威胁模型。

安全执行的研究动机，以及尝试揭示约束为何触发的做法都很有意思。在两个基准上降低观察到的 ASR，同时保留效用，也具有实证意义。然而，当前工作把人工安全策略、表示设计和几何决策结合在一起，现有实验无法将三者的作用分离。

## R2.S Strengths / 优点

### Original English

Placing the safety decision before an irreversible tool call, rather than relying only on planner self restraint, is an important system design. Decomposing the decision into authorization, grounding, and effect support makes failures easier to inspect than a single risk score, and signed margins may help identify the active constraint.

### 中文翻译

在不可逆的工具调用发生之前进行安全决策，而不是只依赖规划器的自我约束，是一种重要的系统设计。把决策分解为授权、事实依据和作用支持，比使用单一风险分数更便于检查失败原因；带符号间隔也可能有助于识别当前起作用的约束。

## R2.1 Policy authoring and geometric isolation / 策略编写与几何贡献隔离

### Original English

The claimed geometric contribution is also not adequately isolated. The role map, deterministic semantic lifting, policy templates, active halfspaces, and joint risk regions are all authored by the paper. It does not explain who writes these rules, how much work is required per benchmark, how role ambiguity or new tool fields are handled, or how much changes across suites. The results may therefore primarily reflect a carefully designed symbolic policy rather than the dynamic geometric representation. The paper should report policy authoring cost, frozen policy transfer across domains, and equivalent rule based, flat threshold, and no geometry controls using the same rule set.

### 中文翻译

论文声称的几何贡献没有得到充分隔离。角色映射、确定性语义提升、策略模板、激活半空间和联合风险区域均由论文作者设计。论文没有说明由谁编写这些规则、每个基准需要多少工作、如何处理角色歧义或新工具字段，以及不同套件之间需要改动多少。因此，结果可能主要来自精心设计的符号策略，而非动态几何表示。论文应报告策略编写成本、冻结策略的跨域迁移情况，并在相同规则集下加入等价规则方法、平坦阈值方法和无几何方法作为对照。

## R2.2 Zero-event uncertainty and adaptive threats / 零事件不确定性与自适应威胁

### Original English

Zero observed attack success across 585 attacked AgentDojo cases and 204 ASB cases for selected settings does not mean that the true attack success rate is zero. Denominators by attack category, suite, and model, confidence intervals, and adaptive attacker tests are not adequately reported. Because DAFR conditions on tool, task, and state relations, an attacker aware of its policy templates may construct a call that superficially satisfies provenance and authorization. Static attacks in the existing benchmarks do not validate this threat model.

### 中文翻译

在选定设置下，585 个 AgentDojo 攻击案例和 204 个 ASB 案例中观察到零次攻击成功，并不意味着真实攻击成功率为零。论文未充分报告按攻击类别、工具套件和模型划分的分母、置信区间以及自适应攻击测试。由于 DAFR 根据工具、任务和状态关系作出判断，了解策略模板的攻击者可能构造表面上满足来源与授权条件的调用。现有基准中的静态攻击无法验证这一威胁模型。

## R2.J Justification of Recommendation / 推荐理由

### Original English

The motivation for safe execution and the attempt to expose why constraints fire is interesting. The reduction in observed ASR while retaining utility on two benchmarks is also empirically meaningful. But the current work combines manual safety policy, representation design, and geometric decision making in a way the experiments cannot separate.

### 中文翻译

安全执行的研究动机，以及尝试解释约束为何触发，都很有意思。在两个基准上降低观察到的 ASR、同时保留效用，也具有实证意义。但当前工作把人工安全策略、表示设计和几何决策结合在一起，现有实验无法区分它们各自的贡献。

## R2.F Specific Points of Feedback for Rebuttal / 供答辩回应的具体问题

### Original English

1. Quantify the manual policy authoring required for AgentDojo and ASB and state exactly which parts of the role map, semantic lifting, and policy templates change between the two suites.
2. Clarify whether the no geometric constraints ablation retains exactly the same evidence projection, manual rules, feedback, and execution permissions, and whether each baseline receives the same trusted source tags and task state.
3. Report denominators and zero event intervals by attack family, planner, and action type for the existing 585 and 204 attacked cases, and indicate whether any risky calls were accepted close to the decision boundary.

### 中文翻译

1. 量化 AgentDojo 和 ASB 所需的人工策略编写工作，并明确说明角色映射、语义提升和策略模板中哪些部分在两个套件之间发生了变化。
2. 说明“无几何约束”消融是否严格保留了相同的证据投影、人工规则、反馈和执行权限，以及各基线是否接收了相同的可信来源标签和任务状态。
3. 针对现有 585 个和 204 个攻击案例，按攻击类别、规划器和动作类型报告分母与零事件区间，并说明是否有风险调用在接近决策边界时被接受。

