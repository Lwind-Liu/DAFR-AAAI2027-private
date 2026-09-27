"""Small numerical helpers used by the paper-level DAFR algorithm."""

from __future__ import annotations

from math import isfinite, sqrt
from typing import Iterable, Sequence


Vector = tuple[float, ...]
Matrix = tuple[Vector, ...]


def finite_vector(values: Iterable[float], *, name: str) -> Vector:
    """Return a finite vector or raise a concise validation error."""

    vector = tuple(float(value) for value in values)
    if not vector:
        raise ValueError(f"{name} must not be empty")
    if not all(isfinite(value) for value in vector):
        raise ValueError(f"{name} must contain only finite values")
    return vector


def finite_matrix(rows: Iterable[Iterable[float]], *, name: str) -> Matrix:
    """Return a finite rectangular matrix."""

    matrix = tuple(finite_vector(row, name=f"{name} row") for row in rows)
    if not matrix:
        raise ValueError(f"{name} must not be empty")
    width = len(matrix[0])
    if any(len(row) != width for row in matrix):
        raise ValueError(f"{name} must be rectangular")
    return matrix


def require_same_dimension(left: Sequence[float], right: Sequence[float]) -> None:
    """Reject vector operations with incompatible dimensions."""

    if len(left) != len(right):
        raise ValueError(
            f"dimension mismatch: received {len(left)} and {len(right)}"
        )


def dot(left: Sequence[float], right: Sequence[float]) -> float:
    """Compute a finite Euclidean inner product."""

    require_same_dimension(left, right)
    value = sum(float(a) * float(b) for a, b in zip(left, right, strict=True))
    if not isfinite(value):
        raise ValueError("inner product is not finite")
    return value


def matvec(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> Vector:
    """Apply a matrix to a vector."""

    return tuple(dot(row, vector) for row in matrix)


def l2_norm(vector: Sequence[float]) -> float:
    """Compute the Euclidean norm of a finite vector."""

    value = sqrt(sum(float(item) ** 2 for item in vector))
    if not isfinite(value):
        raise ValueError("norm is not finite")
    return value
