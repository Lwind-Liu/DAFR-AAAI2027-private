# 论文文件

- `main/DAFR_AAAI2027_Main_Current.tex`：当前正文源码，主线为 typed action--evidence encoding、joint-risk geometry 和 execution certificate。
- `supplement/DAFR_AAAI2027_Supplement_Current.tex`：当前补充材料源码，包含完整 baseline 表、系统消融和 matched geometry 对照。
- `revision/jianghao_method_revision.md`：当前中文修订决策与投稿前检查清单。
- `main/From_Semantics_to_Execution_Dynamic_Geometric_Constraints_for_Tool-Action_Feasibility_Figure_*.pdf`：正文引用的图文件。

当前目录中的 PDF 已按最新源码重新生成，可用于内容和版式预览；它们仍是 AAAI 模板下的 XeTeX 预览，不是 NAACL/ARR 最终提交文件。正式投稿前仍需切换到 ACL/ARR review 模板，并用 PDFLaTeX（或模板要求的引擎）重新生成正文和补充材料。

如果本机的 Tectonic 默认 relay 返回 403，可显式指定可访问的官方 bundle 镜像：

```bash
tectonic -X compile \
  --web-bundle https://data1.fullyjustified.net/tlextras-2022.0r0.tar \
  main/DAFR_AAAI2027_Main_Current.tex
```

仓库内的 `aaai2027.sty` 在 PDFLaTeX 下保持原有严格检查；仅在 XeTeX 预览时放行，并在日志中提示正式提交仍使用 PDFLaTeX。

## 2026-10-01 audit

- `results/summaries/geometry_paper_audit_20261001/summary.json`：在独立的冻结机制重跑中核对 512 个联合风险向量和 256 个修复案例；结果为轴向阈值 25/25 false allow，几何与等价谓词 0/512 分歧，双方修复 192/192 个可修复动作。
- 57/389 是只含 Banking、Slack、Travel 的历史三套件子集；正文的 canonical AgentDojo 协议是四套件 71/585。两者不得在同一张主结果表中混用。
- 多模型 baseline 图中的 GPT 行含历史三套件汇总与 Workspace 重跑，已在补充材料中披露为 archival aggregate，不能描述为统一的新鲜四套件重跑。
