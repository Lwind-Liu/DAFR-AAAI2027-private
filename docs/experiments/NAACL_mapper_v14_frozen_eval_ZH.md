# v14 独立 Mapper 评测

## 协议

v14 在 prompt 调整完成后重新构造并立即冻结，未把模型输出用于修改 split。数据包含远程部署、访问控制、文档签署、采购四个域，每域 5 个明确策略和 1 个确实缺少约束信息的 abstain case，共 24 个 case（20 个 non-ambiguous、4 个 abstain）。工具名和字段名均为新 alias；gold 不发送给模型。

数据文件：`data/mapper_eval_zh_v14_frozen.jsonl`。

SHA-256：`859da39ec7e5fd1b0fcdbfaf05735547a77cb315f9ce20bb01885d202afeb05a`。

构造与离线 gold 校验：

```bash
PYTHONPATH=src .venv/bin/python scripts/build_mapper_eval_zh_v14.py
```

20/20 non-ambiguous gold 通过 `ConstraintIR` validator 和 `IRPolicyCompiler`；4 个 abstain case 不进入执行层。

## 结果

Qwen-Max 使用当前 mapper prompt、canonicalizer、validator、compiler 和 scorer，一次调用每个 case：

| 方法 | 编译通过 | non-ambiguous exact | 正确 abstain |
|---|---:|---:|---:|
| SchemaRule v2 | 20/24 | 1/20 | 4/4 |
| Qwen-Max + semantic gate | 18/24 | 16/20 | 4/4 |

Qwen-Max 的 4 个非歧义失败中，2 个是 validator 拒绝的 role 冲突，2 个是模型输出无法编译；没有 under-constrained 或 over-constrained 的已编译候选。SchemaRule v2 通过 generic field-description rules 提高了编译覆盖，但在 18 个已编译 non-ambiguous candidates 中仍有 17 个 requirement/role mismatch。结果文件为 `results/summaries/mapper_eval_zh_v14_qwen_test/summary.json` 和 `results/summaries/mapper_eval_zh_v14_rule_test/summary.json`。

Qwen raw result SHA-256：`5422c44ad1c408e698feabac732805d1f53a513933e97d8009329e676b023a59`。

## 如何写进论文

v14 支持“语义 mapper 在未见 schema 上显著超过固定字段规则”的方向，但不能写成普遍正确率或端到端安全证明。主文保留 v12 的冻结对照作为主要表格；v14 作为独立复核，证明优势没有依赖 Banking 工具名。角色迁移仍需与 64-case encoder audit 和固定前缀 boundary replay 分开报告。
