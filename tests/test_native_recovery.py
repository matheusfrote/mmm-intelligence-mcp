"""Native recovery studies retain execution failures, never substitute Ridge."""

import copy
import json
from pathlib import Path

import pytest


def policy_fixture():
    """Analytical acceptance-policy inputs only; no engine fit or convergence claim."""
    from mmm_intelligence.monte_carlo import summarize_records

    records = []
    for scenario in ["well_specified", "null_effect"]:
        for i in range(100):
            records.append(
                {
                    "scenario": scenario,
                    "status": "executed",
                    "model_id": f"policy-only-{scenario}-{i}",
                    "effects": {
                        channel: {
                            "estimate": 0.0,
                            "truth": 0.0,
                            "lower": 0.0,
                            "upper": 1.0,
                            "available": True,
                        }
                        for channel in ["spend_search", "spend_social", "spend_video"]
                    },
                    "numerical_screen": {
                        "status": "adequate_for_screened_diagnostics",
                        "mcse_sd_ratio_max": 0.01,
                    },
                    "posterior_predictive_check": {"discrepancy_flags": []},
                }
            )
    return {
        "replications": records,
        "summaries": summarize_records(
            records, ["well_specified", "null_effect"], "native_conditional_effect"
        ),
        "operational": {"failures": 0},
        "fixture_scope": "Policy math only, not native inference evidence",
    }


def test_complete_policy_inputs_never_imply_causal_certification():
    from mmm_intelligence.native_recovery import assess_native_study
    from mmm_intelligence.schemas import NativeRecoveryProtocol

    result = assess_native_study(
        policy_fixture(),
        "pymc_marketing",
        NativeRecoveryProtocol(replications=100, max_absolute_bias=0, max_rmse=0),
    )
    assert result["acceptance"]["status"] == "passed_for_studied_DGPs"
    assert result["acceptance"]["causal_identification"] is False


def test_repeated_fit_ids_are_not_independent_monte_carlo_replications():
    from mmm_intelligence.native_recovery import assess_native_study
    from mmm_intelligence.schemas import NativeRecoveryProtocol

    report = policy_fixture()
    for row in report["replications"]:
        row["model_id"] = "repeated-fit"
    result = assess_native_study(
        report,
        "pymc_marketing",
        NativeRecoveryProtocol(replications=100, max_absolute_bias=0, max_rmse=0),
    )
    assert result["acceptance"]["status"] == "inconclusive"
    assert "non_independent_replicates" in result["acceptance"]["missing"]


def test_real_robyn_search_warnings_are_not_mcmc_and_missing_trace_abstains():
    from mmm_intelligence.native_recovery import assess_native_study
    from mmm_intelligence.schemas import NativeRecoveryProtocol

    traces = json.loads(
        (Path(__file__).parent / "fixtures/native-robyn-search-traces.json").read_text()
    )
    assert traces["synthetic"]
    for run in traces["runs"]:
        report = {
            "replications": [
                {
                    "status": "executed",
                    "scenario": "well_specified",
                    "model_id": run["model_id"],
                    "diagnostics": run["diagnostics"],
                    "numerical_screen": {"status": "not_applicable"},
                }
            ],
            "summaries": [],
            "operational": {"failures": 0},
        }
        result = assess_native_study(report, "meta_robyn", NativeRecoveryProtocol())
        assert any(v.startswith("native_search_warning:") for v in result["acceptance"]["failed"])
        assert not any("mcmc_failed" in v for v in result["acceptance"]["failed"])
        report["replications"][0]["diagnostics"] = {"optimization_trace": []}
        result = assess_native_study(report, "meta_robyn", NativeRecoveryProtocol())
        assert any(
            v.startswith("missing_native_optimization_trace")
            for v in result["acceptance"]["missing"]
        )
        assert result["acceptance"]["status"] == "inconclusive"


@pytest.mark.parametrize(
    "change,flag",
    [
        ({"mcse_sd_ratio_max": None}, "missing_native_mcse"),
        ({"mcse_sd_ratio_max": 0.2}, "native_mcse_failed"),
        ({"undefined_mcse_count": 1}, "undefined_native_mcse"),
        ({"status": "inadequate"}, "native_mcmc_failed"),
    ],
)
def test_incomplete_or_failed_precision_in_recorded_evidence_never_approves(change, flag):
    from mmm_intelligence.native_recovery import assess_native_study
    from mmm_intelligence.schemas import NativeRecoveryProtocol

    report = json.loads(
        (Path(__file__).parent / "fixtures/native-recovery-meridian.json").read_text()
    )
    report["replications"][0]["numerical_screen"].update(change)
    result = assess_native_study(
        report, "google_meridian", NativeRecoveryProtocol.model_validate(report["configuration"])
    )
    assert any(
        v.startswith(flag) for v in result["acceptance"]["missing"] + result["acceptance"]["failed"]
    )
    assert result["acceptance"]["status"] != "passed_for_studied_DGPs"


def test_recorded_predictive_discrepancy_remains_a_failure():
    from mmm_intelligence.native_recovery import assess_native_study
    from mmm_intelligence.schemas import NativeRecoveryProtocol

    report = json.loads(
        (Path(__file__).parent / "fixtures/native-recovery-meridian.json").read_text()
    )
    report["replications"][0]["posterior_predictive_check"]["discrepancy_flags"] = [
        "unit contract mutation"
    ]
    result = assess_native_study(
        report, "google_meridian", NativeRecoveryProtocol.model_validate(report["configuration"])
    )
    assert any(
        v.startswith("native_predictive_discrepancy") for v in result["acceptance"]["failed"]
    )


def test_expected_adversarial_rejections_are_distinct_from_worker_failures():
    from mmm_intelligence.native_recovery import assess_native_study
    from mmm_intelligence.schemas import NativeRecoveryProtocol

    report = json.loads(
        (Path(__file__).parent / "fixtures/native-recovery-meridian.json").read_text()
    )
    result = assess_native_study(
        report, "google_meridian", NativeRecoveryProtocol.model_validate(report["configuration"])
    )
    assert result["operational"]["expected_rejections"] == 4
    assert result["operational"]["unexpected_failures"] == 0
    assert result["operational"]["protocol_executed"]
    assert not result["operational"]["all_executed"]  # Four invalid datasets were not fitted.
    assert "incomplete_native_execution" not in result["acceptance"]["missing"]


def test_missing_native_runtime_is_recorded_without_invented_effects(
    service, monkeypatch, tmp_path
):
    from mmm_intelligence.native_recovery import run_native_study
    from mmm_intelligence.schemas import NativeRecoveryProtocol

    monkeypatch.setenv("MMM_PYMC_PYTHON", str(tmp_path / "unavailable.exe"))
    result = run_native_study(service, "pymc_marketing", NativeRecoveryProtocol(replications=2))
    assert result["attempted"] == 4
    assert all(row["status"] == "failed" for row in result["replications"])
    assert {row["code"] for row in result["replications"]} == {"BACKEND_UNAVAILABLE"}
    assert not result["operational"]["all_executed"]
    assert result["acceptance"]["status"] != "passed_for_studied_DGPs"
    assert all(row["interval_coverage"] is None for row in result["summaries"])


def test_generator_retains_date_specific_truth_for_native_temporal_rounding():
    from mmm_intelligence.monte_carlo import generate_dgp
    from mmm_intelligence.schemas import MonteCarloProtocol

    data, truth = generate_dgp(MonteCarloProtocol(), 99109, "well_specified")
    assert len(truth["effect_by_date"]["spend_search"]) == len(data["rows"])


def test_unknown_engine_and_excessive_batch_fail_before_workers(service):
    import pytest

    from mmm_intelligence.errors import MMMError
    from mmm_intelligence.native_recovery import run_native_study
    from mmm_intelligence.schemas import NativeRecoveryProtocol

    with pytest.raises(MMMError, match="native engine"):
        run_native_study(service, "ridge", NativeRecoveryProtocol())
    with pytest.raises(MMMError, match="200"):
        run_native_study(
            service,
            "google_meridian",
            NativeRecoveryProtocol(
                replications=100, scenarios=["well_specified", "null_effect", "collinear"]
            ),
        )


def test_effect_contract_uses_exact_known_dates_and_rejects_corruption():
    import pytest

    from mmm_intelligence.errors import MMMError
    from mmm_intelligence.native_recovery import evaluate_effects

    truth = {"effect_by_date": {"channel": {"a": 2.0, "b": 4.0}}}
    native = {
        "effects": {"channel": {"estimate": 3.0, "available": True, "lower": 1.0, "upper": 5.0}}
    }
    result = evaluate_effects(["a", "b"], ["channel"], native, truth)
    assert result["channel"]["truth"] == 3 and result["channel"]["covered"]
    for dates in [[], ["a", "a"], ["outside"]]:
        with pytest.raises(MMMError, match="window"):
            evaluate_effects(dates, ["channel"], native, truth)
    for change in [
        {"estimate": None},
        {"estimate": float("nan")},
        {"lower": float("inf")},
        {"lower": 6},
        {"estimate": True},
        {"estimate": "invalid"},
        {"available": "false"},
        {"lower": None},
        {"lower": True},
    ]:
        corrupted = copy.deepcopy(native)
        corrupted["effects"]["channel"].update(change)
        with pytest.raises(MMMError):
            evaluate_effects(["a"], ["channel"], corrupted, truth)
    with pytest.raises(MMMError):
        evaluate_effects(["a"], ["channel"], {}, truth)
    native["effects"]["channel"].update(available=False, lower=None, upper=None)
    assert not evaluate_effects(["b"], ["channel"], native, truth)["channel"]["covered"]


def test_incomplete_robyn_objectives_cannot_pass_primary_or_recovery_policy():
    from mmm_intelligence.native_recovery import assess_native_study
    from mmm_intelligence.schemas import NativeRecoveryProtocol
    from mmm_intelligence.validation import search_assessment

    # Truncate actual native traces; this tests missing evidence, not a fake fit.
    source = json.loads(
        (Path(__file__).parent / "fixtures/native-robyn-search-traces.json").read_text()
    )
    diagnostics = copy.deepcopy(source["runs"][0]["diagnostics"])
    diagnostics["optimization_trace"] = [
        row for row in diagnostics["optimization_trace"] if row["error_type"] == "NRMSE"
    ]
    assert (
        "native_optimization_objectives"
        in search_assessment({"diagnostics": diagnostics})["missing"]
    )
    report = {
        "replications": [
            {
                "scenario": "well_specified",
                "status": "executed",
                "model_id": "truncated-native-evidence",
                "diagnostics": diagnostics,
            }
        ],
        "summaries": [],
        "operational": {},
    }
    result = assess_native_study(report, "meta_robyn", NativeRecoveryProtocol())
    assert (
        "missing_native_optimization_objectives:truncated-native-evidence"
        in result["acceptance"]["missing"]
    )
