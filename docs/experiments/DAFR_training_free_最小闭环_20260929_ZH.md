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

## 冻结 LLM IR 的 AgentDojo 配对结果

从 banking v1.2.2 的 11 个真实工具 schema 生成 LLM IR，8 个通过确定性编译，3 个 abstain。将该 artifact 接入执行器后，在同一 qwen-max、同一 banking user_task_0..7、同一 important_instructions/injection_task_0 下完成配对运行：

| 执行策略 | clean utility | attack utility | 映射失败时行为 |
|---|---:|---:|---|
| 手工 CLAFR | 5/8 | 4/8 | 不适用 |
| 冻结 LLM IR + CLAFR | 3/8 | 2/8 | `clafr_mapper_abstain`，不回退手工映射 |

上述 utility 是 AgentDojo task JSON 的实际结果；原始日志和每个任务 JSON 保存在 `results/runs/agentdojo_mapper_pair_smoke/`。当前输出没有把 attack 组终端 `security=0/0` 解读成 ASR，安全指标还需按 benchmark 的 injection utility 定义重新汇总。

这个结果暂不支持“LLM 映射可直接替代手工规则”。它支持的是更窄的工程结论：确定性 abstain 能阻止不合格 IR 进入执行层，但会明显降低合法任务 utility；下一步需要只修正字段映射和 read-only 工具策略，并保持失败时拒绝执行。

## 最小修复复测：alternate-schema 归一化

对 `preconditions` 字典、`affected_fields` 等模型输出格式做了最小结构归一化，未添加新的安全语义。11 个工具中可编译数由 8 增至 9，但重新运行同一 8 clean + 8 attack 后，utility 降为 clean 2/8、attack 2/8。该结果说明主要问题不是 JSON 格式，而是将统一的授权/确认策略施加到 read-only 工具会造成过度阻断。

因此不再继续增加通用字段规则；下一步改为按 effect class 生成 IR：read-only 工具只接受 schema/来源约束，side-effect 工具才要求 authorization/confirmation，并保留失败时 abstain。

## effect-class 分层尝试

为减少 read-only 工具的误拦，将策略分成两类：`get_*`/`read_*` 只要求参数和来源约束，`send_*`/`update_*`/`schedule_*` 继续要求授权与可信状态。该最小改动重新生成 artifact 后，11 个工具可编译数从 9 降到 6，说明当前 prompt/IR 生成对工具 effect class 的识别仍不稳定；本版本不进入端到端比较，保留作为失败日志。下一步应从确定性的工具元数据读取 effect class，再让 mapper 只填字段角色和条件，不能让 LLM 自由猜测全局 effect。

## 确定性 effect-class 适配复测

新增 `artifact_effectclass_v1.jsonl`：read-only 工具由确定性元数据标记，清除不适用的 authorization/confirmation；side-effect 工具保留 LLM IR，非法或不完整 IR 仍 abstain。相同 8 clean + 8 attack 任务复测得到：clean utility 4/8，attack utility 4/8，3 个任务出现 `clafr_mapper_abstain`。相对未分层的第一版 LLM IR（clean 3/8、attack 2/8），utility 有改善，但仍低于手工 CLAFR（5/8、4/8）。这支持“确定性 effect class + LLM 字段映射 + abstain”比统一全局策略更可行，但尚未支持安全率提升。
