"""IP of Webby-Soft SRL. Lossless datetime encoding for database QA snapshots."""

import json
from datetime import datetime, time
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.core.serializers.json import Serializer as JsonSerializer
from django.db import connection

HISTORY_MODELS = frozenset(
    {"platform_core.auditevent", "platform_core.domainevent", "platform_core.scheduledjobrun"}
)


class SnapshotJSONEncoder(DjangoJSONEncoder):
    def default(self, value: Any) -> Any:
        if isinstance(value, datetime | time):
            return value.isoformat()
        return super().default(value)


class Serializer(JsonSerializer):
    def start_serialization(self) -> None:
        super().start_serialization()
        self.json_kwargs["cls"] = SnapshotJSONEncoder


def partition_validated_snapshot(
    content: bytes, objects: list[Any]
) -> tuple[bytes, dict[Any, list[Any]]]:
    history: dict[Any, list[Any]] = {}
    for item in objects:
        model = type(item.object)
        if model._meta.label_lower in HISTORY_MODELS:
            if item.m2m_data or item.deferred_fields:
                raise ValueError("Batch history restore does not support deferred relationships.")
            history.setdefault(model, []).append(item.object)
    remaining = [row for row in json.loads(content) if row["model"] not in HISTORY_MODELS]
    return json.dumps(remaining).encode("utf-8"), history


def restore_snapshot_history(history: dict[Any, list[Any]]) -> None:
    """Insert preserved history into cleared tables inside the restore transaction."""
    if not connection.in_atomic_block:
        raise RuntimeError("Snapshot history restore requires an atomic database restore.")
    for model, objects in history.items():
        if model._meta.label_lower not in HISTORY_MODELS:
            raise ValueError("Only snapshot history tables may use the batch restore.")
        fields = list(model._meta.local_concrete_fields)
        batch_size = min(1000, connection.ops.bulk_batch_size(fields, objects))
        for start in range(0, len(objects), batch_size):
            # bulk_create runs auto_now/auto_now_add. The fixture raw insert path
            # preserves the original timestamps and bypasses model hooks instead.
            model._base_manager._insert(
                objects[start : start + batch_size], fields=fields, raw=True, using=connection.alias
            )
