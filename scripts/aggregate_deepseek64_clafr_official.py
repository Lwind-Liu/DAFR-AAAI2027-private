from __future__ import annotations

import argparse
import ast
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "results" / "runs" / "deepseek64_clafr_official"

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


def _expected_case_ids() -> set[str]:
    out: set[str] = set()
    for suite, spec in SPLIT.items():
        for user_task in spec["users"]:
            for injection_task in spec["injections"]:
                out.add(f"{suite}|{user_task}|{injection_task}")
    return out


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


def _summary_for_variant(payload: dict[str, Any], variant: str) -> dict[str, Any] | None:
    for summary in payload.get("summaries", []):
        if summary.get("variant") == variant:
            return summary
    return None


def _load_rows(root: Path, group: str, variant: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    case_rows: list[dict[str, Any]] = []
    suite_rows: list[dict[str, Any]] = []
    constraint_rows: list[dict[str, Any]] = []
    for suite in SPLIT:
        results_path = root / group / suite / "results.json"
        if not results_path.exists():
            suite_rows.append({"suite": suite, "status": "missing", "path": str(results_path)})
            continue
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        summary = _summary_for_variant(payload, variant)
        if summary is None:
            suite_rows.append({"suite": suite, "status": "missing_variant", "path": str(results_path)})
            continue
        raw = summary.get("raw_results", {}) or {}
        utility_results = raw.get("utility_results", {}) or {}
        security_results = raw.get("security_results", {}) or {}
        shield = summary.get("shield", {}) or {}
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
                    "suite": suite,
                    "user_task": user_task,
                    "injection_task": injection_task,
                    "case_id": f"{suite}|{user_task}|{injection_task}",
                    "variant": variant,
                    "utility": int(utility),
                    "attack_success": int(attack_success),
                    "safety": int(not attack_success),
                    "jss": int(utility and not attack_success),
                    "path": str(results_path),
                }
            )
        violated_counter: Counter[str] = Counter()
        block_counter: Counter[str] = Counter()
        for log in shield.get("decision_logs", []) or []:
            decision = str(log.get("decision", ""))
            for constraint in log.get("violated_facets", []) or []:
                violated_counter[str(constraint)] += 1
                if decision == "BLOCK":
                    block_counter[str(constraint)] += 1
        for constraint, count in violated_counter.most_common():
            constraint_rows.append(
                {
                    "suite": suite,
                    "constraint": constraint,
                    "violated_count": count,
                    "blocked_count": block_counter.get(constraint, 0),
                }
            )
        suite_case_rows = [row for row in case_rows if row["suite"] == suite]
        suite_rows.append(
            {
                "suite": suite,
                "status": "ok",
                "cases": len(suite_case_rows),
                "utility": mean([row["utility"] for row in suite_case_rows]) if suite_case_rows else 0.0,
                "attack_success": mean([row["attack_success"] for row in suite_case_rows]) if suite_case_rows else 0.0,
                "safety": mean([row["safety"] for row in suite_case_rows]) if suite_case_rows else 0.0,
                "jss": mean([row["jss"] for row in suite_case_rows]) if suite_case_rows else 0.0,
                "elapsed_seconds": summary.get("elapsed_seconds", ""),
                "evaluated_tool_calls": shield.get("evaluated_tool_calls", ""),
                "blocked_tool_calls": shield.get("blocked_tool_calls", ""),
                "changed_tool_calls": shield.get("changed_tool_calls", ""),
                "provider_error_count": shield.get("provider_error_count", ""),
                "selected_certificate_margin_mean": shield.get("selected_certificate_margin_mean", ""),
                "path": str(results_path),
            }
        )
    return case_rows, suite_rows, constraint_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate DeepSeek AgentDojo official 64case CLAFR results.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--group", default="official64")
    parser.add_argument("--variant", default="clafr_full")
    args = parser.parse_args()

    case_rows, suite_rows, constraint_rows = _load_rows(args.root, args.group, args.variant)
    expected = _expected_case_ids()
    seen = {str(row["case_id"]) for row in case_rows}
    missing = sorted(expected - seen)
    aggregate = {
        "schema": "deepseek64-clafr-official-aggregate-v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "official_full_agent_loop": True,
        "model": "deepseek-v4-flash",
        "benchmark_version": "v1.2.2",
        "attack": "important_instructions",
        "variant": args.variant,
        "group": args.group,
        "case_count": len(case_rows),
        "expected_case_count": len(expected),
        "missing_case_count": len(missing),
        "missing_cases": missing,
        "utility": mean([row["utility"] for row in case_rows]) if case_rows else 0.0,
        "attack_success": mean([row["attack_success"] for row in case_rows]) if case_rows else 0.0,
        "safety": mean([row["safety"] for row in case_rows]) if case_rows else 0.0,
        "jss": mean([row["jss"] for row in case_rows]) if case_rows else 0.0,
        "suite_rows": suite_rows,
    }
    args.root.mkdir(parents=True, exist_ok=True)
    _write_csv(args.root / "case_rows.csv", case_rows)
    _write_csv(args.root / "suite_rows.csv", suite_rows)
    _write_csv(args.root / "constraint_rows.csv", constraint_rows)
    (args.root / "aggregate.json").write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    top_constraints: defaultdict[str, int] = defaultdict(int)
    for row in constraint_rows:
        top_constraints[str(row["constraint"])] += int(row["blocked_count"] or 0)
    lines = [
        "# DeepSeek AgentDojo Official 64case CLAFR",
        "",
        f"- official_full_agent_loop: `{aggregate['official_full_agent_loop']}`",
        f"- model: `{aggregate['model']}`",
        f"- benchmark_version: `{aggregate['benchmark_version']}`",
        f"- attack: `{aggregate['attack']}`",
        f"- variant: `{aggregate['variant']}`",
        f"- cases: `{aggregate['case_count']}/{aggregate['expected_case_count']}`",
        f"- utility: `{aggregate['utility']:.3f}`",
        f"- attack_success: `{aggregate['attack_success']:.3f}`",
        f"- safety: `{aggregate['safety']:.3f}`",
        f"- joint_safe_success: `{aggregate['jss']:.3f}`",
        "",
        "## Suites",
        "",
        "| suite | cases | utility | ASR | safety | JSS | evaluated | blocked |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in suite_rows:
        if row.get("status") != "ok":
            lines.append(f"| {row['suite']} | 0 | missing | missing | missing | missing |  |  |")
            continue
        lines.append(
            f"| {row['suite']} | {row['cases']} | {float(row['utility']):.3f} | "
            f"{float(row['attack_success']):.3f} | {float(row['safety']):.3f} | {float(row['jss']):.3f} | "
            f"{row['evaluated_tool_calls']} | {row['blocked_tool_calls']} |"
        )
    lines.extend(["", "## Top Blocked Constraints", ""])
    if top_constraints:
        for constraint, count in sorted(top_constraints.items(), key=lambda item: (-item[1], item[0]))[:10]:
            lines.append(f"- `{constraint}`: {count}")
    else:
        lines.append("- none")
    if missing:
        lines.extend(["", "## Missing Cases", ""])
        lines.extend(f"- `{case}`" for case in missing)
    (args.root / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"deepseek64_clafr_official_aggregate,{args.root / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
