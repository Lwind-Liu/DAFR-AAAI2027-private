# 仓库结构与命名规则

```text
.
├── README.md                  # 中文总入口
├── paper/                     # 当前正文、补充材料和图表
├── reviews/                   # 决定、审稿、中文翻译和追踪表
├── src/clafr/                 # 主要算法实现
├── src/geoconstraints/        # 通用约束与 AgentDojo 集成工具
├── scripts/                   # 实验、聚合、审计和绘图脚本
├── tests/                     # 主工程测试
├── experiments/manifests/     # 补充实验协议
├── method_reference/          # 论文级参考实现
├── external/                  # 第三方基准及本地修改
├── data/                      # 数据切片和冻结清单
├── results/summaries/         # 可审阅的汇总结果
├── release_assets/            # 精选原始结果压缩包
├── docs/                      # 中文协作与实验说明
├── UPLOAD_MANIFEST.csv        # 路径、大小和 SHA-256 清单
└── SHA256SUMS.txt             # SHA-256 校验列表
```

## 命名规则

- 新文件和目录优先使用简短、明确的英文 `snake_case`，中文说明写在 README 中。
- 上游依赖、冻结结果、基准 ID 和 Python 包名保持原名，避免破坏导入和来源追踪。
- 真正的快照才使用 `YYYYMMDD` 日期后缀，不使用 `(1)`、`final_final` 等含糊命名。
- 当前论文放入 `paper/`，审稿放入 `reviews/`，汇总结果放入 `results/summaries/`，大型原始轨迹放入 `release_assets/`。
- 缓存、虚拟环境、凭据和未确认的临时结果不得提交。

