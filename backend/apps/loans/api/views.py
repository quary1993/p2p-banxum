from __future__ import annotations

from typing import Any, cast

from django.db.models import Model, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.loans.api.serializers import (
    LoanCreateRequestSerializer,
    LoanEventSerializer,
    LoanInstallmentSerializer,
    LoanListQuerySerializer,
    LoanSerializer,
    LoanUpdateRequestSerializer,
    PublishLoanRequestSerializer,
    serialize_installment,
    serialize_loan,
    serialize_loan_event,
)
from backend.apps.loans.models import Loan
from backend.apps.loans.services import (
    CreateLoanCommand,
    LoanAuthorizationError,
    LoanValidationError,
    ManualScheduleRowCommand,
    PublishLoanCommand,
    UpdateLoanCommand,
    create_loan,
    publish_loan,
    update_loan,
)
from backend.apps.platform_core.domain.access import is_admin_actor


def _admin_forbidden_response() -> Response:
    return Response(
        {"detail": "Only an active admin can manage loans."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _manual_rows_from_data(
    rows: list[dict[str, Any]] | None,
) -> list[ManualScheduleRowCommand] | None:
    if rows is None:
        return None
    return [
        ManualScheduleRowCommand(
            due_date=row["due_date"],
            principal_minor=row["principal_minor"],
            interest_minor=row["interest_minor"],
        )
        for row in rows
    ]


def _loan_queryset_from_query(data: dict[str, Any]) -> QuerySet[Loan]:
    queryset = Loan.objects.select_related("currency", "borrower").all()
    for field in ("status", "purpose", "repayment_type", "risk_rating"):
        if data.get(field):
            queryset = queryset.filter(**{field: data[field]})
    if data.get("borrower_id"):
        queryset = queryset.filter(borrower_id=data["borrower_id"])
    if data.get("currency"):
        queryset = queryset.filter(currency_id=str(data["currency"]).upper())
    if data.get("q"):
        query = data["q"]
        queryset = queryset.filter(title__icontains=query)
    return queryset


class LoanListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[LoanListQuerySerializer],
        responses={200: LoanSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = LoanListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        loans = _loan_queryset_from_query(data)
        return Response(
            [serialize_loan(loan) for loan in loans[: data["limit"]]],
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=LoanCreateRequestSerializer,
        responses={201: LoanSerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = LoanCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            loan = create_loan(
                CreateLoanCommand(
                    actor=cast(Model, request.user),
                    borrower_id=str(data["borrower_id"]),
                    title=data["title"],
                    investor_summary=data["investor_summary"],
                    purpose=data["purpose"],
                    purpose_description=data.get("purpose_description", ""),
                    principal_minor=data["principal_minor"],
                    currency=data["currency"],
                    interest_rate_bps=data["interest_rate_bps"],
                    term_months=data["term_months"],
                    repayment_type=data["repayment_type"],
                    interest_only_months=data.get("interest_only_months", 0),
                    funding_deadline=data.get("funding_deadline"),
                    first_payment_date=data.get("first_payment_date"),
                    collateral_type=data["collateral_type"],
                    collateral_value_minor=data["collateral_value_minor"],
                    collateral_description=data.get("collateral_description", ""),
                    risk_rating=data["risk_rating"],
                    borrower_success_fee_bps=data.get("borrower_success_fee_bps", 200),
                    lender_payment_fee_minor=data.get("lender_payment_fee_minor", 0),
                    default_penalty_interest_bps=data.get("default_penalty_interest_bps", 0),
                    recovery_fee_bps=data.get("recovery_fee_bps", 0),
                    recovery_waterfall_version=data.get("recovery_waterfall_version", "v1"),
                    manual_schedule_rows=_manual_rows_from_data(
                        data.get("manual_schedule_rows")
                    ),
                    note=data.get("note", ""),
                )
            )
        except LoanAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LoanValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_loan(loan), status=status.HTTP_201_CREATED)


class LoanDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: LoanSerializer})
    def get(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        loan = Loan.objects.select_related("currency", "borrower").filter(id=loan_id).first()
        if loan is None:
            return Response({"detail": "Loan does not exist."}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_loan(loan), status=status.HTTP_200_OK)

    @extend_schema(
        request=LoanUpdateRequestSerializer,
        responses={200: LoanSerializer},
    )
    def patch(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = LoanUpdateRequestSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            loan = update_loan(
                UpdateLoanCommand(
                    actor=cast(Model, request.user),
                    loan_id=loan_id,
                    title=data.get("title"),
                    investor_summary=data.get("investor_summary"),
                    purpose=data.get("purpose"),
                    purpose_description=data.get("purpose_description"),
                    principal_minor=data.get("principal_minor"),
                    interest_rate_bps=data.get("interest_rate_bps"),
                    term_months=data.get("term_months"),
                    repayment_type=data.get("repayment_type"),
                    interest_only_months=data.get("interest_only_months"),
                    funding_deadline=data.get("funding_deadline"),
                    first_payment_date=data.get("first_payment_date"),
                    collateral_type=data.get("collateral_type"),
                    collateral_value_minor=data.get("collateral_value_minor"),
                    collateral_description=data.get("collateral_description"),
                    risk_rating=data.get("risk_rating"),
                    borrower_success_fee_bps=data.get("borrower_success_fee_bps"),
                    lender_payment_fee_minor=data.get("lender_payment_fee_minor"),
                    default_penalty_interest_bps=data.get("default_penalty_interest_bps"),
                    recovery_fee_bps=data.get("recovery_fee_bps"),
                    recovery_waterfall_version=data.get("recovery_waterfall_version"),
                    manual_schedule_rows=_manual_rows_from_data(
                        data.get("manual_schedule_rows")
                    ),
                    investor_message=data.get("investor_message", ""),
                    note=data.get("note", ""),
                )
            )
        except LoanAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LoanValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_loan(loan), status=status.HTTP_200_OK)


class PublishLoanView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PublishLoanRequestSerializer,
        responses={200: LoanSerializer},
    )
    def post(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = PublishLoanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            loan = publish_loan(
                PublishLoanCommand(
                    actor=cast(Model, request.user),
                    loan_id=loan_id,
                    note=data.get("note", ""),
                )
            )
        except LoanAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LoanValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_loan(loan), status=status.HTTP_200_OK)


class LoanScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: LoanInstallmentSerializer(many=True)})
    def get(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        loan = Loan.objects.filter(id=loan_id).first()
        if loan is None:
            return Response({"detail": "Loan does not exist."}, status=status.HTTP_404_NOT_FOUND)
        installments = loan.installments.filter(schedule_version=loan.schedule_version)
        return Response(
            [serialize_installment(installment) for installment in installments],
            status=status.HTTP_200_OK,
        )


class LoanEventListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: LoanEventSerializer(many=True)})
    def get(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        loan = Loan.objects.filter(id=loan_id).first()
        if loan is None:
            return Response({"detail": "Loan does not exist."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            [serialize_loan_event(event) for event in loan.events.all()],
            status=status.HTTP_200_OK,
        )
