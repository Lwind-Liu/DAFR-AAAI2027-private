from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any


MODEL_PREFIX = "gpt-5.4-mini/"
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


def _actual(result_root: Path) -> tuple[list[str], list[str], list[str]]:
    keys: list[str] = []
    errors: list[str] = []
    malformed: list[str] = []
    for path in result_root.rglob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            malformed.append(str(path))
            continue
        if not isinstance(payload, dict):
            continue
        pipeline = payload.get("pipeline_name")
        if not isinstance(pipeline, str) or not pipeline.startswith(MODEL_PREFIX):
            continue
        keys.append(
            _key(
                pipeline.removeprefix(MODEL_PREFIX),
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
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    expected = _expected(manifest)
    actual_list, errors, malformed = _actual(args.result_root)
    counts = Counter(actual_list)
    actual = set(actual_list)
    duplicates = sorted(key for key, count in counts.items() if count != 1)
    report = {
        "schema": "gpt54mini-agentdojo-result-audit-v1",
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
    output = args.result_root / "gpt54mini_result_audit.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
