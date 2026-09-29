"""Experimental IR compiler. Structural validation is not semantic verification."""
from __future__ import annotations

from .compiler import PolicyCompiler
from .geometry import FeasibleRegion, LinearFacet, RiskBudgetCone
from .policy_ir import ConstraintIR, ConstraintIRValidationError, validate_constraint_ir

PRECONDITION_FEATURES = {
    'trusted_grounding': 'critical_argument_grounding',
    'authorization': 'trusted_authorization',
    'confirmation': 'trusted_confirmation',
    'state_freshness': 'state_freshness',
    'prerequisite': 'prerequisite_support',
}
RISK_FEATURES = frozenset({'privacy_egress', 'financial_risk', 'irreversible_risk',
                           'write_risk', 'sink_externality', 'data_sensitivity'})


class IRPolicyCompiler:
    """Intersect mapped constraints with the legacy trusted envelope.

    Experimental single-tool adapter: field-scoped prerequisites, role-driven
    lifting and forbidden effects are rejected rather than silently ignored.
    This preserves baseline constraints, not correctness of the baseline itself.
    """
    def __init__(self, ir: ConstraintIR, *, schema_fields, baseline=None):
        validate_constraint_ir(ir, schema_fields=schema_fields)
        if ir.forbidden_effects:
            raise ConstraintIRValidationError('forbidden_effects are not supported by this backend')
        # Field scope is enforced by ConfidenceLiftedEncoder. The compiler only
        # adds the aggregate margin, so an IR must still retain its field list.
        if any(not p.fields and p.type in {"trusted_grounding", "authorization", "confirmation"}
               for p in ir.preconditions):
            raise ConstraintIRValidationError('security preconditions require field scope')
        for budget in ir.risk_budgets:
            if not budget.weights or set(budget.weights) - RISK_FEATURES:
                raise ConstraintIRValidationError('budget requires supported risk feature weights')
        self.ir = ir
        self.baseline = baseline or PolicyCompiler()

    def compile(self, policies=None, evidence=None):
        base = self.baseline.compile(policies, evidence)
        constraints = list(base.constraints)
        for index, p in enumerate(self.ir.preconditions):
            constraints.append(LinearFacet(
                id=f'ir:{index}:{p.type}', weights={PRECONDITION_FEATURES[p.type]: -1.0},
                bound=-p.minimum, description=f'Mapped {p.type} prerequisite',
                repair_hint=f'Establish {p.type} using trusted evidence.', source='validated_ir'))
        for index, b in enumerate(self.ir.risk_budgets):
            constraints.append(RiskBudgetCone(
                id=f'ir:budget:{index}:{b.name}', risk_weights=dict(b.weights), credit_weights={},
                bound=b.limit, description=f'Mapped risk budget {b.name}',
                repair_hint='Reduce effect risk or request clarification.', source='validated_ir'))
        return FeasibleRegion(tuple(constraints))
