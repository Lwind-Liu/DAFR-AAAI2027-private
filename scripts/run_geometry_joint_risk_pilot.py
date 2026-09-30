"""Matched joint-risk pilot: axis ifelse versus cone geometry/predicate.

The axis baseline is intentionally the common ``if r_i <= t_i`` rule.  The
equivalent predicate uses the same cone membership test, so any disagreement
with geometry is an implementation bug.  No external tool is executed.
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from clafr.geometry import FeasibleRegion, LinearFacet, RiskBudgetCone
from clafr.schemas import FeatureVector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/summaries/geometry_joint_risk_pilot_v1"
OUT.mkdir(parents=True, exist_ok=True)

cone = RiskBudgetCone(
    id="joint:privacy_financial",
    risk_weights={"privacy_egress": 1.0, "financial_risk": 1.0},
    credit_weights={},
    bound=1.0,
    description="joint privacy and financial risk budget",
    repair_hint="reduce one or both coupled risks or request clarification",
    source="pilot",
)
geometry = FeasibleRegion((cone,))
predicate = lambda vector: cone.margin(vector).slack >= 0.0
rows = []
for i in range(32):
    # Boundary-active grid: 16 points pass both axis thresholds; some violate
    # the coupled L2 budget even though neither individual if branch fires.
    privacy = 0.55 + 0.03 * (i % 9)
    financial = 0.55 + 0.03 * ((i * 5) % 9)
    vector = FeatureVector.from_mapping({
        "privacy_egress": privacy,
        "financial_risk": financial,
    })
    axis = privacy <= 0.8 and financial <= 0.8
    t0 = time.perf_counter(); geometric = geometry.feasible(vector); geometry_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter(); pred = predicate(vector); predicate_ms = (time.perf_counter() - t0) * 1000
    margin = cone.margin(vector)
    rows.append({
        "id": i,
        "privacy_egress": privacy,
        "financial_risk": financial,
        "axis_ifelse_allow": axis,
        "geometry_allow": geometric,
        "equivalent_predicate_allow": pred,
        "geometry_predicate_agree": geometric == pred,
        "joint_norm": round(math.hypot(privacy, financial), 6),
        "signed_slack": round(margin.slack, 6),
        "violated_facet": None if geometric else margin.constraint_id,
        "geometry_latency_ms": geometry_ms,
        "predicate_latency_ms": predicate_ms,
        "external_side_effect_executed": False,
    })
summary = {
    "cases": len(rows),
    "axis_ifelse_allow": sum(r["axis_ifelse_allow"] for r in rows),
    "geometry_allow": sum(r["geometry_allow"] for r in rows),
    "equivalent_predicate_allow": sum(r["equivalent_predicate_allow"] for r in rows),
    "axis_false_allow_joint_risk": sum(r["axis_ifelse_allow"] and not r["geometry_allow"] for r in rows),
    "geometry_predicate_disagreements": sum(not r["geometry_predicate_agree"] for r in rows),
    "geometry_mean_latency_ms": sum(r["geometry_latency_ms"] for r in rows) / len(rows),
    "predicate_mean_latency_ms": sum(r["predicate_latency_ms"] for r in rows) / len(rows),
    "scope": "same FeatureVector and RiskBudgetCone; in-process only; no external side effects",
}
(OUT / "rows.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
(OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(summary, ensure_ascii=False, indent=2))
