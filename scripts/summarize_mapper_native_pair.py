"""Audit native-schema mapper/non-mapper runs on matched tool calls.

This is deliberately a replay audit, not a claim that two live planner runs
are paired.  It compares only identical ``(tool, arguments)`` occurrences and
reports the execution fields that can be attributed to the runtime.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def _rows(root: Path) -> dict[tuple, list[dict]]:
    out: dict[tuple, list[dict]] = defaultdict(list)
    for path in sorted(root.glob("qwen-max/clafr/banking/user_task_*/*/*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        calls = {}
        for message in payload.get("messages", []):
            for call in message.get("tool_calls") or []:
                calls[str(call.get("id", ""))] = (
                    str(call.get("function", "")),
                    call.get("args") or {},
                )
        for cert in payload.get("clafr_certificates", []):
            action_id = str(cert.get("action_id", ""))
            if action_id not in calls:
                continue
            tool, args = calls[action_id]
            key = (
                payload.get("user_task_id"),
                payload.get("injection_task_id"),
                tool,
                json.dumps(args, sort_keys=True, ensure_ascii=False),
            )
            out[key].append(cert)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapper", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    mapper = _rows(args.mapper)
    baseline = _rows(args.baseline)
    common = []
    for key in sorted(set(mapper) & set(baseline), key=str):
        for left, right in zip(mapper[key], baseline[key]):
            common.append((left, right))
    fields = ("decision", "feasible", "execution_margin", "violated_constraints")
    exact = sum(all(left.get(field) == right.get(field) for field in fields)
                for left, right in common)
    feature_diff = sum(left.get("features") != right.get("features") for left, right in common)
    result = {
        "schema": "mapper-native-paired-audit-v1",
        "mapper_run": str(args.mapper),
        "baseline_run": str(args.baseline),
        "common_tool_argument_occurrences": len(common),
        "execution_field_exact": exact,
        "execution_field_disagreements": len(common) - exact,
        "feature_payload_disagreements": feature_diff,
        "interpretation": (
            "Live planner traces are not replayed; exact matches support native-schema "
            "non-degradation only. Feature payload differences can reflect planner text."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
