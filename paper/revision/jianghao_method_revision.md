# DAFR 当前修订方案（几何与执行证书主线）

## 当前主张

DAFR 的核心不是把几何形式包装成比所有程序判断更强，而是把工具调用、证据来源、授权、状态和外部风险统一表示为 action--evidence point，并在执行边界生成可审计的 feasibility certificate。

任意算术 predicate 都可以实现同样的 halfspace 和 joint-risk norm boundary，因此 equivalent-predicate 必须与 Geometry 做决策一致性检查。论文只对比以下两个层次：

- 独立逐维 if--else：每个风险坐标单独过阈值，无法捕获共享风险预算；
- 联合约束接口：使用同一风险预算组合多个风险，同时返回 signed margin、violated facet、provenance 和 repair target。

因此，几何的贡献是联合风险的结构化组合和证书接口，而不是任意程序不可表达的安全能力。

## 方法流程

1. **Typed field validation**：将注册工具的字段绑定到 object、destination、data、amount、time、effect、scope 等共享 effect roles，检查字段、策略、授权范围和风险类型是否一致。
2. **Action--evidence encoding**：将 concrete tool call、trusted task、source-tagged evidence 和 execution state 转换为 45 维坐标，保留原始字段和值的来源链接。
3. **Dynamic feasible region**：根据当前 effect 和 state 激活 halfspace 与 joint-risk constraint，计算每个 active margin。
4. **Execution certificate**：返回 ALLOW、CLARIFY/REPAIR 或 BLOCK，并记录 active constraints、signed margins、violated relations 和下一步反馈。
5. **State update**：可信工具结果更新 grounding、prerequisite、authorization 和 state relations；不可信文本只增加 risk/provenance signals，不能直接形成授权。

## 证据边界

当前 AgentDojo/ASB 主表使用 deterministic DAFR configuration。0 observed ASR 只能描述为固定 benchmark、固定攻击集合和给定 threat model 下的观测结果，不能写成一般安全保证。

512-case joint-risk suite 是机制实验：逐维 if--else 放行 512/512，其中 25/512 超过共享预算；Geometry 与 equivalent predicate 都放行 487/512，决策分歧为 0/512。

256-case action repair suite 是 dry-run 接口实验：192 个动作存在保持目标效果的安全候选，64 个动作必须阻断；Geometry 和 Predicate+oracle 都恢复 192/256，bool-only interface 为 0/256，外部副作用为 0。该结果说明 repair success 来自候选与 oracle；几何本身的可测优势是 certificate、margin 和 provenance 的统一输出。

614 条已保存 AgentDojo decision records 中，610 条格式正确。用等价 slack predicate 重查记录后决策一致率为 610/610。这是 certificate consistency audit，不是新的 planner replay，也不是新的 utility/ASR 结果。

64-case stress suite 使用四类固定注入文本，并交叉 fresh/stale state。它是固定族机制测试，不称为 adaptive attack；不含真实外部副作用。

## 主文写作要求

- 不使用训练方式作为卖点。
- 不声称 Geometry 普遍优于 if--else 或 unrestricted predicate。
- 不把 fixed-family stress test 写成 adaptive attack。
- 不把 saved-margin audit 写成 real environment replay。
- 不把 system-level `without dynamic defense path` 消融写成只移除了几何公式。
- 主表直接给出分母、observed ASR 和 threat-model 说明。
- 说明 equivalent predicate 与 Geometry 的接受/拒绝位应该一致；真正比较的是 coupled-budget handling、diagnostic output、repair interface 和 provenance completeness。

## 必须保留的表格

1. AgentDojo 三个 planner 的完整 baseline 表，注明每一行的 raw-run 或聚合来源。
2. ASB 204-case 表，明确 source-tagged threat model 和 0/204 observed attacks。
3. system ablation 表，标注其为 system-level ablation。
4. matched geometry 表，分开 axis-ifelse、weighted halfspace、Geometry、equivalent predicate、Boolean-only interface。
5. repair 表，报告 safe repair、effect preservation、unsafe repair、clarification 和外部副作用。
6. signed-margin 表，作为 decision consistency evidence，而不是 calibration theorem。

## 进一步实验优先级

- 统一所有主表 baseline 的 raw case、planner、模型版本、temperature、seed 和 aggregation provenance。
- 增加 no-provenance/source-unavailable ASB 对照。
- 增加真正的多步反馈攻击，区分 static injection 与 adaptive attack。
- 报告 benign block、false positive、latency 和每个 active facet 的定位统计。
- 对 axis threshold 做独立校准，避免只用天然有利于 axis baseline 的 synthetic distribution。
- 在相同 constraint object、feature vector、candidate set 和 repair budget 下比较 Geometry 与 equivalent predicate。
- 记录新工具的字段绑定数量、template 数量、配置时间和失败类型，支撑可扩展性叙事。

## 投稿前停止条件

- 主文和补充材料只保留上述 deterministic execution story；
- 所有未采用的语义适配实验术语不出现在投稿文本；
- 0% 结果均带分母、攻击集合和 threat-model 说明；
- Geometry 与 equivalent predicate 的决策一致性为 100% 或解释全部差异；
- axis-ifelse 的 false allow、certificate 输出和 repair 结果分开归因；
- 主文改用 ACL/ARR review 模板，A4、双栏、行号、匿名，Limitations 位于 Conclusion 之后；
- 编译通过并重新生成与源码同步的 PDF。
