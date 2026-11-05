"""Storage contracts preserve all random variables and posterior samples."""

import pytest


def test_storage_io_failure_restores_the_original_in_memory_state(tmp_path):
    """Fault injection tests storage cleanup, never a fake sampler result."""
    from types import SimpleNamespace

    from mmm_intelligence.integrations.native_persistence import save_pymc_model

    class Posterior:
        data_vars = {
            "beta": SimpleNamespace(dims=("chain", "draw")),
            "mu": SimpleNamespace(dims=("chain", "draw", "date")),
        }

        def to_dataset(self):
            return self

        def drop_vars(self, names):
            assert names == ["mu"]
            return {"beta": "unchanged storage sentinel"}

    class Tree(dict):
        def copy(self, deep=False):
            assert not deep
            return Tree(self)

    original = Tree(posterior=Posterior())

    class FailedStorage:
        idata = original
        model = SimpleNamespace(free_RVs=[SimpleNamespace(name="beta")])

        def save(self, *args, **kwargs):
            assert self.idata is not original
            raise OSError("unit-only disk failure")

    model = FailedStorage()
    with pytest.raises(OSError):
        save_pymc_model(model, tmp_path / "output.nc", lambda tree: {})
    assert model.idata is original


def test_only_date_dependent_deterministics_may_be_recomputed():
    from mmm_intelligence.integrations.native_persistence import recomputable_variables

    dimensions = {
        "beta": ("chain", "draw", "channel"),
        "mu": ("chain", "draw", "date"),
        "random_walk": ("chain", "draw", "date"),
        "total": ("chain", "draw"),
    }
    assert recomputable_variables(dimensions, {"beta", "random_walk"}) == ["mu"]
    with pytest.raises(ValueError, match="free"):
        recomputable_variables(dimensions, {"missing_free_variable"})


def test_longer_sampling_budget_is_supported_without_relaxing_precision_policy():
    from mmm_intelligence.schemas import BackendRequest, ScientificProtocol

    assert (
        BackendRequest(dataset_id="data", backend="pymc_marketing", draws=4000, tune=2000).draws
        == 4000
    )
    assert ScientificProtocol().max_mcse_sd_ratio == 0.05
    assert ScientificProtocol().max_rhat == 1.01
