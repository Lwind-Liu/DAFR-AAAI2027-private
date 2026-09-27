# CLAFR Four-Suite Ablation

- model: `deepseek-v4-flash`
- benchmark: AgentDojo `v1.2.2`
- selection rule: Use every task in the AutoDojo AgentDojo Table-II banking, slack, and travel suites; use the pre-registered hash-selected 14-of-40 workspace tasks and all 14 workspace injection tasks.
- aggregation: unweighted macro-average over banking, slack, travel, workspace
- signed margin: minimum hard-constraint slack; allowed actions are compared with geometrically blocked actions whose margin is negative
- non-geometric blocks: final blocks with non-negative geometric margin, reported separately rather than mixed into the geometric mechanism metric
- separation: allowed signed margin minus geometrically blocked signed margin
- legacy absolute margin is retained in CSV/JSON for audit only and is not displayed here

| Method | Clean Utility | Static ASR | Static Attack Utility | Allowed Margin | Geometric-Block Margin | Separation | Margin N (A/G) | Non-Geo Blocks | Allow Sign Errors | Cases | Complete |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| CLAFR | 87.5 | 0.0 | 81.4 | +0.712 | -0.368 | 1.080 | 3618/329 | 0 | 0 | 71/585 | yes |
| w/o Evidence Projection | 79.2 | 0.0 | 81.8 | +0.704 | -0.389 | 1.093 | 3676/350 | 0 | 0 | 71/585 | yes |
| w/o Action-Evidence Lifting | 91.5 | 0.7 | 85.3 | N/A | N/A | N/A | 0/0 | 0 | 0 | 71/585 | yes |
| w/o Dynamic Geometry | 90.2 | 16.7 | 81.3 | N/A | N/A | N/A | 0/0 | 0 | 0 | 71/585 | yes |
| w/o Decision & Repair | 79.4 | 0.8 | 80.0 | +0.703 | -0.366 | 1.070 | 3621/332 | 0 | 0 | 71/585 | yes |
