"""Independent analytical examples for protocol compliance and safety metrics."""

import json

import pytest
from test_universal import call, source

from mmm_intelligence.errors import MMMError
from mmm_intelligence.experiments import analyze_experiment, plan_experiment
from mmm_intelligence.universal_schemas import ExperimentPlanRequest


def protocol(**changes):
    return ExperimentPlanRequest(
        **{
            "method": "randomized",
            "outcome_type": "binary",
            "kpi": "conversion",
            "unit_column": "unit",
            "group_column": "arm",
            "treatment": "T",
            "control": "C",
            "baseline": 0.2,
            "minimum_effect": 0.1,
            "population": "eligible accounts",
            "measurement_window": "2026-01-01/2026-01-31",
            "stop_rule": "fixed horizon",
            "guardrails": ["refunds"],
            "hypothesis": "T increases conversion by at least .1",
            "analysis_plan": "ITT at account level, fixed horizon, Bonferroni family",
            "randomization_unit": "unit",
            "duration_days": 31,
            "conversion_window_days": 7,
            "observation_start": "2026-01-01",
            "observation_end": "2026-01-31",
            "date_column": "date",
            "population_column": "eligible",
            "population_value": "yes",
            "operational_constraints": "No live actions",
            "exclusion_criteria": "No exclusions",
            "comparison_family_size": 2,
            "guardrail_specs": {
                "refunds": {
                    "outcome_type": "binary",
                    "direction": "increase",
                    "max_adverse_change": 0.1,
                }
            },
            "cost_column": "cost",
            **changes,
        }
    )


def fixture_rows():
    return [
        {
            "unit": str(i),
            "arm": "C" if i < 100 else "T",
            "conversion": int(i % 10 < (2 if i < 100 else 4)),
            "refunds": 0,
            "cost": 2,
            "date": "2026-01-15",
            "eligible": "yes",
        }
        for i in range(200)
    ]


def result(rows=None, **changes):
    plan = {**plan_experiment(protocol(**changes)), "artifact_id": "plan-test"}
    return analyze_experiment(
        {"artifact_id": "source-test", "rows": rows or fixture_rows(), "synthetic": True}, plan
    )


def test_protocol_guardrails_cost_and_planned_power():
    analysis = result()
    assert analysis["population_verified"] and analysis["measurement_window_verified"]
    assert analysis["guardrails"]["refunds"]["status"] == "compatible_with_threshold"
    assert analysis["cost_per_conversion"]["control"] == 10
    assert analysis["cost_per_conversion"]["treatment"] == 5
    assert analysis["causal_identification"] is False
    assert 0 < analysis["power_at_planned_effect"] < 1


@pytest.mark.parametrize(
    "column,value", [("eligible", "no"), ("date", "2026-02-01"), ("date", None), ("cost", -1)]
)
def test_incompatible_population_window_or_cost_is_rejected(column, value):
    rows = fixture_rows()
    rows[0][column] = value
    with pytest.raises(MMMError):
        result(rows)


def test_guardrail_family_cannot_hide_multiple_comparisons():
    with pytest.raises(MMMError, match="family"):
        plan_experiment(protocol(comparison_family_size=1))


def test_minimum_planned_sample_matches_analysis_contract():
    plan = plan_experiment(
        protocol(
            outcome_type="continuous",
            baseline=0,
            minimum_effect=100,
            standard_deviation=1,
            cost_column=None,
        )
    )
    assert min(plan["sample_size_control"], plan["sample_size_treatment"]) >= 5


def test_missing_guardrail_values_are_reported_not_silently_dropped():
    rows = fixture_rows()
    rows[0]["refunds"] = None
    analysis = result(rows)
    assert analysis["guardrails"]["refunds"]["status"] == "insufficient"


def test_zero_conversions_abstains_from_cost_ratio():
    rows = fixture_rows()
    for row in rows:
        row["conversion"] = 0
    analysis = result(rows)
    assert analysis["cost_per_conversion"]["control"] is None
    assert analysis["cost_per_conversion"]["treatment"] is None


def test_experiment_analysis_links_to_immutable_learning_history(service):
    from test_joins import normalized

    data = normalized(service, "date,conversions\n2026-01-01,1\n2026-01-08,2\n")
    diagnostic = call(service, "create_growth_diagnostic", artifact_id=data["artifact_id"])
    decision = call(
        service,
        "create_growth_decision",
        diagnostic_id=diagnostic["artifact_id"],
        problem="conversion",
        hypothesis="T increases conversion",
        action="manual experiment",
        kpi="conversion",
        guardrails=["refunds"],
        baseline=".2",
        horizon="31 days",
        method="randomized",
        risks=["measurement error"],
    )
    plan = call(service, "plan_experiment", **protocol().model_dump(mode="json"))
    raw = source(service, json.dumps(fixture_rows()), "json")
    analysis = call(
        service, "analyze_experiment", artifact_id=raw["artifact_id"], plan_id=plan["artifact_id"]
    )
    common = {"actor": "reviewer declaration", "note": "synthetic evidence only"}
    approved = call(
        service,
        "transition_growth_decision",
        artifact_id=decision["artifact_id"],
        state="approved",
        **common,
    )
    assumptions = {
        key: "declared"
        for key in [
            "hypothesis",
            "unit",
            "window",
            "duration",
            "sample_assumptions",
            "control",
            "success",
            "stop",
            "guardrails",
        ]
    }
    planned = call(
        service,
        "transition_growth_decision",
        artifact_id=approved["artifact_id"],
        state="planned",
        plan={**assumptions, "experiment_plan_id": plan["artifact_id"]},
        **common,
    )
    invalid = service.call(
        "transition_growth_decision",
        {
            "artifact_id": planned["artifact_id"],
            "state": "evaluated",
            "results_id": raw["artifact_id"],
            **common,
        },
    )
    assert not invalid.ok and invalid.error.code == "RESULTS_INCOMPATIBLE"
    evaluated = call(
        service,
        "transition_growth_decision",
        artifact_id=planned["artifact_id"],
        state="evaluated",
        results_id=analysis["artifact_id"],
        **common,
    )
    learned = call(
        service,
        "transition_growth_decision",
        artifact_id=evaluated["artifact_id"],
        state="learned",
        **common,
    )
    assert learned["results_id"] == analysis["artifact_id"] and learned["state"] == "learned"
    assert learned["external_action_executed"] is False
    assert (
        call(service, "get_growth_artifact", artifact_id=decision["artifact_id"])["state"]
        == "proposed"
    )


def test_continuous_guardrail_zero_variance_is_insufficient():
    analysis = result(
        guardrail_specs={
            "refunds": {
                "outcome_type": "continuous",
                "direction": "decrease",
                "max_adverse_change": 1,
            }
        }
    )
    assert analysis["guardrails"]["refunds"]["status"] == "insufficient"
