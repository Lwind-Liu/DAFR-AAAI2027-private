from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import aggregate_asb_clafr_results as aggregate


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_ROOT = ROOT / "results" / "runs"

METHODS = (
    ("No Defense", "asb_204_final_v2_baseline", "baseline"),
    ("Delimiter", "asb_204_final_v2_delimiter", "asb_delimiter"),
    ("Instructional Prevention", "asb_204_final_v2_instruction", "asb_instruction"),
    ("Observation Sandwich", "asb_204_final_v2_sandwich", "asb_sandwich"),
    ("TS-Flow", "asb_204_final_v2_tsflow", "ts_flow_style"),
    ("Progent-ASB", "asb_204_final_v2_progent", "progent"),
    ("DRIFT-ASB", "asb_204_final_v2_drift", "drift"),
    ("CLAFR", "asb_204_final_v3_clafr", "clafr_feedback"),
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt(value: float) -> str:
    return f"{value:.3f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolidate the frozen 204-case ASB comparison.")
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_RESULTS_ROOT / "asb_204_final_consolidated_v1",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    expected_cases: list[str] | None = None
    expected_protocol: tuple[Any, ...] | None = None
    rows: list[dict[str, Any]] = []
    source_roots: dict[str, str] = {}

    for label, root_name, variant in METHODS:
        root = args.results_root / root_name
        manifest = _load(root / "manifest.json")
        cases = [str(item) for item in manifest.get("cases", [])]
        protocol = (
            manifest.get("model"),
            manifest.get("task_nums"),
            manifest.get("attack_limit"),
            manifest.get("attack_sampling"),
            manifest.get("case_sampling"),
            manifest.get("sampling_seed"),
            manifest.get("tool_provenance"),
            manifest.get("workflow_plan_dir"),
        )
        if expected_cases is None:
            expected_cases = cases
            expected_protocol = protocol
        if cases != expected_cases:
            raise RuntimeError(f"Case list mismatch for {label}")
        if protocol != expected_protocol:
            raise RuntimeError(f"Protocol mismatch for {label}: {protocol} != {expected_protocol}")

        raw_rows = [
            aggregate._load_json(path)
            for path in aggregate._case_paths(root / variant)
        ]
        case_rows = [row for row in raw_rows if row is not None]
        if len(case_rows) != len(cases) or len({row.get("case_id") for row in case_rows}) != len(cases):
            raise RuntimeError(f"Incomplete or duplicate cases for {label}")
        attack_tools = aggregate._case_attack_tools(manifest)
        summary = aggregate._summary_row(
            variant,
            label,
            case_rows,
            expected_cases=len(cases),
            attack_tools=attack_tools,
        )
        rows.append(
            {
                "method": label,
                "variant": variant,
                "utility": summary["utility"],
                "task_success": summary["task_success"],
                "asr": summary["asr"],
                "trace_asr": summary["asr_trace_executed_attacker_tool"],
                "safety": summary["safety"],
                "margin": summary["selected_signed_margin"],
                "blocked_tool_calls": summary["blocked_tool_calls"],
                "cases": summary["cases"],
                "complete": summary["complete"],
            }
        )
        source_roots[label] = str(root)

    assert expected_cases is not None and expected_protocol is not None
    case_hash = hashlib.sha256("\n".join(expected_cases).encode("utf-8")).hexdigest()
    result = {
        "schema": "asb-final-consolidated-v1",
        "case_sha256": case_hash,
        "protocol": {
            "model": expected_protocol[0],
            "task_nums": expected_protocol[1],
            "attack_limit": expected_protocol[2],
            "attack_sampling": expected_protocol[3],
            "case_sampling": expected_protocol[4],
            "sampling_seed": expected_protocol[5],
            "tool_provenance": expected_protocol[6],
            "workflow_plan_dir": expected_protocol[7],
        },
        "case_count": len(expected_cases),
        "asr_definition": "stored attack-goal match OR executed attacker-tool trace",
        "rows": rows,
        "source_roots": source_roots,
    }
    (args.out_dir / "asb_final_204.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (args.out_dir / "asb_final_204.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# ToolSafe-ASB-OPI Final 204-Case Comparison",
        "",
        f"- model: `{expected_protocol[0]}`",
        f"- cases: `{len(expected_cases)}` (`sha256={case_hash}`)",
        f"- sampling: `{expected_protocol[3]}` attacks, `{expected_protocol[4]}` cases, seed `{expected_protocol[5]}`",
        f"- tool provenance: `{expected_protocol[6]}`",
        f"- shared workflow plans: `{expected_protocol[7]}`",
        "- ASR: stored attack-goal match OR executed attacker-tool trace.",
        "- Utility: graded completion score in [0, 1]; Task Success: all normal tools required by the official-style workflow were executed.",
        "",
        "| Method | Utility | Task Success | ASR | Safety | Margin | Cases |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        margin = "-" if row["margin"] is None else _fmt(float(row["margin"]))
        lines.append(
            f"| {row['method']} | {_fmt(float(row['utility']))} | "
            f"{_fmt(float(row['task_success']))} | {_fmt(float(row['asr']))} | "
            f"{_fmt(float(row['safety']))} | {margin} | {row['cases']}/204 |"
        )
    (args.out_dir / "asb_final_204.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(args.out_dir / "asb_final_204.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
