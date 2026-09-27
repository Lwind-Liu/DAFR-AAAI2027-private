from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any


SUITES = ("banking", "slack", "travel")
EXPECTED_CLEAN = {"banking": 16, "slack": 21, "travel": 20}
EXPECTED_ATTACK = {"banking": 144, "slack": 105, "travel": 140}

BASELINE_ROWS = [
    ("No Defense", 89.5, 22.6, 77.4),
    ("Sandwich", 91.2, 14.7, 77.4),
    ("Reminder", 89.5, 4.9, 81.0),
    ("Spotlighting", 75.4, 13.9, 80.5),
    ("PromptGuard", 89.5, 21.3, 70.2),
    ("PIGuard", 45.6, 0.0, 40.9),
    ("ProtectAI", 47.4, 4.6, 31.9),
    ("DataFilter", 91.2, 2.3, 81.5),
    ("Progent", 78.9, 2.8, 73.8),
    ("DRIFT", 59.6, 1.3, 48.1),
]

DISPLAY = {
    "clafr": "CLAFR",
    "clafr_no_evidence_projection": "CLAFR w/o Evidence Projection",
    "clafr_no_action_evidence_lifting": "CLAFR w/o Action-Evidence Lifting",
    "clafr_no_dynamic_geometry": "CLAFR w/o Dynamic Geometry",
    "clafr_no_decision_repair": "CLAFR w/o Decision & Repair",
    "clafr_no_observation_projection": "CLAFR legacy w/o ObsProj",
    "clafr_no_action_lifting": "CLAFR legacy w/o ActionGeo",
    "clafr_no_format_projection": "CLAFR legacy w/o FormatProj",
    "clafr_no_response_projection": "CLAFR legacy w/o RespProj",
    "clafr_no_untrusted_geometry": "CLAFR legacy w/o UntrustedGeo",
}

DISPLAY_ORDER = {
    "clafr": 0,
    "clafr_no_evidence_projection": 1,
    "clafr_no_action_evidence_lifting": 2,
    "clafr_no_dynamic_geometry": 3,
    "clafr_no_decision_repair": 4,
    "clafr_no_observation_projection": 101,
    "clafr_no_action_lifting": 102,
    "clafr_no_format_projection": 103,
    "clafr_no_response_projection": 104,
    "clafr_no_untrusted_geometry": 105,
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


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _defense_dirs(root: Path, model_id: str) -> list[Path]:
    model_root = root / model_id
    if not model_root.exists():
        return []
    return sorted(path for path in model_root.iterdir() if path.is_dir())


def _suite_values(defense_dir: Path, suite: str) -> dict[str, Any]:
    suite_dir = defense_dir / suite
    clean_values: list[int] = []
    attack_utility_values: list[int] = []
    attack_success_values: list[int] = []
    clean_paths = sorted(suite_dir.glob("user_task_*/none/none.json"))
    attack_paths = sorted(suite_dir.glob("user_task_*/important_instructions/injection_task_*.json"))
    for path in clean_paths:
        payload = _read_json(path)
        if payload is None:
            continue
        utility = _bool(payload.get("utility"))
        if utility is not None:
            clean_values.append(int(utility))
    for path in attack_paths:
        payload = _read_json(path)
        if payload is None:
            continue
        utility = _bool(payload.get("utility"))
        security = _bool(payload.get("security"))
        if utility is not None:
            attack_utility_values.append(int(utility))
        if security is not None:
            attack_success_values.append(int(security))
    return {
        "suite": suite,
        "clean_cases": len(clean_values),
        "expected_clean_cases": EXPECTED_CLEAN[suite],
        "clean_utility": mean(clean_values) if clean_values else 0.0,
        "attack_cases": len(attack_utility_values),
        "expected_attack_cases": EXPECTED_ATTACK[suite],
        "static_attack_utility": mean(attack_utility_values) if attack_utility_values else 0.0,
        "static_asr": mean(attack_success_values) if attack_success_values else 0.0,
    }


def _aggregate_defense(defense_dir: Path) -> dict[str, Any]:
    suite_rows = [_suite_values(defense_dir, suite) for suite in SUITES]
    return {
        "method_key": defense_dir.name,
        "method": DISPLAY.get(defense_dir.name, defense_dir.name),
        "clean_cases": sum(row["clean_cases"] for row in suite_rows),
        "expected_clean_cases": sum(EXPECTED_CLEAN.values()),
        "attack_cases": sum(row["attack_cases"] for row in suite_rows),
        "expected_attack_cases": sum(EXPECTED_ATTACK.values()),
        "clean_utility": mean(row["clean_utility"] for row in suite_rows),
        "static_asr": mean(row["static_asr"] for row in suite_rows),
        "static_attack_utility": mean(row["static_attack_utility"] for row in suite_rows),
        "suite_rows": suite_rows,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key == "suite_rows":
                continue
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate AutoDojo Table-II style AgentDojo results.")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model-id", default="deepseek-v4-flash")
    parser.add_argument("--benchmark-version", default="v1.2.2")
    args = parser.parse_args()

    rows = [_aggregate_defense(path) for path in _defense_dirs(args.root, args.model_id)]
    rows = [row for row in rows if row["method_key"].startswith("clafr")]
    rows.sort(key=lambda row: (DISPLAY_ORDER.get(row["method_key"], 1000), row["method_key"]))

    _write_csv(args.root / "autodojo_table_aggregate.csv", rows)
    (args.root / "autodojo_table_aggregate.json").write_text(
        json.dumps(
            {
                "schema": "autodojo-table-agentdojo-aggregate-v1",
                "model_id": args.model_id,
                "benchmark_version": args.benchmark_version,
                "suites": SUITES,
                "expected_clean_cases": sum(EXPECTED_CLEAN.values()),
                "expected_attack_cases": sum(EXPECTED_ATTACK.values()),
                "macro_average_over_suites": True,
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    lines = [
        "# AutoDojo Table-II Style Comparison",
        "",
        f"- model: `{args.model_id}`",
        f"- benchmark version: `{args.benchmark_version}`",
        "- suites: `banking`, `slack`, `travel`",
        f"- expected clean cases: `{sum(EXPECTED_CLEAN.values())}`",
        f"- expected static attack cases: `{sum(EXPECTED_ATTACK.values())}`",
        "- aggregation: unweighted macro-average over the three suites, matching AutoDojo aggregation.",
        "",
        "| Method | Clean Utility | Static ASR | Static Attack Utility | Cases |",
        "|---|---:|---:|---:|---:|",
    ]
    for method, clean, asr, attack_utility in BASELINE_ROWS:
        lines.append(f"| {method} | {clean:.1f} | {asr:.1f} | {attack_utility:.1f} | 57/389 |")
    for row in rows:
        lines.append(
            f"| {row['method']} | {100 * row['clean_utility']:.1f} | "
            f"{100 * row['static_asr']:.1f} | {100 * row['static_attack_utility']:.1f} | "
            f"{row['clean_cases']}/{row['attack_cases']} |"
        )
    (args.root / "autodojo_table_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"autodojo_table_aggregate,{args.root / 'autodojo_table_comparison.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
