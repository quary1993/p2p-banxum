from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from backend.apps.platform_core.domain.time import now_utc
from backend.apps.platform_core.models.qa import QaDevModeState
from backend.apps.platform_core.services import qa_dev_mode
from backend.apps.platform_core.services.qa_dev_mode import (
    AdvanceQaDevModeTimeCommand,
    EnableQaDevModeCommand,
    QaDevModeAuthorizationError,
    QaDevModeValidationError,
    RevertQaDevModeCommand,
    advance_qa_dev_mode_time,
    enable_qa_dev_mode,
    revert_qa_dev_mode,
)


def _user(
    *,
    email: str,
    account_type: str = "superadmin",
    is_superuser: bool = True,
    is_staff: bool = True,
) -> Any:
    user_model = get_user_model()
    return user_model.objects.create_user(
        email=email,
        full_name="QA Operator",
        account_type=account_type,
        status="active",
        is_staff=is_staff,
        is_superuser=is_superuser,
        is_active=True,
    )


def _stub_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        qa_dev_mode,
        "_create_database_snapshot",
        lambda created_at: "/tmp/snap.json",
    )


@pytest.fixture(autouse=True)
def _clear_qa_cache() -> None:
    qa_dev_mode._clear_cached_time()


@pytest.mark.django_db
def test_qa_dev_mode_requires_config_guard(settings: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.QA_DEV_MODE_ALLOWED = False
    settings.IS_PRODUCTION = False
    superadmin = _user(email="qa-superadmin@example.test")
    _stub_snapshot(monkeypatch)

    with pytest.raises(QaDevModeValidationError, match="disabled"):
        enable_qa_dev_mode(EnableQaDevModeCommand(actor=superadmin))


@pytest.mark.django_db
def test_qa_dev_mode_is_never_allowed_in_production(
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.QA_DEV_MODE_ALLOWED = True
    settings.IS_PRODUCTION = True
    superadmin = _user(email="qa-superadmin@example.test")
    _stub_snapshot(monkeypatch)

    with pytest.raises(QaDevModeValidationError, match="production"):
        enable_qa_dev_mode(EnableQaDevModeCommand(actor=superadmin))


@pytest.mark.django_db
def test_qa_dev_mode_requires_superadmin(settings: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.QA_DEV_MODE_ALLOWED = True
    settings.IS_PRODUCTION = False
    admin = _user(
        email="qa-admin@example.test",
        account_type="admin",
        is_superuser=False,
        is_staff=True,
    )
    _stub_snapshot(monkeypatch)

    with pytest.raises(QaDevModeAuthorizationError, match="superadmin"):
        enable_qa_dev_mode(EnableQaDevModeCommand(actor=admin))


@pytest.mark.django_db
def test_enable_qa_dev_mode_sets_time_override(
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.QA_DEV_MODE_ALLOWED = True
    settings.IS_PRODUCTION = False
    superadmin = _user(email="qa-superadmin@example.test")
    _stub_snapshot(monkeypatch)

    before = timezone.now()
    state = enable_qa_dev_mode(EnableQaDevModeCommand(actor=superadmin, note="QA pass"))

    assert state.is_enabled is True
    assert state.snapshot_path == "/tmp/snap.json"
    assert state.note == "QA pass"
    assert state.entered_by_user_id == superadmin.pk
    assert state.current_time is not None
    assert state.current_time >= before
    assert now_utc() == state.current_time


@pytest.mark.django_db
def test_advance_qa_dev_mode_runs_crossed_daily_jobs(
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.QA_DEV_MODE_ALLOWED = True
    settings.IS_PRODUCTION = False
    superadmin = _user(email="qa-superadmin@example.test")
    start = datetime(2026, 6, 25, 10, 0, tzinfo=ZoneInfo("Europe/Zurich"))
    QaDevModeState.objects.create(
        singleton_id=1,
        is_enabled=True,
        entered_at=start,
        entered_by_user_id=superadmin.pk,
        current_time=start,
        snapshot_path="/tmp/snap.json",
        snapshot_created_at=start,
    )
    qa_dev_mode._cache_current_time(start)
    calls: list[tuple[tuple[str, ...], datetime]] = []

    def fake_run(command: Any) -> Any:
        calls.append((command.job_names, command.as_of))

        class Result:
            results: tuple[Any, ...] = ()

        return Result()

    monkeypatch.setattr(qa_dev_mode, "run_scheduled_jobs", fake_run)

    state = advance_qa_dev_mode_time(
        AdvanceQaDevModeTimeCommand(actor=superadmin, days=3)
    )

    assert state.current_time == start + timedelta(days=3)
    assert len(calls) == 7
    daily_calls = [call for call in calls if call[0] != ("email_outbox_dispatch",)]
    email_calls = [call for call in calls if call[0] == ("email_outbox_dispatch",)]
    assert len(daily_calls) == 3
    assert len(email_calls) == 4
    assert state.last_advance_summary["advanced_days"] == 3
    assert state.last_advance_summary["failed_count"] == 0


@pytest.mark.django_db
def test_revert_qa_dev_mode_requires_confirmation(
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.QA_DEV_MODE_ALLOWED = True
    settings.IS_PRODUCTION = False
    superadmin = _user(email="qa-superadmin@example.test")
    state = QaDevModeState.objects.create(
        singleton_id=1,
        is_enabled=True,
        entered_at=timezone.now(),
        entered_by_user_id=superadmin.pk,
        current_time=timezone.now(),
        snapshot_path="/tmp/snap.json",
        snapshot_created_at=timezone.now(),
    )
    called = False

    def fake_restore(_path: str) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(qa_dev_mode, "_restore_database_snapshot", fake_restore)

    with pytest.raises(QaDevModeValidationError, match="REVERT QA DB"):
        revert_qa_dev_mode(RevertQaDevModeCommand(actor=superadmin, confirmation="wrong"))

    state.refresh_from_db()
    assert state.is_enabled is True
    assert called is False


@pytest.mark.django_db
def test_qa_dev_mode_api_is_superadmin_only(
    client: Client,
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.QA_DEV_MODE_ALLOWED = True
    settings.IS_PRODUCTION = False
    admin = _user(
        email="qa-admin@example.test",
        account_type="admin",
        is_superuser=False,
        is_staff=True,
    )
    superadmin = _user(email="qa-superadmin@example.test")
    _stub_snapshot(monkeypatch)

    client.force_login(admin)
    forbidden = client.get("/api/v1/qa/dev-mode/")
    assert forbidden.status_code == 403

    client.force_login(superadmin)
    response = client.post(
        "/api/v1/qa/dev-mode/enable/",
        {"note": "QA"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["is_enabled"] is True
