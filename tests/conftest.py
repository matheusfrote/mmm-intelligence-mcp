import pytest

from mmm_intelligence.config import Settings
from mmm_intelligence.datasets import generate
from mmm_intelligence.schemas import GenerateRequest, ModelRequest
from mmm_intelligence.service import MMMService


@pytest.fixture
def dataset():
    return generate(GenerateRequest())


@pytest.fixture
def service(tmp_path):
    svc = MMMService(Settings(tmp_path / "artifacts"))
    yield svc
    svc.close()


@pytest.fixture
def trained(service):
    assert service.call("generate_demo_dataset", {"dataset_id": "demo"}).ok
    result = service.call("train_mmm", {"dataset_id": "demo", "model_id": "fit"})
    assert result.ok, result.error
    return service.get_model(ModelRequest(model_id="fit"))
