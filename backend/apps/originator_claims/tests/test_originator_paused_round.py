"""A paused Loan Originator subscription round past its deadline (audit A-12).

Decision: an admin can resume a paused round; on or after the deadline an admin can
close it (if the close condition is met) or cancel and refund it. The daily job
never fails on a paused round: it skips it and keeps one open admin task.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from importlib import import_module
from typing import Any, cast

import pytest
from django.db.models import Model
from django.test import Client
from freezegun import freeze_time

from backend.apps.originator_claims.models import (
    OriginatorClaimEvent,
    OriginatorClaimEventType,
    OriginatorFundingRoundClose,
    OriginatorSubscriptionCancellation,
)
from backend.apps.originator_claims.services import (
    CloseOriginatorSubscriptionRoundCommand,
    HoldOriginatorLoanCommand,
    OriginatorClaimsValidationError,
    ResumeOriginatorSubscriptionCommand,
    close_originator_subscription_round,
    mark_originator_funding_close_failed,
    place_originator_loan_on_hold,
    resume_originator_subscription,
)
from backend.apps.originator_claims.tests.test_originator_claims import (  # noqa: F401
    _allocate_par_subscription,
    _create_par_subscription_loan,
    admin_user,
    investor,
)
from backend.apps.platform_core.models import OutboxMessage
from backend.apps.platform_core.models.scheduled_jobs import ScheduledJobRunStatus
from backend.apps.platform_core.services.scheduled_jobs import (
    ORIGINATOR_OPPORTUNITY_LIFECYCLE_SCAN_JOB,
    RunScheduledJobsCommand,
    run_scheduled_jobs,
)

T0 = date(2026, 6, 1)


def _noon(day: date) -> datetime:
    return datetime.combine(day, time(10), UTC)


def _daily_job(admin: Model, day: date) -> Any:
    with freeze_time(_noon(day)):
        return run_scheduled_jobs(
            RunScheduledJobsCommand(
                actor=admin,
                as_of=_noon(day),
                job_names=(ORIGINATOR_OPPORTUNITY_LIFECYCLE_SCAN_JOB,),
            )
        ).results[0]


def _tasks(related_object_type: str, loan: Model) -> Any:
    task_model = import_module("backend.apps.admin_ops.models").AdminTask
    return task_model.objects.filter(
        related_object_type=related_object_type,
        related_object_id=str(loan.pk),
    )


def _paused_round(admin: Model, investor_user: Model, suffix: str) -> Any:
    with freeze_time(_noon(T0)):
        result = _create_par_subscription_loan(admin_user=admin, today=T0, suffix=suffix)
        order = _allocate_par_subscription(
            admin_user=admin,
            investor=investor_user,
            loan=result.loan,
            today=T0,
            amount_minor=160_000,
            suffix=suffix,
        )
        place_originator_loan_on_hold(
            HoldOriginatorLoanCommand(
                actor=admin,
                loan_id=str(result.loan.pk),
                reason="Schedule evidence needs review.",
            )
        )
    return result, order


@pytest.mark.django_db
def test_daily_job_skips_paused_round_keeps_one_task_then_closes_after_resume(
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
) -> None:
    result, order = _paused_round(admin_user, investor, "PAUSE-JOB")
    deadline = T0 + timedelta(days=5)

    for day in (deadline + timedelta(days=1), deadline + timedelta(days=2)):
        run = _daily_job(admin_user, day)
        # Old code: the job failed every day and sent a daily ops alert.
        assert run.status == ScheduledJobRunStatus.SUCCEEDED
        assert run.summary["failed_count"] == 0
        assert run.summary["paused_awaiting_admin_count"] == 1
        result.loan.refresh_from_db()
        order.refresh_from_db()
        assert result.loan.status == "published"
        assert order.status == "balance_allocated"

    paused_tasks = _tasks("PausedSubscriptionRound", result.loan)
    assert paused_tasks.count() == 1
    task = paused_tasks.get()
    assert task.status == "open"
    assert "Resume subscription" in task.notes
    assert "Cancel and refund" in task.notes
    assert not _tasks("LoanFundingCloseFailure", result.loan).exists()
    assert not OutboxMessage.objects.filter(topic="email.originator_funding_close_failed").exists()

    with freeze_time(_noon(deadline + timedelta(days=2))):
        resumed = resume_originator_subscription(
            ResumeOriginatorSubscriptionCommand(
                actor=admin_user,
                loan_id=str(result.loan.pk),
                reason="Evidence checked; publish result stands.",
            )
        )
    assert resumed.is_on_hold is False
    task.refresh_from_db()
    assert task.status == "resolved"
    assert OriginatorClaimEvent.objects.filter(
        loan_id=result.loan.pk,
        event_type=OriginatorClaimEventType.OPPORTUNITY_RESUMED,
    ).exists()

    run = _daily_job(admin_user, deadline + timedelta(days=3))
    assert run.status == ScheduledJobRunStatus.SUCCEEDED
    assert run.summary["closed"][0]["reason"] == "funding_deadline_reached"
    close = OriginatorFundingRoundClose.objects.get(loan_profile=result.profile)
    assert close.subscribed_principal_minor == 160_000


@pytest.mark.django_db
def test_admin_closes_paused_round_only_on_or_after_its_deadline(
    client: Client,
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
) -> None:
    result, _order = _paused_round(admin_user, investor, "PAUSE-CLOSE")
    deadline = T0 + timedelta(days=5)

    def close(day: date, key: str) -> Any:
        with freeze_time(_noon(day)):
            client.logout()
            client.force_login(cast(Any, admin_user))
            return client.post(
                f"/api/v1/originator-claims/admin/loans/{result.loan.pk}/funding-close/",
                data={
                    "as_of_date": day.isoformat(),
                    "close_reason": "admin_decision_after_pause",
                    "idempotency_key": key,
                },
                content_type="application/json",
            )

    early = close(deadline - timedelta(days=1), "pause-close-early")
    assert early.status_code == 400
    assert "on or after its funding deadline" in early.json()["detail"]

    # The automatic (non-admin-decision) path never closes a paused round.
    with freeze_time(_noon(deadline + timedelta(days=1))):
        with pytest.raises(OriginatorClaimsValidationError, match="funding round is paused"):
            close_originator_subscription_round(
                CloseOriginatorSubscriptionRoundCommand(
                    actor=admin_user,
                    loan_id=str(result.loan.pk),
                    as_of_date=deadline + timedelta(days=1),
                    close_reason="funding_deadline_reached",
                    idempotency_key="pause-close-auto",
                )
            )
    _daily_job(admin_user, deadline + timedelta(days=1))
    assert _tasks("PausedSubscriptionRound", result.loan).get().status == "open"

    response = close(deadline + timedelta(days=1), "pause-close-admin")
    assert response.status_code == 200, response.json()
    result.profile.refresh_from_db()
    assert result.profile.is_on_hold is False
    close_record = OriginatorFundingRoundClose.objects.get(loan_profile=result.profile)
    assert close_record.subscribed_principal_minor == 160_000
    assert close_record.metadata["paused_round_closed_by_admin"] is True
    assert _tasks("PausedSubscriptionRound", result.loan).get().status == "resolved"


@pytest.mark.django_db
def test_admin_cancels_and_refunds_paused_round_after_its_deadline(
    client: Client,
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
) -> None:
    result, order = _paused_round(admin_user, investor, "PAUSE-CANCEL")
    deadline = T0 + timedelta(days=5)
    _daily_job(admin_user, deadline + timedelta(days=1))

    with freeze_time(_noon(deadline + timedelta(days=2))):
        client.force_login(cast(Any, admin_user))
        response = client.post(
            f"/api/v1/originator-claims/admin/loans/{result.loan.pk}/subscription-cancel/",
            data={
                "reason": "Evidence could not be confirmed.",
                "investor_message": "The subscription was cancelled. Your money is back.",
                "idempotency_key": "pause-cancel",
            },
            content_type="application/json",
        )

    # Old code: "The published subscription condition is met..." (400).
    assert response.status_code == 200, response.json()
    cancellation = OriginatorSubscriptionCancellation.objects.get(loan_profile=result.profile)
    assert cancellation.released_principal_minor == 160_000
    order.refresh_from_db()
    result.loan.refresh_from_db()
    assert order.status != "balance_allocated"
    assert result.loan.status == "cancelled"
    assert _tasks("PausedSubscriptionRound", result.loan).get().status == "resolved"


@pytest.mark.django_db
def test_round_stuck_by_old_code_is_skipped_and_can_be_resumed(
    client: Client,
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
) -> None:
    result, _order = _paused_round(admin_user, investor, "PAUSE-LEGACY")
    deadline = T0 + timedelta(days=5)
    # What the old daily job left behind: status funding_close_failed, hold kept.
    with freeze_time(_noon(deadline + timedelta(days=1))):
        mark_originator_funding_close_failed(
            triggering_actor=admin_user,
            loan_id=str(result.loan.pk),
            as_of_date=deadline + timedelta(days=1),
            resolution_action="funding-deadline close",
            error=OriginatorClaimsValidationError("held round"),
        )
    result.loan.refresh_from_db()
    assert result.loan.status == "funding_close_failed"
    emails_before = OutboxMessage.objects.filter(
        topic="email.originator_funding_close_failed"
    ).count()

    run = _daily_job(admin_user, deadline + timedelta(days=2))
    assert run.status == ScheduledJobRunStatus.SUCCEEDED
    assert run.summary["paused_awaiting_admin_count"] == 1
    assert (
        OutboxMessage.objects.filter(topic="email.originator_funding_close_failed").count()
        == emails_before
    )

    with freeze_time(_noon(deadline + timedelta(days=2))):
        client.force_login(cast(Any, admin_user))
        detail = client.get(f"/api/v1/originator-claims/admin/loans/{result.loan.pk}/")
        assert detail.json()["is_subscription_paused"] is True
        response = client.post(
            f"/api/v1/originator-claims/admin/loans/{result.loan.pk}/subscription-resume/",
            data={"reason": "Checked."},
            content_type="application/json",
        )
    assert response.status_code == 200, response.json()
    assert response.json()["is_on_hold"] is False

    run = _daily_job(admin_user, deadline + timedelta(days=3))
    assert run.status == ScheduledJobRunStatus.SUCCEEDED
    assert OriginatorFundingRoundClose.objects.filter(loan_profile=result.profile).exists()
    assert _tasks("LoanFundingCloseFailure", result.loan).get().status == "resolved"


@pytest.mark.django_db
def test_resume_refuses_a_round_that_is_not_paused(
    client: Client,
    admin_user: Model,  # noqa: F811
    investor: Model,  # noqa: F811
) -> None:
    with freeze_time(_noon(T0)):
        result = _create_par_subscription_loan(admin_user=admin_user, today=T0, suffix="NOPAUSE")
    with freeze_time(_noon(T0)):
        client.force_login(cast(Any, admin_user))
        response = client.post(
            f"/api/v1/originator-claims/admin/loans/{result.loan.pk}/subscription-resume/",
            data={"reason": "Nothing to resume."},
            content_type="application/json",
        )
    assert response.status_code == 400
    assert "not paused" in response.json()["detail"]
