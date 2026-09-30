# 固定消息前缀的 mapper 执行边界回放

该实验将每个已保存 assistant 工具调用的消息前缀固定，使用真实 AgentDojo Banking v1.2.2 工具 schema 和 CLAFR `_build_evidence` 重建一份证据。同一动作、同一证据、同一基础 PolicyCompiler 分别进入 no mapper 和 v3 roles-only mapper。这里没有调用 API，也没有执行工具或反事实计算任务 utility。

代码版本：`158f5a9e7bc3ee708fda111ca8d1bf50b54acdb4`。输入 320 条 episode，发现 614 次 saved calls，成功比较 610 次。异常调用单列，不算 mapper 语义失败。

| 来源 | 保存调用 | 可比调用 | 判决差异 | 特征差异 | margin 差异 | constraint 差异 |
|---|---:|---:|---:|---:|---:|---:|
| `agentdojo_mapper_banking_roles_only_reencode_v2_full_escalated` | 309 | 308 | 0 | 0 | 0 | 0 |
| `agentdojo_no_mapper_banking_reencode_full` | 305 | 302 | 0 | 0 | 0 | 0 |

状态计数：`{"compared": 610, "malformed_call": 4}`。

允许/阻断配对：`{"ALLOW -> ALLOW": 546, "BLOCK_OR_CLARIFY -> BLOCK_OR_CLARIFY": 64}`。数值容差 1e-12。

历史日志核验（各 equal 字段值是 mismatch 数，不是 match 数）：`{"available": 610, "decision_equal": 0, "logged_features_equal": 0, "execution_margin_equal": 0, "violated_constraints_equal": 0, "counter_meaning": "Each field above counts mismatches, not matches."}`。

## 重建边界

原始 run 没有保存完整的私有 hidden provenance ledger、原始未投影 tool output 和 opaque binding。默认按 saved tool content 回收 hidden blocks，并按 adapter 的去重、截断顺序重建可见部分；两比较分支共享这份证据。原日志只保存六项特征、decision、execution margin 和 violated constraints，故历史核验全部一致也不能证明全部隐藏状态已经还原。

本实验只测试这些固定边界的表示和执行判定。后续消息永远使用原保存轨迹，不会因回放分支改变而重规划；因此不能据此声称端到端 utility 无退化、修复保持原始效果或一般安全保证。repair 只记录本地生成候选，未验证最终效果。

`rows.jsonl` 包含两组完整数值特征、margin、constraint、role trace 及 parity；`inputs.jsonl` 保存共享 action/evidence 快照；`manifest.json` 保存全部 source trace、adapter、输入 artifact 和 code hashes。运行前后会校验文件未改变。

## 复现

```bash
cd '/Users/haomin/Desktop/code/agent算法/DAFR/DAFR-AAAI2027-private'
.venv/bin/python scripts/replay_agentdojo_mapper_boundary.py
```

若需检查隐藏 ledger 回收假设，可另用 `--hidden-ledger empty --output-dir results/summaries/agentdojo_mapper_boundary_replay_empty --doc docs/experiments/NAACL_mapper_boundary_replay_empty_ZH.md`；这仍是受限的 saved-prefix replay，不能当作原始环境完整重放。
