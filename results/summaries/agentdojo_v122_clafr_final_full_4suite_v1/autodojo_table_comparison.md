# AutoDojo Table-II Style Comparison

- model: `deepseek-v4-flash`
- benchmark version: `v1.2.2`
- suites: `banking`, `slack`, `travel`
- expected clean cases: `57`
- expected static attack cases: `389`
- aggregation: unweighted macro-average over the three suites, matching AutoDojo aggregation.

| Method | Clean Utility | Static ASR | Static Attack Utility | Cases |
|---|---:|---:|---:|---:|
| No Defense | 89.5 | 22.6 | 77.4 | 57/389 |
| Sandwich | 91.2 | 14.7 | 77.4 | 57/389 |
| Reminder | 89.5 | 4.9 | 81.0 | 57/389 |
| Spotlighting | 75.4 | 13.9 | 80.5 | 57/389 |
| PromptGuard | 89.5 | 21.3 | 70.2 | 57/389 |
| PIGuard | 45.6 | 0.0 | 40.9 | 57/389 |
| ProtectAI | 47.4 | 4.6 | 31.9 | 57/389 |
| DataFilter | 91.2 | 2.3 | 81.5 | 57/389 |
| Progent | 78.9 | 2.8 | 73.8 | 57/389 |
| DRIFT | 59.6 | 1.3 | 48.1 | 57/389 |
| CLAFR | 88.1 | 0.0 | 83.2 | 57/389 |
