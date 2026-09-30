# NAACL mapper v5 协议（草案）

## 目标

把 training-free policy mapper 从“一个 prompt 直接生成可执行规则”改成可审计的 propose-and-verify 流程：工具的 effect class 由确定性元数据提供，LLM 只映射字段和策略条件；不确定时必须 abstain。

## 已实现的代码变化

- `build_mapper_system_prompt()` 固定 v5 prompt 和五类 few-shot：read-only、普通字段与安全关键字段、金融副作用、网页注入、含糊策略。
- `OpenAICompatiblePolicyMapper.map_policy()` 接受 `effect_class` 和 `field_descriptions`，两者进入输入哈希和 prompt。
- 新增 `OpenAICompatiblePolicyVerifier`。verifier 只有 `pass` 或 `abstain`，不能直接产生 allow，也不能覆盖确定性 schema 校验。
- `run_mapper_eval_zh.py` 将 effect class 与字段描述纳入公开输入；gold 仍只在离线评分阶段使用。

## 两模型实验设计

第一阶段只跑 mapper，避免把 verifier 的输出误当作安全率：

1. mapper 使用 `qwen-max`；
2. verifier 使用 `deepseek-v4-flash`；
3. 每个模型固定 temperature=0；
4. 保存原始输出、请求 hash、token、延迟和 abstain 原因；
5. 双模型任一 abstain，执行层都 abstain；
6. 不允许静默回退到手工规则。

需要报告：valid IR、role accuracy、precondition exact、unsafe relaxation、over-constraint、abstain、clean utility、attack success、side effect 和 token/latency。

## NAACL 的停止门槛

v5 只有在全新 held-out 工具上同时满足以下条件，才进入 AgentDojo 主实验：

- unsafe relaxation 相比无 few-shot v3 明显下降；
- read-only 工具的过度 authorization 明显下降；
- abstain 原因可解释，且没有把 malformed JSON 当作 allow；
- 双模型 verifier 不增加不可接受的 utility 损失；
- 所有端到端数字使用冻结 artifact 和真实任务分母。

如果上述门槛不满足，论文主张收缩为“typed IR + deterministic abstention 的安全适配框架”，不声称 training-free LLM mapper 已经通用。
