# NAACL 2027 / ARR 提交清单（当前版本）

## 已完成

- [x] 主文使用 ACL review 模板：`DAFR_NAACL2027_Main.tex`。
- [x] 正文 8 页，A4 双栏，匿名作者。
- [x] Appendix 使用 ACL review 模板：`DAFR_NAACL2027_Appendix.tex`。
- [x] 主文和 Appendix 均已直接编译，无 undefined reference。
- [x] 71 clean / 585 attack 四套件协议已写入主文和 canonical manifest。
- [x] 0/585、0/204 均保留分母和 static-attack 限定。
- [x] geometry membership 与 repair interface 已拆开报告。
- [x] 三套件 57/389 历史子集已从 canonical aggregate 中隔离。
- [x] 主文与 Appendix 源码匿名性扫描通过，结果见 `results/manifests/arr_anonymity_audit.json`。

## 提交前必须由作者确认

- [ ] ARR submission form 中填写真实作者、审稿服务承诺和 preferred venue `NAACL 2027`。
- [ ] Responsible NLP Research checklist 在 submission form 中逐项填写；当前草稿见 `Responsible_NLP_Checklist_Draft_ZH.md`。
- [ ] 确认该论文没有同时投递其他 archival venue。
- [ ] 如果作为已有评审版本的修订，上传旧版本并提交 revision note；草稿见 `ARR_Revision_Note_ZH.md`。
- [ ] 代码附件打包为单个匿名 `.zip`/`.tgz`，数据附件单独打包；不要上传带作者身份的 URL。
- [ ] 清理提交包中的 Windows 路径、API key、运行日志和未匿名仓库地址。
- [ ] 确认所有闭源模型的调用许可、费用和结果保存符合对应服务条款。

## 结果口径

正式 AgentDojo 主协议为四 suite、71 clean、585 attacked，使用 suite-level macro-average。57/389 仅是 Banking、Slack、Travel 的历史子集，不得混入正式四 suite 表。GPT baseline 表中的部分行来自历史汇总加 Workspace rerun，已在 manifest 中标注，不能描述为全部同一时间的新鲜重跑。

## 当前未完成的科学验证

论文仍然只报告固定 static attacks。64-case stress suite 是 fixed-family local mechanism test；512-case geometry study 使用 analytically specified labels；256-case repair study 使用固定 candidate transformation。这些结果不能表述为 adaptive-attack guarantee 或现实世界安全定理。
