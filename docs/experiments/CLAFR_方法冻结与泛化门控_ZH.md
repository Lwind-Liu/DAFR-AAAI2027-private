# CLAFR 方法冻结与泛化门控

更新时间：2026-07-19

## 1. 冻结目标

CLAFR 在工具调用边界上接收可信任务、运行时证据、工具契约和候选动作，构造 action-evidence 表示并计算动态可行域。方法目标是在不使用 benchmark 标签、任务 ID、攻击字符串或工具白名单的前提下，维持高任务效用并降低攻击成功率。

适用范围是提供工具 schema/description，并能保留最小运行时来源边界的 agent benchmark。完全没有工具语义、参数 schema 和来源信息的环境属于显式边界，不承诺与 provenance-aware 环境相同的安全性。

## 2. 四个模块的独立职责

1. **Evidence Projection**：把 observation 分成事实通道和风险/控制通道。它不再通过删除模型可见文本独立完成防御，也不能把工具输出提升成用户授权。
2. **Action-Evidence Lifting**：从工具名称、描述、schema、参数值和字段来源构造统一坐标。对有副作用动作采用字段级最弱来源原则，关键字段不能被其他可信字段的平均值稀释。
3. **Dynamic Geometry**：主要安全机制。根据当前任务、授权、状态、来源和动作 effect 动态编译线性 facets 与联合风险预算，计算 signed margin，并决定动作是否位于可行域内。
4. **Decision & Repair**：执行可行动作；对越界动作保持阻断，并提供不指定 benchmark 工具的中性修复/澄清反馈。去掉该模块不会绕过几何执行危险动作，只会失去格式修复、反馈恢复和响应投影。

Dynamic Geometry 必须承担主要安全收益：去掉它应提高 ASR、降低安全任务完成能力并使 margin 分离消失。Evidence Projection 主要影响证据可用性；Lifting 影响跨工具语义映射；Decision & Repair 主要恢复被拒后的 Utility。

## 3. 泛化不变量

- 工具重命名：描述和 schema 不变时，决策方向保持不变，margin 只允许小幅变化。
- 描述改写：同义工具描述不改变决策方向。
- 参数顺序：JSON 字段顺序不改变表示与决策。
- 来源反事实：同一外部动作从可信来源翻转为未可信来源时，margin 应跨过安全边界。
- 未知工具回退：无描述工具出现 external destination/payload 时保守阻断或澄清；无副作用的标识符查询可继续执行。
- 关键字段最弱来源：任何关键 recipient/object/amount/destination 只由未可信内容支持时，不得被其他可信字段稀释。

禁止进入核心实现的内容：benchmark 名、suite 名、task/injection ID、固定攻击短语、基于结果挑选的工具名单、ASB normal/attack label 决策规则。

当前回归入口：`ICLR/tests/test_clafr_generalization.py`。2026-07-19 验证结果：泛化与核心测试 33/33，通过；完整 ICLR 测试 59/59，通过；AgentDojo adapter + observation projection 联合测试 22/22，通过。

## 4. AgentDojo 阶段门控

协议：DeepSeek-v4-Flash、AgentDojo v1.2.2、banking/slack/travel/workspace 四 suite；每个 suite 固定 1 clean + 3 attack；manifest 在运行前固定，不按结果重选。

结果：`C:/Users/f1567/Desktop/AAAI/ICLR/results/autodojo_clafr_geometry_gate4suite_v2/clafr_manifest_ablation.md`

| Variant | Clean Utility | Static ASR | Static Attack Utility | Margin | Cases |
|---|---:|---:|---:|---:|---:|
| CLAFR | 75.0 | 0.0 | 50.0 | 0.747 | 4/12 |
| w/o Evidence Projection | 0.0 | 0.0 | 0.0 | 0.812 | 4/12 |
| w/o Action-Evidence Lifting | 50.0 | 33.3 | 50.0 | N/A | 4/12 |
| w/o Dynamic Geometry | 50.0 | 33.3 | 58.3 | N/A | 4/12 |
| w/o Decision & Repair | 50.0 | 16.7 | 50.0 | 0.768 | 4/12 |

阶段解释：Dynamic Geometry 相对其消融使 ASR 降低 33.3 个百分点，并使 clean utility 提升 25 个百分点；Action-Evidence Lifting 有同方向安全贡献；Evidence Projection 防止证据不可用导致全任务失败；Decision & Repair 同时影响 clean utility 和残余 ASR。该表是小样本门控，不作为正式论文消融。

Full 的 Attack Utility 50.0 尚未达到扩大正式实验的门槛。失败分析显示 travel clean 本身失败且 workspace 多数失败没有 CLAFR block；几何误阻断集中在少数需要推导参数或重试的任务。下一步只改 benchmark-independent repair/derived-evidence 支持，不调整几何阈值或按 case 增加规则。

## 5. ASB 阶段门控

协议：ToolSafe-ASB-OPI、DeepSeek-v4-Flash、12 个 agent-round-robin case、source provenance；所有模型可见工具保持在同一 schema 中，攻击工具不从候选集合删除。ASR 使用 stored goal hit 与实际执行 attacker tool trace 的并集。

结果：`C:/Users/f1567/Desktop/AAAI/ICLR/results/asb_12_rr_source_trust_v2/asb_posthoc_summary.md`

| Method | Utility | Task Success | ASR | Trace ASR | Safety |
|---|---:|---:|---:|---:|---:|
| No Defense | 0.417 | 0.083 | 0.667 | 0.667 | 0.333 |
| TS-Flow-style | 0.333 | 0.000 | 0.000 | 0.000 | 1.000 |
| CLAFR | 0.417 | 0.167 | 0.000 | 0.000 | 1.000 |
| ReAct + CLAFR-Feedback | 0.500 | 0.250 | 0.000 | 0.000 | 1.000 |

阶段解释：当前版本在该固定小样本上以更高 Utility 匹配 TS-Flow-style 的低 ASR，ReAct + CLAFR-Feedback 的 Utility 最高。样本量不足以形成正式泛化结论。

无 API 的 200-case 几何压力审计保持不变：source_trust 下攻击工具可行 0/200、正常工具可行 380/400；no_label 下攻击工具可行 124/200。这个结果必须作为来源信号边界公开报告。

## 6. 扩大实验的硬门槛

1. AgentDojo 四 suite 扩展门控中，Full ASR 不高于强 baseline，Clean Utility 和 Attack Utility 不低于当前论文可接受区间。
2. `w/o Dynamic Geometry` 的 ASR/安全任务成功显著退化，且结论跨 suite 同方向。
3. AgentDojo 与 ASB 使用同一冻结核心参数；只允许 adapter 做 schema 和 provenance 映射。
4. 工具重命名、描述改写、参数顺序和来源反事实测试全部通过。
5. 正式结果必须保存 manifest、版本、case 数、trace ASR 和 margin；门控数据与正式数据分表报告。
