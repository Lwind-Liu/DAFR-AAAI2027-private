# Revision working text — experimental, not submission-ready

## Claim correction

A general arithmetic predicate can express exactly the same weighted halfspace and
second-order norm inequalities as our geometric implementation. We do not claim a
representational advantage over unrestricted if/else programs. Axis-aligned thresholds
are a restricted hypothesis class, not an equivalent implementation of the same policy.
The equivalent-predicate control shares constraints, features, evidence and candidate
ranking with the geometric backend. Its acceptance decisions should coincide.

## Why keep geometry instead of a boolean if--else gate?

The claim is about the execution interface, not about the expressive power of
arithmetic. An unrestricted predicate can reproduce every current halfspace and
second-order cone, so the predicate control is required to match the geometry
decision. Geometry is retained because one typed region exposes four quantities
from the same object: (i) joint feasibility across fields, (ii) a signed and
normalized margin for every violated facet, (iii) an interface for future constrained repair search (not yet a closest-action solver), and (iv) a provenance-bearing certificate that
can be composed when a new policy facet is added. A boolean gate returns only
true/false; an arithmetic implementation can expose the same quantities from shared constraint objects. Maintenance and repair advantages therefore remain hypotheses, not intrinsic properties of geometry.

This is a falsifiable systems claim. We will compare geometry and an equivalent
predicate with the same feature vector, constraints, candidates and repair
budget. The primary metrics are decision disagreement (should be zero), boundary
ranking agreement, constraint-localization accuracy, executable repair success,
unsafe repair rate, clarification count, and added latency. If a predicate
implementation is augmented with the same margin and repair oracle, any geometry
advantage should disappear; that result is expected and will be reported as a
representation/maintenance advantage rather than a security guarantee.

The motivating failure mode is a coupled budget: two individually acceptable
fields can exceed a joint risk budget. Geometry represents this as one cone and
reports the joint slack. A collection of independent if--else thresholds misses
the interaction; a hand-written predicate can encode it, but then the coupling,
diagnostic, and repair logic must be maintained separately.

## Proposed method

We investigate a training-free semantic mapper that translates trusted policy text and
tool schemas into a typed constraint representation. Structural and semantic-completeness validation checks the
representation; it does not establish full semantic fidelity. Security preconditions must
name their affected fields and use positive thresholds; failures abstain rather than being
repaired into an allow decision.
The experimental runtime intersects supported mapped constraints with the existing
trusted constraint envelope. Consequently, for fixed features and execution context,
the accepted set is a subset of that envelope. This inclusion is conditional on the
baseline's correctness and says nothing about safety of missing baseline policies.

The current adapter supports field-scoped grounding and authorization through the
feature encoder, and aggregate nonnegative risk budgets over existing features. Field-scoped
risk budgets and forbidden effects are rejected explicitly.
Role labels are supplied by a large-language-model semantic mapper and then checked before
entering the feature encoder. If this mapper transfers to held-out tools without parameter
updates, the evidence supports training-free cross-tool semantic adaptation. It does not
imply that a trained encoder will work; a trained encoder is a separate distilled,
low-latency implementation of the same IR interface and requires its own evaluation.

## Evaluation contract

1. Equivalent predicates: test decision agreement, including boundary points. Do not
   attribute ASR improvements to changing syntax from predicates to regions.
2. Mapper: held-out tools and policy paraphrases; measure omission, unsafe relaxation,
   field/role accuracy, abstention and API usage. Structural validity alone is insufficient.
   Compare manual mapping, LLM mapping, and a trained/distilled encoder under the same IR
   and execution layer; do not transfer conclusions between these adapters.
3. Repair: compare against predicate-based candidate enumeration using identical repair
   candidates and cost. Measure executed effect preservation, unsafe repair and utility;
   feature-space projection distance is not proof of an executable repair.
4. Report fixed-trajectory diagnostic results separately from fresh end-to-end rollouts.

No new benchmark accuracy or security claims have been established by this revision.

## Evidence gate after protocol audit (2026-09-29)

The first mapper pilot was invalid because the runner sent the hand-written `gold`
object to the model.  The corrected runner withholds gold and checks both IR
validation and `IRPolicyCompiler.compile()`.  On the corrected 32-case pilot,
precondition exact match is 21.9% for Qwen-Max and 28.1% for DeepSeek V4 Flash;
unsafe relaxation is 65.6% for both models.  These numbers are the usable mapper
baseline; the earlier positive pilot numbers must not be cited as generalization.

On the same 8 clean plus 8 injection banking tasks, the hand-written CLAFR
baseline succeeds on 5/8 clean tasks and has 0/8 attack successes.  A frozen LLM
IR artifact succeeds on 3/8 clean and 2/8 attack-utility tasks, while a
deterministic read-only/effectful tool-class adapter reaches 4/8 and 4/8.  Both
LLM variants have 0/8 attack successes under AgentDojo's `security=true`
definition, but their abstentions and utility loss prevent a claim that the
mapper improves end-to-end safety.

The matched 64-case in-process geometry pilot has zero geometry/predicate decision
disagreements, 32/64 allows for each, and zero executable repairs.  We therefore
retain the geometry story only as a common representation for coupled constraints
and diagnostics; we withdraw any claim that geometry is more expressive than
if--else or has already demonstrated better repair utility.


## Current smoke evidence (not a benchmark result)

A four-tool smoke pilot with Qwen-Max produced structurally valid, backend-compilable mappings for `send_email`, `transfer_funds`, `delete_record`, and `publish_post`. Against hand-written labels for this pilot, role accuracy and precondition exact match were both 1.0. These numbers are not held-out generalization results. The pilot also exposed a necessary metric for the full study: over-constraint rate, since a mapper may safely include an ordinary field in an authorization set while reducing utility.

## NAACL 执行版主线（P1--P4）

本版本的论文包装不再把贡献写成“几何天然优于 ifelse”，而是把问题提升为：**如何把自然语言安全策略可靠地迁移到未见工具，并在多维耦合风险下生成可审计、可修复的执行决策**。语义映射解决跨 schema 迁移，几何 runtime 提供联合风险的执行证书。这样既有方法故事，也保留了可证伪的对照实验。

### P1：公平 mapper 基线

必须实现一个 schema-aware deterministic mapper，作为强规则基线。它读取同一份 policy、tool schema 和字段描述，使用固定词典、字段类型、effect class 和显式 policy pattern 生成同一 `ConstraintIR`。它不能读取 held-out gold，也不能调用 LLM。所有 mapper 共用 parser、canonicalizer、compiler、encoder 和 runtime。

最小比较矩阵如下：

| Mapper | 是否更新参数 | 是否调用 LLM | 作用 |
|---|---:|---:|---|
| Per-tool handwritten | 否 | 否 | 原始 DAFR 参考上限/开发基线 |
| Schema-aware rules | 否 | 否 | 公平规则基线 |
| Qwen-Max mapper | 否 | 是 | 训练免费语义迁移 |
| Qwen-Max + canonicalizer | 否 | 是 | 最终系统 |
| Distilled encoder（可选） | 是 | 否 | 低延迟实现，不与 training-free 结论混用 |

每个方法报告 role accuracy、precondition exact match、unsafe relaxation、omission、over-constraint、abstention、平均延迟和 token cost。论文中的“LLM 优于规则”只有在 schema-aware rules 也经过调优、使用相同 IR 和相同工具划分时才成立。若规则在封闭 schema 上更好，应将贡献表述为开放工具迁移和低人工配置，而不是绝对精度领先。

### P2：跨工具迁移协议

冻结一个未见工具测试集，建议至少 24 个工具，覆盖 communication、finance、file、calendar、database 和 publishing 六类；每个工具提供 2 个 policy paraphrase 和 1 个 ambiguous policy。训练或 prompt 构造阶段只能使用另一组工具，不能出现测试工具名、字段名和 gold IR。

每个 case 保存四份可审计记录：原始 policy/schema、LLM raw response、canonicalized IR、编译后的 constraint artifact。评测同时使用人工 gold 和独立 verifier。核心指标为：

- role micro/macro F1；
- precondition exact match；
- unsafe relaxation rate（缺少必要限制）；
- over-constraint rate（引入策略没有要求的限制）；
- abstention precision/recall；
- compile success；
- 每个工具的人工修正时间；
- API 延迟和 token 成本。

主表中将“结构合法”与“语义正确”分开。当前 v7--v11 只能作为开发证据，不能替代该冻结测试集。

### P3：联合风险和等价 predicate 对照

扩大当前 32-case joint-risk pilot，生成至少 200 个 boundary-active case，覆盖二维、三维和四维风险。每个 case 固定相同 feature vector、constraint object、candidate action 和 evidence，比较以下四个执行器：

1. Axis-ifelse：逐维阈值；
2. Equivalent-predicate：实现同一个联合约束；
3. Geometry：返回 allow/block、margin、violated facet 和 certificate；
4. Predicate+oracle：在 predicate 上补齐同样的 margin、来源和 repair oracle。

预期结果和解释在实验前固定：Axis-ifelse 应在耦合预算上出现 false allow；Equivalent-predicate 与 Geometry 的 decision disagreement 应为 0；若 Predicate+oracle 与 Geometry 也相同，则几何优势收缩为统一的约束对象、调试和组合接口。必须报告 boundary disagreement、joint-risk false allow、facet localization accuracy、clarification rate、额外 latency 和 provenance completeness，不能用微秒级 pilot 宣称速度优势。

### P4：真实候选动作修复

把当前“删除不可信可选字段”的 repair 扩展为候选动作集合。每个候选动作必须能在同一工具 runtime 中执行或 dry-run，并标注 effect preservation、外部副作用和是否改变用户意图。比较 Geometry、Equivalent-predicate、Predicate+oracle、Block-only 四种策略。

核心指标为 executable repair success、safe repair rate、unsafe repair rate、effect preservation、action edit distance、clarification rate、平均 replay 次数和外部副作用数。feature-space 投影距离不能作为 repair 成功的替代指标。若 Geometry 和 Predicate+oracle 相同，应保留“几何提供原生诊断接口”的工程贡献，不声称它单独产生安全增益。

## 论文包装和停止条件

摘要中的贡献可以写成“policy-to-execution semantic lifting”和“joint-risk execution certificates”，突出两个层次：第一层把自然语言策略迁移到未见工具，第二层把跨字段风险编译为可组合的执行证书。正文中可以使用“training-free semantic adaptation”作为方法属性，但不要把它写成未经大规模验证的普适优势；真正的卖点是低人工配置、跨 schema 迁移、显式 abstention 和可审计执行。

只有满足下面的停止条件，才把主线定稿：

1. schema-aware rules、Qwen-Max 和最终系统在同一 held-out 工具集完成比较；
2. LLM mapper 在 unsafe relaxation 和 over-constraint 上不劣于规则，且至少在迁移成功率或人工配置时间上有明确优势；
3. Geometry 相比 Axis-ifelse 在 joint-risk false allow 上显著更低；
4. Geometry 与 Equivalent-predicate 的决策一致性接近 100%；
5. P4 至少有一项 executable repair 或 facet localization 指标优于 bool-only baseline；
6. AgentDojo 扩展到足够任务数和多 seed 后，clean utility、attack success、abstention 和成本一起报告。

若第 2 或第 5 条不满足，论文仍可投，但应把故事收缩为“统一语义约束编译和审计接口”，不能声称 LLM mapper 或 geometry 已经全面优于规则和 predicate。当前 5/8 clean、4/8 attack utility、0/8 attack success 只作为 smoke evidence，不能作为最终主表。
