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
WORKSPACE_FULL_CLEAN = 40
WORKSPACE_FULL_ATTACK = 560
WORKSPACE_FULL_INJECTIONS = WORKSPACE_FULL_ATTACK // WORKSPACE_FULL_CLEAN

METHODS = [
    ("no_defense", "No Defense", 89.5, 22.6, 77.4),
    ("sandwich", "Sandwich", 91.2, 14.7, 77.4),
    ("reminder", "Reminder", 89.5, 4.9, 81.0),
    ("spotlighting", "Spotlighting", 75.4, 13.9, 80.5),
    ("promptguard", "PromptGuard", 89.5, 21.3, 70.2),
    ("piguard", "PIGuard", 45.6, 0.0, 40.9),
    ("protectai", "ProtectAI", 47.4, 4.6, 31.9),
    ("datafilter", "DataFilter", 91.2, 2.3, 81.5),
    ("progent", "Progent", 78.9, 2.8, 73.8),
    ("drift", "DRIFT", 59.6, 1.3, 48.1),
    ("clafr", "CLAFR", 93.3, 0.0, 90.3),
]


def _base3_clafr_override(root: Path, model_id: str) -> tuple[float, float, float] | None:
    aggregate_path = root / "autodojo_table_aggregate.json"
    if not aggregate_path.exists():
        return None
    payload = json.loads(aggregate_path.read_text(encoding="utf-8"))
    if str(payload.get("model_id", model_id)) != model_id:
        return None
    for row in payload.get("rows", []):
        if row.get("method_key") != "clafr":
            continue
        if int(row.get("clean_cases", 0)) != THREE_SUITE_CLEAN:
            return None
        if int(row.get("attack_cases", 0)) != THREE_SUITE_ATTACK:
            return None
        return (
            round(100 * float(row["clean_utility"]), 1),
            round(100 * float(row["static_asr"]), 1),
            round(100 * float(row["static_attack_utility"]), 1),
        )
    return None


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
    clean_paths = sorted(suite_dir.glob("user_task_*/none/none.json"))
    attack_paths = sorted(suite_dir.glob(f"user_task_*/{ATTACK_NAME}/injection_task_*.json"))

    for path in clean_paths:
        if user_tasks is not None and path.parent.parent.name not in user_tasks:
            continue
        payload = _read_json(path)
        if payload is None:
            continue
        utility = _bool(payload.get("utility"))
        if utility is not None:
            clean_values.append(int(utility))

    for path in attack_paths:
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


def _pct(value: float | None) -> str:
    return "-" if value is None else f"{100 * value:.1f}"


def _pct_number(value: float | None) -> float | None:
    return None if value is None else round(100 * value, 1)


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


def _expected_workspace_cases(user_tasks: set[str] | None, injection_tasks: set[str] | None) -> tuple[int, int]:
    clean = len(user_tasks) if user_tasks is not None else WORKSPACE_FULL_CLEAN
    injections = len(injection_tasks) if injection_tasks is not None else WORKSPACE_FULL_INJECTIONS
    return clean, clean * injections


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge AutoDojo 3-suite table with newly run v1.2.2 workspace results."
    )
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--split-manifest", type=Path, default=None)
    parser.add_argument("--user-tasks", nargs="+", default=[])
    parser.add_argument("--injection-tasks", nargs="+", default=[])
    parser.add_argument(
        "--base3-clafr-root",
        type=Path,
        default=None,
        help="Optional post-generic AutoDojo table aggregate root used to replace the hard-coded CLAFR base3 row.",
    )
    parser.add_argument("--require-base3-clafr-override", action="store_true")
    parser.add_argument(
        "--exclude-methods",
        nargs="+",
        default=["promptguard", "datafilter"],
        help="Method keys to exclude from the four-suite table. Defaults exclude unavailable/heavy baselines.",
    )
    args = parser.parse_args()

    out_dir = args.out_dir or args.workspace_root
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.split_manifest is not None:
        manifest = json.loads(args.split_manifest.read_text(encoding="utf-8"))
        if not args.user_tasks:
            args.user_tasks = [str(item) for item in manifest["user_tasks"]]
        if not args.injection_tasks:
            args.injection_tasks = [str(item) for item in manifest["injection_tasks"]]
    user_task_filter = set(args.user_tasks) if args.user_tasks else None
    injection_task_filter = set(args.injection_tasks) if args.injection_tasks else None
    expected_clean, expected_attack = _expected_workspace_cases(user_task_filter, injection_task_filter)
    selected_full_workspace = expected_clean == WORKSPACE_FULL_CLEAN and expected_attack == WORKSPACE_FULL_ATTACK
    clafr_override = (
        _base3_clafr_override(args.base3_clafr_root, args.model_id)
        if args.base3_clafr_root is not None
        else None
    )
    if args.require_base3_clafr_override and clafr_override is None:
        raise RuntimeError(
            "Missing complete post-generic CLAFR base3 aggregate; refusing to merge with stale hard-coded CLAFR row."
        )

    workspace_rows: list[dict[str, Any]] = []
    merged_rows: list[dict[str, Any]] = []
    complete_selected_workspace = True
    excluded_methods = {str(item).strip().lower() for item in args.exclude_methods}
    for method_key, method, clean3, asr3, attack_util3 in METHODS:
        if method_key in excluded_methods:
            continue
        base3_source = "autodojo_reference_table"
        if method_key == "clafr" and clafr_override is not None:
            clean3, asr3, attack_util3 = clafr_override
            base3_source = "post_generic_clafr_rerun"
        ws = _workspace_values(
            args.workspace_root,
            method_key,
            args.model_id,
            user_task_filter,
            injection_task_filter,
        )
        is_complete = ws["clean_cases"] == expected_clean and ws["attack_cases"] == expected_attack
        complete_selected_workspace = complete_selected_workspace and is_complete
        workspace_rows.append(
            {
                "method_key": method_key,
                "method": method,
                "expected_workspace_clean_cases": expected_clean,
                "expected_workspace_attack_cases": expected_attack,
                "workspace_clean_cases": ws["clean_cases"],
                "workspace_attack_cases": ws["attack_cases"],
                "selected_workspace_complete": int(is_complete),
                "workspace_clean_utility": _pct_number(ws["clean_utility"]),
                "workspace_static_asr": _pct_number(ws["static_asr"]),
                "workspace_static_attack_utility": _pct_number(ws["static_attack_utility"]),
            }
        )
        if ws["clean_utility"] is None or ws["static_asr"] is None or ws["static_attack_utility"] is None:
            merged_clean = None
            merged_asr = None
            merged_attack_util = None
        else:
            merged_clean = ((3 * (clean3 / 100.0)) + ws["clean_utility"]) / 4
            merged_asr = ((3 * (asr3 / 100.0)) + ws["static_asr"]) / 4
            merged_attack_util = ((3 * (attack_util3 / 100.0)) + ws["static_attack_utility"]) / 4
        merged_rows.append(
            {
                "method_key": method_key,
                "method": method,
                "base3_clean_utility": clean3,
                "base3_static_asr": asr3,
                "base3_static_attack_utility": attack_util3,
                "base3_source": base3_source,
                "workspace_clean_cases": ws["clean_cases"],
                "workspace_attack_cases": ws["attack_cases"],
                "workspace_clean_utility": _pct_number(ws["clean_utility"]),
                "workspace_static_asr": _pct_number(ws["static_asr"]),
                "workspace_static_attack_utility": _pct_number(ws["static_attack_utility"]),
                "merged_clean_utility": _pct_number(merged_clean),
                "merged_static_asr": _pct_number(merged_asr),
                "merged_static_attack_utility": _pct_number(merged_attack_util),
                "merged_cases": (
                    f"{THREE_SUITE_CLEAN + ws['clean_cases']}/{THREE_SUITE_ATTACK + ws['attack_cases']}"
                ),
                "full_target_cases": f"{THREE_SUITE_CLEAN + WORKSPACE_FULL_CLEAN}/{THREE_SUITE_ATTACK + WORKSPACE_FULL_ATTACK}",
                "selected_workspace_complete": int(is_complete),
                "selected_workspace_expected_cases": f"{expected_clean}/{expected_attack}",
            }
        )

    _write_csv(out_dir / "workspace_rows.csv", workspace_rows)
    _write_csv(out_dir / "autodojo_v122_4suite_merged.csv", merged_rows)
    (out_dir / "autodojo_v122_4suite_merged.json").write_text(
        json.dumps(
            {
                "schema": "autodojo-v122-workspace-merge-v1",
                "model_id": args.model_id,
                "benchmark_version": BENCHMARK_VERSION,
                "base_suites": ["banking", "slack", "travel"],
                "workspace_suite": SUITE,
                "base_cases": {"clean": THREE_SUITE_CLEAN, "attack": THREE_SUITE_ATTACK},
                "workspace_full_cases": {"clean": WORKSPACE_FULL_CLEAN, "attack": WORKSPACE_FULL_ATTACK},
                "workspace_selected_expected_cases": {"clean": expected_clean, "attack": expected_attack},
                "full_target_cases": {
                    "clean": THREE_SUITE_CLEAN + WORKSPACE_FULL_CLEAN,
                    "attack": THREE_SUITE_ATTACK + WORKSPACE_FULL_ATTACK,
                },
                "selected_workspace_complete": complete_selected_workspace,
                "selected_full_workspace": selected_full_workspace,
                "user_task_filter": sorted(user_task_filter) if user_task_filter is not None else None,
                "injection_task_filter": sorted(injection_task_filter) if injection_task_filter is not None else None,
                "split_manifest": str(args.split_manifest) if args.split_manifest is not None else None,
                "excluded_methods": sorted(excluded_methods),
                "base3_clafr_root": str(args.base3_clafr_root) if args.base3_clafr_root is not None else None,
                "clafr_base3_override_used": clafr_override is not None,
                "merge_formula": "four_suite_macro = (3 * autodojo_table_macro + workspace_metric) / 4",
                "workspace_rows": workspace_rows,
                "merged_rows": merged_rows,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    workspace_title = "Workspace Full Rows" if selected_full_workspace else "Workspace Selected-Split Rows"
    merged_title = (
        "AutoDojo v1.2.2 Four-Suite Full Table"
        if selected_full_workspace
        else "AutoDojo v1.2.2 Four-Suite Selected-Workspace Table"
    )
    lines = [
        f"# {workspace_title}",
        "",
        f"- model: `{args.model_id}`",
        f"- benchmark version: `{BENCHMARK_VERSION}`",
        f"- suite: `{SUITE}`",
        f"- user task filter: `{', '.join(sorted(user_task_filter)) if user_task_filter is not None else 'all'}`",
        f"- injection task filter: `{', '.join(sorted(injection_task_filter)) if injection_task_filter is not None else 'all'}`",
        f"- split manifest: `{args.split_manifest if args.split_manifest is not None else 'none'}`",
        f"- excluded methods: `{', '.join(sorted(excluded_methods)) if excluded_methods else 'none'}`",
        f"- full workspace target: `{WORKSPACE_FULL_CLEAN}/{WORKSPACE_FULL_ATTACK}`",
        f"- selected workspace target: `{expected_clean}/{expected_attack}`",
        f"- current workspace coverage: `{max((r['workspace_clean_cases'] for r in workspace_rows), default=0)}/{max((r['workspace_attack_cases'] for r in workspace_rows), default=0)}` per completed method at most",
        "",
        "| Method | Workspace Clean Utility | Workspace Static ASR | Workspace Static Attack Utility | Workspace Cases | Complete |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in workspace_rows:
        lines.append(
            f"| {row['method']} | "
            f"{row['workspace_clean_utility'] if row['workspace_clean_utility'] is not None else '-'} | "
            f"{row['workspace_static_asr'] if row['workspace_static_asr'] is not None else '-'} | "
            f"{row['workspace_static_attack_utility'] if row['workspace_static_attack_utility'] is not None else '-'} | "
            f"{row['workspace_clean_cases']}/{row['workspace_attack_cases']} | "
            f"{'yes' if row['selected_workspace_complete'] else 'no'} |"
        )
    (out_dir / "workspace_rows.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    lines = [
        f"# {merged_title}",
        "",
        f"- model: `{args.model_id}`",
        f"- benchmark version: `{BENCHMARK_VERSION}`",
        "- base table suites: `banking`, `slack`, `travel`",
        "- added suite: `workspace`",
        f"- CLAFR base3 source: `{'post-generic rerun' if clafr_override is not None else 'hard-coded reference row'}`",
        f"- workspace user task filter: `{', '.join(sorted(user_task_filter)) if user_task_filter is not None else 'all'}`",
        f"- workspace injection task filter: `{', '.join(sorted(injection_task_filter)) if injection_task_filter is not None else 'all'}`",
        f"- split manifest: `{args.split_manifest if args.split_manifest is not None else 'none'}`",
        f"- excluded methods: `{', '.join(sorted(excluded_methods)) if excluded_methods else 'none'}`",
        "- aggregation: unweighted macro-average over suites.",
        "- merge formula: `four_suite_macro = (3 * base3_macro + workspace_metric) / 4`.",
    ]
    if not selected_full_workspace:
        lines += [
            f"- status: selected workspace split `{expected_clean}/{expected_attack}`; this is not the full `97/949` AgentDojo table.",
        ]
    if not complete_selected_workspace:
        lines += ["- selected split status: incomplete; do not report until every method reaches the selected target."]
    lines += [
        "",
        "| Method | Clean Utility | Static ASR | Static Attack Utility | Cases | Workspace Cases |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in merged_rows:
        lines.append(
            f"| {row['method']} | "
            f"{row['merged_clean_utility'] if row['merged_clean_utility'] is not None else '-'} | "
            f"{row['merged_static_asr'] if row['merged_static_asr'] is not None else '-'} | "
            f"{row['merged_static_attack_utility'] if row['merged_static_attack_utility'] is not None else '-'} | "
            f"{row['merged_cases']} | "
            f"{row['workspace_clean_cases']}/{row['workspace_attack_cases']} |"
        )
    (out_dir / "autodojo_v122_4suite_merged.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_dir / "autodojo_v122_4suite_merged.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
