"""Maintainer-only: freeze official Windows binary URLs and SHA256, without executing them."""

import argparse
import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from install_r_binaries import binary_repository

ROOT = Path(__file__).resolve().parents[1]


def freeze(row, snapshot):
    name, version = row["Package"], row["Version"]
    filename = f"{name}_{version}.zip"
    url = binary_repository(snapshot) + filename
    cache = ROOT / "var/r-binary-cache" / snapshot / filename
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists():
        raw = cache.read_bytes()
    else:
        with urllib.request.urlopen(url, timeout=90) as response:
            raw = response.read(64 * 1024 * 1024 + 1)
        if len(raw) > 64 * 1024 * 1024:
            raise ValueError("Excessive package archive: " + name)
        cache.write_bytes(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        description = archive.read(name + "/DESCRIPTION").decode("utf-8")
        assert "Version: " + version in description.splitlines(), name
    return {
        "package": name,
        "version": version,
        "url": url,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--packages-csv", type=Path)
    options = parser.parse_args()
    binary_repository(options.snapshot)
    if options.packages_csv:
        with options.packages_csv.open(encoding="utf-8") as source:
            rows = list(csv.DictReader(source))
    else:
        manifest = json.loads((ROOT / "requirements/robyn-r-win-binaries.json").read_text())
        rows = [{"Package": p["package"], "Version": p["version"]} for p in manifest["packages"]]
    with ThreadPoolExecutor(max_workers=2) as pool:
        locked = list(pool.map(lambda row: freeze(row, options.snapshot), rows))
    target = ROOT / "requirements/robyn-r-win-binaries.json"
    target.write_text(
        json.dumps({"r": "4.5.2", "snapshot": options.snapshot, "packages": locked}, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"packages": len(locked), "manifest": str(target)}))
