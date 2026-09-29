# CLAFR 后续改造：LLM 策略映射与几何/规则隔离

## 目标

把当前 `PolicyCompiler` 中的关键词触发、工具字段角色和手工权重拆成一个可审计的 `ConstraintIR`。LLM 只负责从自然语言策略和 tool schema 生成 IR；确定性校验器验证 IR 后，几何编译器才允许消费它。LLM 不直接进入 allow/block 判决路径。

## 第一阶段已实现

- `src/clafr/policy_ir.py`：typed IR、角色/前置条件/风险预算和 fail-closed 校验。
- `src/clafr/policy_mapper.py`：离线 `StaticPolicyMapper` fixture 与 OpenAI-compatible API mapper。
- API mapper 读取 `DAFR_API_KEY`/`OPENAI_API_KEY`、`DAFR_BASE_URL`、`DAFR_MODEL`，不在仓库保存密钥。
- `tests/test_policy_mapper.py`：schema grounding、非法 role、非可信授权来源、越界风险预算测试。

## 第二阶段必须完成

1. 将 `PolicyCompiler` 的约束模板和权重迁移到 IR/配置文件。
2. 让 `clafr` 和 if-else baseline 共享同一 encoder、证据投影、IR 和案例集。
3. 对 LLM mapper 做字段角色 F1、前置条件 recall、unsafe relaxation rate、编译成功率、延迟和 token 成本评测。
4. 对四种决策表示做同策略隔离：boolean predicate、axis threshold、weighted halfspace、joint-risk cone。
5. 加入 repair metrics：repair success、effect preservation、edit distance、clarification rate。

## 安全不变量

- tool output/webpage 不能产生 authorization 或 confirmation。
- mapper 缺字段、未知 role、越界权重、解析失败时 fail closed。
- LLM 生成的 IR 只能收紧已有安全包络，不能放宽 trusted authorization 条件。
- 所有 runtime decision 记录 IR version、mapper provenance、margin vector 和 violated constraints。

## 论文主张

不声称几何在所有数据集上比 if-else 更安全。主张限定为：在相同语义 lifting 和相同策略下，几何提供联合风险组合、连续 margin 和最小修复方向；逐坐标 if-else 只能给出独立硬切分，无法表达风险预算之间的补偿关系，也不能自然输出修复方向。
