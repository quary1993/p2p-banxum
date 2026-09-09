"""IP of Webby-Soft SRL. Immutable activity projections retained across QA resets."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from django.core.serializers.json import DjangoJSONEncoder

from backend.apps.platform_core.models.qa import ArchivedInvestorActivity


def archive_activity_entries(
    *, investor_user_id: str, stream: str, entries: list[dict[str, Any]], reset_id: UUID
) -> int:
    count = 0
    for entry in entries:
        payload = json.loads(json.dumps(entry, cls=DjangoJSONEncoder))
        _row, created = ArchivedInvestorActivity.objects.get_or_create(
            investor_user_id=investor_user_id,
            stream=stream,
            source_id=str(entry["id"]),
            defaults={
                "occurred_at": entry.get("occurred_at", entry.get("executed_at")),
                "payload": payload,
                "reset_id": reset_id,
            },
        )
        count += int(created)
    return count


def archived_activity_entries(
    *, investor_user_id: str, stream: str, limit: int
) -> list[dict[str, Any]]:
    entries = []
    for row in ArchivedInvestorActivity.objects.filter(
        investor_user_id=investor_user_id, stream=stream
    )[:limit]:
        payload = dict(row.payload)
        date_key = "executed_at" if stream == "fx" else "occurred_at"
        payload[date_key] = row.occurred_at
        payload["archived_at"] = row.archived_at
        entries.append(payload)
    return entries


def merge_archived_activity(
    *, investor_user_id: str, stream: str, entries: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    combined = {
        str(entry["id"]): entry
        for entry in archived_activity_entries(
            investor_user_id=investor_user_id, stream=stream, limit=limit
        )
    }
    combined.update({str(entry["id"]): entry for entry in entries})
    date_key = "executed_at" if stream == "fx" else "occurred_at"

    def timestamp(entry: dict[str, Any]) -> datetime:
        value: datetime = entry[date_key]
        return value

    return sorted(combined.values(), key=timestamp, reverse=True)[:limit]
