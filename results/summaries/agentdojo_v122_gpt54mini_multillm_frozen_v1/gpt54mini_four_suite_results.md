# GPT-5.4-mini AgentDojo v1.2.2 four-suite results

| Method | Clean Utility | Static ASR | Static Attack Utility | Cases | Complete |
|---|---:|---:|---:|---:|:---:|
| CLAFR | 68.7 | 0.0 | 59.5 | 71/585 | yes |
| No Defense | 72.2 | 5.2 | 61.2 | 71/585 | yes |
| Sandwich | 80.6 | 2.1 | 65.4 | 71/585 | yes |
| Reminder | 76.6 | 0.6 | 65.4 | 71/585 | yes |
| Spotlighting | 70.5 | 2.5 | 62.7 | 71/585 | yes |
| PIGuard | 46.3 | 0.0 | 34.4 | 71/585 | yes |
| ProtectAI | 48.9 | 2.3 | 38.6 | 71/585 | yes |
| Progent | 66.0 | 1.4 | 54.2 | 71/585 | yes |
| DRIFT | 41.7 | 0.2 | 38.8 | 71/585 | yes |

All metrics are unweighted four-suite macro-averages. Baseline values combine the supplied Word table's first-three-suite macro-average with the measured workspace rate as (3 * base3 + workspace) / 4. CLAFR is computed directly from its four measured suite rates.
