# Version audit

Audit date: 2026-09-27

## Conclusion

The original `AAAI 2027 ALL` folder is a historical archive, not a uniformly current release tree. It contains valid current artifacts, frozen submission copies, later edits, duplicate files, historical versions, caches, and a stale root checksum manifest.

## Selected current artifacts

| Component | Selected source | Evidence |
|---|---|---|
| Main paper | `02_当前论文与附录/.../DAFR_AAAI2027_Current_Source/` | The main `.tex` matches the active `Desktop/正文/Paper` copy by SHA-256 and recompiles to an 8-page PDF without LaTeX warnings. |
| Supplement | `02_当前论文与附录/.../DAFR_AAAI2027_Supplement_Current_Source/` | Updated on 2026-07-30, later than the 2026-07-28 `Desktop/正文` copy; recompiles to a 3-page PDF without LaTeX warnings. |
| Experiment code | `06_算法与复现代码/ICLR实验工程_代码与配置/` | Its 363 non-result, non-cache files match the original `Desktop/AAAI/ICLR` workspace byte-for-byte. |
| Missing integration utilities | `Desktop/AAAI/src` and modified AgentDojo source | Required by the archived tests but omitted from the old packaged code. Restored here. |
| Paper-level reference code | `06_算法与复现代码/DAFR_方法论算法参考实现_20260730/` | Latest source edit is 2026-07-30; 18 tests pass. |
| Full ablation | `agentdojo_v122_clafr_full_ablation_4suite_20260728` | This is the full 71-clean/585-attack four-suite ablation used by the current paper, newer than the earlier one-third ablation. |
| Main and multi-model results | selected frozen AgentDojo and ASB directories | Their aggregate values match the current main paper and supplement tables. |

## Items that are not current release sources

- `01_最终提交/Submit_20260728/` mixes a frozen main PDF with a later supplement and an extra duplicate main PDF named `DAFR_AAAI2027_Main_Current (1).pdf`.
- `03_LaTeX源码与模板/727_当前整合源码/` contains an older main source than the selected current paper.
- `08_历史版本与修改记录/` and `99_原始工作区完整镜像/` are historical evidence, not release inputs.
- Modification times from 2026-08-12 are generated `__pycache__/*.pyc` files, not newer source code.
- `文件清单_SHA256.csv` was generated on 2026-07-28 and does not describe later 2026-07-30 and 2026-08-01 changes. It must not be used as the checksum manifest for this release.

## Verification performed

- Main paper: isolated `pdflatex` build succeeded; 8 pages; no `Warning`, `Undefined`, `Overfull`, `Underfull`, `Fatal`, or `Error` entries in the new log; every page visually inspected.
- Supplement: isolated `pdflatex` build succeeded; 3 pages; same log checks; every page visually inspected.
- Default test command in this staging tree: 108 tests passed (90 integrated experiment tests plus 18 method-reference tests).
- Credential scan: no OpenAI/Anthropic keys, GitHub tokens, or real private keys found. The private-key-looking string in AgentDojo is synthetic benchmark content.
- GitHub size check: no staged file reaches 100 MB.

## Known caveats

- Re-running paid-model experiments was not attempted.
- The current manuscript reports the public method name `DAFR`, while implementation and results retain the historical identifier `CLAFR`.
- Public-release licensing remains an author decision; see `LICENSE_STATUS.md`.
