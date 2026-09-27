# 审稿问题与后续修改追踪表

**处理模式：** `triage-only`（仅整理与分派，不声称已完成任何新增实验或论文修改）  
**决定类型：** AAAI-27 第一阶段拒稿，决定为最终决定  
**当前包状态：** `needs_author_input`

本表用于下一版论文或转投版本的协作。相同问题在不同审稿意见中重复出现时，保留各自 ID，并通过“合并处理”列关联，避免漏项。

| ID | 核心问题 | 类别 | 严重度 | 建议动作 | 合并处理 | 当前状态 |
|---|---|---|---|---|---|---|
| E.1 | 未进入 Phase 2，决定为最终决定 | Editorial | major | 不走常规 rebuttal；将评审意见转化为下一版修订计划 | 全部 | 已记录 |
| R1.1 | 人工配置成本、角色/模板/系数数量及新工具接入时间未量化 | Methodological | major | `AUTHOR_INPUT_NEEDED`：统计配置项数量、人员角色、工时和跨套件差异 | R2.1, AI.W1, AI.SG | 待作者输入 |
| R1.2 | 几何机制未与等价规则系统公平隔离 | Evidence / interpretation | major | `ACCEPT_EXPERIMENT` 或 `ACCEPT_ANALYSIS`：同规则、同投影、同权限下比较几何与非几何决策 | R2.1, AI.W3 | 待方案与结果 |
| R1.3 | 缺少知道防御策略的自适应攻击 | Methodological | major | `ACCEPT_EXPERIMENT`：构造来源混淆、标签操纵、恶意元数据、伪造前置条件等攻击 | R2.2, AI.SG | 待方案与结果 |
| R1.4 | 坐标块、策略模板、系数、Clarify/Block 路径和敏感性缺失 | Methodological | major | `ACCEPT_TEXT` + `ACCEPT_ANALYSIS`：公开规则并补敏感性实验 | R1.1, AI.W1 | 待作者输入 |
| R2.1 | 人工策略、表示设计和几何决策的贡献无法分离；跨域迁移未验证 | Methodological | major | `ACCEPT_EXPERIMENT`：冻结策略迁移、leave-one-suite/tool-family-out、等价对照 | R1.1, R1.2, AI.W3, AI.SG | 待方案与结果 |
| R2.2 | 零事件不等于真实 ASR 为零；缺分组分母、区间与边界案例 | Statistical | major | `ACCEPT_ANALYSIS`：按攻击族/套件/模型/动作报告分母和零事件区间，审计近边界调用 | AI.W4 | 待统计分析 |
| AI.W1 | 核心安全计算与策略开发流程定义不足，可能含基准特定工程 | Methodological | major | `ACCEPT_TEXT`：给出代表性规则、来源标签假设、系数、激活逻辑和开发协议 | R1.1, R1.4 | 待作者输入 |
| AI.W2 | 与 ShieldAgent、IPIGuard、VIGIL 的创新差异不清 | Citation / positioning | major | `ADD_CITATION` + `SOFTEN_CLAIM`：核验文献并重写几何贡献边界 | — | 待文献核验 |
| AI.W3 | 表 2 消融定义不清，不能证明安全差异来自几何机制 | Evidence / interpretation | major | `ACCEPT_TEXT` + `ACCEPT_EXPERIMENT`：定义每个消融并做公平非几何对照 | R1.2, R2.1 | 待方案与结果 |
| AI.W4 | 多项小幅比较缺种子、置信区间或配对检验 | Statistical | major | `ACCEPT_ANALYSIS` 或 `SOFTEN_CLAIM`：补不确定性或收窄比较结论 | R2.2 | 待统计分析 |
| AI.W5 | 带符号间隔的可解释性主要由定义保证，未验证真实语义缺陷或修订效果 | Evidence / interpretation | major | `ACCEPT_ANALYSIS`：人工标注真实缺陷，评估限制约束识别和反馈修复率 | — | 待方案与结果 |
| AI.W6 | “reliable tool use”等表述超过绝对任务表现 | Evidence / interpretation | major | `SOFTEN_CLAIM`：明确仅保留攻击下的相对进展，并报告剩余失败 | — | 待论文修改 |
| AI.SG1 | 建议用来源混淆、恶意元数据、伪造前置条件和低间隔风险开展自适应评估 | Methodological | major | 与 `R1.3` 合并执行 | R1.3, R2.2 | 待方案与结果 |
| AI.SG2 | 建议用 leave-one-suite/tool-family-out 测量冻结迁移与配置扩展成本 | Methodological | major | 与 `R2.1` 合并执行 | R1.1, R2.1 | 待方案与结果 |
| AI.M1 | 公式（14）的复杂度需要对矩阵结构作假设，且未计入提升/投影成本 | Methodological | minor | `ACCEPT_TEXT`：补假设并修正复杂度范围 | — | 待论文修改 |
| AI.M2 | 算法 1 缺少模式检查失败分支 | Editorial / methodological | minor | `ACCEPT_TEXT`：补失败返回路径 | — | 待论文修改 |
| AI.M3 | 公式（7）、（11）缺空集合约定 | Editorial | minor | `ACCEPT_TEXT`：补空集合定义 | — | 待论文修改 |
| AI.M4 | 公式（8）的单调性需要符号约束 | Methodological | minor | `ACCEPT_TEXT`：形式化对应权重符号限制 | — | 待论文修改 |
| AI.M5 | “Evidence-Lifted Encoder”易被误解为学习编码器 | Editorial | minor | `ACCEPT_TEXT`：改为确定性投影/提升模块并统一术语 | — | 待论文修改 |

## 建议优先顺序

1. 先解决机制隔离：以完全相同的投影、规则、来源标签、状态与执行权限，对比几何决策和等价非几何决策。
2. 再补透明度：统计人工策略编写成本，公开代表性模板、系数、激活逻辑和 Clarify/Block 路径。
3. 补安全有效性：加入策略知情型自适应攻击和跨套件/工具族冻结迁移。
4. 补统计与解释验证：报告分组分母、零事件区间、种子/配对检验、边界案例和反馈修复率。
5. 最后重写贡献和相关工作：收窄可靠性与通用安全声明，清楚定位相对 ShieldAgent、IPIGuard 和 VIGIL 的差异。

## 作者仍需提供的信息

- AgentDojo 与 ASB 的角色映射、模板、系数和规则数量，以及实际配置工时。
- 哪些策略在两个基准间共享，哪些发生变化；新工具接入的真实步骤和耗时。
- 表 2 每个消融的精确定义和对应代码入口。
- 585 个 AgentDojo 与 204 个 ASB 攻击案例的分组计数及逐案例结果。
- 是否已有多随机种子、置信区间、配对检验、自适应攻击或跨域迁移结果。
- 下一投稿版本计划采用哪些修改，以及对应正文/附录/代码位置。
