from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any


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
PRESETS = {
    "gpt54mini": {
        "model": "gpt-5.4-mini",
        "output_prefix": "gpt54mini",
    },
    "claudehaiku45": {
        "model": "claude-haiku-4-5-20251001",
        "output_prefix": "claudehaiku45",
    },
}


def _key(method: str, suite: str, user: str, injection: str | None) -> str:
    return "|".join((method, suite, user, injection or "clean"))


def _expected(manifest: dict[str, Any]) -> set[str]:
    expected: set[str] = set()
    for suite, split in manifest["suites"].items():
        for user in split["user_tasks"]:
            expected.add(_key("clafr", suite, user, None))
            for injection in split["injection_tasks"]:
                expected.add(_key("clafr", suite, user, injection))

    workspace = manifest["suites"]["workspace"]
    for method in BASELINES:
        for user in workspace["user_tasks"]:
            expected.add(_key(method, "workspace", user, None))
            for injection in workspace["injection_tasks"]:
                expected.add(_key(method, "workspace", user, injection))
    return expected


def _actual(result_root: Path, model_prefix: str, output_prefix: str) -> tuple[list[str], list[str], list[str]]:
    keys: list[str] = []
    errors: list[str] = []
    malformed: list[str] = []
    ignored_prefixes = ("run_manifest", "job_results", f"{output_prefix}_")
    for path in result_root.rglob("*.json"):
        if path.name.startswith(ignored_prefixes):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            malformed.append(str(path))
            continue
        if not isinstance(payload, dict):
            continue
        pipeline = payload.get("pipeline_name")
        if not isinstance(pipeline, str) or not pipeline.startswith(model_prefix):
            continue
        keys.append(
            _key(
                pipeline.removeprefix(model_prefix),
                str(payload["suite_name"]),
                str(payload["user_task_id"]),
                payload.get("injection_task_id"),
            )
        )
        if payload.get("error") is not None:
            errors.append(str(path))
    return keys, errors, malformed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--result-root", type=Path, required=True)
    parser.add_argument("--preset", choices=sorted(PRESETS), required=True)
    args = parser.parse_args()

    preset = PRESETS[args.preset]
    model_prefix = f"{preset['model']}/"
    output_prefix = str(preset["output_prefix"])
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    expected = _expected(manifest)
    actual_list, errors, malformed = _actual(args.result_root, model_prefix, output_prefix)
    counts = Counter(actual_list)
    actual = set(actual_list)
    duplicates = sorted(key for key, count in counts.items() if count != 1)
    report = {
        "schema": f"{output_prefix}-agentdojo-result-audit-v1",
        "model": preset["model"],
        "benchmark_version": "v1.2.2",
        "expected_cases": len(expected),
        "actual_cases": len(actual_list),
        "unique_cases": len(actual),
        "missing": sorted(expected - actual),
        "extra": sorted(actual - expected),
        "duplicates": duplicates,
        "error_results": errors,
        "malformed_json": malformed,
        "passed": len(expected) == len(actual_list)
        and expected == actual
        and not duplicates
        and not errors
        and not malformed,
    }
    output = args.result_root / f"{output_prefix}_result_audit.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
