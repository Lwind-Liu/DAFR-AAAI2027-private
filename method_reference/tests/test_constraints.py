"""Unit tests for the generic geometric equations."""

from __future__ import annotations

from math import sqrt
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from methodology_code import CoupledRiskRegion, LinearHalfspace, NumericPoint


class LinearHalfspaceTest(unittest.TestCase):
    def test_signed_margin_matches_affine_equation(self) -> None:
        region = LinearHalfspace(
            name="h",
            weights=(2.0, -1.0),
            bias=0.25,
            scale=0.50,
        )
        result = region.evaluate(NumericPoint((0.50, 0.20)))
        self.assertAlmostEqual(result.raw_margin, 1.05)
        self.assertAlmostEqual(result.normalized_margin, 2.10)
        self.assertTrue(result.feasible)

    def test_negative_margin_is_infeasible(self) -> None:
        region = LinearHalfspace(
            name="h",
            weights=(1.0, 0.0),
            bias=-0.50,
        )
        result = region.evaluate(NumericPoint((0.20, 0.40)))
        self.assertAlmostEqual(result.raw_margin, -0.30)
        self.assertFalse(result.feasible)

    def test_dimension_mismatch_is_rejected(self) -> None:
        region = LinearHalfspace(name="h", weights=(1.0, 0.0), bias=0.0)
        with self.assertRaisesRegex(ValueError, "dimension mismatch"):
            region.evaluate(NumericPoint((0.50,)))

    def test_invalid_scale_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "normalization scale"):
            LinearHalfspace(
                name="h",
                weights=(1.0,),
                bias=0.0,
                scale=0.0,
            )

    def test_nonfinite_point_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "finite"):
            NumericPoint((float("nan"),))


class CoupledRiskRegionTest(unittest.TestCase):
    def test_margin_matches_affine_minus_norm_equation(self) -> None:
        region = CoupledRiskRegion(
            name="c",
            support_weights=(1.0, 0.0, 0.0),
            risk_rows=((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            offset=0.25,
            scale=0.50,
        )
        result = region.evaluate(NumericPoint((0.75, 0.30, 0.40)))
        expected = 0.25 + 0.75 - sqrt(0.30**2 + 0.40**2)
        self.assertAlmostEqual(result.raw_margin, expected)
        self.assertAlmostEqual(result.normalized_margin, expected / 0.50)

    def test_coupled_term_can_make_point_infeasible(self) -> None:
        region = CoupledRiskRegion(
            name="c",
            support_weights=(0.50, 0.0),
            risk_rows=((0.0, 1.0),),
            offset=0.0,
        )
        result = region.evaluate(NumericPoint((0.40, 0.90)))
        self.assertLess(result.raw_margin, 0.0)
        self.assertFalse(result.feasible)

    def test_irregular_matrix_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "rectangular"):
            CoupledRiskRegion(
                name="c",
                support_weights=(1.0, 0.0),
                risk_rows=((1.0, 0.0), (1.0,)),
                offset=0.0,
            )

    def test_constraint_dimensions_must_agree(self) -> None:
        with self.assertRaisesRegex(ValueError, "share a dimension"):
            CoupledRiskRegion(
                name="c",
                support_weights=(1.0, 0.0, 0.0),
                risk_rows=((1.0, 0.0),),
                offset=0.0,
            )


if __name__ == "__main__":
    unittest.main()
