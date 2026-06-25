from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.platform_core.api.serializers import (
    HealthResponseSerializer,
    QaDevModeAdvanceRequestSerializer,
    QaDevModeEnableRequestSerializer,
    QaDevModeRevertRequestSerializer,
    QaDevModeStateSerializer,
)
from backend.apps.platform_core.domain.access import is_superadmin_actor
from backend.apps.platform_core.services.qa_dev_mode import (
    AdvanceQaDevModeTimeCommand,
    EnableQaDevModeCommand,
    QaDevModeAuthorizationError,
    QaDevModeValidationError,
    RevertQaDevModeCommand,
    advance_qa_dev_mode_time,
    enable_qa_dev_mode,
    get_qa_dev_mode_state,
    revert_qa_dev_mode,
    serialize_qa_dev_mode_state,
)


class HealthView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(responses=HealthResponseSerializer)
    def get(self, request):  # type: ignore[no-untyped-def]
        return Response(
            {
                "status": "ok",
                "platform": settings.PLATFORM_BRAND_NAME,
                "operator": settings.LEGAL_OPERATOR_NAME,
                "timezone": settings.TIME_ZONE,
                "environment": settings.ENVIRONMENT,
            }
        )


def _qa_error_response(exc: Exception) -> Response:
    if isinstance(exc, QaDevModeAuthorizationError):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class QaDevModeStateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: QaDevModeStateSerializer})
    def get(self, request):  # type: ignore[no-untyped-def]
        if not is_superadmin_actor(request.user):
            return Response(
                {"detail": "Only an active superadmin can manage QA mode."},
                status=status.HTTP_403_FORBIDDEN,
            )
        state = get_qa_dev_mode_state()
        return Response(QaDevModeStateSerializer(serialize_qa_dev_mode_state(state)).data)


class QaDevModeEnableView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=QaDevModeEnableRequestSerializer,
        responses={200: QaDevModeStateSerializer},
    )
    def post(self, request):  # type: ignore[no-untyped-def]
        serializer = QaDevModeEnableRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            state = enable_qa_dev_mode(
                EnableQaDevModeCommand(
                    actor=request.user,
                    note=serializer.validated_data.get("note", ""),
                )
            )
        except (QaDevModeAuthorizationError, QaDevModeValidationError) as exc:
            return _qa_error_response(exc)
        return Response(QaDevModeStateSerializer(serialize_qa_dev_mode_state(state)).data)


class QaDevModeAdvanceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=QaDevModeAdvanceRequestSerializer,
        responses={200: QaDevModeStateSerializer},
    )
    def post(self, request):  # type: ignore[no-untyped-def]
        serializer = QaDevModeAdvanceRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            state = advance_qa_dev_mode_time(
                AdvanceQaDevModeTimeCommand(
                    actor=request.user,
                    days=serializer.validated_data["days"],
                )
            )
        except (QaDevModeAuthorizationError, QaDevModeValidationError) as exc:
            return _qa_error_response(exc)
        return Response(QaDevModeStateSerializer(serialize_qa_dev_mode_state(state)).data)


class QaDevModeRevertView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=QaDevModeRevertRequestSerializer,
        responses={200: QaDevModeStateSerializer},
    )
    def post(self, request):  # type: ignore[no-untyped-def]
        serializer = QaDevModeRevertRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            revert_qa_dev_mode(
                RevertQaDevModeCommand(
                    actor=request.user,
                    confirmation=serializer.validated_data["confirmation"],
                )
            )
        except (QaDevModeAuthorizationError, QaDevModeValidationError) as exc:
            return _qa_error_response(exc)
        state = get_qa_dev_mode_state()
        return Response(QaDevModeStateSerializer(serialize_qa_dev_mode_state(state)).data)
