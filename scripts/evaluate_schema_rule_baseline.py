"""Evaluate the matched schema-aware deterministic mapper on held-out cases.

The script uses exactly the public case fields consumed by the LLM mapper and
runs the same ConstraintIR validator/compiler and semantic scorer.  Gold is read
only by the evaluator, never by SchemaRulePolicyMapper.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clafr import SchemaRulePolicyMapper
from clafr.mapper_evaluation import score
from clafr.policy_mapper import MapperAbstention

VERSIONS = tuple(sys.argv[1:]) or ("v7", "v8", "v9", "v10", "v11")
OUT = ROOT / "results" / "summaries" / "mapper_rule_baseline_v1"
OUT.mkdir(parents=True, exist_ok=True)
mapper = SchemaRulePolicyMapper()
all_scores = []
all_rows = []
summary = {"baseline": "schema_rule_v1", "versions": {}, "protocol": {}}
for version in VERSIONS:
    data_path = ROOT / "data" / f"mapper_eval_zh_{version}_test.jsonl"
    cases = [json.loads(line) for line in data_path.read_text().splitlines() if line.strip()]
    version_rows, scores = [], []
    for case in cases:
        try:
            ir = mapper.map_policy(
                case["policy"], case["tool_name"], case["fields"],
                effect_class=case.get("effect_class"),
                field_descriptions=case.get("field_descriptions"),
            )
            row = {"id": case["id"], "backend_compilable": True, "ir": ir.to_dict()}
        except Exception as exc:  # abstention is a valid safe result
            row = {"id": case["id"], "backend_compilable": False,
                   "error": f"{type(exc).__name__}: {exc}"}
        result = score(case, row)
        result["gold_status"] = case.get("gold", {}).get("status", "ok")
        row["score"] = result
        version_rows.append(row)
        scores.append(result)
        all_scores.append(result)
        all_rows.append(row)
    nonambiguous = [s for s in scores if s["gold_status"] != "abstain"]
    ambiguous = [s for s in scores if s["gold_status"] == "abstain"]
    summary["versions"][version] = {
        "n": len(scores),
        "nonambiguous_n": len(nonambiguous),
        "compile_n": sum(not s["abstain"] for s in scores),
        "semantic_exact_n": sum(s["semantic_exact"] for s in scores),
        "nonambiguous_exact_n": sum(s["semantic_exact"] for s in nonambiguous),
        "ambiguous_n": len(ambiguous),
        "ambiguous_abstain_n": sum(s["abstain"] for s in ambiguous),
        "underconstrained_n": sum(bool(s.get("underconstrained")) for s in nonambiguous if not s["abstain"]),
        "overconstrained_n": sum(bool(s.get("overconstrained")) for s in nonambiguous if not s["abstain"]),
    }
    (OUT / f"{version}_rows.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in version_rows) + "\n")

nonambiguous = [s for s in all_scores if s["gold_status"] != "abstain"]
ambiguous = [s for s in all_scores if s["gold_status"] == "abstain"]
summary["aggregate"] = {
    "n": len(all_scores),
    "nonambiguous_n": len(nonambiguous),
    "compile_n": sum(not s["abstain"] for s in all_scores),
    "semantic_exact_n": sum(s["semantic_exact"] for s in all_scores),
    "nonambiguous_exact_n": sum(s["semantic_exact"] for s in nonambiguous),
    "ambiguous_n": len(ambiguous),
    "ambiguous_abstain_n": sum(s["abstain"] for s in ambiguous),
    "underconstrained_n": sum(bool(s.get("underconstrained")) for s in nonambiguous if not s["abstain"]),
    "overconstrained_n": sum(bool(s.get("overconstrained")) for s in nonambiguous if not s["abstain"]),
}
summary["protocol"] = {
    "input_fields": ["tool_name", "fields", "policy", "description", "field_descriptions", "effect_class"],
    "gold_not_visible_to_mapper": True,
    "shared_validator": "clafr.policy_ir.validate_constraint_ir",
    "shared_compiler": "clafr.ir_compiler.IRPolicyCompiler",
    "shared_scorer": "clafr.mapper_evaluation.score",
    "versions": list(VERSIONS),
}
summary["input_sha256"] = hashlib.sha256("".join(
    (ROOT / "data" / f"mapper_eval_zh_{v}_test.jsonl").read_bytes().decode() for v in VERSIONS
).encode()).hexdigest()
(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
(OUT / "all_rows.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in all_rows) + "\n")
print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
