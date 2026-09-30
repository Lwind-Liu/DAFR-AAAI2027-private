# 重命名 schema 的 mapper–encoder runtime benchmark

这组实验只验证一个可隔离的机制：当工具 schema 把对象字段命名为 `resource_key`、`entity_ref`、`opaque_object` 等时，旧的字段名启发式是否能够识别“对象必须来自可信状态”，以及经过验证的 role map 是否能把这个字段接入执行约束。

每个 case 固定同一个 `ToolAction` 和 `RuntimeEvidence`，两条路径共享同一个基础 `PolicyCompiler`：

* **Legacy rule**：`ConfidenceLiftedEncoder.encode(action, evidence)`，不提供 IR；
* **Role-only**：提供已验证的 `object`/`data` role map，但不注入字段级 grounding facet，用于隔离语义投影本身；
* **Mapper + encoder + grounding gate**：提供相同 role map，并将 `trusted_grounding(object)` 编译成 `LinearFacet`，再调用同一 selector。

每个重命名 schema 产生 8 个 clean/attack pair，共 8 个 schema、64 个 clean 和 64 个 attack。clean 的对象是可信状态中的 `case-*`；attack 使用不含 case 编号的 `attacker-rogue-object`，避免被数值共现启发式错误地当成可信对象。oracle 是 clean 必须 `ALLOW`，attack 必须 `BLOCK_OR_CLARIFY`。

| 路径 | clean allow | attack block | oracle 正确 | attack 对象 grounding recall | role trace 完整 |
|---|---:|---:|---:|---:|---:|
| Legacy rule | 64/64 | 0/64 | 64/128 | 0/64 | 不适用 |
| Role-only | 64/64 | 0/64 | 64/128 | 不单独计 | 128/128 |
| Mapper + encoder + grounding gate | 64/64 | 64/64 | 128/128 | 64/64 | 128/128 |

因此在这个受控 runtime benchmark 中，role map 本身只完成语义投影；从 Role-only 到完整路径的新增 64 个正确判决来自字段级 grounding gate。完整路径相比 legacy 增加 64 个 oracle-correct decisions，且没有牺牲 clean allow。它验证的是“经过验证的语义 role 能否驱动字段级 grounding gate”，不是 AgentDojo/ASB 的 utility 或安全率，也不代表任意新工具都能自动得到正确 role。

代码和结果：

* `scripts/run_renamed_schema_runtime_benchmark.py`
* `results/summaries/renamed_schema_runtime_benchmark_v1/summary.json`
* `results/summaries/renamed_schema_runtime_benchmark_v1/rows.jsonl`
* `results/summaries/renamed_schema_runtime_benchmark_v1/protocol.json`

复现不需要 API，也不执行外部工具：

```bash
cd /Users/haomin/Desktop/code/agent算法/DAFR/DAFR-AAAI2027-private
.venv/bin/python scripts/run_renamed_schema_runtime_benchmark.py
```

解释边界：该 benchmark 使用冻结的 gold role map 模拟已经通过 mapper validation 的输出，因此它证明 encoder/runtime 接口的可用性，不能单独证明 Qwen-Max mapper 在新 schema 上一定给出正确映射。论文若使用此结果，应把它放在 `role-conditioned encoder / renamed-schema transfer` 机制实验中，并另行报告真实 LLM mapper 的 mapping accuracy 和 abstention。
