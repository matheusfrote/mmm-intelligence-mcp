"""Conditional inference abstains on invalid designs; errors never become certainty."""

import numpy as np
import pytest

from mmm_intelligence.inference import fit_linear_inference, linear_contrast


@pytest.mark.parametrize(
    "x,y,lags",
    [
        ([1, 2], [1, 2], 0),
        ([[1, 0], [1, 1]], [1], 0),
        ([[1], [1]], [1, 2], 0),
        ([[1, 0], [1, np.nan]], [1, 2], 0),
        ([[1, 0], [1, 1]], [1, np.inf], 0),
        ([[0, 0], [0, 1]], [1, 2], 0),
        ([[1, 0], [1, 1]], [1, 2], 0.5),
        ([[1, 0], [1, 1]], [1, 2], 2),
    ],
)
def test_invalid_designs_fail_explicitly(x, y, lags):
    with pytest.raises(ValueError):
        fit_linear_inference(x, y, lags)


def test_insufficient_df_and_extreme_leverage_abstain():
    assert fit_linear_inference([[1, 0], [1, 1]], [1, 2], 0)["reason"].startswith("insufficient")
    x = np.column_stack([np.ones(20), np.r_[1, np.zeros(19)]])
    fitted = fit_linear_inference(x, np.arange(20))
    assert fitted == {"available": False, "reason": "extreme_leverage"}
    assert not linear_contrast(fitted, [0, 1])["available"]


def test_hac_differs_from_hc3_on_serial_errors_and_contrasts_are_checked():
    rng = np.random.default_rng(91)
    x = np.column_stack([np.ones(100), np.linspace(0, 1, 100)])
    y = 2 + x[:, 1] + np.convolve(rng.normal(size=103), np.ones(4), mode="valid")
    fitted = fit_linear_inference(x, y)
    hc3 = linear_contrast(fitted, [0, 1])
    hac = linear_contrast(fitted, [0, 1], covariance="hac")
    assert hac["standard_error"] > hc3["standard_error"]
    for vector, covariance in [([1], "hc3"), ([0, np.nan], "hc3"), ([0, 1], "unsupported")]:
        with pytest.raises(ValueError):
            linear_contrast(fitted, vector, covariance=covariance)
