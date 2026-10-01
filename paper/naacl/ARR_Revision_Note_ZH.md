# ARR Revision Note（中文草稿）

本版本将早期 DAFR 工作重新组织为 typed action--evidence execution interface，重点修订几何约束、ifelse 对照和证书接口的证据边界。

## 主要修订

1. 删除 mapper/LLM semantic mapper 主线，避免将未充分验证的语义适配能力作为核心贡献。
2. 明确 typed field validation、action--evidence encoding、dynamic feasible region 和 execution certificate 的分工。
3. 将 Geometry 与 equivalent arithmetic predicate 对齐，明确不声称 Geometry 比 unrestricted ifelse 更有表达力。
4. 新增 matched 512-case membership audit：独立轴向阈值产生 25 个 false allow，Geometry 与 equivalent predicate 决策一致。
5. 新增 matched 256-case repair audit：192 个可修复动作和 64 个必须阻断动作，Geometry 与同一 repair procedure 的 predicate 结果一致。
6. 将 system-level ablation 与 representation-level geometry control 分开，避免把完整 dynamic defense path 的消融误写成单独几何因果证据。
7. 补充 610 条 saved certificate consistency audit、fresh/stale fixed-family stress test 和 signed-margin 说明。
8. 统一 AgentDojo 四 suite、71 clean / 585 attacked 的 denominator，并隔离 57/389 的历史三-suite 子集。
9. 将论文切换为 ACL/ARR review 模板，正文压缩为 8 页，并补充限制、结果 provenance 和 responsible research 草稿。

## 未解决的限制

本版本仍主要评估 fixed static attacks；adaptive multi-step attacks、参数敏感性和完整 paired significance test 尚未完成。几何 suite 的标签由明确的联合预算解析生成，repair suite 使用固定候选变换；这些实验用于机制审计，不能被解释为现实环境安全定理。
