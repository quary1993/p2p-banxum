from __future__ import annotations

import fcntl
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from django.conf import settings
from django.db import connection

QA_OPERATION_LOCK = 0x42414E58554D5141
_held_mode: ContextVar[str | None] = ContextVar("banxum_qa_lock", default=None)


class QaEnvironmentBusy(RuntimeError):
    pass


@contextmanager
def qa_environment_guard(*, exclusive: bool = False) -> Iterator[None]:
    """Serialize QA operations against requests/jobs without a time-expiring lease."""
    if not settings.QA_DEV_MODE_ALLOWED or settings.IS_PRODUCTION:
        yield
        return
    mode = "exclusive" if exclusive else "shared"
    held = _held_mode.get()
    if held is not None:
        if held == "shared" and exclusive:
            raise QaEnvironmentBusy(
                "Another request or QA operation is in progress. Retry shortly."
            )
        yield
        return

    token = None
    lock_file = None
    locked = False
    suffix = "" if exclusive else "_shared"
    try:
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT pg_try_advisory_lock{suffix}(%s)", [QA_OPERATION_LOCK])
                locked = bool(cursor.fetchone()[0])
        else:
            directory = Path(settings.QA_DEV_MODE_SNAPSHOT_DIR)
            directory.mkdir(parents=True, exist_ok=True)
            lock_file = (directory / ".qa-operation.lock").open("a")
            try:
                fcntl.flock(
                    lock_file, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB
                )
                locked = True
            except BlockingIOError:
                pass
        if not locked:
            raise QaEnvironmentBusy(
                "Another request or QA operation is in progress. Retry shortly."
            )
        token = _held_mode.set(mode)
        yield
    finally:
        if token is not None:
            _held_mode.reset(token)
        if locked and connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT pg_advisory_unlock{suffix}(%s)", [QA_OPERATION_LOCK])
        if lock_file is not None:
            lock_file.close()
