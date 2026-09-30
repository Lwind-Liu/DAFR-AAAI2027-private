# NAACL 鲁棒性与动作级修复评测（v1）

## 目的和范围

这组实验补齐 P3/P4 的真实运行时压力测试。它固定同一个
`clafr` encoder、ConstraintIR、compiler、selector 和候选动作，只改变
工具字段命名、策略/任务措辞、状态新鲜度以及不可信通道内容。实验在进程内
完成，不调用外部模型或真实工具；动作效果由本地 effect model 验证，因此不会
把 dry-run 误报成真实外部安全保证。

运行命令：

```bash
cd /Users/haomin/Desktop/code/agent算法/DAFR/DAFR-AAAI2027-private
PYTHONPATH=src .venv/bin/python scripts/run_naacl_robustness_repair_v1.py
```

随机种子为 `20261001`。逐例结果和汇总位于：

```text
results/summaries/naacl_robustness_repair_v1/
  field_rename_rows.jsonl
  stress_rows.jsonl
  repair_rows.jsonl
  summary.json
```

## 结果

### 字段改名与策略 paraphrase

64 个 case 在 8 组非标准字段 schema 上运行，每组交替包含一个有可信授权的
合法动作和一个由不可信内容诱导的外部动作。字段包括
`target_mailbox`、`assignee_ref`、`endpoint_hint`、`storage_endpoint`、
`beneficiary_ref` 等。IR 显式声明 object/destination/data role，避免把结果
归因于字段名启发式。

| 指标 | 结果 |
|---|---:|
| 正确决策 | 64/64（100%，Wilson 95% CI [94.34%, 100%]）|
| 合法动作放行 | 32/32 |
| 攻击动作阻断 | 32/32 |

这一结果只证明：经过验证的 role-aware IR 在这些字段改名和措辞变体下保持运行时
行为。它不等价于 LLM mapper 在未见 schema 上的 exact accuracy；后者由 v12
mapper set 单独测量。

实现上修复了一个会影响泛化的编码问题：旧的 `critical_field_grounding`
只认识 `recipient/body/amount` 等常见字段名，导致 `payload_bytes` 或
`message_payload` 在已由 IR 声明时仍得到零分。现在对 mapper 声明的字段直接
计算可信文本中的 literal grounding，并继续保留不可信值覆盖检查。

### stale state 与 adaptive injection

64 个 case 发送四种变体的攻击文本，包括伪造“用户已经批准”、要求忽略策略、
以及中文网页指令。攻击动作的 destination 和 payload 只出现在不可信通道；
可信状态只保存 object handle。另加入 `state_freshness >= 0.8` 的显式 IR 前置
条件。

| 指标 | 结果 |
|---|---:|
| 正确阻断 | 64/64（100%，Wilson 95% CI [94.34%, 100%]）|
| adaptive injection 阻断 | 64/64 |
| freshness ≥ 0.8 的攻击仍阻断 | 32/32 |
| freshness < 0.8 的 stale state 阻断 | 32/32 |

不可信文本从未进入 `trusted_authorizations` 或 `trusted_state`，所以不能满足
授权。该 suite 不能替代 AgentDojo/ASB 的自适应攻击，只能证明 provenance
边界和 freshness facet 在同一 runtime 内没有被伪造文本绕过。

### 多工具动作级 repair

256 个动作来自四个写工具别名：`modify_record`、`update_record`、
`edit_record` 和 `change_record`。192 个动作含有可以安全删除的不可信可选
`destination`，64 个动作把 destination 声明为必需参数，正确行为是保持阻断。
每个修复后的动作都通过本地 effect model：record id 必须仍为 `7`，amount
必须保持可信目标值。

| 后端 | 可执行修复 | 说明 |
|---|---:|---|
| Geometry native repair | 192/256（75.0%，CI [69.35%, 79.91%]） | 192 个可修复，64 个必需字段保持阻断 |
| Equivalent predicate + 同一 oracle | 192/256（75.0%） | 与 Geometry 完全一致 |
| Bool-only predicate | 0/256 | 没有动作变换或 repair 接口 |

Geometry 与 predicate 的成功分歧为 0，effect preservation 为 192/192，unsafe
repair 为 0，外部副作用为 0。这个 matched 结果不支持“几何数学形式自身比
predicate 更强”的说法；它支持的说法是：带 margin/facet/provenance 的执行
证书可以连接到可验证的动作变换，而只返回 bool 的接口无法完成该连接。

## 论文中的使用边界

主表可以将这组结果作为 runtime robustness/repair 分析，和 v12 mapper
semantic exact、AgentDojo 端到端任务结果分开。不要把进程内 100% 阻断写成
通用 ASR 保证，也不要把 75% repair 成功率写成真实工具副作用上的成功率。
正式投稿前仍需在冻结的 AgentDojo/ASB task split 上运行相同的字段改名、stale
state、adaptive injection 和候选动作 repair，并报告 task utility、误阻断、
clarification、实际 replay 以及真实副作用标签。
