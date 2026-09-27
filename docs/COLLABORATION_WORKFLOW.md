# Private GitHub collaboration workflow / 私有 GitHub 协作流程

## First download / 首次下载

Only invited collaborators can clone a private repository. After accepting the GitHub invitation:

```powershell
gh auth login
gh repo clone OWNER/REPOSITORY
Set-Location REPOSITORY
```

Without GitHub CLI:

```powershell
git clone https://github.com/OWNER/REPOSITORY.git
Set-Location REPOSITORY
```

GitHub's **Code → Download ZIP** also works after the collaborator signs in, but ZIP downloads do not preserve Git history and cannot be used to push changes.

## Daily synchronization / 日常同步

Create a personal branch; do not work directly on `main`:

```powershell
git switch main
git pull --ff-only origin main
git switch -c username/short-task-name
```

After editing:

```powershell
git status
git add --all
git commit -m "Describe the paper/code/result change"
git push -u origin HEAD
gh pr create --fill
```

Before continuing later:

```powershell
git fetch origin
git rebase origin/main
git push --force-with-lease
```

`--force-with-lease` must only be used on the author's own feature branch, never on shared `main`.

## What goes where / 文件放置

- Manuscript source/PDF: `paper/`
- Review originals/translations/tracker: `reviews/`
- Core code: `src/`, `ICLR/`, `method_reference/`
- Benchmark slices/manifests: `data/`
- Small aggregate results: `results/summaries/`
- Selected raw traces: `release_assets/`
- Collaboration documentation: `docs/`

## Verification before a pull request / PR 前验证

```powershell
python -m pytest -q .\ICLR\tests
python -m pytest -q .\method_reference\tests
```

If the paper changes, compile both `paper/main` and `paper/supplement`, inspect the PDFs, then regenerate `UPLOAD_MANIFEST.csv` and `SHA256SUMS.txt` using the packaging maintainer's release procedure.

Never commit `.env`, API keys, access tokens, local virtual environments, caches, paid-model credentials, or unreviewed bulk outputs.

## Releases and direct downloads / 发布与直接下载

- The entire private repository can be downloaded from **Code → Download ZIP** by authorized users.
- Individual tracked files can be downloaded from their GitHub file page.
- The five files under `release_assets/` can remain tracked because each is below GitHub's 100 MB file limit. They may also be attached to a private GitHub Release for a cleaner download page.
- Keep `UPLOAD_MANIFEST.csv` and `SHA256SUMS.txt` with every release so collaborators can verify completeness and file integrity.

