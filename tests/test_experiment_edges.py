"""Welch reference values and invalid designs/data cover statistical boundaries."""

from copy import deepcopy

import pytest
from test_experiment_protocol import fixture_rows, protocol

from mmm_intelligence.errors import MMMError
from mmm_intelligence.experiments import analyze_experiment, plan_experiment


def artifact(rows):
    return {"artifact_id": "data", "synthetic": True, "rows": rows}


def plan(**changes):
    return {**plan_experiment(protocol(**changes)), "artifact_id": "plan"}


@pytest.mark.parametrize(
    "changes",
    [
        {"treatment": "C"},
        {"kpi": "unit"},
        {
            "guardrail_specs": {
                "absent": {
                    "outcome_type": "binary",
                    "direction": "increase",
                    "max_adverse_change": 0.1,
                }
            }
        },
        {"guardrails": ["conversion"], "guardrail_specs": {}},
        {"randomization_unit": "region"},
        {"date_column": None},
        {"observation_end": "2025-01-01"},
        {"population_value": None},
        {"outcome_type": "continuous", "cost_column": "cost", "standard_deviation": 1},
        {"baseline": 0},
        {"baseline": 0.95},
        {"outcome_type": "continuous", "standard_deviation": None, "cost_column": None},
    ],
)
def test_invalid_protocols_are_rejected_before_planning(changes):
    with pytest.raises(MMMError):
        plan(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"minimum_effect": 1e-300},
        {"alpha": 5e-324},
        {"outcome_type": "continuous", "cost_column": None, "standard_deviation": 1e300},
    ],
)
def test_unrepresentable_power_calculation_has_explicit_range_error(changes):
    with pytest.raises(MMMError) as caught:
        plan(**changes)
    assert caught.value.code == "EXPERIMENT_RANGE"


@pytest.mark.parametrize(
    "change",
    [
        {"unit": None},
        {"arm": "foreign"},
        {"conversion": 2},
        {"conversion": "1"},
        {"conversion": float("inf")},
        {"cost": True},
        {"cost": float("nan")},
    ],
)
def test_unknown_units_arms_or_invalid_outcomes_are_refused(change):
    rows = fixture_rows()
    rows[0].update(change)
    with pytest.raises(MMMError):
        analyze_experiment(artifact(rows), plan())


def test_missing_columns_and_repeated_units_do_not_masquerade_as_independent():
    rows = fixture_rows()
    del rows[0]["conversion"]
    with pytest.raises(MMMError) as caught:
        analyze_experiment(artifact(rows), plan())
    assert caught.value.code == "EXPERIMENT_FIELDS"
    rows = fixture_rows()
    rows.append(deepcopy(rows[0]))
    with pytest.raises(MMMError) as caught:
        analyze_experiment(artifact(rows), plan())
    assert caught.value.code == "EXPERIMENT_UNIT"


def test_continuous_welch_matches_independent_hand_calculation():
    rows = fixture_rows()[:20]
    for i, row in enumerate(rows):
        row["arm"] = "C" if i < 10 else "T"
        row["conversion"] = i % 10 + 1 + (2 if i >= 10 else 0)
    result = analyze_experiment(
        artifact(rows), plan(outcome_type="continuous", standard_deviation=3, cost_column=None)
    )
    estimate = result["estimate"]
    assert estimate["difference"] == 2
    # Each arm has sample variance 55/6, n=10, Welch df=18.
    margin = 2.445005616513677 * ((55 / 6) / 5) ** 0.5  # Bonferroni alpha=.025; t(.9875,18)
    assert estimate["interval"] == pytest.approx([2 - margin, 2 + margin])
    assert result["causal_identification"] is False


def test_complete_case_losses_do_not_change_srm_assignment_denominator():
    rows = fixture_rows()
    rows[0]["conversion"] = None
    analysis = analyze_experiment(artifact(rows), plan())
    assert analysis["losses"]["C"] == 1
    assert analysis["estimate"]["control_n"] == 99
    assert analysis["sample_ratio_mismatch_pvalue"] == 1


def test_adverse_guardrail_difference_is_detected():
    rows = fixture_rows()
    for row in rows:
        row["refunds"] = int(row["arm"] == "T")
    analysis = analyze_experiment(artifact(rows), plan())
    assert analysis["guardrails"]["refunds"]["status"] == "harm_detected"
