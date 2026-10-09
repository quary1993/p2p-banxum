"""Test helpers that pin the QA platform clock and the real wall clock separately."""

from __future__ import annotations

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from unittest import mock

from django.test.utils import override_settings

from backend.apps.platform_core.models.qa import QaDevModeState
from backend.apps.platform_core.services import qa_dev_mode


@contextmanager
def qa_clock(at: datetime) -> Iterator[None]:
    """Enable QA mode with its clock pinned at ``at``, as staging QA mode does."""
    with (
        tempfile.TemporaryDirectory() as snapshot_dir,
        override_settings(
            QA_DEV_MODE_ALLOWED=True,
            IS_PRODUCTION=False,
            QA_DEV_MODE_SNAPSHOT_DIR=snapshot_dir,
        ),
    ):
        QaDevModeState.objects.update_or_create(
            singleton_id=1,
            defaults={
                "is_enabled": True,
                "entered_at": at,
                "current_time": at,
                "snapshot_path": "",
                "snapshot_created_at": at,
            },
        )
        qa_dev_mode._cache_current_time(at)
        try:
            yield
        finally:
            qa_dev_mode._clear_cached_time()


@contextmanager
def wall_clock(at: datetime) -> Iterator[None]:
    """Pin the real wall clock (``django.utils.timezone.now``) at ``at``."""
    with mock.patch("django.utils.timezone.now", return_value=at):
        yield
