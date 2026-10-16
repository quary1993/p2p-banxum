from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from django.core.cache import cache
from django.db.models import Model
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.marketplace_primary.api.serializers import (
    MarketplaceBorrowerDocumentDownloadSerializer,
    MarketplaceLoanDetailSerializer,
    MarketplaceLoanPreviewSerializer,
    PrimaryInvestmentOrderAllocateRequestSerializer,
    PrimaryInvestmentOrderCreateRequestSerializer,
    PrimaryInvestmentOrderReleaseRequestSerializer,
    PrimaryInvestmentOrderSerializer,
    PrimaryLoanCancellationRequestSerializer,
    PrimaryLoanCancellationSerializer,
    PrimaryLoanCloseRequestSerializer,
    PrimaryLoanCloseSerializer,
    PrimaryLoanExpiryScanRequestSerializer,
    PrimaryLoanExpiryScanResponseSerializer,
    PrimaryOrderBatchRequestSerializer,
    PrimaryOrderBatchResponseSerializer,
    PublicMarketplaceLoanListQuerySerializer,
    PublicOriginatorSerializer,
    PublicProjectListQuerySerializer,
    PublicProjectSerializer,
    PublicStatisticsSerializer,
    serialize_primary_expiry_scan_result,
    serialize_primary_loan_cancellation,
    serialize_primary_loan_close,
    serialize_primary_order,
)
from backend.apps.marketplace_primary.public_site import (
    PublicProjectNotFoundError,
    get_public_project,
    get_public_statistics,
    list_public_originators,
    list_public_projects,
)
from backend.apps.marketplace_primary.services import (
    AllocatePrimaryInvestmentOrderCommand,
    CancelPrimaryLoanFundingCommand,
    ClosePrimaryLoanFundingCommand,
    CreatePrimaryInvestmentOrderCommand,
    MarketplacePrimaryAuthorizationError,
    MarketplacePrimaryOrderNotPendingError,
    MarketplacePrimarySwissInvestorLimitError,
    MarketplacePrimaryValidationError,
    PlacePrimaryOrderBatchCommand,
    PrimaryOrderBatchItemCommand,
    ReleasePrimaryInvestmentOrderCommand,
    ScanExpiredPrimaryFundingCommand,
    allocate_primary_order_from_balance,
    cancel_primary_loan_funding,
    close_primary_loan_funding,
    create_primary_investment_order,
    download_marketplace_borrower_document,
    get_full_marketplace_loan,
    list_investor_marketplace_loans,
    place_primary_order_batch,
    release_primary_order_balance,
    scan_expired_primary_loan_funding,
)
from backend.apps.platform_core.api.impersonation import (
    ReadOnlyImpersonationError,
    readonly_read_actor_from_request,
)
from backend.apps.platform_core.api.request_meta import client_ip, user_agent
from backend.apps.platform_core.api.sensitive_actions import (
    sensitive_action_pin_error_response,
)
from backend.apps.platform_core.services.sensitive_actions import SensitiveActionPinError


def _error_response(exc: Exception) -> Response:
    status_code: int = (
        status.HTTP_403_FORBIDDEN
        if isinstance(exc, MarketplacePrimaryAuthorizationError)
        else status.HTTP_400_BAD_REQUEST
    )
    payload: dict[str, str] = {"detail": str(exc)}
    if isinstance(exc, MarketplacePrimaryOrderNotPendingError):
        # The client drops the closed order and creates a new one on retry.
        payload["code"] = MarketplacePrimaryOrderNotPendingError.code
    if isinstance(exc, MarketplacePrimarySwissInvestorLimitError):
        # A Swiss-borrower loan has no place left for a new investor (MKT-DEC-028).
        status_code = status.HTTP_409_CONFLICT
        payload["code"] = MarketplacePrimarySwissInvestorLimitError.code
    return Response(payload, status=status_code)


PUBLIC_SITE_CACHE_SECONDS = 60
PUBLIC_SITE_CACHE_PREFIX = "marketplace_primary:public_site:v1"


def _cached_public_payload(key: str, build: Callable[[], Any]) -> Any:
    """Short shared cache for the anonymous public site payloads (they simply expire)."""
    cache_key = f"{PUBLIC_SITE_CACHE_PREFIX}:{key}"
    try:
        cached = cache.get(cache_key)
    except Exception:  # A cache outage must not take the public site down.
        cached = None
    if cached is not None:
        return cached
    payload = build()
    try:
        cache.set(cache_key, payload, PUBLIC_SITE_CACHE_SECONDS)
    except Exception:  # Serve the fresh payload even when it cannot be cached.
        pass
    return payload


class PublicProjectListView(APIView):
    """Public site: every loan a visitor may see (owner decision 2026-10-15, MKT-DEC-002)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        operation_id="v1_marketplace_primary_public_projects_list",
        summary="Public projects",
        description=(
            "Anonymous. Open loans, fully subscribed loans still in their round and every "
            "funded loan (Direct and Loan Originator claims): open first (newest published "
            "first), then the rest (newest funding close first). Never the borrower's name."
        ),
        parameters=[PublicProjectListQuerySerializer],
        responses={200: PublicProjectSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        serializer = PublicProjectListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        limit = int(serializer.validated_data["limit"])

        def build() -> list[Any]:
            return list(PublicProjectSerializer(list_public_projects(limit=limit), many=True).data)

        payload = _cached_public_payload(f"projects:{limit}", build)
        return Response(payload, status=status.HTTP_200_OK)


class PublicProjectDetailView(APIView):
    """Public site: one project page (404 unless the loan is public)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        operation_id="v1_marketplace_primary_public_projects_retrieve",
        summary="Public project",
        responses={
            200: PublicProjectSerializer,
            404: OpenApiResponse(description="The loan does not exist or is not public."),
        },
    )
    def get(self, request: Request, loan_id: str) -> Response:
        def build() -> dict[str, Any]:
            return dict(PublicProjectSerializer(get_public_project(loan_id=str(loan_id))).data)

        try:
            payload = _cached_public_payload(f"project:{loan_id}", build)
        except PublicProjectNotFoundError as exc:
            raise NotFound() from exc
        return Response(payload, status=status.HTTP_200_OK)


class PublicStatisticsView(APIView):
    """Public site: track record computed from the public projects."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        operation_id="v1_marketplace_primary_public_statistics_retrieve",
        summary="Public statistics",
        responses={200: PublicStatisticsSerializer},
    )
    def get(self, request: Request) -> Response:
        payload = _cached_public_payload(
            "statistics",
            lambda: dict(PublicStatisticsSerializer(get_public_statistics()).data),
        )
        return Response(payload, status=status.HTTP_200_OK)


class PublicOriginatorListView(APIView):
    """Public site: active Loan Originators with at least one public claim."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        operation_id="v1_marketplace_primary_public_originators_list",
        summary="Public Loan Originators",
        responses={200: PublicOriginatorSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        payload = _cached_public_payload(
            "originators",
            lambda: list(PublicOriginatorSerializer(list_public_originators(), many=True).data),
        )
        return Response(payload, status=status.HTTP_200_OK)


class MarketplaceOpportunityListView(APIView):
    """Investor marketplace list with full preview data (registration and KYC required)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[PublicMarketplaceLoanListQuerySerializer],
        responses={200: MarketplaceLoanPreviewSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        serializer = PublicMarketplaceLoanListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            actor, _audit_actor = readonly_read_actor_from_request(request)
            payload = list_investor_marketplace_loans(actor=actor, limit=data["limit"])
        except ReadOnlyImpersonationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except MarketplacePrimaryAuthorizationError as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class MarketplaceLoanDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MarketplaceLoanDetailSerializer})
    def get(self, request: Request, loan_id: str) -> Response:
        try:
            actor, _audit_actor = readonly_read_actor_from_request(request)
            payload = get_full_marketplace_loan(actor=actor, loan_id=loan_id)
        except ReadOnlyImpersonationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except (MarketplacePrimaryAuthorizationError, MarketplacePrimaryValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class MarketplaceLoanDocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MarketplaceBorrowerDocumentDownloadSerializer})
    def get(self, request: Request, loan_id: str, document_id: str) -> Response:
        try:
            actor, audit_actor = readonly_read_actor_from_request(request)
            payload = download_marketplace_borrower_document(
                actor=actor,
                audit_actor=audit_actor,
                loan_id=str(loan_id),
                document_id=str(document_id),
            )
        except ReadOnlyImpersonationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
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
                    sensitive_action_code_id=str(data["sensitive_action_code_id"]),
                    sensitive_action_code=data["sensitive_action_code"],
                    pin=data["pin"],
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except SensitiveActionPinError as exc:
            return sensitive_action_pin_error_response(exc)
        except (MarketplacePrimaryAuthorizationError, MarketplacePrimaryValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_primary_order(order), status=status.HTTP_200_OK)


class PrimaryOrderBatchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="marketplace_primary_orders_batch_create",
        request=PrimaryOrderBatchRequestSerializer,
        responses={201: PrimaryOrderBatchResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = PrimaryOrderBatchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = place_primary_order_batch(
                PlacePrimaryOrderBatchCommand(
                    actor=cast(Model, request.user),
                    items=[
                        PrimaryOrderBatchItemCommand(
                            loan_id=str(item["loan_id"]),
                            amount_minor=int(item["amount_minor"]),
                            quote_id=(
                                str(item["quote_id"]) if item.get("quote_id") is not None else None
                            ),
                        )
                        for item in data["items"]
                    ],
                    document_acceptance_id=str(data["document_acceptance_id"]),
                    sensitive_action_code_id=str(data["sensitive_action_code_id"]),
                    sensitive_action_code=data["sensitive_action_code"],
                    pin=data["pin"],
                    idempotency_key=data["idempotency_key"],
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except SensitiveActionPinError as exc:
            return sensitive_action_pin_error_response(exc)
        except (MarketplacePrimaryAuthorizationError, MarketplacePrimaryValidationError) as exc:
            return _error_response(exc)
        return Response(
            {
                "batch_id": str(result.batch.id),
                "currency": result.batch.currency_id,
                "currency_totals": result.batch.currency_totals,
                "orders": [serialize_primary_order(order) for order in result.orders],
                "order_count": len(result.orders),
                "originator_purchases": [
                    {
                        "purchase_id": str(purchase.id),
                        "quote_id": str(purchase.quote_id),
                        "loan_id": str(purchase.loan_profile.loan_id),
                        "holding_id": str(purchase.holding_id),
                        "currency": purchase.currency_id,
                        "cash_consideration_minor": purchase.cash_consideration_minor,
                        "assigned_principal_minor": purchase.assigned_principal_minor,
                        "outstanding_principal_at_pricing_minor": (
                            purchase.outstanding_principal_at_pricing_minor
                        ),
                        "share_ppm": purchase.share_ppm,
                        "target_yield_bps": purchase.target_yield_bps,
                        "purchased_at": purchase.purchased_at,
                    }
                    for purchase in result.originator_purchases
                ],
                "originator_purchase_count": len(result.originator_purchases),
                "total_amount_minor": (
                    int(result.batch.total_amount_minor)
                    if result.batch.total_amount_minor is not None
                    else None
                ),
            },
            status=status.HTTP_201_CREATED,
        )


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
                    retry_failed=True,
                )
            )
        except (MarketplacePrimaryAuthorizationError, MarketplacePrimaryValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_primary_loan_close(close), status=status.HTTP_200_OK)


class PrimaryLoanCancellationView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PrimaryLoanCancellationRequestSerializer,
        responses={200: PrimaryLoanCancellationSerializer},
    )
    def post(self, request: Request, loan_id: str) -> Response:
        serializer = PrimaryLoanCancellationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            cancellation = cancel_primary_loan_funding(
                CancelPrimaryLoanFundingCommand(
                    actor=cast(Model, request.user),
                    loan_id=loan_id,
                    reason=data["reason"],
                    investor_message=data.get("investor_message", ""),
                    idempotency_key=data["idempotency_key"],
                )
            )
        except (MarketplacePrimaryAuthorizationError, MarketplacePrimaryValidationError) as exc:
            return _error_response(exc)
        return Response(
            serialize_primary_loan_cancellation(cancellation),
            status=status.HTTP_200_OK,
        )


class PrimaryLoanExpiryScanView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PrimaryLoanExpiryScanRequestSerializer,
        responses={200: PrimaryLoanExpiryScanResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = PrimaryLoanExpiryScanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = scan_expired_primary_loan_funding(
                ScanExpiredPrimaryFundingCommand(
                    actor=cast(Model, request.user),
                    as_of_date=data.get("as_of_date"),
                    loan_ids=tuple(str(loan_id) for loan_id in data.get("loan_ids", [])),
                    reason=data.get("reason", ""),
                    investor_message=data.get("investor_message", ""),
                    idempotency_key=data.get("idempotency_key", ""),
                    limit=data.get("limit", 250),
                )
            )
        except (MarketplacePrimaryAuthorizationError, MarketplacePrimaryValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_primary_expiry_scan_result(result), status=status.HTTP_200_OK)
