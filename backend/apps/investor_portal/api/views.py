from __future__ import annotations

from typing import Any

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
    InvestorDepositInstructionsSerializer,
    InvestorDocumentDownloadRequestSerializer,
    InvestorDocumentDownloadResponseSerializer,
    InvestorDocumentsSerializer,
    InvestorNotificationsSerializer,
    InvestorPortfolioSerializer,
    PortalLimitQuerySerializer,
    PortfolioQuerySerializer,
    PrimaryOrdersPortalSerializer,
    SecondaryMarketActivityPortalSerializer,
)
from backend.apps.investor_portal.services import (
    InvestorDocumentDownloadCommand,
    InvestorPortalAuthorizationError,
    InvestorPortalValidationError,
    download_investor_document,
    get_deposit_instructions,
    get_fx_history,
    get_investor_activity,
    get_investor_balances,
    get_investor_dashboard,
    get_investor_documents,
    get_investor_notifications,
    get_investor_portfolio,
    get_primary_orders,
    get_secondary_market_activity,
)
from backend.apps.platform_core.api.impersonation import (
    ReadOnlyImpersonationError,
    readonly_read_actor_from_request,
)


def _portal_read_actor(request: Request) -> tuple[Model, Model]:
    try:
        return readonly_read_actor_from_request(request)
    except ReadOnlyImpersonationError as exc:
        raise InvestorPortalAuthorizationError(str(exc)) from exc


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
            actor, _audit_actor = _portal_read_actor(request)
            payload = get_investor_dashboard(actor=actor)
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class InvestorBalancesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: InvestorBalancePortalSerializer})
    def get(self, request: Request) -> Response:
        try:
            actor, _audit_actor = _portal_read_actor(request)
            payload = get_investor_balances(actor=actor)
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class InvestorDepositInstructionsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: InvestorDepositInstructionsSerializer})
    def get(self, request: Request) -> Response:
        try:
            actor, _audit_actor = _portal_read_actor(request)
            payload = get_deposit_instructions(actor=actor)
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class InvestorDocumentsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: InvestorDocumentsSerializer})
    def get(self, request: Request) -> Response:
        try:
            actor, _audit_actor = _portal_read_actor(request)
            payload = get_investor_documents(actor=actor)
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class InvestorDocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=InvestorDocumentDownloadRequestSerializer,
        responses={200: InvestorDocumentDownloadResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = InvestorDocumentDownloadRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            actor, audit_actor = _portal_read_actor(request)
            payload = download_investor_document(
                InvestorDocumentDownloadCommand(
                    actor=actor,
                    audit_actor=audit_actor,
                    document_kind=data["document_kind"],
                    document_id=data.get("document_id", ""),
                    output_format=data.get("output_format", "pdf"),
                    start_date=data.get("start_date"),
                    end_date=data.get("end_date"),
                    year=data.get("year"),
                )
            )
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class InvestorNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PortalLimitQuerySerializer],
        responses={200: InvestorNotificationsSerializer},
    )
    def get(self, request: Request) -> Response:
        serializer = PortalLimitQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            actor, _audit_actor = _portal_read_actor(request)
            payload = get_investor_notifications(
                actor=actor,
                limit=data["limit"],
            )
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
            actor, _audit_actor = _portal_read_actor(request)
            payload = get_investor_portfolio(
                actor=actor,
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
            actor, _audit_actor = _portal_read_actor(request)
            payload = get_investor_activity(
                actor=actor,
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
            actor, _audit_actor = _portal_read_actor(request)
            payload = get_primary_orders(actor=actor, limit=data["limit"])
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
            actor, _audit_actor = _portal_read_actor(request)
            payload = get_secondary_market_activity(
                actor=actor,
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
            actor, _audit_actor = _portal_read_actor(request)
            payload = get_fx_history(actor=actor, limit=data["limit"])
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)
