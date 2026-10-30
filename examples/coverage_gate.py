"""Record source provenance and enforce exact aggregate Python line/branch coverage.

Only coverage files listed in inspected manifests are combined. Old captures with
different Python source hashes cannot contribute to the acceptance result.
"""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import coverage

ROOT = Path(__file__).resolve().parents[1]


def sources():
    return sorted((ROOT / "src/mmm_intelligence").rglob("*.py")) + [
        ROOT / "server.py",
        ROOT / "plugins/mmm-intelligence-local/launch.py",
    ]


def hashes():
    return {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sources()
    }


def record(directory, label):
    directory = directory.resolve()
    files = sorted(p for p in directory.glob(".coverage*") if p.is_file())
    if not files:
        raise ValueError("No new coverage data to record")
    manifest = {
        "label": label,
        "python": platform.python_version(),
        "coverage": coverage.__version__,
        "source_sha256": hashes(),
        "coverage_files": [p.name for p in files],
    }
    target = directory / "manifest.json"
    target.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(target)


def check(manifests, output):
    current = hashes()
    captures = []
    for manifest_path in manifests:
        manifest_path = manifest_path.resolve()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        recorded = {
            key: value for key, value in manifest["source_sha256"].items() if key.endswith(".py")
        }
        if not recorded:
            raise ValueError("Missing source hashes: " + str(manifest_path))
        for name in manifest["coverage_files"]:
            path = (manifest_path.parent / name).resolve()
            if not path.is_relative_to(manifest_path.parent) or not path.is_file():
                raise ValueError("Invalid coverage input path")
            measured = coverage.CoverageData(basename=str(path))
            measured.read()
            for filename in measured.measured_files():
                if not measured.lines(filename):
                    continue  # An unexecuted source entry contributes no lines or arcs.
                normalized = filename.replace("\\", "/")
                # Package aliases take priority over the generic root server.py
                # suffix, which also occurs in the package's server module.
                marker = "plugin/server/mmm_intelligence/"
                if normalized.startswith(marker) or "/" + marker in normalized:
                    matches = ["src/mmm_intelligence/" + normalized.split(marker, 1)[1]]
                elif normalized == "plugin/launch.py" or normalized.endswith("/plugin/launch.py"):
                    matches = ["plugins/mmm-intelligence-local/launch.py"]
                else:
                    matches = sorted(
                        [
                            key
                            for key in current
                            if normalized == key or normalized.endswith("/" + key)
                        ],
                        key=len,
                        reverse=True,
                    )[:1]
                if (
                    len(matches) != 1
                    or matches[0] not in current
                    or recorded.get(matches[0]) != current[matches[0]]
                ):
                    raise ValueError("Executed source changed since capture: " + filename)
            captures.append(str(path))
    if not captures:
        raise ValueError("No coverage captures")
    output.mkdir(parents=True, exist_ok=True)
    cov = coverage.Coverage(
        config_file=str(ROOT / "pyproject.toml"), data_file=str(output / ".coverage")
    )
    if any(Path(path).parent == output.resolve() for path in captures):
        raise ValueError("Aggregate output must be separate from immutable input captures")
    cov.erase()
    cov.combine(data_paths=captures, strict=True, keep=True)
    # Explicit complete denominator, including both first-party launchers.
    cov.get_data().touch_files([str(p.relative_to(ROOT)) for p in sources()])
    cov.save()
    cov.json_report(outfile=str(output / "coverage.json"))
    cov.html_report(directory=str(output / "html"))
    report = json.loads((output / "coverage.json").read_text(encoding="utf-8"))
    totals = report["totals"]
    result = {
        "source_sha256": current,
        "manifests": [str(p) for p in manifests],
        "lines_covered": totals["covered_lines"],
        "lines_total": totals["num_statements"],
        "branches_covered": totals["covered_branches"],
        "branches_total": totals["num_branches"],
    }
    (output / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result | {"source_sha256": "recorded in result.json"}))
    if totals["missing_lines"] or totals["missing_branches"]:
        raise SystemExit("100% of executable lines AND branches required; inspect coverage.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("record")
    capture.add_argument("--directory", type=Path, required=True)
    capture.add_argument("--label", required=True)
    gate = commands.add_parser("check")
    gate.add_argument("--manifest", type=Path, action="append", required=True)
    gate.add_argument("--output", type=Path, default=Path("evidence/python-coverage"))
    args = parser.parse_args()
    if args.command == "record":
        record(args.directory, args.label)
    else:
        check(args.manifest, args.output)


if __name__ == "__main__":
    main()
