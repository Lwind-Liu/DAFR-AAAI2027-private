"""Compare the frozen mapper AgentDojo run with the deterministic baseline.

The comparator is intentionally independent of AgentDojo's logger.  It reads
the per-episode JSON files emitted by the benchmark (or the runner summary),
uses the same banking denominators (16 clean and 144 attacked episodes), and
reports Wilson intervals for utility and attack success.  Missing episodes
are a hard error by default so a partial run cannot be presented as a paper
result.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
import math


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAPPER_RUN = ROOT / "results/runs/agentdojo_mapper_banking_full_v7"
DEFAULT_BASELINE_SUMMARY = ROOT / "results/summaries/agentdojo_v122_clafr_final_full_4suite_v1/autodojo_table_aggregate.json"
DEFAULT_OUT = ROOT / "results/summaries/agentdojo_mapper_banking_full_v7/comparison.json"
DEFAULT_DOC = ROOT / "docs/experiments/NAACL_agentdojo_mapper_comparison_ZH.md"


def wilson(successes: int, trials: int, z: float = 1.959963984540054) -> dict[str, float | None]:
    if trials <= 0:
        return {"rate": None, "low": None, "high": None}
    p = successes / trials
    denominator = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denominator
    half = z * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)) / denominator
    return {"rate": p, "low": max(0.0, center - half), "high": min(1.0, center + half)}


def _json_rows(run_root: Path) -> list[dict[str, Any]]:
    base = run_root / "qwen-max" / "clafr" / "banking"
    rows: list[dict[str, Any]] = []
    for path in sorted(base.glob("user_task_*/*/*.json")) if base.exists() else []:
        payload = json.loads(path.read_text(encoding="utf-8"))
        messages = payload.get("messages", [])
        errors = [
            str(message.get("error"))
            for message in messages
            if isinstance(message, dict) and message.get("error")
        ]
        abstain = sum(error == "clafr_mapper_abstain" for error in errors)
        rows.append(
            {
                "path": str(path.relative_to(run_root)),
                "user_task_id": payload.get("user_task_id"),
                "injection_task_id": payload.get("injection_task_id"),
                "utility": bool(payload.get("utility")),
                "security": payload.get("security"),
                "mapper_abstain_messages": abstain,
                "mapper_abstain_episode": bool(abstain),
                "message_error_count": len(errors),
                "non_mapper_error_count": len(errors) - abstain,
                "duration": payload.get("duration"),
            }
        )
    return rows


def _summary_rows(run_root: Path) -> list[dict[str, Any]]:
    path = run_root / "summary.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("rows", []))


def _mapper_metrics(run_root: Path, *, allow_partial: bool) -> dict[str, Any]:
    rows = _json_rows(run_root)
    source = "per_episode_json"
    if not rows:
        rows = _summary_rows(run_root)
        source = "runner_summary"
    clean = [row for row in rows if row.get("injection_task_id") is None]
    attack = [row for row in rows if row.get("injection_task_id") is not None]
    expected = {"clean": 16, "attack": 144}
    observed = {"clean": len(clean), "attack": len(attack)}
    complete = observed == expected
    if not complete and not allow_partial:
        raise RuntimeError(
            f"mapper run is incomplete: observed={observed}, expected={expected}; "
            "pass --allow-partial only for debugging"
        )

    def count(rows_: list[dict[str, Any]], key: str) -> int:
        return sum(bool(row.get(key)) for row in rows_)

    clean_u = count(clean, "utility")
    attack_u = count(attack, "utility")
    attack_success = sum(row.get("security") is True for row in attack)
    protocol_path = run_root / "protocol.json"
    execution_mode = "strict"
    if protocol_path.exists():
        try:
            execution_mode = str(json.loads(protocol_path.read_text(encoding="utf-8")).get("mapper_execution_mode") or "strict")
        except (OSError, ValueError, TypeError):
            execution_mode = "strict"
    return {
        "method": f"Qwen-Max mapper + CLAFR ({execution_mode})",
        "mapper_execution_mode": execution_mode,
        "source": source,
        "complete": complete,
        "expected_denominator": expected,
        "observed_denominator": observed,
        "clean_utility": {"successes": clean_u, "trials": len(clean), **wilson(clean_u, len(clean))},
        "attack_utility": {"successes": attack_u, "trials": len(attack), **wilson(attack_u, len(attack))},
        "attack_success_asr": {
            "successes": attack_success,
            "trials": len(attack),
            **wilson(attack_success, len(attack)),
        },
        "attack_safe": {
            "successes": sum(row.get("security") is False for row in attack),
            "trials": len(attack),
            **wilson(sum(row.get("security") is False for row in attack), len(attack)),
        },
        "mapper_abstain_messages": sum(int(row.get("mapper_abstain_messages", 0) or 0) for row in rows),
        "mapper_abstain_episodes": sum(bool(row.get("mapper_abstain_episode")) for row in rows),
        "message_error_count": sum(int(row.get("message_error_count", 0) or 0) for row in rows),
        "non_mapper_error_count": sum(int(row.get("non_mapper_error_count", 0) or 0) for row in rows),
        "episodes_with_non_mapper_error": sum(bool(row.get("non_mapper_error_count")) for row in rows),
    }


def _raw_run_metrics(run_root: Path, *, label: str, allow_partial: bool) -> dict[str, Any]:
    """Aggregate a same-planner run that did not load a mapper artifact."""
    rows = _json_rows(run_root)
    clean = [row for row in rows if row.get("injection_task_id") is None]
    attack = [row for row in rows if row.get("injection_task_id") is not None]
    expected = {"clean": 16, "attack": 144}
    observed = {"clean": len(clean), "attack": len(attack)}
    complete = observed == expected
    if not complete and not allow_partial:
        raise RuntimeError(
            f"same-planner baseline is incomplete: observed={observed}, expected={expected}; "
            "pass --allow-partial only for debugging"
        )
    clean_u = sum(bool(row.get("utility")) for row in clean)
    attack_u = sum(bool(row.get("utility")) for row in attack)
    attack_success = sum(row.get("security") is True for row in attack)
    return {
        "method": label,
        "source": str(run_root),
        "complete": complete,
        "expected_denominator": expected,
        "observed_denominator": observed,
        "clean_utility": {"successes": clean_u, "trials": len(clean), **wilson(clean_u, len(clean))},
        "attack_utility": {"successes": attack_u, "trials": len(attack), **wilson(attack_u, len(attack))},
        "attack_success_asr": {"successes": attack_success, "trials": len(attack), **wilson(attack_success, len(attack))},
        "attack_safe": {
            "successes": sum(row.get("security") is False for row in attack),
            "trials": len(attack),
            **wilson(sum(row.get("security") is False for row in attack), len(attack)),
        },
        "mapper_abstain_messages": None,
        "mapper_abstain_episodes": None,
        "message_error_count": sum(int(row.get("message_error_count", 0) or 0) for row in rows),
        "non_mapper_error_count": sum(int(row.get("non_mapper_error_count", 0) or 0) for row in rows),
        "episodes_with_non_mapper_error": sum(bool(row.get("non_mapper_error_count")) for row in rows),
    }


def _baseline_metrics(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    row = next(
        item for item in payload.get("rows", [])
        if any(suite.get("suite") == "banking" for suite in item.get("suite_rows", []))
    )
    suite = next(suite for suite in row["suite_rows"] if suite.get("suite") == "banking")
    clean_n = int(suite["expected_clean_cases"])
    attack_n = int(suite["expected_attack_cases"])
    clean_u = round(float(suite["clean_utility"]) * clean_n)
    attack_u = round(float(suite["static_attack_utility"]) * attack_n)
    asr = round(float(suite["static_asr"]) * attack_n)
    return {
        "method": "Original deterministic CLAFR",
        "source": str(path),
        "complete": True,
        "expected_denominator": {"clean": clean_n, "attack": attack_n},
        "observed_denominator": {"clean": clean_n, "attack": attack_n},
        "clean_utility": {"successes": clean_u, "trials": clean_n, **wilson(clean_u, clean_n)},
        "attack_utility": {"successes": attack_u, "trials": attack_n, **wilson(attack_u, attack_n)},
        "attack_success_asr": {"successes": asr, "trials": attack_n, **wilson(asr, attack_n)},
        "attack_safe": {"successes": attack_n - asr, "trials": attack_n, **wilson(attack_n - asr, attack_n)},
        "mapper_abstain_messages": None,
        "mapper_abstain_episodes": None,
        "message_error_count": None,
        "non_mapper_error_count": None,
        "episodes_with_non_mapper_error": None,
    }


def _delta(mapper: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    def difference(key: str) -> float | None:
        left = mapper[key]["rate"]
        right = baseline[key]["rate"]
        if left is None or right is None:
            return None
        return left - right

    return {
        "clean_utility_rate": difference("clean_utility"),
        "attack_utility_rate": difference("attack_utility"),
        "attack_asr_rate": difference("attack_success_asr"),
    }


def _pct(value: float | None) -> str:
    return "NA" if value is None else f"{100.0 * value:.2f}%"


def _pp(value: float | None) -> str:
    return "NA" if value is None else f"{100.0 * value:+.2f} pp"


def _write_doc(path: Path, report: dict[str, Any]) -> None:
    mapper = report["mapper"]
    baseline = report["baseline"]
    delta = report["delta"]
    same_planner = report.get("same_planner_baseline")
    lines = [
        "# NAACL AgentDojo：Qwen-Max 语义映射端到端对照（banking）",
        "",
        "本页由 `scripts/aggregate_agentdojo_mapper_compare.py` 生成。评测固定 AgentDojo v1.2.2、banking、Qwen-Max planner、CLAFR runtime 和 `important_instructions` 攻击；唯一变化是 mapper artifact。",
        "",
        "## 分母和完整性",
        "",
        f"- 预注册分母：clean 16，attack 144（16 个 user task × 9 个 injection task）。",
        f"- Qwen-Max mapper：clean {mapper['observed_denominator']['clean']}/{mapper['expected_denominator']['clean']}，attack {mapper['observed_denominator']['attack']}/{mapper['expected_denominator']['attack']}，complete={mapper['complete']}。",
        f"- 原始 deterministic CLAFR：clean {baseline['observed_denominator']['clean']}，attack {baseline['observed_denominator']['attack']}；结果来源为既有 full-suite 汇总。",
        "",
        "## 同分母结果（Wilson 95% CI）",
        "",
        "| 方法 | Clean utility | Attack utility | ASR |",
        "|---|---:|---:|---:|",
        f"| {mapper['method']} | {_pct(mapper['clean_utility']['rate'])} [{_pct(mapper['clean_utility']['low'])}, {_pct(mapper['clean_utility']['high'])}] | {_pct(mapper['attack_utility']['rate'])} [{_pct(mapper['attack_utility']['low'])}, {_pct(mapper['attack_utility']['high'])}] | {_pct(mapper['attack_success_asr']['rate'])} [{_pct(mapper['attack_success_asr']['low'])}, {_pct(mapper['attack_success_asr']['high'])}] |",
        f"| 原始 deterministic CLAFR | {_pct(baseline['clean_utility']['rate'])} [{_pct(baseline['clean_utility']['low'])}, {_pct(baseline['clean_utility']['high'])}] | {_pct(baseline['attack_utility']['rate'])} [{_pct(baseline['attack_utility']['low'])}, {_pct(baseline['attack_utility']['high'])}] | {_pct(baseline['attack_success_asr']['rate'])} [{_pct(baseline['attack_success_asr']['low'])}, {_pct(baseline['attack_success_asr']['high'])}] |",
    ]
    if same_planner is not None:
        lines.append(
            f"| 同 planner 的 no-mapper CLAFR | {_pct(same_planner['clean_utility']['rate'])} [{_pct(same_planner['clean_utility']['low'])}, {_pct(same_planner['clean_utility']['high'])}] | {_pct(same_planner['attack_utility']['rate'])} [{_pct(same_planner['attack_utility']['low'])}, {_pct(same_planner['attack_utility']['high'])}] | {_pct(same_planner['attack_success_asr']['rate'])} [{_pct(same_planner['attack_success_asr']['low'])}, {_pct(same_planner['attack_success_asr']['high'])}] |"
        )
    lines.extend([
        "",
        f"- mapper 相对 deterministic 的差值：clean utility {_pp(delta['clean_utility_rate'])}，attack utility {_pp(delta['attack_utility_rate'])}，ASR {_pp(delta['attack_asr_rate'])}。",
    ])
    if same_planner is not None:
        same_delta = report["same_planner_delta"]
        lines.append(
            f"- mapper 相对同 planner no-mapper 的差值：clean utility {_pp(same_delta['clean_utility_rate'])}，attack utility {_pp(same_delta['attack_utility_rate'])}，ASR {_pp(same_delta['attack_asr_rate'])}。"
        )
    lines.extend([
        "- `security=true` 计为攻击成功；`security=false` 计为攻击被阻断。",
        "",
        "## Mapper 诊断",
        "",
        f"- `clafr_mapper_abstain` 消息数：{mapper['mapper_abstain_messages']}；涉及 episode：{mapper['mapper_abstain_episodes']}。",
        f"- 非 mapper 消息错误数：{mapper['non_mapper_error_count']}；涉及 episode：{mapper['episodes_with_non_mapper_error']}。",
        "- deterministic baseline 没有 mapper artifact，因此其 mapper 指标记为 NA，不能把 runtime block 当作 mapper compile error。",
        "",
        "## 解释边界",
        "",
        "该表只支持在同一 planner、同一任务分母和同一 runtime 下比较语义迁移对端到端 utility/safety 的影响；它不把 Qwen-Max mapper 的小规模结果外推为所有工具上的泛化保证。若 mapper 端到端 utility 未超过 deterministic baseline，应优先报告 clean false block、abstention 和 compile/error 分布，而不是通过删任务来提高平均分。",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapper-run", type=Path, default=DEFAULT_MAPPER_RUN)
    parser.add_argument("--baseline-summary", type=Path, default=DEFAULT_BASELINE_SUMMARY)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    parser.add_argument(
        "--same-planner-baseline-run",
        type=Path,
        default=None,
        help="可选的同 planner、未加载 mapper 的 AgentDojo run 根目录。",
    )
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    mapper = _mapper_metrics(args.mapper_run, allow_partial=args.allow_partial)
    baseline = _baseline_metrics(args.baseline_summary)
    report = {
        "schema": "agentdojo-mapper-comparison-v1",
        "protocol": {
            "suite": "banking",
            "benchmark_version": "v1.2.2",
            "attack": "important_instructions",
            "clean_denominator": 16,
            "attack_denominator": 144,
            "confidence_interval": "Wilson 95%",
        },
        "mapper": mapper,
        "baseline": baseline,
        "delta": _delta(mapper, baseline),
    }
    if args.same_planner_baseline_run is not None:
        same_planner = _raw_run_metrics(
            args.same_planner_baseline_run,
            label="Qwen-Max planner + deterministic CLAFR (no mapper)",
            allow_partial=args.allow_partial,
        )
        report["same_planner_baseline"] = same_planner
        report["same_planner_delta"] = _delta(mapper, same_planner)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_doc(args.doc, report)
    print(json.dumps({"out": str(args.out), "doc": str(args.doc), "delta": report["delta"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
