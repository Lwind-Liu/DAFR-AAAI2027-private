# AgentDojo 真实动作边界 replay：Geometry 与等价 predicate

## 目的

该实验把已保存的 AgentDojo action/evidence 边界重新送入几何执行器，并在同一组约束 margin 上运行等价 predicate。它补充 512-case 受控实验，但不重新调用 planner、API 或外部工具，因此不宣称新的 utility 或 ASR。

## 协议

- 输入：既有 fixed-prefix replay 的 614 条保存动作，其中 610 条格式有效，4 条 malformed call 排除。
- Geometry：读取冻结边界记录的可行性和 execution certificate。
- Equivalent predicate：对相同 hard-constraint slack 做逐项 `slack >= 0` 判断。
- 外部工具执行：0；API 调用：0。

运行：

```bash
PYTHONPATH=src .venv/bin/python scripts/run_agentdojo_geometry_boundary_replay.py
```

## 结果

| 指标 | 结果 |
|---|---:|
| 有效真实 action/evidence 边界 | 610/614 |
| Geometry allow | 546/610 |
| Geometry block/clarify | 64/610 |
| Geometry 与 equivalent predicate 分歧 | 0/610 |
| 具有 decision + execution margin certificate | 610/610 |
| 外部副作用 | 0 |

64 个被阻断边界中，最常见的 violated facet 是 `critical_field_grounding_floor`（43 次）和 `trusted_over_untrusted_direction`（36 次）。一个边界可同时违反多个 facet，因此计数不相加为 64。

## 结论边界

该 replay 证明几何执行证书可以在真实 AgentDojo 保存的动作/证据边界上稳定重放，并与同一约束的 predicate 完全一致；它不证明新的 planner utility、端到端 ASR 或外部执行安全性。正文将它作为真实边界接口审计，和 AgentDojo/ASB 完整任务结果、512-case 联合风险实验分开报告。
