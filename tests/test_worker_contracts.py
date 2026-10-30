"""Test adapter compatibility and failed external diagnostics as such, not native success."""

import sys
from types import SimpleNamespace

import numpy as np
import pytest

from mmm_intelligence.integrations import worker


def test_original_scale_compatibility_initializes_once():
    class NativeModelBoundary:
        def __init__(self):
            self.model = SimpleNamespace(named_vars={"y": object()})

        def add_original_scale_contribution_variable(self, var):
            assert var == ["y"]
            self.model.named_vars["y_original_scale"] = "original units"

    model = NativeModelBoundary()
    worker.ensure_original_scale(model)
    assert model.model.named_vars["y_original_scale"] == "original units"
    worker.ensure_original_scale(model)
    assert len(model.model.named_vars) == 2


def test_restoration_requires_numerical_equality():
    worker.verify_restoration(np.array([[1.0, 2.0]]), [[1.0, 2.0 + 1e-10]], "test", 1e-7)
    with pytest.raises(ValueError, match="persistence changed"):
        worker.verify_restoration([[1.0, 2.0]], [[1.0, 3.0]], "test", 1e-7)


def test_meridian_placeholder_overflow_is_a_clear_input_error():
    with pytest.raises(ValueError, match="placeholder exceeds"):
        worker.prepare_meridian_holdout(
            {"target_type": "revenue", "rows": [{"y": 1e308}] * 5},
            {"target_column": "y", "test_fraction": 0.2},
        )


def test_meridian_external_summary_failure_preserves_abstention(monkeypatch):
    def unavailable(*args, **kwargs):
        raise ValueError("external diagnostics unavailable")

    monkeypatch.setitem(sys.modules, "arviz", SimpleNamespace(summary=unavailable))
    result = worker.meridian_diagnostics(SimpleNamespace(), {"chains": 2, "draws": 20, "tune": 20})
    assert result["summary_available"] is False
    assert result["convergence_certified"] is False
    assert "unavailable" in result["summary_unavailable_reason"]
