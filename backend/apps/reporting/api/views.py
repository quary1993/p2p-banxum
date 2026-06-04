from __future__ import annotations

from typing import Any, cast

from django.db.models import Model
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.reporting.api.serializers import (
    ReportGenerateRequestSerializer,
    ReportGenerateResponseSerializer,
    serialize_report_run,
)
from backend.apps.reporting.services import (
    GenerateReportCommand,
    ReportingAuthorizationError,
    ReportingValidationError,
    generate_report,
)


def _error_response(exc: Exception) -> Response:
    status_code = (
        status.HTTP_403_FORBIDDEN
        if isinstance(exc, ReportingAuthorizationError)
        else status.HTTP_400_BAD_REQUEST
    )
    return Response({"detail": str(exc)}, status=status_code)


class ReportGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ReportGenerateRequestSerializer,
        responses={201: ReportGenerateResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = ReportGenerateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            artifact = generate_report(
                GenerateReportCommand(
                    actor=cast(Model, request.user),
                    report_type=data["report_type"],
                    start_date=data["start_date"],
                    end_date=data["end_date"],
                    output_format=data.get("output_format", "csv"),
                    redaction_mode=data.get("redaction_mode", "redacted"),
                    filters=data.get("filters"),
                    destination_note=data.get("destination_note", ""),
                )
            )
        except (ReportingAuthorizationError, ReportingValidationError) as exc:
            return _error_response(exc)
        return Response(
            {
                "report_run": serialize_report_run(artifact.report_run),
                "content_type": artifact.content_type,
                "filename": artifact.filename,
                "content": artifact.content,
                "manifest": artifact.manifest,
            },
            status=status.HTTP_201_CREATED,
        )
