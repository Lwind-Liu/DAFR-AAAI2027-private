from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


MODEL_PREFIX = "gpt-5.4-mini/"
BASELINES = (
    "no_defense",
    "sandwich",
    "reminder",
    "spotlighting",
    "piguard",
    "protectai",
    "progent",
    "drift",
)
DISPLAY_NAMES = {
    "clafr": "CLAFR",
    "no_defense": "No Defense",
    "sandwich": "Sandwich",
    "reminder": "Reminder",
    "spotlighting": "Spotlighting",
    "piguard": "PIGuard",
    "protectai": "ProtectAI",
    "progent": "Progent",
    "drift": "DRIFT",
}

# GPT-5.4-mini Static columns in the supplied Word table. These cover the
# first three AgentDojo suites: 57 clean cases and 389 attacked cases.
WORD_STATIC_PERCENTAGES = {
    "no_defense": (77.2, 6.9, 60.2),
    "sandwich": (86.0, 2.8, 67.6),
    "reminder": (80.7, 0.8, 66.6),
    "spotlighting": (70.2, 3.1, 61.7),
    "piguard": (47.4, 0.0, 33.9),
    "protectai": (50.9, 3.1, 34.4),
    "progent": (73.7, 1.8, 56.0),
    "drift": (50.9, 0.3, 46.3),
}
WORKSPACE_CLEAN_CASES = 14
WORKSPACE_ATTACK_CASES = 196
FULL_CLEAN_CASES = 71
FULL_ATTACK_CASES = 585
FOUR_SUITES = ("banking", "slack", "travel", "workspace")


def _load_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in root.rglob("*.json"):
        if path.name.startswith(("run_manifest", "job_results", "gpt54mini_")):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        pipeline = payload.get("pipeline_name")
        if not isinstance(pipeline, str) or not pipeline.startswith(MODEL_PREFIX):
            continue
        rows.append(
            {
                "method": pipeline.removeprefix(MODEL_PREFIX),
                "suite": payload.get("suite_name"),
                "attack": bool(payload.get("injection_task_id")),
                "utility": bool(payload.get("utility")),
                "security": bool(payload.get("security")),
                "error": payload.get("error"),
                "path": str(path),
            }
        )
    return rows


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for method in ("clafr", *BASELINES):
        method_rows = [row for row in rows if row["method"] == method]
        clean = [row for row in method_rows if not row["attack"]]
        attack = [row for row in method_rows if row["attack"]]
        suite_metrics: dict[str, dict[str, Any]] = {}
        for suite in FOUR_SUITES:
            suite_rows = [row for row in method_rows if row["suite"] == suite]
            suite_clean = [row for row in suite_rows if not row["attack"]]
            suite_attack = [row for row in suite_rows if row["attack"]]
            suite_metrics[suite] = {
                "clean_cases": len(suite_clean),
                "clean_successes": sum(row["utility"] for row in suite_clean),
                "attack_cases": len(suite_attack),
                "attack_utility_successes": sum(row["utility"] for row in suite_attack),
                "attack_successes": sum(row["security"] for row in suite_attack),
            }
        output[method] = {
            "clean_cases": len(clean),
            "clean_successes": sum(row["utility"] for row in clean),
            "attack_cases": len(attack),
            "attack_utility_successes": sum(row["utility"] for row in attack),
            "attack_successes": sum(row["security"] for row in attack),
            "errors": sum(row["error"] is not None for row in method_rows),
            "suite_metrics": suite_metrics,
        }
    return output


def _pct(successes: int, cases: int) -> float:
    return 100.0 * successes / cases if cases else 0.0


def _macro(values: list[float]) -> float:
    if not values:
        raise ValueError("Cannot average an empty metric list")
    return sum(values) / len(values)


def _suite_metric(entry: dict[str, Any], numerator: str, denominator: str) -> float:
    return _pct(int(entry[numerator]), int(entry[denominator]))


def _four_suite_clafr_metrics(clafr: dict[str, Any]) -> tuple[float, float, float]:
    suites = clafr.get("suite_metrics", {})
    if set(suites) != set(FOUR_SUITES):
        raise ValueError(f"CLAFR suite coverage mismatch: {sorted(suites)}")
    clean = _macro([
        _suite_metric(suites[suite], "clean_successes", "clean_cases")
        for suite in FOUR_SUITES
    ])
    asr = _macro([
        _suite_metric(suites[suite], "attack_successes", "attack_cases")
        for suite in FOUR_SUITES
    ])
    attack_utility = _macro([
        _suite_metric(suites[suite], "attack_utility_successes", "attack_cases")
        for suite in FOUR_SUITES
    ])
    return clean, asr, attack_utility


def _aggregate(summary: dict[str, Any]) -> list[dict[str, Any]]:
    clafr = summary["clafr"]
    clafr_clean, clafr_asr, clafr_attack_utility = _four_suite_clafr_metrics(clafr)
    table = [
        {
            "method": "CLAFR",
            "clean_utility": clafr_clean,
            "static_asr": clafr_asr,
            "static_attack_utility": clafr_attack_utility,
            "clean_cases": clafr["clean_cases"],
            "attack_cases": clafr["attack_cases"],
            "complete": clafr["clean_cases"] == FULL_CLEAN_CASES
            and clafr["attack_cases"] == FULL_ATTACK_CASES
            and clafr["errors"] == 0,
            "source": "four-suite rerun; unweighted suite macro",
        }
    ]
    for method in BASELINES:
        clean_pct, asr_pct, attack_utility_pct = WORD_STATIC_PERCENTAGES[method]
        workspace = summary[method]
        workspace_clean = _pct(workspace["clean_successes"], workspace["clean_cases"])
        workspace_asr = _pct(workspace["attack_successes"], workspace["attack_cases"])
        workspace_attack_utility = _pct(
            workspace["attack_utility_successes"], workspace["attack_cases"]
        )
        table.append(
            {
                "method": DISPLAY_NAMES[method],
                "clean_utility": (3.0 * clean_pct + workspace_clean) / 4.0,
                "static_asr": (3.0 * asr_pct + workspace_asr) / 4.0,
                "static_attack_utility": (
                    3.0 * attack_utility_pct + workspace_attack_utility
                ) / 4.0,
                "clean_cases": FULL_CLEAN_CASES,
                "attack_cases": FULL_ATTACK_CASES,
                "complete": workspace["clean_cases"] == WORKSPACE_CLEAN_CASES
                and workspace["attack_cases"] == WORKSPACE_ATTACK_CASES
                and workspace["errors"] == 0,
                "source": "Word first-three-suite macro + workspace rerun; unweighted suite macro",
            }
        )
    return table


def _write_outputs(root: Path, summary: dict[str, Any], table: list[dict[str, Any]]) -> None:
    payload = {
        "schema": "gpt54mini-agentdojo-four-suite-v1",
        "model": "gpt-5.4-mini",
        "benchmark_version": "v1.2.2",
        "coverage": summary,
        "table": table,
    }
    (root / "gpt54mini_four_suite_results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    with (root / "gpt54mini_four_suite_results.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=table[0].keys())
        writer.writeheader()
        writer.writerows(table)

    lines = [
        "# GPT-5.4-mini AgentDojo v1.2.2 four-suite results",
        "",
        "| Method | Clean Utility | Static ASR | Static Attack Utility | Cases | Complete |",
        "|---|---:|---:|---:|---:|:---:|",
    ]
    for row in table:
        lines.append(
            f"| {row['method']} | {row['clean_utility']:.1f} | "
            f"{row['static_asr']:.1f} | {row['static_attack_utility']:.1f} | "
            f"{row['clean_cases']}/{row['attack_cases']} | "
            f"{'yes' if row['complete'] else 'no'} |"
        )
    lines += [
        "",
        "All metrics are unweighted four-suite macro-averages. Baseline values combine "
        "the supplied Word table's first-three-suite macro-average with the measured "
        "workspace rate as (3 * base3 + workspace) / 4. CLAFR is computed directly "
        "from its four measured suite rates.",
    ]
    (root / "gpt54mini_four_suite_results.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.result_root.resolve()
    rows = _load_rows(root)
    summary = _summary(rows)
    table = _aggregate(summary)
    _write_outputs(root, summary, table)
    print(json.dumps(table, indent=2, ensure_ascii=False))
    return 0 if all(row["complete"] for row in table) else 2


if __name__ == "__main__":
    raise SystemExit(main())
