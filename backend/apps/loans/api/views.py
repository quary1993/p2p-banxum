from __future__ import annotations

from dataclasses import asdict
from importlib import import_module
from typing import Any, cast

from django.db.models import Model, Q, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.loans import credit_checks as loan_credit_checks
from backend.apps.loans import history as loan_history
from backend.apps.loans import securities as loan_securities
from backend.apps.loans.api.serializers import (
    LoanComingSoonRequestSerializer,
    LoanCreateRequestSerializer,
    LoanCreditCheckRequestSerializer,
    LoanCreditCheckSerializer,
    LoanCreditChecksSerializer,
    LoanEventSerializer,
    LoanHistoryEntrySerializer,
    LoanHistoryResponseSerializer,
    LoanInstallmentSerializer,
    LoanListQuerySerializer,
    LoanMonitoringRequestSerializer,
    LoanReportingPlanRequestSerializer,
    LoanSecurityListSerializer,
    LoanSecurityMoveRequestSerializer,
    LoanSecurityRequestSerializer,
    LoanSecuritySerializer,
    LoanSerializer,
    LoanUpdateRequestSerializer,
    OriginalLoanScheduleRowSerializer,
    PublishLoanRequestSerializer,
    admin_loan_list_context,
    serialize_loan,
    serialize_loan_event,
)
from backend.apps.loans.models import Loan
from backend.apps.loans.services import (
    AnnounceComingSoonCommand,
    CreateLoanCommand,
    LoanAuthorizationError,
    LoanValidationError,
    ManualScheduleRowCommand,
    PublishLoanCommand,
    UpdateLoanCommand,
    announce_loan_coming_soon,
    create_loan,
    original_schedule_payload,
    publish_loan,
    update_loan,
    withdraw_loan_coming_soon,
)
from backend.apps.platform_core.domain.access import is_admin_actor
from backend.apps.platform_core.domain.time import business_date, now_utc


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
    queryset = Loan.objects.select_related(
        "currency",
        "borrower",
        "originator_profile__originator",
    ).all()
    for field in ("status", "purpose", "repayment_type", "risk_rating", "product_type"):
        if data.get(field):
            queryset = queryset.filter(**{field: data[field]})
    if data.get("borrower_id"):
        queryset = queryset.filter(borrower_id=data["borrower_id"])
    if data.get("currency"):
        queryset = queryset.filter(currency_id=str(data["currency"]).upper())
    if data.get("q"):
        query = data["q"]
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(borrower__legal_name__icontains=query)
            | Q(originator_profile__originator__legal_name__icontains=query)
            | Q(originator_profile__originator__public_name__icontains=query)
            | Q(originator_profile__borrower_legal_name__icontains=query)
            | Q(originator_profile__borrower_display_name__icontains=query)
        )
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
        loans = list(_loan_queryset_from_query(data)[: data["limit"]])
        rows = LoanSerializer(loans, many=True, context=admin_loan_list_context(loans)).data
        return Response(rows, status=status.HTTP_200_OK)

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
                    is_refinancing=data.get("is_refinancing", False),
                    original_principal_minor=data.get("original_principal_minor"),
                    original_interest_rate_bps=data.get("original_interest_rate_bps"),
                    original_term_months=data.get("original_term_months"),
                    original_repayment_type=data.get("original_repayment_type"),
                    original_interest_only_months=data.get("original_interest_only_months"),
                    original_loan_start_date=data.get("original_loan_start_date"),
                    principal_minor=data["principal_minor"],
                    currency=data["currency"],
                    interest_rate_bps=data["interest_rate_bps"],
                    term_months=data["term_months"],
                    repayment_type=data["repayment_type"],
                    interest_only_months=data.get("interest_only_months", 0),
                    loan_start_date=data.get("loan_start_date"),
                    funding_deadline=data.get("funding_deadline"),
                    collateral_type=data["collateral_type"],
                    collateral_value_minor=data["collateral_value_minor"],
                    collateral_description=data.get("collateral_description", ""),
                    risk_rating=data["risk_rating"],
                    borrower_success_fee_bps=data.get("borrower_success_fee_bps", 200),
                    lender_payment_fee_minor=data.get("lender_payment_fee_minor", 0),
                    default_penalty_interest_bps=data.get("default_penalty_interest_bps", 0),
                    recovery_fee_bps=data.get("recovery_fee_bps", 0),
                    minimum_subscription_bps=data.get("minimum_subscription_bps", 5_000),
                    manual_schedule_rows=_manual_rows_from_data(data.get("manual_schedule_rows")),
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
        loan = (
            Loan.objects.select_related(
                "currency",
                "borrower",
                "originator_profile__originator",
            )
            .filter(id=loan_id)
            .first()
        )
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
                    is_refinancing=data.get("is_refinancing"),
                    original_principal_minor=data.get("original_principal_minor"),
                    original_interest_rate_bps=data.get("original_interest_rate_bps"),
                    original_term_months=data.get("original_term_months"),
                    original_repayment_type=data.get("original_repayment_type"),
                    original_interest_only_months=data.get("original_interest_only_months"),
                    original_loan_start_date=data.get("original_loan_start_date"),
                    principal_minor=data.get("principal_minor"),
                    interest_rate_bps=data.get("interest_rate_bps"),
                    term_months=data.get("term_months"),
                    repayment_type=data.get("repayment_type"),
                    interest_only_months=data.get("interest_only_months"),
                    loan_start_date=data.get("loan_start_date"),
                    funding_deadline=data.get("funding_deadline"),
                    collateral_type=data.get("collateral_type"),
                    collateral_value_minor=data.get("collateral_value_minor"),
                    collateral_description=data.get("collateral_description"),
                    risk_rating=data.get("risk_rating"),
                    borrower_success_fee_bps=data.get("borrower_success_fee_bps"),
                    lender_payment_fee_minor=data.get("lender_payment_fee_minor"),
                    default_penalty_interest_bps=data.get("default_penalty_interest_bps"),
                    recovery_fee_bps=data.get("recovery_fee_bps"),
                    minimum_subscription_bps=data.get("minimum_subscription_bps"),
                    manual_schedule_rows=_manual_rows_from_data(data.get("manual_schedule_rows")),
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
                    pre_publication_paid_installment_numbers=data.get(
                        "pre_publication_paid_installment_numbers"
                    ),
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
        servicing = import_module("backend.apps.servicing.services")
        rows = servicing.get_loan_repayment_schedule_snapshots(
            loans=[loan],
            as_of_date=business_date(now_utc()),
        ).get(str(loan.id), [])
        return Response(
            [dict(LoanInstallmentSerializer(asdict(row)).data) for row in rows],
            status=status.HTTP_200_OK,
        )


class LoanOriginalScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OriginalLoanScheduleRowSerializer(many=True)})
    def get(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        loan = Loan.objects.select_related("currency").filter(id=loan_id).first()
        if loan is None:
            return Response({"detail": "Loan does not exist."}, status=status.HTTP_404_NOT_FOUND)
        if not loan.is_refinancing:
            return Response(
                {"detail": "Loan is not a refinancing loan."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            payload = original_schedule_payload(loan)
        except LoanValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            [dict(OriginalLoanScheduleRowSerializer(row).data) for row in payload],
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


class LoanHistoryView(APIView):
    """The loan's events and the audit entries about it, newest first (admin console)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: LoanHistoryResponseSerializer})
    def get(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        loan = Loan.objects.filter(id=loan_id).first()
        if loan is None:
            return Response({"detail": "Loan does not exist."}, status=status.HTTP_404_NOT_FOUND)
        entries = LoanHistoryEntrySerializer(loan_history.loan_history(loan), many=True).data
        return Response({"entries": entries}, status=status.HTTP_200_OK)


class LoanComingSoonView(APIView):
    """U33-DEC-17: show a draft Direct loan as Coming soon (POST) or hide it again (DELETE)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=LoanComingSoonRequestSerializer, responses={200: LoanSerializer})
    def post(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = LoanComingSoonRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            loan = announce_loan_coming_soon(
                AnnounceComingSoonCommand(
                    actor=cast(Model, request.user),
                    loan_id=str(loan_id),
                    planned_opening_date=data["planned_opening_date"],
                    note=data["note"],
                )
            )
        except LoanAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LoanValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_loan(loan), status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={200: LoanSerializer})
    def delete(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            loan = withdraw_loan_coming_soon(actor=cast(Model, request.user), loan_id=str(loan_id))
        except LoanAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except LoanValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_loan(loan), status=status.HTTP_200_OK)


def _security_command(request: Request, loan_id: str, security_id: str | None) -> Any:
    serializer = LoanSecurityRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data: dict[str, Any] = serializer.validated_data
    return loan_securities.SaveLoanSecurityCommand(
        actor=cast(Model, request.user),
        loan_id=str(loan_id),
        security_id=security_id,
        security_type=data["security_type"],
        description=data["description"],
        holder_name=data["holder_name"],
        rank=data["rank"],
        status=data["status"],
        value_minor=data["value_minor"],
        valuation_date=data["valuation_date"],
        valuation_source=data["valuation_source"],
        appraiser=data["appraiser"],
        prior_ranking_debt_minor=data["prior_ranking_debt_minor"],
        insurance=data["insurance"],
        undertaking_scope=data["undertaking_scope"],
        undertaking_limit_minor=data["undertaking_limit_minor"],
        document_ids=tuple(str(item) for item in data["document_ids"]),
    )


def _security_error(exc: Exception) -> Response:
    if isinstance(exc, loan_securities.LoanSecurityAuthorizationError):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class LoanSecurityListView(APIView):
    """U33-DEC-21: the securities of a loan (GET) or add one (POST)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: LoanSecurityListSerializer})
    def get(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        actor = cast(Model, request.user)
        try:
            securities = loan_securities.list_loan_securities(actor=actor, loan_id=str(loan_id))
            documents = loan_securities.borrower_documents_for_securities(
                actor=actor, loan_id=str(loan_id)
            )
        except loan_securities.LoanSecurityError as exc:
            return _security_error(exc)
        return Response({"securities": securities, "borrower_documents": documents})

    @extend_schema(request=LoanSecurityRequestSerializer, responses={201: LoanSecuritySerializer})
    def post(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            payload = loan_securities.save_loan_security(_security_command(request, loan_id, None))
        except loan_securities.LoanSecurityError as exc:
            return _security_error(exc)
        return Response(payload, status=status.HTTP_201_CREATED)


class LoanSecurityMoveView(APIView):
    """U33-DEC-21: move a security one place up or down in a draft."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LoanSecurityMoveRequestSerializer, responses={200: LoanSecurityListSerializer}
    )
    def post(self, request: Request, loan_id: str, security_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = LoanSecurityMoveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actor = cast(Model, request.user)
        try:
            securities = loan_securities.move_loan_security(
                actor=actor,
                loan_id=str(loan_id),
                security_id=str(security_id),
                direction=serializer.validated_data["direction"],
            )
            documents = loan_securities.borrower_documents_for_securities(
                actor=actor, loan_id=str(loan_id)
            )
        except loan_securities.LoanSecurityError as exc:
            return _security_error(exc)
        return Response({"securities": securities, "borrower_documents": documents})


class LoanSecurityDetailView(APIView):
    """U33-DEC-21: change a security (PUT), or remove a wrong one from a draft (DELETE)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=LoanSecurityRequestSerializer, responses={200: LoanSecuritySerializer})
    def put(self, request: Request, loan_id: str, security_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            payload = loan_securities.save_loan_security(
                _security_command(request, loan_id, str(security_id))
            )
        except loan_securities.LoanSecurityError as exc:
            return _security_error(exc)
        return Response(payload)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request: Request, loan_id: str, security_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            loan_securities.remove_loan_security(
                actor=cast(Model, request.user), loan_id=str(loan_id), security_id=str(security_id)
            )
        except loan_securities.LoanSecurityError as exc:
            return _security_error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _credit_check_error(exc: Exception) -> Response:
    if isinstance(exc, loan_credit_checks.CreditCheckAuthorizationError):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _credit_check_command(request: Request, loan_id: str, check_id: str | None) -> Any:
    serializer = LoanCreditCheckRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data: dict[str, Any] = serializer.validated_data
    return loan_credit_checks.SaveCreditCheckCommand(
        actor=cast(Model, request.user), loan_id=str(loan_id), check_id=check_id, **data
    )


class LoanCreditCheckListView(APIView):
    """U33-DEC-20: the loan's checks and monitoring text (GET) or record a check (POST)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: LoanCreditChecksSerializer})
    def get(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            payload = loan_credit_checks.list_credit_checks(
                actor=cast(Model, request.user), loan_id=str(loan_id)
            )
        except loan_credit_checks.CreditCheckError as exc:
            return _credit_check_error(exc)
        return Response(payload)

    @extend_schema(
        request=LoanCreditCheckRequestSerializer, responses={201: LoanCreditCheckSerializer}
    )
    def post(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            payload = loan_credit_checks.save_credit_check(
                _credit_check_command(request, loan_id, None)
            )
        except loan_credit_checks.CreditCheckError as exc:
            return _credit_check_error(exc)
        return Response(payload, status=status.HTTP_201_CREATED)


class LoanCreditCheckMoveView(APIView):
    """U33-DEC-20: move a check one place up or down."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LoanSecurityMoveRequestSerializer, responses={200: LoanCreditChecksSerializer}
    )
    def post(self, request: Request, loan_id: str, check_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = LoanSecurityMoveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = loan_credit_checks.move_credit_check(
                actor=cast(Model, request.user),
                loan_id=str(loan_id),
                check_id=str(check_id),
                direction=serializer.validated_data["direction"],
            )
        except loan_credit_checks.CreditCheckError as exc:
            return _credit_check_error(exc)
        return Response(payload)


class LoanCreditCheckDetailView(APIView):
    """U33-DEC-20: change (PUT) or remove (DELETE) a check."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LoanCreditCheckRequestSerializer, responses={200: LoanCreditCheckSerializer}
    )
    def put(self, request: Request, loan_id: str, check_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            payload = loan_credit_checks.save_credit_check(
                _credit_check_command(request, loan_id, str(check_id))
            )
        except loan_credit_checks.CreditCheckError as exc:
            return _credit_check_error(exc)
        return Response(payload)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request: Request, loan_id: str, check_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            loan_credit_checks.remove_credit_check(
                actor=cast(Model, request.user), loan_id=str(loan_id), check_id=str(check_id)
            )
        except loan_credit_checks.CreditCheckError as exc:
            return _credit_check_error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class LoanReportingPlanView(APIView):
    """U33-DEC-20: what the borrower reports over the loan term, proposed or agreed."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LoanReportingPlanRequestSerializer, responses={200: LoanCreditChecksSerializer}
    )
    def put(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = LoanReportingPlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = loan_credit_checks.set_reporting_plan(
                actor=cast(Model, request.user),
                loan_id=str(loan_id),
                status=serializer.validated_data["status"],
                milestones=list(serializer.validated_data["milestones"]),
            )
        except loan_credit_checks.CreditCheckError as exc:
            return _credit_check_error(exc)
        return Response(payload)


class LoanMonitoringView(APIView):
    """U33-DEC-20: how often and on what the loan is followed."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LoanMonitoringRequestSerializer, responses={200: LoanCreditChecksSerializer}
    )
    def post(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = LoanMonitoringRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = loan_credit_checks.set_monitoring(
                actor=cast(Model, request.user),
                loan_id=str(loan_id),
                frequency=serializer.validated_data["frequency"],
                focus=serializer.validated_data["focus"],
            )
        except loan_credit_checks.CreditCheckError as exc:
            return _credit_check_error(exc)
        return Response(payload)
