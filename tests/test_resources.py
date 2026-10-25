import subprocess
import sys

import pytest

from mmm_intelligence.resources import run_worker


def test_limited_worker_completes(tmp_path):
    with (tmp_path / "worker.log").open("w") as log:
        result = run_worker(
            [sys.executable, "-c", "print('bounded')"],
            timeout=10,
            env=None,
            cwd=tmp_path,
            stdout=log,
        )
    assert result.returncode == 0
    assert "bounded" in (tmp_path / "worker.log").read_text()


def test_limited_worker_times_out_and_cleans_up(tmp_path):
    with (tmp_path / "worker.log").open("w") as log:
        with pytest.raises(subprocess.TimeoutExpired):
            run_worker(
                [sys.executable, "-c", "import time; time.sleep(10)"],
                timeout=0.1,
                env=None,
                cwd=tmp_path,
                stdout=log,
            )


def test_verbose_worker_output_is_drained_and_bounded(tmp_path):
    path = tmp_path / "verbose.log"
    with path.open("w", encoding="utf-8") as log:
        result = run_worker(
            [
                sys.executable,
                "-c",
                "import sys; sys.stdout.buffer.write(b'x'*2000000+b'END-OF-OUTPUT')",
            ],
            timeout=10,
            env=None,
            cwd=tmp_path,
            stdout=log,
        )
    assert result.returncode == 0
    content = path.read_bytes()
    assert len(content) <= 1_000_000
    assert b"truncated" in content and content.endswith(b"END-OF-OUTPUT")
