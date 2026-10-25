"""Immutable JSON artifacts. No tool accepts filesystem paths or uses pickle."""

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from uuid import uuid4

from .config import Settings
from .errors import MMMError
from .schemas import IDENTIFIER_PATTERN


def canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def reject_links(path: Path):
    """Check every existing ancestor, including Windows junction/reparse points."""
    for part in [path, *path.parents]:
        if part.is_symlink():
            raise MMMError("UNSAFE_PATH", "Links and reparse points are not allowed")
        if part.exists():
            info = part.lstat()
            if getattr(info, "st_file_attributes", 0) & 0x400:
                raise MMMError("UNSAFE_PATH", "Links and reparse points are not allowed")


class ArtifactStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.data_dir.absolute()
        reject_links(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        for kind in ("datasets", "models", "logs", "reports", "dashboards", "backend_models"):
            folder = self.root / kind
            reject_links(folder)
            folder.mkdir(exist_ok=True)

    def path(self, kind: str, artifact_id: str) -> Path:
        if kind not in {
            "datasets",
            "models",
            "reports",
            "dashboards",
            "backend_models",
        } or not re.fullmatch(IDENTIFIER_PATTERN, artifact_id):
            raise MMMError("INVALID_ID", "Use a lowercase artifact ID, not a file path")
        if artifact_id.split("_")[0] in {
            "con",
            "prn",
            "aux",
            "nul",
            *[f"com{i}" for i in range(1, 10)],
            *[f"lpt{i}" for i in range(1, 10)],
        }:
            raise MMMError("INVALID_ID", "Reserved filesystem identifier")
        path = self.root / kind / f"{artifact_id}.json"
        reject_links(path)
        if not path.resolve().is_relative_to(self.root.resolve()):
            raise MMMError("UNSAFE_PATH", "Artifact outside authorized root")
        return path

    def write(self, kind: str, artifact_id: str, payload: dict) -> str:
        path = self.path(kind, artifact_id)
        envelope = {
            "schema_version": 1,
            "kind": kind,
            "sha256": digest(payload),
            "payload": payload,
        }
        raw = canonical(envelope)
        if len(raw) > self.settings.max_file_bytes:
            raise MMMError("ARTIFACT_TOO_LARGE", "Artifact exceeds configured byte limit")
        temporary = path.parent / f".pending-{uuid4().hex}"
        try:
            with temporary.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            # Same-directory hard link publishes a complete file and never replaces a target.
            os.link(temporary, path)
        except FileExistsError as exc:
            raise MMMError("ALREADY_EXISTS", "ID already exists; choose a new ID") from exc
        finally:
            temporary.unlink(missing_ok=True)
        return envelope["sha256"]

    def read(self, kind: str, artifact_id: str) -> dict:
        path = self.path(kind, artifact_id)
        try:
            info = path.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1:
                raise MMMError("UNSAFE_PATH", "Artifact must be a regular, unlinked file")
            if info.st_size > self.settings.max_file_bytes:
                raise MMMError("ARTIFACT_TOO_LARGE", "Artifact exceeds configured byte limit")
            with path.open("rb") as stream:
                raw = stream.read(self.settings.max_file_bytes + 1)
            if len(raw) > self.settings.max_file_bytes:
                raise MMMError("ARTIFACT_TOO_LARGE", "Artifact exceeds configured byte limit")
            envelope = json.loads(raw)
            payload = envelope["payload"]
            if (
                envelope["schema_version"] != 1
                or envelope["kind"] != kind
                or not isinstance(payload, dict)
                or digest(payload) != envelope["sha256"]
            ):
                raise ValueError("Invalid envelope")
            return payload
        except FileNotFoundError as exc:
            raise MMMError("NOT_FOUND", "Artifact ID was not found") from exc
        except (ValueError, KeyError, TypeError, RecursionError) as exc:
            raise MMMError("CORRUPT_ARTIFACT", "Invalid or damaged JSON artifact") from exc
