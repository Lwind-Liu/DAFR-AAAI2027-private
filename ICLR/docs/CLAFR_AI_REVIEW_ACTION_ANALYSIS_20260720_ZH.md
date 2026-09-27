# CLAFR AI 审稿意见分析与修订优先级

## 结论

这份 AI 审稿意见应按“严厉但有参考价值”处理。它不是在否定 CLAFR 的方向，而是在指出当前稿件最容易被 AAAI 审稿人追问的四类证据缺口：实验协议公平性、几何机制的独立贡献、静态攻击以外的压力测试、以及跨工具泛化是否来自通用语义而非 benchmark 特调。

当前论文包里的 `SELF_REVIEW_ZH.md` 版本偏积极，认为稿件已经到 7.2/10；用户贴出的外部 AI review 给到 6/10。更稳妥的策略是按 6/10 版本补强，因为它命中的都是安全类 paper 常见审稿点。

## 审稿意见是否合理

### 1. 实验协议不够可审计：合理，优先级最高

当前 `main.tex` 的实验设置只有一个短段落说明 AgentDojo、DeepSeek V4 Flash、四域 macro-average 和 baseline 类型。它没有集中列出 AgentDojo 版本、case 数、攻击集合、temperature、max steps、失败重试、baseline 来源、workspace 补跑与 Word 复用的计算方式。

这会带来一个直接风险：审稿人会认为 CLAFR 得到了最充分适配，而 Progent、DRIFT、PIGuard 等 baseline 可能没有等价适配。

处理方式：主文不需要写成日志，但必须增加一个高密度 protocol paragraph；附录放完整 manifest、case count、评分脚本、baseline provenance 和 merge 公式。

### 2. 几何机制和规则验证器没有完全隔离：合理，优先级最高

当前消融表显示 `w/o Dynamic Geometry` 后 ASR 从 0.0 升到 18.4，能够支撑“Dynamic Geometry 是主要安全机制”。但严格审稿人会说：这只证明最终 gate 有用，没有证明几何可行域比 boolean rule gate、linear score、hard verifier 或 symbolic policy 更好。

这条意见是全稿最关键的技术风险。因为论文主创新不是“有一个 runtime verifier”，而是“state-conditioned geometric feasible region 作为 action selection inductive bias”。

处理方式：补一个 geometry isolation 表。所有变体共享 Evidence Projection 和 Semantic Lifting，只替换 decision boundary：

- Boolean Rule Gate
- Linear Risk Score
- Independent Thresholds
- Halfspace Only
- SOC Only
- Halfspace + SOC without Margin
- Full CLAFR

指标至少保留 Clean Utility、Attack Utility、Static ASR；如果篇幅允许，附录加 False Block Rate、Clarify Rate、Repair Success Rate、Margin。

### 3. Static ASR 为 0 但没有 adaptive attack：合理，优先级中高

当前稿件已经写成 “zero ASR under static attacks”，没有把 0 ASR 扩张成绝对安全保证，这是正确的。但安全论文里看到 “zero ASR” 仍会自然要求 adaptive stress test。

处理方式：不需要在主表里重构全部实验，最好补一个小型 adaptive stress test，攻击 CLAFR 自身机制：

- provenance spoofing：攻击文本伪装成工具状态或授权；
- destination ambiguity：把恶意 recipient / URL 混入合法实体附近；
- multi-step state contamination：先诱导 benign read，再污染后续 write/disclose；
- clarification exploitation：利用 clarify 回合把不可信内容转写成看似可信请求。

即使 adaptive ASR 不是 0，只要明显低于 baseline，反而更可信。

### 4. Semantic Lifting 细节过抽象：合理，优先级中高

当前方法部分有坐标族表、公式和 running example，但坐标如何从 task/schema/tool description/argument/provenance 计算仍主要交给 artifact。主文里缺少一个具体 call 的坐标例子。

处理方式：增加一个短 example box 或 appendix table，展示一个真实工具调用如何形成：

- trusted intent support
- destination grounding
- argument provenance
- authorization strength
- external sink risk
- untrusted-control signal
- joint risk margin

这能降低“公式包装工程规则”的攻击面。

### 5. ASB / cross-registry 说服力不足：部分合理

审稿意见指出十域 cross-registry 不是标准命名 benchmark，这确实是风险。当前稿件称其 “built from Agent Security Bench tool interfaces”，但如果没有清楚说明 case 生成、domain composition、baseline adapter 和 per-domain breakdown，审稿人会质疑它是否贴合 CLAFR。

处理方式：不要把它包装成标准 ASB leaderboard；应明确称为 “ASB-interface cross-registry transfer setting”。主文只保留迁移结论，附录给 per-domain breakdown、case construction 和 baseline adapter rules。

### 6. Failure boundary 缺失：合理，但写法要控制

用户之前明确要求不要写防御性 limitations，这是对的。这里不应新增一个自我否定的 Limitations 章节。

处理方式：在 method 或 appendix 中写成 deployment contract，而不是 limitation：

- trusted provenance channel
- schema role binding
- trusted confirmation channel
- source metadata availability

表达方式应是“CLAFR 的运行时契约定义了可部署条件”，不是“CLAFR 在这些场景失败”。

## 当前稿件已经覆盖的部分

当前 `main.tex` 已经做对了以下点：

- 摘要明确 CLAFR 是 state-conditioned feasible region，而不是文本过滤器。
- 方法部分已经把 Evidence Projection 和 Dynamic Geometry 分工拆开。
- `Core and Environment Binding` 已写出 core/binding 划分，并声明 weights、budgets、thresholds 固定。
- RQ2 消融已把 Dynamic Geometry 作为主要安全机制。
- `Why It Generalizes` 已给出跨 API 关系语义、cross-registry 和跨 planner 的统一解释。

这些内容应保留，不要倒回旧稿那种实验日志式叙述。

## 必须补的最小修改

1. 在 Experiments 开头补 protocol paragraph：AgentDojo 版本、四 suite、case 数、attack set、model decoding、max steps、scoring、macro-average、baseline 来源与复用/补跑规则。

2. 增加一张 geometry isolation 表，证明 Full CLAFR 的几何边界优于同输入的 rule/score/threshold boundary。

3. 给 `zero ASR` 加准确限定：主文统一使用 “zero observed ASR under evaluated static attacks” 或 “zero static ASR in this protocol”。

4. 附录补 per-domain breakdown、置信区间、failure/error examples、latency。

5. ASB 表改名为 cross-registry transfer setting，并明确不是直接 claim 标准 ASB leaderboard。

## 可以提高评分的补实验

优先顺序：

1. Geometry isolation，最高收益，直接保护核心创新。
2. Adaptive stress test，小规模即可，保护安全主张。
3. Per-domain breakdown + CI，保护结果可信度。
4. Multi-LLM Claude/GPT 扩展，作为泛化补强，但不如前两项关键。

## 不建议做的事

- 不要在摘要里堆版本号、case 数和 baseline 细节。
- 不要新增防御性 Limitations 大段自曝问题。
- 不要把 cross-registry setting 说成完整标准 ASB leaderboard。
- 不要继续只靠 `w/o Dynamic Geometry` 表证明几何必要性。
- 不要把 `zero ASR` 写成无条件安全保证。

## 最终判断

这份审稿意见对当前稿件的最大价值，是提醒我们主张必须从“CLAFR 有效”升级为“几何可行域相对于同输入规则边界有独立优势”。如果只做写作调整，稿件大概是强 6 到弱 7；如果补上 geometry isolation 和一个小型 adaptive stress test，论文的技术可信度会明显更稳。

