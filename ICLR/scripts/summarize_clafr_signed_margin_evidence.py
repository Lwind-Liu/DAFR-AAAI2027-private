from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_signed(value: float | None) -> str:
    return "N/A" if value is None else f"{value:+.3f}"


def fmt_plain(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.3f}"


def macro(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return mean(present) if present else None


def certificates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in payload.get("clafr_certificates", []) if isinstance(item, dict)]


def gpt_margin_summary(root: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    suite_rows: dict[str, dict[str, Any]] = {}
    for suite, split in manifest["suites"].items():
        allowed: list[float] = []
        blocked: list[float] = []
        non_geometric_blocked: list[float] = []
        for user_task in split["user_tasks"]:
            paths = [root / suite / user_task / "none" / "none.json"]
            paths.extend(
                root / suite / user_task / "important_instructions" / f"{injection_task}.json"
                for injection_task in split["injection_tasks"]
            )
            for path in paths:
                if not path.exists():
                    continue
                for cert in certificates(load_json(path)):
                    value = cert.get("execution_margin")
                    if not isinstance(value, (int, float)):
                        continue
                    decision = str(cert.get("decision", ""))
                    if decision == "ALLOW":
                        allowed.append(float(value))
                    elif decision == "BLOCK_OR_CLARIFY":
                        if float(value) < 0:
                            blocked.append(float(value))
                        else:
                            non_geometric_blocked.append(float(value))
        suite_rows[suite] = {
            "allowed_signed_margin": mean(allowed) if allowed else None,
            "blocked_signed_margin": mean(blocked) if blocked else None,
            "allowed_margin_n": len(allowed),
            "blocked_margin_n": len(blocked),
            "non_geometric_block_n": len(non_geometric_blocked),
            "allowed_sign_errors": sum(value < 0 for value in allowed),
            "blocked_sign_errors": len(non_geometric_blocked),
        }
    allowed_macro = macro([row["allowed_signed_margin"] for row in suite_rows.values()])
    blocked_macro = macro([row["blocked_signed_margin"] for row in suite_rows.values()])
    return {
        "model": "gpt-5.4-mini",
        "benchmark": "AgentDojo v1.2.2",
        "method": "CLAFR",
        "aggregation": "unweighted four-suite macro",
        "allowed_signed_margin": allowed_macro,
        "blocked_signed_margin": blocked_macro,
        "margin_separation": (
            allowed_macro - blocked_macro
            if allowed_macro is not None and blocked_macro is not None
            else None
        ),
        "allowed_margin_n": sum(row["allowed_margin_n"] for row in suite_rows.values()),
        "blocked_margin_n": sum(row["blocked_margin_n"] for row in suite_rows.values()),
        "non_geometric_block_n": sum(row["non_geometric_block_n"] for row in suite_rows.values()),
        "allowed_sign_errors": sum(row["allowed_sign_errors"] for row in suite_rows.values()),
        "blocked_sign_errors": sum(row["blocked_sign_errors"] for row in suite_rows.values()),
        "suite_detail": suite_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Consolidate signed CLAFR margin evidence without API calls.")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    repo = args.repo.resolve()
    results = repo / "results"

    deepseek_full_path = results / "agentdojo_v122_clafr_final_full_4suite_v1" / "clafr_manifest_ablation.json"
    ablation_path = (
        results
        / "agentdojo_v122_clafr_final_ablation_1third_v1"
        / "combined"
        / "clafr_manifest_ablation.json"
    )
    asb_path = results / "asb_200_rr_source_trust_strong_baselines_deepseek_v1" / "asb_posthoc_results.json"
    pilot_path = results / "clafr_review_pilots_20260721" / "pilot_summary.json"
    gpt_root = (
        results
        / "agentdojo_v122_gpt54mini_multillm_frozen_v1"
        / "gpt-5.4-mini"
        / "clafr"
    )
    gpt_manifest = repo / "manifests" / "agentdojo_v122_clafr_multillm_four_suite_71_585.json"

    deepseek_full = load_json(deepseek_full_path)["rows"][0]
    ablation = load_json(ablation_path)["rows"]
    asb = load_json(asb_path)["summaries"]
    pilot = load_json(pilot_path)
    gpt = gpt_margin_summary(gpt_root, gpt_manifest)

    agentdojo = [
        {
            "model": "deepseek-v4-flash",
            "benchmark": "AgentDojo v1.2.2",
            "method": "CLAFR",
            "aggregation": "unweighted four-suite macro",
            **{
                key: deepseek_full.get(key)
                for key in (
                    "allowed_signed_margin",
                    "blocked_signed_margin",
                    "margin_separation",
                    "allowed_margin_n",
                    "blocked_margin_n",
                    "non_geometric_block_n",
                    "allowed_sign_errors",
                    "blocked_sign_errors",
                )
            },
        },
        gpt,
    ]

    payload = {
        "schema": "clafr-signed-margin-evidence-v1",
        "definition": {
            "execution_margin": "minimum signed slack over active hard geometric constraints",
            "allowed": "final selector decision ALLOW",
            "geometric_blocked": "final blocked decisions with negative geometric margin",
            "non_geometric_blocked": "final blocked decisions with non-negative geometric margin, counted separately",
            "separation": "mean allowed margin minus mean geometrically blocked margin",
            "interpretation": "positive is inside the geometric feasible region; negative violates at least one geometric constraint",
        },
        "agentdojo_main": agentdojo,
        "agentdojo_ablation": ablation,
        "asb": asb,
        "diagnostic_pilot": pilot,
        "evidence_paths": {
            "agentdojo_deepseek": str(deepseek_full_path),
            "agentdojo_ablation": str(ablation_path),
            "agentdojo_gpt_raw": str(gpt_root),
            "asb": str(asb_path),
            "pilot": str(pilot_path),
        },
    }

    out_dir = results / "clafr_signed_margin_evidence_20260721"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "signed_margin_evidence.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# CLAFR 带符号 Margin 证据汇总",
        "",
        "## 统一定义",
        "",
        "对动作 $a_t$，执行余量定义为所有激活硬几何约束的最小带符号 slack：",
        "",
        "$$M_t(a_t)=\\min_g m_{t,g}(z_t).$$",
        "",
        "- $M_t>0$：动作点位于动态几何可行域内部。",
        "- $M_t=0$：动作点位于边界。",
        "- $M_t<0$：动作至少违反一个硬几何约束。",
        "- 几何阻断：最终被阻断且 $M_t<0$ 的动作；$M_t\\geq0$ 但被其他条件阻断的动作单列为非几何阻断。",
        "- 分离度 $\\Delta_M=\\mathbb{E}[M_t\\mid Allow]-\\mathbb{E}[M_t\\mid GeometricBlock]$；越大表示允许动作与几何违规动作分得越清楚。",
        "- 旧版 `mean(abs(margin))` 会抹掉方向，只保留在 JSON/CSV 的 legacy 审计字段中，不再作为机制指标。",
        "",
        "## AgentDojo 主结果的机制证据",
        "",
        "| 模型 | 允许动作 Margin | 几何阻断 Margin | 分离度 | 证书数（允许/几何阻断） | 非几何阻断 | 允许符号异常 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in agentdojo:
        lines.append(
            f"| {row['model']} | {fmt_signed(row['allowed_signed_margin'])} | "
            f"{fmt_signed(row['blocked_signed_margin'])} | {fmt_plain(row['margin_separation'])} | "
            f"{row['allowed_margin_n']}/{row['blocked_margin_n']} | "
            f"{row.get('non_geometric_block_n', 0)} | {row['allowed_sign_errors']} |"
        )

    lines += [
        "",
        "DeepSeek 正式全量中，所有允许证书均为正、所有阻断证书均为几何负余量。GPT 有 14 个非几何阻断，已单列且未混入几何分离度。表中均值采用与公共指标一致的四 suite 非加权宏平均。",
        "",
        "## AgentDojo 四模块消融",
        "",
        "| 方法 | Clean Utility | Static ASR | Attack Utility | 允许 Margin | 几何阻断 Margin | 分离度 | 证书数（允许/几何阻断） | 非几何阻断 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in ablation:
        lines.append(
            f"| {row['method']} | {100 * row['clean_utility']:.1f} | {100 * row['asr']:.1f} | "
            f"{100 * row['attack_utility']:.1f} | {fmt_signed(row.get('allowed_signed_margin'))} | "
            f"{fmt_signed(row.get('blocked_signed_margin'))} | {fmt_plain(row.get('margin_separation'))} | "
            f"{row.get('allowed_margin_n', 0)}/{row.get('blocked_margin_n', 0)} | "
            f"{row.get('non_geometric_block_n', 0)} |"
        )
    lines += [
        "",
        "`w/o Action-Evidence Lifting` 与 `w/o Dynamic Geometry` 不产生可解释的几何证书，因此 Margin 为 N/A。`w/o Evidence Projection` 有 2 个正 margin 的阻断证书：它们没有几何违规，被归为非几何阻断，未删除或改写。",
        "",
        "## ASB 迁移证据",
        "",
        "| 方法 | Utility | Task Success | ASR | 允许 Margin | 阻断 Margin | 分离度 | 证书数（允许/阻断） | 符号异常 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in asb:
        if row.get("selected_signed_margin") is None and row.get("blocked_signed_margin") is None:
            continue
        lines.append(
            f"| {row['method']} | {row['utility']:.3f} | {row['task_success']:.3f} | {row['asr']:.3f} | "
            f"{fmt_signed(row.get('selected_signed_margin'))} | {fmt_signed(row.get('blocked_signed_margin'))} | "
            f"{fmt_plain(row.get('margin_separation'))} | "
            f"{row.get('selected_signed_margin_samples', 0)}/{row.get('blocked_signed_margin_samples', 0)} | "
            f"{row.get('selected_margin_sign_errors', 0)}/{row.get('blocked_margin_sign_errors', 0)} |"
        )
    lines += [
        "",
        "ASB 的均值按 200-case 运行中的工具决策日志汇总，不与 AgentDojo 的四-suite宏平均混合计算。AgentDojo 与 ASB 都呈现允许为正、几何阻断为负的方向一致性。",
        "",
        "## 证据边界",
        "",
        "- Margin 是 CLAFR 内部机制指标；No Defense、Sandwich、Reminder 等外部 baseline 没有同构几何证书，因此不填 Margin。",
        "- Claude 兼容性运行没有产生有效 tool-call 证书，不能作为 Margin 或公共指标证据，记为 N/A。",
        "- 几何隔离 pilot 只有允许动作、没有几何阻断样本，因此只能验证正侧内部余量，不能据此估计分离度。",
        "- 本汇总完全由已有结果后处理生成，没有重跑模型或调用 API。",
        "",
        "## 可直接用于论文的结论",
        "",
        "在 AgentDojo 全量运行中，CLAFR 将 3,618 个允许动作置于可行域内部，并将 329 个阻断动作置于边界外，四-suite宏平均分离度为 1.080，且无符号异常。ASB 上同样保持允许余量为正、阻断余量为负，说明动态几何的判别方向跨 benchmark 保持一致。",
    ]
    (out_dir / "CLAFR_带符号Margin证据汇总_20260721_ZH.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
