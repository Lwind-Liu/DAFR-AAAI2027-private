"""Unit tests for signed-margin aggregation and decisions."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from methodology_code import (
    BLOCK,
    EXECUTE,
    REVISE,
    CoupledRiskRegion,
    LinearHalfspace,
    NumericPoint,
    REFERENCE_PSEUDOCODE,
    decide,
    decide_from_coordinates,
)


def linear(
    name: str,
    *,
    coordinate: int,
    threshold: float,
    scale: float = 1.0,
    resolution: str = REVISE,
) -> LinearHalfspace:
    weights = [0.0, 0.0, 0.0]
    weights[coordinate] = 1.0
    return LinearHalfspace(
        name=name,
        weights=tuple(weights),
        bias=-threshold,
        scale=scale,
        resolution=resolution,
    )


class DecisionAlgorithmTest(unittest.TestCase):
    def test_feasible_intersection_executes(self) -> None:
        constraints = (
            linear("a", coordinate=0, threshold=0.40),
            linear("b", coordinate=1, threshold=0.30),
        )
        certificate = decide_from_coordinates((0.80, 0.70, 0.10), constraints)
        self.assertEqual(certificate.outcome, EXECUTE)
        self.assertTrue(certificate.feasible)
        self.assertIsNone(certificate.feedback_constraint)
        self.assertEqual(certificate.violated_constraints, ())

    def test_minimum_raw_margin_defines_overall_margin(self) -> None:
        constraints = (
            linear("a", coordinate=0, threshold=0.50),
            linear("b", coordinate=1, threshold=0.20),
        )
        certificate = decide(NumericPoint((0.60, 0.90, 0.00)), constraints)
        self.assertAlmostEqual(certificate.overall_margin, 0.10)
        self.assertEqual(certificate.feasibility_constraint, "a")

    def test_negative_linear_margin_requests_revision(self) -> None:
        constraints = (
            linear("a", coordinate=0, threshold=0.50),
            linear("b", coordinate=1, threshold=0.30),
        )
        certificate = decide_from_coordinates((0.20, 0.80, 0.00), constraints)
        self.assertEqual(certificate.outcome, REVISE)
        self.assertFalse(certificate.feasible)
        self.assertEqual(certificate.feedback_constraint, "a")

    def test_negative_coupled_margin_blocks(self) -> None:
        coupled = CoupledRiskRegion(
            name="c",
            support_weights=(0.50, 0.50, 0.0),
            risk_rows=((0.0, 0.0, 1.0),),
            offset=0.0,
            resolution=BLOCK,
        )
        certificate = decide_from_coordinates(
            (0.20, 0.20, 0.90),
            (coupled,),
        )
        self.assertEqual(certificate.outcome, BLOCK)
        self.assertEqual(certificate.feedback_constraint, "c")

    def test_normalized_margins_order_feedback_only(self) -> None:
        constraints = (
            linear(
                "small_raw",
                coordinate=0,
                threshold=0.30,
                scale=1.00,
            ),
            linear(
                "large_normalized",
                coordinate=1,
                threshold=0.50,
                scale=0.10,
                resolution=BLOCK,
            ),
        )
        certificate = decide_from_coordinates((0.20, 0.45, 0.00), constraints)
        self.assertEqual(certificate.feasibility_constraint, "small_raw")
        self.assertAlmostEqual(certificate.overall_margin, -0.10)
        self.assertEqual(certificate.feedback_constraint, "large_normalized")
        self.assertEqual(certificate.outcome, BLOCK)

    def test_violations_are_returned_in_comparable_order(self) -> None:
        constraints = (
            linear("a", coordinate=0, threshold=0.50, scale=1.00),
            linear("b", coordinate=1, threshold=0.50, scale=0.10),
        )
        certificate = decide_from_coordinates((0.40, 0.48, 0.00), constraints)
        self.assertEqual(certificate.violated_constraints, ("b", "a"))

    def test_empty_intersection_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one constraint"):
            decide_from_coordinates((0.50,), ())

    def test_duplicate_names_are_rejected(self) -> None:
        constraints = (
            linear("same", coordinate=0, threshold=0.20),
            linear("same", coordinate=1, threshold=0.20),
        )
        with self.assertRaisesRegex(ValueError, "unique"):
            decide_from_coordinates((0.50, 0.50, 0.50), constraints)

    def test_reference_pseudocode_contains_core_operations(self) -> None:
        self.assertIn("raw_margins", REFERENCE_PSEUDOCODE)
        self.assertIn("normalized_margin", REFERENCE_PSEUDOCODE)
        self.assertIn("certificate", REFERENCE_PSEUDOCODE)


if __name__ == "__main__":
    unittest.main()
