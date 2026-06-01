from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.kyc_compliance.models import KycProviderSession, KycStatus, KycVerificationCase
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
