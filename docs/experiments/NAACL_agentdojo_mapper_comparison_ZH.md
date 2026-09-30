# NAACL AgentDojo：Qwen-Max 语义映射端到端对照

这份对照固定 AgentDojo v1.2.2 的 banking suite、Qwen-Max planner、CLAFR runtime 和 `important_instructions` 攻击；唯一变化是是否加载冻结的 mapper artifact。完整分母是 16 个 clean user task，以及 16 × 9 = 144 个 attack episode。

运行器为 `scripts/run_agentdojo_mapper_banking_full_v7.py`，比较器为 `scripts/aggregate_agentdojo_mapper_compare.py`。运行器保存 command、protocol、原始 episode JSON 和 stdout，不允许用删任务或重采样方式修正 utility。比较器要求观察到 clean=16、attack=144 后才输出可用于论文的结果；`--allow-partial` 仅用于调试。

原始 deterministic CLAFR 的已冻结 banking 结果来自 `results/summaries/agentdojo_v122_clafr_final_full_4suite_v1/autodojo_table_aggregate.json`：clean utility 为 15/16（93.75%），attack utility 为 123/144（85.42%），static ASR 为 0/144。该结果与新 mapper 运行使用相同的 banking 分母；模型和运行日期不同，因此论文中需明确这是 deterministic reference，而不是同一模型的 planner 对照。

完整 Qwen-Max mapper 运行结束后执行：

```bash
/tmp/dafr-jianghao-venv/bin/python3 \
  scripts/aggregate_agentdojo_mapper_compare.py
```

脚本会生成：

- `results/summaries/agentdojo_mapper_banking_full_v7/comparison.json`；
- 本文件的带数值版本；
- clean utility、attack utility、ASR 的 Wilson 95% CI；
- mapper abstention 消息数和 episode 数；
- 非 mapper runtime/消息错误数；
- 相对 deterministic reference 的百分点差值。

结果解释边界：`security=true` 计为攻击成功，`security=false` 计为攻击被阻断。mapper abstain、IR 编译失败、runtime block 和 planner 自身错误必须分开统计。只有当完整分母通过检查后，Qwen-Max mapper 结果才可进入论文主表；若 clean utility 没有超过 deterministic reference，应保留失败 episode 并优先分析 false block、abstention 和 compile/error 分布。

