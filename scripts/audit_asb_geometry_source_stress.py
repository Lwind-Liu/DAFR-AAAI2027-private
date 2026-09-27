from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CLAFR_SRC = ROOT / "src"
EXPERIMENT_SCRIPTS = ROOT / "scripts"
GEO_SRC = ROOT / "src"
for path in (CLAFR_SRC, EXPERIMENT_SCRIPTS, GEO_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from clafr import ToolAction  # noqa: E402
from run_asb_clafr_agent_score import (  # noqa: E402
    _available_tool_schema,
    _build_cases,
    _make_selector,
    _runtime_evidence,
)


def _violated(selection: Any) -> tuple[str, ...]:
    facets: list[str] = []
    for cert in getattr(selection, "certificates", ()) or ():
        for margin in getattr(cert, "margins", ()) or ():
            if not getattr(margin, "soft", False) and float(getattr(margin, "slack", 0.0)) < 0.0:
                facets.append(str(getattr(margin, "constraint_id", "")))
    return tuple(facet for facet in facets if facet)


def _rate(num: int, den: int) -> float:
    return num / den if den else 0.0


def audit(args: argparse.Namespace) -> dict[str, Any]:
    cases = _build_cases(
        args.data_dir,
        task_nums=args.task_nums,
        attack_limit=args.attack_limit,
        max_cases=args.max_cases,
        attack_sampling=args.attack_sampling,
        case_sampling=args.case_sampling,
    )
    selector = _make_selector("clafr_full")
    rows: list[dict[str, Any]] = []
    for mode in args.tool_provenance:
        counts = Counter()
        attack_block_reasons: Counter[tuple[str, ...]] = Counter()
        normal_block_reasons: Counter[tuple[str, ...]] = Counter()
        for case in cases:
            schema = _available_tool_schema(case)
            normal_observations = [
                str(case.known_actions[str(tool["Tool Name"])]["output"])
                for tool in case.normal_tools
            ]
            for phase, observations in (
                ("first", []),
                ("after_normal_observations", normal_observations),
            ):
                evidence = _runtime_evidence(
                    case,
                    observations,
                    schema,
                    provenance_lift=True,
                    tool_provenance=mode,
                )
                attack_tool_name = str(case.attack_tool["Attacker Tool"])
                attack_action = ToolAction(
                    id=f"{case.case_id}:attack:{phase}",
                    tool_name=attack_tool_name,
                    arguments={},
                    rationale=case.user_query,
                )
                attack_selection = selector.select([attack_action], evidence)
                counts[f"{phase}_attack_total"] += 1
                if attack_selection.selected is not None:
                    counts[f"{phase}_attack_feasible"] += 1
                elif phase == "after_normal_observations":
                    attack_block_reasons[_violated(attack_selection)[:3]] += 1

                for tool in case.normal_tools:
                    normal_tool_name = str(tool["Tool Name"])
                    normal_action = ToolAction(
                        id=f"{case.case_id}:normal:{normal_tool_name}:{phase}",
                        tool_name=normal_tool_name,
                        arguments={},
                        rationale=case.user_query,
                    )
                    normal_selection = selector.select([normal_action], evidence)
                    counts[f"{phase}_normal_total"] += 1
                    if normal_selection.selected is not None:
                        counts[f"{phase}_normal_feasible"] += 1
                    elif phase == "after_normal_observations":
                        normal_block_reasons[_violated(normal_selection)[:3]] += 1

        row = {
            "tool_provenance": mode,
            "cases": len(cases),
            "first_attack_feasible": counts["first_attack_feasible"],
            "first_attack_total": counts["first_attack_total"],
            "first_attack_feasible_rate": _rate(
                counts["first_attack_feasible"], counts["first_attack_total"]
            ),
            "after_attack_feasible": counts["after_normal_observations_attack_feasible"],
            "after_attack_total": counts["after_normal_observations_attack_total"],
            "after_attack_feasible_rate": _rate(
                counts["after_normal_observations_attack_feasible"],
                counts["after_normal_observations_attack_total"],
            ),
            "first_normal_feasible": counts["first_normal_feasible"],
            "first_normal_total": counts["first_normal_total"],
            "first_normal_feasible_rate": _rate(
                counts["first_normal_feasible"], counts["first_normal_total"]
            ),
            "after_normal_feasible": counts["after_normal_observations_normal_feasible"],
            "after_normal_total": counts["after_normal_observations_normal_total"],
            "after_normal_feasible_rate": _rate(
                counts["after_normal_observations_normal_feasible"],
                counts["after_normal_observations_normal_total"],
            ),
            "top_attack_block_reasons": [
                {"facets": list(facets), "count": count}
                for facets, count in attack_block_reasons.most_common(8)
            ],
            "top_normal_block_reasons": [
                {"facets": list(facets), "count": count}
                for facets, count in normal_block_reasons.most_common(8)
            ],
        }
        rows.append(row)
    return {
        "schema": "asb-geometry-source-stress-v1",
        "benchmark": "ToolSafe-ASB-OPI",
        "diagnostic_only": True,
        "case_sampling": args.case_sampling,
        "attack_sampling": args.attack_sampling,
        "task_nums": args.task_nums,
        "attack_limit": args.attack_limit,
        "max_cases": args.max_cases,
        "rows": rows,
        "interpretation": (
            "This no-API audit evaluates geometric feasibility of known normal and "
            "known attacker-supplied tools. It is not a task-level ASR estimate. "
            "It tests whether CLAFR's feasible region depends on runtime source "
            "provenance for separating externally supplied tools."
        ),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        key
        for key in rows[0]
        if key not in {"top_attack_block_reasons", "top_normal_block_reasons"}
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})


def _write_md(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# ASB Geometry Source Stress",
        "",
        f"- benchmark: `{result['benchmark']}`",
        "- diagnostic only: `yes`",
        f"- task nums: `{result['task_nums']}`",
        f"- attack limit: `{result['attack_limit']}`",
        f"- max cases: `{result['max_cases']}`",
        "",
        "| Tool provenance | Cases | Attack feasible after observations | Normal feasible after observations |",
        "|---|---:|---:|---:|",
    ]
    for row in result["rows"]:
        lines.append(
            f"| `{row['tool_provenance']}` | {row['cases']} | "
            f"{row['after_attack_feasible']}/{row['after_attack_total']} "
            f"({row['after_attack_feasible_rate']:.3f}) | "
            f"{row['after_normal_feasible']}/{row['after_normal_total']} "
            f"({row['after_normal_feasible_rate']:.3f}) |"
        )
    lines.extend(
        [
            "",
            "Interpretation: source-provenance is part of the runtime evidence boundary. "
            "The no-label condition is a stress test showing what happens when that "
            "boundary is unavailable.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ASB CLAFR source-provenance geometry without API calls.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT / "external" / "official_benchmarks" / "ToolSafe" / "benchmark" / "asb" / "data",
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--task-nums", type=int, default=5)
    parser.add_argument("--attack-limit", type=int, default=4)
    parser.add_argument("--attack-sampling", choices=["prefix", "stratified"], default="stratified")
    parser.add_argument("--case-sampling", choices=["prefix", "agent_round_robin"], default="agent_round_robin")
    parser.add_argument("--max-cases", type=int, default=200)
    parser.add_argument("--tool-provenance", nargs="+", default=["source_trust", "no_label"])
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    result = audit(args)
    (args.out_dir / "asb_geometry_source_stress.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(args.out_dir / "asb_geometry_source_stress.csv", result["rows"])
    _write_md(args.out_dir / "asb_geometry_source_stress.md", result)
    print(args.out_dir / "asb_geometry_source_stress.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
