from __future__ import annotations

import argparse
import ast
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any


SPLIT: dict[str, dict[str, list[str]]] = {
    "workspace": {
        "users": ["user_task_29", "user_task_21", "user_task_39", "user_task_6"],
        "injections": ["injection_task_1", "injection_task_5", "injection_task_4", "injection_task_3"],
    },
    "travel": {
        "users": ["user_task_10", "user_task_7", "user_task_8", "user_task_17"],
        "injections": ["injection_task_0", "injection_task_5", "injection_task_1", "injection_task_6"],
    },
    "banking": {
        "users": ["user_task_4", "user_task_13", "user_task_8", "user_task_9"],
        "injections": ["injection_task_8", "injection_task_3", "injection_task_1", "injection_task_0"],
    },
    "slack": {
        "users": ["user_task_14", "user_task_13", "user_task_10", "user_task_3"],
        "injections": ["injection_task_1", "injection_task_2", "injection_task_3", "injection_task_4"],
    },
}

METHODS = {
    "clafr_full": {
        "method": "CLAFR",
        "role": "paper_candidate",
        "source": "runner",
    },
    "progent": {
        "method": "Progent-DeepSeek",
        "role": "same_llm_original_baseline",
        "source": "autodojo",
    },
    "drift": {
        "method": "DRIFT-DeepSeek",
        "role": "same_llm_original_baseline",
        "source": "autodojo",
    },
}


def _expected_case_ids(group: str) -> set[str]:
    rows: set[str] = set()
    if group == "smoke":
        spec = SPLIT["workspace"]
        return {f"workspace|{spec['users'][0]}|{spec['injections'][0]}"}
    for suite, spec in SPLIT.items():
        for user_task in spec["users"]:
            for injection_task in spec["injections"]:
                rows.add(f"{suite}|{user_task}|{injection_task}")
    return rows


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


def _case_tuple(raw_key: str) -> tuple[str, str] | None:
    try:
        parsed = ast.literal_eval(raw_key)
    except Exception:
        return None
    if isinstance(parsed, tuple) and len(parsed) == 2:
        return str(parsed[0]), str(parsed[1])
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


def _load_clafr_rows(root: Path, group: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    case_rows: list[dict[str, Any]] = []
    suite_rows: list[dict[str, Any]] = []
    suites = ["workspace"] if group == "smoke" else list(SPLIT)
    for suite in suites:
        results_path = root / "clafr" / group / suite / "results.json"
        if not results_path.exists():
            suite_rows.append({"variant": "clafr_full", "suite": suite, "status": "missing", "path": str(results_path)})
            continue
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        summary = next((item for item in payload.get("summaries", []) if item.get("variant") == "clafr_full"), None)
        if summary is None:
            suite_rows.append({"variant": "clafr_full", "suite": suite, "status": "missing_variant", "path": str(results_path)})
            continue
        raw = summary.get("raw_results", {}) or {}
        utility_results = raw.get("utility_results", {}) or {}
        security_results = raw.get("security_results", {}) or {}
        before_count = len(case_rows)
        for raw_key, raw_utility in utility_results.items():
            parsed = _case_tuple(raw_key)
            if not parsed:
                continue
            user_task, injection_task = parsed
            utility = _bool(raw_utility)
            attack_success = _bool(security_results.get(raw_key))
            if utility is None or attack_success is None:
                continue
            case_rows.append(_case_row("clafr_full", suite, user_task, injection_task, utility, attack_success, results_path))
        suite_cases = case_rows[before_count:]
        shield = summary.get("shield", {}) or {}
        suite_rows.append(
            {
                "variant": "clafr_full",
                "method": METHODS["clafr_full"]["method"],
                "role": METHODS["clafr_full"]["role"],
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
                "provider_error_count": shield.get("provider_error_count", ""),
                "elapsed_seconds": summary.get("elapsed_seconds", ""),
                "path": str(results_path),
            }
        )
    return case_rows, suite_rows


def _case_row(
    variant: str,
    suite: str,
    user_task: str,
    injection_task: str,
    utility: bool,
    attack_success: bool,
    path: Path,
) -> dict[str, Any]:
    return {
        "variant": variant,
        "method": METHODS[variant]["method"],
        "role": METHODS[variant]["role"],
        "suite": suite,
        "user_task": user_task,
        "injection_task": injection_task,
        "case_id": f"{suite}|{user_task}|{injection_task}",
        "utility": int(utility),
        "attack_success": int(attack_success),
        "safety": int(not attack_success),
        "jss": int(utility and not attack_success),
        "path": str(path),
    }


def _load_autodojo_rows(root: Path, group: str, variant: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    case_rows: list[dict[str, Any]] = []
    suite_rows: list[dict[str, Any]] = []
    suites = ["workspace"] if group == "smoke" else list(SPLIT)
    log_root = root / "autodojo" / group / "deepseek-v4-flash" / variant
    for suite in suites:
        before_count = len(case_rows)
        spec = SPLIT[suite]
        users = [spec["users"][0]] if group == "smoke" else spec["users"]
        injections = [spec["injections"][0]] if group == "smoke" else spec["injections"]
        missing = 0
        errors = 0
        for user_task in users:
            for injection_task in injections:
                path = log_root / suite / user_task / "important_instructions" / f"{injection_task}.json"
                if not path.exists():
                    missing += 1
                    continue
                payload = json.loads(path.read_text(encoding="utf-8"))
                utility = _bool(payload.get("utility"))
                attack_success = _bool(payload.get("security"))
                if utility is None or attack_success is None:
                    missing += 1
                    continue
                if payload.get("error") or payload.get("error_type"):
                    errors += 1
                case_rows.append(_case_row(variant, suite, user_task, injection_task, utility, attack_success, path))
        suite_cases = case_rows[before_count:]
        suite_rows.append(
            {
                "variant": variant,
                "method": METHODS[variant]["method"],
                "role": METHODS[variant]["role"],
                "suite": suite,
                "status": "ok" if not missing else ("partial" if suite_cases else "missing"),
                "cases": len(suite_cases),
                "missing": missing,
                "errors": errors,
                "utility": mean([row["utility"] for row in suite_cases]) if suite_cases else 0.0,
                "attack_success": mean([row["attack_success"] for row in suite_cases]) if suite_cases else 0.0,
                "safety": mean([row["safety"] for row in suite_cases]) if suite_cases else 0.0,
                "jss": mean([row["jss"] for row in suite_cases]) if suite_cases else 0.0,
                "path": str(log_root / suite),
            }
        )
    return case_rows, suite_rows


def _aggregate(variant: str, rows: list[dict[str, Any]], expected: set[str]) -> dict[str, Any]:
    seen = {str(row["case_id"]) for row in rows}
    return {
        "variant": variant,
        "method": METHODS[variant]["method"],
        "role": METHODS[variant]["role"],
        "cases": len(rows),
        "expected_cases": len(expected),
        "missing_cases": len(expected - seen),
        "utility": mean([row["utility"] for row in rows]) if rows else 0.0,
        "attack_success": mean([row["attack_success"] for row in rows]) if rows else 0.0,
        "safety": mean([row["safety"] for row in rows]) if rows else 0.0,
        "jss": mean([row["jss"] for row in rows]) if rows else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate CLAFR, Progent and DRIFT on the shared DeepSeek 64case split.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--group", default="official64", choices=["smoke", "official64"])
    args = parser.parse_args()

    expected = _expected_case_ids(args.group)
    all_case_rows: list[dict[str, Any]] = []
    all_suite_rows: list[dict[str, Any]] = []
    aggregate_rows: list[dict[str, Any]] = []

    clafr_cases, clafr_suites = _load_clafr_rows(args.root, args.group)
    all_case_rows.extend(clafr_cases)
    all_suite_rows.extend(clafr_suites)
    aggregate_rows.append(_aggregate("clafr_full", clafr_cases, expected))

    for variant in ("progent", "drift"):
        cases, suites = _load_autodojo_rows(args.root, args.group, variant)
        all_case_rows.extend(cases)
        all_suite_rows.extend(suites)
        aggregate_rows.append(_aggregate(variant, cases, expected))

    _write_csv(args.root / f"{args.group}_case_rows.csv", all_case_rows)
    _write_csv(args.root / f"{args.group}_suite_rows.csv", all_suite_rows)
    _write_csv(args.root / f"{args.group}_aggregate_rows.csv", aggregate_rows)
    (args.root / f"{args.group}_aggregate.json").write_text(
        json.dumps(
            {
                "schema": "deepseek64-progent-drift-clafr-aggregate-v1",
                "group": args.group,
                "expected_cases": len(expected),
                "rows": aggregate_rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "# DeepSeek 64case: CLAFR vs Progent vs DRIFT",
        "",
        f"- group: `{args.group}`",
        f"- expected_cases: `{len(expected)}`",
        "- model: `deepseek-v4-flash`",
        "- note: Progent/DRIFT are same-LLM adapted original baselines, not paper-number reproductions.",
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
    (args.root / f"{args.group}_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
