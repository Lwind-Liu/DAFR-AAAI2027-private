# NAACL 几何约束与 ifelse 的可证伪故事

## 不能讲的故事

- 不能说 ifelse 无法表达斜半空间或二阶范数约束。
- 不能说几何约束天然更安全。
- 不能把当前 64-case 的零分歧结果包装成 geometry 优于 predicate。

一般 arithmetic predicate 可以实现同一个可行域。公平比较必须使用同一 encoder、同一约束、同一候选集合和同一执行预算。

## 可以讲的故事

几何约束的价值是把“是否允许”升级为一个可组合的执行证书：

1. **联合约束**：多个字段的风险可以组成一个 joint cone。独立的 `if dim_i > t_i` 会漏掉“每一维单独合格但联合超预算”的情况；任意 ifelse 可以补上，但需要额外手写耦合逻辑。
2. **边界诊断**：每个 facet 都产生 signed normalized margin，执行器可以知道是 recipient、amount、state freshness 还是 grounding 违反了边界。纯布尔返回值没有这个信息。
3. **修复接口**：同一 region 可以生成 violated facet、repair hint 和最小投影方向。ifelse 如果只返回 true/false，必须另写一套 repair 搜索；如果补齐同样的诊断接口，几何的优势应当消失。
4. **可组合维护**：新增策略只需增加带 provenance 的 facet 或 cone，并保留约束来源；ifelse 需要同步更新判定顺序、错误分支和 repair 分支。

因此主张是“几何提供更统一、可诊断、可修复的执行接口”，不是“几何比任意程序更有表达能力”。

## 实验矩阵

| 变体 | 约束 | 输出 | 用途 |
|---|---|---|---|
| Axis-ifelse | 每维独立阈值 | bool | 展示受限 ifelse 漏掉联合风险 |
| Equivalent-predicate | 与 geometry 完全相同 | bool | 检验表达等价，预期决策 0 分歧 |
| Geometry | 与 predicate 完全相同 | bool + margins + certificate | 测诊断和修复接口 |
| Predicate+oracle | 相同 predicate + 独立 margin/repair oracle | bool + diagnostics | 检验若补齐接口，geometry 优势是否消失 |

## 必须报告的数字

- decision disagreement，特别是边界点；
- joint-risk violation detection；
- violated-constraint localization accuracy；
- executable repair success；
- unsafe repair rate；
- clarification rate；
- 每次判定的额外延迟和 token；
- 外部副作用数量。

几何故事只有在 Geometry 相比 Axis-ifelse 能识别联合风险，并且相比纯 bool predicate 提供更高的可执行修复或更准确的边界诊断时才成立。若 Predicate+oracle 与 Geometry 相同，则结论收缩为统一表示和维护优势。

## 当前证据

现有 64-case pilot 中 geometry 与 equivalent predicate 的判决分歧为 0/64，双方 allow 均为 32/64，executable repair 为 0。因此当前只能说明实现等价，尚未证明 repair 或 utility 优势。下一轮实验必须在同一 `src/clafr` runtime 上增加 boundary-active、joint-risk 和真实候选修复案例，不能继续引用不同 runtime 的 geometry isolation 数字作为主结论。

## 2026-09-30 实现审计更正

当前 clafr 的 repair 是删除缺乏支持的可选字段，不是最近可行工具动作求解器。SOC 的 normalized_slack 是缩放残差，不能当作精确欧氏距离。predicate 也可以共用约束对象输出 margin、失败规则和来源，不能声称它必然需要复制维护逻辑。上述投影、维护优势属于待验证设计假设。

## 同一 clafr runtime 的 v2 pilot

`run_geometry_predicate_execution_pilot.py` 在同一 encoder/compiler/candidate/evidence 上运行 64 个决策 case，并增加 16 个可执行删除可选字段的 repair case：

- geometry/predicate decision disagreement：0/64；
- geometry allow：32/64，predicate allow：32/64；
- 平均耗时：geometry 0.292 ms，predicate 0.290 ms；
- 两者共用 repair 实现时，repair success 都是 16/16；
- bool-only predicate 没有诊断和 repair 接口，因此对应为 0/16，但这只是接口比较，不是表达能力比较；
- 外部副作用：0。

这组结果支持的故事是：几何可作为统一的 margin/violated-constraint/certificate 接口，且能与执行修复直接连接。它不支持“几何比等价 predicate 更安全”或“几何天然更快”。如果 predicate 也实现同样的诊断和 repair oracle，预期结果应当相同。

## 联合风险的可证伪 pilot

为了让“几何优于 ifelse”的故事不依赖抽象描述，新增 `run_geometry_joint_risk_pilot.py`。它固定同一个 `FeatureVector` 和同一个二维 `RiskBudgetCone`，比较三种判定：

- `Axis-ifelse`：两个独立阈值 `privacy <= 0.8 and financial <= 0.8`；
- `Geometry`：联合 L2 风险预算；
- `Equivalent-predicate`：复用完全相同的 cone membership。

32 个边界附近 case 中，Axis-ifelse 放行 32/32，Geometry 放行 23/32，其中 9 个 case 每一维都没有超过独立阈值，但联合风险范数超过 1；Geometry 与 equivalent predicate 的分歧为 0/32。平均耗时约为 0.0023 ms 与 0.0017 ms，样本极小，只用于证明联合风险漏检机制，不用于速度结论。

因此可讲的精确故事是：朴素的逐维 ifelse 会漏掉耦合风险，几何约束把耦合预算写成一个可检查的 region；对于能够表达同一联合 predicate 的 ifelse，决策应当完全一致，几何的额外价值在 margin、违规 facet、provenance 和 repair 接口。论文不能把这个结果扩大为“几何优于任意程序”。
