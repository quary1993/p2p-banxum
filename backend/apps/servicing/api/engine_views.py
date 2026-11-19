"""IP of Webby-Soft SRL. 18.6 admin API of the interest engine: servicing position, payment
preview, recovery expenses and the Default declaration (and its cancellation)."""

from __future__ import annotations

from typing import Any, cast

from django.apps import apps
from django.db.models import Model
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.platform_core.domain.access import is_admin_actor
from backend.apps.servicing import engine as engine_servicing


class EngineExpenseSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    amount_minor = serializers.IntegerField()
    currency = serializers.CharField()
    value_date = serializers.DateField()
    note = serializers.CharField()
    evidence_reference = serializers.CharField(allow_blank=True)
    document_id = serializers.CharField(allow_blank=True)
    owed_minor = serializers.IntegerField()
    penalty_owed_minor = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class EngineDeclarationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    declared_on = serializers.DateField()
    days_late = serializers.IntegerField()
    note = serializers.CharField(allow_blank=True)
    whole_principal_minor = serializers.IntegerField()
    whole_interest_minor = serializers.IntegerField()
    frozen_penalty_minor = serializers.IntegerField()
    cancelled_at = serializers.DateTimeField(allow_null=True)
    cancel_reason = serializers.CharField(allow_blank=True)


class EngineInstallmentPenaltySerializer(serializers.Serializer[Any]):
    installment_number = serializers.IntegerField()
    due_date = serializers.DateField()
    owed_minor = serializers.IntegerField()
    penalty_owed_minor = serializers.IntegerField()


class LoanServicingPositionSerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    interest_engine = serializers.BooleanField()
    currency = serializers.CharField()
    status = serializers.CharField()
    days_late = serializers.IntegerField()
    default_possible = serializers.BooleanField()
    late_days = serializers.IntegerField()
    default_days = serializers.IntegerField()
    declarations = EngineDeclarationSerializer(many=True)
    expenses = EngineExpenseSerializer(many=True)
    oldest_unpaid_due_date = serializers.DateField(allow_null=True, required=False)
    as_of = serializers.DateField(required=False)
    principal_owed_minor = serializers.IntegerField(required=False)
    due_now_minor = serializers.IntegerField(required=False)
    penalty_owed_minor = serializers.IntegerField(required=False)
    expenses_owed_minor = serializers.IntegerField(required=False)
    penalty_daily_rate_percent = serializers.CharField(required=False)
    penalty_investor_share_bps = serializers.IntegerField(required=False)
    grace_business_days = serializers.IntegerField(required=False)
    payment_frequency = serializers.CharField(required=False)
    expenses_allowed = serializers.BooleanField(required=False)
    installment_penalties = EngineInstallmentPenaltySerializer(many=True, required=False)


class EnginePaymentPreviewRequestSerializer(serializers.Serializer[Any]):
    amount_minor = serializers.IntegerField(min_value=1)
    value_date = serializers.DateField()


class EnginePaymentPreviewInstallmentSerializer(serializers.Serializer[Any]):
    installment_number = serializers.IntegerField()
    due_date = serializers.CharField(allow_blank=True)
    penalty_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    principal_minor = serializers.IntegerField()


class EngineScheduleRowSerializer(serializers.Serializer[Any]):
    installment_number = serializers.IntegerField()
    due_date = serializers.DateField()
    principal_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    total_minor = serializers.IntegerField()


class EnginePaymentPreviewSerializer(serializers.Serializer[Any]):
    loan_id = serializers.UUIDField()
    currency = serializers.CharField()
    amount_minor = serializers.IntegerField()
    value_date = serializers.DateField()
    expenses_minor = serializers.IntegerField()
    penalty_minor = serializers.IntegerField()
    interest_minor = serializers.IntegerField()
    principal_minor = serializers.IntegerField()
    prepayment_minor = serializers.IntegerField()
    accrued_interest_days = serializers.IntegerField()
    schedule_changes = serializers.BooleanField()
    penalty_to_investors_minor = serializers.IntegerField()
    to_garanta_minor = serializers.IntegerField()
    fully_repaid = serializers.BooleanField()
    installments = EnginePaymentPreviewInstallmentSerializer(many=True)
    new_schedule = EngineScheduleRowSerializer(many=True)


class EngineExpenseRequestSerializer(serializers.Serializer[Any]):
    amount_minor = serializers.IntegerField(min_value=1)
    value_date = serializers.DateField()
    note = serializers.CharField()
    evidence_reference = serializers.CharField(required=False, allow_blank=True, default="")
    document_id = serializers.CharField(required=False, allow_blank=True, default="")
    idempotency_key = serializers.CharField(max_length=160)


class EngineDeclareDefaultRequestSerializer(serializers.Serializer[Any]):
    note = serializers.CharField(required=False, allow_blank=True, default="")


class EngineCancelDefaultRequestSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField()


def _forbidden() -> Response:
    return Response({"detail": "Admin access is required."}, status=status.HTTP_403_FORBIDDEN)


def _loan(loan_id: str) -> Model | None:
    return cast(Model | None, apps.get_model("loans", "Loan").objects.filter(id=loan_id).first())


def _error(exc: Exception) -> Response:
    detail = str(exc)
    code = (
        status.HTTP_403_FORBIDDEN
        if "super admin" in detail or "Admin access" in detail
        else status.HTTP_400_BAD_REQUEST
    )
    return Response({"detail": detail}, status=code)


class LoanServicingPositionView(APIView):
    """18.6: status (Pending / Due / Late / Default), amounts owed, expenses and declarations."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: LoanServicingPositionSerializer})
    def get(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _forbidden()
        loan = _loan(str(loan_id))
        if loan is None:
            return Response({"detail": "Loan does not exist."}, status=status.HTTP_404_NOT_FOUND)
        return Response(engine_servicing.servicing_position_payload(loan))


class EnginePaymentPreviewView(APIView):
    """18.6: how a payment would be used (expenses, penalties, interest, principal, prepayment)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=EnginePaymentPreviewRequestSerializer,
        responses={200: EnginePaymentPreviewSerializer},
    )
    def post(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _forbidden()
        serializer = EnginePaymentPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            payload = engine_servicing.preview_engine_payment(
                actor=cast(Model, request.user),
                loan_id=str(loan_id),
                amount_minor=int(data["amount_minor"]),
                value_date=data["value_date"],
            )
        except engine_servicing.EngineServicingError as exc:
            return _error(exc)
        return Response(payload)


class LoanExpenseListCreateView(APIView):
    """18.6: the recovery expenses of a loan (GET) or record one (POST)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: EngineExpenseSerializer(many=True)})
    def get(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _forbidden()
        loan = _loan(str(loan_id))
        if loan is None:
            return Response({"detail": "Loan does not exist."}, status=status.HTTP_404_NOT_FOUND)
        payload = engine_servicing.servicing_position_payload(loan)
        return Response(payload.get("expenses", []))

    @extend_schema(request=EngineExpenseRequestSerializer, responses={201: EngineExpenseSerializer})
    def post(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _forbidden()
        serializer = EngineExpenseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            expense = engine_servicing.record_loan_expense(
                engine_servicing.RecordLoanExpenseCommand(
                    actor=cast(Model, request.user),
                    loan_id=str(loan_id),
                    amount_minor=int(data["amount_minor"]),
                    value_date=data["value_date"],
                    note=data["note"],
                    evidence_reference=data.get("evidence_reference", ""),
                    document_id=data.get("document_id", ""),
                    idempotency_key=data["idempotency_key"],
                )
            )
        except engine_servicing.EngineServicingError as exc:
            return _error(exc)
        return Response(engine_servicing.expense_payload(expense), status=status.HTTP_201_CREATED)


class LoanDefaultDeclarationView(APIView):
    """18.6: declare Default (maturity) once the oldest unpaid installment reached the Default
    days. Never automatic."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=EngineDeclareDefaultRequestSerializer,
        responses={200: LoanServicingPositionSerializer},
    )
    def post(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _forbidden()
        serializer = EngineDeclareDefaultRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            engine_servicing.declare_loan_default(
                engine_servicing.DeclareLoanDefaultCommand(
                    actor=cast(Model, request.user),
                    loan_id=str(loan_id),
                    note=serializer.validated_data.get("note", ""),
                )
            )
        except engine_servicing.EngineServicingError as exc:
            return _error(exc)
        loan = cast(Model, _loan(str(loan_id)))
        return Response(engine_servicing.servicing_position_payload(loan))


class LoanDefaultCancellationView(APIView):
    """18.6: a super admin cancels a Default declared by mistake, with a written reason."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=EngineCancelDefaultRequestSerializer,
        responses={200: LoanServicingPositionSerializer},
    )
    def post(self, request: Request, loan_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _forbidden()
        serializer = EngineCancelDefaultRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            engine_servicing.cancel_loan_default(
                engine_servicing.CancelLoanDefaultCommand(
                    actor=cast(Model, request.user),
                    loan_id=str(loan_id),
                    reason=serializer.validated_data["reason"],
                )
            )
        except engine_servicing.EngineServicingError as exc:
            return _error(exc)
        loan = cast(Model, _loan(str(loan_id)))
        return Response(engine_servicing.servicing_position_payload(loan))
