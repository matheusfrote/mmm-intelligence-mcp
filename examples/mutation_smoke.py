"""Selective real-test mutation check in disposable copies; never edits production."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CASES = [
    (
        "normalized_adstock",
        "modeling.py",
        "(1 - decay) * value + decay * state",
        "value + decay * state",
        "tests/test_modeling.py::test_adstock_hand_calculation_continuity_and_time_direction",
    ),
    (
        "hill_denominator",
        "modeling.py",
        "return x / (half_saturation + x)",
        "return x / (half_saturation + 2 * x)",
        "tests/test_modeling.py::test_hill_half_saturation_monotonicity_and_concavity",
    ),
    (
        "complete_cohort_window",
        "growth_analytics.py",
        "if end <= as_of + timedelta(days=1):",
        "if end < as_of + timedelta(days=1):",
        "tests/test_growth_analytics.py::test_cohort_eligibility_does_not_mark_censored_units_lost",
    ),
    (
        "effect_direction",
        "experiments.py",
        "difference = m1 - m0",
        "difference = m0 - m1",
        "tests/test_growth_analytics.py::test_binary_experiment_estimate_and_power_are_not_causal_proof",
    ),
    (
        "duplicate_parquet_columns",
        "file_readers.py",
        "if len(set(file.schema_arrow.names)) != len(file.schema_arrow.names):",
        "if False:",
        "tests/test_reader_edges.py::test_parquet_dates_decimal_null_and_duplicate_names",
    ),
]


def run(output):
    project = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=False)
    scratch = project / "var/mutation-copies"
    scratch.mkdir(parents=True, exist_ok=True)
    baseline_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COVERAGE_", "COV_CORE_"))
    }

    def check(source, tests):
        environment = {
            **baseline_env,
            "PYTHONPATH": os.pathsep.join([str(source), str(project / "tests")]),
            "MMM_MUTATION_SOURCE": str(source.resolve()),
        }
        guard = source / "mutation_guard.py"
        guard.write_text(
            "import os\nfrom pathlib import Path\nimport mmm_intelligence\ndef pytest_sessionstart(session):\n assert Path(mmm_intelligence.__file__).resolve().is_relative_to(Path(os.environ['MMM_MUTATION_SOURCE']))\n",
            encoding="utf-8",
        )
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "mutation_guard",
                "-p",
                "no:cov",
                "-o",
                "cache_dir=var/mutation-cache",
                *tests,
            ],
            cwd=project,
            env=environment,
            capture_output=True,
            text=True,
            timeout=120,
        )

    # The same tests must pass before mutation, from a verified fresh package copy.
    baseline = Path(tempfile.mkdtemp(prefix="baseline-", dir=scratch))
    shutil.copytree(
        project / "src/mmm_intelligence",
        baseline / "mmm_intelligence",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    result = check(baseline, [case[4] for case in CASES])
    (output / "baseline.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, "Mutation baseline failed; inspect baseline.log"
    receipts = []
    for name, filename, before, after, test in CASES:
        root = Path(tempfile.mkdtemp(prefix=name + "-", dir=scratch))
        shutil.copytree(
            project / "src/mmm_intelligence",
            root / "mmm_intelligence",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        path = root / "mmm_intelligence" / filename
        original = path.read_text(encoding="utf-8")
        assert original.count(before) == 1, name
        path.write_text(original.replace(before, after, 1), encoding="utf-8")
        result = check(root, [test])
        log = result.stdout + result.stderr
        (output / (name + ".log")).write_text(log, encoding="utf-8")
        killed = result.returncode == 1 and "FAILED tests" in log and "ERROR collecting" not in log
        receipts.append({"mutation": name, "file": filename, "test": test, "detected": killed})
    receipt = {
        "selective_only": True,
        "production_modified": False,
        "baseline_passed": True,
        "mutations": receipts,
        "detected": sum(row["detected"] for row in receipts),
        "total": len(receipts),
    }
    (output / "result.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))
    assert all(row["detected"] for row in receipts), (
        "A targeted mutation survived; inspect its test"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    run(parser.parse_args().output_dir.resolve())
