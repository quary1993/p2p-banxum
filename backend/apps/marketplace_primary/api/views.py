from __future__ import annotations

from typing import Any, cast

from django.db.models import Model
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.marketplace_primary.api.serializers import (
    MarketplaceLoanDetailSerializer,
    MarketplaceLoanPreviewSerializer,
    PrimaryInvestmentOrderAllocateRequestSerializer,
    PrimaryInvestmentOrderCreateRequestSerializer,
    PrimaryInvestmentOrderReleaseRequestSerializer,
    PrimaryInvestmentOrderSerializer,
    PrimaryLoanCloseRequestSerializer,
    PrimaryLoanCloseSerializer,
    PublicMarketplaceLoanListQuerySerializer,
    serialize_primary_loan_close,
    serialize_primary_order,
)
from backend.apps.marketplace_primary.services import (
    AllocatePrimaryInvestmentOrderCommand,
    ClosePrimaryLoanFundingCommand,
    CreatePrimaryInvestmentOrderCommand,
    MarketplacePrimaryAuthorizationError,
    MarketplacePrimaryValidationError,
    ReleasePrimaryInvestmentOrderCommand,
    allocate_primary_order_from_balance,
    close_primary_loan_funding,
    create_primary_investment_order,
    get_full_marketplace_loan,
    list_public_marketplace_loans,
    release_primary_order_balance,
)


def _error_response(exc: Exception) -> Response:
    status_code = (
        status.HTTP_403_FORBIDDEN
        if isinstance(exc, MarketplacePrimaryAuthorizationError)
        else status.HTTP_400_BAD_REQUEST
    )
    return Response({"detail": str(exc)}, status=status_code)


class PublicMarketplaceLoanListView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[PublicMarketplaceLoanListQuerySerializer],
        responses={200: MarketplaceLoanPreviewSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        serializer = PublicMarketplaceLoanListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        return Response(
            list_public_marketplace_loans(limit=data["limit"]),
            status=status.HTTP_200_OK,
        )


class MarketplaceLoanDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MarketplaceLoanDetailSerializer})
    def get(self, request: Request, loan_id: str) -> Response:
        try:
            payload = get_full_marketplace_loan(actor=cast(Model, request.user), loan_id=loan_id)
        except (MarketplacePrimaryAuthorizationError, MarketplacePrimaryValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class PrimaryInvestmentOrderCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PrimaryInvestmentOrderCreateRequestSerializer,
        responses={201: PrimaryInvestmentOrderSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = PrimaryInvestmentOrderCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            order = create_primary_investment_order(
                CreatePrimaryInvestmentOrderCommand(
                    actor=cast(Model, request.user),
                    loan_id=str(data["loan_id"]),
                    amount_minor=data["amount_minor"],
                    idempotency_key=data["idempotency_key"],
                    notes=data.get("notes", ""),
                )
            )
        except (MarketplacePrimaryAuthorizationError, MarketplacePrimaryValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_primary_order(order), status=status.HTTP_201_CREATED)


class PrimaryInvestmentOrderAllocateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PrimaryInvestmentOrderAllocateRequestSerializer,
        responses={200: PrimaryInvestmentOrderSerializer},
    )
    def post(self, request: Request, order_id: str) -> Response:
        serializer = PrimaryInvestmentOrderAllocateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            order = allocate_primary_order_from_balance(
                AllocatePrimaryInvestmentOrderCommand(
                    actor=cast(Model, request.user),
                    order_id=order_id,
                    document_acceptance_id=str(data["document_acceptance_id"]),
                    idempotency_key=data["idempotency_key"],
                )
            )
        except (MarketplacePrimaryAuthorizationError, MarketplacePrimaryValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_primary_order(order), status=status.HTTP_200_OK)


class PrimaryInvestmentOrderReleaseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PrimaryInvestmentOrderReleaseRequestSerializer,
        responses={200: PrimaryInvestmentOrderSerializer},
    )
    def post(self, request: Request, order_id: str) -> Response:
        serializer = PrimaryInvestmentOrderReleaseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            order = release_primary_order_balance(
                ReleasePrimaryInvestmentOrderCommand(
                    actor=cast(Model, request.user),
                    order_id=order_id,
                    reason=data["reason"],
                    idempotency_key=data["idempotency_key"],
                )
            )
        except (MarketplacePrimaryAuthorizationError, MarketplacePrimaryValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_primary_order(order), status=status.HTTP_200_OK)


class PrimaryLoanCloseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PrimaryLoanCloseRequestSerializer,
        responses={200: PrimaryLoanCloseSerializer},
    )
    def post(self, request: Request, loan_id: str) -> Response:
        serializer = PrimaryLoanCloseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            close = close_primary_loan_funding(
                ClosePrimaryLoanFundingCommand(
                    actor=cast(Model, request.user),
                    loan_id=loan_id,
                    reason=data["reason"],
                    investor_message=data.get("investor_message", ""),
                    idempotency_key=data["idempotency_key"],
                )
            )
        except (MarketplacePrimaryAuthorizationError, MarketplacePrimaryValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_primary_loan_close(close), status=status.HTTP_200_OK)
