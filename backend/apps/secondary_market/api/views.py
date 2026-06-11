from __future__ import annotations

from typing import Any, cast

from django.db.models import Model
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.platform_core.api.request_meta import client_ip, user_agent
from backend.apps.secondary_market.api.serializers import (
    SecondaryMarketBuyerListingSerializer,
    SecondaryMarketListingApproveRequestSerializer,
    SecondaryMarketListingCancelRequestSerializer,
    SecondaryMarketListingCreateRequestSerializer,
    SecondaryMarketListingListQuerySerializer,
    SecondaryMarketListingRejectRequestSerializer,
    SecondaryMarketListingRemoveRequestSerializer,
    SecondaryMarketListingSerializer,
    SecondaryMarketPurchaseRequestSerializer,
    SecondaryMarketPurchaseSerializer,
    serialize_secondary_buyer_listing,
    serialize_secondary_listing,
    serialize_secondary_purchase,
)
from backend.apps.secondary_market.services import (
    ApproveSecondaryMarketListingCommand,
    CancelSecondaryMarketListingCommand,
    CreateSecondaryMarketListingCommand,
    PurchaseSecondaryMarketListingCommand,
    RejectSecondaryMarketListingCommand,
    RemoveSecondaryMarketListingCommand,
    SecondaryMarketAuthorizationError,
    SecondaryMarketValidationError,
    approve_secondary_market_listing,
    cancel_secondary_market_listing,
    create_secondary_market_listing,
    list_active_secondary_market_listings,
    purchase_secondary_market_listing,
    reject_secondary_market_listing,
    remove_secondary_market_listing,
)


def _error_response(exc: Exception) -> Response:
    status_code = (
        status.HTTP_403_FORBIDDEN
        if isinstance(exc, SecondaryMarketAuthorizationError)
        else status.HTTP_400_BAD_REQUEST
    )
    return Response({"detail": str(exc)}, status=status_code)


class SecondaryMarketListingListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[SecondaryMarketListingListQuerySerializer],
        responses={200: SecondaryMarketBuyerListingSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        serializer = SecondaryMarketListingListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            listings = list_active_secondary_market_listings(
                actor=cast(Model, request.user),
                limit=data["limit"],
            )
        except (SecondaryMarketAuthorizationError, SecondaryMarketValidationError) as exc:
            return _error_response(exc)
        return Response(
            [serialize_secondary_buyer_listing(listing) for listing in listings],
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=SecondaryMarketListingCreateRequestSerializer,
        responses={201: SecondaryMarketListingSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = SecondaryMarketListingCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            listing = create_secondary_market_listing(
                CreateSecondaryMarketListingCommand(
                    actor=cast(Model, request.user),
                    holding_id=str(data["holding_id"]),
                    price_bps=data["price_bps"],
                    document_acceptance_id=str(data["document_acceptance_id"]),
                    idempotency_key=data["idempotency_key"],
                    sensitive_action_code_id=str(data["sensitive_action_code_id"]),
                    sensitive_action_code=data["sensitive_action_code"],
                    notes=data.get("notes", ""),
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except (SecondaryMarketAuthorizationError, SecondaryMarketValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_secondary_listing(listing), status=status.HTTP_201_CREATED)


class SecondaryMarketListingApproveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SecondaryMarketListingApproveRequestSerializer,
        responses={200: SecondaryMarketListingSerializer},
    )
    def post(self, request: Request, listing_id: str) -> Response:
        serializer = SecondaryMarketListingApproveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            listing = approve_secondary_market_listing(
                ApproveSecondaryMarketListingCommand(
                    actor=cast(Model, request.user),
                    listing_id=listing_id,
                    reason=data["reason"],
                    disclosure_note=data["disclosure_note"],
                    idempotency_key=data["idempotency_key"],
                )
            )
        except (SecondaryMarketAuthorizationError, SecondaryMarketValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_secondary_listing(listing), status=status.HTTP_200_OK)


class SecondaryMarketListingRejectView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SecondaryMarketListingRejectRequestSerializer,
        responses={200: SecondaryMarketListingSerializer},
    )
    def post(self, request: Request, listing_id: str) -> Response:
        serializer = SecondaryMarketListingRejectRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            listing = reject_secondary_market_listing(
                RejectSecondaryMarketListingCommand(
                    actor=cast(Model, request.user),
                    listing_id=listing_id,
                    reason=data["reason"],
                    idempotency_key=data["idempotency_key"],
                )
            )
        except (SecondaryMarketAuthorizationError, SecondaryMarketValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_secondary_listing(listing), status=status.HTTP_200_OK)


class SecondaryMarketListingRemoveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SecondaryMarketListingRemoveRequestSerializer,
        responses={200: SecondaryMarketListingSerializer},
    )
    def post(self, request: Request, listing_id: str) -> Response:
        serializer = SecondaryMarketListingRemoveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            listing = remove_secondary_market_listing(
                RemoveSecondaryMarketListingCommand(
                    actor=cast(Model, request.user),
                    listing_id=listing_id,
                    reason=data["reason"],
                    idempotency_key=data["idempotency_key"],
                )
            )
        except (SecondaryMarketAuthorizationError, SecondaryMarketValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_secondary_listing(listing), status=status.HTTP_200_OK)


class SecondaryMarketListingCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SecondaryMarketListingCancelRequestSerializer,
        responses={200: SecondaryMarketListingSerializer},
    )
    def post(self, request: Request, listing_id: str) -> Response:
        serializer = SecondaryMarketListingCancelRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            listing = cancel_secondary_market_listing(
                CancelSecondaryMarketListingCommand(
                    actor=cast(Model, request.user),
                    listing_id=listing_id,
                    reason=data["reason"],
                    idempotency_key=data["idempotency_key"],
                )
            )
        except (SecondaryMarketAuthorizationError, SecondaryMarketValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_secondary_listing(listing), status=status.HTTP_200_OK)


class SecondaryMarketListingPurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SecondaryMarketPurchaseRequestSerializer,
        responses={201: SecondaryMarketPurchaseSerializer},
    )
    def post(self, request: Request, listing_id: str) -> Response:
        serializer = SecondaryMarketPurchaseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            purchase = purchase_secondary_market_listing(
                PurchaseSecondaryMarketListingCommand(
                    actor=cast(Model, request.user),
                    listing_id=listing_id,
                    document_acceptance_id=str(data["document_acceptance_id"]),
                    risk_acknowledgement_accepted=data["risk_acknowledgement_accepted"],
                    idempotency_key=data["idempotency_key"],
                    sensitive_action_code_id=str(data["sensitive_action_code_id"]),
                    sensitive_action_code=data["sensitive_action_code"],
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except (SecondaryMarketAuthorizationError, SecondaryMarketValidationError) as exc:
            return _error_response(exc)
        return Response(serialize_secondary_purchase(purchase), status=status.HTTP_201_CREATED)
