# 私人仓库权限检查清单

目标：只有仓库所有者和明确批准的论文合作者可以访问。

1. 仓库可见性必须保持 `Private`，不能改为 `Public` 或 `Internal`。
2. 只邀请确认过的 GitHub 用户名，不通过共享账号或共享令牌协作。
3. 个人账号私人仓库的合作者具有读写权限；若以后需要细分只读、写入、维护和管理权限，应迁移到 GitHub Organization。
4. `main` 应通过 Pull Request 修改，并禁止强制推送和删除。
5. 定期检查 **Settings → Collaborators**，移除离组人员和不明账号。
6. 定期检查 Deploy Keys、Webhooks 和 GitHub Apps；没有明确用途的条目应保持为空。
7. 所有合作者应启用双重验证。
8. 移除 GitHub 权限不能删除对方已经下载到本地的副本，离组流程还需要求删除本地研究资料。

## 命令行核查

```powershell
gh repo view Lwind-Liu/DAFR-AAAI2027-private --json nameWithOwner,visibility,url
gh api repos/Lwind-Liu/DAFR-AAAI2027-private/collaborators --jq '.[] | [.login, .permissions]'
gh api repos/Lwind-Liu/DAFR-AAAI2027-private/keys --jq '.[] | [.title, .read_only]'
gh api repos/Lwind-Liu/DAFR-AAAI2027-private/hooks --jq '.[] | [.name, .active]'
```

预期结果：可见性为 `PRIVATE`；合作者名单只有批准的论文成员；Deploy Keys 和 Webhooks 在无明确用途时为空。

