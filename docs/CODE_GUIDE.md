# 代码说明

## 两个核心代码包

### `src/clafr/`

这是当前论文实验的主要算法实现。它把候选工具动作从 `tool_name + arguments` 提升为“动作—证据”向量，涉及任务一致性、工具可供性、参数来源、可信授权、状态依据、风险、提示注入一致性和置信度。

主要文件：

- `schemas.py`：数据结构和接口。
- `features.py`：动作与证据特征。
- `projection.py`：动作—证据投影。
- `compiler.py`：策略和约束编译。
- `geometry.py`：半空间、可行域和间隔计算。
- `selector.py`：候选动作选择与执行决策。
- `baselines.py`：对比基线。
- `demo.py`：最小演示。

### `src/geoconstraints/`

这是较早形成、但当前 AgentDojo 集成仍需要的通用工具包，包含策略加载、语义映射、运行时验证、观测约束投影、离线检查和指标工具。它与 `src/clafr/` 的职责有重叠，但当前测试和集成仍同时依赖两者，因此暂不合并。

## 其他代码目录

- `scripts/`：实验运行、恢复、聚合和审计脚本。
- `scripts/figures/`：结果图和半空间示意图生成脚本。
- `tests/`：90 项主工程测试。
- `method_reference/`：与论文公式和伪代码对应的简化参考实现，含 18 项测试。
- `external/official_baselines/AutoDojo/agentdojo/`：本地修改过的 AgentDojo 基准代码。
- `external/official_benchmarks/ToolSafe/`：ASB/ToolSafe 数据和配置切片。

## 运行测试

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD\external\official_baselines\AutoDojo\agentdojo\src"
python -m pytest -q .\tests
python -m pytest -q .\method_reference\tests
```

## 目录迁移说明

这些文件原先位于历史目录 `ICLR/`。为避免合作者误解，已按职责迁移：

| 原路径 | 当前路径 |
|---|---|
| `ICLR/src/clafr/` | `src/clafr/` |
| `ICLR/scripts/` | `scripts/` |
| `ICLR/tests/` | `tests/` |
| `ICLR/docs/` | `docs/experiments/` |
| `ICLR/experiments/` | `experiments/` |
| `ICLR/manifests/` | 已删除重复副本，保留 `data/manifests/` |
| `ICLR/draw*.py` | `scripts/figures/` |

历史结果和实验文档中出现的旧绝对路径仅作为来源记录保留，不代表当前运行路径。

