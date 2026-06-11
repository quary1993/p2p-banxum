from __future__ import annotations

from datetime import datetime, timedelta
from io import StringIO
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from backend.apps.platform_core.models.scheduled_jobs import (
    ScheduledJobRun,
    ScheduledJobRunStatus,
)
from backend.apps.platform_core.services import scheduled_jobs
from backend.apps.platform_core.services.scheduled_jobs import (
    DEFAULT_SCHEDULED_JOB_NAMES,
    EMAIL_OUTBOX_DISPATCH_JOB,
    LOAN_SERVICING_STATUS_SCAN_JOB,
    RunScheduledJobsCommand,
    ScheduledJobValidationError,
    run_scheduled_jobs,
)


def _admin_user(email: str = "scheduler@example.test") -> Any:
    user_model = get_user_model()
    return user_model.objects.create_user(
        email=email,
        full_name="Scheduler Admin",
        account_type="superadmin",
        status="active",
        is_staff=True,
        is_superuser=True,
        is_active=True,
    )


def _as_of() -> datetime:
    return datetime(2026, 1, 10, 12, 0, tzinfo=ZoneInfo("Europe/Zurich"))


@pytest.mark.django_db
def test_scheduled_jobs_run_once_per_period_and_skip_duplicates() -> None:
    admin = _admin_user()
    first = run_scheduled_jobs(RunScheduledJobsCommand(actor=admin, as_of=_as_of()))

    assert [result.job_name for result in first.results] == list(DEFAULT_SCHEDULED_JOB_NAMES)
    assert {result.status for result in first.results} == {ScheduledJobRunStatus.SUCCEEDED}
    assert ScheduledJobRun.objects.count() == len(DEFAULT_SCHEDULED_JOB_NAMES)

    second = run_scheduled_jobs(RunScheduledJobsCommand(actor=admin, as_of=_as_of()))

    assert {result.status for result in second.results} == {ScheduledJobRunStatus.SKIPPED}
    assert ScheduledJobRun.objects.count() == len(DEFAULT_SCHEDULED_JOB_NAMES)


@pytest.mark.django_db
def test_failed_scheduled_job_retries_with_same_run_key(monkeypatch: pytest.MonkeyPatch) -> None:
    as_of = _as_of()

    def fail_once(_command: RunScheduledJobsCommand, _as_of: datetime) -> dict[str, Any]:
        raise RuntimeError("provider outage")

    monkeypatch.setattr(scheduled_jobs, "_email_outbox_dispatch_summary", fail_once)
    failed = run_scheduled_jobs(
        RunScheduledJobsCommand(job_names=(EMAIL_OUTBOX_DISPATCH_JOB,), as_of=as_of)
    )

    failed_result = failed.results[0]
    assert failed_result.status == ScheduledJobRunStatus.FAILED
    job_run = ScheduledJobRun.objects.get(run_key=failed_result.run_key)
    assert job_run.status == ScheduledJobRunStatus.FAILED
    assert job_run.attempt_count == 1

    def succeed(_command: RunScheduledJobsCommand, _as_of: datetime) -> dict[str, Any]:
        return {"processed_count": 0}

    monkeypatch.setattr(scheduled_jobs, "_email_outbox_dispatch_summary", succeed)
    retried = run_scheduled_jobs(
        RunScheduledJobsCommand(job_names=(EMAIL_OUTBOX_DISPATCH_JOB,), as_of=as_of)
    )

    retried_result = retried.results[0]
    job_run.refresh_from_db()
    assert retried_result.status == ScheduledJobRunStatus.SUCCEEDED
    assert retried_result.run_key == failed_result.run_key
    assert job_run.status == ScheduledJobRunStatus.SUCCEEDED
    assert job_run.attempt_count == 2
    assert job_run.summary == {"processed_count": 0}


@pytest.mark.django_db
def test_stale_running_scheduled_job_is_reclaimed(
    settings: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.SCHEDULED_JOBS_RUNNING_TIMEOUT_MINUTES = 30
    as_of = _as_of()
    run_key = scheduled_jobs._scheduled_job_run_key(
        EMAIL_OUTBOX_DISPATCH_JOB,
        as_of=as_of,
        force=False,
    )
    stale_run = ScheduledJobRun.objects.create(
        job_name=EMAIL_OUTBOX_DISPATCH_JOB,
        run_key=run_key,
        status=ScheduledJobRunStatus.RUNNING,
        scheduled_for=as_of,
        started_at=timezone.now() - timedelta(hours=1),
        summary={"claimed": True},
    )

    def succeed(_command: RunScheduledJobsCommand, _as_of: datetime) -> dict[str, Any]:
        return {"processed_count": 0}

    monkeypatch.setattr(scheduled_jobs, "_email_outbox_dispatch_summary", succeed)
    result = run_scheduled_jobs(
        RunScheduledJobsCommand(job_names=(EMAIL_OUTBOX_DISPATCH_JOB,), as_of=as_of)
    )

    stale_run.refresh_from_db()
    assert result.results[0].status == ScheduledJobRunStatus.SUCCEEDED
    assert result.results[0].run_key == run_key
    assert stale_run.status == ScheduledJobRunStatus.SUCCEEDED
    assert stale_run.attempt_count == 2
    assert stale_run.summary == {"processed_count": 0}


@pytest.mark.django_db
def test_fresh_running_scheduled_job_is_not_reclaimed(monkeypatch: pytest.MonkeyPatch) -> None:
    as_of = _as_of()
    run_key = scheduled_jobs._scheduled_job_run_key(
        EMAIL_OUTBOX_DISPATCH_JOB,
        as_of=as_of,
        force=False,
    )
    ScheduledJobRun.objects.create(
        job_name=EMAIL_OUTBOX_DISPATCH_JOB,
        run_key=run_key,
        status=ScheduledJobRunStatus.RUNNING,
        scheduled_for=as_of,
        started_at=timezone.now(),
    )

    def fail_if_called(_command: RunScheduledJobsCommand, _as_of: datetime) -> dict[str, Any]:
        raise AssertionError("Fresh RUNNING run should be skipped, not reclaimed.")

    monkeypatch.setattr(scheduled_jobs, "_email_outbox_dispatch_summary", fail_if_called)
    result = run_scheduled_jobs(
        RunScheduledJobsCommand(job_names=(EMAIL_OUTBOX_DISPATCH_JOB,), as_of=as_of)
    )

    assert result.results[0].status == ScheduledJobRunStatus.SKIPPED
    assert result.results[0].summary["existing_status"] == ScheduledJobRunStatus.RUNNING


@pytest.mark.django_db
def test_dry_run_is_limited_to_balance_ageing_scan() -> None:
    admin = _admin_user()

    with pytest.raises(ScheduledJobValidationError, match="balance_ageing_scan"):
        run_scheduled_jobs(RunScheduledJobsCommand(actor=admin, as_of=_as_of(), dry_run=True))


@pytest.mark.django_db
def test_run_scheduled_jobs_command_resolves_configured_actor(settings: Any) -> None:
    admin = _admin_user(email="jobs@example.test")
    settings.SCHEDULED_JOBS_ACTOR_EMAIL = admin.email
    output = StringIO()

    call_command(
        "run_scheduled_jobs",
        "--job",
        LOAN_SERVICING_STATUS_SCAN_JOB,
        "--as-of",
        "2026-01-10",
        stdout=output,
    )

    run = ScheduledJobRun.objects.get(job_name=LOAN_SERVICING_STATUS_SCAN_JOB)
    assert run.status == ScheduledJobRunStatus.SUCCEEDED
    assert run.actor_user_id == admin.id
    assert run.run_key == f"{LOAN_SERVICING_STATUS_SCAN_JOB}:2026-01-10"
    assert "loan_servicing_status_scan: succeeded" in output.getvalue()


@pytest.mark.django_db
def test_check_scheduled_jobs_command_passes_when_runs_are_healthy() -> None:
    as_of = _as_of()
    ScheduledJobRun.objects.create(
        job_name=EMAIL_OUTBOX_DISPATCH_JOB,
        run_key="email_outbox_dispatch:2026-01-10T12:00:00+01:00",
        status=ScheduledJobRunStatus.SUCCEEDED,
        scheduled_for=as_of,
        started_at=timezone.now(),
        finished_at=timezone.now(),
    )
    output = StringIO()

    call_command("check_scheduled_jobs", stdout=output)

    assert "Scheduled job monitor OK" in output.getvalue()


@pytest.mark.django_db
def test_check_scheduled_jobs_command_fails_on_failed_or_stale_running_runs(
    settings: Any,
) -> None:
    settings.SCHEDULED_JOBS_RUNNING_TIMEOUT_MINUTES = 30
    as_of = _as_of()
    ScheduledJobRun.objects.create(
        job_name=EMAIL_OUTBOX_DISPATCH_JOB,
        run_key="email_outbox_dispatch:failed",
        status=ScheduledJobRunStatus.FAILED,
        scheduled_for=as_of,
        started_at=timezone.now() - timedelta(minutes=10),
        finished_at=timezone.now() - timedelta(minutes=9),
        error="provider outage",
    )
    ScheduledJobRun.objects.create(
        job_name=LOAN_SERVICING_STATUS_SCAN_JOB,
        run_key="loan_servicing_status_scan:stale",
        status=ScheduledJobRunStatus.RUNNING,
        scheduled_for=as_of,
        started_at=timezone.now() - timedelta(hours=2),
    )
    output = StringIO()

    with pytest.raises(CommandError, match="failed or stale"):
        call_command("check_scheduled_jobs", stdout=output)

    rendered = output.getvalue()
    assert "FAILED runs" in rendered
    assert "Stale RUNNING runs" in rendered
    assert "provider outage" in rendered
