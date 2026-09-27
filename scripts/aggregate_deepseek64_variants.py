from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any

from aggregate_deepseek64_clafr_official import SPLIT, _case_tuple, _expected_case_ids, _summary_for_variant


DISPLAY_NAMES = {
    "baseline": "No Defense",
    "agentdojo_spotlighting": "Spotlighting",
    "agentdojo_repeat_user_prompt": "Repeat User Prompt",
    "agentdojo_tool_filter": "Tool Filter",
    "rule_shield": "Rule Shield",
    "llm_judge": "LLM Judge",
    "clafr_full": "CLAFR",
    "clafr_ablate_no_provenance_typing": "CLAFR w/o provenance-typed evidence",
    "clafr_ablate_no_action_lifting": "CLAFR w/o action-evidence lifting",
    "clafr_ablate_no_confidence_region": "CLAFR w/o confidence-lifted region",
    "clafr_ablate_no_feasible_region": "CLAFR w/o certificate execution",
    "clafr_ablate_no_provenance_lift": "CLAFR w/o provenance lift",
    "clafr_ablate_no_channel_provenance": "CLAFR w/o channel provenance",
    "clafr_ablate_no_untrusted_geometry": "CLAFR w/o untrusted geometry",
    "clafr_ablate_no_risk_budgets": "CLAFR w/o risk-budget cones",
    "clafr_ablate_no_format_projection": "CLAFR w/o format projection",
}

PRIMARY_ROLE = {
    "baseline": "clean_model_reference",
    "agentdojo_spotlighting": "official_defense",
    "agentdojo_repeat_user_prompt": "official_defense",
    "agentdojo_tool_filter": "official_defense",
    "rule_shield": "diagnostic_detector_baseline",
    "llm_judge": "diagnostic_llm_guard_baseline",
    "clafr_full": "paper_candidate",
    "clafr_ablate_no_provenance_typing": "paper_ablation",
    "clafr_ablate_no_action_lifting": "paper_ablation",
    "clafr_ablate_no_confidence_region": "paper_ablation",
    "clafr_ablate_no_feasible_region": "paper_ablation",
    "clafr_ablate_no_provenance_lift": "paper_ablation",
    "clafr_ablate_no_channel_provenance": "paper_ablation",
    "clafr_ablate_no_untrusted_geometry": "paper_ablation",
    "clafr_ablate_no_risk_budgets": "paper_ablation",
    "clafr_ablate_no_format_projection": "paper_ablation",
}


def _bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_variant_rows(root: Path, group: str, variant: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    case_rows: list[dict[str, Any]] = []
    suite_rows: list[dict[str, Any]] = []
    for suite in SPLIT:
        results_path = root / group / suite / "results.json"
        if not results_path.exists():
            suite_rows.append(
                {
                    "variant": variant,
                    "suite": suite,
                    "status": "missing",
                    "path": str(results_path),
                }
            )
            continue
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        summary = _summary_for_variant(payload, variant)
        if summary is None:
            suite_rows.append(
                {
                    "variant": variant,
                    "suite": suite,
                    "status": "missing_variant",
                    "path": str(results_path),
                }
            )
            continue
        raw = summary.get("raw_results", {}) or {}
        utility_results = raw.get("utility_results", {}) or {}
        security_results = raw.get("security_results", {}) or {}
        for raw_key, raw_utility in utility_results.items():
            parsed = _case_tuple(raw_key)
            if not parsed:
                continue
            user_task, injection_task = parsed
            utility = _bool(raw_utility)
            attack_success = _bool(security_results.get(raw_key))
            if utility is None or attack_success is None:
                continue
            case_rows.append(
                {
                    "variant": variant,
                    "method": DISPLAY_NAMES.get(variant, variant),
                    "role": PRIMARY_ROLE.get(variant, "baseline"),
                    "suite": suite,
                    "user_task": user_task,
                    "injection_task": injection_task,
                    "case_id": f"{suite}|{user_task}|{injection_task}",
                    "utility": int(utility),
                    "attack_success": int(attack_success),
                    "safety": int(not attack_success),
                    "jss": int(utility and not attack_success),
                    "path": str(results_path),
                }
            )
        suite_case_rows = [row for row in case_rows if row["suite"] == suite]
        shield = summary.get("shield", {}) or {}
        suite_rows.append(
            {
                "variant": variant,
                "method": DISPLAY_NAMES.get(variant, variant),
                "role": PRIMARY_ROLE.get(variant, "baseline"),
                "suite": suite,
                "status": "ok",
                "cases": len(suite_case_rows),
                "utility": mean([row["utility"] for row in suite_case_rows]) if suite_case_rows else 0.0,
                "attack_success": mean([row["attack_success"] for row in suite_case_rows]) if suite_case_rows else 0.0,
                "safety": mean([row["safety"] for row in suite_case_rows]) if suite_case_rows else 0.0,
                "jss": mean([row["jss"] for row in suite_case_rows]) if suite_case_rows else 0.0,
                "evaluated_tool_calls": shield.get("evaluated_tool_calls", ""),
                "blocked_tool_calls": shield.get("blocked_tool_calls", ""),
                "changed_tool_calls": shield.get("changed_tool_calls", ""),
                "provider_error_count": shield.get("provider_error_count", ""),
                "elapsed_seconds": summary.get("elapsed_seconds", ""),
                "path": str(results_path),
            }
        )
    return case_rows, suite_rows


def _aggregate_variant(variant: str, case_rows: list[dict[str, Any]], expected: set[str]) -> dict[str, Any]:
    seen = {str(row["case_id"]) for row in case_rows}
    return {
        "variant": variant,
        "method": DISPLAY_NAMES.get(variant, variant),
        "role": PRIMARY_ROLE.get(variant, "baseline"),
        "cases": len(case_rows),
        "expected_cases": len(expected),
        "missing_cases": len(expected - seen),
        "utility": mean([row["utility"] for row in case_rows]) if case_rows else 0.0,
        "attack_success": mean([row["attack_success"] for row in case_rows]) if case_rows else 0.0,
        "safety": mean([row["safety"] for row in case_rows]) if case_rows else 0.0,
        "jss": mean([row["jss"] for row in case_rows]) if case_rows else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate DeepSeek AgentDojo 64case results across variants.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--group", default="official64")
    parser.add_argument(
        "--variants",
        nargs="+",
        default=[
            "baseline",
            "agentdojo_spotlighting",
            "agentdojo_repeat_user_prompt",
            "agentdojo_tool_filter",
            "rule_shield",
            "llm_judge",
            "clafr_full",
        ],
    )
    args = parser.parse_args()

    expected = _expected_case_ids()
    all_case_rows: list[dict[str, Any]] = []
    all_suite_rows: list[dict[str, Any]] = []
    aggregate_rows: list[dict[str, Any]] = []
    for variant in args.variants:
        case_rows, suite_rows = _load_variant_rows(args.root, args.group, variant)
        all_case_rows.extend(case_rows)
        all_suite_rows.extend(suite_rows)
        aggregate_rows.append(_aggregate_variant(variant, case_rows, expected))

    _write_csv(args.root / "variant_case_rows.csv", all_case_rows)
    _write_csv(args.root / "variant_suite_rows.csv", all_suite_rows)
    _write_csv(args.root / "variant_aggregate_rows.csv", aggregate_rows)
    (args.root / "variant_aggregate.json").write_text(
        json.dumps(
            {
                "schema": "deepseek64-agentdojo-variant-aggregate-v1",
                "group": args.group,
                "expected_cases": len(expected),
                "variants": args.variants,
                "rows": aggregate_rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "# DeepSeek AgentDojo Variant Comparison",
        "",
        f"- group: `{args.group}`",
        f"- expected_cases: `{len(expected)}`",
        "",
        "| method | variant | role | cases | utility | ASR | safety | JSS | missing |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate_rows:
        lines.append(
            f"| {row['method']} | `{row['variant']}` | `{row['role']}` | {row['cases']} | "
            f"{row['utility']:.3f} | {row['attack_success']:.3f} | {row['safety']:.3f} | "
            f"{row['jss']:.3f} | {row['missing_cases']} |"
        )
    (args.root / "variant_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"deepseek64_variant_aggregate,{args.root / 'variant_comparison.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
