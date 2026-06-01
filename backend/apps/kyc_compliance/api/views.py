from __future__ import annotations

from typing import Any, cast

from django.db.models import Model
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.kyc_compliance.api.serializers import (
    DiditWebhookResponseSerializer,
    KycSessionResponseSerializer,
    KycStatusResponseSerializer,
    serialize_kyc_status,
)
from backend.apps.kyc_compliance.models import KycProviderSession, KycVerificationCase
from backend.apps.kyc_compliance.services import (
    CreateKycSessionCommand,
    KycWebhookMatchError,
    KycWebhookSignatureError,
    ProviderKycEventCommand,
    create_kyc_session,
    process_didit_event,
    verify_didit_webhook_signature,
)


class KycStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: KycStatusResponseSerializer})
    def get(self, request: Request) -> Response:
        user = cast(Model, request.user)
        case = KycVerificationCase.objects.filter(user_id=user.pk).first()
        latest_session = (
            KycProviderSession.objects.filter(case=case).first() if case is not None else None
        )
        return Response(
            serialize_kyc_status(user=user, case=case, latest_session=latest_session),
            status=status.HTTP_200_OK,
        )


class KycSessionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={202: KycSessionResponseSerializer})
    def post(self, request: Request) -> Response:
        result = create_kyc_session(CreateKycSessionCommand(user=cast(Model, request.user)))
        return Response(
            {
                "status": result.case.status,
                "provider_session_id": (
                    result.session.provider_session_id if result.session is not None else None
                ),
                "verification_url": (
                    result.session.verification_url if result.session is not None else None
                ),
                "already_approved": result.already_approved,
            },
            status=status.HTTP_200_OK if result.already_approved else status.HTTP_202_ACCEPTED,
        )


def _payload_value(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return str(value)
    return ""


def _payload_vendor_data(payload: dict[str, Any]) -> str:
    metadata = payload.get("metadata")
    if isinstance(metadata, dict) and metadata.get("vendor_data") is not None:
        return str(metadata["vendor_data"])
    return _payload_value(payload, "vendor_data", "vendorData")


def _payload_flags(payload: dict[str, Any]) -> list[str]:
    value = payload.get("detected_flags", payload.get("flags", []))
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _provider_event_command(payload: dict[str, Any]) -> ProviderKycEventCommand:
    provider_event_id = _payload_value(payload, "provider_event_id", "event_id", "id")
    provider_session_id = _payload_value(
        payload,
        "provider_session_id",
        "session_id",
        "sessionId",
    )
    if not provider_event_id:
        raise KycWebhookMatchError("Didit webhook is missing a provider event ID.")
    return ProviderKycEventCommand(
        provider_event_id=provider_event_id,
        provider_event_type=_payload_value(payload, "event_type", "type") or "verification.updated",
        provider_status=_payload_value(payload, "provider_status", "status", "verification_status"),
        provider_session_id=provider_session_id,
        vendor_data=_payload_vendor_data(payload),
        verification_id=_payload_value(payload, "verification_id", "verificationId"),
        report_id=_payload_value(payload, "report_id", "reportId"),
        aml_screening_id=_payload_value(payload, "aml_screening_id", "amlScreeningId"),
        provider_subject_id=_payload_value(payload, "provider_subject_id", "subject_id"),
        risk_classification=_payload_value(payload, "risk_classification", "risk"),
        detected_flags=_payload_flags(payload),
        raw_payload=payload,
    )


class DiditWebhookView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(request=None, responses={202: DiditWebhookResponseSerializer})
    def post(self, request: Request) -> Response:
        raw_body = request._request.body  # noqa: SLF001
        signature = str(request.META.get("HTTP_X_DIDIT_SIGNATURE", ""))
        if not verify_didit_webhook_signature(raw_body=raw_body, signature=signature):
            raise KycWebhookSignatureError("Didit webhook signature is invalid.")

        payload = request.data
        try:
            result = process_didit_event(_provider_event_command(payload))
        except KycWebhookMatchError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"status": result.case.status, "idempotent": result.idempotent},
            status=status.HTTP_202_ACCEPTED,
        )

    def handle_exception(self, exc: Exception) -> Response:
        if isinstance(exc, KycWebhookSignatureError):
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return super().handle_exception(exc)
