from __future__ import annotations

from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from django.db.models import Model
from django.test import Client
from django.utils import timezone

from backend.apps.kyc_compliance.models import (
    KycManualReviewDecision,
    KycManualReviewDecisionType,
    KycManualReviewReason,
    KycStatus,
)
from backend.apps.kyc_compliance.services import (
    CreateKycSessionCommand,
    KycManualReviewError,
    ManualReviewDecisionCommand,
    ProviderKycEventCommand,
    create_kyc_session,
    get_or_create_user_kyc_case,
    process_didit_event,
    record_manual_review_decision,
    user_can_access_financial_features,
)
from backend.apps.platform_core.models import AuditEvent, DomainEvent
from backend.apps.platform_core.models.base import AppendOnlyViolation


def create_lender(email: str = "investor@example.test") -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email=email,
            full_name="Investor",
            account_type="natural_person_lender",
            status="pending_kyc",
            phone_number="+41790000000",
        ),
    )


def create_admin(email: str = "admin@example.test") -> Model:
    user_model: Any = get_user_model()
    return cast(
        Model,
        user_model.objects.create_user(
            email=email,
            password="AdminPass123!",
            full_name="Admin",
            account_type="admin",
            status="active",
            is_staff=True,
        ),
    )


def mark_phone_verified(user: Model) -> None:
    user_with_phone = cast(Any, user)
    user_with_phone.phone_verified_at = timezone.now()
    user.save(update_fields=["phone_verified_at"])


@pytest.mark.django_db
def test_provider_flag_opens_internal_manual_review_queue() -> None:
    user = create_lender()
    session_result = create_kyc_session(CreateKycSessionCommand(user=user))
    assert session_result.session is not None

    result = process_didit_event(
        ProviderKycEventCommand(
            provider_event_id="didit-event-pep",
            provider_event_type="verification.completed",
            provider_status="approved",
            provider_session_id=session_result.session.provider_session_id,
            vendor_data=f"user:{user.pk}",
            detected_flags=["pep"],
            risk_classification="low",
            raw_payload={"id": "didit-event-pep", "status": "approved"},
        )
    )

    assert result.case.status == KycStatus.PEP_HIT
    assert result.case.manual_review_required is True
    assert user_can_access_financial_features(user) is False


@pytest.mark.django_db
def test_didit_in_review_status_maps_to_manual_review() -> None:
    user = create_lender()
    session_result = create_kyc_session(CreateKycSessionCommand(user=user))
    assert session_result.session is not None

    result = process_didit_event(
        ProviderKycEventCommand(
            provider_event_id="didit-event-in-review",
            provider_event_type="verification.updated",
            provider_status="in_review",
            provider_session_id=session_result.session.provider_session_id,
            vendor_data=f"user:{user.pk}",
            raw_payload={"id": "didit-event-in-review", "status": "In Review"},
        )
    )

    assert result.case.status == KycStatus.MANUAL_REVIEW
    assert result.case.manual_review_required is True


@pytest.mark.django_db
def test_manual_review_approval_activates_pending_kyc_user() -> None:
    user = create_lender()
    mark_phone_verified(user)
    admin = create_admin()
    session_result = create_kyc_session(CreateKycSessionCommand(user=user))
    assert session_result.session is not None
    event_result = process_didit_event(
        ProviderKycEventCommand(
            provider_event_id="didit-event-high-risk",
            provider_event_type="verification.completed",
            provider_status="approved",
            provider_session_id=session_result.session.provider_session_id,
            vendor_data=f"user:{user.pk}",
            risk_classification="high",
            raw_payload={"id": "didit-event-high-risk"},
        )
    )

    decision = record_manual_review_decision(
        ManualReviewDecisionCommand(
            actor=admin,
            case_id=str(event_result.case.id),
            decision=KycManualReviewDecisionType.APPROVE,
            reason_code=KycManualReviewReason.HIGH_RISK_REVIEW,
            note="Approved after enhanced due-diligence review.",
        )
    )

    event_result.case.refresh_from_db()
    user.refresh_from_db()
    assert decision.previous_status == KycStatus.HIGH_RISK
    assert decision.new_status == KycStatus.APPROVED
    assert event_result.case.status == KycStatus.APPROVED
    assert event_result.case.manual_review_required is False
    assert cast(Any, user).status == "active"
    assert user_can_access_financial_features(user) is True
    assert AuditEvent.objects.filter(
        action="kyc.manual_review_decision_recorded",
        target_id=str(event_result.case.id),
    ).exists()
    assert DomainEvent.objects.filter(
        event_type="KycManualReviewDecisionRecorded",
        aggregate_id=str(event_result.case.id),
    ).exists()


@pytest.mark.django_db
def test_manual_review_cannot_approve_sanctions_hit() -> None:
    user = create_lender()
    admin = create_admin()
    session_result = create_kyc_session(CreateKycSessionCommand(user=user))
    assert session_result.session is not None
    event_result = process_didit_event(
        ProviderKycEventCommand(
            provider_event_id="didit-event-sanctions",
            provider_event_type="verification.completed",
            provider_status="approved",
            provider_session_id=session_result.session.provider_session_id,
            vendor_data=f"user:{user.pk}",
            detected_flags=["sanctions"],
            raw_payload={"id": "didit-event-sanctions"},
        )
    )

    with pytest.raises(KycManualReviewError):
        record_manual_review_decision(
            ManualReviewDecisionCommand(
                actor=admin,
                case_id=str(event_result.case.id),
                decision=KycManualReviewDecisionType.APPROVE,
                reason_code=KycManualReviewReason.SANCTIONS_REVIEW,
                note="Should not be allowed.",
            )
        )

    event_result.case.refresh_from_db()
    assert event_result.case.status == KycStatus.SANCTIONS_HIT
    assert event_result.case.manual_review_required is True


@pytest.mark.django_db
def test_manual_review_cannot_approve_not_started_case() -> None:
    user = create_lender()
    admin = create_admin()
    case = get_or_create_user_kyc_case(user)

    with pytest.raises(KycManualReviewError):
        record_manual_review_decision(
            ManualReviewDecisionCommand(
                actor=admin,
                case_id=str(case.id),
                decision=KycManualReviewDecisionType.APPROVE,
                reason_code=KycManualReviewReason.OFF_PLATFORM_REVIEW,
                note="Should not be allowed without provider review.",
            )
        )

    case.refresh_from_db()
    user.refresh_from_db()
    assert case.status == KycStatus.NOT_STARTED
    assert cast(Any, user).status == "pending_kyc"
    assert KycManualReviewDecision.objects.filter(case=case).count() == 0


@pytest.mark.django_db
def test_manual_review_cannot_approve_pending_case() -> None:
    user = create_lender()
    admin = create_admin()
    session_result = create_kyc_session(CreateKycSessionCommand(user=user))
    assert session_result.session is not None
    case = session_result.case

    with pytest.raises(KycManualReviewError):
        record_manual_review_decision(
            ManualReviewDecisionCommand(
                actor=admin,
                case_id=str(case.id),
                decision=KycManualReviewDecisionType.APPROVE,
                reason_code=KycManualReviewReason.OFF_PLATFORM_REVIEW,
                note="Should not be allowed while the provider case is pending.",
            )
        )

    case.refresh_from_db()
    user.refresh_from_db()
    assert case.status == KycStatus.PENDING
    assert cast(Any, user).status == "pending_kyc"
    assert KycManualReviewDecision.objects.filter(case=case).count() == 0


@pytest.mark.django_db
def test_manual_review_api_lists_and_records_decision(client: Client) -> None:
    user = create_lender()
    admin = create_admin()
    client.force_login(cast(Any, admin))
    session_result = create_kyc_session(CreateKycSessionCommand(user=user))
    assert session_result.session is not None
    event_result = process_didit_event(
        ProviderKycEventCommand(
            provider_event_id="didit-event-adverse-media",
            provider_event_type="verification.completed",
            provider_status="approved",
            provider_session_id=session_result.session.provider_session_id,
            vendor_data=f"user:{user.pk}",
            detected_flags=["adverse_media"],
            raw_payload={"id": "didit-event-adverse-media"},
        )
    )

    list_response = client.get("/api/v1/kyc/admin/manual-reviews/")
    decision_response = client.post(
        f"/api/v1/kyc/admin/cases/{event_result.case.id}/manual-review/",
        data={
            "decision": KycManualReviewDecisionType.DECLINE,
            "reason_code": KycManualReviewReason.ADVERSE_MEDIA_REVIEW,
            "note": "Declined after adverse media review.",
        },
        content_type="application/json",
    )

    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["id"] == str(event_result.case.id)
    assert decision_response.status_code == 200
    assert decision_response.json()["case"]["status"] == KycStatus.DECLINED
    assert decision_response.json()["case"]["manual_review_required"] is False


@pytest.mark.django_db
def test_manual_review_decisions_are_append_only() -> None:
    user = create_lender()
    admin = create_admin()
    session_result = create_kyc_session(CreateKycSessionCommand(user=user))
    assert session_result.session is not None
    event_result = process_didit_event(
        ProviderKycEventCommand(
            provider_event_id="didit-event-append-review",
            provider_event_type="verification.updated",
            provider_status="in_review",
            provider_session_id=session_result.session.provider_session_id,
            vendor_data=f"user:{user.pk}",
            raw_payload={"id": "didit-event-append-review"},
        )
    )
    decision = record_manual_review_decision(
        ManualReviewDecisionCommand(
            actor=admin,
            case_id=str(event_result.case.id),
            decision=KycManualReviewDecisionType.REQUEST_REVERIFICATION,
            reason_code=KycManualReviewReason.REVERIFICATION_REQUIRED,
            note="New document required.",
        )
    )

    decision.note = "changed"
    with pytest.raises(AppendOnlyViolation):
        decision.save()
    with pytest.raises(AppendOnlyViolation):
        KycManualReviewDecision.objects.filter(id=decision.id).update(note="changed")
    with pytest.raises(AppendOnlyViolation):
        KycManualReviewDecision.objects.filter(id=decision.id).delete()

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE kyc_compliance_kycmanualreviewdecision SET note = %s WHERE id = %s",
                ["changed", decision.id],
            )

    with pytest.raises(DatabaseError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM kyc_compliance_kycmanualreviewdecision WHERE id = %s",
                [decision.id],
            )
