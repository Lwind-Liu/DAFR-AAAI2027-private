# CLAFR 多 LLM 实验协议冻结

日期：2026-07-20

## 1. 实验目的

验证冻结后的 CLAFR 是否能在不同模型与 function-calling 协议上保持高 Utility 和低 ASR。最终表与 DeepSeek 主表使用相同四-suite协议。

## 2. 模型与数据

- 开发模型：`deepseek-v4-flash`，现有结果不再修改。
- 新模型：`gpt-5.4-mini`、`gemini-2.5-flash`、`claude-haiku-4-5-20251001`。
- AgentDojo：`v1.2.2`。
- Suites：`banking / slack / travel / workspace-selected`。
- AutoDojo 参考部分：57 clean / 389 `important_instructions` static attack。
- Workspace 补充部分：固定 14 clean / 196 attack。
- 最终每个方法：71 clean / 585 attack。
- 聚合：四个 suite 的非加权宏平均。

冻结 case manifest：`C:\Users\f1567\Desktop\AAAI\ICLR\manifests\agentdojo_v122_clafr_multillm_four_suite_71_585.json`

## 3. Baseline 复用

Baseline 数据来自 `C:\Users\f1567\Desktop\AAAI\AutoDojo_AgentDojo完整模型Baseline数据汇总.docx` 中 AutoDojo Table II 的三-suite结果。

复用方法：No Defense、Sandwich、Reminder、Spotlighting、PIGuard、ProtectAI、Progent、DRIFT。

只使用以下列：

- Clean Utility
- Static ASR
- Static Attack Utility

不使用 `AutoDojo ASR` 与 `AutoDojo Attack Utility`，因为它们不属于当前 static attack 协议。PromptGuard 因 gated 模型不可复现而排除；DataFilter 按主实验决策排除。

## 4. 新运行

每个新模型运行：

- CLAFR：完整四-suite，71 clean / 585 attack，共 656 cases。
- 8 个参考 baseline：只补 workspace-selected，每个方法 14 clean / 196 attack，共 210 cases。

Word 中的 baseline 三-suite结果继续复用；workspace 必须按模型和方法真实运行，不能从 DeepSeek 或三-suite结果推导。最终四-suite指标按以下公式计算：

\[
M_{4\text{-suite}}=\frac{3M_{\text{base3}}+M_{\text{workspace}}}{4}.
\]

每个新增模型总量：`656 + 8 x 210 = 2336` cases。当前三模型目标总量：`3 x 2336 = 7008` cases。

多 LLM 表与 DeepSeek 主表承担不同证据角色：

- DeepSeek 主表：71 clean / 585 attack，四-suite完整比较。
- 多 LLM 表：同样为 71 clean / 585 attack；baseline 的前三个 suite 来自 AutoDojo Table II，workspace 为本次补跑。

## 5. 禁止调整

- 不按模型调整 CLAFR 阈值、风险预算或几何权重。
- 不根据模型名称、suite 名称或 benchmark 名称进入专用核心分支。
- 不读取 normal/attack 标签。
- 不根据结果删除或替换 case。
- 只允许 provider serialization、tool schema、tool-call parsing、API 参数兼容和固定重试策略等接口适配。

## 6. 预算门控

- 原两模型初步总成本：35-60 USD；Progent 和 DRIFT 可能产生独立 defender-model 费用。
- Claude-Haiku-4.5 单模型估计：18-35 USD，按输入 0.300/M、输出 1.500/M、缓存读取 0.030/M、缓存创建 0.375/M 估算。
- Claude-Haiku-4.5 暂定硬停止预算：40 USD。
- 正式运行前按模型、方法执行小 smoke，实测 target-agent 与 defender-model 成本后重新给出全量投影。
- smoke 不通过或投影超过硬停止预算时停止，不启动对应模型的 2336-case 正式运行。

## 7. 最终输出

每个模型报告：Clean Utility、Static ASR、Static Attack Utility，以及 CLAFR 的 Selected Signed Margin。Baseline 行标记为 `AutoDojo Table II base3 + measured workspace`，CLAFR 行标记为 `our four-suite rerun under the same manifest`。

## 8. Claude-Haiku-4.5 适配方案

模型 ID：`claude-haiku-4-5-20251001`。

Provider：PackyAPI OpenAI-compatible endpoint。运行时只替换 LLM endpoint/model，CLAFR 特征、几何权重、风险预算、阈值、case manifest 与 GPT-5.4-mini 完全一致。

Word 中 `Claude-Haiku-4.5` 的三-suite static baseline：

| Method | Clean Utility | Static ASR | Static Attack Utility |
|---|---:|---:|---:|
| No Defense | 70.2 | 0.3 | 61.4 |
| Sandwich | 71.9 | 0.0 | 63.5 |
| Reminder | 68.4 | 0.0 | 59.9 |
| Spotlighting | 70.2 | 0.0 | 57.1 |
| PIGuard | 47.4 | 0.0 | 36.5 |
| ProtectAI | 50.9 | 2.8 | 36.8 |
| Progent | 63.2 | 0.0 | 55.3 |
| DRIFT | 45.6 | 0.3 | 47.0 |

Claude 输出目录：

`C:\Users\f1567\Desktop\AAAI\ICLR\results\agentdojo_v122_claudehaiku45_multillm_frozen_v1`

运行命令模板：

```powershell
$env:OPENAI_COMPATIBLE_API_KEY="<PackyAPI key>"
python ICLR\scripts\run_agentdojo_multillm_frozen.py `
  --manifest ICLR\manifests\agentdojo_v122_clafr_multillm_four_suite_71_585.json `
  --out-root ICLR\results\agentdojo_v122_claudehaiku45_multillm_frozen_v1 `
  --model claude-haiku-4-5-20251001 `
  --base-url https://www.packyapi.com/v1 `
  --protocol chat_completions `
  --phase all `
  --max-workers 4
```

聚合与审计：

```powershell
python ICLR\scripts\audit_multillm_result_coverage.py `
  --manifest ICLR\manifests\agentdojo_v122_clafr_multillm_four_suite_71_585.json `
  --result-root ICLR\results\agentdojo_v122_claudehaiku45_multillm_frozen_v1 `
  --preset claudehaiku45

python ICLR\scripts\aggregate_multillm_four_suite.py `
  --result-root ICLR\results\agentdojo_v122_claudehaiku45_multillm_frozen_v1 `
  --preset claudehaiku45
```

输出文件：

- `claudehaiku45_result_audit.json`
- `claudehaiku45_four_suite_results.md`
- `claudehaiku45_four_suite_results.csv`
- `claudehaiku45_four_suite_results.json`
