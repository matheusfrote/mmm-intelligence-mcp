"""Maintainer-only: freeze official Windows binary URLs and SHA256, without executing them."""

import csv
import hashlib
import io
import json
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def freeze(row):
    name, version = row["Package"], row["Version"]
    filename = f"{name}_{version}.zip"
    url = "https://cloud.r-project.org/bin/windows/contrib/4.5/" + filename
    cache = ROOT / "var/r-binary-cache" / filename
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
    rows = list(csv.DictReader((ROOT / "var/r-packages-with-tests.csv").open(encoding="utf-8")))
    with ThreadPoolExecutor(max_workers=4) as pool:
        locked = list(pool.map(freeze, rows))
    target = ROOT / "requirements/robyn-r-win-binaries.json"
    target.write_text(json.dumps({"r": "4.5.2", "packages": locked}, indent=2), encoding="utf-8")
    print(json.dumps({"packages": len(locked), "manifest": str(target)}))
