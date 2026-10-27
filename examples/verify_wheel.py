"""Install one wheel and frozen dependencies in a fresh venv, then run real MCP outside source."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import venv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    wheels = list(args.wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        parser.error("Use a directory containing exactly one reviewed wheel")
    wheel = wheels[0].absolute()
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="mmm-wheel-") as task:
        temporary = Path(task)
        runtime = temporary / "runtime"
        venv.EnvBuilder(with_pip=True).create(runtime)
        python = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

        def run(*argv, executable=python):
            return subprocess.run(
                [str(executable), *map(str, argv)],
                cwd=temporary,
                env=env,
                capture_output=True,
                text=True,
                check=True,
                timeout=300,
            )

        run(
            "-m",
            "pip",
            "install",
            "--require-hashes",
            "--only-binary=:all:",
            "-r",
            root / "requirements/base-ci.txt",
        )
        run("-m", "pip", "install", "--no-deps", wheel)
        run("-m", "pip", "check")
        located = run(
            "-c", "import mmm_intelligence; print(mmm_intelligence.__file__)"
        ).stdout.strip()
        if not Path(located).is_relative_to(runtime):
            raise RuntimeError("Package was not imported from the installed wheel")
        console = runtime / (
            "Scripts/mmm-intelligence-mcp.exe" if os.name == "nt" else "bin/mmm-intelligence-mcp"
        )
        doctor = json.loads(run("doctor", executable=console).stdout)
        scripts = temporary / "examples"
        scripts.mkdir()
        shutil.copyfile(root / "examples/mcp_workflow.py", scripts / "mcp_workflow.py")
        output = temporary / "evidence"
        run(
            scripts / "mcp_workflow.py",
            "--extended",
            "--data-dir",
            temporary / "data",
            "--output-dir",
            output,
        )
        result = json.loads((output / "mcp-cycle.json").read_text(encoding="utf-8"))
        receipt = {
            "wheel": wheel.name,
            "sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
            "clean_venv": True,
            "import_origin_verified": True,
            "doctor": doctor,
            "console_script_verified": True,
            "tools_discovered": len(result["tools"]),
            "local_calls": len(result["calls"]),
            "restart_persistence": result["restart_persistence"],
        }
        if args.receipt:
            args.receipt.parent.mkdir(parents=True, exist_ok=True)
            with args.receipt.open("x", encoding="utf-8") as f:
                json.dump(receipt, f, indent=2)
        print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
