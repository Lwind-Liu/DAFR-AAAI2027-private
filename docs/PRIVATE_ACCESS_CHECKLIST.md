# Private-access checklist / 私有访问权限清单

Goal: only the paper owner and explicitly approved collaborators should have GitHub repository access.

## Recommended setup

1. Create the repository with visibility **Private** from the beginning. Do not create it as Public or Internal and then convert it.
2. Prefer an organization-owned private repository if different collaborators need different roles. Set the organization's base repository permission to **None**, then grant access only through a dedicated paper team.
3. Assign least privilege:
   - `Read`: download/view only.
   - `Write`: authors who actively push branches.
   - `Maintain`: one project maintainer if needed.
   - `Admin`: repository owner and at most one trusted backup administrator.
4. Protect `main`: require pull requests, at least one approval, conversation resolution, and passing tests; block force pushes and deletion.
5. Disable private-repository forking if the organization plan/settings allow it.
6. Audit **Settings → Collaborators and teams** after invitations are accepted. Remove unknown users, broad teams, stale collaborators, deploy keys, webhooks, and GitHub Apps.
7. Require two-factor authentication for all collaborators. Never share one GitHub account or personal access token.
8. Recheck access when a collaborator leaves. Removing GitHub access does not delete copies already cloned to a collaborator's computer; project policy must require local deletion.

## Personal-account limitation

A private repository owned by a personal account is simple, but personal repositories only distinguish the owner and collaborators; private-repository collaborators receive write access. Use an organization if you need true read-only, triage, write, maintain, and admin separation.

## Verification commands after remote creation

```powershell
gh repo view OWNER/REPOSITORY --json nameWithOwner,visibility,url
gh api repos/OWNER/REPOSITORY/collaborators --jq '.[] | [.login, .permissions]'
gh api repos/OWNER/REPOSITORY/keys --jq '.[] | [.title, .read_only]'
gh api repos/OWNER/REPOSITORY/hooks --jq '.[] | [.name, .active]'
```

Expected visibility is `PRIVATE`. The collaborator list must contain only approved paper workers, and deploy-key/webhook lists should be empty unless every entry is documented.

## Important boundary

GitHub permissions prevent uninvited accounts from viewing a private repository, but they cannot revoke local clones that an authorized collaborator already downloaded. Confidentiality therefore also depends on the collaborators' local-device and offboarding practices.

## GitHub documentation

- [Managing teams and people with access to your repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/managing-teams-and-people-with-access-to-your-repository)
- [Repository roles for an organization](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization)
- [Setting base permissions for an organization](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/setting-base-permissions-for-an-organization)
- [Permission levels for a personal account repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository)
