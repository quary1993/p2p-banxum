from __future__ import annotations

from typing import Any, cast

from django.db.models import Model
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.fx.api.serializers import (
    FxDeltaReportQuerySerializer,
    FxDeltaReportSerializer,
    FxExchangeSerializer,
    FxExternalSettlementDeclareRequestSerializer,
    FxExternalSettlementSerializer,
    FxQuoteExecuteRequestSerializer,
    FxQuoteIssueRequestSerializer,
    FxQuoteSerializer,
    FxRealizedSettlementReportSerializer,
    serialize_fx_delta_report,
    serialize_fx_exchange,
    serialize_fx_external_settlement,
    serialize_fx_quote,
    serialize_fx_realized_settlement_report,
)
from backend.apps.fx.services import (
    DeclareFxExternalSettlementCommand,
    ExecuteFxQuoteCommand,
    FxAuthorizationError,
    FxValidationError,
    IssueFxQuoteCommand,
    configured_provider_rate,
    create_fx_delta_report,
    create_fx_realized_settlement_report,
    declare_fx_external_settlement,
    execute_fx_quote,
    issue_fx_quote,
)
from backend.apps.platform_core.api.request_meta import client_ip, user_agent


def _error_response(exc: Exception) -> Response:
    status_code = (
        status.HTTP_403_FORBIDDEN
        if isinstance(exc, FxAuthorizationError)
        else status.HTTP_400_BAD_REQUEST
    )
    return Response({"detail": str(exc)}, status=status_code)


class FxQuoteIssueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=FxQuoteIssueRequestSerializer,
        responses={201: FxQuoteSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = FxQuoteIssueRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            provider_rate = configured_provider_rate(
                source_currency=data["source_currency"],
                target_currency=data["target_currency"],
            )
            quote = issue_fx_quote(
                IssueFxQuoteCommand(
                    actor=cast(Model, request.user),
                    source_currency=data["source_currency"],
                    target_currency=data["target_currency"],
                    source_amount_minor=data["source_amount_minor"],
                    provider_rate=provider_rate,
                    idempotency_key=data["idempotency_key"],
                )
            )
        except (FxAuthorizationError, FxValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_fx_quote(quote), status=status.HTTP_201_CREATED)


class FxQuoteExecuteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=FxQuoteExecuteRequestSerializer,
        responses={201: FxExchangeSerializer},
    )
    def post(self, request: Request, quote_id: str) -> Response:
        serializer = FxQuoteExecuteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            exchange = execute_fx_quote(
                ExecuteFxQuoteCommand(
                    actor=cast(Model, request.user),
                    quote_id=quote_id,
                    idempotency_key=data["idempotency_key"],
                    sensitive_action_code_id=str(data["sensitive_action_code_id"]),
                    sensitive_action_code=data["sensitive_action_code"],
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except (FxAuthorizationError, FxValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_fx_exchange(exchange), status=status.HTTP_201_CREATED)


class FxDeltaReportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[FxDeltaReportQuerySerializer],
        responses={200: FxDeltaReportSerializer},
    )
    def get(self, request: Request) -> Response:
        serializer = FxDeltaReportQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            report = create_fx_delta_report(
                actor=cast(Model, request.user),
                start_date=data["start_date"],
                end_date=data["end_date"],
            )
        except (FxAuthorizationError, FxValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_fx_delta_report(report), status=status.HTTP_200_OK)


class FxExternalSettlementDeclareView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=FxExternalSettlementDeclareRequestSerializer,
        responses={201: FxExternalSettlementSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = FxExternalSettlementDeclareRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            settlement = declare_fx_external_settlement(
                DeclareFxExternalSettlementCommand(
                    actor=cast(Model, request.user),
                    sold_currency=data["sold_currency"],
                    bought_currency=data["bought_currency"],
                    sold_amount_minor=data["sold_amount_minor"],
                    bought_amount_minor=data["bought_amount_minor"],
                    start_date=data["start_date"],
                    end_date=data["end_date"],
                    booking_date=data["booking_date"],
                    value_date=data["value_date"],
                    collection_account_identifier=data["collection_account_identifier"],
                    bank_reference=data.get("bank_reference", ""),
                    payment_reference=data.get("payment_reference", ""),
                    evidence_reference=data.get("evidence_reference", ""),
                    notes=data.get("notes", ""),
                    idempotency_key=data["idempotency_key"],
                )
            )
        except (FxAuthorizationError, FxValidationError) as exc:
            return _error_response(exc)
        return Response(
            serialize_fx_external_settlement(settlement),
            status=status.HTTP_201_CREATED,
        )


class FxRealizedSettlementReportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[FxDeltaReportQuerySerializer],
        responses={200: FxRealizedSettlementReportSerializer},
    )
    def get(self, request: Request) -> Response:
        serializer = FxDeltaReportQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            report = create_fx_realized_settlement_report(
                actor=cast(Model, request.user),
                start_date=data["start_date"],
                end_date=data["end_date"],
            )
        except (FxAuthorizationError, FxValidationError) as exc:
            return _error_response(exc)
        return Response(
            serialize_fx_realized_settlement_report(report),
            status=status.HTTP_200_OK,
        )
