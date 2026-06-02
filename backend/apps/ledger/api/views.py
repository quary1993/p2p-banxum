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
    InvestorBalanceSummaryQuerySerializer,
    InvestorBalanceSummarySerializer,
    LenderDepositDeclareRequestSerializer,
    LenderDepositDeclareResponseSerializer,
    ReconciliationSnapshotCreateRequestSerializer,
    ReconciliationSnapshotSerializer,
    serialize_balance_lot,
    serialize_balance_summary,
    serialize_bank_operation,
    serialize_journal_entry,
    serialize_reconciliation_snapshot,
)
from backend.apps.ledger.services import (
    CreateReconciliationSnapshotCommand,
    DeclareLenderDepositCommand,
    LedgerAuthorizationError,
    LedgerValidationError,
    create_reconciliation_snapshot,
    declare_lender_deposit,
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
