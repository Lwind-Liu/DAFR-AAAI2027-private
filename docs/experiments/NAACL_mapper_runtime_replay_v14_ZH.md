# v14 Mapper → Runtime 下游传递实验

## 目的

v14 原本只测 semantic mapping accuracy。本实验把同一批冻结的 Qwen-Max IR 和 schema-rule IR 直接接入同一个 `IRPolicyCompiler` 与 action selector，检查语义映射是否能传递到字段级执行判定。

每个非歧义 case 生成一对固定动作：clean 动作使用可信 object 值，attack 动作只把 object 替换为 `attacker-rogue-object`。两臂共享完全相同的 action、evidence、compiler baseline 和 scorer。trusted state、authorization、confirmation 均只包含 clean 值。实验不调用 planner、API 或真实工具。

## 结果

| 执行臂 | 编译 clean case | clean allow | attack block | oracle-correct |
|---|---:|---:|---:|---:|
| Legacy（无 IR） | 20/20 | 20/20 | 2/20 | 22/40 |
| SchemaRule v2 | 20/20 | 20/20 | 4/20 | 24/40 |
| Qwen-Max IR | 18/20 | 18/20 | 18/20 | 36/40 |
| Gold IR oracle | 20/20 | 20/20 | 20/20 | 40/40 |

Qwen-Max 的两个未编译 case 保持显式 abstain，不被计为 attack allow。对已经编译的 18 个 case，clean 全部放行，rogue object 全部阻断。规则 mapper 虽然全部编译，但只阻断 4/20 个 rogue object，说明结构合法不等于语义覆盖。

## 可写入论文的结论

该实验支持一个更窄且更强的归因：held-out semantic mapping 的收益可以传递到共享执行层；Qwen-Max 的 IR 在 18 个可编译 case 上保留 clean allow 并阻断 rogue object。它不能替代 v14 mapping accuracy，也不能被写成 AgentDojo utility 或真实环境安全率。两个 abstain case 应保留在 coverage 分母中，不能删除以提高结果。

复现：

```bash
cd /Users/haomin/Desktop/code/agent算法/DAFR/DAFR-AAAI2027-private
PYTHONPATH=src .venv/bin/python scripts/run_mapper_runtime_replay_v14.py
```

结果位于 `results/summaries/mapper_runtime_replay_v14/`。
