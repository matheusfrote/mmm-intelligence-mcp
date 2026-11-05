"""Run fixed local engine workers, with independent environments and bounded time."""

import json
import os

# Only fixed worker argv and operator configuration, never client commands.
import subprocess  # nosec B404
import tempfile
from contextlib import ExitStack
from pathlib import Path
from uuid import uuid4

from ..errors import MMMError
from ..resources import run_worker
from ..storage import reject_links


def configured_r_library() -> Path:
    """Host-only configuration; installed wheels need not contain local runtimes."""
    default = Path(__file__).resolve().parents[3] / "var/runtime/r-library"
    library = Path(os.environ.get("MMM_R_LIBRARY", str(default)))
    if "MMM_R_LIBRARY" in os.environ and not library.is_dir():
        raise MMMError("INVALID_CONFIG", "Configured R library directory is unavailable")
    return library.resolve()


def executable(backend: str) -> Path:
    if backend not in {"google_meridian", "pymc_marketing", "meta_robyn"}:
        raise MMMError("UNKNOWN_BACKEND", "Unknown modeling backend")
    name = {"google_meridian": "meridian", "pymc_marketing": "pymc", "meta_robyn": "robyn"}[backend]
    default = (
        Path(__file__).resolve().parents[3]
        / "var"
        / "envs"
        / name
        / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    return Path(os.environ.get("MMM_" + name.upper() + "_PYTHON", str(default)))


def worker_environment() -> dict[str, str]:
    """Inherit OS/runtime locations, never the host's unrelated credentials or tokens."""
    allowed = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "SYSTEMDRIVE",
        "PATHEXT",
        "USERPROFILE",
        "HOMEDRIVE",
        "HOMEPATH",
        "HOME",
        "APPDATA",
        "LOCALAPPDATA",
        "TEMP",
        "TMP",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "TZ",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "NUMBER_OF_PROCESSORS",
        "PROCESSOR_ARCHITECTURE",
        "MMM_RSCRIPT",
    }
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


def retain_failure(store, root, reason, returncode=None):
    """Preserve bounded private diagnostics before temporary jobs are removed."""
    destination = root / "output.json"
    record = {
        "reason": reason,
        "worker_exit_code": returncode,
        "output_bytes": destination.stat().st_size if destination.is_file() else None,
        "result_limit_bytes": store.settings.max_file_bytes,
    }
    diagnostics = store.root / "logs" / ("backend-" + uuid4().hex + ".log")
    reject_links(diagnostics)
    with diagnostics.open("xb") as output:
        output.write((json.dumps(record) + "\n").encode())
        with (root / "worker.log").open("rb") as source:
            source.seek(0, 2)
            source.seek(max(0, source.tell() - 1_000_000))
            output.write(source.read(1_000_000))
    return diagnostics.name


def execute(store, backend: str, payload: dict) -> dict:
    python = executable(backend)
    if not python.is_file():
        raise MMMError(
            "BACKEND_UNAVAILABLE", "Backend runtime is not installed/configured: " + backend
        )
    jobs = store.root / "jobs"
    reject_links(jobs)
    jobs.mkdir(exist_ok=True)
    timeout = int(os.environ.get("MMM_BACKEND_TIMEOUT_SECONDS", "900"))
    if not 10 <= timeout <= 3600:
        raise MMMError("INVALID_CONFIG", "Backend timeout must be between 10 and 3600 seconds")
    with tempfile.TemporaryDirectory(prefix="job-", dir=jobs) as task, ExitStack() as resources:
        root = Path(task)
        source, destination = root / "input.json", root / "output.json"
        source.write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")
        env = {
            **worker_environment(),
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "TF_NUM_INTRAOP_THREADS": "1",
            "TF_NUM_INTEROP_THREADS": "1",
            "TF_CPP_MIN_LOG_LEVEL": "2",
            "MMM_BACKEND_TIMEOUT_SECONDS": str(timeout),
            "MPLCONFIGDIR": str(root / "mpl"),
            "NUMBA_CACHE_DIR": str(root / "numba"),
            "PYTENSOR_FLAGS": "base_compiledir="
            + str(root / "pytensor").replace("\\", "/")
            + ",compiledir="
            + str(root / "pytensor" / "compiled").replace("\\", "/")
            + ",cxx=",
            "NUMBA_NUM_THREADS": "1",
            "XDG_CACHE_HOME": str(root / "cache"),
        }
        if backend == "meta_robyn":
            # Windows R refuses spaces in its internal temp directory. Use an
            # automatically cleaned directory in the authorized OS temp root.
            temporary_path = resources.enter_context(tempfile.TemporaryDirectory(prefix="mmm-r-"))
            if " " in temporary_path:
                raise MMMError(
                    "R_TEMP_PATH", "Configure an OS temporary directory without spaces for R"
                )
            env.update(
                RETICULATE_PYTHON=str(python),
                RETICULATE_AUTOCONFIGURE="FALSE",
                R_LIBS_USER=str(configured_r_library()),
                R_USER=temporary_path,
                TMPDIR=temporary_path,
                TEMP=temporary_path,
                TMP=temporary_path,
                LANG="C",
            )
        try:
            with (root / "worker.log").open("w", encoding="utf-8") as log:
                completed = run_worker(
                    [
                        str(python),
                        str(Path(__file__).with_name("worker.py")),
                        backend,
                        str(source),
                        str(destination),
                    ],
                    cwd=root,
                    env=env,
                    stdout=log,
                    timeout=timeout,
                )
            if destination.exists() and destination.stat().st_size <= store.settings.max_file_bytes:
                try:
                    result = json.loads(destination.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    retain_failure(store, root, "invalid_json_result", completed.returncode)
                    raise MMMError(
                        "BACKEND_FAILED", "Native result was invalid; private diagnostics retained"
                    ) from exc
                if (
                    not isinstance(result, dict)
                    or result.get("ok") is True
                    and not isinstance(result.get("data"), dict)
                ):
                    retain_failure(store, root, "invalid_result_contract", completed.returncode)
                    raise MMMError(
                        "BACKEND_FAILED",
                        "Native result contract was invalid; private diagnostics retained",
                    )
                if result.get("ok") is True and completed.returncode == 0:
                    result["data"]["execution_limits"] = {
                        "platform": os.name,
                        "wall_timeout_seconds": timeout,
                        "numeric_threads": 1,
                        "cpu_percent": int(os.environ.get("MMM_WORKER_CPU_PERCENT", "50"))
                        if os.name == "nt"
                        else None,
                        "memory_mb": int(os.environ.get("MMM_WORKER_MEMORY_MB", "4096"))
                        if os.name == "nt"
                        else None,
                        "process_tree_cleanup": True,
                    }
                    return result["data"]
                retain_failure(store, root, "native_error_result", completed.returncode)
                # Keep the bounded error diagnostic, no training rows or input paths.
                raise MMMError(
                    "BACKEND_FAILED",
                    "Backend execution failed; inspect the private host diagnostic log",
                )
            reason = "oversized_result" if destination.exists() else "missing_result"
            retain_failure(store, root, reason, completed.returncode)
            raise MMMError(
                "BACKEND_FAILED",
                "Backend failed without a valid bounded result; private diagnostics retained ("
                + reason
                + ")",
            )
        except subprocess.TimeoutExpired as exc:
            retain_failure(store, root, "timeout")
            raise MMMError(
                "BACKEND_TIMEOUT", "Backend exceeded the configured wall-clock limit"
            ) from exc
        except OSError as exc:
            retain_failure(store, root, "runtime_io_failure")
            raise MMMError(
                "BACKEND_FAILED", "Native runtime I/O failed; private diagnostics retained"
            ) from exc
