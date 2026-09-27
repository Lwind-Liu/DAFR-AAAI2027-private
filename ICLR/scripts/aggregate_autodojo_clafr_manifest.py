from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any


LABELS = {
    "clafr": "CLAFR",
    "clafr_no_evidence_projection": "w/o Evidence Projection",
    "clafr_no_action_evidence_lifting": "w/o Action-Evidence Lifting",
    "clafr_no_dynamic_geometry": "w/o Dynamic Geometry",
    "clafr_no_decision_repair": "w/o Decision & Repair",
}


def _load(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _case_metrics(root: Path, model: str, defense: str, suite: str, split: dict[str, Any]) -> dict[str, Any]:
    base = root / model / defense / suite
    clean: list[int] = []
    attack_utility: list[int] = []
    attack_success: list[int] = []
    allowed_margins: list[float] = []
    blocked_margins: list[float] = []
    non_geometric_block_margins: list[float] = []
    legacy_margins: list[float] = []
    for user_task in split["user_tasks"]:
        clean_payload = _load(base / user_task / "none" / "none.json")
        if clean_payload is not None and isinstance(clean_payload.get("utility"), bool):
            clean.append(int(clean_payload["utility"]))
            _extend_margins(
                clean_payload,
                allowed_margins,
                blocked_margins,
                non_geometric_block_margins,
                legacy_margins,
            )
        for injection_task in split["injection_tasks"]:
            payload = _load(base / user_task / "important_instructions" / f"{injection_task}.json")
            if payload is None:
                continue
            if isinstance(payload.get("utility"), bool):
                attack_utility.append(int(payload["utility"]))
            if isinstance(payload.get("security"), bool):
                attack_success.append(int(payload["security"]))
            _extend_margins(
                payload,
                allowed_margins,
                blocked_margins,
                non_geometric_block_margins,
                legacy_margins,
            )
    allowed_mean = mean(allowed_margins) if allowed_margins else None
    blocked_mean = mean(blocked_margins) if blocked_margins else None
    return {
        "clean_n": len(clean),
        "attack_n": len(attack_utility),
        "clean_utility": mean(clean) if clean else None,
        "asr": mean(attack_success) if attack_success else None,
        "attack_utility": mean(attack_utility) if attack_utility else None,
        "allowed_signed_margin": allowed_mean,
        "blocked_signed_margin": blocked_mean,
        "margin_separation": (
            allowed_mean - blocked_mean
            if allowed_mean is not None and blocked_mean is not None
            else None
        ),
        "allowed_margin_n": len(allowed_margins),
        "blocked_margin_n": len(blocked_margins),
        "non_geometric_block_n": len(non_geometric_block_margins),
        "decision_blocked_signed_margin": (
            mean([*blocked_margins, *non_geometric_block_margins])
            if blocked_margins or non_geometric_block_margins
            else None
        ),
        "allowed_sign_errors": sum(value < 0 for value in allowed_margins),
        "blocked_sign_errors": len(non_geometric_block_margins),
        # Kept only for backward-compatible audit of previously generated summaries.
        "legacy_absolute_margin": mean(abs(item) for item in legacy_margins) if legacy_margins else None,
        "legacy_margin_n": len(legacy_margins),
    }


def _extend_margins(
    payload: dict[str, Any],
    allowed: list[float],
    blocked: list[float],
    non_geometric_blocked: list[float],
    legacy: list[float],
) -> None:
    for record in payload.get("clafr_certificates", []):
        if not isinstance(record, dict):
            continue
        value = record.get("execution_margin")
        if isinstance(value, (int, float)):
            signed = float(value)
            legacy.append(signed)
            decision = record.get("decision")
            if decision == "ALLOW":
                allowed.append(signed)
            elif decision == "BLOCK_OR_CLARIFY":
                if signed < 0:
                    blocked.append(signed)
                else:
                    non_geometric_blocked.append(signed)


def _pct(value: float | None) -> str:
    return "N/A" if value is None else f"{100 * value:.1f}"


def _macro(suite_rows: dict[str, dict[str, Any]], metric: str) -> float | None:
    values = [item[metric] for item in suite_rows.values() if item[metric] is not None]
    return mean(values) if values else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate a frozen four-suite CLAFR ablation manifest.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model-id", default="deepseek-v4-flash")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))

    rows: list[dict[str, Any]] = []
    detail: dict[str, Any] = {}
    for defense in manifest["defenses"]:
        suite_rows = {
            suite: _case_metrics(args.root, args.model_id, defense, suite, split)
            for suite, split in manifest["suites"].items()
        }
        complete = all(
            row["clean_n"] == len(manifest["suites"][suite]["user_tasks"])
            and row["attack_n"]
            == len(manifest["suites"][suite]["user_tasks"])
            * len(manifest["suites"][suite]["injection_tasks"])
            for suite, row in suite_rows.items()
        )
        metrics = (
            "clean_utility",
            "asr",
            "attack_utility",
            "allowed_signed_margin",
            "blocked_signed_margin",
            "margin_separation",
            "decision_blocked_signed_margin",
            "legacy_absolute_margin",
        )
        row = {
            "method_key": defense,
            "method": LABELS.get(defense, defense),
            **{metric: _macro(suite_rows, metric) for metric in metrics},
            "allowed_margin_n": sum(item["allowed_margin_n"] for item in suite_rows.values()),
            "blocked_margin_n": sum(item["blocked_margin_n"] for item in suite_rows.values()),
            "non_geometric_block_n": sum(item["non_geometric_block_n"] for item in suite_rows.values()),
            "allowed_sign_errors": sum(item["allowed_sign_errors"] for item in suite_rows.values()),
            "blocked_sign_errors": sum(item["blocked_sign_errors"] for item in suite_rows.values()),
            "clean_cases": sum(item["clean_n"] for item in suite_rows.values()),
            "attack_cases": sum(item["attack_n"] for item in suite_rows.values()),
            "complete": complete,
        }
        rows.append(row)
        detail[defense] = suite_rows

    csv_path = args.root / "clafr_manifest_ablation.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (args.root / "clafr_manifest_ablation.json").write_text(
        json.dumps({"manifest": manifest, "rows": rows, "suite_detail": detail}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# CLAFR Four-Suite Ablation",
        "",
        f"- model: `{args.model_id}`",
        f"- benchmark: AgentDojo `{manifest['benchmark_version']}`",
        f"- selection rule: {manifest['selection_rule']}",
        "- aggregation: unweighted macro-average over banking, slack, travel, workspace",
        "- signed margin: minimum hard-constraint slack; allowed actions are compared with geometrically blocked actions whose margin is negative",
        "- non-geometric blocks: final blocks with non-negative geometric margin, reported separately rather than mixed into the geometric mechanism metric",
        "- separation: allowed signed margin minus geometrically blocked signed margin",
        "- legacy absolute margin is retained in CSV/JSON for audit only and is not displayed here",
        "",
        "| Method | Clean Utility | Static ASR | Static Attack Utility | Allowed Margin | Geometric-Block Margin | Separation | Margin N (A/G) | Non-Geo Blocks | Allow Sign Errors | Cases | Complete |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        allowed = "N/A" if row["allowed_signed_margin"] is None else f"{row['allowed_signed_margin']:+.3f}"
        blocked = "N/A" if row["blocked_signed_margin"] is None else f"{row['blocked_signed_margin']:+.3f}"
        separation = "N/A" if row["margin_separation"] is None else f"{row['margin_separation']:.3f}"
        lines.append(
            f"| {row['method']} | {_pct(row['clean_utility'])} | {_pct(row['asr'])} | "
            f"{_pct(row['attack_utility'])} | {allowed} | {blocked} | {separation} | "
            f"{row['allowed_margin_n']}/{row['blocked_margin_n']} | "
            f"{row['non_geometric_block_n']} | {row['allowed_sign_errors']} | "
            f"{row['clean_cases']}/{row['attack_cases']} | "
            f"{'yes' if row['complete'] else 'no'} |"
        )
    md_path = args.root / "clafr_manifest_ablation.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
