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
    LoanRecoveryPaymentRecordRequestSerializer,
    LoanRecoveryPaymentRecordResponseSerializer,
    LoanRiskNoteCreateRequestSerializer,
    LoanRiskNoteListQuerySerializer,
    LoanRiskNoteSerializer,
    LoanServicingStatusScanRequestSerializer,
    LoanServicingStatusScanResponseSerializer,
    LoanWriteOffEventSerializer,
    LoanWriteOffRecordRequestSerializer,
    PublicLoanRiskNoteListQuerySerializer,
    PublicLoanRiskNoteSerializer,
    serialize_borrower_repayment_event,
    serialize_distribution_line,
    serialize_public_risk_note,
    serialize_recovery_distribution_line,
    serialize_recovery_event,
    serialize_risk_note,
    serialize_status_change,
    serialize_write_off_event,
)
from backend.apps.servicing.services import (
    AddLoanRiskNoteCommand,
    RecordBorrowerRepaymentCommand,
    RecordLoanRecoveryPaymentCommand,
    RecordLoanWriteOffCommand,
    ScanLoanServicingStatusesCommand,
    ServicingAuthorizationError,
    ServicingValidationError,
    add_loan_risk_note,
    list_admin_loan_risk_notes,
    list_public_loan_risk_notes,
    record_borrower_repayment,
    record_loan_recovery_payment,
    record_loan_write_off,
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


class LoanRiskNoteAdminListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[LoanRiskNoteListQuerySerializer],
        responses={200: LoanRiskNoteSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = LoanRiskNoteListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            notes = list_admin_loan_risk_notes(
                actor=cast(Model, request.user),
                loan_id=str(data["loan_id"]),
                include_internal=data["include_internal"],
                limit=data["limit"],
            )
        except ServicingAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ServicingValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response([serialize_risk_note(note) for note in notes], status=status.HTTP_200_OK)

    @extend_schema(
        request=LoanRiskNoteCreateRequestSerializer,
        responses={201: LoanRiskNoteSerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = LoanRiskNoteCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            note = add_loan_risk_note(
                AddLoanRiskNoteCommand(
                    actor=cast(Model, request.user),
                    loan_id=str(data["loan_id"]),
                    visibility=data["visibility"],
                    note_type=data["note_type"],
                    title=data.get("title", ""),
                    body=data["body"],
                    evidence_reference=data.get("evidence_reference", ""),
                    metadata=data.get("metadata", {}),
                    idempotency_key=data["idempotency_key"],
                )
            )
        except ServicingAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ServicingValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_risk_note(note), status=status.HTTP_201_CREATED)


class PublicLoanRiskNoteListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PublicLoanRiskNoteListQuerySerializer],
        responses={200: PublicLoanRiskNoteSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        serializer = PublicLoanRiskNoteListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            notes = list_public_loan_risk_notes(
                actor=cast(Model, request.user),
                loan_id=str(data["loan_id"]),
                limit=data["limit"],
            )
        except ServicingAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ServicingValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            [serialize_public_risk_note(note) for note in notes],
            status=status.HTTP_200_OK,
        )


class LoanWriteOffRecordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LoanWriteOffRecordRequestSerializer,
        responses={201: LoanWriteOffEventSerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = LoanWriteOffRecordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            write_off = record_loan_write_off(
                RecordLoanWriteOffCommand(
                    actor=cast(Model, request.user),
                    loan_id=str(data["loan_id"]),
                    written_off_principal_minor=data["written_off_principal_minor"],
                    written_off_contractual_interest_minor=data[
                        "written_off_contractual_interest_minor"
                    ],
                    written_off_default_interest_minor=data[
                        "written_off_default_interest_minor"
                    ],
                    written_off_fees_minor=data["written_off_fees_minor"],
                    written_off_penalties_minor=data["written_off_penalties_minor"],
                    reason=data["reason"],
                    notes=data.get("notes", ""),
                    evidence_reference=data.get("evidence_reference", ""),
                    metadata=data.get("metadata", {}),
                    idempotency_key=data["idempotency_key"],
                )
            )
        except ServicingAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ServicingValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_write_off_event(write_off), status=status.HTTP_201_CREATED)


class LoanRecoveryPaymentRecordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LoanRecoveryPaymentRecordRequestSerializer,
        responses={201: LoanRecoveryPaymentRecordResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = LoanRecoveryPaymentRecordRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = record_loan_recovery_payment(
                RecordLoanRecoveryPaymentCommand(
                    actor=cast(Model, request.user),
                    loan_id=str(data["loan_id"]),
                    gross_recovered_minor=data["gross_recovered_minor"],
                    externally_deducted_costs_minor=data[
                        "externally_deducted_costs_minor"
                    ],
                    third_party_costs_from_received_minor=data[
                        "third_party_costs_from_received_minor"
                    ],
                    recovery_fee_applied=data["recovery_fee_applied"],
                    recovery_fee_bps=data["recovery_fee_bps"],
                    principal_recovered_minor=data["principal_recovered_minor"],
                    contractual_interest_recovered_minor=data[
                        "contractual_interest_recovered_minor"
                    ],
                    default_interest_recovered_minor=data[
                        "default_interest_recovered_minor"
                    ],
                    penalties_recovered_minor=data["penalties_recovered_minor"],
                    other_costs_recovered_minor=data["other_costs_recovered_minor"],
                    booking_date=data["booking_date"],
                    value_date=data["value_date"],
                    collection_account_identifier=data["collection_account_identifier"],
                    payer_name=data["payer_name"],
                    payer_account_identifier=data.get("payer_account_identifier", ""),
                    bank_reference=data.get("bank_reference", ""),
                    payment_reference=data.get("payment_reference", ""),
                    evidence_reference=data.get("evidence_reference", ""),
                    notes=data.get("notes", ""),
                    recovery_waterfall_config=data.get("recovery_waterfall_config", {}),
                    metadata=data.get("metadata", {}),
                    idempotency_key=data["idempotency_key"],
                )
            )
        except ServicingAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except ServicingValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "recovery_event": serialize_recovery_event(result.recovery_event),
                "distribution_lines": [
                    serialize_recovery_distribution_line(line)
                    for line in result.distribution_lines
                ],
            },
            status=status.HTTP_201_CREATED,
        )
