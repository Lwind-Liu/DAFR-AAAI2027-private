# 结果说明

`summaries/` 保存与论文主要实验、四套件完整消融、多模型评估、ASB 对比和带符号间隔审计对应的 CSV、JSON 与 Markdown 汇总结果。

精选底层运行轨迹位于 [`../release_assets/`](../release_assets/)。历史调参记录、不完整试运行、缓存和无关探索输出没有纳入共享包。

今后重新运行实验时，默认将临时输出写入被 Git 忽略的 `results/runs/`，确认有效后再选择性整理进 `results/summaries/` 或 `release_assets/`。

