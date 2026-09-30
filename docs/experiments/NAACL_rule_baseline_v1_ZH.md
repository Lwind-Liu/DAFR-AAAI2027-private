# P1：可复现的 schema-aware 规则映射基线（2026-09-30）

## 目的

为避免把一个很弱的手写 fixture 当作规则基线，新增 `SchemaRulePolicyMapper`。它与 Qwen-Max mapper 使用相同输入边界、相同 `ConstraintIR`、相同 validator/compiler 和相同语义评分器。规则 mapper 只能读取：工具名、schema 字段、自然语言 policy、effect class、可信字段描述；gold IR 只在评估器中使用。

该基线不是 per-tool gold lookup，也不读取测试集的 `gold` 字段。它用字段描述进行 role 归类，用 policy 中显式出现的授权、确认、可信来源和新鲜度短语抽取前置条件。遇到“根据上下文适当……”这类没有可执行安全条件的策略时返回 abstain。

## 运行命令

```bash
cd /Users/haomin/Desktop/code/agent算法/DAFR/DAFR-AAAI2027-private
PYTHONPATH=src .venv/bin/python scripts/evaluate_schema_rule_baseline.py
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_rule_mapper.py tests/test_policy_mapper.py
```

结果目录：`results/summaries/mapper_rule_baseline_v1/`。其中 `summary.json` 保存版本、输入哈希、每条输出和评分；mapper 运行时不会读取 gold。

## 结果

| held-out 集 | 全部样例 | 非歧义样例 | 可编译 | 非歧义 exact | 歧义 abstain | under/over |
|---|---:|---:|---:|---:|---:|---:|
| v7 | 10 | 9 | 9 | 9/9 | 1/1 | 0/0 |
| v8 | 10 | 9 | 9 | 9/9 | 1/1 | 0/0 |
| v9 | 8 | 7 | 7 | 7/7 | 1/1 | 0/0 |
| v10 | 8 | 7 | 7 | 7/7 | 1/1 | 0/0 |
| v11 | 6 | 5 | 5 | 5/5 | 1/1 | 0/0 |
| **合计** | **42** | **37** | **37** | **37/37** | **5/5** | **0/0** |

此前 Qwen-Max 的 v7–v11 canonicalized 结果为 36/37 非歧义 exact（v10 有 1 个角色错误），因此在当前模板化 held-out 协议上，schema-aware 规则基线并不劣于 LLM。这个结果必须如实报告，不能用它声称 LLM 显著优于规则。

## 对论文主线的影响

这个结果暴露了当前 mapper benchmark 的饱和问题：策略文本中的字段名和安全动词高度规则化，确定性 parser 已经可以恢复 gold。它仍然有两个价值：

1. 提供了真正匹配的 deterministic baseline，避免和弱 `StaticPolicyMapper` 比较造成虚假提升；
2. 说明后续应把 mapper 的科学问题从“固定模板上的 exact match”推进到跨语言 paraphrase、字段同义改名、隐式作用域、跨句指代和受控歧义，而不是继续堆 prompt。

下一轮应冻结一组不暴露字段名的 paraphrase/renaming 测试，并把 role accuracy、precondition exact、unsafe relaxation、over-constraint、abstention、延迟和 token cost 分开报告。规则基线和 LLM 必须继续使用同一个 IR/compiler/runtime；如果新测试上 LLM 不能在安全错误率或覆盖率上超过规则基线，应收缩“LLM 泛化”表述，把贡献重点放到统一语义接口和执行层。
