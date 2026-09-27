from __future__ import annotations

import argparse
import ast
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any


DISPLAY_NAMES = {
    "baseline": "No Defense",
    "prompt_policy": "Prompt-only Policy",
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
    "clafr_ablate_no_observation_projection": "CLAFR w/o observation projection",
}


ROLES = {
    "baseline": "no_defense_baseline",
    "prompt_policy": "prompt_only_baseline",
    "clafr_full": "paper_candidate",
    "clafr_ablate_no_provenance_typing": "paper_ablation",
    "clafr_ablate_no_action_lifting": "paper_ablation",
    "clafr_ablate_no_confidence_region": "paper_ablation",
    "clafr_ablate_no_feasible_region": "paper_ablation",
    "clafr_ablate_no_provenance_lift": "paper_ablation",
    "clafr_ablate_no_channel_provenance": "paper_ablation",
    "clafr_ablate_no_untrusted_geometry": "paper_ablation",
    "clafr_ablate_no_risk_budgets": "paper_ablation",
    "clafr_ablate_no_format_projection": "engineering_ablation",
    "clafr_ablate_no_observation_projection": "paper_ablation",
}


def _role(variant: str) -> str:
    return ROLES.get(variant, "paper_ablation")


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


def _case_tuple(raw_key: object) -> tuple[str, str] | None:
    try:
        parsed = ast.literal_eval(str(raw_key))
    except Exception:
        return None
    if isinstance(parsed, tuple) and len(parsed) == 2:
        return str(parsed[0]), str(parsed[1])
    return None


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _summary_for_variant(payload: dict[str, Any], variant: str) -> dict[str, Any] | None:
    for summary in payload.get("summaries", []) or []:
        if summary.get("variant") == variant:
            return summary
    return None


def _expected_cases(manifest: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for suite, spec in dict(manifest.get("suites", {})).items():
        for user_task in spec.get("users", []):
            for injection_task in spec.get("injections", []):
                out.add(f"{suite}|{user_task}|{injection_task}")
    return out


def _load_rows(
    root: Path,
    group: str,
    manifest: dict[str, Any],
    variant: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    case_rows: list[dict[str, Any]] = []
    suite_rows: list[dict[str, Any]] = []
    for suite, spec in dict(manifest.get("suites", {})).items():
        results_path = root / group / suite / "results.json"
        if not results_path.exists():
            suite_rows.append({"variant": variant, "suite": suite, "status": "missing", "path": str(results_path)})
            continue
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        summary = _summary_for_variant(payload, variant)
        if summary is None:
            suite_rows.append({"variant": variant, "suite": suite, "status": "missing_variant", "path": str(results_path)})
            continue
        raw = summary.get("raw_results", {}) or {}
        utility_results = raw.get("utility_results", {}) or {}
        security_results = raw.get("security_results", {}) or {}
        expected_suite = {
            f"{suite}|{user_task}|{injection_task}"
            for user_task in spec.get("users", [])
            for injection_task in spec.get("injections", [])
        }
        before = len(case_rows)
        for raw_key, raw_utility in utility_results.items():
            parsed = _case_tuple(raw_key)
            if not parsed:
                continue
            user_task, injection_task = parsed
            case_id = f"{suite}|{user_task}|{injection_task}"
            if case_id not in expected_suite:
                continue
            utility = _bool(raw_utility)
            attack_success = _bool(security_results.get(raw_key))
            if utility is None or attack_success is None:
                continue
            case_rows.append(
                {
                    "variant": variant,
                    "method": DISPLAY_NAMES.get(variant, variant),
                    "role": _role(variant),
                    "suite": suite,
                    "user_task": user_task,
                    "injection_task": injection_task,
                    "case_id": case_id,
                    "utility": int(utility),
                    "attack_success": int(attack_success),
                    "safety": int(not attack_success),
                    "jss": int(utility and not attack_success),
                    "path": str(results_path),
                }
            )
        suite_cases = case_rows[before:]
        shield = summary.get("shield", {}) or {}
        suite_rows.append(
            {
                "variant": variant,
                "method": DISPLAY_NAMES.get(variant, variant),
                "role": _role(variant),
                "suite": suite,
                "status": "ok",
                "cases": len(suite_cases),
                "utility": mean([row["utility"] for row in suite_cases]) if suite_cases else 0.0,
                "attack_success": mean([row["attack_success"] for row in suite_cases]) if suite_cases else 0.0,
                "safety": mean([row["safety"] for row in suite_cases]) if suite_cases else 0.0,
                "jss": mean([row["jss"] for row in suite_cases]) if suite_cases else 0.0,
                "evaluated_tool_calls": shield.get("evaluated_tool_calls", ""),
                "blocked_tool_calls": shield.get("blocked_tool_calls", ""),
                "changed_tool_calls": shield.get("changed_tool_calls", ""),
                "path": str(results_path),
            }
        )
    return case_rows, suite_rows


def _aggregate(variant: str, rows: list[dict[str, Any]], expected: set[str]) -> dict[str, Any]:
    seen = {str(row["case_id"]) for row in rows}
    return {
        "variant": variant,
        "method": DISPLAY_NAMES.get(variant, variant),
        "role": _role(variant),
        "cases": len(rows),
        "expected_cases": len(expected),
        "missing_cases": len(expected - seen),
        "utility": mean([row["utility"] for row in rows]) if rows else 0.0,
        "attack_success": mean([row["attack_success"] for row in rows]) if rows else 0.0,
        "safety": mean([row["safety"] for row in rows]) if rows else 0.0,
        "jss": mean([row["jss"] for row in rows]) if rows else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate CLAFR four-suite 32-case ablations.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--group", default="official32")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--variants", nargs="+", required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    expected = _expected_cases(manifest)
    all_case_rows: list[dict[str, Any]] = []
    all_suite_rows: list[dict[str, Any]] = []
    aggregate_rows: list[dict[str, Any]] = []
    for variant in args.variants:
        case_rows, suite_rows = _load_rows(args.root, args.group, manifest, variant)
        all_case_rows.extend(case_rows)
        all_suite_rows.extend(suite_rows)
        aggregate_rows.append(_aggregate(variant, case_rows, expected))

    _write_csv(args.root / "ablation32_case_rows.csv", all_case_rows)
    _write_csv(args.root / "ablation32_suite_rows.csv", all_suite_rows)
    _write_csv(args.root / "ablation32_aggregate_rows.csv", aggregate_rows)
    (args.root / "ablation32_aggregate.json").write_text(
        json.dumps(
            {
                "schema": "clafr-ablation32-aggregate-v1",
                "group": args.group,
                "expected_cases": len(expected),
                "manifest": str(args.manifest),
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
        "# CLAFR Four-Suite 32-Case Ablation",
        "",
        f"- group: `{args.group}`",
        f"- expected_cases: `{len(expected)}`",
        f"- split_seed: `{manifest.get('seed', '')}`",
        "",
        "| method | variant | role | cases | Utility | ASR | Safety | JSS | missing |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate_rows:
        lines.append(
            f"| {row['method']} | `{row['variant']}` | `{row['role']}` | {row['cases']} | "
            f"{row['utility']:.3f} | {row['attack_success']:.3f} | {row['safety']:.3f} | "
            f"{row['jss']:.3f} | {row['missing_cases']} |"
        )
    (args.root / "ablation32_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"clafr_ablation32_aggregate,{args.root / 'ablation32_comparison.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
