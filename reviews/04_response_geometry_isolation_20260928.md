# Response to R1.2 / R2.1 / AI.W3 — geometric constraints vs. threshold rules (2026-09-28, rev. 2)

Reviewer-facing text. Decision recorded by the authors on 2026-09-28: this material goes
into the rebuttal / revision response and the appendix. **Main-paper Table 3 is left
unchanged.**

Reproduce every number below:

```bash
PYTHONPATH=src python3 scripts/geometry_isolation_ifelse_ablation.py
PYTHONPATH=src python3 scripts/verify_geometry_isolation_claims.py   # every check must pass
```

Artifacts: `results/summaries/geometry_isolation_ifelse_ablation_v2/`,
analysis in `docs/experiments/CLAFR_几何与规则隔离消融_20260928_ZH.md`.

---

## 1. What the reviewers asked

- **R1.2** (`reviews/01_official_nxgr/review_bilingual.md`): "The underlying decision is a
  set of threshold checks ... could be implemented as plain rule-based predicates without
  any halfspace or norm formulation. The ablation section does not replace them with
  equivalent non-geometric predicates."
- **R2.1** (`reviews/02_official_nr4b/review_bilingual.md`): "report ... equivalent rule
  based, flat threshold, and no geometry controls using the same rule set."
- **AI.W3** (`reviews/03_ai_review/review_bilingual.md`): "the ASR increase from 0 to 16.7
  percent cannot establish that geometry, rather than removal of the underlying policy
  checks, causes the security difference."

All three are correct that the previous ablation did not isolate the representation. We
have now run the controls they asked for. Auditing the code in order to build them surfaced
something the submission should have stated outright: **the repository contains two
runtimes.** Section 2 says which one produced which numbers, because that determines how
far the concession in Section 3 reaches.

## 2. Two runtimes, and which one the ablation uses

| | `src/clafr` | `src/geoconstraints` |
|---|---|---|
| Feature space | **45** coordinates | 52 structured + 64 semantic-hash = **116** |
| Compiler | `PolicyCompiler` | `ConstraintCompiler` |
| Used by | `clafr_defense.py:29` (AgentDojo), `run_asb_clafr_agent_score.py:570` (ASB) — **every number reported in the paper** | the `policy_variants.py` arms — **the new isolation study below** |
| Boolean verifier in the decision path | **none** | `verifier.py:1371`, called at `policy.py:142` |

In `clafr`, feasibility is exactly `all(margin.slack >= 0 for margin in margins if not
margin.soft)` (`selector.py:80-81`). `clafr.HardVerifier` does exist, but its own docstring
calls it "a deliberately flat verifier baseline" and it has **no call sites anywhere in the
repository**. The hard geometry that decides every reported result is:

| Shape | Count | Widest |
|---|---:|---|
| Axis-aligned facet | 1 (`schema_complete`) | 1 term |
| Oblique facet, mixed-sign fractional weights | 8 | **14 terms** (`trusted_action_support`, bound 0.35) |
| Second-order cone `‖W_r r‖₂ ≤ β + w_cᵀc` | 4 | 8 risk + 8 credit terms |
| *soft*, can only abstain, never block | 1 (`confidence_floor`) | 3 terms |

So **12 of the 13 hard constraints are not per-coordinate thresholds.** Which of them are
*active* is evidence- and text-conditioned (`compiler.py:194-211`: the untrusted-control
group fires on `has_untrusted_evidence` or injection keywords, each cone on its own policy
keyword set) — that gating is the state-conditioning the paper describes.

Counted statically from `clafr/compiler.py`; `src/clafr` requires Python ≥ 3.10 and was not
executed here, so this is a source reading, not a measurement.

The new isolation study runs on `geoconstraints`, because that is where the repository
already contains a sanctioned per-coordinate control. **This is a limitation, not a
detail**, and Section 6 states it as one.

### Controls added

All arms share the frozen policy text, the same feature lifting, the same evidence
projection and the same case set. **Only the decision representation changes.** No geometry
weight, bound or threshold was modified. The composition column is measured from the built
regions and emitted into the JSON, not asserted.

| Arm | Hard geometry (axis / oblique / SOC) | *soft* | Verifier | What it is |
|---|:--:|:--:|:--:|---|
| `axis_additive_only` | 6 / 0 / 0 | 3 | off | independent per-coordinate evidence thresholds (`policy_variants.py:101-160`) — the literal `if dim_i > t_i: return False`, R2's "flat threshold" |
| `verifier_only` | 0 / 0 / 0 (**empty region**) | 0 | on | boolean hard rules only — R1's "plain rule-based predicates", R2's "no geometry" |
| `halfspace_only` | 4 / 0 / 0 | 4 | off | the base compiler's facets. **Its constraint set is identical to `full`'s; the two differ only in `hard_verifier_enabled`.** |
| `convex_region_only` | 3 / 2 / 5 | 3 | off | axis-aligned scope + oblique affine provenance facets + second-order cones |

Case set: 160 deterministic cases (4 action families × 5 risk levels × 8 evidence levels),
16 labelled attack / 24 labelled benign / 120 mixed. Labels pre-registered in `label_rule()`
before any variant was evaluated. Risk-stratified by design — the earlier pilot
(`docs/experiments/CLAFR_审稿补充实验与修改决策_20260721_ZH.md` §3) could not separate the
variants because its 8 cases saturated at 100/0/100.

## 3. Concession, scoped precisely

**In the ablation runtime, the reviewers are right on both counts.**

1. With its boolean hard verifier enabled, `verifier_only` — whose feasible region is
   *empty*, zero geometric constraints — reproduces `full`'s decision on **all 160 cases
   (0.0% divergence)**.
2. `full`'s *hard* geometry in that runtime is **4 axis-aligned thresholds at 0.5**, with
   zero oblique facets and zero cones. The conjunctions the reviewer intuits are real: they
   are folded into the lifting stage — `features.py:411` computes
   `irreversible_without_confirmation = irreversible and not confirmation_seen and not
   safe_repair` — so what sits on top of them is a per-coordinate cutoff.

We do not claim, and the revised text will not claim, that this configuration reaches a
different accept/reject decision than an equivalent rule set.

**The scope matters.** The configuration that produced every reported benchmark number is
`clafr`, where there is no boolean verifier in the decision path and 12 of the 13 hard
constraints are oblique facets or second-order cones over continuous coordinates. There the
accept/reject bit is a conjunction of weighted halfspace inequalities and norm inequalities,
not a per-dimension cutoff. We are not arguing the two runtimes are interchangeable. We are
stating which claim survives in which one — and the revision will name the runtime and the
dimension $d$ explicitly, since the paper currently states neither.

## 4. What the controls nevertheless show

Every number in this section is from the `geoconstraints` runtime.

### 4.1 Per-coordinate thresholds are degenerate: perfect security, total utility collapse

With the verifier disabled so that the decision comes only from the region shape:

| Decision representation | Hard geometry | Attack pass | Benign block |
|---|:--:|---:|---:|
| Per-coordinate thresholds (if-else) | 6/0/0 | 0/16 | **24/24** |
| Axis-aligned facets on conjoined coordinates (= `full`'s geometry) | 4/0/0 | 4/16 | 6/24 |
| **Axis-aligned + oblique facets + second-order cones** | 3/2/5 | **2/16** | **6/24** |

The axis-aligned control blocks **every** benign action, uniformly across all four families
(6/6 in each). A constant cutoff per coordinate cannot trade accumulated risk against
partial trusted evidence, so it collapses to deny-everything on any action that requires
evidence. The convex region recovers 18 of 24 benign actions **and** admits fewer attacks
than axis-aligned facets alone (2/16 vs 4/16).

The gain is **concentrated in privacy egress** (attack pass 4/4 → 2/4; the other three
families are unchanged at 0/4). Mechanism: the privacy budget is a joint cone over
disclosure, access, destination, provenance and authorization, so partial evidence can
offset partial risk. We state this as a localized effect and do **not** claim a universal
advantage.

### 4.2 A boolean predicate emits no repair signal

This is structural, not statistical:

| Decision representation | Projection rate | Mean proj. distance | Margin–evidence rank corr. |
|---|---:|---:|---:|
| Boolean hard rules (empty region) | **0.0%** | **0.000** | n/a |
| Per-coordinate thresholds (if-else) | 100.0% | 0.649 | n/a |
| Axis-aligned facets (= `full`'s geometry) | 100.0% | 0.585 | n/a |
| **Axis-aligned + oblique + cones** | 100.0% | **0.811** | **ρ = 0.433** |

On every blocked case the non-geometric control reports projection distance 0.000 — there is
no direction and no magnitude, hence no minimal edit. The convex region yields a non-zero
minimal-edit direction on 100% of blocked cases, and its signed margin rises with
accumulated trusted evidence (Spearman ρ = 0.433 — a positive rank association, **not**
monotonicity). Minimal-edit repair is what converts a blocked action into an admissible one
rather than merely rejecting it, and it has no threshold-rule analogue.

The axis-aligned arms project too — they are halfspaces — but their margins do not vary
with evidence strength, so ρ is undefined: a per-coordinate cutoff yields the same edit
regardless of how much trusted evidence the action carries.

## 5. How this relates to Table 3 (which we are not changing)

AI.W3 is right, and the code shows it more concretely than our original text did.

Table 3's `w/o Geometric Constraints` is produced by `enable_dynamic_geometry=False`, which
cascades (`clafr_defense.py:499-556`):

- `enable_semantic_facets=False` → the 6 oblique semantic facets removed (`:60-178`)
- `enable_confidence_floor=False` → the soft facet removed (no decision effect: it is soft)
- `enable_untrusted_geometry=False` → the 2 untrusted-control facets and their cone removed
  (`:194-205`)
- privacy / financial / state-write budgets `False` → the remaining 3 cones removed
  (`:206-211`)
- the compiler is therefore left emitting **only `schema_complete`**, a single axis-aligned
  facet
- `enable_geometry_conditioned_observation=False`, and untrusted provenance blocks are no
  longer passed into the evidence (`:589`) — so **risk-aware observation quarantine is
  removed together with the geometry**

Likewise `w/o Action–Evidence Lifting` (`:622-636`) skips the selector entirely and falls
back to a bare schema check (tool registered + required arguments non-empty), so that row
removes lifting, geometry **and** repair at once — which is why it *raises* utility to
91.5/85.3 while leaking 0.7% ASR.

So Table 3 is a **module-level, end-to-end** ablation: its ASR measures the cost of losing
the region, the margins, the projection, the repair feedback *and* the provenance quarantine
together, at the trajectory level. The table in §4 is a **representation-level,
decision-level** isolation: the module stays, only the shape of the decision boundary
changes. These measure different quantities and both are correct in their own scope.
AI.W3's concern was that Table 3 alone could not attribute the effect to geometry rather
than to removed policy checks — the cascade above confirms that it cannot, which is exactly
why the representation-level control is needed *in addition*, not as a replacement. The
revised text will state both the distinction and the cascade.

## 6. Limits we will state in the paper

1. **Two runtimes.** The isolation study runs on `src/geoconstraints` (116 coordinates); the
   reported benchmark numbers come from `src/clafr` (45 coordinates). They share the frozen
   policy text and the observation projector, not the feature space or the compiler. No
   number in §4 is a measurement of the configuration that produced Tables 1–3, and none is
   presented as one.
2. **Offline and decision-level.** No agent trajectories, so **no** end-task AgentDojo/ASB
   utility or ASR is claimed from this study.
3. n is small (16 attack / 24 benign). Counts are exact; no significance test is claimed.
   The load-bearing argument in §4.2 is deterministic, not sampling-dependent.
4. We do **not** claim mixed geometry outperforms single-shape geometry. The 20260721 pilot
   found no such difference, and this study independently reproduces that:
   `convex_region_only` is at least as good as `full` here. The claim is narrower — a convex
   region outperforms axis-aligned thresholds and boolean rules on utility preservation and
   repair.
5. **Unwired code disclosed.** `policy_variants._oblique_dynamic_halfspaces` (`:163-304`) is
   not wired into any variant, yet its docstring says "Full method", which is wrong. It is
   retained in the tree; the docstring will be corrected to state that it is unwired, and
   nothing in the paper or in this response cites it as evidence.
6. The paper never states $d$, never mentions the soft/hard distinction, and defines $M_t$
   as the minimum over all active margins while the implementation excludes soft constraints
   and the `schema_complete` facet (`clafr_defense.py:308-322`). All three will be stated.

## 7. Revised claim (proposed wording)

> In the configuration evaluated on AgentDojo and ASB, feasibility is decided by the
> feasible region alone — there is no rule layer in the decision path. Of the thirteen hard
> constraints the compiler instantiates, one is an axis-aligned schema facet and the other
> twelve are oblique halfspaces with mixed-sign fractional weights, or second-order cones
> over continuous action–evidence coordinates; which of them are active is conditioned on
> the current evidence. A per-coordinate threshold formulation of the same policy is not
> merely an alternative encoding: it reaches comparable security only by blocking every
> evidence-requiring action, and it emits no repair direction that grades with accumulated
> evidence. Where we do pair a region with a boolean verifier, we report honestly that the
> verifier alone reproduces the decision — and that configuration is not the one whose
> results we report.

## 8. Paste-ready AAAI table

```latex
\begin{table*}[t]
\centering
\small
\setlength{\tabcolsep}{4pt}
\begin{tabular}{lcccccc}
\toprule
Decision representation & Hard geom.\ (ax/obl/SOC) & Verifier & Atk.\ pass & Ben.\ block & Proj.\ dist. & Margin $\rho$ \\
\midrule
Boolean hard rules (empty region) & 0/0/0 & on & 4/16 & 18/24 & 0.000 & n/a \\
\midrule
Per-coordinate thresholds (if-else) & 6/0/0 & off & 0/16 & 24/24 & 0.649 & n/a \\
Axis-aligned facets on conjoined coordinates & 4/0/0 & off & 4/16 & 6/24 & 0.585 & n/a \\
\textbf{Axis-aligned + oblique facets + cones} & \textbf{3/2/5} & off & \textbf{2/16} & \textbf{6/24} & \textbf{0.811} & \textbf{0.433} \\
\bottomrule
\end{tabular}
\caption{Representation-level geometry isolation, run on the \texttt{geoconstraints} runtime
(116 coordinates: 52 structured, 64 semantic-hash). All arms share the frozen policy text,
feature lifting and evidence projection; only the decision representation changes, and no
weight, bound or threshold was modified. ``Hard geometry'' counts the constraints that can
block, measured from the built regions; soft dense-semantic boundaries are excluded because
they can only trigger abstention. The top row keeps the boolean hard verifier enabled and is
separated by a midrule because its decision is produced by the verifier rather than by a
region: with the verifier on, an empty feasible region reproduces the full configuration's
decision on all 160 cases, and that configuration's own hard geometry is four axis-aligned
thresholds. The lower three rows disable the verifier so the decision comes only from the
region shape, which is what makes them mutually comparable; the second of them is therefore
the full configuration's geometry evaluated without its rule layer. Attack pass and benign
block are exact counts over a pre-registered, risk-stratified 160-case isolation set
evaluated offline at the decision level (no agent trajectories), so no end-task utility or
ASR is claimed. Projection distance is the mean minimal-edit norm over blocked cases; margin
$\rho$ is the Spearman correlation between evidence strength and signed margin, undefined
(n/a) when the margin does not vary. Per-coordinate thresholds buy perfect security at total
utility collapse and, like the boolean rules, give a margin that does not grade with
evidence. The benchmark results in Tables 1--3 come from a different runtime
(\texttt{clafr}, 45 coordinates) whose decision path contains no boolean verifier and whose
hard geometry is eight oblique facets plus four second-order cones.}
\label{tab:geometry-isolation}
\end{table*}
```
