"""Synthetic numeric example for the formula-level DAFR algorithm."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from methodology_code import CoupledRiskRegion, LinearHalfspace, decide_from_coordinates


def example_constraints() -> tuple[LinearHalfspace | CoupledRiskRegion, ...]:
    return (
        LinearHalfspace(
            name="region_a",
            weights=(1.0, 0.0, 0.0),
            bias=-0.40,
            scale=0.50,
            resolution="revise",
        ),
        LinearHalfspace(
            name="region_b",
            weights=(0.0, 1.0, 0.0),
            bias=-0.30,
            scale=0.50,
            resolution="revise",
        ),
        CoupledRiskRegion(
            name="region_c",
            support_weights=(0.20, 0.80, 0.0),
            risk_rows=((0.0, 0.0, 1.0),),
            offset=0.10,
            scale=1.0,
            resolution="block",
        ),
    )


def main() -> None:
    constraints = example_constraints()
    points = {
        "p0": (0.80, 0.70, 0.20),
        "p1": (0.20, 0.70, 0.20),
        "p2": (0.80, 0.35, 0.95),
    }

    for name, coordinates in points.items():
        certificate = decide_from_coordinates(coordinates, constraints)
        print(
            name,
            certificate.outcome,
            f"{certificate.overall_margin:.3f}",
            certificate.feedback_constraint,
        )


if __name__ == "__main__":
    main()
