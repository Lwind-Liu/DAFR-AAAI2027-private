"""Executable reference for the formula-level DAFR decision algorithm."""

from __future__ import annotations

from collections.abc import Iterable

from .constraints import GeometricConstraint
from .records import (
    BLOCK,
    EXECUTE,
    DecisionCertificate,
    MarginEvaluation,
    NumericPoint,
)


def _evaluate_all(
    point: NumericPoint,
    constraints: Iterable[GeometricConstraint],
) -> tuple[MarginEvaluation, ...]:
    evaluations = tuple(constraint.evaluate(point) for constraint in constraints)
    if not evaluations:
        raise ValueError("at least one constraint is required")
    names = tuple(evaluation.name for evaluation in evaluations)
    if len(set(names)) != len(names):
        raise ValueError("constraint names must be unique")
    return evaluations


def _rank_violations(
    evaluations: tuple[MarginEvaluation, ...],
) -> tuple[MarginEvaluation, ...]:
    violated = (evaluation for evaluation in evaluations if not evaluation.feasible)
    return tuple(
        sorted(
            violated,
            key=lambda evaluation: (
                evaluation.normalized_margin,
                evaluation.raw_margin,
                evaluation.name,
            ),
        )
    )


def decide(
    point: NumericPoint,
    constraints: Iterable[GeometricConstraint],
) -> DecisionCertificate:
    """Evaluate an intersection and return its signed-margin certificate.

    Raw margins determine feasibility.  Normalized margins order the violated
    constraints only after infeasibility has been established.
    """

    evaluations = _evaluate_all(point, constraints)
    feasibility = min(
        evaluations,
        key=lambda evaluation: (evaluation.raw_margin, evaluation.name),
    )
    violations = _rank_violations(evaluations)

    if feasibility.raw_margin >= 0.0:
        outcome = EXECUTE
        feedback_constraint = None
    else:
        feedback = violations[0]
        outcome = BLOCK if feedback.resolution == BLOCK else feedback.resolution
        feedback_constraint = feedback.name

    return DecisionCertificate(
        outcome=outcome,
        overall_margin=feasibility.raw_margin,
        feasibility_constraint=feasibility.name,
        feedback_constraint=feedback_constraint,
        violated_constraints=tuple(item.name for item in violations),
        evaluations=evaluations,
    )


def decide_from_coordinates(
    coordinates: Iterable[float],
    constraints: Iterable[GeometricConstraint],
) -> DecisionCertificate:
    """Convenience entry point for an already constructed numeric point."""

    return decide(NumericPoint(tuple(coordinates)), constraints)
