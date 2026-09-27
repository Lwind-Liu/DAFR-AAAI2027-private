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
        "users": ["user_task_29", "user_task_21"],
        "injections": ["injection_task_1", "injection_task_5", "injection_task_4", "injection_task_3"],
    },
    "travel": {
        "users": ["user_task_10", "user_task_7"],
        "injections": ["injection_task_0", "injection_task_5", "injection_task_1", "injection_task_6"],
    },
    "banking": {
        "users": ["user_task_4", "user_task_13"],
        "injections": ["injection_task_8", "injection_task_3", "injection_task_1", "injection_task_0"],
    },
    "slack": {
        "users": ["user_task_14", "user_task_13"],
        "injections": ["injection_task_1", "injection_task_2", "injection_task_3", "injection_task_4"],
    },
}

METHODS = {
    "baseline": ("No Defense", "basic_baseline"),
    "prompt_policy": ("Prompt-only Policy", "custom_prompt_baseline"),
    "agentdojo_reminder": ("AgentDojo Reminder", "custom_prompt_baseline"),
    "agentdojo_tool_filter": ("AgentDojo Tool Filter", "official_agentdojo_baseline"),
    "agentdojo_spotlighting": ("AgentDojo Spotlighting", "official_agentdojo_baseline"),
    "agentdojo_repeat_user_prompt": ("AgentDojo Repeat User Prompt", "official_agentdojo_baseline"),
    "clafr_full": ("CLAFR semantic-12", "paper_candidate"),
    "progent": ("Progent-DeepSeek", "external_paper_baseline"),
    "drift": ("DRIFT-DeepSeek", "external_paper_baseline"),
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


def _case_tuple(raw_key: object) -> tuple[str, str] | None:
    try:
        parsed = ast.literal_eval(str(raw_key))
    except Exception:
        return None
    if isinstance(parsed, tuple) and len(parsed) == 2:
        return str(parsed[0]), str(parsed[1])
    return None


def _expected_cases() -> set[str]:
    return {
        f"{suite}|{user}|{inj}"
        for suite, spec in SPLIT.items()
        for user in spec["users"]
        for inj in spec["injections"]
    }


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


def _case_row(variant: str, suite: str, user: str, inj: str, utility: bool, attack_success: bool, path: Path) -> dict[str, Any]:
    method, role = METHODS[variant]
    return {
        "variant": variant,
        "method": method,
        "role": role,
        "suite": suite,
        "user_task": user,
        "injection_task": inj,
        "case_id": f"{suite}|{user}|{inj}",
        "utility": int(utility),
        "attack_success": int(attack_success),
        "safety": int(not attack_success),
        "jss": int(utility and not attack_success),
        "path": str(path),
    }


def _load_agentdojo_runner_rows(root: Path, group: str, variant: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    case_rows: list[dict[str, Any]] = []
    suite_rows: list[dict[str, Any]] = []
    for suite, spec in SPLIT.items():
        path = root / "agentdojo" / group / suite / "results.json"
        if not path.exists():
            suite_rows.append({"variant": variant, "suite": suite, "status": "missing", "path": str(path)})
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        summary = next((item for item in payload.get("summaries", []) if item.get("variant") == variant), None)
        if summary is None:
            suite_rows.append({"variant": variant, "suite": suite, "status": "missing_variant", "path": str(path)})
            continue
        raw = summary.get("raw_results", {}) or {}
        utility_results = raw.get("utility_results", {}) or {}
        security_results = raw.get("security_results", {}) or {}
        before = len(case_rows)
        expected = {f"{suite}|{u}|{i}" for u in spec["users"] for i in spec["injections"]}
        for raw_key, raw_utility in utility_results.items():
            parsed = _case_tuple(raw_key)
            if parsed is None:
                continue
            user, inj = parsed
            case_id = f"{suite}|{user}|{inj}"
            if case_id not in expected:
                continue
            utility = _bool(raw_utility)
            attack_success = _bool(security_results.get(raw_key))
            if utility is None or attack_success is None:
                continue
            case_rows.append(_case_row(variant, suite, user, inj, utility, attack_success, path))
        suite_cases = case_rows[before:]
        shield = summary.get("shield", {}) or {}
        method, role = METHODS[variant]
        suite_rows.append(
            {
                "variant": variant,
                "method": method,
                "role": role,
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
                "path": str(path),
            }
        )
    return case_rows, suite_rows


def _load_autodojo_rows(root: Path, group: str, variant: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    case_rows: list[dict[str, Any]] = []
    suite_rows: list[dict[str, Any]] = []
    log_root = root / "autodojo" / group / "deepseek-v4-flash" / variant
    for suite, spec in SPLIT.items():
        before = len(case_rows)
        missing = 0
        errors = 0
        for user in spec["users"]:
            for inj in spec["injections"]:
                path = log_root / suite / user / "important_instructions" / f"{inj}.json"
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
                case_rows.append(_case_row(variant, suite, user, inj, utility, attack_success, path))
        suite_cases = case_rows[before:]
        method, role = METHODS[variant]
        suite_rows.append(
            {
                "variant": variant,
                "method": method,
                "role": role,
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
    method, role = METHODS[variant]
    seen = {str(row["case_id"]) for row in rows}
    return {
        "variant": variant,
        "method": method,
        "role": role,
        "cases": len(rows),
        "expected_cases": len(expected),
        "missing_cases": len(expected - seen),
        "utility": mean([row["utility"] for row in rows]) if rows else 0.0,
        "attack_success": mean([row["attack_success"] for row in rows]) if rows else 0.0,
        "safety": mean([row["safety"] for row in rows]) if rows else 0.0,
        "jss": mean([row["jss"] for row in rows]) if rows else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate AgentDojo 32-case paper baselines.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--group", default="official32")
    args = parser.parse_args()

    expected = _expected_cases()
    case_rows: list[dict[str, Any]] = []
    suite_rows: list[dict[str, Any]] = []
    aggregate_rows: list[dict[str, Any]] = []

    for variant in (
        "baseline",
        "agentdojo_tool_filter",
        "agentdojo_spotlighting",
        "agentdojo_repeat_user_prompt",
        "clafr_full",
    ):
        cases, suites = _load_agentdojo_runner_rows(args.root, args.group, variant)
        case_rows.extend(cases)
        suite_rows.extend(suites)
        if cases:
            aggregate_rows.append(_aggregate(variant, cases, expected))

    for variant in ("progent", "drift"):
        cases, suites = _load_autodojo_rows(args.root, args.group, variant)
        case_rows.extend(cases)
        suite_rows.extend(suites)
        aggregate_rows.append(_aggregate(variant, cases, expected))

    _write_csv(args.root / "agentdojo32_case_rows.csv", case_rows)
    _write_csv(args.root / "agentdojo32_suite_rows.csv", suite_rows)
    _write_csv(args.root / "agentdojo32_aggregate_rows.csv", aggregate_rows)
    (args.root / "agentdojo32_aggregate.json").write_text(
        json.dumps({"schema": "agentdojo32-paper-baselines-v1", "group": args.group, "rows": aggregate_rows}, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# AgentDojo 32-Case Paper Baselines",
        "",
        f"- group: `{args.group}`",
        f"- expected_cases: `{len(expected)}`",
        "- split: first two users per suite from the frozen DeepSeek 64case split; four fixed injections per suite.",
        "",
        "| method | variant | role | cases | Utility | ASR | Safety | JSS | missing |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate_rows:
        lines.append(
            f"| {row['method']} | `{row['variant']}` | {row['role']} | {row['cases']} | "
            f"{row['utility']:.3f} | {row['attack_success']:.3f} | {row['safety']:.3f} | "
            f"{row['jss']:.3f} | {row['missing_cases']} |"
        )
    (args.root / "agentdojo32_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.root / "agentdojo32_comparison.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
