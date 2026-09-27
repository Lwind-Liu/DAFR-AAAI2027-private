from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
AUTODOJO_ROOT = ROOT / "external" / "official_baselines" / "AutoDojo"
MODEL_ID = "deepseek-v4-flash"
BENCHMARK_VERSION = "v1.2.2"
SUITE = "workspace"
ATTACK_NAME = "important_instructions"

DEFAULT_DEFENSES = [
    "no_defense",
    "sandwich",
    "reminder",
    "spotlighting",
    "promptguard",
    "piguard",
    "protectai",
    "datafilter",
    "progent",
    "drift",
    "clafr",
]

DEFAULT_USER_TASKS = ["user_task_0", "user_task_1", "user_task_3"]


def load_dotenv_no_print(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing dotenv file: {path}")
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


def _defense_args(defense: str) -> list[str]:
    if defense == "no_defense":
        return []
    args = ["--defense", defense]
    if defense in {"drift", "progent"}:
        args += ["--defense-model", MODEL_ID, "--defense-model-id", MODEL_ID]
    return args


def run_benchmark(
    *,
    out_root: Path,
    env: dict[str, str],
    defense: str,
    with_attack: bool,
    force_rerun: bool,
    user_tasks: list[str],
    injection_tasks: list[str],
) -> None:
    group = "attack" if with_attack else "clean"
    log_path = out_root / "logs" / f"{group}-{defense}-{SUITE}.log"
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
        SUITE,
        "--logdir",
        str(out_root),
    ]
    args += _defense_args(defense)
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
        log.write(f"\n===== START {group} {defense} {SUITE} =====\n")
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
        log.write(f"===== END {group} {defense} {SUITE} exit={result.returncode} =====\n")
    if result.returncode != 0:
        raise RuntimeError(f"{group} {defense} {SUITE} failed; see {log_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run DeepSeek-v4-Flash AutoDojo v1.2.2 workspace clean/static slices."
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=ROOT / "ICLR" / "results" / "autodojo_v122_workspace_slice_v1",
    )
    parser.add_argument("--split-manifest", type=Path, default=None)
    parser.add_argument("--defenses", nargs="+", default=None)
    parser.add_argument("--user-tasks", nargs="+", default=DEFAULT_USER_TASKS)
    parser.add_argument("--injection-tasks", nargs="+", default=[])
    parser.add_argument("--clean-only", action="store_true")
    parser.add_argument("--attack-only", action="store_true")
    parser.add_argument("--force-rerun", action="store_true")
    args = parser.parse_args()

    if not args.out_root.is_absolute():
        args.out_root = (Path.cwd() / args.out_root).resolve()
    if args.split_manifest is not None:
        manifest = json.loads(args.split_manifest.read_text(encoding="utf-8"))
        args.user_tasks = [str(item) for item in manifest["user_tasks"]]
        args.injection_tasks = [str(item) for item in manifest["injection_tasks"]]
        if args.defenses is None:
            args.defenses = [str(item) for item in manifest.get("defenses", DEFAULT_DEFENSES)]
    if args.defenses is None:
        args.defenses = list(DEFAULT_DEFENSES)
    args.out_root.mkdir(parents=True, exist_ok=True)

    env = configure_env()
    for defense in args.defenses:
        if not args.attack_only:
            run_benchmark(
                out_root=args.out_root,
                env=env,
                defense=defense,
                with_attack=False,
                force_rerun=args.force_rerun,
                user_tasks=args.user_tasks,
                injection_tasks=args.injection_tasks,
            )
        if not args.clean_only:
            run_benchmark(
                out_root=args.out_root,
                env=env,
                defense=defense,
                with_attack=True,
                force_rerun=args.force_rerun,
                user_tasks=args.user_tasks,
                injection_tasks=args.injection_tasks,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
