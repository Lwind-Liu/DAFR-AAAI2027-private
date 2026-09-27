from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any


MODEL_ID = "deepseek-v4-flash"
BENCHMARK_VERSION = "v1.2.2"
SUITE = "workspace"
ATTACK_NAME = "important_instructions"
THREE_SUITE_CLEAN = 57
THREE_SUITE_ATTACK = 389

PAPER_ABLATIONS = [
    ("clafr", "CLAFR"),
    ("clafr_no_evidence_projection", "CLAFR w/o Evidence Projection"),
    ("clafr_no_action_evidence_lifting", "CLAFR w/o Action-Evidence Lifting"),
    ("clafr_no_dynamic_geometry", "CLAFR w/o Dynamic Geometry"),
    ("clafr_no_decision_repair", "CLAFR w/o Decision & Repair"),
]


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


def _pct(value: float | None) -> float | None:
    return None if value is None else round(100 * value, 1)


def _load_base3_rows(root: Path) -> dict[str, dict[str, Any]]:
    aggregate_path = root / "autodojo_table_aggregate.json"
    if not aggregate_path.exists():
        raise FileNotFoundError(f"Missing base3 aggregate: {aggregate_path}")
    payload = json.loads(aggregate_path.read_text(encoding="utf-8"))
    return {str(row["method_key"]): row for row in payload.get("rows", [])}


def _workspace_values(
    root: Path,
    method_key: str,
    model_id: str,
    user_tasks: set[str] | None,
    injection_tasks: set[str] | None,
) -> dict[str, Any]:
    suite_dir = root / model_id / method_key / SUITE
    clean_values: list[int] = []
    attack_utility_values: list[int] = []
    attack_success_values: list[int] = []

    for path in sorted(suite_dir.glob("user_task_*/none/none.json")):
        if user_tasks is not None and path.parent.parent.name not in user_tasks:
            continue
        payload = _read_json(path)
        if payload is None:
            continue
        utility = _bool(payload.get("utility"))
        if utility is not None:
            clean_values.append(int(utility))

    for path in sorted(suite_dir.glob(f"user_task_*/{ATTACK_NAME}/injection_task_*.json")):
        if user_tasks is not None and path.parent.parent.name not in user_tasks:
            continue
        if injection_tasks is not None and path.stem not in injection_tasks:
            continue
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
        "clean_cases": len(clean_values),
        "attack_cases": len(attack_utility_values),
        "clean_utility": mean(clean_values) if clean_values else None,
        "static_asr": mean(attack_success_values) if attack_success_values else None,
        "static_attack_utility": mean(attack_utility_values) if attack_utility_values else None,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge AutoDojo three-suite CLAFR ablation with workspace-selected results."
    )
    parser.add_argument("--base3-root", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--benchmark-version", default=BENCHMARK_VERSION)
    parser.add_argument("--split-manifest", type=Path, default=None)
    parser.add_argument("--user-tasks", nargs="+", default=[])
    parser.add_argument("--injection-tasks", nargs="+", default=[])
    args = parser.parse_args()

    if args.split_manifest is not None:
        manifest = json.loads(args.split_manifest.read_text(encoding="utf-8"))
        if not args.user_tasks:
            args.user_tasks = [str(item) for item in manifest["user_tasks"]]
        if not args.injection_tasks:
            args.injection_tasks = [str(item) for item in manifest["injection_tasks"]]

    user_task_filter = set(args.user_tasks) if args.user_tasks else None
    injection_task_filter = set(args.injection_tasks) if args.injection_tasks else None
    expected_workspace_clean = len(user_task_filter) if user_task_filter is not None else None
    expected_workspace_attack = (
        len(user_task_filter) * len(injection_task_filter)
        if user_task_filter is not None and injection_task_filter is not None
        else None
    )

    out_dir = args.out_dir or args.workspace_root
    out_dir.mkdir(parents=True, exist_ok=True)
    base3_rows = _load_base3_rows(args.base3_root)

    rows: list[dict[str, Any]] = []
    for method_key, method in PAPER_ABLATIONS:
        base3 = base3_rows.get(method_key)
        if base3 is None:
            continue
        ws = _workspace_values(
            args.workspace_root,
            method_key,
            args.model_id,
            user_task_filter,
            injection_task_filter,
        )
        if ws["clean_utility"] is None or ws["static_asr"] is None or ws["static_attack_utility"] is None:
            merged_clean = None
            merged_asr = None
            merged_attack_utility = None
        else:
            merged_clean = (3 * float(base3["clean_utility"]) + ws["clean_utility"]) / 4
            merged_asr = (3 * float(base3["static_asr"]) + ws["static_asr"]) / 4
            merged_attack_utility = (
                3 * float(base3["static_attack_utility"]) + ws["static_attack_utility"]
            ) / 4
        rows.append(
            {
                "method_key": method_key,
                "method": method,
                "base3_clean_cases": int(base3.get("clean_cases", 0)),
                "base3_attack_cases": int(base3.get("attack_cases", 0)),
                "base3_complete": int(
                    int(base3.get("clean_cases", 0)) == THREE_SUITE_CLEAN
                    and int(base3.get("attack_cases", 0)) == THREE_SUITE_ATTACK
                ),
                "base3_clean_utility": _pct(float(base3["clean_utility"])),
                "base3_static_asr": _pct(float(base3["static_asr"])),
                "base3_static_attack_utility": _pct(float(base3["static_attack_utility"])),
                "workspace_clean_cases": ws["clean_cases"],
                "workspace_attack_cases": ws["attack_cases"],
                "workspace_complete": int(
                    (expected_workspace_clean is None or ws["clean_cases"] == expected_workspace_clean)
                    and (expected_workspace_attack is None or ws["attack_cases"] == expected_workspace_attack)
                ),
                "workspace_clean_utility": _pct(ws["clean_utility"]),
                "workspace_static_asr": _pct(ws["static_asr"]),
                "workspace_static_attack_utility": _pct(ws["static_attack_utility"]),
                "merged_clean_utility": _pct(merged_clean),
                "merged_static_asr": _pct(merged_asr),
                "merged_static_attack_utility": _pct(merged_attack_utility),
                "merged_cases": f"{THREE_SUITE_CLEAN + ws['clean_cases']}/{THREE_SUITE_ATTACK + ws['attack_cases']}",
            }
        )

    csv_path = out_dir / "autodojo_v122_4suite_clafr_ablation.csv"
    json_path = out_dir / "autodojo_v122_4suite_clafr_ablation.json"
    md_path = out_dir / "autodojo_v122_4suite_clafr_ablation.md"
    _write_csv(csv_path, rows)
    json_path.write_text(
        json.dumps(
            {
                "schema": "autodojo-v122-4suite-clafr-paper-ablation-v1",
                "model_id": args.model_id,
                "benchmark_version": args.benchmark_version,
                "base3_root": str(args.base3_root),
                "workspace_root": str(args.workspace_root),
                "split_manifest": str(args.split_manifest) if args.split_manifest else None,
                "aggregation": "four_suite_macro = (3 * base3_macro + workspace_selected_metric) / 4",
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
        "# AutoDojo v1.2.2 Four-Suite CLAFR Paper Ablation",
        "",
        f"- model: `{args.model_id}`",
        f"- benchmark version: `{args.benchmark_version}`",
        "- suites: `banking`, `slack`, `travel`, `workspace-selected`",
        "- aggregation: `(3 * three-suite macro + workspace-selected metric) / 4`",
        "",
        "| Method | Clean Utility | Static ASR | Static Attack Utility | Cases | Complete |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        complete = "yes" if row["base3_complete"] and row["workspace_complete"] else "no"
        lines.append(
            f"| {row['method']} | {row['merged_clean_utility']} | {row['merged_static_asr']} | "
            f"{row['merged_static_attack_utility']} | {row['merged_cases']} | {complete} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"autodojo_4suite_clafr_ablation,{md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
