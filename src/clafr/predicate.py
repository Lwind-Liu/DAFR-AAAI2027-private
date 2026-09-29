"""Equivalent arithmetic predicates, independent of margin methods.

General if/else can express both oblique and norm constraints. This control
should match geometric membership; it is not an axis-threshold approximation.
"""
import math
from .geometry import LinearFacet, RiskBudgetCone


def predicate_feasible(region, vector):
    for c in region.constraints:
        if c.soft:
            continue
        if isinstance(c, LinearFacet):
            value = sum(float(w) * vector.get(k) for k, w in c.weights.items())
        elif isinstance(c, RiskBudgetCone):
            risk = math.sqrt(sum((float(w) * max(0., vector.get(k))) ** 2
                                 for k, w in c.risk_weights.items()))
            credit = sum(float(w) * max(0., vector.get(k)) for k, w in c.credit_weights.items())
            value = risk - credit
        else:
            raise TypeError(f'Unsupported constraint: {type(c).__name__}')
        if not value <= float(c.bound):
            return False
    return True
