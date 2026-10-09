"""A flagged KYC case stays with the admins (audit A-14 / SECCODE-01).

Neither the investor (starting a new provider session) nor a later provider event may clear a
case that needs an admin decision. Only an admin decision moves it, and an admin request for
re-verification is the one way to let the investor start again.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, cast

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.kyc_compliance.models import (
    KycManualReviewDecisionType,
    KycManualReviewReason,
    KycProviderEvent,
    KycProviderSession,
    KycStatus,
    KycVerificationCase,
)
from backend.apps.kyc_compliance.services import (
    KYC_REVIEW_IN_PROGRESS_MESSAGE,
    CreateKycSessionCommand,
    KycSessionStartBlockedError,
    ManualReviewDecisionCommand,
    ProviderKycEventCommand,
    ProviderKycEventResult,
    create_kyc_session,
    process_didit_event,
    record_manual_review_decision,
    user_can_access_financial_features,
)
from backend.apps.platform_core.models import AuditEvent

SESSION_URL = "/api/v1/kyc/session/"
STATUS_URL = "/api/v1/kyc/status/"
MANUAL_REVIEWS_URL = "/api/v1/kyc/admin/manual-reviews/"

# Provider results that must stay with the admins: (provider status, flags, risk, internal status).
FLAGGED_RESULTS = [
    pytest.param("Declined", ["sanctions"], "", KycStatus.SANCTIONS_HIT, id="sanctions_hit"),
    pytest.param("Declined", [], "", KycStatus.DECLINED, id="declined"),
    pytest.param("In Review", [], "", KycStatus.MANUAL_REVIEW, id="manual_review"),
    pytest.param("Approved", ["pep"], "", KycStatus.PEP_HIT, id="pep_hit"),
    pytest.param(
        "Approved", ["adverse_media"], "", KycStatus.ADVERSE_MEDIA_HIT, id="adverse_media"
    ),
    pytest.param("Approved", [], "high", KycStatus.HIGH_RISK, id="high_risk"),
    pytest.param("Resubmitted", [], "", KycStatus.REVERIFICATION_REQUIRED, id="provider_recheck"),
]


def create_lender(email: str = "held-investor@example.test") -> Model:
    user_model: Any = get_user_model()
    user = user_model.objects.create_user(
        email=email,
        full_name="Held Investor",
        account_type="natural_person_lender",
        status="pending_kyc",
        phone_number="+41790000000",
    )
    user.phone_verified_at = timezone.now()
    user.save(update_fields=["phone_verified_at"])
    return cast(Model, user)


def create_admin(email: str = "kyc-admin@example.test") -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email=email,
            password="AdminPass123!",
            full_name="KYC Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


def investor_client(user: Model) -> Client:
    client = Client()
    client.force_login(cast(Any, user))
    return client


def provider_event(
    user: Model,
    *,
    event_id: str,
    status: str,
    session_id: str = "",
    flags: list[str] | None = None,
    risk: str = "",
) -> ProviderKycEventResult:
    return process_didit_event(
        ProviderKycEventCommand(
            provider_event_id=event_id,
            provider_event_type="status.updated",
            provider_status=status,
            provider_session_id=session_id,
            vendor_data=f"user:{user.pk}",
            detected_flags=list(flags or []),
            risk_classification=risk,
            raw_payload={"event_id": event_id, "status": status, "session_id": session_id},
        )
    )


def decide(admin: Model, case: KycVerificationCase, decision: str, reason: str) -> None:
    record_manual_review_decision(
        ManualReviewDecisionCommand(
            actor=admin,
            case_id=str(case.id),
            decision=KycManualReviewDecisionType(decision),
            reason_code=KycManualReviewReason(reason),
            note=f"Admin {decision}.",
        )
    )


def kyc_review_tasks(case: KycVerificationCase) -> Any:
    task_model = apps.get_model("admin_ops", "AdminTask")
    return task_model.objects.filter(
        task_type="kyc_manual_review",
        related_object_type="KycVerificationCase",
        related_object_id=str(case.id),
    )


def open_kyc_review_task(case: KycVerificationCase) -> Any:
    return kyc_review_tasks(case).filter(status__in=["open", "in_progress", "waiting"]).first()


def flagged_case(
    user: Model,
    *,
    status: str,
    flags: list[str],
    risk: str,
    expected: KycStatus,
) -> tuple[KycVerificationCase, str]:
    response = investor_client(user).post(SESSION_URL, data={}, content_type="application/json")
    assert response.status_code == 202
    session_id = response.json()["provider_session_id"]
    result = provider_event(
        user, event_id="evt-flagged", status=status, session_id=session_id, flags=flags, risk=risk
    )
    assert result.case.status == expected
    assert result.case.manual_review_required is True
    return result.case, session_id


def snapshot(case: KycVerificationCase) -> tuple[str, bool, str, str]:
    case.refresh_from_db()
    return (
        case.status,
        case.manual_review_required,
        case.blocking_reason,
        case.provider_session_id,
    )


def in_admin_queue(admin: Model, case: KycVerificationCase) -> bool:
    response = investor_client(admin).get(MANUAL_REVIEWS_URL)
    assert response.status_code == 200
    return any(item["id"] == str(case.id) for item in response.json())


@pytest.mark.django_db
@pytest.mark.parametrize(("provider_status", "flags", "risk", "expected"), FLAGGED_RESULTS)
def test_investor_cannot_restart_a_flagged_case(
    provider_status: str, flags: list[str], risk: str, expected: KycStatus
) -> None:
    user = create_lender()
    admin = create_admin()
    case, _session_id = flagged_case(
        user, status=provider_status, flags=flags, risk=risk, expected=expected
    )
    before = snapshot(case)
    assert in_admin_queue(admin, case)
    task = open_kyc_review_task(case)
    assert task is not None
    assert task.priority == ("urgent" if expected == KycStatus.SANCTIONS_HIT else "high")

    response = investor_client(user).post(SESSION_URL, data={}, content_type="application/json")

    assert response.status_code == 409
    assert response.json() == {
        "detail": KYC_REVIEW_IN_PROGRESS_MESSAGE,
        "code": "kyc_review_in_progress",
    }
    assert "sanction" not in response.content.decode().lower()
    assert snapshot(case) == before
    assert KycProviderSession.objects.filter(case=case).count() == 1
    assert in_admin_queue(admin, case)
    assert open_kyc_review_task(case) is not None
    assert AuditEvent.objects.filter(
        action="kyc.session_start_refused", target_id=str(case.id)
    ).exists()
    with pytest.raises(KycSessionStartBlockedError):
        create_kyc_session(CreateKycSessionCommand(user=user, force_new=True))
    assert snapshot(case) == before


@pytest.mark.django_db
@pytest.mark.parametrize(("provider_status", "flags", "risk", "expected"), FLAGGED_RESULTS)
def test_later_provider_events_do_not_clear_a_flagged_case(
    provider_status: str, flags: list[str], risk: str, expected: KycStatus
) -> None:
    user = create_lender()
    admin = create_admin()
    case, session_id = flagged_case(
        user, status=provider_status, flags=flags, risk=risk, expected=expected
    )
    before = snapshot(case)

    approved = provider_event(
        user, event_id="evt-approved", status="Approved", session_id=session_id
    )
    unmatched = provider_event(user, event_id="evt-approved-unknown-session", status="Approved")
    in_progress = provider_event(
        user, event_id="evt-in-progress", status="In Progress", session_id=session_id
    )
    expired = provider_event(user, event_id="evt-expired", status="Expired", session_id=session_id)

    assert snapshot(case) == before
    for result in (approved, unmatched, in_progress, expired):
        assert result.case.status == expected
    user.refresh_from_db()
    assert cast(Any, user).status == "pending_kyc"
    assert user_can_access_financial_features(user) is False
    # The provider result is kept as evidence for the admin, and the review item stays open.
    assert KycProviderEvent.objects.get(provider_event_id="evt-approved").normalized_status == (
        KycStatus.APPROVED
    )
    assert in_admin_queue(admin, case)
    task = open_kyc_review_task(case)
    assert task is not None
    assert "approved" in task.notes.lower()
    assert kyc_review_tasks(case).count() == 1
    assert (
        AuditEvent.objects.filter(
            action="kyc.didit_event_held_for_review", target_id=str(case.id)
        ).count()
        == 4
    )


@pytest.mark.django_db
def test_investor_status_does_not_reveal_a_sanctions_hit() -> None:
    user = create_lender()
    admin = create_admin()
    case, _session_id = flagged_case(
        user, status="Declined", flags=["sanctions"], risk="", expected=KycStatus.SANCTIONS_HIT
    )

    response = investor_client(user).get(STATUS_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == KycStatus.MANUAL_REVIEW
    assert body["detected_flags"] == []
    assert body["risk_classification"] == ""
    assert "sanction" not in response.content.decode().lower()
    admin_rows = investor_client(admin).get(MANUAL_REVIEWS_URL).json()
    assert [row["status"] for row in admin_rows if row["id"] == str(case.id)] == [
        KycStatus.SANCTIONS_HIT
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("first_result", "decision", "reason", "expected"),
    [
        pytest.param(
            ("In Review", [], ""),
            "decline",
            "document_or_identity_issue",
            KycStatus.DECLINED,
            id="admin_decline",
        ),
        pytest.param(
            ("Approved", [], "low"),
            "reopen",
            "admin_correction",
            KycStatus.MANUAL_REVIEW,
            id="admin_reopen_of_approved_case",
        ),
    ],
)
def test_admin_held_cases_stay_held(
    first_result: tuple[str, list[str], str], decision: str, reason: str, expected: KycStatus
) -> None:
    user = create_lender()
    admin = create_admin()
    response = investor_client(user).post(SESSION_URL, data={}, content_type="application/json")
    session_id = response.json()["provider_session_id"]
    status, flags, risk = first_result
    case = provider_event(
        user, event_id="evt-first", status=status, session_id=session_id, flags=flags, risk=risk
    ).case
    decide(admin, case, decision, reason)
    before = snapshot(case)
    assert before[0] == expected

    refused = investor_client(user).post(SESSION_URL, data={}, content_type="application/json")
    late = provider_event(
        user, event_id="evt-late-approved", status="Approved", session_id=session_id
    )

    assert refused.status_code == 409
    assert refused.json()["detail"] == KYC_REVIEW_IN_PROGRESS_MESSAGE
    assert late.case.status == expected
    assert snapshot(case) == before
    assert user_can_access_financial_features(user) is False
    assert KycProviderSession.objects.filter(case=case).count() == 1
    # A provider result that disagrees with the admin decision is put in front of an admin.
    assert open_kyc_review_task(case) is not None


@pytest.mark.django_db
def test_admin_request_for_reverification_lets_the_investor_start_again() -> None:
    user = create_lender()
    admin = create_admin()
    case, old_session_id = flagged_case(
        user, status="Declined", flags=["sanctions"], risk="", expected=KycStatus.SANCTIONS_HIT
    )

    decide(admin, case, "request_reverification", "sanctions_review")
    case.refresh_from_db()
    assert case.status == KycStatus.REVERIFICATION_REQUIRED
    assert open_kyc_review_task(case) is None
    assert kyc_review_tasks(case).get().status == "resolved"
    assert KycProviderSession.objects.get(provider_session_id=old_session_id).superseded_at

    status_body = investor_client(user).get(STATUS_URL).json()
    assert status_body["status"] == KycStatus.REVERIFICATION_REQUIRED
    assert status_body["manual_review_required"] is False
    response = investor_client(user).post(SESSION_URL, data={}, content_type="application/json")
    assert response.status_code == 202
    new_session_id = response.json()["provider_session_id"]
    assert new_session_id != old_session_id
    case.refresh_from_db()
    assert case.status == KycStatus.PENDING
    assert case.provider_session_id == new_session_id
    # The admin's reason stays on the case until a provider result replaces it.
    assert case.blocking_reason == KycManualReviewReason.SANCTIONS_REVIEW

    # A late result for the superseded session cannot approve the case.
    late = provider_event(
        user, event_id="evt-old-approved", status="Approved", session_id=old_session_id
    )
    assert late.held_for_review is True
    assert late.case.status == KycStatus.PENDING
    user.refresh_from_db()
    assert cast(Any, user).status == "pending_kyc"
    # The investor is re-verifying at the admin's request: no new admin task for old evidence.
    assert open_kyc_review_task(case) is None

    approved = provider_event(
        user, event_id="evt-new-approved", status="Approved", session_id=new_session_id
    )
    assert approved.case.status == KycStatus.APPROVED
    user.refresh_from_db()
    assert cast(Any, user).status == "active"
    assert user_can_access_financial_features(user) is True
    assert open_kyc_review_task(case) is None


@pytest.mark.django_db
def test_new_flag_after_reverification_reopens_the_review_task() -> None:
    user = create_lender()
    admin = create_admin()
    case, _old_session_id = flagged_case(
        user, status="In Review", flags=[], risk="", expected=KycStatus.MANUAL_REVIEW
    )
    decide(admin, case, "request_reverification", "document_or_identity_issue")
    response = investor_client(user).post(SESSION_URL, data={}, content_type="application/json")
    new_session_id = response.json()["provider_session_id"]

    result = provider_event(
        user, event_id="evt-new-pep", status="Approved", session_id=new_session_id, flags=["pep"]
    )

    assert result.case.status == KycStatus.PEP_HIT
    assert result.case.manual_review_required is True
    assert open_kyc_review_task(case) is not None
    assert kyc_review_tasks(case).count() == 1
    assert (
        investor_client(user)
        .post(SESSION_URL, data={}, content_type="application/json")
        .status_code
        == 409
    )


@pytest.mark.django_db
def test_provider_recheck_without_admin_request_is_still_held() -> None:
    user = create_lender()
    admin = create_admin()
    case, _session_id = flagged_case(
        user, status="In Review", flags=[], risk="", expected=KycStatus.MANUAL_REVIEW
    )
    # An earlier admin request does not authorise a later, provider-reported re-check.
    decide(admin, case, "request_reverification", "document_or_identity_issue")
    new_session_id = (
        investor_client(user)
        .post(SESSION_URL, data={}, content_type="application/json")
        .json()["provider_session_id"]
    )
    provider_event(user, event_id="evt-recheck", status="Resubmitted", session_id=new_session_id)
    case.refresh_from_db()
    assert case.status == KycStatus.REVERIFICATION_REQUIRED
    assert case.manual_review_required is True

    response = investor_client(user).post(SESSION_URL, data={}, content_type="application/json")

    assert response.status_code == 409
    assert KycProviderSession.objects.filter(case=case).count() == 2


@pytest.mark.django_db
def test_admin_approval_of_review_case_activates_and_resolves_task() -> None:
    user = create_lender()
    admin = create_admin()
    case, session_id = flagged_case(
        user, status="Approved", flags=["pep"], risk="", expected=KycStatus.PEP_HIT
    )

    decide(admin, case, "approve", "pep_review")

    case.refresh_from_db()
    user.refresh_from_db()
    assert case.status == KycStatus.APPROVED
    assert cast(Any, user).status == "active"
    assert user_can_access_financial_features(user) is True
    assert open_kyc_review_task(case) is None

    # The provider repeating the result the admin already cleared does not undo the approval.
    repeat = provider_event(
        user, event_id="evt-pep-again", status="Approved", session_id=session_id, flags=["pep"]
    )
    duplicate = provider_event(
        user, event_id="evt-approved-again", status="Approved", session_id=session_id
    )
    assert repeat.case.status == KycStatus.APPROVED
    assert duplicate.case.status == KycStatus.APPROVED
    assert user_can_access_financial_features(user) is True
    # ...but the disagreeing provider result is put back in front of an admin.
    task = open_kyc_review_task(case)
    assert task is not None
    assert "pep_hit" in task.notes


@pytest.mark.django_db
def test_admin_reopen_locks_access_and_approval_restores_it() -> None:
    user = create_lender()
    admin = create_admin()
    session_id = (
        investor_client(user)
        .post(SESSION_URL, data={}, content_type="application/json")
        .json()["provider_session_id"]
    )
    case = provider_event(user, event_id="evt-ok", status="Approved", session_id=session_id).case
    assert user_can_access_financial_features(user) is True

    decide(admin, case, "reopen", "admin_correction")
    assert user_can_access_financial_features(user) is False
    assert (
        investor_client(user)
        .post(SESSION_URL, data={}, content_type="application/json")
        .status_code
        == 409
    )

    decide(admin, case, "approve", "admin_correction")
    assert user_can_access_financial_features(user) is True


@pytest.mark.django_db
def test_first_verification_approves_and_activates() -> None:
    user = create_lender()
    client = investor_client(user)

    response = client.post(SESSION_URL, data={}, content_type="application/json")
    assert response.status_code == 202
    session_id = response.json()["provider_session_id"]
    result = provider_event(user, event_id="evt-first-ok", status="Approved", session_id=session_id)

    assert result.case.status == KycStatus.APPROVED
    assert result.case.manual_review_required is False
    assert kyc_review_tasks(result.case).count() == 0
    user.refresh_from_db()
    assert cast(Any, user).status == "active"
    again = client.post(SESSION_URL, data={}, content_type="application/json")
    assert again.status_code == 200
    assert again.json()["already_approved"] is True


@pytest.mark.django_db
def test_expired_provider_session_can_be_restarted_while_pending() -> None:
    user = create_lender()
    client = investor_client(user)
    first_id = client.post(SESSION_URL, data={}, content_type="application/json").json()[
        "provider_session_id"
    ]
    reused_id = client.post(SESSION_URL, data={}, content_type="application/json").json()[
        "provider_session_id"
    ]
    assert reused_id == first_id
    KycProviderSession.objects.filter(provider_session_id=first_id).update(
        expires_at=timezone.now() - timedelta(minutes=1)
    )

    response = client.post(SESSION_URL, data={}, content_type="application/json")

    assert response.status_code == 202
    second_id = response.json()["provider_session_id"]
    assert second_id != first_id
    case = KycVerificationCase.objects.get(user_id=user.pk)
    assert case.status == KycStatus.PENDING
    assert case.provider_session_id == second_id
    assert (
        provider_event(
            user, event_id="evt-second-ok", status="Approved", session_id=second_id
        ).case.status
        == KycStatus.APPROVED
    )


@pytest.mark.django_db
def test_provider_expired_case_can_be_restarted() -> None:
    user = create_lender()
    client = investor_client(user)
    session_id = client.post(SESSION_URL, data={}, content_type="application/json").json()[
        "provider_session_id"
    ]
    case = provider_event(
        user, event_id="evt-abandoned", status="Abandoned", session_id=session_id
    ).case
    assert case.status == KycStatus.EXPIRED
    assert case.manual_review_required is False

    response = client.post(SESSION_URL, data={}, content_type="application/json")

    assert response.status_code == 202
    assert response.json()["provider_session_id"] != session_id
    case.refresh_from_db()
    assert case.status == KycStatus.PENDING


@pytest.mark.django_db
def test_provider_flag_on_provider_approved_case_blocks_access() -> None:
    user = create_lender()
    session_id = (
        investor_client(user)
        .post(SESSION_URL, data={}, content_type="application/json")
        .json()["provider_session_id"]
    )
    provider_event(user, event_id="evt-approved-first", status="Approved", session_id=session_id)
    assert user_can_access_financial_features(user) is True

    result = provider_event(
        user,
        event_id="evt-sanctions-later",
        status="Declined",
        session_id=session_id,
        flags=["sanctions"],
    )
    stale = provider_event(
        user, event_id="evt-in-progress-late", status="In Progress", session_id=session_id
    )

    assert result.case.status == KycStatus.SANCTIONS_HIT
    assert result.case.manual_review_required is True
    assert stale.case.status == KycStatus.SANCTIONS_HIT
    assert user_can_access_financial_features(user) is False
    assert open_kyc_review_task(result.case) is not None


@pytest.mark.django_db
def test_stale_provider_progress_does_not_revoke_an_approval() -> None:
    user = create_lender()
    session_id = (
        investor_client(user)
        .post(SESSION_URL, data={}, content_type="application/json")
        .json()["provider_session_id"]
    )
    provider_event(user, event_id="evt-approved-ok", status="Approved", session_id=session_id)

    stale = provider_event(
        user, event_id="evt-in-progress-old", status="In Progress", session_id=session_id
    )

    assert stale.case.status == KycStatus.APPROVED
    assert user_can_access_financial_features(user) is True
