# CLAFR 带符号 Margin 证据汇总

## 统一定义

对动作 $a_t$，执行余量定义为所有激活硬几何约束的最小带符号 slack：

$$M_t(a_t)=\min_g m_{t,g}(z_t).$$

- $M_t>0$：动作点位于动态几何可行域内部。
- $M_t=0$：动作点位于边界。
- $M_t<0$：动作至少违反一个硬几何约束。
- 几何阻断：最终被阻断且 $M_t<0$ 的动作；$M_t\geq0$ 但被其他条件阻断的动作单列为非几何阻断。
- 分离度 $\Delta_M=\mathbb{E}[M_t\mid Allow]-\mathbb{E}[M_t\mid GeometricBlock]$；越大表示允许动作与几何违规动作分得越清楚。
- 旧版 `mean(abs(margin))` 会抹掉方向，只保留在 JSON/CSV 的 legacy 审计字段中，不再作为机制指标。

## AgentDojo 主结果的机制证据

| 模型 | 允许动作 Margin | 几何阻断 Margin | 分离度 | 证书数（允许/几何阻断） | 非几何阻断 | 允许符号异常 |
|---|---:|---:|---:|---:|---:|---:|
| deepseek-v4-flash | +0.712 | -0.368 | 1.080 | 3618/329 | 0 | 0 |
| gpt-5.4-mini | +0.748 | -0.214 | 0.963 | 2825/77 | 14 | 0 |

DeepSeek 正式全量中，所有允许证书均为正、所有阻断证书均为几何负余量。GPT 有 14 个非几何阻断，已单列且未混入几何分离度。表中均值采用与公共指标一致的四 suite 非加权宏平均。

## AgentDojo 四模块消融

| 方法 | Clean Utility | Static ASR | Attack Utility | 允许 Margin | 几何阻断 Margin | 分离度 | 证书数（允许/几何阻断） | 非几何阻断 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CLAFR | 91.4 | 0.0 | 79.1 | +0.706 | -0.348 | 1.110 | 1408/102 | 0 |
| w/o Evidence Projection | 40.4 | 4.3 | 39.7 | +0.688 | -1.178 | 1.865 | 1781/822 | 2 |
| w/o Action-Evidence Lifting | 91.4 | 1.4 | 82.2 | N/A | N/A | N/A | 0/0 | 0 |
| w/o Dynamic Geometry | 91.4 | 1.0 | 80.3 | N/A | N/A | N/A | 0/0 | 0 |
| w/o Decision & Repair | 77.3 | 1.5 | 79.2 | +0.698 | -0.238 | 0.935 | 1421/104 | 0 |

`w/o Action-Evidence Lifting` 与 `w/o Dynamic Geometry` 不产生可解释的几何证书，因此 Margin 为 N/A。`w/o Evidence Projection` 有 2 个正 margin 的阻断证书：它们没有几何违规，被归为非几何阻断，未删除或改写。

## ASB 迁移证据

| 方法 | Utility | Task Success | ASR | 允许 Margin | 阻断 Margin | 分离度 | 证书数（允许/阻断） | 符号异常 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| clafr_full | 0.465 | 0.195 | 0.000 | +0.155 | -0.795 | 0.950 | 203/33 | 0/0 |
| clafr_feedback | 0.495 | 0.210 | 0.000 | +0.156 | -0.710 | 0.865 | 230/29 | 0/0 |

ASB 的均值按 200-case 运行中的工具决策日志汇总，不与 AgentDojo 的四-suite宏平均混合计算。AgentDojo 与 ASB 都呈现允许为正、几何阻断为负的方向一致性。

## 证据边界

- Margin 是 CLAFR 内部机制指标；No Defense、Sandwich、Reminder 等外部 baseline 没有同构几何证书，因此不填 Margin。
- Claude 兼容性运行没有产生有效 tool-call 证书，不能作为 Margin 或公共指标证据，记为 N/A。
- 几何隔离 pilot 只有允许动作、没有几何阻断样本，因此只能验证正侧内部余量，不能据此估计分离度。
- 本汇总完全由已有结果后处理生成，没有重跑模型或调用 API。

## 可直接用于论文的结论

在 AgentDojo 全量运行中，CLAFR 将 3,618 个允许动作置于可行域内部，并将 329 个阻断动作置于边界外，四-suite宏平均分离度为 1.080，且无符号异常。ASB 上同样保持允许余量为正、阻断余量为负，说明动态几何的判别方向跨 benchmark 保持一致。
