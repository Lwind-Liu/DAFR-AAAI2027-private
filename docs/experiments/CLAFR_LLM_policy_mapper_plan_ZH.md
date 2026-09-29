# jianghao 分支执行状态

## 当前已实现

- Typed ConstraintIR、结构校验与 API mapper 接口。
- `IRPolicyCompiler` 将全局前置条件和风险预算附加到原 clafr 可信约束；原约束不会被替换。
- Selector 可选择 geometry / predicate 两个判决后端，共享特征、约束和候选排序。
- 字段级约束、forbidden_effects 暂不支持，会明确报错，不能静默丢弃。
- 明确区分未指定 schema 与空 schema，修复空 schema 验证漏洞。

## 已确认的边界

结构校验不能检测遗漏策略，不能保证自然语言映射正确。保留原约束只能保证在固定特征下不扩大原可行域。
role 映射将由 LLM 生成并经过确定性校验后接入 encoder。实验若在 held-out 工具上保持有效，可以支持“无需训练的跨工具语义适配”这一主张；它不能直接证明训练 encoder 有效。训练 encoder 只能作为同一 IR 接口上的蒸馏/降成本实现，并需单独评测。
一般 if/else 可以表达相同的斜半空间和范数约束，也可以配合候选搜索修复；之前“无法联合风险/无法修复”的说法撤回。

## 运行

使用 Python >=3.10，并安装 pytest、numpy。

```sh
python -m pytest tests/test_policy_mapper.py tests/test_ir_runtime.py tests/test_clafr.py tests/test_clafr_generalization.py
PYTHONPATH=src python scripts/check_clafr_predicate_equivalence.py
```

## 后续实验门槛

1. 接入 LLM role mapper 与 role 驱动 encoder 后，再做 held-out tool 泛化；mapper 的输出必须记录并冻结，不能边测边改。
2. 比较三种适配器：手工映射、LLM 映射、训练/蒸馏 encoder；三者消费同一 ConstraintIR 和同一执行层。
3. API prompt 必须提供完整 IR schema，记录模型、请求哈希、usage 和解析失败；不能只看成功返回 JSON。
4. 用同候选、同预算的 predicate repair 比较几何修复，测实际副作用而非只测特征投影。
5. AgentDojo/ASB 端到端重新运行后才允许更新论文数字；旧数字不自动继承到新方法。

论文工作稿：`paper/revision/jianghao_method_revision.md`。
