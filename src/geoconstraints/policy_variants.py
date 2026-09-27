from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from geoconstraints.compiler import ConstraintCompiler
from geoconstraints.geometry import (
    FeasibleRegion,
    HalfSpace,
    SecondOrderRiskConstraint,
    coordinate_halfspace,
    weighted_halfspace,
)
from geoconstraints.policy import SemanticGeoConstraintPolicy
from geoconstraints.schemas import ActionEvaluation, NaturalLanguageConstraint, SelectionResult, ShieldDecision, ToolAction, UtilityFn


POLICY_VARIANTS = (
    "allow_all",
    "deny_all",
    "rule_shield",
    "policy_prompt",
    "semantic_only",
    "gated_only",
    "verifier_only",
    "halfspace_only",
    "halfspace_additive_only",
    "axis_additive_only",
    "convex_region_only",
    "gated_verifier",
    "full_no_margin",
    "full",
)


# Coordinates that explicitly lift action/evidence/provenance conjunctions.
# The additive ablation keeps the same policy, compiler, semantic action
# encoding, evidence ledger, and facet machinery while zeroing only these
# registered interaction coordinates.
RELATIONAL_LIFT_FEATURE_NAMES = (
    "confirmation_missing",
    "authorization_missing",
    "read_before_write_gap",
    "policy_evidence_gap",
    "state_dependency_gap",
    "irreversible_without_confirmation",
    "side_effect_without_confirmation",
    "privacy_disclosure_without_auth",
    "existing_record_write_without_read",
    "financial_action_without_auth",
    "private_data_access_without_auth",
    "external_web_access_without_user_intent",
    "user_intent_missing",
)


RELATIONAL_FACET_SUFFIXES = {
    "irreversible_without_confirmation",
    "side_effect_without_confirmation",
    "privacy_disclosure_without_auth",
    "private_data_access_without_auth",
    "financial_action_without_auth",
    "existing_record_write_without_read",
    "user_intent_missing",
    "external_web_access_without_user_intent",
}


def _non_relational_halfspaces(compiled: Sequence[object]) -> list[HalfSpace]:
    """Keep semantic and non-relational facets while replacing Boolean conjunction facets."""

    selected: list[HalfSpace] = []
    for item in compiled:
        for halfspace in item.halfspaces:
            if halfspace.id.rsplit(":", 1)[-1] not in RELATIONAL_FACET_SUFFIXES:
                selected.append(halfspace)
    return selected


def _shared_action_scope_halfspace(compiler: ConstraintCompiler, clause: object) -> HalfSpace:
    """Common v8.2 action-scope atom used by every geometric cell.

    Action-family scope is input information, not a mixed-risk interaction.
    Keeping the same axis-aligned facet in Additive and Convex prevents Full
    from gaining an unregistered feature that the ablation never receives.
    """

    return coordinate_halfspace(
        f"{clause.id}:shared_action_family_scope",
        compiler.feature_space.feature_index("trusted_action_family_mismatch"),
        compiler.feature_space.dimension,
        0.5,
        "State-changing actions must remain inside the trusted user's action family.",
        "Choose an action family authorized by the trusted user request.",
        weight=1.0,
        source="shared_action_scope",
        severity=clause.severity,
    )


def _axis_aligned_evidence_halfspaces(compiler: ConstraintCompiler, compiled: Sequence[object]) -> tuple[HalfSpace, ...]:
    """Additive ablation: independent evidence coordinates, without risk/evidence coupling."""

    fs = compiler.feature_space
    dim = fs.dimension
    out = _non_relational_halfspaces(compiled)

    def require(clause, feature_name: str, suffix: str, description: str, repair_hint: str, *, soft: bool = False) -> None:
        out.append(
            coordinate_halfspace(
                f"{clause.id}:{suffix}",
                fs.feature_index(feature_name),
                dim,
                -0.5,
                description,
                repair_hint,
                weight=-1.0,
                source="axis_aligned_evidence",
                severity=clause.severity,
                soft=soft,
            )
        )

    for item in compiled:
        clause = item.clause
        evidence = clause.required_evidence
        out.append(_shared_action_scope_halfspace(compiler, clause))
        if evidence.confirmation_required:
            require(
                clause,
                "trusted_confirmation_seen",
                "axis_confirmation_evidence",
                "Triggered actions require an independently satisfied confirmation coordinate.",
                "Obtain explicit scoped user confirmation.",
            )
        if evidence.authorization_required:
            require(
                clause,
                "trusted_authorization_seen",
                "axis_authorization_evidence",
                "Triggered actions require an independently satisfied authorization coordinate.",
                "Obtain trusted authorization.",
            )
        if evidence.state_read_required:
            require(
                clause,
                "trusted_state_seen",
                "axis_state_evidence",
                "Triggered writes require an independently satisfied state-evidence coordinate.",
                "Read the current state before writing.",
            )
        if evidence.user_intent_required:
            require(
                clause,
                "trusted_user_intent_seen",
                "axis_user_intent_evidence",
                "Triggered actions require an independently satisfied trusted-intent coordinate.",
                "Obtain trusted user intent for the action.",
            )
    return tuple(out)


def _oblique_dynamic_halfspaces(compiler: ConstraintCompiler, compiled: Sequence[object]) -> tuple[HalfSpace, ...]:
    """Full method: policy-scoped oblique risk budgets over primitive action/evidence coordinates."""

    fs = compiler.feature_space
    dim = fs.dimension
    out = _non_relational_halfspaces(compiled)

    def add(clause, suffix: str, weights: dict[str, float], bound: float, description: str, repair_hint: str) -> None:
        out.append(
            weighted_halfspace(
                f"{clause.id}:{suffix}",
                {fs.feature_index(name): weight for name, weight in weights.items()},
                dim,
                bound,
                description,
                repair_hint,
                source="oblique_primitive_coupling",
                severity=clause.severity,
            )
        )

    for item in compiled:
        clause = item.clause
        categories = set(clause.trigger.action_types)
        evidence = clause.required_evidence
        if evidence.confirmation_required:
            add(
                clause,
                "oblique_confirmation_budget",
                {
                    "external_side_effect": 0.55,
                    "irreversibility": 0.35,
                    "recipient_or_target_risk": 0.10,
                    "trusted_confirmation_seen": -0.85,
                    "trusted_manager_approval_seen": -0.15,
                },
                0.45,
                "Joint action-risk and trusted-confirmation budget.",
                "Reduce side-effect risk or obtain scoped confirmation.",
            )
        if evidence.state_read_required:
            add(
                clause,
                "oblique_state_budget",
                {
                    "is_existing_record_write": 0.55,
                    "tool_is_write": 0.25,
                    "recipient_or_target_risk": 0.10,
                    "loop_or_retry_count": 0.10,
                    "trusted_state_seen": -0.80,
                    "is_policy_lookup": -0.20,
                },
                0.45,
                "Joint write-risk and current-state evidence budget.",
                "Read current state or reduce the write scope.",
            )
        if "privacy" in categories:
            add(
                clause,
                "oblique_privacy_budget",
                {
                    "is_private_data_disclosure": 0.45,
                    "is_private_data_access": 0.35,
                    "privacy_risk": 0.15,
                    "recipient_is_external": 0.15,
                    "argument_sensitivity": 0.10,
                    "trusted_authorization_seen": -0.55,
                    "trusted_user_intent_seen": -0.35,
                    "trusted_identity_seen": -0.20,
                    "trusted_source_grounding_seen": -0.15,
                    "is_redaction_action": -0.50,
                },
                0.45,
                "Joint privacy, destination, provenance, and authorization budget.",
                "Use trusted intent or authorization, ground the data source, redact, or avoid external disclosure.",
            )
        if "financial" in categories:
            add(
                clause,
                "oblique_financial_budget",
                {
                    "financial_risk": 0.40,
                    "external_side_effect": 0.25,
                    "amount_or_quantity_risk": 0.20,
                    "recipient_or_target_risk": 0.10,
                    "trusted_authorization_seen": -0.45,
                    "trusted_confirmation_seen": -0.30,
                    "trusted_manager_approval_seen": -0.35,
                    "trusted_user_intent_seen": -0.20,
                },
                0.55,
                "Joint financial-risk and multi-source approval budget.",
                "Reduce financial exposure or obtain trusted approval evidence.",
            )
        if evidence.user_intent_required:
            add(
                clause,
                "oblique_intent_budget",
                {
                    "external_side_effect": 0.40,
                    "is_external_web_access": 0.35,
                    "recipient_or_target_risk": 0.15,
                    "instruction_in_untrusted_context": 0.25,
                    "policy_override_attempt": 0.35,
                    "trusted_user_intent_seen": -0.70,
                    "trusted_confirmation_seen": -0.20,
                },
                0.45,
                "Joint action-risk, provenance, and trusted-intent budget.",
                "Obtain matching trusted user intent or avoid the untrusted side effect.",
            )
        if "external_web_access" in categories:
            add(
                clause,
                "oblique_untrusted_instruction_budget",
                {
                    "is_external_web_access": 0.55,
                    "instruction_in_untrusted_context": 0.35,
                    "policy_override_attempt": 0.45,
                    "evidence_from_untrusted_source": 0.20,
                    "trusted_user_intent_seen": -0.60,
                },
                0.45,
                "Joint external-access and untrusted-instruction budget.",
                "Ignore untrusted instructions or obtain matching trusted user intent for the external access.",
            )
        if evidence.authorization_required:
            add(
                clause,
                "oblique_authorization_provenance_budget",
                {
                    "instruction_in_untrusted_context": 0.35,
                    "policy_override_attempt": 0.45,
                    "evidence_from_untrusted_source": 0.25,
                    "trusted_authorization_seen": -0.40,
                    "trusted_user_intent_seen": -0.25,
                },
                0.40,
                "Joint provenance and trusted-authorization budget.",
                "Reject untrusted authorization claims or obtain trusted authorization.",
            )
    return tuple(out)


def _mixed_convex_constraints(compiler: ConstraintCompiler, compiled: Sequence[object]) -> tuple[object, ...]:
    """Full method: affine provenance facets plus evidence-gated second-order risk budgets."""

    fs = compiler.feature_space
    dim = fs.dimension
    out: list[object] = list(_non_relational_halfspaces(compiled))

    def soc(
        clause,
        suffix: str,
        risk_weights: dict[str, float],
        evidence_weights: dict[str, float],
        bound: float,
        description: str,
        repair_hint: str,
    ) -> None:
        out.append(
            SecondOrderRiskConstraint(
                id=f"{clause.id}:{suffix}",
                risk_weights={fs.feature_index(name): weight for name, weight in risk_weights.items()},
                evidence_weights={fs.feature_index(name): weight for name, weight in evidence_weights.items()},
                bound=bound,
                description=description,
                repair_hint=repair_hint,
                severity=clause.severity,
            )
        )

    def affine(
        clause,
        suffix: str,
        weights: dict[str, float],
        bound: float,
        description: str,
        repair_hint: str,
    ) -> None:
        out.append(
            weighted_halfspace(
                f"{clause.id}:{suffix}",
                {fs.feature_index(name): weight for name, weight in weights.items()},
                dim,
                bound,
                description,
                repair_hint,
                source="affine_provenance_facet",
                severity=clause.severity,
            )
        )

    for item in compiled:
        clause = item.clause
        categories = set(clause.trigger.action_types)
        evidence = clause.required_evidence
        out.append(_shared_action_scope_halfspace(compiler, clause))
        if evidence.confirmation_required:
            soc(
                clause,
                "soc_confirmation_budget",
                {
                    "external_side_effect": 0.75,
                    "irreversibility": 0.65,
                    "recipient_or_target_risk": 0.30,
                },
                {
                    "trusted_confirmation_seen": 0.85,
                    "trusted_manager_approval_seen": 0.20,
                },
                0.45,
                "Second-order action-risk budget expanded by trusted confirmation.",
                "Reduce action risk or obtain scoped confirmation.",
            )
        if evidence.state_read_required:
            soc(
                clause,
                "soc_state_budget",
                {
                    "is_existing_record_write": 0.75,
                    "tool_is_write": 0.45,
                    "loop_or_retry_count": 0.25,
                    "recipient_or_target_risk": 0.20,
                },
                {
                    "trusted_state_seen": 0.85,
                    "is_policy_lookup": 0.20,
                },
                0.50,
                "Second-order write-risk budget expanded by current-state evidence.",
                "Read current state or reduce the write scope.",
            )
        if "privacy" in categories:
            soc(
                clause,
                "soc_privacy_budget",
                {
                    "is_private_data_disclosure": 0.65,
                    "is_private_data_access": 0.55,
                    "privacy_risk": 0.30,
                    "recipient_is_external": 0.35,
                    "argument_sensitivity": 0.25,
                },
                {
                    "trusted_authorization_seen": 0.55,
                    "trusted_user_intent_seen": 0.35,
                    "trusted_identity_seen": 0.20,
                    "trusted_source_grounding_seen": 0.15,
                    "is_redaction_action": 0.45,
                },
                0.55,
                "Second-order privacy/destination risk budget expanded by trusted provenance and authorization.",
                "Ground, authorize, redact, or avoid the private external action.",
            )
        if "financial" in categories:
            soc(
                clause,
                "soc_financial_budget",
                {
                    "financial_risk": 0.55,
                    "external_side_effect": 0.45,
                    "amount_or_quantity_risk": 0.40,
                    "recipient_or_target_risk": 0.25,
                },
                {
                    "trusted_authorization_seen": 0.45,
                    "trusted_confirmation_seen": 0.35,
                    "trusted_manager_approval_seen": 0.35,
                    "trusted_user_intent_seen": 0.20,
                },
                0.60,
                "Second-order financial exposure budget expanded by trusted approval evidence.",
                "Reduce financial exposure or obtain trusted approval.",
            )
        if evidence.user_intent_required:
            soc(
                clause,
                "soc_intent_budget",
                {
                    "external_side_effect": 0.50,
                    "is_external_web_access": 0.55,
                    "recipient_or_target_risk": 0.25,
                    "instruction_in_untrusted_context": 0.45,
                    "policy_override_attempt": 0.60,
                },
                {
                    "trusted_user_intent_seen": 0.75,
                    "trusted_confirmation_seen": 0.25,
                },
                0.55,
                "Second-order action/provenance risk budget expanded by matching trusted intent.",
                "Obtain matching trusted user intent or avoid the untrusted side effect.",
            )
        if "external_web_access" in categories:
            affine(
                clause,
                "affine_untrusted_override_facet",
                {
                    "instruction_in_untrusted_context": 0.10,
                    "policy_override_attempt": 0.15,
                    "evidence_from_untrusted_source": 0.10,
                    "external_side_effect": 0.30,
                    "is_external_web_access": 0.30,
                    "trusted_user_intent_seen": -0.35,
                },
                0.55,
                "Affine hard facet for untrusted policy-override provenance coupled to current action risk.",
                "Ignore policy-override instructions from untrusted content.",
            )
        if evidence.authorization_required:
            affine(
                clause,
                "affine_authorization_provenance_facet",
                {
                    "instruction_in_untrusted_context": 0.10,
                    "policy_override_attempt": 0.15,
                    "evidence_from_untrusted_source": 0.10,
                    "external_side_effect": 0.30,
                    "is_external_web_access": 0.20,
                    "trusted_authorization_seen": -0.25,
                    "trusted_user_intent_seen": -0.20,
                },
                0.50,
                "Affine hard facet preventing untrusted text from authorizing a risky current action.",
                "Use authorization from a trusted user or policy channel.",
            )
    return tuple(out)


class PolicyVariantAdapter:
    """Small adapter for target.md baseline variants that are not separate policies."""

    def __init__(self, base: SemanticGeoConstraintPolicy, *, variant: str) -> None:
        self.base = base
        self.variant = variant
        self.feature_space = base.feature_space
        self.region = base.region
        self.clauses = base.clauses

    def _with_decision(self, evaluation: ActionEvaluation, decision: ShieldDecision, *, margin: float | None = None) -> ActionEvaluation:
        new_margin = evaluation.margin if margin is None else float(margin)
        feasible = decision in {ShieldDecision.ALLOW, ShieldDecision.REPAIR_ACTION}
        certificate = evaluation.certificate
        if certificate is None:
            new_certificate = None
        else:
            new_certificate = replace(
                certificate,
                decision=decision,
                min_margin=new_margin,
                certificate_margin=new_margin,
            )
        return replace(
            evaluation,
            decision=decision,
            feasible=feasible,
            margin=new_margin,
            certificate=new_certificate,
        )

    def evaluate(self, action: ToolAction, utility: float = 0.0, margin_weight: float = 0.4) -> ActionEvaluation:
        if self.variant in {"allow_all", "policy_prompt"}:
            return self._with_decision(self.base.evaluate(action, utility, margin_weight=0.0), ShieldDecision.ALLOW, margin=1.0)
        if self.variant == "deny_all":
            return self._with_decision(self.base.evaluate(action, utility, margin_weight=0.0), ShieldDecision.BLOCK, margin=-1.0)
        if self.variant == "full_no_margin":
            return self.base.evaluate(action, utility, margin_weight=0.0)
        return self.base.evaluate(action, utility, margin_weight=margin_weight)

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
        if self.variant == "full_no_margin":
            return self.base.select(
                actions,
                utility_fn=utility_fn,
                margin_weight=0.0,
                selection_strategy=selection_strategy,
                utility_band_epsilon=utility_band_epsilon,
                allow_repair_actions=allow_repair_actions,
                margin_floor=margin_floor,
            )
        if self.variant not in {"allow_all", "policy_prompt", "deny_all"}:
            return self.base.select(
                actions,
                utility_fn=utility_fn,
                margin_weight=margin_weight,
                selection_strategy=selection_strategy,
                utility_band_epsilon=utility_band_epsilon,
                allow_repair_actions=allow_repair_actions,
                margin_floor=margin_floor,
            )

        utility_fn = utility_fn or (lambda action: 0.0)
        evaluations = tuple(self.evaluate(action, utility_fn(action), margin_weight=margin_weight) for action in actions)
        allow = tuple(
            sorted(
                (ev for ev in evaluations if ev.decision == ShieldDecision.ALLOW),
                key=lambda ev: (ev.utility, ev.score, ev.margin),
                reverse=True,
            )
        )
        repair = tuple(ev for ev in evaluations if ev.decision == ShieldDecision.REPAIR_ACTION)
        rejected = tuple(ev for ev in evaluations if ev.decision in {ShieldDecision.ABSTAIN, ShieldDecision.BLOCK})
        selected = allow[0] if allow else None
        utility_baseline = max(evaluations, key=lambda ev: ev.utility, default=None)
        return SelectionResult(
            selected=selected,
            feasible=allow + repair,
            rejected=rejected,
            ranked=allow + repair + rejected,
            status="OK" if selected else "NO_ALLOW_ACTION",
            selection_certificate={
                "selected_action_id": selected.action.id if selected else "",
                "selected_decision": selected.decision.value if selected else "",
                "selected_margin": selected.margin if selected else 0.0,
                "selected_certificate_margin": selected.certificate.certificate_margin if selected and selected.certificate else 0.0,
                "utility_baseline_action_id": utility_baseline.action.id if utility_baseline else "",
                "utility_baseline_decision": utility_baseline.decision.value if utility_baseline else "",
                "utility_baseline_margin": utility_baseline.margin if utility_baseline else 0.0,
                "utility_baseline_certificate_margin": (
                    utility_baseline.certificate.certificate_margin
                    if utility_baseline and utility_baseline.certificate
                    else utility_baseline.margin
                    if utility_baseline
                    else 0.0
                ),
                "utility_baseline_projection_distance": (
                    utility_baseline.projection.distance if utility_baseline and utility_baseline.projection else 0.0
                ),
                "selection_changed_by_constraints": bool(
                    selected and utility_baseline and selected.action.id != utility_baseline.action.id
                ),
                "projection_changed_tool_action": False,
            },
        )

    def project_action(self, action: ToolAction) -> dict[str, float]:
        return self.base.project_action(action)

    def project_action_certificate(self, action: ToolAction) -> object:
        return self.base.project_action_certificate(action)


def build_policy_variant(
    constraints: Sequence[NaturalLanguageConstraint | str],
    *,
    variant: str = "full",
    semantic_dims: int = 64,
) -> SemanticGeoConstraintPolicy:
    """Build a policy ablation without changing the benchmark task or policy text."""

    normalized_variant = "full" if variant == "shielded" else variant
    if normalized_variant not in POLICY_VARIANTS:
        raise ValueError(f"unknown policy variant: {variant}")
    if normalized_variant in {"allow_all", "policy_prompt"}:
        return PolicyVariantAdapter(
            SemanticGeoConstraintPolicy.from_constraints([], semantic_dims=semantic_dims),
            variant=normalized_variant,
        )

    normalized_constraints = tuple(
        NaturalLanguageConstraint(id=f"c{idx}", text=item) if isinstance(item, str) else item
        for idx, item in enumerate(constraints, 1)
    )
    compiler = ConstraintCompiler.default(semantic_dims=semantic_dims)
    compiled = compiler.compile_constraints(normalized_constraints)
    clauses = tuple(item.clause for item in compiled)
    halfspaces = tuple(halfspace for item in compiled for halfspace in item.halfspaces)

    if normalized_variant == "deny_all":
        return PolicyVariantAdapter(
            SemanticGeoConstraintPolicy(compiler.feature_space, FeasibleRegion(()), ()),
            variant="deny_all",
        )
    if normalized_variant == "semantic_only":
        selected = tuple(halfspace for halfspace in halfspaces if halfspace.soft)
        return SemanticGeoConstraintPolicy(compiler.feature_space, FeasibleRegion(selected), ())
    if normalized_variant == "gated_only":
        selected = tuple(halfspace for halfspace in halfspaces if not halfspace.soft)
        return SemanticGeoConstraintPolicy(compiler.feature_space, FeasibleRegion(selected), ())
    if normalized_variant == "verifier_only":
        return SemanticGeoConstraintPolicy(compiler.feature_space, FeasibleRegion(()), clauses)
    if normalized_variant == "halfspace_only":
        return SemanticGeoConstraintPolicy(
            compiler.feature_space,
            FeasibleRegion(halfspaces),
            clauses,
            hard_verifier_enabled=False,
        )
    if normalized_variant == "halfspace_additive_only":
        return SemanticGeoConstraintPolicy(
            compiler.feature_space,
            FeasibleRegion(halfspaces),
            clauses,
            hard_verifier_enabled=False,
            disabled_feature_names=RELATIONAL_LIFT_FEATURE_NAMES,
        )
    if normalized_variant == "axis_additive_only":
        return SemanticGeoConstraintPolicy(
            compiler.feature_space,
            FeasibleRegion(_axis_aligned_evidence_halfspaces(compiler, compiled)),
            clauses,
            hard_verifier_enabled=False,
        )
    if normalized_variant == "convex_region_only":
        return SemanticGeoConstraintPolicy(
            compiler.feature_space,
            FeasibleRegion(_mixed_convex_constraints(compiler, compiled)),
            clauses,
            hard_verifier_enabled=False,
        )
    if normalized_variant in {"rule_shield", "gated_verifier"}:
        selected = tuple(halfspace for halfspace in halfspaces if not halfspace.soft)
        return SemanticGeoConstraintPolicy(compiler.feature_space, FeasibleRegion(selected), clauses)
    full = SemanticGeoConstraintPolicy(compiler.feature_space, FeasibleRegion(halfspaces), clauses)
    if normalized_variant == "full_no_margin":
        return PolicyVariantAdapter(full, variant="full_no_margin")
    return full
