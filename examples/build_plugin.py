"""Build a deterministic, allowlisted local plugin ZIP. Does not install or publish."""

import argparse
import hashlib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "mmm-intelligence-local"


def members():
    paths = {p.relative_to(PLUGIN).as_posix(): p for p in PLUGIN.rglob("*") if p.is_file()}
    for name in ("LICENSE", "NOTICE"):
        paths[name] = ROOT / name
    source = ROOT / "src" / "mmm_intelligence"
    for path in source.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".R", ".js", ".css", ".html", ".svg"}:
            paths["server/mmm_intelligence/" + path.relative_to(source).as_posix()] = path
    for name, path in paths.items():
        if (
            path.is_symlink()
            or ".." in Path(name).parts
            or any(
                part.startswith(".") or part in {"__pycache__", "node_modules"}
                for part in Path(name).parts
            )
        ):
            raise ValueError("Unexpected plugin member")
        if path.suffix not in {
            ".py",
            ".R",
            ".json",
            ".md",
            ".js",
            ".css",
            ".html",
            ".svg",
        } and name not in {"LICENSE", "NOTICE"}:
            raise ValueError("Unapproved plugin file type")
    return paths


def build(destination):
    paths = members()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves prior artifacts. Stored entries avoid zlib-version drift.
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_STORED) as archive:
        for name, path in sorted(paths.items()):
            info = zipfile.ZipInfo(name, (2000, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    return hashlib.sha256(destination.read_bytes()).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=ROOT / "dist" / "mmm-intelligence-local-0.1.0.zip"
    )
    print(build(parser.parse_args().output))
