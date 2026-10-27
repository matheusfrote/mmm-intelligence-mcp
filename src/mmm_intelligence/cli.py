"""Local operator CLI; no arguments preserve the stdio server entrypoint."""

import argparse
import json
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from . import __version__


def doctor() -> dict:
    from .integrations.bridge import executable

    versions: dict[str, str | None] = {}
    for package in ("mcp", "numpy", "scipy", "pydantic", "threadpoolctl"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return {
        "version": __version__,
        "python": ".".join(map(str, sys.version_info[:3])),
        "base_runtime_ok": sys.version_info >= (3, 11) and all(versions.values()),
        "dependencies": versions,
        "optional_runtimes": {
            name: {"executable_present": executable(name).is_file(), "library_verified": False}
            for name in ("google_meridian", "pymc_marketing", "meta_robyn")
        },
        "scope": "Read-only metadata; run backend_smoke for native execution. No credentials printed.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="MMM Intelligence: local exploratory modeling")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("serve", help="Run MCP using host environment (stdio by default)")
    commands.add_parser("doctor", help="Read dependency metadata without training or network")
    dashboard = commands.add_parser("dashboard", help="Open the local workspace without a login")
    dashboard.add_argument("--port", type=int, default=8769)
    config = commands.add_parser(
        "config", help="Print a stdio client configuration; no files written"
    )
    config.add_argument("--data-dir", type=Path, required=True)
    delete = commands.add_parser(
        "delete-artifact",
        help="Operator only: stop server and delete one reviewed, unreferenced artifact",
    )
    delete.add_argument("--data-dir", type=Path, required=True)
    delete.add_argument(
        "--kind",
        choices=["datasets", "models", "backend_models", "reports", "dashboards"],
        required=True,
    )
    delete.add_argument("--id", required=True)
    delete.add_argument("--sha256", required=True)
    args = parser.parse_args(argv)
    if args.command in (None, "serve"):
        from .server import main as serve

        serve()
    elif args.command == "doctor":
        result = doctor()
        print(json.dumps(result, indent=2))
        return 0 if result["base_runtime_ok"] else 1
    elif args.command == "dashboard":
        import uvicorn

        from .config import Settings
        from .http_transport import create_http_app

        if not 1 <= args.port <= 65535:
            parser.error("Port must be between 1 and 65535")
        print(f"Local dashboard: http://127.0.0.1:{args.port}/app", file=sys.stderr)
        uvicorn.run(
            create_http_app(Settings.from_env()),
            host="127.0.0.1",
            port=args.port,
            proxy_headers=False,
        )
    elif args.command == "delete-artifact":
        from dataclasses import replace

        from .config import Settings
        from .errors import MMMError
        from .lifecycle import delete_artifact
        from .storage import ArtifactStore

        if not args.data_dir.is_dir():
            parser.error("Deletion requires an existing operator-selected storage root")
        try:
            result = delete_artifact(
                ArtifactStore(replace(Settings.from_env(), data_dir=args.data_dir)),
                args.kind,
                args.id,
                args.sha256,
            )
        except MMMError as exc:
            print(json.dumps({"ok": False, "code": exc.code, "message": str(exc)}), file=sys.stderr)
            return 1
        print(json.dumps(result))
    else:
        print(
            json.dumps(
                {
                    "mcpServers": {
                        "mmm-intelligence": {
                            "command": str(Path(sys.executable).absolute()),
                            "args": ["-m", "mmm_intelligence.server"],
                            "env": {
                                "MMM_DATA_DIR": str(args.data_dir.absolute()),
                                "MMM_ALLOW_REAL_DATA": "false",
                                "MMM_TRANSPORT": "stdio",
                            },
                        }
                    }
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
