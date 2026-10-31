"""Sampling-budget labels never certify convergence; runtime versions are explicit."""


def test_sampling_warning_distinguishes_transport_from_analytical_budget():
    from mmm_intelligence.integrations.worker import sampling_warning

    assert "SHORT_CHAINS" in sampling_warning({"draws": 20, "tune": 20, "chains": 2})
    warning = sampling_warning({"draws": 1000, "tune": 1000, "chains": 4})
    assert "DIAGNOSTICS_REQUIRED" in warning
    assert "SHORT_CHAINS" not in warning


def test_missing_optional_runtime_versions_are_unavailable_not_invented():
    from mmm_intelligence.integrations.worker import runtime_versions

    actual = runtime_versions("pymc_marketing")
    assert actual["numpy"]
    assert "pymc" in actual


def test_r_child_timeout_respects_validated_parent_budget(monkeypatch):
    import pytest

    from mmm_intelligence.integrations.worker import r_timeout

    monkeypatch.delenv("MMM_BACKEND_TIMEOUT_SECONDS", raising=False)
    assert r_timeout() == 850
    monkeypatch.setenv("MMM_BACKEND_TIMEOUT_SECONDS", "3600")
    assert r_timeout() == 3550
    monkeypatch.setenv("MMM_BACKEND_TIMEOUT_SECONDS", "10")
    assert r_timeout() == 9
    monkeypatch.setenv("MMM_BACKEND_TIMEOUT_SECONDS", "3601")
    with pytest.raises(ValueError):
        r_timeout()
