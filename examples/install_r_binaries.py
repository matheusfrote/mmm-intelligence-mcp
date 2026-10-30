"""Install only the exact official Windows archives in the reviewed SHA256 manifest."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def install(library, offline):
    manifest = json.loads(
        (ROOT / "requirements/robyn-r-win-binaries.json").read_text(encoding="utf-8")
    )
    cache = ROOT / "var/r-binary-cache"
    cache.mkdir(parents=True, exist_ok=True)

    def archive(record):
        assert re.fullmatch(r"[A-Za-z][A-Za-z0-9._]*", record["package"])
        assert re.fullmatch(r"[A-Za-z0-9.-]+", record["version"])
        name = record["package"] + "_" + record["version"] + ".zip"
        assert record["url"] == "https://cloud.r-project.org/bin/windows/contrib/4.5/" + name
        path = cache / name
        if not path.exists():
            if offline:
                raise FileNotFoundError(name)
            with urllib.request.urlopen(record["url"], timeout=120) as response:
                raw = response.read(64 * 1024 * 1024 + 1)
            if len(raw) > 64 * 1024 * 1024:
                raise ValueError("Excessive R archive")
            path.write_bytes(raw)
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("R archive checksum mismatch: " + name)
        return str(path).replace("\\", "/")

    with ThreadPoolExecutor(max_workers=4) as pool:
        files = list(pool.map(archive, manifest["packages"]))
    library = library.resolve()
    library.mkdir(parents=True, exist_ok=True)

    def vector(values):
        return "c(" + ",".join(json.dumps(value) for value in values) + ")"

    script = cache / ("install-" + uuid4().hex + ".R")
    script.write_text(
        "library_path <- "
        + json.dumps(str(library).replace("\\", "/"))
        + "\n.libPaths(c(library_path,.libPaths()))\ninstall.packages("
        + vector(files)
        + ",lib=library_path,repos=NULL,type='win.binary')\nexpected <- "
        + vector([p["version"] for p in manifest["packages"]])
        + "\nactual <- vapply("
        + vector([p["package"] for p in manifest["packages"]])
        + ",function(p) packageDescription(p,lib.loc=library_path,fields='Version'),character(1))\nstopifnot(all(unname(actual)==expected))\n",
        encoding="utf-8",
    )
    rscript = ROOT / "var/runtime/r-portable/R-4.5.2/bin/Rscript.exe"
    with tempfile.TemporaryDirectory(prefix="mmm-r-install-") as temporary:
        completed = subprocess.run(
            [str(rscript), "--vanilla", str(script)],
            cwd=ROOT,
            env={
                **os.environ,
                "R_USER": temporary,
                "TMPDIR": temporary,
                "TEMP": temporary,
                "TMP": temporary,
            },
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        print(completed.stdout[-100000:])
        print(completed.stderr[-100000:])
        completed.check_returncode()
    print(json.dumps({"packages_verified_and_installed": len(files), "library": str(library)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=ROOT / "var/runtime/r-library")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    install(args.library, args.offline)
