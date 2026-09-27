"""Generic geometric constraints corresponding to the paper equations."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Protocol

from .algebra import Matrix, Vector, dot, finite_matrix, finite_vector, l2_norm, matvec
from .records import MarginEvaluation, NumericPoint, VALID_RESOLUTIONS


class GeometricConstraint(Protocol):
    """Interface consumed by the benchmark-independent decision algorithm."""

    name: str

    def evaluate(self, point: NumericPoint) -> MarginEvaluation:
        """Evaluate the supplied point and return a signed margin."""


def _validate_common(
    *,
    name: str,
    scale: float,
    resolution: str,
) -> tuple[float, str]:
    if not name:
        raise ValueError("constraint name must not be empty")
    scale = float(scale)
    if not isfinite(scale) or scale <= 0.0:
        raise ValueError("normalization scale must be positive and finite")
    if resolution not in VALID_RESOLUTIONS:
        raise ValueError("resolution must be 'revise' or 'block'")
    return scale, resolution


@dataclass(frozen=True)
class LinearHalfspace:
    """Halfspace with signed margin w^T z + b."""

    name: str
    weights: Vector
    bias: float
    scale: float = 1.0
    resolution: str = "revise"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "weights",
            finite_vector(self.weights, name="weights"),
        )
        bias = float(self.bias)
        if not isfinite(bias):
            raise ValueError("bias must be finite")
        object.__setattr__(self, "bias", bias)
        scale, resolution = _validate_common(
            name=self.name,
            scale=self.scale,
            resolution=self.resolution,
        )
        object.__setattr__(self, "scale", scale)
        object.__setattr__(self, "resolution", resolution)

    def evaluate(self, point: NumericPoint) -> MarginEvaluation:
        raw = dot(self.weights, point.coordinates) + self.bias
        return MarginEvaluation(
            name=self.name,
            family="linear",
            raw_margin=raw,
            normalized_margin=raw / self.scale,
            resolution=self.resolution,
        )


@dataclass(frozen=True)
class CoupledRiskRegion:
    """Region with margin beta + v^T z - ||Wz||_2."""

    name: str
    support_weights: Vector
    risk_rows: Matrix
    offset: float
    scale: float = 1.0
    resolution: str = "block"

    def __post_init__(self) -> None:
        support = finite_vector(self.support_weights, name="support weights")
        rows = finite_matrix(self.risk_rows, name="risk rows")
        if len(support) != len(rows[0]):
            raise ValueError("support weights and risk rows must share a dimension")
        offset = float(self.offset)
        if not isfinite(offset):
            raise ValueError("offset must be finite")
        scale, resolution = _validate_common(
            name=self.name,
            scale=self.scale,
            resolution=self.resolution,
        )
        object.__setattr__(self, "support_weights", support)
        object.__setattr__(self, "risk_rows", rows)
        object.__setattr__(self, "offset", offset)
        object.__setattr__(self, "scale", scale)
        object.__setattr__(self, "resolution", resolution)

    def evaluate(self, point: NumericPoint) -> MarginEvaluation:
        support = dot(self.support_weights, point.coordinates)
        coupled_risk = l2_norm(matvec(self.risk_rows, point.coordinates))
        raw = self.offset + support - coupled_risk
        return MarginEvaluation(
            name=self.name,
            family="coupled",
            raw_margin=raw,
            normalized_margin=raw / self.scale,
            resolution=self.resolution,
        )
