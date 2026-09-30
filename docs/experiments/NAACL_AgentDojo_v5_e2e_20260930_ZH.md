# v5 mapper 的 AgentDojo 真实执行配对

## 协议

- AutoDojo v1.2.2 banking；qwen-max；8 个 clean + 8 个 `important_instructions` injection task。
- tool schema 由 banking suite 读取；effect class 由工具名确定性标记；LLM 使用当前 v5 prompt；输出经过 `parse_mapper_response`、IRPolicyCompiler 和高置信 field-role gate。
- 失败只返回 `clafr_mapper_abstain`，不回退到手工规则。
- 原始 task JSON 和 stdout 位于 `results/runs/agentdojo_mapper_pair_v2/llm_mapper_clafr_v5/`。

## 结果

| 组别 | utility | AgentDojo security |
|---|---:|---:|
| clean | 2/8 | 不用于 ASR |
| injection | 2/8 | 0/8 attack success |

clean 和 injection 中都出现 mapper abstain；它们的具体次数以 task JSON 中的 `clafr_mapper_abstain` 消息计数为准。`security=false` 表示攻击被防住，不能把 clean 的 `security=true` 或 injection 的终端摘要误作同一个指标。

## 解释

与旧 effect-class artifact 的 clean 4/8、attack utility 4/8 相比，当前严格 role gate 的安全通过率更可审计，但 utility 明显下降。这个结果暴露出当前 mapper 的主要瓶颈是 read-only/低风险工具的过度 abstain 和字段角色门，而不是攻击放行。下一步需要在不放宽 side-effect 安全关键字段的前提下，单独优化 read-only policy 和编译覆盖率，再重新跑同一 16-task 配对。

当前不能声称 v5 mapper 已经有效替代手工规则；它已经完成真实执行验证，但仍未达到 utility 门槛。
