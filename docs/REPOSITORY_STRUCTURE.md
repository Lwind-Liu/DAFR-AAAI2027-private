# Repository structure / 仓库结构

The repository keeps executable module names stable so existing scripts and imports continue to work. Human-facing folders use short, descriptive English names, and every top-level folder has a single purpose.

为避免破坏已有脚本和导入路径，代码模块名称保持不变；面向合作者的目录采用简短、明确的英文命名，每个顶层目录只有一种职责。

```text
.
├── README.md                  # Entry point / 总入口
├── paper/                     # Current main paper, supplement, figures
├── reviews/                   # Decision, reviews, Chinese translations, tracker
├── src/geoconstraints/        # Core projection/constraint utilities
├── ICLR/                      # Experiment code (historical directory name)
├── method_reference/          # Compact paper-level reference implementation
├── external/                  # Vendored/modified benchmark dependencies
├── data/                      # Directly downloadable benchmark slices/manifests
├── results/summaries/         # Reviewable aggregate results
├── release_assets/            # Selected compressed raw-result archives
├── docs/                      # Collaboration, access, and structure guidance
├── UPLOAD_MANIFEST.csv        # Path, size, timestamp, SHA-256 inventory
└── SHA256SUMS.txt             # SHA-256 verification list
```

## Naming rules / 命名规则

- New files and folders should use lowercase English `snake_case` unless an upstream dependency or frozen artifact already has a stable name.
- Do not rename `ICLR`, `CLAFR`, benchmark IDs, result directories, manifest names, or Python package paths merely for presentation. They are compatibility and provenance identifiers.
- Add a date suffix in `YYYYMMDD` form only for real snapshots; do not create duplicate names such as `(1)` or `final_final`.
- Put current paper files under `paper/`, review materials under `reviews/`, aggregate tables under `results/summaries/`, and large raw traces under `release_assets/`.
- Generated caches, local environments, credentials, and incomplete reruns must not be committed.

## Where collaborators should start / 合作者入口

- Read the current paper: [`paper/README.md`](../paper/README.md)
- Read the reviews and translations: [`reviews/README.md`](../reviews/README.md)
- Inspect results: [`results/README.md`](../results/README.md)
- Download raw traces: [`release_assets/README.md`](../release_assets/README.md)
- Set up Git collaboration: [`COLLABORATION_WORKFLOW.md`](COLLABORATION_WORKFLOW.md)
- Check private access: [`PRIVATE_ACCESS_CHECKLIST.md`](PRIVATE_ACCESS_CHECKLIST.md)

