from __future__ import annotations

import re
from typing import Sequence

from .geometry import FeasibleRegion, LinearFacet, RiskBudgetCone
from .schemas import RuntimeEvidence


def _has(text: str, *patterns: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


class PolicyCompiler:
    """Compile simple policy text into a confidence-lifted feasible region."""

    def __init__(
        self,
        *,
        enable_schema_verifier: bool = True,
        enable_semantic_facets: bool = True,
        enable_confidence_floor: bool = True,
        enable_untrusted_control: bool = True,
        enable_untrusted_linear_facets: bool = True,
        enable_untrusted_budget: bool = True,
        enable_privacy_budget: bool = True,
        enable_financial_budget: bool = True,
        enable_state_write_budget: bool = True,
    ) -> None:
        self.enable_schema_verifier = bool(enable_schema_verifier)
        self.enable_semantic_facets = bool(enable_semantic_facets)
        self.enable_confidence_floor = bool(enable_confidence_floor)
        self.enable_untrusted_control = bool(enable_untrusted_control)
        self.enable_untrusted_linear_facets = bool(enable_untrusted_linear_facets)
        self.enable_untrusted_budget = bool(enable_untrusted_budget)
        self.enable_privacy_budget = bool(enable_privacy_budget)
        self.enable_financial_budget = bool(enable_financial_budget)
        self.enable_state_write_budget = bool(enable_state_write_budget)

    def compile(self, policies: Sequence[str] | None, evidence: RuntimeEvidence | None = None) -> FeasibleRegion:
        policy_text = " ".join(policies or ())
        has_untrusted_evidence = False
        if evidence is not None:
            policy_text = " ".join((policy_text, evidence.policy_text, evidence.untrusted_text))
            has_untrusted_evidence = bool(evidence.untrusted_text.strip() or evidence.untrusted_tools)

        constraints: list[object] = []
        if self.enable_schema_verifier:
            constraints.append(
                LinearFacet(
                    id="schema_complete",
                    weights={"schema_format_validity": -1.0},
                    bound=-0.50,
                    description="Tool calls must satisfy the visible schema before geometric selection.",
                    repair_hint="Fill required tool arguments or choose a schema-complete action.",
                    source="hard_schema_verifier",
                )
            )

        if self.enable_semantic_facets:
            constraints.extend(
                [
                    LinearFacet(
                        id="trusted_action_support",
                        weights={
                            "effect_class": 0.55,
                            "state_cleanliness_cost": 0.45,
                            "sink_externality": 0.25,
                            "privacy_egress": 0.35,
                            "source_channel_risk": 0.20,
                            "tool_source_risk": 0.25,
                            "trusted_intent_support": -0.95,
                            "prerequisite_support": -0.65,
                            "state_read_necessity": -0.55,
                            "argument_trusted_provenance": -0.25,
                            "critical_argument_grounding": -0.45,
                            "entity_grounding_confidence": -0.25,
                            "write_authorization_strength": -0.45,
                            "trusted_authorization": -0.35,
                        },
                        bound=0.35,
                        description="Every effectful action must be necessary for the trusted user task or a grounded prerequisite.",
                        repair_hint="Use only actions supported by the trusted task or a necessary grounded prerequisite.",
                        source="semantic_action_support",
                        severity=1.25,
                    ),
                    LinearFacet(
                        id="state_cleanliness",
                        weights={
                            "state_cleanliness_cost": 1.00,
                            "effect_class": 0.15,
                            "sink_externality": 0.15,
                            "trusted_intent_support": -0.45,
                            "prerequisite_support": -0.30,
                            "state_read_necessity": -0.45,
                            "trusted_authorization": -0.30,
                        },
                        bound=0.35,
                        description="Latent writes and unrelated state mutations must not pollute the environment.",
                        repair_hint="Avoid state-changing reads or writes unless the trusted task requires them.",
                        source="semantic_state_cleanliness",
                        severity=1.1,
                    ),
                    LinearFacet(
                        id="entity_grounding_required",
                        weights={
                            "sink_externality": 0.45,
                            "privacy_egress": 0.35,
                            "irreversible_risk": 0.45,
                            "effect_class": 0.25,
                            "entity_grounding_confidence": -0.75,
                            "critical_argument_grounding": -0.60,
                            "write_authorization_strength": -0.35,
                            "argument_trusted_provenance": -0.35,
                            "trusted_intent_support": -0.35,
                        },
                        bound=0.25,
                        description="Destinations, objects, and irreversible actions must be grounded before execution.",
                        repair_hint="Ground the exact recipient, channel, object id, or date from trusted task/state.",
                        source="semantic_entity_grounding",
                        severity=1.0,
                    ),
                    LinearFacet(
                        id="critical_side_effect_grounding",
                        weights={
                            "sink_externality": 0.55,
                            "privacy_egress": 0.20,
                            "effect_class": 0.35,
                            "source_channel_risk": 0.25,
                            "tool_source_risk": 0.35,
                            "critical_argument_grounding": -1.00,
                            "write_authorization_strength": -0.25,
                            "trusted_intent_support": -0.15,
                            "trusted_authorization": -0.25,
                            "trusted_confirmation": -0.25,
                        },
                        bound=0.45,
                        description="External or state-changing effects require trusted grounding for their critical arguments.",
                        repair_hint="Ground recipient, channel, object, amount, date, and message fields in trusted task/state.",
                        source="semantic_critical_argument_grounding",
                        severity=1.15,
                    ),
                    LinearFacet(
                        id="critical_field_grounding_floor",
                        weights={
                            "effect_class": 0.45,
                            "sink_externality": 0.55,
                            "critical_argument_grounding": -1.00,
                        },
                        bound=0.45,
                        description="High-impact or external effects require grounded critical fields.",
                        repair_hint="Ground every security-critical destination, identifier, amount, and payload literal in trusted evidence.",
                        source="critical_field_provenance_floor",
                        severity=1.35,
                    ),
                    LinearFacet(
                        id="irreversible_effect_authorization",
                        weights={
                            "irreversible_risk": 0.75,
                            "write_risk": 0.45,
                            "effect_class": 0.25,
                            "state_cleanliness_cost": 0.35,
                            "write_authorization_strength": -0.55,
                            "trusted_authorization": -0.45,
                            "trusted_confirmation": -0.30,
                            "critical_argument_grounding": -0.30,
                            "trusted_intent_support": -0.20,
                            "state_grounding": -0.25,
                            "completion_sufficiency": -0.20,
                        },
                        bound=0.35,
                        description="Destructive or irreversible effects require explicit trusted authorization and grounded arguments.",
                        repair_hint="Avoid destructive state changes unless the trusted task explicitly authorizes them.",
                        source="semantic_irreversible_authorization",
                        severity=1.2,
                    ),
                ]
            )

        if self.enable_confidence_floor:
            constraints.append(
                LinearFacet(
                    id="confidence_floor",
                    weights={"uncertainty": 0.75, "confidence": -0.50, "object_uniqueness": -0.20},
                    bound=0.45,
                    description="Low evidence confidence should push the action toward read or clarify behavior.",
                    repair_hint="Ground the object, verify state, or ask for clarification.",
                    source="confidence_soft_facet",
                    soft=True,
                    severity=0.35,
                )
            )

        if self.enable_untrusted_control and (
            has_untrusted_evidence or _has(policy_text, "prompt|inject|untrusted|webpage|ignore|override|bypass")
        ):
            constraints.extend(
                constraint
                for constraint in self._untrusted_control_constraints()
                if (
                    self.enable_untrusted_budget
                    if isinstance(constraint, RiskBudgetCone)
                    else self.enable_untrusted_linear_facets
                )
            )
        if self.enable_privacy_budget and _has(policy_text, "private|privacy|confidential|secret|password|code|token|message|email|data"):
            constraints.append(self._privacy_budget())
        if self.enable_financial_budget and _has(policy_text, "bank|financial|payment|transfer|invoice|card|money|amount"):
            constraints.append(self._financial_budget())
        if self.enable_state_write_budget and _has(policy_text, "update|delete|remove|write|change|record|state|confirm"):
            constraints.append(self._state_write_budget())

        return FeasibleRegion(tuple(constraints))

    @staticmethod
    def _untrusted_control_constraints() -> tuple[object, ...]:
        return (
            LinearFacet(
                id="untrusted_tool_source_requires_authorization",
                weights={
                    "tool_source_risk": 1.00,
                    "trusted_authorization": -0.65,
                    "trusted_confirmation": -0.45,
                    "trusted_intent_support": -0.20,
                },
                bound=0.05,
                description="Tools from an untrusted source require explicit trusted authorization before execution.",
                repair_hint="Use a trusted runtime tool or obtain explicit user authorization for this tool source.",
                source="tool_source_provenance_boundary",
                severity=1.3,
            ),
            LinearFacet(
                id="trusted_over_untrusted_direction",
                weights={
                    "untrusted_instruction_alignment": 1.00,
                    "source_channel_risk": 0.55,
                    "tool_source_risk": 0.70,
                    "trusted_intent_support": -0.95,
                    "prerequisite_support": -0.45,
                    "state_read_necessity": -0.35,
                    "argument_trusted_provenance": -0.25,
                    "critical_argument_grounding": -0.35,
                    "read_before_write": -1.05,
                    "state_grounding": -0.35,
                    "effect_class": 0.45,
                    "sink_externality": 0.35,
                    "privacy_egress": 0.25,
                },
                bound=-0.05,
                description="Candidate action must align more with trusted intent than with untrusted observations.",
                repair_hint="Choose an action whose effect follows the trusted user task, not untrusted-channel content.",
                source="untrusted_control_direction",
                severity=1.2,
            ),
            RiskBudgetCone(
                id="untrusted_control_budget",
                risk_weights={
                    "untrusted_instruction_alignment": 0.75,
                    "untrusted_control_signal": 0.65,
                    "source_channel_risk": 0.55,
                    "tool_source_risk": 0.75,
                    "sink_externality": 0.45,
                    "privacy_egress": 0.50,
                    "effect_class": 0.35,
                    "overreach_risk": 0.45,
                },
                credit_weights={
                    "trusted_intent_support": 0.55,
                    "prerequisite_support": 0.20,
                    "state_read_necessity": 0.25,
                    "argument_trusted_provenance": 0.25,
                    "critical_argument_grounding": 0.35,
                    "write_authorization_strength": 0.30,
                    "trusted_authorization": 0.25,
                    "confidence": 0.20,
                },
                bound=0.45,
                description="Joint budget for untrusted-channel alignment and risky action effects.",
                repair_hint="Reduce side effects, remove untrusted-sourced parameters, or obtain trusted authorization.",
                source="untrusted_joint_risk_budget",
                severity=1.3,
            ),
        )

    @staticmethod
    def _privacy_budget() -> RiskBudgetCone:
        return RiskBudgetCone(
            id="privacy_destination_budget",
            risk_weights={
                "privacy_egress": 0.90,
                "sink_externality": 0.35,
                "data_sensitivity": 0.20,
                "source_channel_risk": 0.35,
                "effect_class": 0.30,
            },
            credit_weights={
                "trusted_authorization": 0.55,
                "trusted_confirmation": 0.30,
                "trusted_intent_support": 0.35,
                "critical_argument_grounding": 0.40,
                "write_authorization_strength": 0.35,
                "entity_grounding_confidence": 0.25,
                "state_read_necessity": 0.35,
                "source_grounding": 0.25,
                "redaction_present": 0.45,
            },
            bound=0.50,
            description="Private data can leave the system only under trusted authorization, grounding, or redaction.",
            repair_hint="Avoid disclosure, redact the content, or obtain trusted authorization.",
            source="privacy_joint_risk_budget",
            severity=1.2,
        )

    @staticmethod
    def _financial_budget() -> RiskBudgetCone:
        return RiskBudgetCone(
            id="financial_exposure_budget",
            risk_weights={
                "financial_risk": 0.70,
                "privacy_egress": 0.45,
                "sink_externality": 0.35,
                "irreversible_risk": 0.45,
                "effect_class": 0.30,
            },
            credit_weights={
                "trusted_authorization": 0.50,
                "trusted_confirmation": 0.35,
                "state_grounding": 0.25,
                "state_read_necessity": 0.45,
                "critical_argument_grounding": 0.30,
                "write_authorization_strength": 0.35,
                "trusted_intent_support": 0.25,
                "prerequisite_support": 0.30,
                "entity_grounding_confidence": 0.20,
            },
            bound=0.55,
            description="Financial exposure requires explicit authorization and state grounding.",
            repair_hint="Verify state and obtain explicit authorization before financial side effects.",
            source="financial_joint_risk_budget",
            severity=1.2,
        )

    @staticmethod
    def _state_write_budget() -> RiskBudgetCone:
        return RiskBudgetCone(
            id="state_write_budget",
            risk_weights={
                "write_risk": 0.60,
                "sink_externality": 0.25,
                "irreversible_risk": 0.55,
                "overreach_risk": 0.35,
                "state_cleanliness_cost": 0.55,
            },
            credit_weights={
                "read_before_write": 0.40,
                "state_grounding": 0.35,
                "trusted_confirmation": 0.40,
                "trusted_intent_support": 0.35,
                "critical_argument_grounding": 0.40,
                "write_authorization_strength": 0.45,
                "entity_grounding_confidence": 0.20,
            },
            bound=0.55,
            description="State-changing actions require grounding, scoped intent, and confirmation when risky.",
            repair_hint="Read current state, reduce write scope, or ask for confirmation.",
            source="state_joint_risk_budget",
            severity=1.0,
        )
