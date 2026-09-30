# Mapper v3：语义提升与执行兼容性记录

## 本轮目标

本轮不把 live AgentDojo 的一次独立 planner 采样当成 mapper 的因果提升。真正要验证的是三段链路是否闭合：

```text
自然语言策略 + 工具 schema
        ↓
Qwen-Max semantic mapper → ConstraintIR
        ↓
validated role map → semantic action encoder
        ↓
joint-risk geometry → execution certificate
```

其中 mapper 的有效性用未见工具和重命名字段测量，encoder 的有效性用固定动作和固定证据测量，geometry 的有效性用联合风险与可执行修复测量。Banking 只用来检查 native schema 上的执行不退化。

## Mapper v3 改动

1. **描述优先的角色判定。** `payment amount`、`refund amount`、`transfer quantity` 等明确金额描述优先映射为 `amount`；只有查询数量、分页和范围控制（`n`、`count`、`limit`、`page_size`、`offset`、`top_k`）映射为 `scope`。因此 `unit_count: payment amount` 不会再被字段名中的 `count` 误判。
2. **字段集合不替换。** 策略说“同一组字段”“两项字段”时，mapper 必须复制上一句明确命名的字段集合，不能把 `credit_handle`、`account_id` 等 object handle 替换进 confirmation 集合。
3. **保守语义回退。** native 字段（例如 `recipient`、`amount`、`body`）继续由 deterministic encoder 的既有启发式处理；只有 legacy 识别不到的重命名字段（例如 `owner_ref`、`target_mailbox`）才让 mapper-derived `destination` 扩展外部 sink 覆盖。这样同一 native tool call 的 mapper 路径不会因为一个新 role 而改变既有判决。
4. **可审计冻结。** Banking v3 artifact 保存 `ConstraintIR`、输入哈希、prompt/request 哈希、重试次数、finish reason 与截断的原始响应；LLM 短暂输出失败最多重试三次，语义不确定仍保持显式 abstain。

## 可复核结果

### 未见 schema mapper 主评测

数据为 24 个 case，包含 22 个非歧义 case 和 2 个应 abstain case；工具名不出现在 few-shot 中，字段采用 alias/重命名，策略包含中英文 approval/confirmation 改写。gold 不发送给模型，Qwen-Max 与 schema-aware rules 使用相同 validator/compiler/scorer。

| 方法 | 编译通过 | 非歧义 exact | 歧义正确 abstain | under/over-constrained |
|---|---:|---:|---:|---:|
| Schema-aware rules | 14/24 | 1/22 | 2/2 | 11/5 |
| Qwen-Max + validator + canonicalizer（原冻结 v12） | 22/24 | **21/22** | **2/2** | 1/1 |

结果文件：`results/summaries/mapper_eval_zh_v12_qwen_test/summary.json` 与 `results.jsonl`。原冻结 v12 结果沿用 21/22；之后在同一 v12 上改 prompt 的 22/22 重跑仅作为开发诊断，不计入泛化主表。独立无污染复核见 v14 文档。

### Mapper→Encoder 角色迁移

在 64 个固定动作、固定证据的 renamed-schema cases 中，字段名启发式 encoder 只能在 16/64 个 opaque destination cases 标记 external-destination risk；提供 validated role map 后为 64/64，且 64/64 生成完整 field-level provenance trace。该实验没有 planner 和外部副作用，结论是角色确实进入 encoder，不把它冒充成任务级安全率。

### Banking 执行兼容性

roles-only live run 为 clean 9/16、attack utility 75/144、ASR 0/144；no-mapper live run 为 8/16、80/144、ASR 0/144。两次 planner 调用没有 trace replay，因此 utility 差异不能归因于 mapper。对 190 个完全相同的 `(tool,args)` 调用，decision、feasible、execution margin、violated constraints 均 190/190 一致；这是 native schema 不退化证据，而不是 mapper utility superiority。复核脚本和结果在 `scripts/summarize_mapper_native_pair.py`、`results/summaries/agentdojo_mapper_native_pair_v1/summary.json`。

## 论文故事的固定表述

论文主张应写成：**semantic mapper 解决 schema fragmentation，semantic encoder 把角色和证据绑定到统一 action coordinates，geometry 提供联合风险证书、signed margin 和 repair target。**

不要写成“mapper 让 Banking utility 必然上升”，也不要写成“几何比所有 if--else 更安全或更有表达力”。几何对比的可辩护结论是：独立逐维阈值会漏掉联合风险（25/512 false allows），而 joint-risk region 能保留耦合预算、边界 margin 和可执行 repair；unrestricted predicate 与 geometry 的 accept/reject 应保持等价。
