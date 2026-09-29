# DAFR training-free 修订最小闭环（2026-09-29）

## 当前状态

协议审计已经发现并修复一个决定性问题：旧 mapper runner 将 `gold` 放入模型输入，因此旧 v1/v2 正确率不能作为泛化证据。v3 runner 只发送工具名、字段和策略文本，并在结构校验后实际调用 `IRPolicyCompiler.compile()`；v3 结果显示 qwen-max 的安全前置条件 exact 为 0.219、deepseek-v4-flash 为 0.281，说明当前训练-free mapper 尚未达到可直接进入端到端的安全映射门槛。

v4 进一步使用 32 条显式策略组合，gold 只保留在离线评分文件；两模型的后端可编译数分别为 12/32 和 11/32。v4 结果用于暴露 abstain 和语义失败模式，不能包装为泛化成功。

## AgentDojo 真实执行 smoke

使用 AutoDojo v1.2.2 banking、qwen-max、clafr，同一 API、同一防护配置，完成 8 个 clean 和 8 个 attack 任务。原始日志在 `results/runs/agentdojo_mapper_pair_smoke/manual_clafr/`。

- clean utility：5/8（62.5%）；
- attack utility：4/8（50.0%）；
- attack 组终端 security 字段为 0/0，不能直接解释成 ASR，需按 AgentDojo 的 task result JSON 重新汇总；
- 本次是真实工具执行，不是轨迹回放；但仍是手工策略映射基线，尚未完成 LLM-mapped 对照。

## 目前不能声称的内容

1. 不能声称 v1/v2 的 mapper 泛化率；gold 泄漏使它们失效。
2. 不能声称几何约束比任意 if/else 更有表达能力；同一可行域的 predicate 判决已验证等价。
3. 不能把 AgentDojo 16-task 手工基线当成 LLM mapper 的端到端结果。

## 下一步门槛

- 用 AgentDojo banking 的真实 tool schema 生成并冻结每个工具的 mapper IR；
- 在同一 16 个任务、同一模型、同一攻击下运行 manual IR 与 frozen LLM IR；
- 从每个 task JSON 汇总 legitimate success、attack success、blocked、abstain、tool side effect 和 token/latency；
- 只有当 mapper 失败时显式 abstain，不能静默退回手工策略；
- 几何/ predicate 比较必须记录实际 repair success、clarification、额外调用和副作用。
