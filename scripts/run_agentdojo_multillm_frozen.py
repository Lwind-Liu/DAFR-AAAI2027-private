from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUTODOJO_ROOT = ROOT / "external" / "official_baselines" / "AutoDojo"
BENCHMARK_VERSION = "v1.2.2"
ATTACK_NAME = "important_instructions"
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


@dataclass(frozen=True)
class Job:
    defense: str
    suite: str
    with_attack: bool
    user_tasks: tuple[str, ...]
    injection_tasks: tuple[str, ...]

    @property
    def group(self) -> str:
        return "attack" if self.with_attack else "clean"

    @property
    def label(self) -> str:
        return f"{self.group}-{self.defense}-{self.suite}"


def _configured_env(model: str, base_url: str, protocol: str) -> dict[str, str]:
    api_key = os.environ.get("OPENAI_COMPATIBLE_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_COMPATIBLE_API_KEY must be set in the process environment")
    env = dict(os.environ)
    env.update(
        {
            "OPENAI_MODEL": model,
            "OPENAI_COMPATIBLE_BASE_URL": base_url,
            "OPENAI_COMPATIBLE_PROTOCOL": protocol,
            "ANTHROPIC_API_KEY": api_key,
            "ANTHROPIC_BASE_URL": base_url,
            "SECAGENT_API_KEY": api_key,
            "SECAGENT_BASE_URL": base_url,
            "AGENTDOJO_OPENAI_TIMEOUT_SECONDS": os.environ.get(
                "AGENTDOJO_OPENAI_TIMEOUT_SECONDS", "120"
            ),
            "AGENTDOJO_HTTP_RETRIES": os.environ.get("AGENTDOJO_HTTP_RETRIES", "2"),
            "AGENTDOJO_RUN_INJECTION_UTILITY": "0",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "NO_COLOR": "1",
            "TERM": "dumb",
            "PYTHONPATH": ";".join(
                (
                    r"agentdojo\src",
                    r"agentdojo\variant_generation",
                    str(ROOT / "src"),
                    str(ROOT / "src"),
                    str(ROOT),
                )
            ),
        }
    )
    return env


def _defense_args(defense: str, model: str) -> list[str]:
    if defense == "no_defense":
        return []
    args = ["--defense", defense]
    if defense in {"progent", "drift"}:
        args += ["--defense-model", model, "--defense-model-id", model]
    return args


def _command(job: Job, model: str, out_root: Path) -> list[str]:
    args = [
        sys.executable,
        "-m",
        "agentdojo.scripts.benchmark",
        "--model",
        model,
        "--model-id",
        model,
        "--benchmark-version",
        BENCHMARK_VERSION,
        "--suite",
        job.suite,
        "--logdir",
        str(out_root),
    ]
    args += _defense_args(job.defense, model)
    if job.with_attack:
        args += ["--attack", ATTACK_NAME]
    for user_task in job.user_tasks:
        args += ["--user-task", user_task]
    if job.with_attack:
        for injection_task in job.injection_tasks:
            args += ["--injection-task", injection_task]
    return args


def _run_job(job: Job, model: str, out_root: Path, env: dict[str, str]) -> dict[str, Any]:
    log_path = out_root / "logs" / f"{job.label}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = _command(job, model, out_root)
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n===== START {job.label} =====\n")
        log.write(" ".join(command) + "\n")
        log.flush()
        result = subprocess.run(
            command,
            cwd=AUTODOJO_ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        log.write(f"===== END {job.label} exit={result.returncode} =====\n")
    return {
        "label": job.label,
        "exit_code": result.returncode,
        "log": str(log_path),
    }


def _build_jobs(
    manifest: dict[str, Any], phase: str, defenses: tuple[str, ...] | None = None
) -> list[Job]:
    jobs: list[Job] = []
    if phase in {"all", "clafr"}:
        for suite, split in manifest["suites"].items():
            for with_attack in (False, True):
                jobs.append(
                    Job(
                        defense="clafr",
                        suite=str(suite),
                        with_attack=with_attack,
                        user_tasks=tuple(str(item) for item in split["user_tasks"]),
                        injection_tasks=tuple(str(item) for item in split["injection_tasks"]),
                    )
                )
    if phase in {"all", "baselines"}:
        split = manifest["suites"]["workspace"]
        selected_baselines = defenses or BASELINES
        for defense in selected_baselines:
            for with_attack in (False, True):
                jobs.append(
                    Job(
                        defense=defense,
                        suite="workspace",
                        with_attack=with_attack,
                        user_tasks=tuple(str(item) for item in split["user_tasks"]),
                        injection_tasks=tuple(str(item) for item in split["injection_tasks"]),
                    )
                )
    return jobs


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen AgentDojo multi-LLM protocol.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-root", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--protocol", choices=("chat_completions", "responses", "anthropic_messages"), required=True)
    parser.add_argument("--phase", choices=("all", "clafr", "baselines"), default="all")
    parser.add_argument("--defenses", nargs="+", choices=BASELINES, default=None)
    parser.add_argument("--max-workers", type=int, default=4)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    out_root = args.out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    selected_defenses = tuple(args.defenses) if args.defenses else None
    jobs = _build_jobs(manifest, args.phase, selected_defenses)
    suffix = ""
    if selected_defenses:
        suffix = "_" + "-".join(selected_defenses)
    run_manifest = {
        "schema": "agentdojo-multillm-frozen-run-v1",
        "source_manifest": str(args.manifest.resolve()),
        "model": args.model,
        "base_url": args.base_url,
        "protocol": args.protocol,
        "phase": args.phase,
        "max_workers": args.max_workers,
        "jobs": [job.label for job in jobs],
        "expected_cases": 2336 if args.phase == "all" else None,
    }
    (out_root / f"run_manifest{suffix}.json").write_text(
        json.dumps(run_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    env = _configured_env(args.model, args.base_url, args.protocol)
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(_run_job, job, args.model, out_root, env): job for job in jobs
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)

    failed = [result for result in results if result["exit_code"] != 0]
    (out_root / f"job_results{suffix}.json").write_text(
        json.dumps(sorted(results, key=lambda item: item["label"]), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
