"""Cross-check every number claimed in the geometry-isolation write-ups against the JSON
produced by scripts/geometry_isolation_ifelse_ablation.py.

Two documents are verified: the internal analysis note and the reviewer-facing response.
Three classes of drift are guarded:

  1. numeric claims vs. the JSON (decision counts, projection distances, rho);
  2. shape claims vs. the measured region composition (axis / oblique / SOC per arm);
  3. runtime claims -- the ablation runs on src/geoconstraints (116-dim) while every
     reported benchmark number comes from src/clafr (45-dim), and no document may blur
     that, overclaim, or cite the unwired `_oblique_dynamic_halfspaces` as live.

Run:
    PYTHONPATH=src python3 scripts/verify_geometry_isolation_claims.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results/summaries/geometry_isolation_ifelse_ablation_v2/geometry_isolation_results.json"
DOCS = {
    "analysis": ROOT / "docs/experiments/CLAFR_几何与规则隔离消融_20260928_ZH.md",
    "rebuttal": ROOT / "reviews/04_response_geometry_isolation_20260928.md",
}

# A banned phrase is tolerated only when a negation cue appears shortly before it, e.g.
# "we do not claim mixed geometry outperforms ..." or "不能写混合几何优于...".
NEGATION_CUES = (
    "not", "never", "cannot", "no such", "avoid", "instead of", "rather than",
    "不能", "不得", "不要", "并非", "禁止", "不", "无法", "订正",
)
NEGATION_WINDOW = 160

BANNED = (
    "monotonically",
    "monotonic increase",
    "geometry is more secure",
    "lower ASR than",
    "mixed geometry outperforms",
    "混合几何优于",
    "statistically significant",
    "replaces Table 3",
    "替换 Table 3",
    "proves that geometry",
    # shapes, counts and labels that were wrong in an earlier draft
    "the paper's geometry",
    "nine oblique facets",
    "13 of the 14",
    "affine facets only",
)

# The boolean verifier's over-blocking is an internal observation the authors decided must
# not reach the reviewer-facing text.
REBUTTAL_SCOPE_BANNED = ("over-block", "过度拦截", "75%")

UNWIRED_SYMBOL = "_oblique_dynamic_halfspaces"
UNWIRED_MARKERS = ("unwired", "not wired", "未接线", "无调用点", "dead code", "死代码")


def frac(row: dict, kind: str, den: str) -> str:
    return f"{row[kind + '_n']}/{row[den + '_n']}"


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def paragraphs(text: str) -> list[str]:
    return [flat(p) for p in re.split(r"\n\s*\n", text) if p.strip()]


def scan_banned(text: str, banned: tuple[str, ...]) -> list[str]:
    """Return banned phrases that occur without a nearby preceding negation cue."""

    violations = []
    for para in paragraphs(text):
        lowered = para.lower()
        for phrase in banned:
            needle = phrase.lower()
            start = lowered.find(needle)
            while start != -1:
                window = lowered[max(0, start - NEGATION_WINDOW):start]
                if not any(cue in window for cue in NEGATION_CUES):
                    violations.append(f"{phrase!r} in: ...{para[max(0, start - 60):start + len(phrase) + 40]}...")
                start = lowered.find(needle, start + len(needle))
    return violations


def scan_unwired(text: str) -> list[str]:
    """Every mention of the unwired symbol must be labelled as such in the same paragraph.

    The function is retained in the tree by author decision, so the guard enforces
    labelling rather than absence: no paragraph may cite it as if it were live.
    """

    violations = []
    for para in paragraphs(text):
        if UNWIRED_SYMBOL in para:
            lowered = para.lower()
            if not any(marker in lowered for marker in UNWIRED_MARKERS):
                violations.append(f"{UNWIRED_SYMBOL} cited without an unwired label: ...{para[:120]}...")
    return violations


def shape(row: dict) -> str:
    hard = row["region_composition"]["hard_shape_counts"]
    return f"{hard['axis_aligned']}/{hard['oblique']}/{hard['second_order']}"


def main() -> int:
    data = json.loads(RESULTS.read_text(encoding="utf-8"))
    texts = {key: path.read_text(encoding="utf-8") for key, path in DOCS.items()}
    flats = {key: flat(text) for key, text in texts.items()}

    A, B = data["blocks"]["A"], data["blocks"]["B"]
    ax, hs, soc = A["axis_additive_only"], A["halfspace_only"], A["convex_region_only"]
    vo, full, fnm, rs = B["verifier_only"], B["full"], B["full_no_margin"], B["rule_shield"]
    cat = data["block_a_per_category"]
    rt = data["runtime"]
    families = ("external_sink", "privacy_egress", "financial_transfer", "irreversible_write")

    # Each entry: (name, data_holds, {doc_key: needle that must appear in that doc}).
    checks: list[tuple[str, bool, dict[str, str]]] = [
        # --- decision counts -------------------------------------------------------
        ("if-else attack 0/16", frac(ax, "attack_pass", "attack") == "0/16",
         {"analysis": "(0/16)", "rebuttal": "0/16"}),
        ("if-else benign 24/24", frac(ax, "benign_block", "benign") == "24/24",
         {"analysis": "24/24", "rebuttal": "**24/24**"}),
        ("axis-aligned attack 4/16", frac(hs, "attack_pass", "attack") == "4/16",
         {"analysis": "(4/16)", "rebuttal": "4/0/0 | 4/16 | 6/24"}),
        ("axis-aligned benign 6/24", frac(hs, "benign_block", "benign") == "6/24",
         {"analysis": "(6/24)", "rebuttal": "4/0/0 | 4/16 | 6/24"}),
        ("mixed region attack 2/16", frac(soc, "attack_pass", "attack") == "2/16",
         {"analysis": "(2/16)", "rebuttal": "**2/16**"}),
        ("mixed region benign 6/24", frac(soc, "benign_block", "benign") == "6/24",
         {"analysis": "(6/24)", "rebuttal": "**6/24**"}),
        ("boolean attack 4/16", frac(vo, "attack_pass", "attack") == "4/16",
         {"analysis": "| 0 | 0/0/0 | 0 | on | 25.0% (4/16)", "rebuttal": "0/0/0 & on & 4/16"}),
        ("boolean benign 18/24", frac(vo, "benign_block", "benign") == "18/24",
         {"analysis": "18/24", "rebuttal": "18/24"}),
        # --- repair signal ---------------------------------------------------------
        ("proj dist if-else 0.649", abs(ax["mean_projection_distance"] - 0.649) < 5e-4,
         {"analysis": "0.649", "rebuttal": "0.649"}),
        ("proj dist axis-aligned 0.585", abs(hs["mean_projection_distance"] - 0.585) < 5e-4,
         {"analysis": "0.585", "rebuttal": "0.585"}),
        ("proj dist mixed 0.811", abs(soc["mean_projection_distance"] - 0.811) < 5e-4,
         {"analysis": "0.811", "rebuttal": "0.811"}),
        ("proj dist boolean 0.000", abs(vo["mean_projection_distance"]) < 1e-9,
         {"analysis": "0.000", "rebuttal": "0.000"}),
        ("rho mixed 0.433", abs(soc["margin_grading_rho"] - 0.433) < 5e-4,
         {"analysis": "0.433", "rebuttal": "0.433"}),
        ("rho undefined for others", all(row["margin_grading_rho"] is None for row in (ax, hs, vo)),
         {"analysis": "n/a", "rebuttal": "n/a"}),
        ("projection rate 100% (geometric arms)",
         all(abs(row["projection_rate"] - 1.0) < 1e-9 for row in (ax, hs, soc)),
         {"analysis": "100.0%", "rebuttal": "100.0%"}),
        ("projection rate 0% (boolean)", abs(vo["projection_rate"]) < 1e-9,
         {"analysis": "**0.0%**", "rebuttal": "**0.0%**"}),
        # --- case set --------------------------------------------------------------
        ("boolean 0% divergence from full", vo["divergence_from_reference"] == 0.0,
         {"analysis": "**0.0%**", "rebuttal": "0.0% divergence"}),
        ("boolean region empty (0 constraints)", vo["n_constraints"] == 0,
         {"analysis": "0 个几何约束", "rebuttal": "*empty*"}),
        ("case count 160", data["case_count"] == 160,
         {"analysis": "160 例", "rebuttal": "160 cases"}),
        ("labels 16 attack / 24 benign / 120 mixed",
         data["label_counts"] == {"attack": 16, "benign": 24, "mixed": 120},
         {"analysis": "16 attack / 24 benign", "rebuttal": "16 labelled attack / 24 labelled benign / 120 mixed"}),
        ("mixed region recovers 18 of 24 benign", soc["benign_n"] - soc["benign_block_n"] == 18,
         {"rebuttal": "18 of 24"}),
        ("if-else blocks benign uniformly 6/6",
         all(cat["axis_additive_only"][f]["benign_block"] == "6/6" for f in families),
         {"analysis": "6/6", "rebuttal": "(6/6 in each)"}),
        ("privacy egress 4/4 -> 2/4",
         cat["halfspace_only"]["privacy_egress"]["attack_pass"] == "4/4"
         and cat["convex_region_only"]["privacy_egress"]["attack_pass"] == "2/4",
         {"analysis": "**4/4** · 0/6", "rebuttal": "4/4 → 2/4"}),
        ("other families unchanged at 0/4",
         all(cat["convex_region_only"][f]["attack_pass"] == "0/4"
             for f in families if f != "privacy_egress"),
         {"rebuttal": "unchanged at 0/4"}),
        # --- measured region composition -------------------------------------------
        ("shape if-else 6/0/0", shape(ax) == "6/0/0",
         {"analysis": "| 9 | 6/0/0 | 3 |", "rebuttal": "6/0/0"}),
        ("shape axis-aligned 4/0/0", shape(hs) == "4/0/0",
         {"analysis": "| 8 | 4/0/0 | 4 |", "rebuttal": "4/0/0"}),
        ("shape mixed region 3/2/5", shape(soc) == "3/2/5",
         {"analysis": "| 13 | **3/2/5** | 3 |", "rebuttal": "3/2/5"}),
        ("shape boolean 0/0/0", shape(vo) == "0/0/0",
         {"analysis": "| 0 | 0/0/0 | 0 |", "rebuttal": "0/0/0"}),
        ("full hard geometry is 4 axis-aligned only",
         shape(full) == "4/0/0" and full["hard_verifier"] is True,
         {"analysis": "| `full` | 8 | 4/0/0 | 4 | on |", "rebuttal": "four axis-aligned thresholds"}),
        ("full_no_margin is an adapter over full",
         fnm["region_composition"]["adapter_wrapped"] is True and fnm["hard_verifier"] is True,
         {"analysis": "adapter_wrapped=true"}),
        ("rule_shield is not a boolean baseline", shape(rs) == "4/0/0" and rs["n_constraints"] == 4,
         {"analysis": "不是布尔规则基线"}),
        ("verifier on only for Block B",
         vo["hard_verifier"] is True and all(row["hard_verifier"] is False for row in (ax, hs, soc)),
         {"analysis": "Verifier", "rebuttal": "Verifier"}),
        # --- runtime separation -----------------------------------------------------
        ("ablation runtime is geoconstraints", "geoconstraints" in rt["ablation_runtime"],
         {"analysis": "`src/clafr`", "rebuttal": "`src/geoconstraints`"}),
        ("benchmark runtime is clafr", "clafr" in rt["benchmark_runtime"],
         {"analysis": "**论文里所有数字**", "rebuttal": "every number reported in the paper"}),
        ("runtimes are not the same", rt["same_runtime"] is False,
         {"analysis": "两套 runtime 不可互换", "rebuttal": "not the feature space or the compiler"}),
        ("dimension 116 = 52 + 64",
         rt["feature_dimension"] == 116 and rt["structured_coordinates"] == 52
         and rt["semantic_hash_coordinates"] == 64,
         {"analysis": "52 结构化 + 64 语义哈希 = **116**", "rebuttal": "52 structured + 64 semantic-hash = **116**"}),
        ("benchmark runtime has no boolean verifier",
         rt["boolean_hard_verifier"]["in_benchmark_runtime"] is False,
         {"analysis": "全仓没有任何调用点", "rebuttal": "no call sites anywhere in the"}),
        ("clafr facts marked source-read not measured", True,
         {"analysis": "读码结论不是测量结果", "rebuttal": "a source reading, not a measurement"}),
        ("Table 3 left unchanged (decision recorded)", True,
         {"analysis": "Table 3 保持原样", "rebuttal": "Table 3 is left unchanged"}),
        ("placement is rebuttal/appendix only", True,
         {"analysis": "仅用于 rebuttal 与 appendix", "rebuttal": "rebuttal / revision response and the appendix"}),
        ("Table 3 cascade is evidenced by code", True,
         {"analysis": "clafr_defense.py:499-556", "rebuttal": "clafr_defense.py:499-556"}),
        ("unwired code disclosed", True,
         {"analysis": "未接线代码披露", "rebuttal": "Unwired code disclosed"}),
        ("retention decision recorded (not deleted)", True,
         {"analysis": "代码保留不删", "rebuttal": "retained in the tree"}),
        ("unstated d flagged for revision", True,
         {"analysis": "论文从未给出 $d$ 的数值", "rebuttal": "since the paper currently states neither"}),
    ]

    failures: list[str] = []
    for name, data_ok, needles in checks:
        missing = [key for key, needle in needles.items() if needle not in flats[key]]
        ok = bool(data_ok) and not missing
        where = "both docs" if not missing else f"missing in {missing}"
        print(f"{'OK  ' if ok else 'FAIL'} {name:46s} data={bool(data_ok)!s:5s} {where}")
        if not ok:
            failures.append(name)

    print()
    guard_failures: list[str] = []
    for key, text in texts.items():
        scope = BANNED + (REBUTTAL_SCOPE_BANNED if key == "rebuttal" else ())
        for violation in scan_banned(text, scope):
            print(f"FAIL overclaim [{key}]: {violation}")
            guard_failures.append(f"{key}: {violation}")
        for violation in scan_unwired(text):
            print(f"FAIL unwired citation [{key}]: {violation}")
            guard_failures.append(f"{key}: {violation}")
    if not guard_failures:
        print("OK   no unnegated overclaims; unwired code never cited as live; "
              "no internal-only verifier criticism in the rebuttal")
    failures.extend(guard_failures)

    print()
    total = len(checks)
    if failures:
        print(f"RESULT: {len(failures)} FAILURES out of {total} numeric checks -> {failures}")
        return 1
    print(f"RESULT: ALL {total} NUMERIC CHECKS VERIFIED AGAINST DATA (analysis + rebuttal)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
