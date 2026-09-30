"""Replay saved AgentDojo action boundaries with exactly shared inputs.

No planner calls, benchmark tool execution, environment replay, or utility
counterfactuals.  The evidence builder is the real CLAFR adapter.  The saved
message prefix is authoritative; hidden provenance is recovered only from
visible saved tool messages, because the historical private ledger was not
serialized.  Every comparison reuses one action and one RuntimeEvidence.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AGENTDOJO_SRC = ROOT / "external/official_baselines/AutoDojo/agentdojo/src"
for source in (ROOT / "src", AGENTDOJO_SRC):
    sys.path.insert(0, str(source))

from agentdojo.agent_pipeline import clafr_defense as adapter
from agentdojo.functions_runtime import FunctionsRuntime
from agentdojo.task_suite.load_suites import get_suite
from clafr import ConfidenceLiftedActionSelector, ToolAction, project_action_format
from clafr.ir_compiler import IRPolicyCompiler
from clafr.policy_ir import ConstraintIR, validate_constraint_ir


DEFAULT_RUNS = (
    ROOT / "results/runs/agentdojo_mapper_banking_roles_only_reencode_v2_full_escalated",
    ROOT / "results/runs/agentdojo_no_mapper_banking_reencode_full",
)
EPSILON = 1e-12


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def code_hashes() -> dict[str, str]:
    """Hash implementation modules, including already imported suite sources."""
    paths = {Path(__file__).resolve()}
    for base in (ROOT / "src/clafr", ROOT / "src/geoconstraints"):
        paths.update(base.rglob("*.py"))
    for module in tuple(sys.modules.values()):
        source = getattr(module, "__file__", None)
        if source and source.endswith(".py"):
            path = Path(source).resolve()
            if path.is_relative_to(AGENTDOJO_SRC):
                paths.add(path)
    return {relative(path): file_hash(path) for path in sorted(paths)}


def load_artifact(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        tool = record["tool_name"]
        if tool in records:
            raise ValueError(f"Duplicate artifact tool: {tool}")
        records[tool] = record
    return records


def mapped_selector(record: dict[str, Any] | None, action: ToolAction,
                    evidence: Any, base: Any, mode: str = "roles_only"):
    if record is None or record.get("status") != "allow_to_compile" or not record.get("ir"):
        return None, "missing_or_abstained_mapper_record"
    ir = ConstraintIR.from_dict(record["ir"])
    # Match adapter schema union exactly; do not make this replay a new policy.
    fields = tuple(dict.fromkeys((*record.get("fields", ()),
                                *evidence.tool_schema.get(action.tool_name, ()),
                                *action.arguments.keys())))
    try:
        validate_constraint_ir(ir, schema_fields=fields or tuple(ir.roles))
        if mode == "roles_only":
            if ir.forbidden_effects:
                return None, "unsupported_forbidden_effects"
            ir = replace(ir, preconditions=(), risk_budgets=(),
                         provenance=f"{ir.provenance}:roles_only")
        compiler = IRPolicyCompiler(ir, schema_fields=fields or tuple(ir.roles), baseline=base)
    except (ValueError, TypeError, KeyError) as exc:
        return None, f"invalid_mapper_record:{type(exc).__name__}:{exc}"
    return ConfidenceLiftedActionSelector(compiler=compiler), None


def result_record(selector: Any, action: ToolAction, evidence: Any) -> dict[str, Any]:
    result = selector.select((action,), evidence)
    certificate = result.certificates[0]
    hard = [m for m in certificate.margins if not m.soft and m.constraint_id != "schema_complete"]
    region = selector.compiler.compile(evidence.policies, evidence)
    return {
        "decision": result.decision,
        "feasible": certificate.feasible,
        "features": dict(certificate.features),
        "margins": [asdict(m) for m in certificate.margins],
        "constraints": [asdict(c) for c in region.constraints],
        "execution_margin": min((m.slack for m in hard), default=None),
        "violated_constraints": list(certificate.violated_constraints),
        "role_projection": dict(certificate.role_projection),
    }


def repair_record(selector: Any, action: ToolAction, evidence: Any,
                  primary: dict[str, Any]) -> dict[str, Any]:
    if primary["feasible"]:
        return {"attempted": False, "candidate_found": False}
    repaired = selector.repair(action, evidence)
    if repaired is None or repaired.selected is None:
        return {"attempted": True, "candidate_found": False}
    return {"attempted": True, "candidate_found": True,
            "candidate": asdict(repaired.selected),
            "certificate": asdict(repaired.selected_certificate),
            "externally_executed": False,
            "effect_preservation_verified": False}


def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    deltas = {k: right["features"].get(k, 0) - left["features"].get(k, 0)
              for k in left["features"].keys() | right["features"].keys()}
    lm = {m["constraint_id"]: m for m in left["margins"]}
    rm = {m["constraint_id"]: m for m in right["margins"]}
    margin_delta = {k: rm[k]["slack"] - lm[k]["slack"] for k in lm.keys() & rm.keys()}
    return {
        "decision_equal": left["decision"] == right["decision"],
        "features_equal": all(abs(v) <= EPSILON for v in deltas.values()),
        "feature_max_abs_delta": max(map(abs, deltas.values()), default=0.0),
        "changed_features": {k: v for k, v in deltas.items() if abs(v) > EPSILON},
        "constraints_equal": canonical(left["constraints"]) == canonical(right["constraints"]),
        "margin_ids_equal": lm.keys() == rm.keys(),
        "margins_equal": lm.keys() == rm.keys() and all(abs(v) <= EPSILON for v in margin_delta.values()),
        "margin_max_abs_delta": max(map(abs, margin_delta.values()), default=0.0),
        "changed_margin_slacks": {k: v for k, v in margin_delta.items() if abs(v) > EPSILON},
        "violated_constraints_equal": left["violated_constraints"] == right["violated_constraints"],
    }


def historical_comparison(saved: dict[str, Any] | None, replay: dict[str, Any]) -> dict[str, Any]:
    if saved is None:
        return {"available": False}
    feature_delta = {k: replay["features"].get(k, 0) - value
                     for k, value in saved.get("features", {}).items()}
    # The historical logger intentionally excludes the hard schema gate.
    replay_violated = [c for c in replay["violated_constraints"] if c != "schema_complete"]
    old_margin, new_margin = saved.get("execution_margin"), replay["execution_margin"]
    return {
        "available": True,
        "decision_equal": saved.get("decision") == replay["decision"],
        "logged_feature_count": len(feature_delta),
        "logged_features_equal": all(abs(v) <= EPSILON for v in feature_delta.values()),
        "changed_logged_features": {k: v for k, v in feature_delta.items() if abs(v) > EPSILON},
        "execution_margin_equal": (old_margin == new_margin if old_margin is None or new_margin is None
                                   else abs(old_margin - new_margin) <= EPSILON),
        "execution_margin_delta": None if old_margin is None or new_margin is None else new_margin - old_margin,
        "violated_constraints_equal": saved.get("violated_constraints", []) == replay_violated,
    }


def recover_hidden_blocks(messages: list[dict[str, Any]]) -> list[str]:
    """Approximate the unsaved private ledger from saved projected observations.

    This is explicitly not recovery of unavailable raw tool outputs or opaque
    bindings. Both experimental arms receive this one identical reconstruction.
    """
    blocks: list[str] = []
    for message in messages:
        if message.get("role") != "tool" or message.get("error") in {"clafr_blocked", "clafr_mapper_abstain"}:
            continue
        text = adapter._content_text(message.get("content"))
        _, hidden, _ = adapter._observation_transition(
            text, {}, enable_evidence_projection=True, enable_dynamic_geometry=True)
        for block in hidden:
            if block not in blocks:
                blocks.append(block[:8000])
        blocks = blocks[-32:]
        if message.get("error"):
            artifact = adapter.DEFAULT_OBSERVATION_CONSTRAINT_PROJECTOR.project(str(message["error"]), {})
            blocks.extend(artifact.untrusted_blocks)
            blocks = blocks[-32:]
    return blocks


def counters(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [r for r in rows if r["status"] == "compared"]
    old = [r["historical_fidelity"] for r in valid if r["historical_fidelity"].get("available")]
    return {
        "saved_actions": len(rows), "compared_actions": len(valid),
        "statuses": dict(Counter(r["status"] for r in rows)),
        "decision_pairs": dict(Counter(f'{r["no_mapper"]["decision"]} -> {r["mapper"]["decision"]}' for r in valid)),
        "decision_disagreements": sum(not r["parity"]["decision_equal"] for r in valid),
        "feature_disagreements": sum(not r["parity"]["features_equal"] for r in valid),
        "constraint_disagreements": sum(not r["parity"]["constraints_equal"] for r in valid),
        "margin_disagreements": sum(not r["parity"]["margins_equal"] for r in valid),
        "violated_constraint_disagreements": sum(not r["parity"]["violated_constraints_equal"] for r in valid),
        "max_feature_delta": max((r["parity"]["feature_max_abs_delta"] for r in valid), default=0),
        "max_margin_delta": max((r["parity"]["margin_max_abs_delta"] for r in valid), default=0),
        "repair_candidate_differences": sum(canonical(r["no_mapper_repair"]) != canonical(r["mapper_repair"]) for r in valid),
        "historical_fidelity": {
            "available": len(old),
            **{field: sum(not r[field] for r in old) for field in (
                "decision_equal", "logged_features_equal", "execution_margin_equal", "violated_constraints_equal")},
            "counter_meaning": "Each field above counts mismatches, not matches.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", action="append", type=Path,
                        help="Repeat for multiple source runs; default replays both frozen banking runs.")
    parser.add_argument("--mapper-artifact", type=Path, default=ROOT / "results/summaries/agentdojo_mapper_banking_v3/artifact_v3.jsonl")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/summaries/agentdojo_mapper_boundary_replay_v1")
    parser.add_argument("--doc", type=Path, default=ROOT / "docs/experiments/NAACL_mapper_boundary_replay_v1_ZH.md")
    parser.add_argument("--hidden-ledger", choices=("recover_saved", "empty"), default="recover_saved")
    args = parser.parse_args()
    runs = [p.resolve() for p in (args.run_dir or DEFAULT_RUNS)]
    artifact_path = args.mapper_artifact.resolve()
    records = load_artifact(artifact_path)
    suite = get_suite("v1.2.2", "banking")
    runtime = FunctionsRuntime(suite.tools)
    # A tripwire makes accidental environment execution fail instead of running.
    def forbidden_execution(*_args, **_kwargs):
        raise RuntimeError("Boundary replay never executes benchmark tools")
    runtime.run_function = forbidden_execution
    base = adapter.CLAFRToolsExecutor()._base_compiler
    no_mapper_selector = ConfidenceLiftedActionSelector(compiler=base)
    before_hashes = code_hashes()
    artifact_sha = file_hash(artifact_path)
    source_files: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    inputs: list[dict[str, Any]] = []
    protocols: list[dict[str, Any]] = []
    for run in runs:
        protocol_path = run / "protocol.json"
        protocol = json.loads(protocol_path.read_text())
        if (protocol.get("suite"), protocol.get("benchmark_version"), protocol.get("defense")) != ("banking", "v1.2.2", "clafr"):
            raise ValueError(f"Unsupported source protocol: {protocol_path}")
        protocols.append({"path": relative(protocol_path), "sha256": file_hash(protocol_path), "protocol": protocol})
        historical_records = (load_artifact(Path(protocol["mapper_artifact"])) if protocol.get("mapper_artifact") else None)
        files = sorted((run / "qwen-max/clafr/banking").glob("*/*/*.json"))
        if not files:
            raise ValueError(f"No task traces: {run}")
        for path in files:
            task = json.loads(path.read_text())
            source_sha = file_hash(path)
            source_files.append({"path": relative(path), "sha256": source_sha})
            messages = task["messages"]
            saved_certificates = {c["action_id"]: c for c in task.get("clafr_certificates", [])}
            for message_index, message in enumerate(messages):
                if message.get("role") != "assistant" or not message.get("tool_calls"):
                    continue
                prefix = messages[:message_index + 1]
                hidden = recover_hidden_blocks(prefix) if args.hidden_ledger == "recover_saved" else []
                evidence = adapter._build_evidence(prefix, runtime, hidden,
                    project_tool_state=True, detect_untrusted_control=True,
                    geometry_fallback_state=False, state_freshness=1.0)
                evidence_data = asdict(evidence)
                context = "\n\n".join(f"{m.get('role')}: {adapter._content_text(m.get('content'))}" for m in prefix[-12:])
                for call_index, call in enumerate(message["tool_calls"]):
                    key = f"{run.name}/{task['user_task_id']}/{task.get('injection_task_id') or 'none'}/{message_index}/{call_index}"
                    row: dict[str, Any] = {
                        "id": key, "source_run": run.name, "source_path": relative(path),
                        "source_sha256": source_sha, "user_task_id": task["user_task_id"],
                        "injection_task_id": task.get("injection_task_id"),
                        "message_index": message_index, "tool_call_index": call_index,
                        "prefix_sha256": digest(prefix), "evidence_sha256": digest(evidence_data),
                        "hidden_blocks_recovered": len(hidden),
                        "historical_episode_error": task.get("error"),
                    }
                    tool_name = call.get("function")
                    arguments = call.get("args")
                    if not isinstance(tool_name, str) or not tool_name.strip() or not isinstance(arguments, dict):
                        row.update(status="malformed_call", saved_call=call)
                        rows.append(row)
                        continue
                    if tool_name not in runtime.functions:
                        row.update(status="unknown_tool", saved_call=call)
                        rows.append(row)
                        continue
                    raw_action = ToolAction(id=str(call.get("id") or f"clafr_call_{call_index}"),
                        tool_name=tool_name, arguments=dict(arguments), rationale=context[-1200:])
                    projection = project_action_format(raw_action, evidence)
                    action = projection.action
                    row.update(action_sha256=digest(asdict(action)), tool_name=tool_name,
                               format_projection_changed=projection.changed)
                    inputs.append({"id": key, "prefix_sha256": row["prefix_sha256"],
                        "evidence_sha256": row["evidence_sha256"], "raw_action": asdict(raw_action),
                        "projected_action": asdict(action), "evidence": evidence_data,
                        "hidden_untrusted_blocks": hidden})
                    mapped, reason = mapped_selector(records.get(tool_name), action, evidence, base)
                    if mapped is None:
                        row.update(status="mapper_abstain", reason=reason)
                        rows.append(row)
                        continue
                    no = result_record(no_mapper_selector, action, evidence)
                    yes = result_record(mapped, action, evidence)
                    historical_selector = no_mapper_selector
                    if historical_records is not None:
                        historical_selector, historical_error = mapped_selector(historical_records.get(tool_name), action,
                            evidence, base, protocol.get("mapper_execution_mode") or "strict")
                        if historical_selector is None:
                            raise ValueError(f"Cannot reconstruct original mapper mode: {key}: {historical_error}")
                    old = result_record(historical_selector, action, evidence)
                    row.update(status="compared", no_mapper=no, mapper=yes, parity=compare(no, yes),
                        no_mapper_repair=repair_record(no_mapper_selector, action, evidence, no),
                        mapper_repair=repair_record(mapped, action, evidence, yes),
                        historical_fidelity=historical_comparison(saved_certificates.get(action.id), old))
                    # Comparisons must not mutate their shared inputs.
                    if digest(asdict(evidence)) != row["evidence_sha256"] or digest(asdict(action)) != row["action_sha256"]:
                        raise RuntimeError(f"Input mutation during replay: {key}")
                    rows.append(row)
    after_hashes = code_hashes()
    if before_hashes != after_hashes or artifact_sha != file_hash(artifact_path):
        raise RuntimeError("Code/artifact changed during replay; discard this run and retry with frozen code")
    for entry in source_files:
        if file_hash(ROOT / entry["path"]) != entry["sha256"]:
            raise RuntimeError(f"Source trace changed: {entry['path']}")
    summary = {"schema": "agentdojo-fixed-prefix-boundary-replay-v1", "created_at": datetime.now(timezone.utc).isoformat(),
        "source_episodes": len(source_files), "hidden_ledger_protocol": args.hidden_ledger,
        "mapper_artifact": relative(artifact_path), "mapper_artifact_sha256": artifact_sha,
        "mapper_mode": "roles_only", "code_commit": git("rev-parse", "HEAD"),
        "code_unchanged_during_replay": True, "external_tool_executions": 0, "api_calls": 0,
        "utility_counterfactual_evaluated": False, "numeric_equality_tolerance": EPSILON,
        **counters(rows), "by_source_run": {run.name: counters([r for r in rows if r["source_run"] == run.name]) for run in runs},
        "limitations": [
            "Saved messages are post-projection observations; original raw outputs, private hidden-provenance ledger and opaque bindings were not serialized.",
            "Recovered hidden blocks are reconstructed from saved text, not claimed to be the original private ledger.",
            "Historical fidelity compares only saved decision, six logged features, execution margin and violated constraints; matching them cannot prove complete historical state identity.",
            "The source protocol did not pin all code/artifact hashes; fidelity is current-code replay, not proof of exact historical version reproduction.",
            "Both arms receive exactly the same reconstructed action/evidence. No new observations or repaired actions are executed; later prefixes remain the recorded trajectory.",
            "Decision parity is restricted to these reconstructed saved boundaries and does not establish utility non-degradation or general safety.",
        ]}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in (("rows.jsonl", rows), ("inputs.jsonl", inputs)):
        (args.output_dir / name).write_text("".join(canonical(row) + "\n" for row in payload), encoding="utf-8")
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {"code_commit": summary["code_commit"], "code_files": before_hashes,
        "code_tree_sha256": digest(before_hashes), "adapter_sha256": file_hash(Path(adapter.__file__)),
        "mapper_artifact": {"path": relative(artifact_path), "sha256": artifact_sha},
        "source_protocols": protocols, "source_traces": source_files,
        "source_trace_set_sha256": digest(source_files),
        "output_files": {name: file_hash(args.output_dir / name) for name in ("rows.jsonl", "inputs.jsonl", "summary.json")}}
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    doc = ["# 固定消息前缀的 mapper 执行边界回放", "",
        "该实验将每个已保存 assistant 工具调用的消息前缀固定，使用真实 AgentDojo Banking v1.2.2 工具 schema 和 CLAFR `_build_evidence` 重建一份证据。同一动作、同一证据、同一基础 PolicyCompiler 分别进入 no mapper 和 v3 roles-only mapper。这里没有调用 API，也没有执行工具或反事实计算任务 utility。", "",
        f"代码版本：`{summary['code_commit']}`。输入 {len(source_files)} 条 episode，发现 {summary['saved_actions']} 次 saved calls，成功比较 {summary['compared_actions']} 次。异常调用单列，不算 mapper 语义失败。", "",
        "| 来源 | 保存调用 | 可比调用 | 判决差异 | 特征差异 | margin 差异 | constraint 差异 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for name, item in summary["by_source_run"].items():
        doc.append(f"| `{name}` | {item['saved_actions']} | {item['compared_actions']} | {item['decision_disagreements']} | {item['feature_disagreements']} | {item['margin_disagreements']} | {item['constraint_disagreements']} |")
    doc += ["", f"状态计数：`{json.dumps(summary['statuses'], ensure_ascii=False)}`。", "",
        f"允许/阻断配对：`{json.dumps(summary['decision_pairs'], ensure_ascii=False)}`。数值容差 {EPSILON:g}。", "",
        f"历史日志核验（各 equal 字段值是 mismatch 数，不是 match 数）：`{json.dumps(summary['historical_fidelity'], ensure_ascii=False)}`。", "",
        "## 重建边界", "",
        "原始 run 没有保存完整的私有 hidden provenance ledger、原始未投影 tool output 和 opaque binding。默认按 saved tool content 回收 hidden blocks，并按 adapter 的去重、截断顺序重建可见部分；两比较分支共享这份证据。原日志只保存六项特征、decision、execution margin 和 violated constraints，故历史核验全部一致也不能证明全部隐藏状态已经还原。", "",
        "本实验只测试这些固定边界的表示和执行判定。后续消息永远使用原保存轨迹，不会因回放分支改变而重规划；因此不能据此声称端到端 utility 无退化、修复保持原始效果或一般安全保证。repair 只记录本地生成候选，未验证最终效果。", "",
        "`rows.jsonl` 包含两组完整数值特征、margin、constraint、role trace 及 parity；`inputs.jsonl` 保存共享 action/evidence 快照；`manifest.json` 保存全部 source trace、adapter、输入 artifact 和 code hashes。运行前后会校验文件未改变。", "",
        "## 复现", "", "```bash", f"cd '{ROOT}'", ".venv/bin/python scripts/replay_agentdojo_mapper_boundary.py", "```", "",
        "若需检查隐藏 ledger 回收假设，可另用 `--hidden-ledger empty --output-dir results/summaries/agentdojo_mapper_boundary_replay_empty --doc docs/experiments/NAACL_mapper_boundary_replay_empty_ZH.md`；这仍是受限的 saved-prefix replay，不能当作原始环境完整重放。", ""]
    args.doc.parent.mkdir(parents=True, exist_ok=True)
    args.doc.write_text("\n".join(doc), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in {"by_source_run", "limitations"}}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
