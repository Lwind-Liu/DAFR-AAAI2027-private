"""Run the frozen Qwen-Max mapper on all AgentDojo banking tasks.

This runner deliberately keeps planner and defense fixed.  The only mapper
artifact is the validated Qwen-Max banking artifact; no mapper API calls are
made during the benchmark.  It writes command/protocol metadata and raw
AgentDojo JSON files under ``results/runs`` so the run can be audited later.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
AUTO = ROOT / "external" / "official_baselines" / "AutoDojo"
PYTHON = Path(os.environ.get("DAFR_AGENTDOJO_PYTHON", str(ROOT / ".venv/bin/python")))
BENCHMARK = "v1.2.2"
SUITE = "banking"
ATTACK = "important_instructions"
MAPPER = Path(
    os.environ.get(
        "DAFR_MAPPER_ARTIFACT",
        str(ROOT / "results/summaries/agentdojo_mapper_banking_v2/artifact_v2.jsonl"),
    )
)


def _read_platform_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _configured_env(platform_env: Path, *, mapper_artifact: Path | None) -> dict[str, str]:
    cfg = _read_platform_env(platform_env)
    required = ("API_BASE_URL", "ACCESS_KEY", "APP_NAME", "QUOTA_ID", "USER_ID")
    missing = [key for key in required if not cfg.get(key)]
    if missing:
        raise RuntimeError(f"platform env missing {missing}")
    env = dict(os.environ)
    # AutoDojo's OpenAI-compatible route forwards the Distill metadata in
    # extra_body.  The bearer value is also set for the proxy's auth layer.
    env.update(
        {
            "OPENAI_MODEL": "qwen-max",
            "OPENAI_COMPATIBLE_BASE_URL": cfg["API_BASE_URL"],
            "OPENAI_COMPATIBLE_PROTOCOL": "chat_completions",
            "OPENAI_COMPATIBLE_API_KEY": cfg["ACCESS_KEY"],
            "DISTILL_ACCESS_KEY": cfg["ACCESS_KEY"],
            "DISTILL_APP_NAME": cfg["APP_NAME"],
            "DISTILL_QUOTA_ID": cfg["QUOTA_ID"],
            "DISTILL_USER_ID": cfg["USER_ID"],
            "ANTHROPIC_API_KEY": cfg["ACCESS_KEY"],
            "SECAGENT_API_KEY": cfg["ACCESS_KEY"],
            "AGENTDOJO_OPENAI_TIMEOUT_SECONDS": os.environ.get(
                "AGENTDOJO_OPENAI_TIMEOUT_SECONDS", "180"
            ),
            "AGENTDOJO_HTTP_RETRIES": os.environ.get("AGENTDOJO_HTTP_RETRIES", "2"),
            "AGENTDOJO_RUN_INJECTION_UTILITY": "0",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "NO_COLOR": "1",
            "TERM": "dumb",
            "PYTHONPATH": os.pathsep.join(
                (
                    str(AUTO / "agentdojo/src"),
                    str(AUTO / "agentdojo/variant_generation"),
                    str(ROOT / "src"),
                    str(ROOT),
                )
            ),
        }
    )
    if mapper_artifact is not None:
        env["CLAFR_MAPPER_ARTIFACT"] = str(mapper_artifact)
    else:
        env.pop("CLAFR_MAPPER_ARTIFACT", None)
    return env


def _benchmark_command(out_root: Path, *, attack: bool, force: bool) -> list[str]:
    command = [
        str(PYTHON),
        "-m",
        "agentdojo.scripts.benchmark",
        "--model",
        "qwen-max",
        "--model-id",
        "qwen-max",
        "--benchmark-version",
        BENCHMARK,
        "--suite",
        SUITE,
        "--defense",
        "clafr",
        "--logdir",
        str(out_root),
    ]
    if attack:
        command.extend(["--attack", ATTACK])
        for task in range(9):
            command.extend(["--injection-task", f"injection_task_{task}"])
    for task in range(16):
        command.extend(["--user-task", f"user_task_{task}"])
    if force:
        command.append("--force-rerun")
    return command


def _collect(out_root: Path, *, mapper_artifact: Path | None) -> dict[str, object]:
    base = out_root / "qwen-max" / "clafr" / SUITE
    rows = []
    for path in sorted(base.glob("user_task_*/*/*.json")) if base.exists() else []:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows.append(
            {
                "path": str(path.relative_to(out_root)),
                "user_task_id": payload.get("user_task_id"),
                "injection_task_id": payload.get("injection_task_id"),
                "utility": bool(payload.get("utility")),
                "security": payload.get("security"),
                "duration": payload.get("duration"),
                "mapper_abstain_messages": sum(
                    message.get("error") == "clafr_mapper_abstain"
                    for message in payload.get("messages", [])
                    if isinstance(message, dict)
                ),
                "error": payload.get("error"),
            }
        )
    clean = [row for row in rows if row["injection_task_id"] is None]
    attack = [row for row in rows if row["injection_task_id"] is not None]
    summary = {
        "suite": SUITE,
        "benchmark_version": BENCHMARK,
        "model": "qwen-max",
        "defense": "clafr",
        "mapper_artifact": (str(mapper_artifact.relative_to(ROOT)) if mapper_artifact is not None else None),
        "clean_n": len(clean),
        "clean_utility": sum(row["utility"] for row in clean),
        "clean_utility_rate": (sum(row["utility"] for row in clean) / len(clean)) if clean else None,
        "attack_n": len(attack),
        "attack_utility": sum(row["utility"] for row in attack),
        "attack_utility_rate": (sum(row["utility"] for row in attack) / len(attack)) if attack else None,
        "attack_success": sum(row["security"] is True for row in attack),
        "attack_success_rate": (sum(row["security"] is True for row in attack) / len(attack)) if attack else None,
        "attack_safe_rate": (sum(row["security"] is False for row in attack) / len(attack)) if attack else None,
        "mapper_abstain_messages": sum(row["mapper_abstain_messages"] for row in rows),
        "rows": rows,
    }
    return summary


def main() -> int:
    global PYTHON, MAPPER
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out-root",
        type=Path,
        default=ROOT / "results/runs/agentdojo_mapper_banking_full_v7",
    )
    parser.add_argument(
        "--platform-env",
        type=Path,
        default=Path("/Users/haomin/Desktop/code/distill/playground-batch-annotate/platform.env"),
    )
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--skip-attack", action="store_true")
    parser.add_argument("--no-force", action="store_true")
    parser.add_argument(
        "--mapper-artifact",
        type=Path,
        default=MAPPER,
        help="冻结的语义映射产物；默认使用当前 v2 Qwen-Max 产物。",
    )
    parser.add_argument(
        "--python",
        dest="python_path",
        type=Path,
        default=PYTHON,
        help="AgentDojo 运行时 Python；默认使用仓库 .venv。",
    )
    parser.add_argument(
        "--disable-mapper",
        action="store_true",
        help="只用于公平同 planner/runtime 对照：不加载语义映射 artifact。",
    )
    args = parser.parse_args()
    # Keep the venv launcher path intact. Resolving its symlink to the shared
    # interpreter would drop the venv site-packages (notably ``click``).
    PYTHON = args.python_path.absolute()
    MAPPER = args.mapper_artifact.resolve()
    if not PYTHON.exists():
        raise RuntimeError(f"missing benchmark runtime: {PYTHON}")
    if not args.disable_mapper and not MAPPER.exists():
        raise RuntimeError(f"missing mapper artifact: {MAPPER}")
    out_root = args.out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    env = _configured_env(args.platform_env, mapper_artifact=None if args.disable_mapper else MAPPER)
    protocol = {
        "schema": "agentdojo-mapper-banking-full-v7-v1",
        "suite": SUITE,
        "benchmark_version": BENCHMARK,
        "attack": ATTACK,
        "model": "qwen-max",
        "defense": "clafr",
        "mapper_artifact": None if args.disable_mapper else str(MAPPER.resolve()),
        "clean_user_tasks": [f"user_task_{i}" for i in range(16)],
        "attack_user_tasks": [f"user_task_{i}" for i in range(16)],
        "injection_tasks": [f"injection_task_{i}" for i in range(9)],
        "same_planner_for_clean_attack": True,
        "api_base_url": env["OPENAI_COMPATIBLE_BASE_URL"],
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out_root / "protocol.json").write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for name, attack in (("clean", False), ("attack", True)):
        if (args.skip_clean and not attack) or (args.skip_attack and attack):
            continue
        command = _benchmark_command(out_root, attack=attack, force=not args.no_force)
        log_path = out_root / f"{name}.stdout.log"
        (out_root / f"{name}.command.txt").write_text(" ".join(command) + "\n", encoding="utf-8")
        with log_path.open("w", encoding="utf-8") as log:
            log.write(" ".join(command) + "\n")
            log.flush()
            started = time.monotonic()
            completed = subprocess.run(command, cwd=AUTO, env=env, stdout=log, stderr=subprocess.STDOUT)
            log.write(f"\nexit_code={completed.returncode} elapsed_sec={time.monotonic()-started:.3f}\n")
        print(json.dumps({"phase": name, "exit_code": completed.returncode}, ensure_ascii=False), flush=True)
        if completed.returncode != 0:
            # Keep the partial files for audit, then continue to write a
            # summary that distinguishes missing rows from failed jobs.
            break
    summary = _collect(
        out_root,
        mapper_artifact=None if args.disable_mapper else MAPPER,
    )
    (out_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: summary[k] for k in summary if k != "rows"}, ensure_ascii=False, indent=2))
    return 0 if summary["clean_n"] == 16 and summary["attack_n"] == 144 else 2


if __name__ == "__main__":
    raise SystemExit(main())
