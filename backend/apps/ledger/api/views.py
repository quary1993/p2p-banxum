from __future__ import annotations

from typing import Any, cast

from django.db.models import Model
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.ledger.api.serializers import (
    BalanceAgeingScanRequestSerializer,
    BalanceAgeingScanResponseSerializer,
    BorrowerDisbursementFinalizeRequestSerializer,
    BorrowerDisbursementFinalizeResponseSerializer,
    InvestorBalanceSummaryQuerySerializer,
    InvestorBalanceSummarySerializer,
    InvestorPayoutInstructionRegisterRequestSerializer,
    InvestorPayoutInstructionRegisterResponseSerializer,
    InvestorWithdrawalCancelRequestSerializer,
    InvestorWithdrawalCancelResponseSerializer,
    InvestorWithdrawalFinalizeRequestSerializer,
    InvestorWithdrawalFinalizeResponseSerializer,
    InvestorWithdrawalRequestCreateRequestSerializer,
    InvestorWithdrawalRequestCreateResponseSerializer,
    LenderDepositDeclareRequestSerializer,
    LenderDepositDeclareResponseSerializer,
    ReconciliationSnapshotCreateRequestSerializer,
    ReconciliationSnapshotSerializer,
    serialize_balance_ageing_scan_result,
    serialize_balance_lot,
    serialize_balance_summary,
    serialize_bank_operation,
    serialize_journal_entry,
    serialize_payout_instruction,
    serialize_reconciliation_snapshot,
    serialize_withdrawal_request,
)
from backend.apps.ledger.services import (
    CancelInvestorWithdrawalCommand,
    CreateReconciliationSnapshotCommand,
    DeclareLenderDepositCommand,
    FinalizeBorrowerDisbursementCommand,
    FinalizeInvestorWithdrawalCommand,
    LedgerAuthorizationError,
    LedgerValidationError,
    RegisterInvestorPayoutInstructionCommand,
    RequestInvestorWithdrawalCommand,
    RunBalanceAgeingScanCommand,
    cancel_investor_withdrawal,
    create_reconciliation_snapshot,
    declare_lender_deposit,
    finalize_borrower_disbursement,
    finalize_investor_withdrawal,
    register_investor_payout_instruction,
    request_investor_withdrawal,
    run_balance_ageing_scan,
    summarize_investor_balance,
)
from backend.apps.platform_core.domain.access import is_admin_actor


def _admin_forbidden_response() -> Response:
    return Response(
        {"detail": "Only an active admin can manage ledger operations."},
        status=status.HTTP_403_FORBIDDEN,
    )


class LenderDepositDeclareView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LenderDepositDeclareRequestSerializer,
        responses={201: LenderDepositDeclareResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = LenderDepositDeclareRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = declare_lender_deposit(
                DeclareLenderDepositCommand(
                    actor=cast(Model, request.user),
                    investor_user_id=str(data["investor_user_id"]),
                    amount_minor=data["amount_minor"],
                    currency=data["currency"],
                    booking_date=data["booking_date"],
                    value_date=data["value_date"],
                    collection_account_identifier=data["collection_account_identifier"],
                    payer_name=data.get("payer_name", ""),
                    payer_account_identifier=data.get("payer_account_identifier", ""),
                    bank_reference=data.get("bank_reference", ""),
                    payment_reference=data.get("payment_reference", ""),
                    evidence_reference=data.get("evidence_reference", ""),
                    notes=data.get("notes", ""),
                    idempotency_key=data["idempotency_key"],
                )
            )
        except LedgerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LedgerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "bank_operation": serialize_bank_operation(result.bank_operation),
                "journal_entry": serialize_journal_entry(result.journal_entry),
                "balance_lot": serialize_balance_lot(result.balance_lot),
            },
            status=status.HTTP_201_CREATED,
        )


class InvestorPayoutInstructionRegisterView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=InvestorPayoutInstructionRegisterRequestSerializer,
        responses={201: InvestorPayoutInstructionRegisterResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = InvestorPayoutInstructionRegisterRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            payout_instruction = register_investor_payout_instruction(
                RegisterInvestorPayoutInstructionCommand(
                    actor=cast(Model, request.user),
                    investor_user_id=str(data["investor_user_id"]),
                    currency=data["currency"],
                    destination_iban=data["destination_iban"],
                    destination_account_name=data["destination_account_name"],
                    is_verified_usable=data.get("is_verified_usable", True),
                    notes=data.get("notes", ""),
                    metadata=data.get("metadata"),
                )
            )
        except LedgerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LedgerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"payout_instruction": serialize_payout_instruction(payout_instruction)},
            status=status.HTTP_201_CREATED,
        )


class InvestorBalanceSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[InvestorBalanceSummaryQuerySerializer],
        responses={200: InvestorBalanceSummarySerializer},
    )
    def get(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = InvestorBalanceSummaryQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            summary = summarize_investor_balance(
                investor_user_id=str(data["investor_user_id"]),
                currency=data["currency"],
            )
        except LedgerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_balance_summary(summary), status=status.HTTP_200_OK)


class InvestorWithdrawalRequestCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=InvestorWithdrawalRequestCreateRequestSerializer,
        responses={201: InvestorWithdrawalRequestCreateResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = InvestorWithdrawalRequestCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            withdrawal_request = request_investor_withdrawal(
                RequestInvestorWithdrawalCommand(
                    actor=cast(Model, request.user),
                    amount_minor=data["amount_minor"],
                    currency=data["currency"],
                    destination_iban=data["destination_iban"],
                    destination_account_name=data.get("destination_account_name", ""),
                    notes=data.get("notes", ""),
                    idempotency_key=data["idempotency_key"],
                )
            )
            summary = summarize_investor_balance(
                investor_user_id=str(request.user.pk),
                currency=data["currency"],
            )
        except LedgerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LedgerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "withdrawal_request": serialize_withdrawal_request(withdrawal_request),
                "balance_summary": serialize_balance_summary(summary),
            },
            status=status.HTTP_201_CREATED,
        )


class InvestorWithdrawalFinalizeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=InvestorWithdrawalFinalizeRequestSerializer,
        responses={200: InvestorWithdrawalFinalizeResponseSerializer},
    )
    def post(self, request: Request, withdrawal_request_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = InvestorWithdrawalFinalizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = finalize_investor_withdrawal(
                FinalizeInvestorWithdrawalCommand(
                    actor=cast(Model, request.user),
                    withdrawal_request_id=withdrawal_request_id,
                    booking_date=data["booking_date"],
                    value_date=data["value_date"],
                    collection_account_identifier=data["collection_account_identifier"],
                    bank_reference=data.get("bank_reference", ""),
                    payment_reference=data.get("payment_reference", ""),
                    evidence_reference=data.get("evidence_reference", ""),
                    admin_notes=data.get("admin_notes", ""),
                    idempotency_key=data["idempotency_key"],
                )
            )
        except LedgerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LedgerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "withdrawal_request": serialize_withdrawal_request(result.withdrawal_request),
                "bank_operation": serialize_bank_operation(result.bank_operation),
                "journal_entry": serialize_journal_entry(result.journal_entry),
            },
            status=status.HTTP_200_OK,
        )


class BorrowerDisbursementFinalizeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=BorrowerDisbursementFinalizeRequestSerializer,
        responses={201: BorrowerDisbursementFinalizeResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = BorrowerDisbursementFinalizeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = finalize_borrower_disbursement(
                FinalizeBorrowerDisbursementCommand(
                    actor=cast(Model, request.user),
                    loan_id=str(data["loan_id"]),
                    borrower_id=str(data["borrower_id"]),
                    amount_minor=data["amount_minor"],
                    currency=data["currency"],
                    booking_date=data["booking_date"],
                    value_date=data["value_date"],
                    collection_account_identifier=data["collection_account_identifier"],
                    payee_name=data["payee_name"],
                    payee_account_identifier=data["payee_account_identifier"],
                    bank_reference=data.get("bank_reference", ""),
                    payment_reference=data.get("payment_reference", ""),
                    evidence_reference=data.get("evidence_reference", ""),
                    admin_notes=data.get("admin_notes", ""),
                    idempotency_key=data["idempotency_key"],
                )
            )
        except LedgerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LedgerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "bank_operation": serialize_bank_operation(result.bank_operation),
                "journal_entry": serialize_journal_entry(result.journal_entry),
            },
            status=status.HTTP_201_CREATED,
        )


class InvestorWithdrawalCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=InvestorWithdrawalCancelRequestSerializer,
        responses={200: InvestorWithdrawalCancelResponseSerializer},
    )
    def post(self, request: Request, withdrawal_request_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = InvestorWithdrawalCancelRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = cancel_investor_withdrawal(
                CancelInvestorWithdrawalCommand(
                    actor=cast(Model, request.user),
                    withdrawal_request_id=withdrawal_request_id,
                    reason=data.get("reason", ""),
                    idempotency_key=data["idempotency_key"],
                )
            )
        except LedgerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LedgerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "withdrawal_request": serialize_withdrawal_request(result.withdrawal_request),
                "journal_entry": serialize_journal_entry(result.journal_entry),
            },
            status=status.HTTP_200_OK,
        )


class ReconciliationSnapshotCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ReconciliationSnapshotCreateRequestSerializer,
        responses={201: ReconciliationSnapshotSerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = ReconciliationSnapshotCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            snapshot = create_reconciliation_snapshot(
                CreateReconciliationSnapshotCommand(
                    actor=cast(Model, request.user),
                    currency=data["currency"],
                    as_of_date=data["as_of_date"],
                    bank_stated_balance_minor=data["bank_stated_balance_minor"],
                    pending_exception_balance_minor=data.get(
                        "pending_exception_balance_minor",
                        0,
                    ),
                    notes=data.get("notes", ""),
                    metadata=data.get("metadata"),
                )
            )
        except LedgerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LedgerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            serialize_reconciliation_snapshot(snapshot),
            status=status.HTTP_201_CREATED,
        )


class BalanceAgeingScanView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=BalanceAgeingScanRequestSerializer,
        responses={200: BalanceAgeingScanResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = BalanceAgeingScanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = run_balance_ageing_scan(
                RunBalanceAgeingScanCommand(
                    actor=cast(Model, request.user),
                    as_of=data.get("as_of"),
                    currency=data.get("currency"),
                    dry_run=data.get("dry_run", False),
                )
            )
        except LedgerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LedgerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            serialize_balance_ageing_scan_result(result),
            status=status.HTTP_200_OK,
        )
