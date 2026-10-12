"""IP of Webby-Soft SRL. Private restore bookmarks survive database restoration."""

from __future__ import annotations

import hashlib
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from django.conf import settings

RESTORE_TARGETS = frozenset({"seed", "snapshot"})


def _registry_path() -> Path:
    return Path(settings.QA_DEV_MODE_SNAPSHOT_DIR).expanduser() / "restore-points.json"


def read_restore_points() -> dict[str, dict[str, Any]]:
    registry = _registry_path()
    if not registry.exists():
        return {}
    payload = json.loads(registry.read_text(encoding="utf-8"))
    if payload.get("version") != 1 or not isinstance(payload.get("points"), dict):
        raise ValueError("The QA restore-point registry is invalid.")
    points = payload["points"]
    for kind, point in points.items():
        if kind not in RESTORE_TARGETS or not isinstance(point, dict):
            raise ValueError("Unknown QA restore point.")
        path = Path(point["path"]).resolve()
        if path.parent != registry.parent.resolve():
            raise ValueError("QA restore points must stay in the private snapshot directory.")
        datetime.fromisoformat(point["created_at"])
    return cast(dict[str, dict[str, Any]], points)


def register_restore_point(
    *, kind: str, path: str, created_at: datetime, new_seed: bool = False
) -> None:
    """Called under the exclusive QA guard after the snapshot transaction commits."""
    if kind not in RESTORE_TARGETS or (new_seed and kind != "seed"):
        raise ValueError("Invalid QA restore-point kind.")
    registry = _registry_path()
    target = Path(path).resolve()
    if target.parent != registry.parent.resolve() or not target.is_file():
        raise ValueError("The completed QA snapshot is missing from its private directory.")
    points = {} if new_seed else read_restore_points()
    points[kind] = {"path": str(target), "created_at": created_at.isoformat()}
    registry.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=registry.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        try:
            json.dump({"version": 1, "points": points}, stream)
            stream.flush()
            temporary.chmod(0o600)
            temporary.replace(registry)
        finally:
            temporary.unlink(missing_ok=True)


def validate_snapshot_file(path: str | Path, *, migrations: list[str]) -> bytes:
    """Validate one private snapshot without changing database state."""
    snapshot = Path(path).resolve()
    if snapshot.parent != _registry_path().parent.resolve():
        raise ValueError("The QA snapshot is outside the private snapshot directory.")
    if not snapshot.is_file():
        raise ValueError("QA snapshot file is missing.")
    manifest_path = snapshot.with_suffix(".manifest.json")
    if not manifest_path.is_file():
        raise ValueError("QA snapshot manifest is missing.")
    content = snapshot.read_bytes()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("sha256") != hashlib.sha256(content).hexdigest():
        raise ValueError("Snapshot checksum mismatch.")
    if manifest.get("migrations") != migrations:
        raise ValueError("Database schema changed since the snapshot was created.")
    return content
