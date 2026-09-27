from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
AUTODOJO_ROOT = ROOT / "external" / "official_baselines" / "AutoDojo"
MODEL_ID = "deepseek-v4-flash"
BENCHMARK_VERSION = "v1.2.2"
ATTACK_NAME = "important_instructions"


def load_dotenv_no_print(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


def configure_env() -> dict[str, str]:
    load_dotenv_no_print(ROOT / ".env")
    env = dict(os.environ)
    env["OPENAI_MODEL"] = MODEL_ID
    env["OPENAI_COMPATIBLE_API_KEY"] = env.get("OPENAI_API_KEY", "")
    env["OPENAI_COMPATIBLE_BASE_URL"] = env.get("OPENAI_BASE_URL", "")
    env["SECAGENT_API_KEY"] = env.get("OPENAI_API_KEY", "")
    env["SECAGENT_BASE_URL"] = env.get("OPENAI_BASE_URL", "")
    env["AGENTDOJO_OPENAI_TIMEOUT_SECONDS"] = "120"
    env["AGENTDOJO_HTTP_RETRIES"] = "2"
    env["AGENTDOJO_RUN_INJECTION_UTILITY"] = "0"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    env["PYTHONPATH"] = (
        r"agentdojo\src;agentdojo\variant_generation;"
        + str(ROOT / "ICLR" / "src")
        + ";"
        + str(ROOT / "src")
        + ";"
        + str(ROOT)
    )
    return env


def run_benchmark(
    *,
    out_root: Path,
    env: dict[str, str],
    defense: str,
    suite: str,
    with_attack: bool,
    force_rerun: bool,
    user_tasks: list[str],
    injection_tasks: list[str],
) -> None:
    group = "attack" if with_attack else "clean"
    log_path = out_root / "logs" / f"{group}-{defense}-{suite}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        sys.executable,
        "-m",
        "agentdojo.scripts.benchmark",
        "--model",
        MODEL_ID,
        "--model-id",
        MODEL_ID,
        "--benchmark-version",
        BENCHMARK_VERSION,
        "--suite",
        suite,
        "--defense",
        defense,
        "--logdir",
        str(out_root),
    ]
    if with_attack:
        args += ["--attack", ATTACK_NAME]
    for user_task in user_tasks:
        args += ["--user-task", user_task]
    if with_attack:
        for injection_task in injection_tasks:
            args += ["--injection-task", injection_task]
    if force_rerun:
        args += ["--force-rerun"]

    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n===== START {group} {defense} {suite} =====\n")
        log.write(" ".join(args) + "\n")
        log.flush()
        result = subprocess.run(
            args,
            cwd=AUTODOJO_ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        log.write(f"===== END {group} {defense} {suite} exit={result.returncode} =====\n")
    if result.returncode != 0:
        raise RuntimeError(f"{group} {defense} {suite} failed; see {log_path}")


def aggregate(out_root: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "ICLR" / "scripts" / "aggregate_autodojo_table.py"),
            "--root",
            str(out_root),
            "--model-id",
            MODEL_ID,
            "--benchmark-version",
            BENCHMARK_VERSION,
        ],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CLAFR under AutoDojo Table-II AgentDojo settings.")
    parser.add_argument("--out-root", type=Path, default=ROOT / "ICLR" / "results" / "autodojo_table_clafr_full")
    parser.add_argument("--suites", nargs="+", default=["banking", "slack", "travel"])
    parser.add_argument("--defenses", nargs="+", default=["clafr"])
    parser.add_argument("--clean-only", action="store_true")
    parser.add_argument("--attack-only", action="store_true")
    parser.add_argument("--force-rerun", action="store_true")
    parser.add_argument("--user-tasks", nargs="+", default=[])
    parser.add_argument("--injection-tasks", nargs="+", default=[])
    args = parser.parse_args()

    if not args.out_root.is_absolute():
        args.out_root = (Path.cwd() / args.out_root).resolve()

    env = configure_env()
    args.out_root.mkdir(parents=True, exist_ok=True)
    for defense in args.defenses:
        if not args.attack_only:
            for suite in args.suites:
                run_benchmark(
                    out_root=args.out_root,
                    env=env,
                    defense=defense,
                    suite=suite,
                    with_attack=False,
                    force_rerun=args.force_rerun,
                    user_tasks=args.user_tasks,
                    injection_tasks=args.injection_tasks,
                )
        if not args.clean_only:
            for suite in args.suites:
                run_benchmark(
                    out_root=args.out_root,
                    env=env,
                    defense=defense,
                    suite=suite,
                    with_attack=True,
                    force_rerun=args.force_rerun,
                    user_tasks=args.user_tasks,
                    injection_tasks=args.injection_tasks,
                )
    aggregate(args.out_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
