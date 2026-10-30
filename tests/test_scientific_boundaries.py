"""Short histories and mismatched evidence cannot bypass scientific abstention."""

from copy import deepcopy

import pytest

from mmm_intelligence.analysis import calibrate, tune
from mmm_intelligence.datasets import generate, validate
from mmm_intelligence.errors import MMMError
from mmm_intelligence.modeling import train
from mmm_intelligence.schemas import (
    AuditRequest,
    CalibrationRequest,
    GenerateRequest,
    TrainRequest,
    TuneRequest,
)
from mmm_intelligence.scientific import audit, backtest, decision_support, decomposition
from mmm_intelligence.storage import digest


def small(periods=64):
    return generate(GenerateRequest(periods=periods))


def calibration(**changes):
    return CalibrationRequest(
        **{
            "model_id": "fit",
            "channel": "spend_search",
            "treatment_spend": 100.0,
            "control_spend": 0.0,
            "lift_mean": 1.0,
            "lift_sd": 1.0,
            "experiment_id": "synthetic-study",
            "synthetic": True,
            **changes,
        }
    )


def test_calibration_rejects_unknown_channel_absent_uncertainty_and_no_contrast(trained):
    for model, request, code in [
        (trained, calibration(channel="unknown"), "CHANNEL_MISMATCH"),
        (trained, calibration(), "UNCERTAINTY_REQUIRED"),
        ({**trained, "coefficient_draws": [[0.0] * 9] * 19}, calibration(), "UNCERTAINTY_REQUIRED"),
        (
            {**trained, "coefficient_draws": [[0.0] * 9] * 20},
            calibration(treatment_spend=0.0),
            "UNINFORMATIVE_EXPERIMENT",
        ),
    ]:
        with pytest.raises(MMMError) as caught:
            calibrate(model, request)
        assert caught.value.code == code


def test_tuning_refuses_insufficient_pretest_history_without_using_outer_holdout():
    with pytest.raises(MMMError) as caught:
        tune(small(), TuneRequest(dataset_id="data", decays=[0.5], multipliers=[1.0]), "fit", 10000)
    assert caught.value.code == "INSUFFICIENT_TUNING_HISTORY"


def test_legacy_missing_diagnostics_or_no_holdout_improvement_abstains():
    support = decision_support(
        {
            "synthetic": False,
            "metrics": {"test": {"mae": 5}, "test_train_mean_baseline": {"mae": 4}},
        }
    )
    assert {
        "SCIENTIFIC_DIAGNOSTICS_UNAVAILABLE",
        "NO_HOLDOUT_IMPROVEMENT_OVER_MEAN_BASELINE",
    } <= set(support["reasons"])
    assert support["business_recommendation_eligible"] is False


def test_decomposition_mismatch_and_corrupt_draws_are_refused(service, trained):
    dataset = service.load_dataset("demo")
    model = deepcopy(trained)
    model["predictions"][0]["predicted"] += 1e6
    with pytest.raises(MMMError) as caught:
        decomposition(dataset, model)
    assert caught.value.code == "DECOMPOSITION_MISMATCH"
    model = deepcopy(trained)
    model["coefficient_draws"] = [[1.0]]
    with pytest.raises(MMMError) as caught:
        decomposition(dataset, model)
    assert caught.value.code == "CORRUPT_MODEL"


def test_backtest_short_history_and_unsupported_fold_windows_abstain(trained):
    assert (
        backtest({**small(), "rows": small()["rows"][:40]}, trained, 3)["status"]
        == "insufficient_history"
    )
    model = deepcopy(trained)
    model["request"]["warmup_periods"] = 52
    result = backtest(small(104), model, 5)
    assert result["status"] == "insufficient_history" and "proportions" in result["reason"]
    result = backtest(small(), trained, 5)
    assert result["status"] == "insufficient_history"


def test_backtest_reselects_tuning_or_propagates_other_domain_failures(trained):
    model = deepcopy(trained)
    model["shape_selection"] = {"rankings": [{"decay": 0.5, "saturation_multiplier": 1.0}]}
    result = backtest(small(), model, 1)
    assert result["status"] == "insufficient_history" and "Nested" in result["reason"]
    data = small(156)
    for row in data["rows"]:
        row["spend_search"] = 100.0
    with pytest.raises(MMMError) as caught:
        backtest(data, model, 2)
    assert caught.value.code == "UNIDENTIFIABLE_MEDIA"


def test_audit_checks_lineage_quality_and_reports_unavailable_backtest(service, trained):
    dataset = service.load_dataset("demo")
    changed = deepcopy(dataset)
    changed["rows"][0]["revenue"] = -1
    with pytest.raises(MMMError) as caught:
        audit(changed, trained, AuditRequest(model_id="fit"), 10000)
    assert caught.value.code == "LINEAGE_MISMATCH"
    with pytest.raises(MMMError) as caught:
        audit(
            changed,
            {**trained, "dataset_sha256": digest(changed)},
            AuditRequest(model_id="fit"),
            10000,
        )
    assert caught.value.code == "DATASET_INVALID"
    short = small()
    request = TrainRequest(dataset_id="short")
    fitted = train(short, request, "short", validate(short, request, 10000))
    report = audit(
        short,
        fitted,
        AuditRequest(model_id="short", folds=5, decays=[0.5], multipliers=[1.0]),
        10000,
    )
    assert "BACKTEST_UNAVAILABLE" in report["decision_support"]["reasons"]
