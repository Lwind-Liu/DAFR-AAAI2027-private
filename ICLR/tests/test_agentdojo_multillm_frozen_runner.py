import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ICLR" / "scripts" / "run_agentdojo_multillm_frozen.py"
MANIFEST = ROOT / "ICLR" / "manifests" / "agentdojo_v122_clafr_multillm_four_suite_71_585.json"


def _load_module():
    spec = importlib.util.spec_from_file_location("multillm_runner", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_runner_builds_exact_24_jobs() -> None:
    module = _load_module()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    jobs = module._build_jobs(manifest, "all")

    assert len(jobs) == 24
    assert sum(job.defense == "clafr" for job in jobs) == 8
    assert sum(job.suite == "workspace" and job.defense != "clafr" for job in jobs) == 16
    assert {job.defense for job in jobs if job.defense != "clafr"} == set(module.BASELINES)


def test_frozen_runner_can_select_failed_baselines() -> None:
    module = _load_module()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    jobs = module._build_jobs(manifest, "baselines", ("progent", "drift"))

    assert len(jobs) == 4
    assert {job.defense for job in jobs} == {"progent", "drift"}


def test_clean_jobs_do_not_pass_injection_filters() -> None:
    module = _load_module()
    job = module.Job(
        defense="clafr",
        suite="banking",
        with_attack=False,
        user_tasks=("user_task_0",),
        injection_tasks=("injection_task_0",),
    )

    command = module._command(job, "gpt-5.4-mini", Path("results"))

    assert "--attack" not in command
    assert "--injection-task" not in command
    assert command.count("--user-task") == 1


def test_progent_and_drift_use_the_same_model() -> None:
    module = _load_module()

    assert module._defense_args("progent", "gpt-5.4-mini") == [
        "--defense",
        "progent",
        "--defense-model",
        "gpt-5.4-mini",
        "--defense-model-id",
        "gpt-5.4-mini",
    ]
    assert module._defense_args("drift", "gpt-5.4-mini") == [
        "--defense",
        "drift",
        "--defense-model",
        "gpt-5.4-mini",
        "--defense-model-id",
        "gpt-5.4-mini",
    ]
