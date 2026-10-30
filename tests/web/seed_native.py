"""Seed actual synthetic native metadata for browser consultation contracts.

This does not train or certify a native engine. Native cycles test that separately.
"""

import json
import sys
from pathlib import Path

from mmm_intelligence.config import Settings
from mmm_intelligence.storage import ArtifactStore, digest

project = Path(__file__).resolve().parents[2]
fixture = json.loads((project / "tests/fixtures/dashboard-models.json").read_text())
assert fixture["synthetic"] is True
store = ArtifactStore(Settings(Path(sys.argv[1]) / "dashboard"))
item = fixture["models"]["pymc_marketing"]
assert item["dataset"]["synthetic"] is True and item["model"]["synthetic"] is True
assert digest(item["dataset"]) == item["model"]["dataset_sha256"]
store.write("datasets", item["model"]["dataset_id"], item["dataset"])
store.write(
    "backend_models", item["model"]["model_id"], {**item["model"], "dataset": item["dataset"]}
)
print(
    json.dumps(
        {
            "dataset_id": item["model"]["dataset_id"],
            "model_id": item["model"]["model_id"],
            "mae": item["analysis"]["metrics"]["mae"],
        }
    )
)
