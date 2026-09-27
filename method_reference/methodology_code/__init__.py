"""Benchmark-independent implementation of the DAFR paper-level algorithm."""

from .algorithm import decide, decide_from_coordinates
from .constraints import CoupledRiskRegion, GeometricConstraint, LinearHalfspace
from .pseudocode import REFERENCE_PSEUDOCODE
from .records import (
    BLOCK,
    EXECUTE,
    REVISE,
    DecisionCertificate,
    MarginEvaluation,
    NumericPoint,
)

__all__ = [
    "BLOCK",
    "CoupledRiskRegion",
    "DecisionCertificate",
    "EXECUTE",
    "GeometricConstraint",
    "LinearHalfspace",
    "MarginEvaluation",
    "NumericPoint",
    "REFERENCE_PSEUDOCODE",
    "REVISE",
    "decide",
    "decide_from_coordinates",
]
