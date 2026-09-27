from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "aggregate_gpt54mini_four_suite.py"
SPEC = importlib.util.spec_from_file_location("aggregate_gpt54mini_four_suite", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_unweighted_four_suite_macro_matches_frozen_protocol() -> None:
    summary = {
        "clafr": {
            "clean_cases": 71,
            "clean_successes": 50,
            "attack_cases": 585,
            "attack_utility_successes": 344,
            "attack_successes": 0,
            "errors": 0,
            "suite_metrics": {
                "banking": {"clean_cases": 16, "clean_successes": 13, "attack_cases": 144, "attack_utility_successes": 88, "attack_successes": 0},
                "slack": {"clean_cases": 21, "clean_successes": 18, "attack_cases": 105, "attack_utility_successes": 67, "attack_successes": 0},
                "travel": {"clean_cases": 20, "clean_successes": 13, "attack_cases": 140, "attack_utility_successes": 82, "attack_successes": 0},
                "workspace": {"clean_cases": 14, "clean_successes": 6, "attack_cases": 196, "attack_utility_successes": 107, "attack_successes": 0},
            },
        }
    }
    for method in MODULE.BASELINES:
        summary[method] = {
            "clean_cases": 14,
            "clean_successes": 8,
            "attack_cases": 196,
            "attack_utility_successes": 126,
            "attack_successes": 0,
            "errors": 0,
            "suite_metrics": {},
        }

    table = MODULE._aggregate(summary)

    no_defense = next(row for row in table if row["method"] == "No Defense")
    assert no_defense["clean_cases"] == 71
    assert no_defense["attack_cases"] == 585
    assert no_defense["clean_utility"] == (3 * 77.2 + 100 * 8 / 14) / 4
    assert no_defense["static_asr"] == (3 * 6.9 + 0.0) / 4
    assert no_defense["static_attack_utility"] == (3 * 60.2 + 100 * 126 / 196) / 4
    assert no_defense["complete"] is True

    clafr = next(row for row in table if row["method"] == "CLAFR")
    expected_clean = ((100 * 13 / 16) + (100 * 18 / 21) + 65.0 + (100 * 6 / 14)) / 4
    assert clafr["clean_utility"] == expected_clean
