# DAFR: Dynamic Action Feasible Regions

This repository snapshot accompanies the AAAI 2027 manuscript **“From Semantics to Execution: Dynamic Geometric Constraints for Tool-Action Feasibility.”** It packages the current paper, implementation, benchmark data, experiment manifests, aggregate results, and selected raw-result archives found in the authors' local workspace on 2026-09-27.

## What is included

- `paper/`: current anonymous main paper and supplement, their LaTeX sources, bibliography, figures, and AAAI style files.
- `reviews/`: AAAI-27 decision, two official reviews, the AI review, section-aligned Chinese translations, and a modification tracker.
- `ICLR/`: the latest archived experiment code, manifests, scripts, documentation, and tests. The directory name is historical.
- `src/geoconstraints/`: the projection and constraint utilities required by the AgentDojo integration.
- `external/`: the locally modified AgentDojo fork and the ToolSafe/ASB data slice used by the experiments.
- `data/`: directly downloadable copies of the AgentDojo data, ASB JSONL data, and frozen run manifests.
- `results/summaries/`: small, reviewable CSV/JSON/Markdown aggregates supporting the tables in the paper.
- `release_assets/`: compressed selected raw results, each below GitHub's 100 MB per-file limit.
- `method_reference/`: compact reference implementation of the paper-level DAFR decision procedure.
- `docs/`: repository map, private-access checklist, and download/upload/synchronization workflow.

The code and old result manifests retain the internal identifier `CLAFR`. The current paper uses `DAFR`. These identifiers were not bulk-renamed because scripts, result paths, and audit records depend on the original names.

## Quick start on Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip install -e ".\ICLR[dev]"
python -m pip install -e ".\external\official_baselines\AutoDojo\agentdojo"

$env:PYTHONPATH = "$PWD\src;$PWD\ICLR\src;$PWD\external\official_baselines\AutoDojo\agentdojo\src"
python -m pytest -q .\ICLR\tests
python -m pytest -q .\method_reference\tests
```

The unit tests do not call paid model APIs. Rerunning model experiments does require the provider-specific environment variables referenced by the scripts. No `.env` file or real credential is included.

## Compile the paper

```powershell
Push-Location .\paper\main
pdflatex -interaction=nonstopmode -halt-on-error DAFR_AAAI2027_Main_Current.tex
Pop-Location

Push-Location .\paper\supplement
pdflatex -interaction=nonstopmode -halt-on-error DAFR_AAAI2027_Supplement_Current.tex
Pop-Location
```

The checked-in `.bbl` lets the main paper compile without rerunning BibTeX. If references change, run BibTeX and then LaTeX twice.

## Results and raw artifacts

Start with `results/summaries/`. The five ZIP files in `release_assets/` contain the selected underlying JSON traces for the main AgentDojo run, full four-suite ablation, GPT-5.4-mini run, Claude Haiku 4.5 run, and ASB/margin evidence. See `release_assets/README.md` for the mapping.

## Reviews and Chinese translations

Start with [`reviews/README.md`](reviews/README.md). Each review file preserves the English text supplied in the screenshots and places the corresponding Chinese translation under the same stable comment ID. [`reviews/response_tracker_zh.md`](reviews/response_tracker_zh.md) consolidates repeated concerns without claiming that any new experiment or revision has already been completed.

## Private GitHub collaboration

This snapshot is intended for a **private** GitHub repository. Use [`docs/PRIVATE_ACCESS_CHECKLIST.md`](docs/PRIVATE_ACCESS_CHECKLIST.md) before inviting collaborators, and use [`docs/COLLABORATION_WORKFLOW.md`](docs/COLLABORATION_WORKFLOW.md) for clone, branch, pull-request, upload, and synchronization commands. The full tree is explained in [`docs/REPOSITORY_STRUCTURE.md`](docs/REPOSITORY_STRUCTURE.md).

## Snapshot status

This package fixes omissions in the old archive by restoring `src/geoconstraints/` and `agentdojo/attacks/clafr_adaptive_attacks.py` from the original experiment workspace. See `VERSION_AUDIT.md` for the exact selection decisions and known caveats.

## Licensing and visibility

The project itself did not contain an explicit top-level license. Keep the repository private and restricted to approved paper collaborators until the authors choose a license and resolve third-party redistribution status. Vendored AgentDojo retains its MIT license. ToolSafe's archived README labels the project MIT, but the local data slice did not include a standalone license file; verify and add the upstream license before any public redistribution. See `LICENSE_STATUS.md` and `THIRD_PARTY_NOTICES.md`.
