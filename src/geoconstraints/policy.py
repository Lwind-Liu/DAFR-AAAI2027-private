from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Sequence

from geoconstraints.compiler import ConstraintCompiler
from geoconstraints.features import FeatureSpace
from geoconstraints.geometry import FeasibleRegion, HalfSpace, cyclic_project
from geoconstraints.schemas import (
    ActionEvaluation,
    ConstraintClause,
    ConstraintCertificate,
    NaturalLanguageConstraint,
    ProjectionCertificate,
    SelectionResult,
    ShieldDecision,
    ToolAction,
    UtilityFn,
)
from geoconstraints.scope import action_scope_terms, clause_applies_to_terms, direct_action_scope_terms
from geoconstraints.text import flatten_value
from geoconstraints.verifier import HardVerifier


def _low_confidence_threshold(clause: ConstraintClause, default_threshold: float) -> float:
    if "requires_unmodeled_workflow" in clause.unsupported_reasons:
        text = clause.text.lower()
        if "can help" in text and "follow" in text and "step" in text:
            return default_threshold
        return max(default_threshold, 0.3)
    return default_threshold


def _action_eval_cache_key(action: ToolAction, utility: float, margin_weight: float) -> tuple[str, str, str, str, str, str, float, float]:
    return (
        action.tool_name,
        action.action_text,
        flatten_value(action.arguments),
        action.context_text,
        flatten_value(action.history),
        flatten_value(action.raw),
        float(utility),
        float(margin_weight),
    )


def _certificate_margin(margin: float, hard_failures: Sequence[object]) -> float:
    severities = [float(getattr(item, "severity", 1.0)) for item in hard_failures]
    if not severities:
        return margin
    return min(margin, -max(severities))


@dataclass
class SemanticGeoConstraintPolicy:
    feature_space: FeatureSpace
    region: FeasibleRegion
    clauses: tuple[ConstraintClause, ...] = ()
    hard_verifier_enabled: bool = True
    disabled_feature_names: tuple[str, ...] = ()
    semantic_abstain_base: float = -0.8
    low_confidence_semantic_threshold: float = -0.1
    _evaluation_cache: dict[tuple[str, str, str, str, str, str, float, float], ActionEvaluation] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def from_constraints(
        cls,
        constraints: Sequence[NaturalLanguageConstraint | str],
        *,
        semantic_dims: int = 256,
    ) -> "SemanticGeoConstraintPolicy":
        normalized = [
            item if isinstance(item, NaturalLanguageConstraint) else NaturalLanguageConstraint(id=f"c{idx}", text=str(item))
            for idx, item in enumerate(constraints)
        ]
        compiler = ConstraintCompiler.default(semantic_dims=semantic_dims)
        compiled = compiler.compile_constraints(normalized)
        halfspaces = tuple(halfspace for item in compiled for halfspace in item.halfspaces)
        clauses = tuple(item.clause for item in compiled)
        return cls(compiler.feature_space, FeasibleRegion(halfspaces), clauses)

    @classmethod
    def from_halfspaces(cls, feature_space: FeatureSpace, halfspaces: Sequence[HalfSpace]) -> "SemanticGeoConstraintPolicy":
        return cls(feature_space, FeasibleRegion(tuple(halfspaces)), ())

    def evaluate(self, action: ToolAction, utility: float = 0.0, margin_weight: float = 0.4) -> ActionEvaluation:
        cache_key = _action_eval_cache_key(action, utility, margin_weight)
        cached = self._evaluation_cache.get(cache_key)
        if cached is not None:
            return replace(cached, action=action)

        vector = self.feature_space.vectorize_action(action)
        if self.disabled_feature_names:
            vector = vector.copy()
            for name in self.disabled_feature_names:
                vector[self.feature_space.feature_index(name)] = 0.0
        all_margins = self.region.margins(vector)
        feature_values = self.feature_space.feature_dict(vector)
        action_terms = action_scope_terms(action)
        direct_action_terms = direct_action_scope_terms(action)
        clause_by_id = {clause.id: clause for clause in self.clauses}
        margins = tuple(
            item
            for item in all_margins
            if item.soft
            or clause_by_id.get(item.constraint_id.rsplit(":", 1)[0]) is None
            or clause_applies_to_terms(
                clause_by_id[item.constraint_id.rsplit(":", 1)[0]],
                action_terms,
                feature_values,
                direct_action_terms=direct_action_terms,
            )
        )
        hard_margins = tuple(item for item in margins if not item.soft)
        soft_margins = tuple(item for item in margins if item.soft)
        hard_feasible = all(item.slack >= -1e-9 for item in hard_margins)
        hard_margin = min((item.normalized_margin for item in hard_margins), default=float("inf"))
        soft_margin = min((item.normalized_margin for item in soft_margins), default=float("inf"))
        margin = min(hard_margin, soft_margin)
        if margin == float("inf"):
            margin = hard_margin if hard_margin != float("inf") else 1.0
        active_hard_ids = {item.constraint_id for item in hard_margins}
        active_hard_constraints = tuple(
            constraint for constraint in self.region.constraints if constraint.id in active_hard_ids and not constraint.soft
        )
        projected = cyclic_project(vector, active_hard_constraints) if active_hard_constraints else vector.copy()
        projection_delta = projected - vector
        projection_distance = float((projection_delta @ projection_delta) ** 0.5)
        projected_margins = tuple(constraint.margin(projected) for constraint in active_hard_constraints)
        projected_margin = min((item.normalized_margin for item in projected_margins), default=margin)
        projection = ProjectionCertificate(
            original_margin=hard_margin if hard_margin != float("inf") else margin,
            projected_margin=projected_margin,
            distance=projection_distance,
            feasible=all(item.slack >= -1e-8 for item in projected_margins),
            active_constraints=tuple(item.constraint_id for item in hard_margins),
            violated_facets=tuple(item.constraint_id for item in hard_margins if item.slack < 0.0),
            projected_features=self.feature_space.feature_dict(projected),
        )

        verifier_results = (
            HardVerifier(self.clauses).verify(
                action,
                feature_values,
                action_terms=action_terms,
            )
            if self.hard_verifier_enabled
            else ()
        )
        failed_verifier = tuple(item for item in verifier_results if not item.passed)
        runtime_unknown_reasons = {
            "amount_unknown",
            "required_argument_unknown",
            "state_requirement_unknown",
            "identity_verification_unknown",
            "source_grounding_unknown",
            "user_intent_unknown",
        }
        unknown_runtime = tuple(item for item in failed_verifier if item.reason in runtime_unknown_reasons)
        hard_verifier_failures = tuple(item for item in failed_verifier if item.reason not in runtime_unknown_reasons)
        identity_repair_enabled = any(clause.required_evidence.identity_required for clause in self.clauses)
        safe_repair_names = (
            "is_user_confirmation_request",
            "is_policy_lookup",
            "is_state_read",
            "is_user_intent_request_action",
            "is_human_escalation",
        )
        safe_repair = any(
            feature_values.get(name, 0.0) > 0.5 for name in safe_repair_names
        ) or (
            identity_repair_enabled and feature_values.get("is_identity_verification_action", 0.0) > 0.5
        ) or (
            feature_values.get("is_redaction_action", 0.0) > 0.5
            and (action.tool_name == "redact_sensitive_info" or ":repair_" in action.id)
        )
        risky_side_effect = any(
            feature_values.get(name, 0.0) > 0.5
            for name in (
                "external_side_effect",
                "irreversibility",
                "is_existing_record_write",
            )
        )
        trusted_repair_evidence = any(
            feature_values.get(name, 0.0) > 0.5
            for name in (
                "trusted_confirmation_seen",
                "trusted_authorization_seen",
                "trusted_identity_seen",
                "trusted_source_grounding_seen",
                "trusted_user_intent_seen",
                "trusted_state_seen",
                "trusted_manager_approval_seen",
            )
        )
        untrusted_repair_without_trust = (
            safe_repair
            and (
                feature_values.get("evidence_from_untrusted_source", 0.0) > 0.5
                or feature_values.get("instruction_in_untrusted_context", 0.0) > 0.5
            )
            and not trusted_repair_evidence
        )
        semantic_margin_by_clause = {
            item.constraint_id.rsplit(":", 1)[0]: item.normalized_margin
            for item in margins
            if item.source == "semantic_boundary"
        }
        relevant_low_confidence_clauses = tuple(
            clause
            for clause in self.clauses
            if clause.parse_confidence < 0.5
            and clause.unsupported_reasons
            and clause_applies_to_terms(clause, direct_action_terms, feature_values)
            and semantic_margin_by_clause.get(clause.id, float("inf"))
            <= _low_confidence_threshold(clause, self.low_confidence_semantic_threshold)
        )

        uncertainty = max((1.0 - clause.parse_confidence for clause in relevant_low_confidence_clauses), default=0.0)
        if unknown_runtime:
            uncertainty = max(uncertainty, 0.5)
        weighted_violation_penalty = sum(max(0.0, -item.normalized_margin) * max(item.severity, 0.05) for item in margins)
        verifier_penalty = sum(item.severity for item in hard_verifier_failures)
        score_margin = margin if margin != float("inf") else 1.0
        score = (
            float(utility)
            + float(margin_weight) * max(score_margin, -1.0)
            - weighted_violation_penalty
            - verifier_penalty
            - 0.2 * projection_distance
            - 0.5 * uncertainty
        )

        repair_hints = tuple(
            dict.fromkeys(
                [
                    *(item.repair_hint for item in margins if item.slack < 0.0 and item.repair_hint),
                    *(item.repair_hint for item in failed_verifier if item.repair_hint),
                    *(
                        "Route risky action to policy review because one or more constraints were semantic-only."
                        for _ in relevant_low_confidence_clauses[:1]
                        if risky_side_effect
                    ),
                ]
            )
        )
        abstain_reason = ""
        if hard_verifier_failures or not hard_feasible:
            decision = ShieldDecision.BLOCK
        elif unknown_runtime:
            decision = ShieldDecision.ABSTAIN
            abstain_reason = ";".join(item.reason for item in unknown_runtime)
        elif untrusted_repair_without_trust:
            decision = ShieldDecision.BLOCK
        elif safe_repair:
            decision = ShieldDecision.REPAIR_ACTION
        elif risky_side_effect and relevant_low_confidence_clauses:
            decision = ShieldDecision.ABSTAIN
            abstain_reason = "low_confidence_policy_clause"
        else:
            max_soft_severity = max((item.severity for item in soft_margins), default=1.0)
            semantic_threshold = self.semantic_abstain_base / max(max_soft_severity, 0.05)
            if soft_margin < semantic_threshold:
                decision = ShieldDecision.ABSTAIN
                abstain_reason = "near_or_outside_soft_semantic_boundary"
            else:
                decision = ShieldDecision.ALLOW
        feasible = decision in {ShieldDecision.ALLOW, ShieldDecision.REPAIR_ACTION}
        missing_evidence = tuple(item.constraint_id for item in unknown_runtime)
        hard_failure_ids = tuple(item.constraint_id for item in hard_verifier_failures)
        violated_facets = tuple(
            dict.fromkeys(
                [
                    *(item.constraint_id for item in hard_margins if item.slack < 0.0),
                    *hard_failure_ids,
                ]
            )
        )
        active_constraints = tuple(
            dict.fromkeys(
                [
                    *(item.constraint_id for item in hard_margins),
                    *(item.constraint_id for item in verifier_results),
                ]
            )
        )
        certificate = ConstraintCertificate(
            decision=decision,
            min_margin=margin,
            certificate_margin=_certificate_margin(margin, hard_verifier_failures),
            active_constraints=active_constraints,
            violated_facets=violated_facets,
            missing_evidence=missing_evidence,
            hard_failures=hard_failure_ids,
            projection=projection,
            uncertainty=uncertainty,
        )
        evaluation = ActionEvaluation(
            action=action,
            feasible=feasible,
            margin=margin,
            score=score,
            utility=float(utility),
            margins=margins,
            feature_values=feature_values,
            decision=decision,
            abstain_reason=abstain_reason,
            repair_hints=repair_hints,
            hard_verifier_results=verifier_results,
            certificate=certificate,
            projection=projection,
        )
        self._evaluation_cache[cache_key] = evaluation
        return evaluation

    def select(
        self,
        actions: Sequence[ToolAction],
        utility_fn: UtilityFn | None = None,
        margin_weight: float = 0.4,
        *,
        selection_strategy: str = "linear_score",
        utility_band_epsilon: float = 0.0,
        allow_repair_actions: bool = True,
        margin_floor: float | None = None,
    ) -> SelectionResult:
        """Select a feasible action with a deterministic safety certificate.

        ``linear_score`` preserves the original behavior: feasible candidates are
        ranked by utility plus a weighted signed margin.

        ``utility_band`` is the legacy paper-facing selector for public utility/JSS
        benchmarks. It first applies the exact same half-space/verifier filter,
        then keeps only selectable actions whose utility is within
        ``utility_band_epsilon`` of the best selectable utility, and finally uses
        certificate margin as the tie-breaker inside that band. This keeps margin
        as the geometric selection signal while preventing a safer-but-much-less
        useful repair/plan from displacing a direct safe action.

        ``robust_interior`` is the contracted DSFR selector. It applies the same
        utility band and then maximizes the normalized minimum active-facet
        margin, independent of the legacy linear ``margin_weight``. ``top1`` and
        ``utility_first`` are causal ablations. ``shuffled_margin`` preserves the
        candidate-pool margin distribution but deterministically rotates margins
        across actions before selection.

        ``boundary_rescue`` preserves the agent's original action whenever that
        action is selectable. Geometry is activated only when the original lies
        outside the feasible region (or fails the hard verifier); the selector
        then chooses the maximum-margin repair inside the frozen utility band.
        This prevents small interior-margin fluctuations from replacing benign
        task-progress actions while retaining geometric action correction at the
        decision boundary.

        ``guarded_interior`` extends boundary rescue to feasible but genuinely
        boundary-sensitive actions.  It replaces a feasible original only when
        another candidate stays inside the same utility band and improves the
        signed certificate margin by at least the width of that band.  The same
        epsilon therefore bounds both tolerated task regret and the minimum
        geometric evidence required to intervene.
        """

        utility_fn = utility_fn or (lambda action: 0.0)
        action_tuple = tuple(actions)
        order = {id(action): idx for idx, action in enumerate(action_tuple)}
        normalized_strategy = selection_strategy.strip().lower().replace("-", "_")
        if normalized_strategy in {"pareto", "safe_utility_band", "lexicographic"}:
            normalized_strategy = "utility_band"
        if normalized_strategy not in {
            "linear_score",
            "score",
            "weighted",
            "utility_band",
            "top1",
            "utility_first",
            "robust_interior",
            "shuffled_margin",
            "boundary_rescue",
            "guarded_interior",
        }:
            raise ValueError(f"unknown selection_strategy: {selection_strategy}")
        if normalized_strategy in {"score", "weighted"}:
            normalized_strategy = "linear_score"
        use_margin_tiebreak = normalized_strategy in {
            "robust_interior",
            "shuffled_margin",
            "boundary_rescue",
            "guarded_interior",
        } or (
            normalized_strategy == "utility_band" and abs(float(margin_weight)) > 1e-12
        )
        epsilon = max(0.0, float(utility_band_epsilon))

        def _order_index(evaluation: ActionEvaluation) -> int:
            return order.get(id(evaluation.action), 0)

        def _certificate_margin_value(evaluation: ActionEvaluation) -> float:
            if evaluation.certificate is not None:
                return float(evaluation.certificate.certificate_margin)
            return float(evaluation.margin)

        def _selectable_key(evaluation: ActionEvaluation) -> tuple[float, float, float, int]:
            if use_margin_tiebreak:
                return (evaluation.score, evaluation.margin, evaluation.utility, -_order_index(evaluation))
            return (evaluation.score, evaluation.utility, 0.0, -_order_index(evaluation))

        selection_margin_values: dict[int, float] = {}

        def _selection_margin_value(evaluation: ActionEvaluation) -> float:
            return selection_margin_values.get(id(evaluation), _certificate_margin_value(evaluation))

        def _band_key(evaluation: ActionEvaluation) -> tuple[float, float, float, int, int]:
            decision_rank = 1 if evaluation.decision == ShieldDecision.ALLOW else 0
            if use_margin_tiebreak:
                return (
                    _selection_margin_value(evaluation),
                    evaluation.margin,
                    evaluation.utility,
                    decision_rank,
                    -_order_index(evaluation),
                )
            return (
                evaluation.utility,
                float(decision_rank),
                0.0,
                decision_rank,
                -_order_index(evaluation),
            )

        def _rejected_key(evaluation: ActionEvaluation) -> tuple[bool, float, float, int]:
            if use_margin_tiebreak:
                return (evaluation.decision == ShieldDecision.ABSTAIN, evaluation.margin, evaluation.utility, -_order_index(evaluation))
            return (evaluation.decision == ShieldDecision.ABSTAIN, evaluation.utility, 0.0, -_order_index(evaluation))

        evaluations = tuple(self.evaluate(action, utility_fn(action), margin_weight=margin_weight) for action in action_tuple)
        allow = tuple(
            sorted(
                (ev for ev in evaluations if ev.decision == ShieldDecision.ALLOW),
                key=_selectable_key,
                reverse=True,
            )
        )
        repair = tuple(
            sorted(
                (ev for ev in evaluations if ev.decision == ShieldDecision.REPAIR_ACTION),
                key=_selectable_key,
                reverse=True,
            )
        )
        rejected = tuple(
            sorted(
                (ev for ev in evaluations if ev.decision in {ShieldDecision.ABSTAIN, ShieldDecision.BLOCK}),
                key=_rejected_key,
                reverse=True,
            )
        )
        feasible = tuple(sorted((*allow, *repair), key=_selectable_key, reverse=True))

        selectable_decisions = {ShieldDecision.ALLOW}
        if allow_repair_actions:
            selectable_decisions.add(ShieldDecision.REPAIR_ACTION)
        selectable = tuple(ev for ev in feasible if ev.decision in selectable_decisions)
        nonselectable_feasible = tuple(ev for ev in feasible if ev.decision not in selectable_decisions)
        best_selectable = max(selectable, key=lambda ev: (ev.utility, -_order_index(ev)), default=None)
        if normalized_strategy == "shuffled_margin" and len(selectable) > 1:
            ordered_selectable = sorted(selectable, key=_order_index)
            actual_margins = [_certificate_margin_value(ev) for ev in ordered_selectable]
            rotated_margins = actual_margins[1:] + actual_margins[:1]
            selection_margin_values = {
                id(ev): float(rotated)
                for ev, rotated in zip(ordered_selectable, rotated_margins)
            }
        band: tuple[ActionEvaluation, ...] = ()
        selected: ActionEvaluation | None
        band_strategies = {"utility_band", "robust_interior", "shuffled_margin"}
        margin_tiebreak_used = False
        if normalized_strategy in {"boundary_rescue", "guarded_interior"}:
            original = evaluations[0] if evaluations else None
            if original is not None and original in selectable:
                if normalized_strategy == "guarded_interior":
                    max_selectable_utility = (
                        best_selectable.utility
                        if best_selectable is not None
                        else max(ev.utility for ev in selectable)
                    )
                    band_candidates = [
                        ev
                        for ev in selectable
                        if ev.utility >= max_selectable_utility - epsilon - 1e-12
                    ]
                    band = tuple(sorted(band_candidates, key=_band_key, reverse=True))
                    geometric = band[0] if band else original
                    margin_gain = (
                        _certificate_margin_value(geometric)
                        - _certificate_margin_value(original)
                    )
                    minimum_gain = max(epsilon, 1e-9)
                    selected = (
                        geometric
                        if geometric is not original and margin_gain >= minimum_gain - 1e-12
                        else original
                    )
                    margin_tiebreak_used = selected is not original
                    ranked = (selected,) + tuple(
                        ev for ev in (*feasible, *rejected) if ev is not selected
                    )
                else:
                    # Candidate alternatives are repairs, not substitutes for
                    # a feasible agent plan.  Preserve the original unless
                    # geometry certifies that it is outside the region.
                    selected = original
                    band = (original,)
                    ranked = (original,) + tuple(
                        ev for ev in (*feasible, *rejected) if ev is not original
                    )
            elif selectable:
                max_selectable_utility = (
                    best_selectable.utility
                    if best_selectable is not None
                    else max(ev.utility for ev in selectable)
                )
                band_candidates = [
                    ev
                    for ev in selectable
                    if ev.utility >= max_selectable_utility - epsilon - 1e-12
                ]
                if margin_floor is not None:
                    floor_candidates = [
                        ev
                        for ev in band_candidates
                        if _certificate_margin_value(ev) >= float(margin_floor)
                    ]
                    if floor_candidates:
                        band_candidates = floor_candidates
                band = tuple(sorted(band_candidates, key=_band_key, reverse=True))
                selected = band[0] if band else best_selectable
                band_ids = {id(ev) for ev in band}
                rest_feasible = tuple(ev for ev in feasible if id(ev) not in band_ids)
                ranked = band + rest_feasible + rejected
                margin_tiebreak_used = bool(
                    selected is not None
                    and best_selectable is not None
                    and selected.action.id != best_selectable.action.id
                )
            else:
                selected = None
                ranked = feasible + rejected
        elif normalized_strategy in band_strategies and selectable:
            max_selectable_utility = best_selectable.utility if best_selectable is not None else max(ev.utility for ev in selectable)
            band_candidates = [ev for ev in selectable if ev.utility >= max_selectable_utility - epsilon - 1e-12]
            if margin_floor is not None:
                floor_candidates = [ev for ev in band_candidates if _certificate_margin_value(ev) >= float(margin_floor)]
                if floor_candidates:
                    band_candidates = floor_candidates
            band = tuple(sorted(band_candidates, key=_band_key, reverse=True))
            selected = band[0] if band else best_selectable
            margin_tiebreak_used = bool(
                selected is not None
                and best_selectable is not None
                and selected.action.id != best_selectable.action.id
            )
            band_ids = {id(ev) for ev in band}
            rest_feasible = tuple(ev for ev in feasible if id(ev) not in band_ids)
            ranked = band + rest_feasible + rejected
        elif normalized_strategy in band_strategies:
            selected = None
            ranked = feasible + rejected
        elif normalized_strategy == "top1":
            first = evaluations[0] if evaluations else None
            selected = first if first is not None and first in selectable else None
            ranked = ((selected,) if selected is not None else ()) + tuple(
                ev for ev in (*feasible, *rejected) if ev is not selected
            )
        elif normalized_strategy == "utility_first":
            utility_ranked = tuple(
                sorted(selectable, key=lambda ev: (ev.utility, -_order_index(ev)), reverse=True)
            )
            selected = utility_ranked[0] if utility_ranked else None
            selected_ids = {id(ev) for ev in utility_ranked}
            ranked = utility_ranked + tuple(ev for ev in (*feasible, *rejected) if id(ev) not in selected_ids)
        else:
            selected_pool = selectable if selectable else ()
            selected = selected_pool[0] if selected_pool else None
            ranked = selected_pool + nonselectable_feasible + rejected

        utility_baseline = max(evaluations, key=lambda ev: (ev.utility, -_order_index(ev)), default=None)
        best_selectable_utility = best_selectable.utility if best_selectable is not None else 0.0
        selected_regret = max(0.0, best_selectable_utility - selected.utility) if selected is not None else best_selectable_utility
        selection_certificate = {
            "selected_action_id": selected.action.id if selected else "",
            "selected_decision": selected.decision.value if selected else "",
            "selected_margin": selected.margin if selected else 0.0,
            "selected_certificate_margin": _certificate_margin_value(selected) if selected else 0.0,
            "selected_selection_margin": _selection_margin_value(selected) if selected else 0.0,
            "utility_baseline_action_id": utility_baseline.action.id if utility_baseline else "",
            "utility_baseline_decision": utility_baseline.decision.value if utility_baseline else "",
            "utility_baseline_margin": utility_baseline.margin if utility_baseline else 0.0,
            "utility_baseline_certificate_margin": _certificate_margin_value(utility_baseline) if utility_baseline else 0.0,
            "utility_baseline_projection_distance": (
                utility_baseline.projection.distance if utility_baseline and utility_baseline.projection else 0.0
            ),
            "selection_changed_by_constraints": bool(selected and utility_baseline and selected.action.id != utility_baseline.action.id),
            "projection_changed_tool_action": bool(
                selected
                and utility_baseline
                and selected.action.id != utility_baseline.action.id
                and utility_baseline.projection
                and utility_baseline.projection.distance > 1e-9
            ),
            "selection_strategy": normalized_strategy,
            "utility_band_epsilon": epsilon,
            "minimum_geometric_intervention_gain": (
                max(epsilon, 1e-9)
                if normalized_strategy == "guarded_interior"
                else ""
            ),
            "allow_repair_actions": bool(allow_repair_actions),
            "margin_floor": "" if margin_floor is None else float(margin_floor),
            "best_selectable_action_id": best_selectable.action.id if best_selectable else "",
            "best_selectable_utility": best_selectable_utility,
            "selected_utility_regret_vs_best_selectable": selected_regret,
            "utility_band_action_ids": tuple(ev.action.id for ev in band),
            "selection_margin_tiebreak_used": margin_tiebreak_used,
            "shuffled_margin_assignment": tuple(
                (ev.action.id, _selection_margin_value(ev))
                for ev in selectable
            ) if normalized_strategy == "shuffled_margin" else (),
        }
        return SelectionResult(
            selected=selected,
            feasible=feasible,
            rejected=rejected,
            ranked=ranked,
            status="OK" if selected and selected.decision == ShieldDecision.ALLOW else "REPAIR_ACTION" if selected else "NO_ALLOW_ACTION",
            selection_certificate=selection_certificate,
        )

    def project_action(self, action: ToolAction) -> dict[str, float]:
        """Return the nearest feasible feature projection used by the action certificate."""
        evaluation = self.evaluate(action)
        if evaluation.projection is None:
            return self.feature_space.feature_dict(self.feature_space.vectorize_action(action))
        return dict(evaluation.projection.projected_features)

    def project_action_certificate(self, action: ToolAction) -> ProjectionCertificate:
        return self.evaluate(action).projection or ProjectionCertificate(
            original_margin=1.0,
            projected_margin=1.0,
            distance=0.0,
            feasible=True,
        )
