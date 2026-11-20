"""IP of Webby-Soft SRL. Audit S2-1: the archive merge keeps the whole history when asked."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from backend.apps.platform_core.services.activity_archive import (
    archive_activity_entries,
    merge_archived_activity,
)

pytestmark = pytest.mark.django_db

START = datetime(2024, 1, 1, 9, 0, tzinfo=UTC)


def _entry(number: int) -> dict[str, Any]:
    return {"id": f"row-{number}", "occurred_at": START + timedelta(days=number)}


def test_no_limit_returns_every_archived_and_live_row_newest_first() -> None:
    investor_id = str(uuid4())
    archive_activity_entries(
        investor_user_id=investor_id,
        stream="portfolio",
        entries=[_entry(number) for number in range(5)],
        reset_id=uuid4(),
    )
    live = [_entry(number) for number in range(5, 8)]

    everything = merge_archived_activity(
        investor_user_id=investor_id, stream="portfolio", entries=live, limit=None
    )
    assert [row["id"] for row in everything] == [f"row-{n}" for n in range(7, -1, -1)]

    newest = merge_archived_activity(
        investor_user_id=investor_id, stream="portfolio", entries=live, limit=2
    )
    assert [row["id"] for row in newest] == ["row-7", "row-6"]


def test_a_limit_on_the_archive_keeps_the_newest_archived_rows() -> None:
    investor_id = str(uuid4())
    archive_activity_entries(
        investor_user_id=investor_id,
        stream="portfolio",
        entries=[_entry(number) for number in range(4)],
        reset_id=uuid4(),
    )
    rows = merge_archived_activity(
        investor_user_id=investor_id, stream="portfolio", entries=[], limit=1
    )
    assert [row["id"] for row in rows] == ["row-3"]
