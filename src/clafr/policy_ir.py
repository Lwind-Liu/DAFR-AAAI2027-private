from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


ROLE_NAMES = frozenset({"object", "destination", "data", "amount", "time", "effect", "scope"})
PRECONDITION_TYPES = frozenset({"trusted_grounding", "authorization", "confirmation", "state_freshness", "prerequisite"})


@dataclass(frozen=True, slots=True)
class Precondition:
    type: str
    fields: tuple[str, ...] = ()
    minimum: float = 0.0
    source: str = "trusted"


@dataclass(frozen=True, slots=True)
class RiskBudget:
    name: str
    fields: tuple[str, ...] = ()
    limit: float = 1.0
    weights: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConstraintIR:
    """Typed, model-produced policy representation consumed by deterministic code.

    The mapper is deliberately not part of the execution decision. A caller must
    validate this object before using it to compile constraints.
    """

    tool_name: str
    roles: Mapping[str, str] = field(default_factory=dict)
    preconditions: tuple[Precondition, ...] = ()
    risk_budgets: tuple[RiskBudget, ...] = ()
    forbidden_effects: tuple[str, ...] = ()
    version: str = "1"
    provenance: str = "llm"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ConstraintIR":
        preconditions = tuple(
            Precondition(
                type=str(item.get("type", "")),
                fields=tuple(str(x) for x in item.get("fields", ())),
                minimum=float(item.get("minimum", 0.0)),
                source=str(item.get("source", "trusted")),
            )
            for item in payload.get("preconditions", ())
        )
        budgets = tuple(
            RiskBudget(
                name=str(item.get("name", "")),
                fields=tuple(str(x) for x in item.get("fields", ())),
                limit=float(item.get("limit", 1.0)),
                weights={str(k): float(v) for k, v in dict(item.get("weights", {})).items()},
            )
            for item in payload.get("risk_budgets", ())
        )
        return cls(
            tool_name=str(payload.get("tool_name", "")),
            roles={str(k): str(v) for k, v in dict(payload.get("roles", {})).items()},
            preconditions=preconditions,
            risk_budgets=budgets,
            forbidden_effects=tuple(str(x) for x in payload.get("forbidden_effects", ())),
            version=str(payload.get("version", "1")),
            provenance=str(payload.get("provenance", "llm")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "tool_name": self.tool_name,
            "roles": dict(self.roles),
            "preconditions": [
                {"type": p.type, "fields": list(p.fields), "minimum": p.minimum, "source": p.source}
                for p in self.preconditions
            ],
            "risk_budgets": [
                {"name": b.name, "fields": list(b.fields), "limit": b.limit, "weights": dict(b.weights)}
                for b in self.risk_budgets
            ],
            "forbidden_effects": list(self.forbidden_effects),
            "provenance": self.provenance,
        }


class ConstraintIRValidationError(ValueError):
    pass


def validate_constraint_ir(
    ir: ConstraintIR,
    *,
    schema_fields: Sequence[str] | None = None,
    max_budget_limit: float = 1.0,
) -> ConstraintIR:
    """Validate structure only; this cannot detect omitted or mistranslated policy."""
    if not ir.tool_name.strip():
        raise ConstraintIRValidationError("tool_name must be non-empty")
    if ir.version != "1":
        raise ConstraintIRValidationError("unsupported IR version")
    fields = set(ir.roles.keys() if schema_fields is None else schema_fields)
    unknown = set(ir.roles) - fields
    if unknown:
        raise ConstraintIRValidationError(f"role mapping references unknown fields: {sorted(unknown)}")
    invalid_roles = set(ir.roles.values()) - ROLE_NAMES
    if invalid_roles:
        raise ConstraintIRValidationError(f"unknown execution roles: {sorted(invalid_roles)}")
    for p in ir.preconditions:
        if p.type not in PRECONDITION_TYPES:
            raise ConstraintIRValidationError(f"unknown precondition type: {p.type}")
        if not 0.0 <= p.minimum <= 1.0:
            raise ConstraintIRValidationError(f"precondition minimum out of range: {p.minimum}")
        if set(p.fields) - fields:
            raise ConstraintIRValidationError(f"precondition references unknown fields: {p.fields}")
        if p.source != "trusted":
            raise ConstraintIRValidationError("authorization preconditions must use trusted source")
    for b in ir.risk_budgets:
        if not b.name.strip() or not 0.0 < b.limit <= max_budget_limit:
            raise ConstraintIRValidationError(f"invalid risk budget: {b.name!r}, {b.limit}")
        if set(b.fields) - fields:
            raise ConstraintIRValidationError(f"risk budget references unknown fields: {b.fields}")
        if any(not 0.0 <= float(v) <= 1.0 for v in b.weights.values()):
            raise ConstraintIRValidationError(f"risk weights must be in [0,1]: {b.name}")
    return ir
