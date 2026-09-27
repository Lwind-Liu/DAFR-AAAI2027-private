from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace


def _load_runner():
    path = Path("scripts/run_autodojo_workspace_slice.py")
    spec = importlib.util.spec_from_file_location("run_autodojo_workspace_slice", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_table_runner():
    path = Path("scripts/run_autodojo_table_clafr.py")
    spec = importlib.util.spec_from_file_location("run_autodojo_table_clafr", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_workspace_aggregator():
    path = Path("scripts/aggregate_autodojo_workspace_full_table.py")
    spec = importlib.util.spec_from_file_location("aggregate_autodojo_workspace_full_table", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_four_suite_ablation_aggregator():
    path = Path("scripts/aggregate_autodojo_four_suite_clafr_ablation.py")
    spec = importlib.util.spec_from_file_location("aggregate_autodojo_four_suite_clafr_ablation", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_clean_workspace_run_does_not_pass_injection_filters(monkeypatch, tmp_path) -> None:
    runner = _load_runner()
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append([str(item) for item in args])
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    runner.run_benchmark(
        out_root=tmp_path,
        env={},
        defense="no_defense",
        with_attack=False,
        force_rerun=False,
        user_tasks=["user_task_0"],
        injection_tasks=["injection_task_0"],
    )

    assert "--user-task" in calls[0]
    assert "--attack" not in calls[0]
    assert "--injection-task" not in calls[0]


def test_attack_workspace_run_passes_injection_filters(monkeypatch, tmp_path) -> None:
    runner = _load_runner()
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append([str(item) for item in args])
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    runner.run_benchmark(
        out_root=tmp_path,
        env={},
        defense="no_defense",
        with_attack=True,
        force_rerun=False,
        user_tasks=["user_task_0"],
        injection_tasks=["injection_task_0"],
    )

    assert "--attack" in calls[0]
    assert "--injection-task" in calls[0]
    assert "injection_task_0" in calls[0]


def test_workspace_cli_defenses_override_split_manifest(monkeypatch, tmp_path) -> None:
    runner = _load_runner()
    split_manifest = tmp_path / "split_manifest.json"
    split_manifest.write_text(
        json.dumps(
            {
                "user_tasks": ["user_task_0"],
                "injection_tasks": ["injection_task_0"],
                "defenses": ["no_defense", "sandwich"],
            }
        ),
        encoding="utf-8",
    )
    calls: list[tuple[str, bool]] = []

    def fake_configure_env():
        return {}

    def fake_run_benchmark(**kwargs):
        calls.append((str(kwargs["defense"]), bool(kwargs["with_attack"])))

    monkeypatch.setattr(runner, "configure_env", fake_configure_env)
    monkeypatch.setattr(runner, "run_benchmark", fake_run_benchmark)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_autodojo_workspace_slice.py",
            "--out-root",
            str(tmp_path / "out"),
            "--split-manifest",
            str(split_manifest),
            "--defenses",
            "clafr",
        ],
    )

    assert runner.main() == 0
    assert calls == [("clafr", False), ("clafr", True)]


def test_clean_table_ablation_run_does_not_pass_injection_filters(monkeypatch, tmp_path) -> None:
    runner = _load_table_runner()
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append([str(item) for item in args])
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    runner.run_benchmark(
        out_root=tmp_path,
        env={},
        defense="clafr_no_observation_projection",
        suite="banking",
        with_attack=False,
        force_rerun=False,
        user_tasks=["user_task_0"],
        injection_tasks=["injection_task_0"],
    )

    assert "--user-task" in calls[0]
    assert "--attack" not in calls[0]
    assert "--injection-task" not in calls[0]


def test_attack_table_ablation_run_passes_injection_filters(monkeypatch, tmp_path) -> None:
    runner = _load_table_runner()
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append([str(item) for item in args])
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    runner.run_benchmark(
        out_root=tmp_path,
        env={},
        defense="clafr_no_observation_projection",
        suite="banking",
        with_attack=True,
        force_rerun=False,
        user_tasks=["user_task_0"],
        injection_tasks=["injection_task_0"],
    )

    assert "--attack" in calls[0]
    assert "--injection-task" in calls[0]
    assert "injection_task_0" in calls[0]


def test_workspace_merge_uses_post_generic_clafr_base3_override(monkeypatch, tmp_path) -> None:
    aggregator = _load_workspace_aggregator()
    workspace_root = tmp_path / "workspace"
    base3_root = tmp_path / "base3"
    split_manifest = tmp_path / "split_manifest.json"

    clean_path = (
        workspace_root
        / "deepseek-v4-flash"
        / "clafr"
        / "workspace"
        / "user_task_0"
        / "none"
        / "none.json"
    )
    attack_path = (
        workspace_root
        / "deepseek-v4-flash"
        / "clafr"
        / "workspace"
        / "user_task_0"
        / "important_instructions"
        / "injection_task_0.json"
    )
    clean_path.parent.mkdir(parents=True)
    attack_path.parent.mkdir(parents=True)
    clean_path.write_text(json.dumps({"utility": True}), encoding="utf-8")
    attack_path.write_text(json.dumps({"utility": True, "security": False}), encoding="utf-8")
    split_manifest.write_text(
        json.dumps(
            {
                "user_tasks": ["user_task_0"],
                "injection_tasks": ["injection_task_0"],
            }
        ),
        encoding="utf-8",
    )
    base3_root.mkdir()
    (base3_root / "autodojo_table_aggregate.json").write_text(
        json.dumps(
            {
                "model_id": "deepseek-v4-flash",
                "rows": [
                    {
                        "method_key": "clafr",
                        "clean_cases": 57,
                        "attack_cases": 389,
                        "clean_utility": 0.8,
                        "static_asr": 0.2,
                        "static_attack_utility": 0.7,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "aggregate_autodojo_workspace_full_table.py",
            "--workspace-root",
            str(workspace_root),
            "--split-manifest",
            str(split_manifest),
            "--base3-clafr-root",
            str(base3_root),
            "--require-base3-clafr-override",
        ],
    )

    assert aggregator.main() == 0
    rows = list(csv.DictReader((workspace_root / "autodojo_v122_4suite_merged.csv").open(encoding="utf-8")))
    clafr = next(row for row in rows if row["method_key"] == "clafr")

    assert clafr["base3_source"] == "post_generic_clafr_rerun"
    assert clafr["base3_clean_utility"] == "80.0"
    assert clafr["base3_static_asr"] == "20.0"
    assert clafr["merged_clean_utility"] == "85.0"
    assert clafr["merged_static_asr"] == "15.0"


def test_four_suite_paper_ablation_aggregator_merges_workspace(monkeypatch, tmp_path) -> None:
    aggregator = _load_four_suite_ablation_aggregator()
    base3_root = tmp_path / "base3"
    workspace_root = tmp_path / "workspace"
    split_manifest = tmp_path / "split_manifest.json"
    base3_root.mkdir()
    split_manifest.write_text(
        json.dumps(
            {
                "user_tasks": ["user_task_0"],
                "injection_tasks": ["injection_task_0"],
            }
        ),
        encoding="utf-8",
    )
    (base3_root / "autodojo_table_aggregate.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "method_key": "clafr",
                        "clean_cases": 57,
                        "attack_cases": 389,
                        "clean_utility": 0.8,
                        "static_asr": 0.2,
                        "static_attack_utility": 0.6,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    clean_path = (
        workspace_root
        / "deepseek-v4-flash"
        / "clafr"
        / "workspace"
        / "user_task_0"
        / "none"
        / "none.json"
    )
    attack_path = (
        workspace_root
        / "deepseek-v4-flash"
        / "clafr"
        / "workspace"
        / "user_task_0"
        / "important_instructions"
        / "injection_task_0.json"
    )
    clean_path.parent.mkdir(parents=True)
    attack_path.parent.mkdir(parents=True)
    clean_path.write_text(json.dumps({"utility": True}), encoding="utf-8")
    attack_path.write_text(json.dumps({"utility": True, "security": False}), encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "aggregate_autodojo_four_suite_clafr_ablation.py",
            "--base3-root",
            str(base3_root),
            "--workspace-root",
            str(workspace_root),
            "--split-manifest",
            str(split_manifest),
        ],
    )

    assert aggregator.main() == 0
    rows = list(csv.DictReader((workspace_root / "autodojo_v122_4suite_clafr_ablation.csv").open(encoding="utf-8")))
    clafr = next(row for row in rows if row["method_key"] == "clafr")

    assert clafr["merged_cases"] == "58/390"
    assert clafr["merged_clean_utility"] == "85.0"
    assert clafr["merged_static_asr"] == "15.0"
    assert clafr["merged_static_attack_utility"] == "70.0"
