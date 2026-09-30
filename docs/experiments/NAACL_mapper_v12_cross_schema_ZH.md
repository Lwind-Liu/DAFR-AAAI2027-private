# v12 跨 schema 与策略 paraphrase 映射评测

## 目的

v7--v11 的工具族和策略模板已经被 schema-aware 规则基线基本覆盖，不能据此宣称 Qwen-Max 优于规则。v12 重新冻结 24 个未见工具 case，覆盖 communication、finance、file、calendar、database 和 publishing；字段名称全部改写，策略混合中英文批准/确认表达，并保留 2 个上下文含糊 case。

LLM 和规则 mapper 只看到相同的公开输入：policy、tool schema、effect class 和字段描述。gold 不进入 mapper。两者都经过同一个 `ConstraintIR` validator、canonicalizer、compiler 和 scorer。

## 结果

| Mapper | 可编译 | 非歧义 exact | 歧义正确 abstain | under-constrained | over-constrained |
|---|---:|---:|---:|---:|---:|
| SchemaRule v1 | 14/24 | 1/22 | 2/2 | 11 | 5 |
| Qwen-Max + canonicalizer | 22/24 | 21/22 | 2/2 | 1 | 1 |

Qwen-Max 的 21/22 非歧义 exact 为 95.45%，规则 baseline 为 1/22（4.55%）。两种 mapper 都正确拒绝了 2 个含糊策略。Qwen-Max 平均 API 延迟为 5.31 秒；规则 mapper 为本地确定性执行，不把两者延迟直接混合比较。

Qwen-Max 唯一的非歧义错误是一个跨句指代案例：策略先要求授权 `counterparty_ref` 与 `credit_units`，后文用“两个金额相关字段”表达确认范围，模型把其中一个字段错误替换成了可信对象标识。该错误保留在结果中，没有从分母中删除。

## Prompt 修订

v12 暴露出两类可复现问题：

1. `批准/核准/允许/sign off` 容易被模型和 confirmation 混淆；
2. `scope flag`、`time zone context`、外部收款账户等新描述会触发 role 冲突。

随后加入了 authorization 与 confirmation 的对比 few-shot、trusted-state 同义表达、scope flag 语义和跨句字段指代规则。重跑后从第一次的 11/22 exact、5 个 over-constraint、2 个 under-constraint 提升到 21/22 exact、1 个 over-constraint、1 个 under-constraint。

## 论文可用结论

这组结果支持一个有限但有价值的结论：在未见工具名、字段名和策略表达发生变化时，LLM mapper 能够比同一 IR 上的 schema-aware 规则 baseline 保留更高的语义覆盖率，同时维持正确的 ambiguity abstention。它不证明 LLM 永远优于规则，也不构成端到端安全证明；v7--v11 的模板化结果仍应单独报告，不能与 v12 混为一个无条件泛化数字。

原始请求、响应、哈希、编译结果和逐 case 评分保存在：

```text
data/mapper_eval_zh_v12_test.jsonl
results/summaries/mapper_eval_zh_v12_qwen_test/
results/summaries/mapper_rule_baseline_v1/v12_rows.jsonl
```

复现实验：

```bash
PYTHONPATH=src .venv/bin/python scripts/build_mapper_eval_zh_v12.py
PYTHONPATH=src .venv/bin/python scripts/evaluate_schema_rule_baseline.py v12
PYTHONPATH=src .venv/bin/python scripts/run_mapper_eval_zh_v12_qwen.py
```

