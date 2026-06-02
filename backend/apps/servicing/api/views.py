from __future__ import annotations

from typing import Any, cast

from django.db.models import Model
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.platform_core.domain.access import is_admin_actor
from backend.apps.servicing.api.serializers import (
    BorrowerRepaymentRecordRequestSerializer,
    BorrowerRepaymentRecordResponseSerializer,
    LoanServicingStatusScanRequestSerializer,
    LoanServicingStatusScanResponseSerializer,
    serialize_borrower_repayment_event,
    serialize_distribution_line,
    serialize_status_change,
)
from backend.apps.servicing.services import (
    RecordBorrowerRepaymentCommand,
    ScanLoanServicingStatusesCommand,
    ServicingAuthorizationError,
    ServicingValidationError,
    record_borrower_repayment,
    scan_loan_servicing_statuses,
)


def _admin_forbidden_response() -> Response:
    return Response(
        {"detail": "Only an active admin can manage servicing."},
        status=status.HTTP_403_FORBIDDEN,
    )


class BorrowerRepaymentRecordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=BorrowerRepaymentRecordRequestSerializer,
        responses={201: BorrowerRepaymentRecordResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = BorrowerRepaymentRecordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = record_borrower_repayment(
                RecordBorrowerRepaymentCommand(
                    actor=cast(Model, request.user),
                    loan_id=str(data["loan_id"]),
                    amount_minor=data["amount_minor"],
                    booking_date=data["booking_date"],
                    value_date=data["value_date"],
                    collection_account_identifier=data["collection_account_identifier"],
                    payer_name=data["payer_name"],
                    payer_account_identifier=data.get("payer_account_identifier", ""),
                    bank_reference=data.get("bank_reference", ""),
                    payment_reference=data.get("payment_reference", ""),
                    evidence_reference=data.get("evidence_reference", ""),
                    admin_notes=data.get("admin_notes", ""),
                    warning_acknowledged=data.get("warning_acknowledged", False),
                    idempotency_key=data["idempotency_key"],
                )
            )
        except ServicingAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ServicingValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "repayment_event": serialize_borrower_repayment_event(
                    result.repayment_event
                ),
                "distribution_lines": [
                    serialize_distribution_line(line) for line in result.distribution_lines
                ],
            },
            status=status.HTTP_201_CREATED,
        )


class LoanServicingStatusScanView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LoanServicingStatusScanRequestSerializer,
        responses={200: LoanServicingStatusScanResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = LoanServicingStatusScanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = scan_loan_servicing_statuses(
                ScanLoanServicingStatusesCommand(
                    actor=cast(Model, request.user),
                    as_of_date=data["as_of_date"],
                    loan_ids=tuple(str(loan_id) for loan_id in data.get("loan_ids", [])),
                )
            )
        except ServicingAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ServicingValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "as_of_date": result.as_of_date,
                "changes": [serialize_status_change(change) for change in result.changes],
            },
            status=status.HTTP_200_OK,
        )
