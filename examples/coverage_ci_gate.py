"""Require the complete base matrix and three native captures before the gate."""

import json
from pathlib import Path

from coverage_gate import check

manifests = sorted(Path("var/coverage-downloads").rglob("manifest.json"))
records = [json.loads(p.read_text(encoding="utf-8")) for p in manifests]
expected = {
    f"base-{system}-{version}"
    for system in ["ubuntu-latest", "windows-latest", "macos-latest"]
    for version in ["3.11", "3.12", "3.13"]
}
assert expected <= {item.get("label") for item in records}, "Missing base matrix capture"
assert {"google_meridian", "pymc_marketing", "meta_robyn"} <= {
    item.get("backend") for item in records
}, "Missing native worker capture"
check(manifests, Path("evidence/python-coverage"))
