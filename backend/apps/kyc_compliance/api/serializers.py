from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.kyc_compliance.models import (
    KycManualReviewDecision,
    KycManualReviewDecisionType,
    KycManualReviewReason,
    KycProviderSession,
    KycStatus,
    KycVerificationCase,
)
from backend.apps.kyc_compliance.services import user_can_access_financial_features


class KycStatusResponseSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=KycStatus.choices)
    financial_access_allowed = serializers.BooleanField()
    phone_verified = serializers.BooleanField()
    provider = serializers.CharField()
    provider_session_id = serializers.CharField(allow_blank=True)
    verification_url = serializers.URLField(allow_blank=True, allow_null=True)
    manual_review_required = serializers.BooleanField()
    detected_flags = serializers.ListField(child=serializers.CharField())
    risk_classification = serializers.CharField(allow_blank=True)


class KycSessionResponseSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=KycStatus.choices)
    provider_session_id = serializers.CharField(allow_null=True)
    verification_url = serializers.URLField(allow_null=True)
    already_approved = serializers.BooleanField()


class DiditWebhookResponseSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(choices=KycStatus.choices)
    idempotent = serializers.BooleanField()


class KycAdminCaseSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    subject_type = serializers.CharField()
    subject_reference = serializers.CharField()
    user_id = serializers.UUIDField(allow_null=True)
    user_full_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    investor_reference = serializers.SerializerMethodField()
    provider = serializers.CharField()
    provider_environment = serializers.CharField()
    workflow_id = serializers.CharField()
    status = serializers.CharField()
    manual_review_required = serializers.BooleanField()
    blocking_reason = serializers.CharField()
    risk_classification = serializers.CharField()
    detected_flags = serializers.ListField(child=serializers.CharField())
    provider_session_id = serializers.CharField()
    provider_verification_id = serializers.CharField()
    provider_report_id = serializers.CharField()
    aml_screening_id = serializers.CharField()
    provider_subject_id = serializers.CharField()
    decision_at = serializers.DateTimeField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def _user(self, obj: Any) -> Any:
        return getattr(obj, "user", None)

    def get_user_full_name(self, obj: Any) -> str:
        user = self._user(obj)
        return str(getattr(user, "full_name", "") or "") if user else ""

    def get_user_email(self, obj: Any) -> str:
        user = self._user(obj)
        return str(getattr(user, "email", "") or "") if user else ""

    def get_investor_reference(self, obj: Any) -> str:
        user = self._user(obj)
        return str(getattr(user, "investor_reference", "") or "") if user else ""


class KycManualReviewDecisionRequestSerializer(serializers.Serializer[Any]):
    decision = serializers.ChoiceField(choices=KycManualReviewDecisionType.choices)
    reason_code = serializers.ChoiceField(choices=KycManualReviewReason.choices)
    note = serializers.CharField(required=False, allow_blank=True)
    evidence_summary = serializers.CharField(required=False, allow_blank=True)


class KycManualReviewDecisionSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    case_id = serializers.UUIDField(source="case.id")
    actor_user_id = serializers.UUIDField()
    actor_account_type = serializers.CharField()
    decision = serializers.CharField()
    reason_code = serializers.CharField()
    previous_status = serializers.CharField()
    new_status = serializers.CharField()
    note = serializers.CharField()
    evidence_summary = serializers.CharField()
    decided_at = serializers.DateTimeField()


class KycManualReviewDecisionResponseSerializer(serializers.Serializer[Any]):
    case = KycAdminCaseSerializer()
    decision = KycManualReviewDecisionSerializer()


def serialize_kyc_admin_case(case: KycVerificationCase) -> dict[str, Any]:
    return dict(KycAdminCaseSerializer(case).data)


def serialize_manual_review_decision(decision: KycManualReviewDecision) -> dict[str, Any]:
    return dict(KycManualReviewDecisionSerializer(decision).data)


def serialize_kyc_status(
    *,
    user: Any,
    case: KycVerificationCase | None,
    latest_session: KycProviderSession | None,
) -> dict[str, Any]:
    return {
        "status": case.status if case is not None else KycStatus.NOT_STARTED,
        "financial_access_allowed": user_can_access_financial_features(user),
        "phone_verified": getattr(user, "phone_verified_at", None) is not None,
        "provider": case.provider if case is not None else "didit",
        "provider_session_id": latest_session.provider_session_id if latest_session else "",
        "verification_url": latest_session.verification_url if latest_session else None,
        "manual_review_required": case.manual_review_required if case is not None else False,
        "detected_flags": case.detected_flags if case is not None else [],
        "risk_classification": case.risk_classification if case is not None else "",
    }
