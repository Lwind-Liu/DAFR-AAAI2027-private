from __future__ import annotations

import argparse
import ast
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any


ATTACK_EXPECTED = 629
CLEAN_EXPECTED = 97

RUNNER_METHODS = {
    "clafr_full": ("CLAFR", "paper_candidate"),
    "agentdojo_tool_filter": ("Tool Filter", "official_agentdojo_baseline"),
    "agentdojo_spotlighting": ("Spotlighting", "official_agentdojo_baseline"),
    "agentdojo_repeat_user_prompt": ("Repeat User Prompt", "official_agentdojo_baseline"),
}

AUTODOJO_METHODS = {
    "progent": ("Progent-DeepSeek", "external_paper_baseline"),
    "drift": ("DRIFT-DeepSeek", "external_paper_baseline"),
}

SUITES = {"workspace", "travel", "banking", "slack"}


def _canonical_suite(value: Any) -> str:
    text = str(value)
    if text in SUITES:
        return text
    head = text.split("__", 1)[0]
    if head in SUITES:
        return head
    return text


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


def _case_key(suite: str, raw_key: Any, *, group: str) -> tuple[str, str, str]:
    suite = _canonical_suite(suite)
    if isinstance(raw_key, tuple):
        parsed = raw_key
    else:
        try:
            parsed = ast.literal_eval(str(raw_key))
        except Exception:
            parsed = raw_key
    if isinstance(parsed, tuple):
        if len(parsed) >= 2:
            user_task = str(parsed[0])
            injection_task = str(parsed[1])
        elif len(parsed) == 1:
            user_task = str(parsed[0])
            injection_task = "none"
        else:
            user_task = str(raw_key)
            injection_task = "none"
    else:
        user_task = str(parsed)
        injection_task = "none"
    if group == "clean":
        injection_task = "none"
    return suite, user_task, injection_task


def _summary_for_variant(payload: dict[str, Any], variant: str) -> dict[str, Any] | None:
    for summary in payload.get("summaries", []) or []:
        if summary.get("variant") == variant:
            return summary
    return None


def _add_case_row(
    rows: list[dict[str, Any]],
    *,
    method_key: str,
    method: str,
    role: str,
    source: str,
    group: str,
    suite: str,
    user_task: str,
    injection_task: str,
    utility: bool,
    attack_success: bool | None,
    path: Path,
) -> None:
    suite = _canonical_suite(suite)
    rows.append(
        {
            "method_key": method_key,
            "method": method,
            "role": role,
            "source": source,
            "group": group,
            "suite": suite,
            "user_task": user_task,
            "injection_task": injection_task,
            "case_id": f"{suite}|{user_task}|{injection_task}",
            "utility": int(utility),
            "attack_success": "" if attack_success is None else int(attack_success),
            "safety": "" if attack_success is None else int(not attack_success),
            "jss": "" if attack_success is None else int(utility and not attack_success),
            "path": str(path),
        }
    )


def _load_runner_rows(root: Path, group: str, variants: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    group_root = root / f"runner_{group}"
    seen: set[tuple[str, str, str, str]] = set()
    summary_pairs: set[tuple[str, str]] = set()
    for results_path in sorted(group_root.glob("*/results.json")):
        suite = _canonical_suite(results_path.parent.name)
        payload = json.loads(results_path.read_text(encoding="utf-8"))
        for variant in variants:
            if variant not in RUNNER_METHODS:
                continue
            summary = _summary_for_variant(payload, variant)
            if summary is None:
                continue
            summary_pairs.add((variant, suite))
            method, role = RUNNER_METHODS[variant]
            raw = summary.get("raw_results", {}) or {}
            utility_results = raw.get("utility_results", {}) or {}
            security_results = raw.get("security_results", {}) or {}
            for raw_key, raw_utility in utility_results.items():
                utility = _bool(raw_utility)
                if utility is None:
                    continue
                parsed_suite, user_task, injection_task = _case_key(suite, raw_key, group=group)
                attack_success = None
                if group == "attack":
                    if injection_task == "none":
                        continue
                    attack_success = _bool(security_results.get(raw_key))
                    if attack_success is None:
                        continue
                seen.add((variant, parsed_suite, user_task, injection_task))
                _add_case_row(
                    rows,
                    method_key=variant,
                    method=method,
                    role=role,
                    source="agentdojo_runner",
                    group=group,
                    suite=parsed_suite,
                    user_task=user_task,
                    injection_task=injection_task,
                    utility=utility,
                    attack_success=attack_success,
                    path=results_path,
                )
    for variant in variants:
        if variant not in RUNNER_METHODS:
            continue
        method, role = RUNNER_METHODS[variant]
        for path in sorted(group_root.glob(f"*/{variant}/*/*/*/*/*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            suite = _canonical_suite(payload.get("suite_name") or path.parts[-5])
            if (variant, suite) in summary_pairs:
                continue
            user_task = str(payload.get("user_task_id") or path.parts[-3])
            injection_task = str(payload.get("injection_task_id") or path.stem)
            if group == "clean":
                injection_task = "none"
            key = (variant, suite, user_task, injection_task)
            if key in seen:
                continue
            utility = _bool(payload.get("utility"))
            if utility is None:
                continue
            attack_success = None
            if group == "attack":
                if injection_task == "none":
                    continue
                attack_success = _bool(payload.get("security"))
                if attack_success is None:
                    continue
            seen.add(key)
            _add_case_row(
                rows,
                method_key=variant,
                method=method,
                role=role,
                source="agentdojo_runner_trace",
                group=group,
                suite=suite,
                user_task=user_task,
                injection_task=injection_task,
                utility=utility,
                attack_success=attack_success,
                path=path,
            )
    return rows


def _load_autodojo_rows(root: Path, group: str, defenses: list[str], model_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    group_root = root / f"autodojo_{group}" / model_id
    for defense in defenses:
        if defense not in AUTODOJO_METHODS:
            continue
        method, role = AUTODOJO_METHODS[defense]
        defense_root = group_root / defense
        if not defense_root.exists():
            continue
        for path in sorted(defense_root.glob("*/*/*/*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            suite = _canonical_suite(payload.get("suite_name") or path.parts[-4])
            user_task = str(payload.get("user_task_id") or path.parts[-3])
            injection_task = str(payload.get("injection_task_id") or ("none" if group == "clean" else path.stem))
            if group == "clean":
                injection_task = "none"
            utility = _bool(payload.get("utility"))
            if utility is None:
                continue
            attack_success = None
            if group == "attack":
                attack_success = _bool(payload.get("security"))
                if attack_success is None:
                    continue
            _add_case_row(
                rows,
                method_key=defense,
                method=method,
                role=role,
                source="autodojo",
                group=group,
                suite=suite,
                user_task=user_task,
                injection_task=injection_task,
                utility=utility,
                attack_success=attack_success,
                path=path,
            )
    return rows


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest_by_key: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    latest_mtime: dict[tuple[str, str, str, str, str], float] = {}
    for row in rows:
        row["suite"] = _canonical_suite(row["suite"])
        row["case_id"] = f"{row['suite']}|{row['user_task']}|{row['injection_task']}"
        key = (
            str(row["method_key"]),
            str(row["group"]),
            str(row["suite"]),
            str(row["user_task"]),
            str(row["injection_task"]),
        )
        try:
            mtime = Path(str(row["path"])).stat().st_mtime
        except OSError:
            mtime = 0.0
        if key not in latest_by_key or mtime >= latest_mtime[key]:
            latest_by_key[key] = row
            latest_mtime[key] = mtime
    return list(latest_by_key.values())


def _aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    method_order = [
        "clafr_full",
        "progent",
        "drift",
        "agentdojo_tool_filter",
        "agentdojo_spotlighting",
        "agentdojo_repeat_user_prompt",
    ]
    rows_by_method = {key: [row for row in rows if row["method_key"] == key] for key in method_order}
    aggregate_rows: list[dict[str, Any]] = []
    for key in method_order:
        method_rows = rows_by_method[key]
        if key in RUNNER_METHODS:
            method, role = RUNNER_METHODS[key]
        else:
            method, role = AUTODOJO_METHODS[key]
        clean = [row for row in method_rows if row["group"] == "clean"]
        attack = [row for row in method_rows if row["group"] == "attack"]
        attack_success_values = [int(row["attack_success"]) for row in attack if row["attack_success"] != ""]
        jss_values = [int(row["jss"]) for row in attack if row["jss"] != ""]
        aggregate_rows.append(
            {
                "method_key": key,
                "method": method,
                "role": role,
                "clean_cases": len(clean),
                "expected_clean_cases": CLEAN_EXPECTED,
                "missing_clean_cases": max(0, CLEAN_EXPECTED - len(clean)),
                "clean_utility": mean([int(row["utility"]) for row in clean]) if clean else 0.0,
                "attack_cases": len(attack),
                "expected_attack_cases": ATTACK_EXPECTED,
                "missing_attack_cases": max(0, ATTACK_EXPECTED - len(attack)),
                "utility_under_attack": mean([int(row["utility"]) for row in attack]) if attack else 0.0,
                "attack_success": mean(attack_success_values) if attack_success_values else 0.0,
                "safety": 1.0 - mean(attack_success_values) if attack_success_values else 0.0,
                "jss": mean(jss_values) if jss_values else 0.0,
            }
        )
    return aggregate_rows


def _suite_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    keys = sorted({(row["method_key"], row["method"], row["role"], row["group"], row["suite"]) for row in rows})
    for method_key, method, role, group, suite in keys:
        selected = [
            row
            for row in rows
            if row["method_key"] == method_key and row["group"] == group and row["suite"] == suite
        ]
        attack_values = [int(row["attack_success"]) for row in selected if row["attack_success"] != ""]
        jss_values = [int(row["jss"]) for row in selected if row["jss"] != ""]
        out.append(
            {
                "method_key": method_key,
                "method": method,
                "role": role,
                "group": group,
                "suite": suite,
                "cases": len(selected),
                "utility": mean([int(row["utility"]) for row in selected]) if selected else 0.0,
                "attack_success": "" if group == "clean" else (mean(attack_values) if attack_values else 0.0),
                "safety": "" if group == "clean" else (1.0 - mean(attack_values) if attack_values else 0.0),
                "jss": "" if group == "clean" else (mean(jss_values) if jss_values else 0.0),
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate AgentDojo DeepSeek full 629 attack + 97 clean results.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model-id", default="deepseek-v4-flash")
    parser.add_argument("--benchmark-version", default="v1")
    parser.add_argument(
        "--runner-variants",
        nargs="+",
        default=[
            "clafr_full",
            "agentdojo_tool_filter",
            "agentdojo_spotlighting",
            "agentdojo_repeat_user_prompt",
        ],
    )
    parser.add_argument("--autodojo-defenses", nargs="+", default=["progent", "drift"])
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for group in ("clean", "attack"):
        rows.extend(_load_runner_rows(args.root, group, args.runner_variants))
        rows.extend(_load_autodojo_rows(args.root, group, args.autodojo_defenses, args.model_id))
    rows = _dedupe_rows(rows)

    aggregate_rows = _aggregate(rows)
    suite_rows = _suite_rows(rows)
    _write_csv(args.root / "full_case_rows.csv", rows)
    _write_csv(args.root / "full_suite_rows.csv", suite_rows)
    _write_csv(args.root / "full_aggregate_rows.csv", aggregate_rows)
    (args.root / "full_aggregate.json").write_text(
        json.dumps(
            {
                "schema": "agentdojo-deepseek-full-629-97-aggregate-v1",
                "benchmark_version": args.benchmark_version,
                "expected_attack_cases": ATTACK_EXPECTED,
                "expected_clean_cases": CLEAN_EXPECTED,
                "rows": aggregate_rows,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "# AgentDojo DeepSeek Full 629+97",
        "",
        f"- benchmark version: `{args.benchmark_version}`",
        f"- expected clean cases: `{CLEAN_EXPECTED}`",
        f"- expected attack cases: `{ATTACK_EXPECTED}`",
        "",
        "| method | role | clean cases | clean utility | attack cases | utility under attack | ASR | safety | JSS | missing clean | missing attack |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in aggregate_rows:
        lines.append(
            f"| {row['method']} | `{row['role']}` | {row['clean_cases']} | {row['clean_utility']:.3f} | "
            f"{row['attack_cases']} | {row['utility_under_attack']:.3f} | {row['attack_success']:.3f} | "
            f"{row['safety']:.3f} | {row['jss']:.3f} | {row['missing_clean_cases']} | {row['missing_attack_cases']} |"
        )
    (args.root / "full_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"agentdojo_full_629_97_aggregate,{args.root / 'full_comparison.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
