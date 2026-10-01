# NAACL/ARR review draft

This directory is the ACL review-format draft. It uses the official `acl.sty` in review mode, keeps the submission anonymous, and reuses the frozen four-suite AgentDojo (71 clean / 585 attacked) results. The AAAI source remains in `paper/main/` as a historical working version.

The canonical multi-model result manifest is `results/manifests/agentdojo_v122_multimodel_canonical_v1.json`. It records the four-suite denominator and per-row provenance; the 57/389 three-suite archive is explicitly excluded from the canonical aggregate.
- `DAFR_NAACL2027_Appendix.tex/pdf`：ACL review-format appendix with complete tables, geometry audit, ASB protocol, and reproducibility record.
- `ARR_Submission_Checklist_ZH.md`：提交前清单。
- `Responsible_NLP_Checklist_Draft_ZH.md`：Responsible NLP checklist 填写草稿。
- `ARR_Revision_Note_ZH.md`：已有评审版本修订说明草稿。
- `results/manifests/arr_anonymity_audit.json`：匿名性扫描结果。
