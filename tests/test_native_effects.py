"""Matched contrasts of conditional means, not differences of noisy observations."""

import numpy as np
import pytest


def test_native_effect_keeps_joint_draws_and_holdout_carryover():
    from mmm_intelligence.integrations.native_scientific import paired_effect

    base = np.random.default_rng(731).normal(size=(100, 20))
    scenario = base + np.arange(20)
    result = paired_effect(base, scenario, 10)
    assert result["estimate"] == 14.5
    assert result["lower"] == result["upper"] == 14.5
    assert result["interval_type"] == "posterior_conditional_effect"
    with pytest.raises(ValueError):
        paired_effect(base, scenario[:, :-1], 10)
