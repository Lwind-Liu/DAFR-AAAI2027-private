from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


MODEL = "deepseek-v4-flash"
GEOMETRY_NAMES = {
    "clafr": "Full CLAFR (halfspaces + cones)",
    "clafr_geometry_halfspace_only": "Halfspace only",
    "clafr_geometry_cone_only": "Risk-cone only",
    "clafr_geometry_schema_only": "Schema-only gate",
}


def load_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in root.rglob("*.json"):
        if path.name.endswith("manifest.json") or path.name.endswith("summary.json"):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or not payload.get("pipeline_name"):
            continue
        pipeline = str(payload["pipeline_name"])
        method = pipeline.split("/", 1)[1] if "/" in pipeline else "no_defense"
        rows.append(
            {
                "method": method or "no_defense",
                "suite": str(payload.get("suite_name")),
                "attack": str(payload.get("attack_type") or "clean"),
                "utility": bool(payload.get("utility")),
                "security": bool(payload.get("security")),
                "error": payload.get("error"),
                "certificates": payload.get("clafr_certificates") or [],
                "path": str(path),
            }
        )
    return rows


def certificate_margins(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    values: dict[str, list[float]] = {"allowed": [], "blocked": []}
    for row in rows:
        for cert in row["certificates"]:
            value = cert.get("execution_margin") if isinstance(cert, dict) else None
            if isinstance(value, (int, float)):
                decision = cert.get("decision")
                feasible = cert.get("feasible")
                if feasible is True or (feasible is None and decision == "ALLOW"):
                    values["allowed"].append(float(value))
                elif feasible is False or (feasible is None and decision == "BLOCK_OR_CLARIFY"):
                    values["blocked"].append(float(value))
    return values


def geometry_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for method, label in GEOMETRY_NAMES.items():
        selected = [row for row in rows if row["method"] == method]
        clean = [row for row in selected if row["attack"] == "clean"]
        attack = [row for row in selected if row["attack"] != "clean"]
        margins = certificate_margins(selected)
        allowed_mean = sum(margins["allowed"]) / len(margins["allowed"]) if margins["allowed"] else None
        blocked_mean = sum(margins["blocked"]) / len(margins["blocked"]) if margins["blocked"] else None
        output.append(
            {
                "method": label,
                "method_key": method,
                "clean_cases": len(clean),
                "attack_cases": len(attack),
                "clean_utility": sum(row["utility"] for row in clean) / len(clean) if clean else None,
                "static_asr": sum(row["security"] for row in attack) / len(attack) if attack else None,
                "attack_utility": sum(row["utility"] for row in attack) / len(attack) if attack else None,
                "allowed_signed_margin": allowed_mean,
                "blocked_signed_margin": blocked_mean,
                "margin_separation": (
                    allowed_mean - blocked_mean
                    if allowed_mean is not None and blocked_mean is not None
                    else None
                ),
                "allowed_margin_n": len(margins["allowed"]),
                "blocked_margin_n": len(margins["blocked"]),
                "allowed_sign_errors": sum(value < 0 for value in margins["allowed"]),
                "blocked_sign_errors": sum(value >= 0 for value in margins["blocked"]),
                "errors": sum(row["error"] is not None for row in selected),
                "complete": len(clean) == 4 and len(attack) == 4,
            }
        )
    return output


def adaptive_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["method"], row["attack"])].append(row)
    output: list[dict[str, Any]] = []
    for method in ("no_defense", "clafr"):
        selected = [row for row in rows if row["method"] == method]
        output.append(
            {
                "method": "No Defense" if method == "no_defense" else "CLAFR",
                "method_key": method,
                "cases": len(selected),
                "adaptive_asr": sum(row["security"] for row in selected) / len(selected) if selected else None,
                "attack_utility": sum(row["utility"] for row in selected) / len(selected) if selected else None,
                "errors": sum(row["error"] is not None for row in selected),
                "complete": len(selected) == 4,
                "per_attack": {
                    attack: {
                        "asr": sum(row["security"] for row in items) / len(items),
                        "utility": sum(row["utility"] for row in items) / len(items),
                    }
                    for (group_method, attack), items in sorted(grouped.items())
                    if group_method == method
                },
            }
        )
    return output


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    flat = [{key: value for key, value in row.items() if key != "per_attack"} for row in rows]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)


def fmt(value: Any) -> str:
    return "N/A" if value is None else f"{100 * float(value):.1f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--geometry-root", type=Path, required=True)
    parser.add_argument("--adaptive-root", type=Path, required=True)
    args = parser.parse_args()

    geometry = geometry_summary(load_rows(args.geometry_root))
    adaptive = adaptive_summary(load_rows(args.adaptive_root))
    payload = {
        "schema": "clafr-review-pilots-summary-v1",
        "status": "diagnostic_only",
        "model": MODEL,
        "geometry_isolation": geometry,
        "adaptive_stress": adaptive,
    }
    output_root = args.geometry_root.parent / "clafr_review_pilots_20260721"
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "pilot_summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(output_root / "geometry_isolation.csv", geometry)
    write_csv(output_root / "adaptive_stress.csv", adaptive)

    lines = [
        "# CLAFR Review Pilots",
        "",
        "Diagnostic-only fixed pilot; not a paper main-table result.",
        "",
        "## Geometry isolation",
        "",
        "Signed margin is the minimum hard-constraint slack grouped by geometric feasibility: feasible actions should be non-negative and infeasible actions negative.",
        "",
        "| Boundary | Clean Utility | Static ASR | Attack Utility | Allowed Margin | Blocked Margin | Separation | Margin N (A/B) | Sign Errors | Cases | Complete |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for row in geometry:
        allowed = row["allowed_signed_margin"]
        blocked = row["blocked_signed_margin"]
        separation = row["margin_separation"]
        lines.append(
            f"| {row['method']} | {fmt(row['clean_utility'])} | {fmt(row['static_asr'])} | "
            f"{fmt(row['attack_utility'])} | {'N/A' if allowed is None else f'{allowed:+.3f}'} | "
            f"{'N/A' if blocked is None else f'{blocked:+.3f}'} | "
            f"{'N/A' if separation is None else f'{separation:.3f}'} | "
            f"{row['allowed_margin_n']}/{row['blocked_margin_n']} | "
            f"{row['allowed_sign_errors']}/{row['blocked_sign_errors']} | "
            f"{row['clean_cases']}/{row['attack_cases']} | {'yes' if row['complete'] else 'no'} |"
        )
    lines += [
        "",
        "## Adaptive stress",
        "",
        "| Method | Adaptive ASR | Attack Utility | Cases | Complete |",
        "|---|---:|---:|---:|:---:|",
    ]
    for row in adaptive:
        lines.append(
            f"| {row['method']} | {fmt(row['adaptive_asr'])} | {fmt(row['attack_utility'])} | "
            f"{row['cases']} | {'yes' if row['complete'] else 'no'} |"
        )
    (output_root / "pilot_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if all(row["complete"] and row["errors"] == 0 for row in [*geometry, *adaptive]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
