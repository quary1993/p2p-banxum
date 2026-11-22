from __future__ import annotations

from importlib import import_module
from typing import Any, cast

from django.db.models import Model
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
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
    InvestorNotificationReadResponseSerializer,
    InvestorNotificationsSerializer,
    InvestorPortalFeaturesSerializer,
    InvestorPortfolioSerializer,
    InvestorReportCreateRequestSerializer,
    InvestorReportSerializer,
    InvestorReportsSerializer,
    InvestorReportSummaryQuerySerializer,
    InvestorReportSummarySerializer,
    InvestorSupportRequestCreateSerializer,
    InvestorSupportRequestReceiptSerializer,
    PortalLimitQuerySerializer,
    PortfolioQuerySerializer,
    PrimaryOrdersPortalSerializer,
    SecondaryMarketActivityPortalSerializer,
    TransactionPageSerializer,
    TransactionQuerySerializer,
)
from backend.apps.investor_portal.services import (
    InvestorDocumentDownloadCommand,
    InvestorPortalAuthorizationError,
    InvestorPortalNotFoundError,
    InvestorPortalValidationError,
    SubmitInvestorSupportRequestCommand,
    create_investor_report,
    download_investor_document,
    download_investor_report,
    export_investor_transactions_csv,
    get_deposit_instructions,
    get_fx_history,
    get_investor_activity,
    get_investor_balances,
    get_investor_dashboard,
    get_investor_documents,
    get_investor_notifications,
    get_investor_portal_features,
    get_investor_portfolio,
    get_investor_transactions,
    get_primary_orders,
    get_secondary_market_activity,
    investor_report_summary,
    list_investor_reports,
    mark_all_investor_notifications_read,
    mark_investor_notification_read,
    submit_investor_support_request,
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
        else status.HTTP_404_NOT_FOUND
        if isinstance(exc, InvestorPortalNotFoundError)
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


class InvestorReportsView(APIView):
    """18.3: the investor's kept reports (GET) and a new report (POST)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: InvestorReportsSerializer})
    def get(self, request: Request) -> Response:
        try:
            actor, _audit_actor = _portal_read_actor(request)
            payload = list_investor_reports(actor=actor)
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(InvestorReportsSerializer(payload).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=InvestorReportCreateRequestSerializer,
        responses={201: InvestorReportSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = InvestorReportCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            actor, audit_actor = _portal_read_actor(request)
            payload = create_investor_report(
                actor=actor,
                audit_actor=audit_actor,
                kind=data["kind"],
                start_date=data["start_date"],
                end_date=data["end_date"],
                currency=data["currency"],
                output_format=data["output_format"],
            )
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(InvestorReportSerializer(payload).data, status=status.HTTP_201_CREATED)


class InvestorReportDownloadView(APIView):
    """18.3: the file of a kept report, as it was issued."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: InvestorDocumentDownloadResponseSerializer})
    def get(self, request: Request, report_id: str) -> Response:
        try:
            actor, _audit_actor = _portal_read_actor(request)
            payload = download_investor_report(actor=actor, report_id=report_id)
        except (
            InvestorPortalAuthorizationError,
            InvestorPortalValidationError,
            InvestorPortalNotFoundError,
        ) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class InvestorReportSummaryView(APIView):
    """18.3: invested, principal repaid and interest received per currency (year or all)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[InvestorReportSummaryQuerySerializer],
        responses={200: InvestorReportSummarySerializer},
    )
    def get(self, request: Request) -> Response:
        serializer = InvestorReportSummaryQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        raw = str(serializer.validated_data["year"])
        year = int(raw) if raw.isdigit() and len(raw) == 4 else None
        try:
            actor, _audit_actor = _portal_read_actor(request)
            payload = investor_report_summary(actor=actor, year=year)
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(InvestorReportSummarySerializer(payload).data, status=status.HTTP_200_OK)


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


class InvestorNotificationReadView(APIView):
    """Marks one of the signed-in investor's own notifications as read (idempotent)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: InvestorNotificationReadResponseSerializer})
    def post(self, request: Request, notification_id: str) -> Response:
        try:
            payload = mark_investor_notification_read(
                actor=cast(Model, request.user),
                notification_id=notification_id,
            )
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class InvestorNotificationsReadAllView(APIView):
    """Marks every listed notification of the signed-in investor as read (idempotent)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: InvestorNotificationReadResponseSerializer})
    def post(self, request: Request) -> Response:
        try:
            payload = mark_all_investor_notifications_read(actor=cast(Model, request.user))
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


def _transaction_filters(data: dict[str, Any]) -> Any:
    from backend.apps.investor_portal.transactions import TransactionFilters

    return TransactionFilters(
        currency=str(data["currency"] or ""),
        group=str(data["group"] or ""),
        date_from=data["date_from"],
        date_to=data["date_to"],
        search=str(data["q"] or ""),
    )


class InvestorTransactionsView(APIView):
    """18.3: the Transactions page with server filters, pages and the available balance."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[TransactionQuerySerializer], responses={200: TransactionPageSerializer}
    )
    def get(self, request: Request) -> Response:
        serializer = TransactionQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            actor, _audit_actor = _portal_read_actor(request)
            payload = get_investor_transactions(
                actor=actor,
                filters=_transaction_filters(data),
                offset=data["offset"],
                limit=data["limit"],
            )
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(TransactionPageSerializer(payload).data, status=status.HTTP_200_OK)


class InvestorTransactionsExportView(APIView):
    """18.3: the whole filtered history as CSV in the investor's number format."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[TransactionQuerySerializer],
        responses={(200, "text/csv"): OpenApiTypes.STR},
    )
    def get(self, request: Request) -> HttpResponse | Response:
        serializer = TransactionQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            actor, _audit_actor = _portal_read_actor(request)
            content = export_investor_transactions_csv(
                actor=actor, filters=_transaction_filters(serializer.validated_data)
            )
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        response = HttpResponse(content, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="banxum-transactions.csv"'
        return response


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


class InvestorPortalFeaturesView(APIView):
    """Which optional features the investor app shows (for example currency exchange).

    Anonymous-safe: it returns only platform switches, never account data.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: InvestorPortalFeaturesSerializer})
    def get(self, request: Request) -> Response:
        return Response(get_investor_portal_features(), status=status.HTTP_200_OK)


class InvestorSupportRequestView(APIView):
    """Send a Help message or an account closure request to the team by email.

    201 with the receipt (reference, time, receipt email). 409 when the request key was used
    for another message; 429 with Retry-After after too many messages.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=InvestorSupportRequestCreateSerializer,
        responses={
            201: InvestorSupportRequestReceiptSerializer,
            200: InvestorSupportRequestReceiptSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = InvestorSupportRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        support = import_module("backend.apps.communications.support_requests")
        try:
            receipt = submit_investor_support_request(
                SubmitInvestorSupportRequestCommand(
                    actor=cast(Model, request.user),
                    kind=data["kind"],
                    idempotency_key=data["idempotency_key"],
                    topic=data["topic"],
                    message=data["message"],
                    context_type=data["context_type"],
                    context_id=data["context_id"],
                )
            )
        except support.SupportRequestThrottled as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(exc.wait_seconds)},
            )
        except support.SupportRequestConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except (InvestorPortalAuthorizationError, InvestorPortalValidationError) as exc:
            return _error_response(exc)
        return Response(receipt, status=status.HTTP_201_CREATED)
