# 语义动作编码角色迁移 Pilot v1

## 目的

验证 `ConstraintIR` 角色映射是否真正进入动作编码器，而不是只停留在 mapper 输出中。实验固定动作、可信任务、策略文本和运行时状态，只替换工具字段名，并比较：

- **Raw encoder**：不提供 IR，使用原有字段名和工具文本启发式；
- **Role-conditioned encoder**：提供经过验证的 `ConstraintIR`，按 `destination/data/amount/time/scope/object` 角色编码，并保留字段级 provenance trace。

## 协议

- 8 组工具 schema，每组 6 个语义字段；
- 每组 8 个动作，共 64 个 paired cases；
- 字段使用 `owner`、`target_mailbox`、`payload_bytes`、`cents`、`when`、`resource_key` 等不稳定别名；
- 一部分案例将目的地替换为不受信任的 opaque identifier；
- 不调用 planner，不执行外部工具，没有 AgentDojo/ASB 任务分母。

## 结果

| 指标 | Raw encoder | Role-conditioned encoder |
|---|---:|---:|
| 标记 external destination risk 的案例覆盖 | 16/64 (25.0%) | 64/64 (100.0%) |
| 字段级 role trace 完整 | 不适用 | 64/64 (100.0%) |

Raw encoder 仍能识别带有传统邮箱或目的地字段名的少数案例，因此该实验不是声称 raw encoder 完全失效。它说明在字段重命名且值本身为 opaque identifier 时，角色接口能够把语义信息传递到执行坐标；这正是 mapper 与 encoder 之间需要验证的接口性质。

## 复现

```bash
PYTHONPATH=src .venv/bin/python scripts/run_encoder_role_transfer_pilot.py
```

结果文件：

- `results/summaries/encoder_role_transfer_pilot_v1/summary.json`
- `results/summaries/encoder_role_transfer_pilot_v1/rows.jsonl`
- `results/summaries/encoder_role_transfer_pilot_v1/protocol.json`

该 pilot 只支持“角色映射确实改变了跨 schema 的动作表示”这一接口性结论，不能替代 AgentDojo/ASB 的任务级安全评估。
