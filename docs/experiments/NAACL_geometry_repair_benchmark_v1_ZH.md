# 几何、等价 predicate 与动作修复对照（v1）

## 实验目的

本实验把三个容易混在一起的命题分开验证：

1. **朴素逐维 ifelse 是否漏掉联合风险**：`Axis-ifelse` 对每个风险维度独立判断 `r_i <= 0.8`。
2. **几何判决是否与等价 predicate 一致**：`Equivalent-predicate` 复用同一 `RiskBudgetCone` 的约束，理论上必须与 Geometry 完全一致；若不一致，说明实现错误，不能算作方法收益。
3. **修复收益是否来自几何本身**：`Predicate+oracle` 与 Geometry 使用同一个可执行字段删除修复器；如果二者相同，不能声称几何天然提供更强修复能力。`Bool-only predicate` 只返回真假，用于展示没有诊断/修复接口时的基线行为。

所有动作候选、encoder、compiler 和可信/不可信证据对各后端相同。实验只在进程内运行，不调用真实外部工具，因此没有外部副作用。

## 运行命令

```bash
cd /Users/haomin/Desktop/code/agent算法/DAFR/DAFR-AAAI2027-private
PYTHONPATH=src .venv/bin/python scripts/run_geometry_repair_benchmark_v1.py
```

固定随机种子为 `20260930`。原始逐案例记录和汇总文件位于：

```text
results/summaries/geometry_repair_benchmark_v1/
  joint_rows.jsonl
  repair_rows.jsonl
  summary.json
```

## 联合风险结果

联合风险套件包含 512 个四维风险向量。每个样本随机选择两个非零风险维度，且每一维都不超过 `0.8`；因此 Axis-ifelse 不会触发，样本仍可能违反半径为 `1.0` 的联合预算。

| 后端 | 放行数 | 放行率 | 95% Wilson 区间 |
|---|---:|---:|---:|
| Axis-ifelse | 512/512 | 100.0% | [99.26%, 100.0%] |
| Geometry joint cone | 487/512 | 95.12% | [92.89%, 96.67%] |
| Equivalent-predicate | 487/512 | 95.12% | [92.89%, 96.67%] |

Axis-ifelse 错误放行 25/512（4.88%，95% 区间 [3.33%, 7.11%]）。这些样本满足每个独立阈值，却违反联合风险范数。Geometry 与 Equivalent-predicate 的判决分歧为 `0/512`。

单次进程内测得 Geometry 平均判决耗时约 `0.0032 ms`，predicate 约 `0.0010 ms`。该样本只用于实现 sanity check，不能据此宣称速度优势；事实上 bool predicate 更快。

## 动作级修复结果

动作套件包含 256 个相同候选动作。192 个案例的动作含有不可信、可删除的可选 `destination`；64 个案例把 `destination` 标记为必需参数，正确行为是阻断而不是删除必需字段。

| 后端 | 阻断数 | 可执行修复成功 | 说明 |
|---|---:|---:|---|
| Geometry + native repair | 256/256 | 192/256（75.0%） | 192 个可修复，64 个按预期阻断 |
| Predicate + 同一 repair oracle | 256/256 | 192/256（75.0%） | 与 Geometry 完全一致 |
| Bool-only predicate | 256/256 | 0/256（0.0%） | 没有字段变换、margin 或 repair 接口 |
| Block-only | 256/256 | 0/256（0.0%） | 安全但牺牲可恢复效用 |

Geometry 和 Predicate+oracle 的 repair 成功率 95% Wilson 区间相同，均为 `[69.35%, 79.91%]`；阻断判决分歧为 `0/256`。整个动作套件的外部副作用为 `0`。

动作级结果支持的精确结论是：

- 共享修复 oracle 后，几何与等价 predicate 的安全判决和修复效用相同；不能把修复收益归因于“几何数学形式本身”。
- 相比只返回 bool 的 predicate，带有 margin、违规约束和可执行字段修复接口的 runtime 可以恢复 192 个原本可安全修复的动作。
- 对必需 `destination` 的 64 个案例，系统没有删除必需字段，全部保持阻断，说明修复器没有以牺牲动作语义为代价追求放行率。

## 论文中的推荐表述

可以写：

> Independent axis checks accepted all 512 boundary-active candidates, including 25 candidates whose joint risk exceeded the shared budget. A single joint-risk region and its equivalent predicate rejected the same 25 candidates. This isolates the practical failure mode of naive per-dimension branches rather than claiming that geometry is more expressive than arbitrary arithmetic code. In the action-level suite, Geometry and a predicate equipped with the same repair oracle both recovered 192/256 executable actions, whereas a bool-only predicate recovered none. The measured benefit is therefore a unified certificate/diagnostic/repair interface; it is not an intrinsic speed or expressiveness advantage of geometry.

中文可以表述为：

> 逐维阈值判断在 512 个边界样本中全部放行，其中 25 个动作的联合风险已经超过共享预算。几何区域和表达同一约束的 predicate 拒绝了完全相同的 25 个动作。该结果说明朴素分支会漏掉耦合风险，但不意味着几何比任意算术程序更有表达能力。在动作级修复实验中，Geometry 与配备同一修复 oracle 的 predicate 都恢复了 192/256 个可执行动作，而只返回 bool 的 predicate 一个也无法修复。因此可归因的贡献是统一的证书、诊断和修复接口，而不是几何天然更快或更强。

## 仍需补充

当前实验仍是合成且无外部副作用的 runtime benchmark。正式投稿前需要把相同的四类比较接入冻结的真实工具任务集，并报告任务级而非仅进程级指标：安全放行率、误阻断率、可执行修复成功率、动作效果保持率、unsafe repair rate、clarification rate、额外延迟和调用成本。若真实任务上的 Predicate+oracle 与 Geometry 仍然持平，应保留“统一接口和可维护执行证书”的叙事，删除“几何带来额外安全性/修复能力”的表述。
