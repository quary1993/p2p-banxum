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
    create_kyc_session,
    process_didit_event,
    provider_event_command_from_payload,
    record_manual_review_decision,
    refresh_user_kyc_status_from_provider,
    verify_didit_webhook_signature,
)
from backend.apps.platform_core.domain.access import is_admin_actor
from backend.apps.platform_core.services.impersonation import (
    READONLY_IMPERSONATION_HEADER,
    ReadOnlyImpersonationError,
    resolve_readonly_impersonation,
)


class KycStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: KycStatusResponseSerializer})
    def get(self, request: Request) -> Response:
        readonly_token = request.headers.get(READONLY_IMPERSONATION_HEADER, "")
        if readonly_token:
            try:
                readonly_user, _context = resolve_readonly_impersonation(
                    actor=cast(Model, request.user),
                    token=readonly_token,
                )
            except ReadOnlyImpersonationError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
            case = KycVerificationCase.objects.filter(user_id=readonly_user.pk).first()
            latest_session = (
                KycProviderSession.objects.filter(case=case).first() if case is not None else None
            )
            return Response(
                serialize_kyc_status(user=readonly_user, case=case, latest_session=latest_session),
                status=status.HTTP_200_OK,
            )

        user = cast(Model, request.user)
        try:
            case, latest_session = refresh_user_kyc_status_from_provider(user)
            user.refresh_from_db()
        except (DiditApiError, KycWebhookMatchError):
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
        cases = (
            KycVerificationCase.objects.select_related("user")
            .filter(manual_review_required=True)
            .order_by("-updated_at", "-created_at")
        )
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
            result = process_didit_event(provider_event_command_from_payload(payload))
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
