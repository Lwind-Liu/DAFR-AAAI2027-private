# 私人 GitHub 协作流程

## 首次下载

接受仓库邀请后运行：

```powershell
gh auth login
gh repo clone Lwind-Liu/DAFR-AAAI2027-private
Set-Location DAFR-AAAI2027-private
```

也可以登录 GitHub 后使用 **Code → Download ZIP**。ZIP 适合直接下载，但不包含 Git 历史，也不能用于上传修改。

## 日常同步

```powershell
git switch main
git pull --ff-only origin main
git switch -c 用户名/任务简称
```

完成修改后：

```powershell
git status
git add --all
git commit -m "说明本次论文、代码或结果修改"
git push -u origin HEAD
gh pr create --fill
```

后续继续工作前：

```powershell
git fetch origin
git rebase origin/main
git push --force-with-lease
```

`--force-with-lease` 只能用于自己的功能分支，不能用于共享 `main`。

## PR 前验证

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD\external\official_baselines\AutoDojo\agentdojo\src"
python -m pytest -q .\tests
python -m pytest -q .\method_reference\tests
```

论文发生变化时，还应编译正文和补充材料并检查 PDF。发布新快照前，由维护者重新生成 `UPLOAD_MANIFEST.csv` 和 `SHA256SUMS.txt`。

不得提交 `.env`、API Key、访问令牌、虚拟环境、缓存、付费模型凭据或未经审核的批量输出。

## 直接下载与发布

- 有权限的合作者可以使用 **Code → Download ZIP** 下载整个私人仓库。
- 单个文件可以在 GitHub 文件页面直接下载。
- `release_assets/` 下五个 ZIP 均低于 GitHub 100 MB 单文件限制，也可附加到私人 GitHub Release。
- 每次发布应同时保留 `UPLOAD_MANIFEST.csv` 和 `SHA256SUMS.txt`，用于核对完整性。

