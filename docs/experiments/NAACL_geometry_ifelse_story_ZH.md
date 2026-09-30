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
