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
