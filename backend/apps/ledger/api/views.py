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
    AdminPayoutInstructionListQuerySerializer,
    AdminPayoutInstructionListResponseSerializer,
    AdminPayoutInstructionRowSerializer,
    BalanceAgeingScanRequestSerializer,
    BalanceAgeingScanResponseSerializer,
    BorrowerDisbursementFinalizeRequestSerializer,
    BorrowerDisbursementFinalizeResponseSerializer,
    CollectionAccountSerializer,
    InvestorBalanceSummaryQuerySerializer,
    InvestorBalanceSummarySerializer,
    InvestorPayoutInstructionRegisterRequestSerializer,
    InvestorPayoutInstructionRegisterResponseSerializer,
    InvestorPayoutInstructionRevokeRequestSerializer,
    InvestorPayoutInstructionRevokeResponseSerializer,
    InvestorPayoutInstructionVerifyRequestSerializer,
    InvestorSelfServicePayoutInstructionRegisterRequestSerializer,
    InvestorWithdrawalCancelRequestSerializer,
    InvestorWithdrawalCancelResponseSerializer,
    InvestorWithdrawalFinalizeRequestSerializer,
    InvestorWithdrawalFinalizeResponseSerializer,
    InvestorWithdrawalHistoryQuerySerializer,
    InvestorWithdrawalHistoryResponseSerializer,
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
from backend.apps.ledger.selectors import (
    admin_payout_instruction_detail,
    list_admin_payout_instructions,
    list_closed_investor_withdrawals,
    list_collection_accounts,
)
from backend.apps.ledger.services import (
    CancelInvestorWithdrawalCommand,
    CreateReconciliationSnapshotCommand,
    DeclareLenderDepositCommand,
    FinalizeBorrowerDisbursementCommand,
    FinalizeInvestorWithdrawalCommand,
    LedgerAuthorizationError,
    LedgerConflictError,
    LedgerDuplicateDepositError,
    LedgerValidationError,
    RegisterInvestorPayoutInstructionCommand,
    RegisterInvestorSelfServicePayoutInstructionCommand,
    RequestInvestorWithdrawalCommand,
    RevokeInvestorPayoutInstructionCommand,
    RunBalanceAgeingScanCommand,
    VerifyInvestorPayoutInstructionCommand,
    cancel_investor_withdrawal,
    create_reconciliation_snapshot,
    declare_lender_deposit,
    finalize_borrower_disbursement,
    finalize_investor_withdrawal,
    register_investor_payout_instruction,
    register_investor_self_service_payout_instruction,
    request_investor_withdrawal,
    revoke_investor_payout_instruction,
    run_balance_ageing_scan,
    summarize_investor_balance,
    verify_investor_payout_instruction,
)
from backend.apps.platform_core.api.request_meta import client_ip, user_agent
from backend.apps.platform_core.domain.access import is_admin_actor


def _admin_forbidden_response() -> Response:
    return Response(
        {"detail": "Only an active admin can manage ledger operations."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _conflict_response(exc: LedgerConflictError) -> Response:
    return Response(
        {"detail": str(exc), "code": exc.code, **exc.details},
        status=status.HTTP_409_CONFLICT,
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
                    collection_account_identifier=data.get("collection_account_identifier", ""),
                    payer_name=data.get("payer_name", ""),
                    payer_account_identifier=data["payer_account_identifier"],
                    bank_reference=data.get("bank_reference", ""),
                    payment_reference=data.get("payment_reference", ""),
                    evidence_reference=data.get("evidence_reference", ""),
                    notes=data.get("notes", ""),
                    idempotency_key=data["idempotency_key"],
                    confirm_repeat_deposit=data["confirm_repeat_deposit"],
                )
            )
        except LedgerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LedgerDuplicateDepositError as exc:
            # 409 tells the admin console to offer the explicit repeat confirmation.
            return Response(
                {
                    "detail": str(exc),
                    "code": "duplicate_lender_deposit",
                    "duplicate_bank_operation_id": exc.duplicate_bank_operation_id,
                },
                status=status.HTTP_409_CONFLICT,
            )
        except LedgerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "bank_operation": serialize_bank_operation(result.bank_operation),
                "journal_entry": serialize_journal_entry(result.journal_entry),
                "balance_lot": serialize_balance_lot(result.balance_lot),
                "payout_instruction": (
                    serialize_payout_instruction(result.payout_instruction)
                    if result.payout_instruction is not None
                    else None
                ),
            },
            status=status.HTTP_201_CREATED,
        )


class InvestorPayoutInstructionRegisterView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="v1_ledger_admin_payout_instructions_list",
        parameters=[AdminPayoutInstructionListQuerySerializer],
        responses={200: AdminPayoutInstructionListResponseSerializer},
    )
    def get(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = AdminPayoutInstructionListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        payload = list_admin_payout_instructions(
            state=str(data.get("state") or ""),
            investor_user_id=str(data.get("investor_user_id") or ""),
            currency=str(data.get("currency") or ""),
            query=str(data.get("q") or ""),
            limit=cast(int, data.get("limit", 50)),
            offset=cast(int, data.get("offset", 0)),
        )
        return Response(
            AdminPayoutInstructionListResponseSerializer(payload).data,
            status=status.HTTP_200_OK,
        )

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
                    evidence_reference=data.get("evidence_reference", ""),
                    other_investor_override_reason=data.get(
                        "other_investor_override_reason", ""
                    ),
                )
            )
        except LedgerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LedgerConflictError as exc:
            return _conflict_response(exc)
        except LedgerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"payout_instruction": serialize_payout_instruction(payout_instruction)},
            status=status.HTTP_201_CREATED,
        )


class AdminPayoutInstructionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: AdminPayoutInstructionRowSerializer})
    def get(self, request: Request, instruction_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        row = admin_payout_instruction_detail(str(instruction_id))
        if row is None:
            return Response(
                {"detail": "Payout IBAN does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(AdminPayoutInstructionRowSerializer(row).data, status=status.HTTP_200_OK)


class AdminPayoutInstructionVerifyView(APIView):
    """Verify an investor's pending payout-IBAN request with evidence."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=InvestorPayoutInstructionVerifyRequestSerializer,
        responses={200: InvestorPayoutInstructionRegisterResponseSerializer},
    )
    def post(self, request: Request, instruction_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = InvestorPayoutInstructionVerifyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            instruction = verify_investor_payout_instruction(
                VerifyInvestorPayoutInstructionCommand(
                    actor=cast(Model, request.user),
                    instruction_id=str(instruction_id),
                    evidence_reference=data["evidence_reference"],
                    notes=data.get("notes", ""),
                    other_investor_override_reason=data.get(
                        "other_investor_override_reason", ""
                    ),
                    destination_account_name=data.get("destination_account_name", ""),
                )
            )
        except LedgerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LedgerConflictError as exc:
            return _conflict_response(exc)
        except LedgerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {"payout_instruction": serialize_payout_instruction(instruction)},
            status=status.HTTP_200_OK,
        )


class AdminPayoutInstructionRevokeView(APIView):
    """Revoke a verified payout IBAN, or reject a pending request."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=InvestorPayoutInstructionRevokeRequestSerializer,
        responses={200: InvestorPayoutInstructionRevokeResponseSerializer},
    )
    def post(self, request: Request, instruction_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = InvestorPayoutInstructionRevokeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = revoke_investor_payout_instruction(
                RevokeInvestorPayoutInstructionCommand(
                    actor=cast(Model, request.user),
                    instruction_id=str(instruction_id),
                    reason=data["reason"],
                )
            )
        except LedgerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LedgerConflictError as exc:
            return _conflict_response(exc)
        except LedgerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "payout_instruction": serialize_payout_instruction(result.instruction),
                "action": result.action,
                "flagged_withdrawal_request_ids": result.flagged_withdrawal_request_ids,
            },
            status=status.HTTP_200_OK,
        )


class CollectionAccountListView(APIView):
    """Configured collection accounts, so admin forms do not retype them."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: CollectionAccountSerializer(many=True)})
    def get(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        return Response(
            CollectionAccountSerializer(list_collection_accounts(), many=True).data,
            status=status.HTTP_200_OK,
        )


class InvestorSelfServicePayoutInstructionRegisterView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=InvestorSelfServicePayoutInstructionRegisterRequestSerializer,
        responses={201: InvestorPayoutInstructionRegisterResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = InvestorSelfServicePayoutInstructionRegisterRequestSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            payout_instruction = register_investor_self_service_payout_instruction(
                RegisterInvestorSelfServicePayoutInstructionCommand(
                    actor=cast(Model, request.user),
                    currency=data["currency"],
                    destination_iban=data["destination_iban"],
                    destination_account_name=data["destination_account_name"],
                    notes=data.get("notes", ""),
                    sensitive_action_code_id=str(data["sensitive_action_code_id"]),
                    sensitive_action_code=data["sensitive_action_code"],
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
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


class InvestorWithdrawalHistoryView(APIView):
    """Read-only admin history of finalized and cancelled investor withdrawals."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[InvestorWithdrawalHistoryQuerySerializer],
        responses={200: InvestorWithdrawalHistoryResponseSerializer},
    )
    def get(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = InvestorWithdrawalHistoryQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        payload = list_closed_investor_withdrawals(
            status=str(data.get("status") or ""),
            currency=str(data.get("currency") or ""),
            is_forced=data.get("is_forced"),
            query=str(data.get("q") or ""),
            limit=cast(int, data.get("limit", 50)),
            offset=cast(int, data.get("offset", 0)),
        )
        return Response(
            InvestorWithdrawalHistoryResponseSerializer(payload).data,
            status=status.HTTP_200_OK,
        )


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
                    sensitive_action_code_id=str(data["sensitive_action_code_id"]),
                    sensitive_action_code=data["sensitive_action_code"],
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
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
                    collection_account_identifier=data.get("collection_account_identifier", ""),
                    bank_reference=data.get("bank_reference", ""),
                    payment_reference=data.get("payment_reference", ""),
                    evidence_reference=data.get("evidence_reference", ""),
                    admin_notes=data.get("admin_notes", ""),
                    idempotency_key=data["idempotency_key"],
                )
            )
        except LedgerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LedgerConflictError as exc:
            return _conflict_response(exc)
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
                    fee_minor=data["fee_minor"],
                    currency=data["currency"],
                    booking_date=data["booking_date"],
                    value_date=data["value_date"],
                    collection_account_identifier=data.get("collection_account_identifier", ""),
                    payee_name=data["payee_name"],
                    payee_account_identifier=data["payee_account_identifier"],
                    override_note=data.get("override_note", ""),
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
