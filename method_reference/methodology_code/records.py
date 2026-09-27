"""Immutable records returned by the paper-level DAFR algorithm."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .algebra import Vector, finite_vector


EXECUTE = "execute"
REVISE = "revise"
BLOCK = "block"
VALID_RESOLUTIONS = frozenset({REVISE, BLOCK})


@dataclass(frozen=True)
class NumericPoint:
    """A benchmark-independent point supplied to the geometric algorithm."""

    coordinates: Vector

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "coordinates",
            finite_vector(self.coordinates, name="coordinates"),
        )

    @property
    def dimension(self) -> int:
        return len(self.coordinates)


@dataclass(frozen=True)
class MarginEvaluation:
    """The raw and comparable margins of one supplied constraint."""

    name: str
    family: str
    raw_margin: float
    normalized_margin: float
    resolution: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("constraint name must not be empty")
        if not self.family:
            raise ValueError("constraint family must not be empty")
        if not isfinite(self.raw_margin):
            raise ValueError("raw margin must be finite")
        if not isfinite(self.normalized_margin):
            raise ValueError("normalized margin must be finite")
        if self.resolution not in VALID_RESOLUTIONS:
            raise ValueError("resolution must be 'revise' or 'block'")

    @property
    def feasible(self) -> bool:
        return self.raw_margin >= 0.0


@dataclass(frozen=True)
class DecisionCertificate:
    """Auditable output of one abstract feasibility decision."""

    outcome: str
    overall_margin: float
    feasibility_constraint: str
    feedback_constraint: str | None
    violated_constraints: tuple[str, ...]
    evaluations: tuple[MarginEvaluation, ...]

    def __post_init__(self) -> None:
        if self.outcome not in {EXECUTE, REVISE, BLOCK}:
            raise ValueError("unknown decision outcome")
        if not isfinite(self.overall_margin):
            raise ValueError("overall margin must be finite")
        if not self.feasibility_constraint:
            raise ValueError("feasibility constraint must not be empty")
        if not self.evaluations:
            raise ValueError("certificate must contain margin evaluations")

    @property
    def feasible(self) -> bool:
        return self.overall_margin >= 0.0
