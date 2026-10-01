# Responsible NLP Research Checklist 草稿

这是填写 ARR submission form 的准备稿，不是替代官方问卷。

## 数据与任务

- 使用 AgentDojo v1.2.2 和 Agent Security Benchmark 的公开/许可任务配置。
- AgentDojo 主协议包含四个工具 suite，71 个 clean episodes 和 585 个 attacked episodes。
- ASB 使用 204 个 case，记录 seed 17、stratified attack sampling、agent round-robin case sampling 和 source-tagged provenance。
- 本工作不新增人工受试者数据，不处理真实个人信息，不向真实外部工具发送实验调用。

## 模型与计算

- 评估 planner 为 DeepSeek V4 Flash、GPT-5.4-mini 和 Claude Haiku 4.5；ASB 使用 DeepSeek V4 Flash。
- execution verifier 为 deterministic runtime，不在执行阶段调用语言模型。
- 闭源模型结果应在提交表单中披露模型名称、调用协议、版本和成本；当前仓库不保存 API key。
- geometry 和 repair 机制实验均为 in-process，无外部副作用。

## 风险与限制

- 研究目标是减少间接 prompt injection 导致的未授权工具效果，但执行策略错误仍可能导致误拦或漏放。
- 0 observed ASR 只适用于给定 benchmark、攻击集合和 provenance threat model，不是一般安全保证。
- static attack 结果不能外推到 adaptive multi-step attacker。
- source provenance、授权通道和 typed field binding 不正确时，系统可能 abstain 或拒绝合法调用。
- 研究不提供绕过安全防护的攻击代码或真实外部执行能力。

## 可复现性

- 主文、Appendix、canonical baseline manifest、geometry audit summary 和运行脚本均保留。
- 结果按 suite、planner、case denominator 和 provenance 分开记录。
- 需要在上传软件和数据附件前再次检查匿名性和第三方许可证。
