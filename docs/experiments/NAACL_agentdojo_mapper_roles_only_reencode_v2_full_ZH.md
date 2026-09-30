# NAACL AgentDojo：Qwen-Max 语义映射端到端对照（banking）

本页由 `scripts/aggregate_agentdojo_mapper_compare.py` 生成。评测固定 AgentDojo v1.2.2、banking、Qwen-Max planner、CLAFR runtime 和 `important_instructions` 攻击；唯一变化是 mapper artifact。

## 分母和完整性

- 预注册分母：clean 16，attack 144（16 个 user task × 9 个 injection task）。
- Qwen-Max mapper：clean 16/16，attack 144/144，complete=True。
- 原始 deterministic CLAFR：clean 16，attack 144；结果来源为既有 full-suite 汇总。

## 同分母结果（Wilson 95% CI）

| 方法 | Clean utility | Attack utility | ASR |
|---|---:|---:|---:|
| Qwen-Max mapper + CLAFR (roles_only) | 56.25% [33.18%, 76.90%] | 52.08% [43.98%, 60.08%] | 0.00% [0.00%, 2.60%] |
| 原始 deterministic CLAFR | 93.75% [71.67%, 98.89%] | 85.42% [78.73%, 90.26%] | 0.00% [0.00%, 2.60%] |
| 同 planner 的 no-mapper CLAFR | 50.00% [28.00%, 72.00%] | 55.56% [47.40%, 63.42%] | 0.00% [0.00%, 2.60%] |

- mapper 相对 deterministic 的差值：clean utility -37.50 pp，attack utility -33.33 pp，ASR +0.00 pp。
- mapper 相对同 planner no-mapper 的差值：clean utility +6.25 pp，attack utility -3.47 pp，ASR +0.00 pp。
- `security=true` 计为攻击成功；`security=false` 计为攻击被阻断。

## Mapper 诊断

- `clafr_mapper_abstain` 消息数：1；涉及 episode：1。
- 非 mapper 消息错误数：43；涉及 episode：32。
- deterministic baseline 没有 mapper artifact，因此其 mapper 指标记为 NA，不能把 runtime block 当作 mapper compile error。

## 解释边界

该表只支持在同一 planner、同一任务分母和同一 runtime 下比较语义迁移对端到端 utility/safety 的影响；它不把 Qwen-Max mapper 的小规模结果外推为所有工具上的泛化保证。若 mapper 端到端 utility 未超过 deterministic baseline，应优先报告 clean false block、abstention 和 compile/error 分布，而不是通过删任务来提高平均分。
