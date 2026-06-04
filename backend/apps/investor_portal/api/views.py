from __future__ import annotations

from typing import Any, cast

from django.db.models import Model
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.investor_portal.api.serializers import (
    FxHistoryPortalSerializer,
    InvestorActivitySerializer,
    InvestorBalancePortalSerializer,
    InvestorDashboardSerializer,
    InvestorPortfolioSerializer,
    PortalLimitQuerySerializer,
    PortfolioQuerySerializer,
    PrimaryOrdersPortalSerializer,
    SecondaryMarketActivityPortalSerializer,
)
from backend.apps.investor_portal.services import (
    InvestorPortalAuthorizationError,
    InvestorPortalValidationError,
    get_fx_history,
    get_investor_activity,
    get_investor_balances,
    get_investor_dashboard,
    get_investor_portfolio,
    get_primary_orders,
    get_secondary_market_activity,
)


def _error_response(exc: Exception) -> Response:
    status_code = (
        status.HTTP_403_FORBIDDEN
        if isinstance(exc, InvestorPortalAuthorizationError)
        else status.HTTP_400_BAD_REQUEST
    )
    return Response({"detail": str(exc)}, status=status_code)


class InvestorDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: InvestorDashboardSerializer})
    def get(self, request: Request) -> Response:
        try:
            payload = get_investor_dashboard(actor=cast(Model, request.user))
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class InvestorBalancesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: InvestorBalancePortalSerializer})
    def get(self, request: Request) -> Response:
        try:
            payload = get_investor_balances(actor=cast(Model, request.user))
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class InvestorPortfolioView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PortfolioQuerySerializer],
        responses={200: InvestorPortfolioSerializer},
    )
    def get(self, request: Request) -> Response:
        serializer = PortfolioQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            payload = get_investor_portfolio(
                actor=cast(Model, request.user),
                include_inactive=data["include_inactive"],
            )
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class InvestorActivityView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PortalLimitQuerySerializer],
        responses={200: InvestorActivitySerializer},
    )
    def get(self, request: Request) -> Response:
        serializer = PortalLimitQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            payload = get_investor_activity(
                actor=cast(Model, request.user),
                limit=data["limit"],
            )
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class InvestorPrimaryOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PortalLimitQuerySerializer],
        responses={200: PrimaryOrdersPortalSerializer},
    )
    def get(self, request: Request) -> Response:
        serializer = PortalLimitQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            payload = get_primary_orders(actor=cast(Model, request.user), limit=data["limit"])
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class InvestorSecondaryMarketActivityView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PortalLimitQuerySerializer],
        responses={200: SecondaryMarketActivityPortalSerializer},
    )
    def get(self, request: Request) -> Response:
        serializer = PortalLimitQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            payload = get_secondary_market_activity(
                actor=cast(Model, request.user),
                limit=data["limit"],
            )
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class InvestorFxHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PortalLimitQuerySerializer],
        responses={200: FxHistoryPortalSerializer},
    )
    def get(self, request: Request) -> Response:
        serializer = PortalLimitQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            payload = get_fx_history(actor=cast(Model, request.user), limit=data["limit"])
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)
