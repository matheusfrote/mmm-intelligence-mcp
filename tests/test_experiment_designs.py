"""Inference follows randomization units, never replicated individual rows."""

import numpy as np
import pytest
from scipy.stats import ttest_rel

from mmm_intelligence.errors import MMMError
from mmm_intelligence.experiments import analyze_experiment, plan_experiment
from mmm_intelligence.universal_schemas import ExperimentPlanRequest


def plan(design, **options):
    request = ExperimentPlanRequest.model_validate(
        {
            "method": "randomized",
            "outcome_type": "continuous",
            "kpi": "outcome",
            "unit_column": "unit",
            "group_column": "arm",
            "treatment": "T",
            "control": "C",
            "baseline": 10,
            "standard_deviation": 2,
            "minimum_effect": 1,
            "population": "eligible units",
            "measurement_window": "fixed follow-up",
            "stop_rule": "fixed sample",
            "guardrails": ["quality"],
            "analysis_unit": design,
            **options,
        }
    )
    return {**plan_experiment(request), "artifact_id": "plan"}


def artifact(rows):
    return {"rows": rows, "artifact_id": "observations", "synthetic": True}


def test_paired_matches_scipy_and_preserves_original_lineage():
    p = plan("paired", pair_column="pair")
    control = np.arange(8) * 100 + 10
    treatment = control + np.array([1, 2, 0, 3, 1, 4, 2, 1])
    rows = [
        dict(unit=f"{i}-{arm}", pair=i, arm=arm, outcome=float(value))
        for i, values in enumerate(zip(control, treatment))
        for arm, value in zip(["C", "T"], values)
    ]
    a = artifact(rows)
    result = analyze_experiment(a, p)
    expected = ttest_rel(treatment, control)
    assert result["estimate"]["pvalue"] == pytest.approx(expected.pvalue)
    assert result["estimate"]["standard_error"] == pytest.approx(
        np.std(treatment - control, ddof=1) / np.sqrt(8)
    )
    assert result["sample_ratio_mismatch_pvalue"] is None
    assert result["independent_units"] == 8
    assert result["source_hashes"]["observations"]
    assert a == artifact(rows)
    rows.pop()
    with pytest.raises(MMMError, match="complete"):
        analyze_experiment(a, p)


def test_cluster_replication_does_not_manufacture_precision():
    p = plan("cluster", cluster_column="geo", randomization_unit="geo")
    rows = [
        dict(
            unit=f"{arm}-{i}-{j}",
            geo=f"{arm}-{i}",
            arm=arm,
            outcome=float(i * i + (1 if arm == "T" else 0)),
        )
        for arm in ["T", "C"]
        for i in range(6)
        for j in range(i + 1)
    ]
    result = analyze_experiment(artifact(rows), p)
    expanded = [{**r, "unit": r["unit"] + f"-{j}"} for r in rows for j in range(3)]
    duplicate = analyze_experiment(artifact(expanded), p)
    assert duplicate["estimate"] == result["estimate"]
    assert result["estimate"]["treatment_n"] == 6
    assert result["independent_units"] == 12
    rows.append(dict(unit="cross-arm", geo="T-0", arm="C", outcome=2))
    with pytest.raises(MMMError, match="arm"):
        analyze_experiment(artifact(rows), p)


@pytest.mark.parametrize(
    "design,options",
    [
        ("paired", {}),
        ("cluster", {}),
        ("paired", {"pair_column": "unit"}),
        ("independent", {"pair_column": "pair"}),
        ("cluster", {"cluster_column": "geo", "pair_column": "pair"}),
        ("paired", {"pair_column": "pair", "expected_treatment_fraction": 0.3}),
        ("paired", {"pair_column": "pair", "outcome_type": "binary"}),
        ("paired", {"pair_column": "pair", "cost_column": "cost"}),
        (
            "paired",
            {
                "pair_column": "pair",
                "guardrail_specs": {
                    "quality": {
                        "outcome_type": "binary",
                        "direction": "decrease",
                        "max_adverse_change": 0.1,
                    }
                },
            },
        ),
    ],
)
def test_unsupported_designs_abstain(design, options):
    with pytest.raises(MMMError):
        plan(design, **options)


@pytest.mark.parametrize(
    "key,value", [("pair", None), ("pair", True), ("pair", []), ("outcome", None)]
)
def test_incomplete_pairs_abstain_without_complete_case_selection(key, value):
    rows = [
        dict(unit="C", arm="C", pair="one", outcome=1),
        dict(unit="T", arm="T", pair="one", outcome=2),
    ]
    rows[0][key] = value
    with pytest.raises(MMMError, match="Complete"):
        analyze_experiment(artifact(rows), plan("paired", pair_column="pair"))


def test_zero_variance_pairs_do_not_produce_spurious_certainty():
    rows = [
        dict(unit=f"{i}-{arm}", pair=i, arm=arm, outcome=i + (arm == "T"))
        for i in range(6)
        for arm in ["C", "T"]
    ]
    with pytest.raises(MMMError, match="variance"):
        analyze_experiment(artifact(rows), plan("paired", pair_column="pair"))
