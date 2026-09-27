# DAFR：动态动作可行域

本私人仓库对应 AAAI 2027 论文《From Semantics to Execution: Dynamic Geometric Constraints for Tool-Action Feasibility》，整理了截至 2026-09-27 的当前论文、补充材料、代码、数据、实验配置、结果和审稿意见，供论文合作者下载、复现和同步修改。

## 建议阅读顺序

1. 当前论文与补充材料：[`paper/README.md`](paper/README.md)
2. 审稿意见和中文翻译：[`reviews/README.md`](reviews/README.md)
3. 代码说明：[`docs/CODE_GUIDE.md`](docs/CODE_GUIDE.md)
4. 汇总结果：[`results/README.md`](results/README.md)
5. 原始结果压缩包：[`release_assets/README.md`](release_assets/README.md)
6. 下载、上传和同步：[`docs/COLLABORATION_WORKFLOW.md`](docs/COLLABORATION_WORKFLOW.md)

## 仓库结构

| 路径 | 内容 |
|---|---|
| `paper/` | 当前匿名正文、补充材料、LaTeX 源码、参考文献和图表。 |
| `reviews/` | AAAI-27 决定、两份人工审稿、AI 审稿、对应中文翻译和修改追踪表。 |
| `src/clafr/` | 论文主要动作—证据表示、约束编译、几何决策和选择器实现。 |
| `src/geoconstraints/` | AgentDojo 集成所需的投影、约束和运行时工具。 |
| `scripts/` | AgentDojo、ASB、多模型、消融、审计和结果聚合脚本。 |
| `tests/` | 主实验工程的单元测试和集成测试。 |
| `experiments/manifests/` | 补充实验协议。 |
| `method_reference/` | 与论文算法描述对应的紧凑参考实现。 |
| `external/` | 本地修改过的 AgentDojo 代码及 ToolSafe/ASB 数据切片。 |
| `data/` | 可直接下载的 AgentDojo、ASB 数据和冻结实验清单。 |
| `results/summaries/` | 支撑论文表格的 CSV、JSON 和 Markdown 汇总结果。 |
| `release_assets/` | 精选原始结果 ZIP，每个文件均低于 GitHub 100 MB 限制。 |
| `docs/` | 代码、实验、仓库结构、私有权限和协作说明。 |

实现和旧结果中仍使用历史内部名称 `CLAFR`，当前论文使用公开名称 `DAFR`。为保持代码、结果路径和审计记录可追溯，没有对算法标识进行批量改名。

## Windows PowerShell 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip install -e ".\external\official_baselines\AutoDojo\agentdojo"

$env:PYTHONPATH = "$PWD\src;$PWD\external\official_baselines\AutoDojo\agentdojo\src"
python -m pytest -q .\tests
python -m pytest -q .\method_reference\tests
```

单元测试不会调用付费模型 API。重新运行模型实验需要按照对应脚本设置模型供应商环境变量。本仓库不包含 `.env` 或真实凭据。

## 编译论文

```powershell
Push-Location .\paper\main
pdflatex -interaction=nonstopmode -halt-on-error DAFR_AAAI2027_Main_Current.tex
Pop-Location

Push-Location .\paper\supplement
pdflatex -interaction=nonstopmode -halt-on-error DAFR_AAAI2027_Supplement_Current.tex
Pop-Location
```

正文目录中已包含 `.bbl`。参考文献发生变化后，应重新运行 BibTeX，再运行两次 LaTeX。

## 版本和完整性

- 原始 `AAAI 2027 ALL` 是历史归档，不是全部文件都最新。
- 当前版本选择依据见 [`VERSION_AUDIT.md`](VERSION_AUDIT.md)。
- 文件大小和 SHA-256 见 [`UPLOAD_MANIFEST.csv`](UPLOAD_MANIFEST.csv) 与 [`SHA256SUMS.txt`](SHA256SUMS.txt)。
- 旧归档遗漏的 `src/geoconstraints/` 和 `clafr_adaptive_attacks.py` 已从原实验工作区补回。

## 私有协作和许可

本仓库必须保持 **Private**，仅向论文合作者授权。权限检查见 [`docs/PRIVATE_ACCESS_CHECKLIST.md`](docs/PRIVATE_ACCESS_CHECKLIST.md)。项目尚无明确的顶层开源许可证；在作者确定许可并核清第三方再分发条件前，不得公开仓库。

