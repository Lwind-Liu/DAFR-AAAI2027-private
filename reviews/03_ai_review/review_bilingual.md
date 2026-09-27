# AI Review / AI 审稿意见

**Source:** AI Reviewer  
**Posted:** 27 Jul 2026, 19:59  
**Modified:** 25 Sep 2026, 05:23  
**Paper title:** From Semantics to Execution: Dynamic Geometric Constraints for Tool-Action Feasibility  
**论文标题：** 从语义到执行：面向工具动作可行性的动态几何约束

> The supplied screenshots do not show an AI-review rating or confidence field. / 所提供截图未显示 AI 审稿的评分或置信度。

## AI.0 Synopsis of the paper / 论文概要

### Original English

This paper studies execution-time defenses for tool-using agents whose schema-valid calls may nevertheless be induced by untrusted content or lack authorization. DAFR maps calls and source-tagged evidence into interpretable coordinates, compiles state-dependent policy constraints into a feasible region, and uses constraint margins for execution decisions and revision feedback. Experiments on two agent-security benchmarks examine its security-utility trade-off across multiple planners.

### 中文翻译

本文研究工具使用型智能体的执行时防御：即使工具调用符合模式要求，也仍可能受到不可信内容诱导或缺少授权。DAFR 将调用和带来源标签的证据映射为可解释坐标，把依赖状态的策略约束编译成可行域，并利用约束间隔作出执行决策和提供修订反馈。论文在两个智能体安全基准上开展实验，考察该方法在多个规划器上的安全性—效用权衡。

## AI.1 Summary of Review / 审稿总结

### Original English

The paper addresses the consequential problem of grounding concrete tool effects in trusted evidence, authorization, and runtime state. Its technical contribution is a policy-compilation framework combining semantic coordinates, convex constraints, and margin-based feedback. The principal validity threat is that the security-critical lifting, evidence classification, constraint activation, and policy construction are not operationally specified, so the zero observed attack-success results cannot be separated from possible oracle labeling or benchmark-specific policy engineering. Novelty over recent dependency-graph, verifiable-policy, and verify-before-commit defenses also requires sharper differentiation. The experiments support a narrow empirical security claim, but not broader claims of general security, explanation correctness, or reliable tool use.

### 中文翻译

论文研究了一个后果重大的问题：如何让具体工具作用建立在可信证据、授权和运行时状态之上。其技术贡献是一个策略编译框架，将语义坐标、凸约束和基于间隔的反馈结合起来。主要有效性威胁在于，与安全密切相关的语义提升、证据分类、约束激活和策略构建都缺少可操作的说明，因此观察到的零攻击成功结果无法与潜在的“预言机式”标注或面向特定基准的策略工程区分开来。论文还需要更清晰地区分自身与近期基于依赖图、可验证策略及“提交前验证”的防御方法之间的创新性。现有实验支持一个范围较窄的实证安全结论，但不足以支持关于通用安全性、解释正确性或可靠工具使用的更宽泛主张。

## AI.S Strengths / 优点

### Original English

- The problem formulation makes effect-bearing arguments—not merely tool names or schema validity—the unit of authorization. The customer-record example in the Introduction and the role map in Equation (5) distinguish a verified identifier used for a requested update from an untrusted disclosure destination, directly addressing attacks in which both calls are well formed.
- The constraint language accommodates both conjunctive requirements and coupled risks. Equations (7)–(13) combine critical-argument grounding, halfspaces, convex joint-risk regions, and signed margins within one decision rule, allowing the execution decision and its reported limiting relation to share a common representation.
- The evaluation spans both planner and benchmark variation. Figure 2 covers three planners on AgentDojo, Table 1 uses a distinct benchmark protocol, and Table 2 examines the security and utility behavior of several component removals.

### 中文翻译

- 问题定义把承载工具作用的参数——而不仅仅是工具名称或模式合法性——作为授权单元。引言中的客户记录示例和公式（5）中的角色映射，区分了用于完成请求更新的已验证标识符与来自不可信来源的数据披露目的地，直接处理了两个调用在形式上都合法的攻击情形。
- 约束语言同时支持合取要求和耦合风险。公式（7）至（13）在同一决策规则中结合关键参数的事实依据、半空间、凸联合风险区域和带符号间隔，使执行决策及其报告的限制关系能够共享统一表示。
- 评估同时覆盖规划器差异和基准差异。图 2 展示了 AgentDojo 上的三个规划器；表 1 使用不同的基准协议；表 2 考察了移除若干组件后安全性和效用的变化。

## AI.W1 Security computation is underspecified / 安全计算定义不充分

### Original English

The central security computation is not specified sufficiently to assess the zero-ASR claim. Equations (4)–(9) leave the rules for *L*, *g*, *P*, *H_t*, and *K_t* undefined, including how *P* recognizes untrusted instructions, conflicts, and unsupported effects. Because these choices could encode benchmark annotations or attack patterns, the results do not distinguish a generic defense from benchmark-specific policy engineering; the main text needs representative rules, source-label assumptions, coefficients, activation logic, and the policy-development protocol.

### 中文翻译

论文没有充分定义核心安全计算，因此无法评估零 ASR 声明。公式（4）至（9）没有给出 *L*、*g*、*P*、*H_t* 和 *K_t* 的具体规则，包括 *P* 如何识别不可信指令、冲突和不受支持的作用。由于这些选择可能编码基准标注或攻击模式，现有结果无法区分通用防御与针对特定基准的策略工程；正文需要提供代表性规则、来源标签假设、系数、激活逻辑和策略开发流程。

## AI.W2 Novelty positioning is incomplete / 创新性定位不完整

### Original English

Novelty over recent execution-centric defenses is incomplete. Related Work cites ShieldAgent only as an explicit-policy method, although it compiles action rules into verifiable circuits (Chen et al., 2025); IPIGuard resolves unknown tool arguments from prior outputs through a dependency graph (An et al., 2025), and VIGIL addresses manipulated tool metadata and runtime feedback through verify-before-commit (Lin et al., 2026), yet neither is cited. These overlaps leave unclear which capability is created specifically by DAFR’s geometry.

### 中文翻译

论文没有完整阐明相对于近期执行中心型防御方法的创新性。相关工作仅把 ShieldAgent 作为显式策略方法引用，但它会把动作规则编译成可验证电路（Chen 等，2025）；IPIGuard 通过依赖图从先前输出中解析未知工具参数（An 等，2025）；VIGIL 则通过“提交前验证”处理被操纵的工具元数据和运行时反馈（Lin 等，2026），但后两者均未被引用。这些重叠使人难以判断究竟哪项能力是由 DAFR 的几何设计特有地创造出来的。

## AI.W3 Ablations do not isolate geometry / 消融实验未隔离几何贡献

### Original English

Table 2 does not isolate the contribution of the geometric formulation because its ablations are undefined. The paper does not state what representation remains without action–evidence lifting, what decision rule replaces geometric constraints, or whether “w/o Decision & Feedback” removes enforcement or only planner feedback. Consequently, the ASR increase from 0 to 16.7 percent cannot establish that geometry, rather than removal of the underlying policy checks, causes the security difference.

### 中文翻译

表 2 没有隔离几何形式的贡献，因为其中的消融设置未被明确定义。论文没有说明移除“动作—证据”提升后保留何种表示、用什么决策规则替代几何约束，也没有说明“w/o Decision & Feedback”移除的是强制执行机制还是仅移除规划器反馈。因此，ASR 从 0 上升到 16.7% 并不能证明安全性差异来自几何机制，而不是来自底层策略检查被移除。

## AI.W4 Uncertainty support is missing / 缺少不确定性分析

### Original English

Several comparative conclusions lack uncertainty support. Figure 2 provides no seeds, intervals, or paired tests even though DAFR’s advantage over the best displayed attack-utility baseline is only 2.2 points for DeepSeek and 2.1 for Claude, while displayed Claude ASRs span only 0 to 0.2 points; Table 1 similarly reports gains of 0.8 utility and 0.5 task-success points over Progent. These data establish observed outcomes, but not meaningful differences on these metrics.

### 中文翻译

若干比较结论缺少不确定性支持。图 2 没有给出随机种子、区间或配对检验，而 DAFR 相比图中最佳攻击效用基线，对 DeepSeek 的优势仅为 2.2 个百分点、对 Claude 的优势仅为 2.1 个百分点；图中 Claude 的 ASR 也只分布在 0 至 0.2 个百分点之间。类似地，表 1 相比 Progent 只报告了 0.8 个百分点的效用增益和 0.5 个百分点的任务成功率增益。这些数据能够说明观察到的结果，但不能证明这些指标上的差异具有实际意义。

## AI.W5 Margin interpretability is not validated / 间隔可解释性未得到验证

### Original English

Table 3 does not validate the claimed interpretability of the margins. Calls are partitioned by the rule *M_t(z_t) ≥ 0*, so positive admitted means and negative rejected means follow by construction, while positive rescaling of individual constraints can change raw magnitudes without changing their decisions. No analysis verifies whether the limiting constraint identifies the true semantic defect or whether its feedback enables a correct revision.

### 中文翻译

表 3 没有验证所声称的间隔可解释性。调用依据规则 *M_t(z_t) ≥ 0* 被划分，因此被接受调用的均值为正、被拒绝调用的均值为负是由构造方式直接决定的；与此同时，对单个约束进行正比例缩放可以改变原始数值大小，却不改变决策。论文没有分析限制性约束是否识别了真实的语义缺陷，也没有验证其反馈能否促成正确修订。

## AI.W6 Reliability claims are too broad / 可靠性表述过宽

### Original English

The broad reliability language exceeds the reported absolute task performance. Figure 2 gives DAFR 59.5 percent attack utility with GPT, and Table 1 reports 73.5 percent ASB task success. These levels demonstrate retained progress under attack, but leave substantial task failure unaccounted for in the Introduction’s claim of “reliable tool use.”

### 中文翻译

论文中较宽泛的可靠性表述超出了已报告的绝对任务表现。图 2 中，DAFR 在 GPT 上的攻击场景效用为 59.5%；表 1 报告的 ASB 任务成功率为 73.5%。这些结果表明系统在攻击下仍能保留一定任务进展，但引言中“可靠工具使用”的表述没有解释仍然存在的大量任务失败。

## AI.SG Suggestions for Improvement / 改进建议

### Original English

- **AI.SG1.** An adaptive evaluation could target the deterministic templates through provenance confusion, malicious tool metadata, fabricated prerequisites, and coordinated low-margin risks. The current fixed AgentDojo and ASB attacks do not characterize whether public knowledge of the feasible-region policy enables evasive calls that remain inside the region.
- **AI.SG2.** A leave-one-suite or leave-one-tool-family-out experiment could measure whether shared execution roles transfer without benchmark-specific redesign. Reporting the number of new role mappings, templates, and policy rules required would directly characterize the scalability of the “unified execution-layer” claim made in the Introduction and Limitations.

### 中文翻译

- **AI.SG1.** 可通过来源混淆、恶意工具元数据、伪造前置条件和协同的低间隔风险来攻击确定性模板，从而开展自适应评估。当前固定的 AgentDojo 和 ASB 攻击无法说明：当可行域策略公开后，攻击者是否可以构造仍位于域内的规避调用。
- **AI.SG2.** 可以采用“留一套件”或“留一工具族”实验，测量共享执行角色能否在不针对基准重新设计的情况下迁移。报告新增角色映射、模板和策略规则的数量，可以直接刻画引言和局限性部分所称“统一执行层”的可扩展性。

## AI.M Additional Details and Minor Issues / 其他细节与次要问题

### Original English

- **AI.M1.** Equation (14) requires structural assumptions on *W_k*: a dense matrix in Equation (9) need not permit linear time evaluation in the selected dimension. The bound also excludes semantic lifting and evidence projection.
- **AI.M2.** Algorithm 1 has no branch for a failed schema check at line 1, although the Problem Setup states that only schema-valid calls proceed.
- **AI.M3.** Equations (7) and (11) require conventions for empty critical-value or active-constraint sets.
- **AI.M4.** In Equation (8), stronger support raises *b_j − w_j^T z* only under appropriate signs for the corresponding entries of *w_j*; these sign restrictions should be formalized.
- **AI.M5.** Figure 1 labels the deterministic lifting component an “Evidence-Lifted Encoder,” which may suggest a learned encoder and conflicts with the description surrounding Equation (4).

### 中文翻译

- **AI.M1.** 公式（14）需要对 *W_k* 作结构性假设：公式（9）中的稠密矩阵不一定能在所选维度上实现线性时间计算；该复杂度界也没有包含语义提升和证据投影。
- **AI.M2.** 算法 1 在第 1 行模式检查失败时没有对应分支，但问题设置称只有模式合法的调用才能继续。
- **AI.M3.** 公式（7）和（11）需要规定关键值集合或激活约束集合为空时的处理约定。
- **AI.M4.** 在公式（8）中，只有当 *w_j* 的对应元素具有适当符号时，更强的支持才会提高 *b_j − w_j^T z*；论文应形式化这些符号限制。
- **AI.M5.** 图 1 把确定性提升组件标记为“Evidence-Lifted Encoder”，这可能让人误以为它是学习得到的编码器，并与公式（4）附近的描述冲突。

## References / 参考文献

An, H., Zhang, J., Du, T., Zhou, C., Li, Q., Lin, T., & Ji, S. (2025). IPIGuard: A novel tool dependency graph-based defense against indirect prompt injection in LLM agents. In *Proceedings of the 2025 Conference on Empirical Methods in Natural Language Processing* (pp. 1023–1039). Association for Computational Linguistics.

Chen, Z., Kang, M., & Li, B. (2025). ShieldAgent: Shielding agents via verifiable safety policy reasoning. In *Proceedings of the 42nd International Conference on Machine Learning* (Vol. 267, pp. 8313–8344). Proceedings of Machine Learning Research.

Lin, J., Zhou, Z., Zheng, Z., Liu, S., Xu, T., Chen, Y., & Chen, F. (2026). VIGIL: Defending LLM agents against tool-stream injection via verify-before-commit. In *Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)* (pp. 9764–9785). Association for Computational Linguistics.

### 中文说明

以上参考文献条目按截图原文保留，未在本次整理中重新核验其出版信息。
