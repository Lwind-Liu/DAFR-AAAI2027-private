from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUTODOJO_ROOT = ROOT / "external" / "official_baselines" / "AutoDojo"
MODEL_PREFIX = "gpt-5.4-mini/"


def _environment(model: str, base_url: str, protocol: str) -> dict[str, str]:
    api_key = os.environ.get("OPENAI_COMPATIBLE_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_COMPATIBLE_API_KEY must be set")
    env = dict(os.environ)
    env.update(
        {
            "OPENAI_MODEL": model,
            "OPENAI_COMPATIBLE_BASE_URL": base_url,
            "OPENAI_COMPATIBLE_PROTOCOL": protocol,
            "SECAGENT_API_KEY": api_key,
            "SECAGENT_BASE_URL": base_url,
            "AGENTDOJO_OPENAI_TIMEOUT_SECONDS": "120",
            "AGENTDOJO_HTTP_RETRIES": "2",
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


def _error_cases(result_root: Path) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    for path in result_root.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        pipeline = payload.get("pipeline_name")
        if (
            isinstance(pipeline, str)
            and pipeline.startswith(MODEL_PREFIX)
            and payload.get("error") is not None
            and payload.get("injection_task_id")
        ):
            cases.append(
                {
                    "method": pipeline.removeprefix(MODEL_PREFIX),
                    "suite": str(payload["suite_name"]),
                    "user_task": str(payload["user_task_id"]),
                    "injection_task": str(payload["injection_task_id"]),
                    "path": str(path),
                }
            )
    return sorted(
        cases,
        key=lambda item: (item["method"], item["suite"], item["user_task"], item["injection_task"]),
    )


def _command(case: dict[str, str], model: str, result_root: Path) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "agentdojo.scripts.benchmark",
        "--model",
        model,
        "--model-id",
        model,
        "--benchmark-version",
        "v1.2.2",
        "--suite",
        case["suite"],
        "--logdir",
        str(result_root),
        "--defense",
        case["method"],
        "--attack",
        "important_instructions",
        "--user-task",
        case["user_task"],
        "--injection-task",
        case["injection_task"],
        "--force-rerun",
    ]
    if case["method"] in {"progent", "drift"}:
        command += ["--defense-model", model, "--defense-model-id", model]
    return command


def _run_case(
    case: dict[str, str], model: str, result_root: Path, env: dict[str, str]
) -> dict[str, Any]:
    log_dir = result_root / "logs" / "error_case_repairs"
    log_dir.mkdir(parents=True, exist_ok=True)
    label = "-".join(
        (case["method"], case["suite"], case["user_task"], case["injection_task"])
    )
    log_path = log_dir / f"{label}.log"
    with log_path.open("w", encoding="utf-8") as log:
        result = subprocess.run(
            _command(case, model, result_root),
            cwd=AUTODOJO_ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    repaired = json.loads(Path(case["path"]).read_text(encoding="utf-8"))
    return {
        **case,
        "exit_code": result.returncode,
        "remaining_error": repaired.get("error"),
        "log": str(log_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-root", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--protocol", choices=("chat_completions", "responses"), required=True)
    parser.add_argument("--max-workers", type=int, default=1)
    args = parser.parse_args()

    result_root = args.result_root.resolve()
    cases = _error_cases(result_root)
    env = _environment(args.model, args.base_url, args.protocol)
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(_run_case, case, args.model, result_root, env): case
            for case in cases
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)

    report = result_root / "error_case_repair_results.json"
    report.write_text(
        json.dumps(sorted(results, key=lambda item: item["path"]), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    failed = [
        result
        for result in results
        if result["exit_code"] != 0 or result["remaining_error"] is not None
    ]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
