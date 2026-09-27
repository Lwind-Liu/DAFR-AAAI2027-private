from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from geoconstraints.schemas import ConstraintMargin


@dataclass(frozen=True)
class HalfSpace:
    id: str
    normal: np.ndarray
    bound: float
    description: str
    repair_hint: str = "Move the action away from the violation side of this constraint."
    source: str = "compiled"
    severity: float = 1.0
    soft: bool = False

    def value(self, vector: np.ndarray) -> float:
        return float(self.normal @ vector)

    @property
    def norm(self) -> float:
        value = float(np.linalg.norm(self.normal))
        return value if value > 1e-12 else 1.0

    def margin(self, vector: np.ndarray) -> ConstraintMargin:
        val = self.value(vector)
        slack = float(self.bound - val)
        return ConstraintMargin(
            constraint_id=self.id,
            value=val,
            bound=float(self.bound),
            slack=slack,
            normalized_margin=slack / self.norm,
            description=self.description,
            repair_hint=self.repair_hint,
            severity=float(self.severity),
            soft=bool(self.soft),
            source=self.source,
        )


@dataclass(frozen=True)
class SecondOrderRiskConstraint:
    """Convex evidence-gated risk budget: ||W_r r||_2 <= bound + w_e^T e."""

    id: str
    risk_weights: Mapping[int, float]
    evidence_weights: Mapping[int, float]
    bound: float
    description: str
    repair_hint: str
    source: str = "second_order_risk_budget"
    severity: float = 1.0
    soft: bool = False

    def risk_norm(self, vector: np.ndarray) -> float:
        return float(
            np.linalg.norm(
                np.asarray([float(weight) * float(vector[int(index)]) for index, weight in self.risk_weights.items()])
            )
        )

    def evidence_credit(self, vector: np.ndarray) -> float:
        return float(
            sum(float(weight) * max(0.0, float(vector[int(index)])) for index, weight in self.evidence_weights.items())
        )

    def value(self, vector: np.ndarray) -> float:
        return self.risk_norm(vector) - self.evidence_credit(vector)

    @property
    def norm(self) -> float:
        value = float(
            np.linalg.norm(
                np.asarray([*self.risk_weights.values(), *self.evidence_weights.values()], dtype=float)
            )
        )
        return value if value > 1e-12 else 1.0

    def margin(self, vector: np.ndarray) -> ConstraintMargin:
        val = self.value(vector)
        slack = float(self.bound - val)
        return ConstraintMargin(
            constraint_id=self.id,
            value=val,
            bound=float(self.bound),
            slack=slack,
            normalized_margin=slack / self.norm,
            description=self.description,
            repair_hint=self.repair_hint,
            severity=float(self.severity),
            soft=bool(self.soft),
            source=self.source,
        )

    def project(self, vector: np.ndarray, tolerance: float = 1e-12) -> tuple[np.ndarray, bool]:
        projected = vector.astype(float).copy()
        current_norm = self.risk_norm(projected)
        radius = max(0.0, float(self.bound) + self.evidence_credit(projected))
        if current_norm <= radius + tolerance or current_norm <= tolerance:
            return projected, False
        scale = radius / current_norm
        for index in self.risk_weights:
            projected[int(index)] *= scale
        return projected, True


@dataclass(frozen=True)
class FeasibleRegion:
    constraints: tuple[Any, ...]

    def margins(self, vector: np.ndarray) -> tuple[ConstraintMargin, ...]:
        return tuple(constraint.margin(vector) for constraint in self.constraints)

    def feasible(self, vector: np.ndarray, tolerance: float = 1e-9) -> bool:
        return all(item.slack >= -tolerance for item in self.margins(vector))

    def min_margin(self, vector: np.ndarray) -> float:
        margins = self.margins(vector)
        if not margins:
            return float("inf")
        return min(item.normalized_margin for item in margins)


def semantic_boundary(
    constraint_id: str,
    safe_vectors: np.ndarray,
    unsafe_vectors: np.ndarray,
    description: str,
    repair_hint: str,
    priority: float = 1.0,
    slack_bias: float = 0.25,
) -> HalfSpace:
    if safe_vectors.size == 0 or unsafe_vectors.size == 0:
        raise ValueError("semantic boundary requires safe and unsafe vectors")
    safe_center = np.mean(safe_vectors, axis=0)
    unsafe_center = np.mean(unsafe_vectors, axis=0)
    normal = unsafe_center - safe_center
    if np.linalg.norm(normal) <= 1e-12:
        normal = np.zeros_like(safe_center)
        normal[0] = 1.0
    midpoint = 0.5 * (safe_center + unsafe_center)
    bound = float(normal @ midpoint) + float(slack_bias) * float(np.linalg.norm(normal))
    return HalfSpace(
        id=f"{constraint_id}:semantic_boundary",
        normal=normal,
        bound=bound,
        description=description,
        repair_hint=repair_hint,
        source="semantic_boundary",
        severity=float(priority),
        soft=True,
    )


def coordinate_halfspace(
    constraint_id: str,
    feature_index: int,
    dimension: int,
    bound: float,
    description: str,
    repair_hint: str,
    weight: float = 1.0,
    source: str = "structured_feature",
    severity: float = 1.0,
    soft: bool = False,
) -> HalfSpace:
    normal = np.zeros(dimension, dtype=float)
    normal[int(feature_index)] = float(weight)
    return HalfSpace(
        id=constraint_id,
        normal=normal,
        bound=float(bound),
        description=description,
        repair_hint=repair_hint,
        source=source,
        severity=float(severity),
        soft=bool(soft),
    )


def weighted_halfspace(
    constraint_id: str,
    feature_indices: dict[int, float],
    dimension: int,
    bound: float,
    description: str,
    repair_hint: str,
    source: str = "structured_coupling",
    severity: float = 1.0,
    soft: bool = False,
) -> HalfSpace:
    normal = np.zeros(dimension, dtype=float)
    for idx, weight in feature_indices.items():
        normal[int(idx)] = float(weight)
    return HalfSpace(
        id=constraint_id,
        normal=normal,
        bound=float(bound),
        description=description,
        repair_hint=repair_hint,
        source=source,
        severity=float(severity),
        soft=bool(soft),
    )


def project_onto_halfspace(vector: np.ndarray, halfspace: HalfSpace, tolerance: float = 1e-12) -> tuple[np.ndarray, bool]:
    violation = float(halfspace.normal @ vector - halfspace.bound)
    if violation <= tolerance:
        return vector.copy(), False
    norm_sq = float(halfspace.normal @ halfspace.normal)
    if norm_sq <= tolerance:
        return vector.copy(), False
    return vector - (violation / norm_sq) * halfspace.normal, True


def cyclic_project(vector: np.ndarray, constraints: Sequence[Any], max_iter: int = 40, tolerance: float = 1e-8) -> np.ndarray:
    projected = vector.astype(float).copy()
    for _ in range(max_iter):
        changed = False
        for constraint in constraints:
            if hasattr(constraint, "project"):
                projected, active = constraint.project(projected, tolerance=tolerance)
            else:
                projected, active = project_onto_halfspace(projected, constraint, tolerance=tolerance)
            changed = changed or active
        if not changed:
            break
    return projected
