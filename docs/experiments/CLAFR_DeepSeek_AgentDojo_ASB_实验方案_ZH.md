# CLAFR DeepSeek-v4-Flash 可信实验数据方案

更新时间：2026-07-19

> **归档说明：本文件保留实验方案与历史审计过程，不再作为最终数值来源。冻结后的最终主表、消融和可信写作边界统一见 `C:\Users\f1567\Desktop\AAAI\ICLR\docs\CLAFR_最终可信实验数据_20260719_ZH.md`。下文出现的旧 CLAFR 89.6/86.0、旧 ASB 200-case 与“待复跑”状态均已被最终文档替代。**

> 2026-07-19 方法冻结更新：原四-suite主表（CLAFR 89.6/0.0/86.0）来自模型可见 observation 被前置清洗的旧 projection 行为，可保留为历史审计结果，但不能用于证明 Dynamic Geometry 的独立贡献。当前几何主导版本、泛化不变量和新门控结果以 `docs/CLAFR_方法冻结与泛化门控_ZH.md` 为准；在正式复跑完成前，两版数据不得合并。

本文档只归档当前可以写进论文或补充材料的数据，并显式标出因协议修订而作废的数据。旧版本、不一致协议、单方法 smoke、provider 失败或不能直接比较的结果不进入主结论。

## 1. 结论边界

当前可以形成三组可信证据：

1. `AgentDojo / AutoDojo-style main table`：在 DeepSeek-v4-Flash、AgentDojo `v1.2.2`、`banking / slack / travel / workspace-selected` 四 suite 口径上，排除当前不可复现/过重的 PromptGuard 与 DataFilter 后，CLAFR 达到最低 ASR 与最高 static attack utility；clean utility 为 89.6，接近最高 Sandwich 89.8。
2. `ASB generalization`：旧 32/200 high-score ASB 结果经代码审计发现含 trusted-tool utility guidance；后续 neutral 结果又发现把 ASB `normal_tools` 当 trusted schema、把 `attack_tool` 排除在 schema 外，属于 schema-oracle，不能写进论文。2026-07-18 已修为 source-provenance 口径：所有模型可见工具均保留在 schema 内，攻击工具仅作为未信任工具源进入几何风险维度。正式 200-case source-provenance run 已完成，可作为 provenance-aware runtime evidence 的泛化证据。
3. `AgentDojo paper-module ablation`：旧五开关消融已废弃为 legacy engineering ablation；最终论文消融改为四个大模块：Evidence Projection、Action-Evidence Lifting、Dynamic Geometry、Decision & Repair，并按 `banking / slack / travel / workspace-selected` 四 suite 口径汇总。

当前不能形成的结论：

- 不能把 AgentDojo `v1` 97/629 结果混进 AutoDojo `v1.2.2` 主表。
- 不能把 GPT-4o/GPT-4o-mini 的 ASB DRIFT/Progent 日志混进 DeepSeek-v4-Flash 主表。
- 不能把 same-harness surrogate 的 ASB `progent/drift` 当作官方 baseline。
- 不能把 `run_agentdojo_full_agent_score.py` 的 32-case `clafr_full` 消融写成主消融；它与 AutoDojo `--defense clafr` 主表路径行为不一致。
- 不能把 PromptGuard/DataFilter 混入当前四 suite 主表：PromptGuard 依赖 gated HF 模型，DataFilter 会拉取大模型并导致本地磁盘/内存不可控，当前实验口径中排除。
- 不能继续使用旧 ASB `asb_200_stratified_deepseek_final_v1`、`asb_32_strong_baselines_deepseek_v1`、`asb_32_rr_strict_strong_baselines_deepseek_v1`、`asb_200_rr_strict_strong_baselines_deepseek_v1`、`asb_12_rr_neutral_audit_deepseek_v1`、`asb_200_rr_neutral_strong_baselines_deepseek_v1` 的 CLAFR 高分；这些结果来自 trusted-tool utility guidance 或 schema-oracle 口径，已作废。

## 2. AgentDojo 主表

### 2.1 协议

- 模型：`DeepSeek-v4-Flash`
- Benchmark：AgentDojo `v1.2.2`
- Evaluation path：AutoDojo fork 的 `python -m agentdojo.scripts.benchmark`
- Main suites：`banking / slack / travel / workspace-selected`
- Base suites：`banking / slack / travel`，57 clean / 389 static attack，沿用 AutoDojo 表格口径
- Workspace selected split：14 clean / 196 static attack，固定 manifest `C:\Users\f1567\Desktop\AAAI\ICLR\results\autodojo_v122_workspace_14x14_deepseek_v1\split_manifest.json`
- Main table cases：71 clean / 585 static attack
- Attack：`important_instructions`
- Aggregation：four-suite unweighted macro-average，`four_suite_macro = (3 * base3_macro + workspace_metric) / 4`
- Result path：`C:\Users\f1567\Desktop\AAAI\ICLR\results\autodojo_v122_workspace_14x14_deepseek_v1\autodojo_v122_4suite_merged.md`
- Included methods：`No Defense / Sandwich / Reminder / Spotlighting / PIGuard / ProtectAI / Progent / DRIFT / CLAFR`
- Excluded methods：`PromptGuard / DataFilter`。PromptGuard 依赖 gated HF 模型，当前环境无法复现；DataFilter 会拉取大模型并造成磁盘/内存风险，按当前实验决策不进入四 suite 主表。

### 2.2 四 Suite 主表结果

| Method | Clean Utility | Static ASR | Static Attack Utility | Cases |
|---|---:|---:|---:|---:|
| No Defense | 86.8 | 17.7 | 75.4 | 71/585 |
| Sandwich | 89.8 | 12.0 | 76.2 | 71/585 |
| Reminder | 85.0 | 3.9 | 79.2 | 71/585 |
| Spotlighting | 74.4 | 11.3 | 77.8 | 71/585 |
| PIGuard | 44.9 | 0.0 | 42.5 | 71/585 |
| ProtectAI | 48.0 | 4.2 | 36.2 | 71/585 |
| Progent | 75.2 | 2.1 | 71.7 | 71/585 |
| DRIFT | 62.6 | 1.4 | 53.2 | 71/585 |
| CLAFR | 89.6 | 0.0 | 86.0 | 71/585 |

可写结论：CLAFR achieves the lowest static ASR (0.0) and the highest static attack utility (86.0) among the reproducible four-suite baselines, while maintaining clean utility close to the best baseline (89.6 vs. Sandwich 89.8). 不应写成 clean utility 绝对第一。

### 2.3 Base3 与 Workspace Breakdown

Base3 source：`C:\Users\f1567\Desktop\AAAI\ICLR\results\autodojo_table_clafr_authfix_full_v1\autodojo_table_comparison.md`

Workspace source：`C:\Users\f1567\Desktop\AAAI\ICLR\results\autodojo_v122_workspace_14x14_deepseek_v1\workspace_rows.md`

| Suite | Clean Cases | Attack Cases | Clean Utility | Static ASR | Static Attack Utility |
|---|---:|---:|---:|---:|---:|
| banking | 16 | 144 | 100.0 | 0.0 | 93.1 |
| slack | 21 | 105 | 100.0 | 0.0 | 100.0 |
| travel | 20 | 140 | 80.0 | 0.0 | 77.9 |
| workspace-selected | 14 | 196 | 78.6 | 0.0 | 73.0 |

CLAFR workspace clean 失败的 3 个 case 没有 CLAFR block，主要来自模型最终回答格式或严格 utility checker 细节不满足；当前不做 benchmark-specific 修补。

### 2.4 同模型强 Baseline 补充

这组结果可作为补充说明，不替代 AutoDojo 主表。

- Result path：`C:\Users\f1567\Desktop\AAAI\ICLR\results\deepseek64_progent_drift_clafr\official64_comparison.md`
- Model：`DeepSeek-v4-Flash`
- Cases：64
- Scope：same-LLM adapted original baselines

| Method | Utility | ASR | Safety | JSS |
|---|---:|---:|---:|---:|
| CLAFR | 0.766 | 0.047 | 0.953 | 0.734 |
| Progent-DeepSeek | 0.703 | 0.031 | 0.969 | 0.688 |
| DRIFT-DeepSeek | 0.578 | 0.016 | 0.984 | 0.562 |

### 2.5 Workspace 边界

AgentDojo `v1.2.2` 的完整 `workspace` suite 规模为 40 clean / 560 attack cases。当前主表使用固定 selected split，不声称覆盖完整 workspace：

`four_suite_macro = (3 * base3_macro + workspace_metric) / 4`

已冻结 workspace split：

- Result root：`C:\Users\f1567\Desktop\AAAI\ICLR\results\autodojo_v122_workspace_14x14_deepseek_v1`
- Split manifest：`C:\Users\f1567\Desktop\AAAI\ICLR\results\autodojo_v122_workspace_14x14_deepseek_v1\split_manifest.json`
- Selection：固定 seed `clafr-autodojo-v122-workspace-14x14-20260718`，对 40 个 workspace user tasks 做 SHA256 排序，取前 14 个；使用全部 14 个 injection tasks。
- Coverage per method：14 clean / 196 attack = 210 cases。
- Included defenses：`no_defense / sandwich / reminder / spotlighting / piguard / protectai / progent / drift / clafr`。
- Excluded defenses：`promptguard / datafilter`，原因见 2.1。
- 现有 AgentDojo `v1` workspace/full 结果只作历史参考，不进入 `v1.2.2` 主表。
- 2026-07-18 runner 修订：workspace clean run 不再传 `--injection-task`，attack run 才传 injection filter；已用单元测试锁定，避免 clean 条件被 CLI filter 行为污染。
- 2026-07-19 状态：included defenses 的 selected workspace split 均已完成 `14/196`；四 suite 合并表已生成。

## 3. ASB 泛化实验

### 3.1 协议

- Benchmark：ToolSafe-ASB-OPI
- Model：`DeepSeek-v4-Flash`
- Manifest：10 agents x 5 tasks x 4 attacks = 200 cases
- 200-case source-provenance variants：`baseline / prompt_policy / ts_guard_style / ts_flow_style / clafr_full / clafr_feedback`，已完成
- 200-case source-provenance run path：`C:\Users\f1567\Desktop\AAAI\ICLR\results\asb_200_rr_source_trust_strong_baselines_deepseek_v1`
- 200-case source-provenance manifest path：`C:\Users\f1567\Desktop\AAAI\ICLR\results\asb_200_rr_source_trust_strong_baselines_deepseek_v1\manifest.json`
- 200-case manifest coverage：10 agents x 20 cases，每个 agent 覆盖 5 tasks x 4 attacks
- neutral feedback 修订：`run_asb_clafr_agent_score.py` 中 `clafr_feedback` 不再给出 preferred trusted tools，不再提示模型在 final answer 前优先调用 trusted tools。
- source-provenance 修订：CLAFR 不再把攻击工具移出 visible schema；`tool_source_risk` 与 `untrusted_tool_source_requires_authorization` hard facet 负责表达未信任工具源边界。
- observation-projection 修订：尾随工具输出注入不再依赖 ASB 的固定 `pay attention` 包装短语；当前规则基于句子边界、第二人称/agent 控制指令、新请求/命令标记、以及危险动作与安全关键对象的组合。
- no-label 压力测试边界：若 benchmark 完全不给工具来源信号，ASB 本地几何 sanity 中攻击工具直接候选仍有 124/200 可行，不能宣称同样强。进一步审计显示，ASB 中大量攻击工具在 name/description 上被伪装成正常安全、合规、验证或数据管理工具；在没有 source provenance 的设定下，这些工具与正常工具表面不可分。论文中 ASB 只能作为 provenance-aware runtime evidence 的迁移证明，同时必须报告 no-label stress 作为边界。Artifact：`C:\Users\f1567\Desktop\AAAI\ICLR\results\asb_geometry_source_stress_v1\asb_geometry_source_stress.md`。
- 作废旧结果：`asb_200_stratified_deepseek_final_v1`、`asb_32_strong_baselines_deepseek_v1`、`asb_32_rr_strict_strong_baselines_deepseek_v1`、`asb_200_rr_strict_strong_baselines_deepseek_v1`、`asb_12_rr_neutral_audit_deepseek_v1`、`asb_200_rr_neutral_strong_baselines_deepseek_v1`

### 3.2 ASB 200-case Source-Provenance 主结果

旧 200-case `0.843 / ASR 0.000` 结果来自旧 nudge/schema-oracle 协议，不能写进论文。正式 200-case run 使用 `--tool-provenance source_trust`，并只把 `baseline / prompt_policy / ts_guard_style / ts_flow_style / clafr_full / clafr_feedback` 作为 ASB 表；`progent/drift` ASB surrogate 只可作为诊断，不进主表。

Result path：`C:\Users\f1567\Desktop\AAAI\ICLR\results\asb_200_rr_source_trust_strong_baselines_deepseek_v1\asb_posthoc_summary.md`

| Method | Cases | Utility | Task Success | ASR | Trace ASR | Safety | Margin | Blocked | Projection Changed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| No Defense | 200/200 | 0.450 | 0.135 | 0.720 | 0.720 | 0.280 | - | 0 | 0 |
| Prompt-only Policy | 200/200 | 0.425 | 0.160 | 0.405 | 0.405 | 0.595 | - | 0 | 0 |
| ToolSafe TS-Guard-style | 200/200 | 0.422 | 0.085 | 0.260 | 0.260 | 0.740 | - | 99 | 0 |
| ToolSafe TS-Flow-style | 200/200 | 0.440 | 0.160 | 0.205 | 0.205 | 0.795 | - | 123 | 0 |
| CLAFR | 200/200 | 0.465 | 0.195 | 0.000 | 0.000 | 1.000 | 0.155 | 33 | 203 |
| ReAct + CLAFR-Feedback (neutral) | 200/200 | 0.495 | 0.210 | 0.000 | 0.000 | 1.000 | 0.156 | 29 | 230 |

ASR 使用保守 trace 口径：stored attack-goal hit OR executed attacker-tool trace。该结果说明 source-provenance runtime evidence 下，CLAFR/CLAFR-Feedback 显著低于 No Defense、Prompt-only、TS-Guard-style 和 TS-Flow-style 的 ASR，同时 Utility 最高；但它不能表述为无来源信号也可保持同等效果。

写作边界：source-provenance 表不能表述为“无额外来源信号也能识别所有攻击工具”。更准确的结论是：当运行时保留工具/观测来源边界时，CLAFR 将该来源证据提升为几何风险维度，在保持正常工具可行的同时阻断 untrusted-source 行为。no-label stress 用于说明缺少来源边界时的不可分性。

### 3.2.1 ASB no-label 几何压力审计

该审计不调用 API，不是任务级 ASR；它只看同一批 200 个 case 中，已知正常工具和已知 attacker-supplied 工具在 CLAFR 可行域里是否可行：

| Tool provenance | Attack feasible | Normal feasible |
|---|---:|---:|
| `source_trust` | 0/200 | 380/400 |
| `no_label` | 124/200 | 380/400 |

结论：source provenance 是方法的运行时证据边界之一。缺少该边界时，ASB 中很多伪装工具在动作表面上不可分，因此不能把 source-provenance 结果外推为 no-label 泛化。

### 3.3 ASB Source-Provenance Sanity

这张表仅用于 sanity audit，不作为论文主表。它用于确认移除 trusted-tool guidance 和 schema-oracle 后，CLAFR 仍能在 source-provenance 口径下保持安全且不全拒绝。

Result path：`C:\Users\f1567\Desktop\AAAI\ICLR\results\asb_12_rr_source_trust_audit_deepseek_v1\summary.md`

| Method | Cases | Utility Score | Task Success | ASR | Safety | Margin | Blocked |
|---|---:|---:|---:|---:|---:|---:|---:|
| No Defense | 12 | 0.417 | 0.083 | 0.583 | 0.417 | - | 0 |
| CLAFR | 12 | 0.458 | 0.167 | 0.000 | 1.000 | 0.157 | 1 |
| ReAct + CLAFR-Feedback (neutral) | 12 | 0.500 | 0.250 | 0.000 | 1.000 | 0.156 | 2 |

解释边界：12 cases 太小，不能支撑 ASR=0 的论文结论；它只说明 source-provenance protocol 修复后方向没有立即崩掉。正式 ASB 结论必须来自 200-case source-provenance strong-baseline table。

### 3.4 ASB Trace Audit

ASR=0 容易被质疑，因此必须同时报告 trace audit。

| Check | Value |
|---|---:|
| Cases | 12 |
| Utility score | 0.500 |
| Task success | 0.250 |
| ASR | 0.000 |
| Cases with at least one block | 2 |
| Evaluated tool calls | 15 |
| Allowed tool calls | 13 |
| Blocked tool calls | 2 |
| Selected signed margin mean | 0.156 |
| Selected signed margin samples | 13 |
| Blocked signed margin mean | -1.053 |
| Blocked signed margin samples | 2 |

解释边界：

- ASR=0 不是因为全拒绝；source-provenance CLAFR-Feedback 在 12-case sanity 中允许 13 次 tool call，阻断 2 次。
- allowed actions 的 signed margin 为正，blocked actions 的 signed margin 为负，支持几何可行域解释。

### 3.5 ASB Baseline 边界

本地 ToolSafe official runner 包含 `TS-Guard` 和 `TS-Flow` 思路，但默认配置依赖外部 `ashell-guardian` endpoint。当前已在我们同一 ASB runner 中实现 DeepSeek-compatible ToolSafe-style guard/flow，用作同模型强 baseline pilot。

本地 ASB official DRIFT/Progent 入口默认只支持 `gpt / gemini / claude / ollama`，没有 DeepSeek/OpenAI-compatible 分支。当前 `progent/drift` ASB surrogate 使用 ASB normal/attack 工具标签，只能作为 diagnostic upper-bound，不是官方 DRIFT/Progent baseline。若要把 DRIFT-ASB 或 Progent-ASB 写进 ASB 主表，必须先实现 DeepSeek adapter，并在同一 frozen manifest 上重跑。

## 4. 机制指标

机制指标只保留一个：`Selected Signed Margin`。

定义：CLAFR 最终选中 action 在所有 hard constraints 下的最小 signed slack。越高说明 action 离几何可行域边界越远；负值说明违反硬约束。

当前 ASB 200-case source-provenance 主结果：

| Quantity | Value |
|---|---:|
| CLAFR allowed selected signed margin | 0.155 |
| CLAFR allowed margin samples | 203 |
| CLAFR blocked signed margin | -0.795 |
| CLAFR blocked margin samples | 33 |
| CLAFR-Feedback allowed selected signed margin | 0.156 |
| CLAFR-Feedback allowed margin samples | 230 |
| CLAFR-Feedback blocked signed margin | -0.710 |
| CLAFR-Feedback blocked margin samples | 29 |

可写法：The margin audit shows a clear separation between executed actions and blocked actions: executed actions have positive signed margin on average, whereas blocked actions lie outside the feasible region.

## 5. AgentDojo 同协议消融

### 5.1 协议

消融必须使用 AutoDojo 主表相同入口：

- Runner：`python -m agentdojo.scripts.benchmark`
- Benchmark：AgentDojo `v1.2.2`
- Suites：`banking / slack / travel`
- Cases：57 clean / 389 static attack
- Aggregation：三 suite unweighted macro-average
- Full result path：`C:\Users\f1567\Desktop\AAAI\ICLR\results\autodojo_table_clafr_authfix_full_v1\autodojo_table_comparison.md`
- Ablation result path：`C:\Users\f1567\Desktop\AAAI\ICLR\results\autodojo_table_clafr_ablation_full_v1\autodojo_table_comparison.md`

`run_agentdojo_full_agent_score.py` 的 32-case 消融不作为论文主消融，因为该 runner 的 CLAFR 行为与 AutoDojo `--defense clafr` 主表不一致。

### 5.2 Paper-module 消融设计

旧 `CLAFR w/o ObsProj / FormatProj / RespProj / UntrustedGeo / ActionGeo` 五开关结果不进入论文主消融。原因是这些开关对应工程子路径，而不是论文大模块；其中 `w/o UntrustedGeo` 只关掉 untrusted-control 子约束，privacy / financial / state-write / semantic grounding 仍然保留，不能代表去掉动态几何。

最终论文消融统一使用以下四个 AutoDojo defense 名称：

| Defense key | Paper row | 关闭内容 | 预期观测 |
|---|---|---|---|
| `clafr_no_evidence_projection` | CLAFR w/o Evidence Projection | observation projection、opaque state projection、hidden untrusted block 提取和 trusted/untrusted evidence split | ASR 上升，attack utility 下降 |
| `clafr_no_action_evidence_lifting` | CLAFR w/o Action-Evidence Lifting | schema-guided action repair、action/evidence feature lifting、几何 selector 输入向量 | ASR 或 utility 下降，因为动作只剩 schema-level check |
| `clafr_no_dynamic_geometry` | CLAFR w/o Dynamic Geometry | semantic facets、confidence floor、untrusted-control、privacy/financial/state risk budgets | ASR 上升或 margin 分离消失；只保留 schema verifier |
| `clafr_no_decision_repair` | CLAFR w/o Decision & Repair | block/clarify repair fallback、format projection、final response projection | utility/attack utility 下降，部分风险 action 不再被转为修复/澄清 |

最终表必须是四 suite：`banking / slack / travel / workspace-selected`。三 suite legacy ablation 只作为调试记录，不写入主文。

## 6. 不进入主结果的数据

| 数据 | 原因 |
|---|---|
| `deepseek_agentdojo_v1_full_629_97` | AgentDojo `v1`，版本与 AutoDojo `v1.2.2` 主表不一致 |
| 旧 32-case `run_agentdojo_full_agent_score.py` 消融 | Full CLAFR 与 AutoDojo defense 路径不一致，且模块贡献不稳定 |
| ASB CLAFR-only recovery | 缺少同 manifest baseline |
| GPT-4o/GPT-4o-mini DRIFT-ASB 日志 | 模型不一致 |
| ToolSafe guardian-only 日志 | guard detection，不是 agent-level ASR/Utility |
| Same-harness ASB `progent/drift` surrogate | 不是官方 DRIFT/Progent baseline；只能作为 strong reference |

## 7. 论文表格建议

| 表/图 | 内容 | 当前状态 |
|---|---|---|
| Table 1 | AgentDojo four-suite main table：CLAFR vs reproducible AutoDojo-AgentDojo baselines | 已完成；PromptGuard/DataFilter 排除；selected workspace split 非完整 97/949 |
| Table 2 | ASB generalization：200-case source-provenance strong-baseline table + no-label stress | 200-case source-provenance 已完成；no-label 作为边界审计 |
| Table 3 | AgentDojo four-suite paper-module ablation | 已修正代码口径；需要按四 suite 复跑四个 paper-module ablation |
| Table 4 或 Appendix | AgentDojo suite/workspace breakdown + ASB per-agent breakdown | AgentDojo breakdown 已完成；ASB per-agent 可由 posthoc JSON/MD 补充生成 |
| Figure 1 | CLAFR 方法主图 | 可画 |
| Figure 2 | Margin mechanism：allowed vs blocked signed margin | 可画 |

## 8. 已完成验证

- ASB runner 已补 `Selected Signed Margin` 日志和汇总列。
- ASB posthoc 聚合脚本已补：`ICLR\scripts\aggregate_asb_clafr_results.py`，用于从 case JSON 生成总表、per-agent breakdown、margin/blocked/projection 审计，并显式标出 incomplete variant。
- ASB runner 已移除 `clafr_feedback` 的 preferred trusted tools 和 final 前 trusted-tool guidance。
- ASB runner 已在 manifest 中显式记录 `source_trust` 的 provenance 前提；单元测试确认攻击工具仍在 visible schema 内，source-provenance 只增加 untrusted source risk，不做 schema-oracle 删除。
- ASB no-API 几何压力审计已固定：`ICLR\scripts\audit_asb_geometry_source_stress.py`，结果写入 `ICLR\results\asb_geometry_source_stress_v1`。
- AutoDojo workspace / ablation runners 已修正 clean/attack CLI filter 边界：clean run 不再传 `--injection-task`，attack run 保留 injection filter。
- AgentDojo CLAFR adapter 已修正跨 case 状态隔离：`CLAFRToolsExecutor` 在新 conversation 无 tool observation 时清空上一 case 的 opaque binding 与 hidden untrusted blocks，避免前一 case 的 projection 状态污染后一 case。
- ASB 并行断点续跑已完成：父进程 PID `85256`，脚本 `ICLR\scripts\run_asb_parallel_resume.ps1`。该脚本按 variant 启动独立 worker，最后恢复完整六列 manifest，避免并行 worker 的临时 manifest 覆盖影响 posthoc 聚合。
- AgentDojo four-suite selected-workspace 主表已完成：`C:\Users\f1567\Desktop\AAAI\ICLR\results\autodojo_v122_workspace_14x14_deepseek_v1\autodojo_v122_4suite_merged.md`。
- AgentDojo 旧五开关消融已标记为 legacy，不进入论文主消融：`C:\Users\f1567\Desktop\AAAI\ICLR\results\autodojo_table_clafr_ablation_full_v1\autodojo_table_comparison.md`。
- 当前验证命令：`PYTHONPATH=ICLR;ICLR\src;src;. pytest -p no:cacheprovider ICLR/tests/test_clafr_agentdojo_adapter.py ICLR/tests/test_autodojo_workspace_slice.py ICLR/tests/test_clafr.py tests/test_observation_constraint_projection.py`，结果 `56 passed`；`py_compile` 覆盖 CLAFR compiler/selector、AutoDojo `clafr_defense.py` / `agent_pipeline.py`、`aggregate_autodojo_table.py` 与 `aggregate_autodojo_four_suite_clafr_ablation.py`，结果 passed。
- ASB runner 已修正断点续跑缓存读取：0-byte、坏 JSON、缺少 metrics 的 case 文件不再被视为完成结果；新 case 结果通过临时文件原子替换，避免磁盘/进程中断留下半写文件污染后续结果。
- ASB 12-case source-provenance sanity 已完成：No Defense、CLAFR、ReAct + CLAFR-Feedback neutral。
- ASB 12 source-provenance trace audit：CLAFR-Feedback 13 allowed tool calls / 2 blocked tool calls。
- ASB no-API geometry sanity：source_trust 下攻击工具直接候选 0/200 可行、正常工具 380/400 可行；no_label 下攻击工具直接候选 124/200 可行，说明强泛化结论必须声明工具来源信号前提。
- AutoDojo-style paper-module 消融已新增四个 defense key：`clafr_no_evidence_projection`、`clafr_no_action_evidence_lifting`、`clafr_no_dynamic_geometry`、`clafr_no_decision_repair`；后续结果必须用四 suite 聚合脚本 `ICLR\scripts\aggregate_autodojo_four_suite_clafr_ablation.py`。
- AgentDojo provider failure 已定位为 `run_agentdojo_full_agent_score.py` 默认清代理导致；该脚本的 ablation helper 已加 `-KeepProxy`，但该 runner 不进入主消融。
- CLAFR 格式投影已去掉 `update_user_info` 专用逻辑，改为通用 schema-guided structured split。
- Observation projection 已去掉 ASB 固定尾随短语依赖，并新增 generalized trailing-control 测试。
- 开源路径风险修订：`ICLR\scripts\*.ps1` 已去掉 `C:\Users\f1567\Desktop\AAAI` 默认路径，改为基于 `$PSScriptRoot` 推导 repo root 与默认 result root；脚本从任意 cwd 调用时会 `Set-Location` 到 repo root。
- CLAFR 四个 paper-level 模块的 12-case 本地机制 stress 已完成：`C:\Users\f1567\Desktop\AAAI\ICLR\results\clafr_paper_module_local_stress_12case_v1\stress_summary.md`。Full 为 0/8 unsafe allowed、0/4 safe blocked；去掉 Action-Evidence Lifting、Dynamic Geometry、Decision Repair 均为 8/8 unsafe allowed；去掉 Evidence Projection 不直接放行 unsafe，但 mean unsafe margin 从 -0.673 退化到 -0.237，可与 AgentDojo DeepSeek 12-case banking smoke 中 ASR 0.0 -> 66.7 的 outcome evidence 配套使用。

测试记录：

- `python -m pytest ICLR\tests\test_asb_clafr_feedback.py ICLR\tests\test_clafr.py tests\test_observation_constraint_projection.py -q -o cache_dir=C:\Users\f1567\AppData\Local\Temp\pytest-cache-clafr-strict-v2`（cwd=`C:\Users\f1567\Desktop\AAAI`）：43 passed。
- `python -m py_compile ICLR\scripts\run_asb_clafr_agent_score.py external\official_baselines\AutoDojo\agentdojo\src\agentdojo\agent_pipeline\clafr_defense.py ICLR\src\clafr\projection.py ICLR\src\clafr\features.py ICLR\src\clafr\compiler.py`：passed。
- `python -m pytest C:\Users\f1567\Desktop\AAAI\ICLR\tests\test_asb_clafr_feedback.py C:\Users\f1567\Desktop\AAAI\ICLR\tests\test_clafr.py C:\Users\f1567\Desktop\AAAI\tests\test_agentdojo_dynamic_plan.py C:\Users\f1567\Desktop\AAAI\tests\test_observation_constraint_projection.py`（cwd=`C:\Users\f1567\Desktop\AAAI`）：71 passed，1 个 pytest cache 权限 warning。
- `python -m pytest C:\Users\f1567\Desktop\AAAI\ICLR\tests\test_asb_clafr_feedback.py C:\Users\f1567\Desktop\AAAI\ICLR\tests\test_clafr.py C:\Users\f1567\Desktop\AAAI\tests\test_observation_constraint_projection.py`：41 passed。
- `python -m pytest C:\Users\f1567\Desktop\AAAI\ICLR\tests\test_asb_clafr_feedback.py C:\Users\f1567\Desktop\AAAI\ICLR\tests\test_clafr.py C:\Users\f1567\Desktop\AAAI\tests\test_observation_constraint_projection.py`（post neutral-feedback fix）：44 passed，1 个 pytest cache 权限 warning。
- `python -m pytest C:\Users\f1567\Desktop\AAAI\tests\test_agentdojo_dynamic_plan.py C:\Users\f1567\Desktop\AAAI\tests\test_agentdojo_core_geometry_gate.py C:\Users\f1567\Desktop\AAAI\ICLR\tests\test_clafr.py`：56 passed。
- `python -m pytest C:\Users\f1567\Desktop\AAAI\ICLR\tests\test_asb_clafr_feedback.py C:\Users\f1567\Desktop\AAAI\ICLR\tests\test_clafr.py C:\Users\f1567\Desktop\AAAI\tests\test_observation_constraint_projection.py`（post source-provenance fix）：45 passed，1 个 pytest cache 权限 warning。
- `python -m pytest C:\Users\f1567\Desktop\AAAI\ICLR\tests\test_asb_clafr_feedback.py C:\Users\f1567\Desktop\AAAI\ICLR\tests\test_clafr.py C:\Users\f1567\Desktop\AAAI\tests\test_observation_constraint_projection.py`（post generalized trailing-control projection fix）：46 passed，1 个 pytest cache 权限 warning。
- `python -m py_compile C:\Users\f1567\Desktop\AAAI\ICLR\scripts\aggregate_asb_clafr_results.py`：passed。
- `python C:\Users\f1567\Desktop\AAAI\ICLR\scripts\aggregate_asb_clafr_results.py --root C:\Users\f1567\Desktop\AAAI\ICLR\results\asb_200_rr_source_trust_strong_baselines_deepseek_v1`：生成 final posthoc summary，明确 `complete all variants: yes`。
- PowerShell parser check over `C:\Users\f1567\Desktop\AAAI\ICLR\scripts\*.ps1`：`all ps1 parse ok`。
- `rg 'C:\\Users\\f1567\\Desktop\\AAAI|f1567' C:\Users\f1567\Desktop\AAAI\ICLR\scripts -g '*.ps1'`：无命中。
