"""Local inventory and operator-only, hash-confirmed deletion. No automatic expiry."""

from datetime import datetime, timezone

from .errors import MMMError
from .storage import digest

KINDS = ("datasets", "models", "backend_models", "reports", "dashboards")


def inventory(store):
    result = []
    now = datetime.now(timezone.utc).timestamp()
    for kind in KINDS:
        folder = store.root / kind
        from .storage import reject_links

        reject_links(folder)
        for item in sorted(folder.glob("*.json")):
            if len(result) >= 10000:
                raise MMMError(
                    "INVENTORY_LIMIT", "Inventory exceeds 10000 artifacts; operator review required"
                )
            payload = store.read(kind, item.stem)
            path = store.path(kind, item.stem)
            info = path.stat()
            result.append(
                {
                    "kind": kind,
                    "artifact_id": item.stem,
                    "sha256": digest(payload),
                    "bytes": info.st_size,
                    "modified_at": datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat(),
                    "age_days": max(0.0, (now - info.st_mtime) / 86400),
                    "synthetic": payload.get("synthetic") is True,
                    "dataset_id": payload.get("dataset_id"),
                    "dataset_sha256": payload.get("dataset_sha256"),
                    "model_id": payload.get("model_id"),
                }
            )
    return {
        "artifacts": result,
        "total_bytes": sum(r["bytes"] for r in result),
        "scope": "Verified JSON artifacts only; logs, jobs, environments and backups are excluded",
        "automatic_deletion": False,
    }


def references(items, target):
    links = []
    for item in items:
        if (item["kind"], item["artifact_id"]) == (target["kind"], target["artifact_id"]):
            continue
        if target["kind"] == "datasets":
            linked = (
                item["dataset_id"] == target["artifact_id"]
                or item["dataset_sha256"] == target["sha256"]
            )
        elif target["kind"] in {"models", "backend_models"}:
            linked = (
                item["kind"] in {"reports", "dashboards"}
                and item["model_id"] == target["artifact_id"]
            )
        else:
            linked = False
        if linked:
            links.append({"kind": item["kind"], "artifact_id": item["artifact_id"]})
    return links


def retention_plan(store, older_than_days):
    items = inventory(store)["artifacts"]
    return {
        "candidates": [
            {**item, "blocked_by": references(items, item)}
            for item in items
            if item["age_days"] >= older_than_days
        ],
        "older_than_days": older_than_days,
        "age_basis": "filesystem modification time, not a legal retention policy",
        "deleted": False,
        "instruction": "Stop the server, review backups and dependents, then use operator delete-artifact with the exact hash. Never delete an entire root.",
    }


def delete_artifact(store, kind, artifact_id, expected_sha256):
    # The operator supplies a single ID and an inspected content hash. Never recurse.
    path = store.path(kind, artifact_id)
    payload = store.read(kind, artifact_id)
    if digest(payload) != expected_sha256:
        raise MMMError("HASH_MISMATCH", "Artifact hash differs from the reviewed deletion target")
    items = inventory(store)["artifacts"]
    target = next(i for i in items if i["kind"] == kind and i["artifact_id"] == artifact_id)
    if references(items, target):
        raise MMMError(
            "ARTIFACT_REFERENCED", "Referenced artifact cannot be deleted; review dependents first"
        )
    # Repeat integrity/path checks immediately before the single-file operation.
    if digest(store.read(kind, artifact_id)) != expected_sha256:
        raise MMMError("HASH_MISMATCH", "Artifact hash changed during deletion review")
    path = store.path(kind, artifact_id)
    if not path.resolve().is_relative_to(store.root.resolve()) or path == store.root:
        raise MMMError("UNSAFE_PATH", "Deletion target outside authorized root")
    path.unlink()
    return {
        "deleted": True,
        "kind": kind,
        "artifact_id": artifact_id,
        "sha256": expected_sha256,
        "scope": "One local artifact; external backups and retained copies require separate handling",
    }
