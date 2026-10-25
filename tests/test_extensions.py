import inspect

from mmm_intelligence.integrations import CAPABILITIES, PLANNED_CAPABILITIES
from mmm_intelligence.integrations.contracts import (
    DashboardRenderer,
    InvestmentOptimizer,
    ModelBackend,
    ReportRenderer,
)


def test_future_contracts_do_not_claim_working_integrations():
    assert len(CAPABILITIES) == 6
    assert not PLANNED_CAPABILITIES
    assert CAPABILITIES["meta_robyn"] == "implemented_optional_runtime"
    assert set(inspect.signature(ModelBackend.fit).parameters) == {"self", "data", "options"}
    assert callable(InvestmentOptimizer.optimize)
    assert callable(DashboardRenderer.render)
    assert callable(ReportRenderer.render)
