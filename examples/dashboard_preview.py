"""Seed the isolated local dashboard with synthetic data; no token configuration."""

import os

from mmm_intelligence.cli import main
from mmm_intelligence.config import Settings
from mmm_intelligence.http_transport import TenantRouter

if __name__ == "__main__":
    router = TenantRouter(Settings.from_env(), {})
    try:
        for service in [router.dashboard_service]:
            if not service.store.path("datasets", "preview-demo").exists():
                assert service.call("generate_demo_dataset", {"dataset_id": "preview-demo"}).ok
            if not service.store.path("models", "preview-fit").exists():
                result = service.call(
                    "train_mmm",
                    {
                        "dataset_id": "preview-demo",
                        "model_id": "preview-fit",
                        "bootstrap_samples": 100,
                    },
                )
                assert result.ok, result.error
    finally:
        router.close()
    main(["dashboard", "--port", os.getenv("MMM_PORT", "8769")])
