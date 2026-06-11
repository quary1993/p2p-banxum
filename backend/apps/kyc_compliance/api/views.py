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
    KycAdminCaseSerializer,
    KycManualReviewDecisionRequestSerializer,
    KycManualReviewDecisionResponseSerializer,
    KycSessionResponseSerializer,
    KycStatusResponseSerializer,
    serialize_kyc_admin_case,
    serialize_kyc_status,
    serialize_manual_review_decision,
)
from backend.apps.kyc_compliance.models import (
    KycManualReviewDecisionType,
    KycManualReviewReason,
    KycProviderSession,
    KycVerificationCase,
)
from backend.apps.kyc_compliance.services import (
    CreateKycSessionCommand,
    DiditApiError,
    KycManualReviewError,
    KycWebhookMatchError,
    KycWebhookSignatureError,
    ManualReviewDecisionCommand,
    ProviderKycEventCommand,
    create_kyc_session,
    process_didit_event,
    record_manual_review_decision,
    verify_didit_webhook_signature,
)
from backend.apps.platform_core.domain.access import is_admin_actor


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
        try:
            result = create_kyc_session(CreateKycSessionCommand(user=cast(Model, request.user)))
        except DiditApiError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
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


class KycAdminManualReviewListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: KycAdminCaseSerializer(many=True)})
    def get(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return Response(
                {"detail": "Only an active admin can view KYC manual reviews."},
                status=status.HTTP_403_FORBIDDEN,
            )
        cases = KycVerificationCase.objects.filter(
            manual_review_required=True,
        ).order_by("-updated_at", "-created_at")
        return Response(
            [serialize_kyc_admin_case(case) for case in cases],
            status=status.HTTP_200_OK,
        )


class KycAdminManualReviewDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=KycManualReviewDecisionRequestSerializer,
        responses={200: KycManualReviewDecisionResponseSerializer},
    )
    def post(self, request: Request, case_id: str) -> Response:
        if not is_admin_actor(request.user):
            return Response(
                {"detail": "Only an active admin can record KYC manual review decisions."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = KycManualReviewDecisionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            decision = record_manual_review_decision(
                ManualReviewDecisionCommand(
                    actor=cast(Model, request.user),
                    case_id=case_id,
                    decision=KycManualReviewDecisionType(data["decision"]),
                    reason_code=KycManualReviewReason(data["reason_code"]),
                    note=data.get("note", ""),
                    evidence_summary=data.get("evidence_summary", ""),
                )
            )
        except KycManualReviewError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        decision.case.refresh_from_db()
        return Response(
            {
                "case": serialize_kyc_admin_case(decision.case),
                "decision": serialize_manual_review_decision(decision),
            },
            status=status.HTTP_200_OK,
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


def _decision_payload(payload: dict[str, Any]) -> dict[str, Any]:
    decision = payload.get("decision")
    if isinstance(decision, dict):
        return decision
    return {}


def _nested_payload_value(payload: dict[str, Any], *keys: str) -> str:
    decision = _decision_payload(payload)
    for key in keys:
        value = payload.get(key)
        if value is None:
            value = decision.get(key)
        if value is not None:
            return str(value)
    return ""


def _first_decision_item_value(
    payload: dict[str, Any],
    collection_key: str,
    *keys: str,
) -> str:
    collection = _decision_payload(payload).get(collection_key)
    if not isinstance(collection, list):
        return ""
    for item in collection:
        if not isinstance(item, dict):
            continue
        for key in keys:
            value = item.get(key)
            if value is not None:
                return str(value)
    return ""


def _iter_text_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        values: list[str] = []
        for key, item in value.items():
            values.append(str(key))
            values.extend(_iter_text_values(item))
        return values
    if isinstance(value, list):
        values = []
        for item in value:
            values.extend(_iter_text_values(item))
        return values
    if isinstance(value, str):
        return [value]
    return []


def _payload_flags(payload: dict[str, Any]) -> list[str]:
    value = payload.get("detected_flags", payload.get("flags", []))
    flags: set[str] = set()
    if isinstance(value, list):
        flags.update(str(item) for item in value)
    if isinstance(value, str) and value:
        flags.update(item.strip() for item in value.split(",") if item.strip())

    decision = _decision_payload(payload)
    for collection_key in ("aml_screenings", "reviews", "id_verifications"):
        collection = decision.get(collection_key)
        if not isinstance(collection, list):
            continue
        for item in collection:
            text = " ".join(_iter_text_values(item)).lower() if isinstance(item, dict) else ""
            if "sanction" in text:
                flags.add("sanctions")
            if "pep" in text:
                flags.add("pep")
            if "adverse" in text and "media" in text:
                flags.add("adverse_media")
            if "fraud" in text:
                flags.add("identity_fraud")
    return sorted(flags)


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
        provider_event_type=(
            _payload_value(payload, "provider_event_type", "event_type", "webhook_type", "type")
            or "verification.updated"
        ),
        provider_status=_payload_value(payload, "provider_status", "status", "verification_status"),
        provider_session_id=provider_session_id,
        vendor_data=_payload_vendor_data(payload),
        verification_id=_payload_value(payload, "verification_id", "verificationId", "session_id"),
        report_id=_payload_value(payload, "report_id", "reportId", "pdf_report_id"),
        aml_screening_id=(
            _payload_value(payload, "aml_screening_id", "amlScreeningId")
            or _first_decision_item_value(
                payload,
                "aml_screenings",
                "id",
                "screening_id",
                "node_id",
            )
        ),
        provider_subject_id=_payload_value(
            payload,
            "provider_subject_id",
            "subject_id",
            "vendor_user_id",
            "vendor_business_id",
            "user_id",
        ),
        risk_classification=_nested_payload_value(
            payload,
            "risk_classification",
            "risk",
            "risk_level",
            "severity",
        ),
        detected_flags=_payload_flags(payload),
        raw_payload=payload,
    )


class DiditWebhookView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(request=None, responses={202: DiditWebhookResponseSerializer})
    def post(self, request: Request) -> Response:
        raw_body = request._request.body  # noqa: SLF001
        payload = request.data
        if not isinstance(payload, dict):
            return Response(
                {"detail": "Didit webhook payload must be a JSON object."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        signature = str(
            request.META.get("HTTP_X_SIGNATURE", "")
            or request.META.get("HTTP_X_DIDIT_SIGNATURE", "")
        )
        if not verify_didit_webhook_signature(
            raw_body=raw_body,
            signature=signature,
            payload=payload,
            signature_v2=str(request.META.get("HTTP_X_SIGNATURE_V2", "")),
            signature_simple=str(request.META.get("HTTP_X_SIGNATURE_SIMPLE", "")),
            timestamp=str(request.META.get("HTTP_X_TIMESTAMP", "")),
        ):
            raise KycWebhookSignatureError("Didit webhook signature is invalid.")
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
