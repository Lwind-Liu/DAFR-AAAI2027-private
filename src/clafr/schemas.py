from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Mapping, Sequence


def _tuple(value: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(str(item) for item in (value or ()))


def _string_mapping(value: Mapping[str, Any] | None) -> dict[str, str]:
    return {str(key): str(item) for key, item in dict(value or {}).items()}


@dataclass(frozen=True, slots=True)
class ToolAction:
    """A concrete JSON tool call proposed at the current control boundary."""

    id: str
    tool_name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    rationale: str = ""
    utility_hint: float = 0.0

    @property
    def argument_text(self) -> str:
        return json.dumps(self.arguments, ensure_ascii=False, sort_keys=True)

    @property
    def text(self) -> str:
        return " ".join(
            part for part in (self.tool_name, self.argument_text, self.rationale) if part
        )


@dataclass(frozen=True, slots=True)
class RuntimeEvidence:
    """Trusted and untrusted evidence available at one action boundary.

    Untrusted observations are allowed to raise risk. They never create
    authorization, confirmation, or trusted intent credit.
    """

    trusted_task: str = ""
    policies: tuple[str, ...] = ()
    trusted_authorizations: tuple[str, ...] = ()
    trusted_confirmations: tuple[str, ...] = ()
    trusted_state: tuple[str, ...] = ()
    untrusted_observations: tuple[str, ...] = ()
    completed_steps: tuple[str, ...] = ()
    tool_schema: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    tool_descriptions: Mapping[str, str] = field(default_factory=dict)
    untrusted_tools: tuple[str, ...] = ()
    state_freshness: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "policies", _tuple(self.policies))
        object.__setattr__(
            self, "trusted_authorizations", _tuple(self.trusted_authorizations)
        )
        object.__setattr__(
            self, "trusted_confirmations", _tuple(self.trusted_confirmations)
        )
        object.__setattr__(self, "trusted_state", _tuple(self.trusted_state))
        object.__setattr__(
            self, "untrusted_observations", _tuple(self.untrusted_observations)
        )
        object.__setattr__(self, "completed_steps", _tuple(self.completed_steps))
        object.__setattr__(self, "tool_descriptions", _string_mapping(self.tool_descriptions))
        object.__setattr__(self, "untrusted_tools", _tuple(self.untrusted_tools))

    @property
    def trusted_text(self) -> str:
        return " ".join(
            (
                self.trusted_task,
                *self.trusted_authorizations,
                *self.trusted_confirmations,
                *self.trusted_state,
                *self.completed_steps,
            )
        )

    @property
    def untrusted_text(self) -> str:
        return " ".join(self.untrusted_observations)

    @property
    def policy_text(self) -> str:
        return " ".join(self.policies)

    def required_args(self, tool_name: str) -> tuple[str, ...]:
        return tuple(self.tool_schema.get(tool_name, ()))

    def tool_description(self, tool_name: str) -> str:
        return str(self.tool_descriptions.get(tool_name, ""))

    def is_untrusted_tool(self, tool_name: str) -> bool:
        return str(tool_name) in set(self.untrusted_tools)


@dataclass(frozen=True, slots=True)
class FeatureVector:
    """Named action-evidence vector used by geometric constraints."""

    names: tuple[str, ...]
    values: tuple[float, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, values: Mapping[str, float], *, names: Sequence[str] | None = None) -> "FeatureVector":
        ordered = tuple(names or sorted(values))
        return cls(ordered, tuple(float(values.get(name, 0.0)) for name in ordered))

    def get(self, name: str, default: float = 0.0) -> float:
        try:
            idx = self.names.index(name)
        except ValueError:
            return float(default)
        return float(self.values[idx])

    def as_dict(self) -> dict[str, float]:
        return dict(zip(self.names, self.values))

    def squared_distance(self, other: "FeatureVector", names: Sequence[str] | None = None) -> float:
        selected = tuple(names or self.names)
        return sum((self.get(name) - other.get(name)) ** 2 for name in selected)


@dataclass(frozen=True, slots=True)
class ConstraintMargin:
    constraint_id: str
    source: str
    value: float
    bound: float
    slack: float
    normalized_slack: float
    description: str
    repair_hint: str
    soft: bool = False
    severity: float = 1.0


@dataclass(frozen=True, slots=True)
class ActionCertificate:
    action_id: str
    tool_name: str
    features: Mapping[str, float]
    margins: tuple[ConstraintMargin, ...]
    feasible: bool
    utility: float
    interior_score: float
    proximity_penalty: float
    final_score: float
    trace: Mapping[str, Any] = field(default_factory=dict)

    @property
    def violated_constraints(self) -> tuple[str, ...]:
        return tuple(
            margin.constraint_id
            for margin in self.margins
            if (not margin.soft and margin.slack < 0.0)
        )

    @property
    def active_constraints(self) -> tuple[str, ...]:
        return tuple(
            margin.constraint_id for margin in self.margins if margin.normalized_slack < 0.15
        )

    @property
    def role_projection(self) -> Mapping[str, Any]:
        """Auditable semantic projection retained alongside the numeric certificate."""
        return self.trace.get("role_projection", {})


@dataclass(frozen=True, slots=True)
class SelectionResult:
    decision: str
    selected: ToolAction | None
    selected_certificate: ActionCertificate | None
    certificates: tuple[ActionCertificate, ...]
    region_metadata: Mapping[str, Any]
