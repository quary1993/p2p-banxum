from __future__ import annotations

from typing import Any, cast

from django.db.models import Model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.originator_claims.api.serializers import (
    LoanOriginatorCreateSerializer,
    LoanOriginatorSerializer,
    LoanOriginatorUpdateSerializer,
    OriginatorAdminLoanDetailResponseSerializer,
    OriginatorBorrowerRepaymentRequestSerializer,
    OriginatorBorrowerRepaymentResponseSerializer,
    OriginatorClaimPurchaseRequestSerializer,
    OriginatorClaimPurchaseResponseSerializer,
    OriginatorClaimQuoteRequestSerializer,
    OriginatorClaimQuoteResponseSerializer,
    OriginatorLoanCreateSerializer,
    OriginatorLoanHoldSerializer,
    OriginatorLoanProfileResponseSerializer,
    OriginatorLoanPublishSerializer,
    OriginatorSettlementQueueRowSerializer,
    OriginatorSettlementRequestSerializer,
    OriginatorSettlementResponseSerializer,
)
from backend.apps.originator_claims.services import (
    CreateLoanOriginatorCommand,
    CreateOriginatorClaimQuoteCommand,
    CreateOriginatorLoanCommand,
    FinalizeOriginatorSettlementCommand,
    HoldOriginatorLoanCommand,
    OriginatorClaimsAuthorizationError,
    OriginatorClaimsValidationError,
    PublishOriginatorLoanCommand,
    PurchaseOriginatorClaimCommand,
    RecordOriginatorBorrowerRepaymentCommand,
    UpdateLoanOriginatorCommand,
    create_loan_originator,
    create_originator_claim_quote,
    create_originator_loan,
    finalize_originator_settlement,
    get_originator_admin_loan_payload,
    list_loan_originators,
    list_outstanding_originator_settlements,
    place_originator_loan_on_hold,
    publish_originator_loan,
    purchase_originator_claim,
    record_originator_borrower_repayment,
    replace_originator_loan_draft,
    update_loan_originator,
)
from backend.apps.platform_core.api.request_meta import client_ip, user_agent


def _error_response(exc: Exception) -> Response:
    response_status = (
        status.HTTP_403_FORBIDDEN
        if isinstance(exc, OriginatorClaimsAuthorizationError)
        else status.HTTP_400_BAD_REQUEST
    )
    return Response({"detail": str(exc)}, status=response_status)


def _actor(request: Request) -> Model:
    """Return the authenticated actor after DRF permission enforcement."""
    return cast(Model, request.user)


class OriginatorListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="originator_claims_admin_originators_list",
        parameters=[
            OpenApiParameter(
                name="query",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                    "Case-insensitive search over legal name, public name, and registration number."
                ),
            )
        ],
        responses={200: LoanOriginatorSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        try:
            queryset = list_loan_originators(
                actor=_actor(request),
                query=str(request.query_params.get("query", "")),
            )
        except OriginatorClaimsAuthorizationError as exc:
            return _error_response(exc)
        return Response(LoanOriginatorSerializer(queryset, many=True).data)

    @extend_schema(
        operation_id="originator_claims_admin_originators_create",
        request=LoanOriginatorCreateSerializer,
        responses={201: LoanOriginatorSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = LoanOriginatorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            originator = create_loan_originator(
                CreateLoanOriginatorCommand(actor=_actor(request), **data)
            )
        except (OriginatorClaimsAuthorizationError, OriginatorClaimsValidationError) as exc:
            return _error_response(exc)
        return Response(LoanOriginatorSerializer(originator).data, status=status.HTTP_201_CREATED)


class OriginatorDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="originator_claims_admin_originators_retrieve",
        responses={200: LoanOriginatorSerializer},
    )
    def get(self, request: Request, originator_id: Any) -> Response:
        try:
            queryset = list_loan_originators(actor=_actor(request))
        except OriginatorClaimsAuthorizationError as exc:
            return _error_response(exc)
        originator = get_object_or_404(queryset, id=originator_id)
        return Response(LoanOriginatorSerializer(originator).data)

    @extend_schema(
        operation_id="originator_claims_admin_originators_update",
        request=LoanOriginatorUpdateSerializer,
        responses={200: LoanOriginatorSerializer},
    )
    def patch(self, request: Request, originator_id: Any) -> Response:
        serializer = LoanOriginatorUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            originator = update_loan_originator(
                UpdateLoanOriginatorCommand(
                    actor=_actor(request),
                    originator_id=str(originator_id),
                    changes=dict(serializer.validated_data),
                )
            )
        except (OriginatorClaimsAuthorizationError, OriginatorClaimsValidationError) as exc:
            return _error_response(exc)
        return Response(LoanOriginatorSerializer(originator).data)


def _profile_payload(profile: Any) -> dict[str, Any]:
    return {
        "loan_id": str(profile.loan_id),
        "originator_id": str(profile.originator_id),
        "originator_name": profile.originator.public_name,
        "opportunity_status": profile.opportunity_status,
        "target_yield_bps": profile.target_yield_bps,
        "minimum_investment_minor": profile.minimum_investment_minor,
        "premium_fee_bps": profile.premium_fee_bps,
        "current_outstanding_principal_minor": profile.current_outstanding_principal_minor,
        "unsold_principal_minor": profile.unsold_principal_minor,
        "maturity_date": profile.maturity_date,
        "schedule_revision": profile.schedule_revision,
        "borrower_display_name": profile.borrower_display_name,
        "is_on_hold": profile.is_on_hold,
        "hold_reason": profile.hold_reason,
    }


class OriginatorLoanCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="originator_claims_admin_loans_create",
        request=OriginatorLoanCreateSerializer,
        responses={201: OriginatorLoanProfileResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = OriginatorLoanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = create_originator_loan(
                CreateOriginatorLoanCommand(
                    actor=_actor(request),
                    originator_id=str(data.pop("originator_id")),
                    **data,
                )
            )
        except (OriginatorClaimsAuthorizationError, OriginatorClaimsValidationError) as exc:
            return _error_response(exc)
        payload = _profile_payload(result.profile)
        payload["import_id"] = str(result.loan_import.id)
        return Response(payload, status=status.HTTP_201_CREATED)


class OriginatorLoanDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="originator_claims_admin_loans_retrieve",
        responses={200: OriginatorAdminLoanDetailResponseSerializer},
    )
    def get(self, request: Request, loan_id: Any) -> Response:
        try:
            payload = get_originator_admin_loan_payload(
                actor=_actor(request),
                loan_id=str(loan_id),
            )
        except (OriginatorClaimsAuthorizationError, OriginatorClaimsValidationError) as exc:
            return _error_response(exc)
        return Response(payload)

    @extend_schema(
        operation_id="originator_claims_admin_loans_update",
        request=OriginatorLoanCreateSerializer,
        responses={200: OriginatorLoanProfileResponseSerializer},
    )
    def patch(self, request: Request, loan_id: Any) -> Response:
        serializer = OriginatorLoanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = replace_originator_loan_draft(
                loan_id=str(loan_id),
                command=CreateOriginatorLoanCommand(
                    actor=_actor(request),
                    originator_id=str(data.pop("originator_id")),
                    **data,
                ),
            )
        except (OriginatorClaimsAuthorizationError, OriginatorClaimsValidationError) as exc:
            return _error_response(exc)
        payload = _profile_payload(result.profile)
        payload["import_id"] = str(result.loan_import.id)
        return Response(payload)


class OriginatorLoanPublishView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="originator_claims_admin_loans_publish",
        request=OriginatorLoanPublishSerializer,
        responses={200: OriginatorLoanProfileResponseSerializer},
    )
    def post(self, request: Request, loan_id: Any) -> Response:
        serializer = OriginatorLoanPublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            profile = publish_originator_loan(
                PublishOriginatorLoanCommand(
                    actor=_actor(request),
                    loan_id=str(loan_id),
                    as_of_date=serializer.validated_data["as_of_date"],
                )
            )
        except (OriginatorClaimsAuthorizationError, OriginatorClaimsValidationError) as exc:
            return _error_response(exc)
        return Response(_profile_payload(profile))


class OriginatorLoanHoldView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="originator_claims_admin_loans_hold",
        request=OriginatorLoanHoldSerializer,
        responses={200: OriginatorLoanProfileResponseSerializer},
    )
    def post(self, request: Request, loan_id: Any) -> Response:
        serializer = OriginatorLoanHoldSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            profile = place_originator_loan_on_hold(
                HoldOriginatorLoanCommand(
                    actor=_actor(request),
                    loan_id=str(loan_id),
                    reason=str(serializer.validated_data["reason"]),
                )
            )
        except (OriginatorClaimsAuthorizationError, OriginatorClaimsValidationError) as exc:
            return _error_response(exc)
        return Response(_profile_payload(profile))


class OriginatorClaimQuoteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="originator_claims_loans_quote_create",
        request=OriginatorClaimQuoteRequestSerializer,
        responses={200: OriginatorClaimQuoteResponseSerializer},
    )
    def post(self, request: Request, loan_id: Any) -> Response:
        serializer = OriginatorClaimQuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            quote = create_originator_claim_quote(
                CreateOriginatorClaimQuoteCommand(
                    actor=_actor(request),
                    loan_id=str(loan_id),
                    requested_cash_minor=serializer.validated_data["requested_cash_minor"],
                )
            )
        except (OriginatorClaimsAuthorizationError, OriginatorClaimsValidationError) as exc:
            return _error_response(exc)
        return Response(
            {
                "quote_id": str(quote.id),
                "loan_id": str(quote.loan_profile.loan_id),
                "currency": quote.currency_id,
                "requested_cash_minor": quote.requested_cash_minor,
                "executable_cash_minor": quote.executable_cash_minor,
                "assigned_principal_minor": quote.assigned_principal_minor,
                "outstanding_principal_at_pricing_minor": (
                    quote.outstanding_principal_at_pricing_minor
                ),
                "share_ppm": quote.share_ppm,
                "target_yield_bps": quote.target_yield_bps,
                "premium_discount_minor": quote.premium_discount_minor,
                "rounding_remainder_minor": quote.rounding_remainder_minor,
                "entitlement_start_at": quote.entitlement_start_at,
                "expires_at": quote.expires_at,
                "cash_flows": quote.cash_flows,
            }
        )


class OriginatorClaimPurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="originator_claims_quotes_purchase_create",
        request=OriginatorClaimPurchaseRequestSerializer,
        responses={201: OriginatorClaimPurchaseResponseSerializer},
    )
    def post(self, request: Request, quote_id: Any) -> Response:
        serializer = OriginatorClaimPurchaseRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            purchase = purchase_originator_claim(
                PurchaseOriginatorClaimCommand(
                    actor=_actor(request),
                    quote_id=str(quote_id),
                    document_acceptance_id=str(data["document_acceptance_id"]),
                    sensitive_action_code_id=str(data["sensitive_action_code_id"]),
                    sensitive_action_code=str(data["sensitive_action_code"]),
                    idempotency_key=str(data["idempotency_key"]),
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except (OriginatorClaimsAuthorizationError, OriginatorClaimsValidationError) as exc:
            return _error_response(exc)
        return Response(
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
            },
            status=status.HTTP_201_CREATED,
        )


class OriginatorSettlementQueueView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="originator_claims_admin_settlements_outstanding_list",
        responses={200: OriginatorSettlementQueueRowSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        try:
            rows = list_outstanding_originator_settlements(actor=_actor(request))
        except OriginatorClaimsAuthorizationError as exc:
            return _error_response(exc)
        return Response(rows)


class OriginatorBorrowerRepaymentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="originator_claims_admin_loan_repayments_create",
        request=OriginatorBorrowerRepaymentRequestSerializer,
        responses={201: OriginatorBorrowerRepaymentResponseSerializer},
    )
    def post(self, request: Request, loan_id: Any) -> Response:
        serializer = OriginatorBorrowerRepaymentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            repayment = record_originator_borrower_repayment(
                RecordOriginatorBorrowerRepaymentCommand(
                    actor=_actor(request),
                    loan_id=str(loan_id),
                    **data,
                )
            )
        except (OriginatorClaimsAuthorizationError, OriginatorClaimsValidationError) as exc:
            return _error_response(exc)
        return Response(
            {
                "repayment_id": str(repayment.id),
                "loan_id": str(repayment.loan_profile.loan_id),
                "payment_reference": repayment.payment_reference,
                "currency": repayment.currency_id,
                "amount_minor": repayment.amount_minor,
                "principal_minor": repayment.principal_minor,
                "interest_minor": repayment.interest_minor,
                "penalty_minor": repayment.penalty_minor,
                "fee_minor": repayment.fee_minor,
                "investor_distributed_minor": repayment.investor_distributed_minor,
                "originator_payable_minor": repayment.originator_payable_minor,
                "principal_after_minor": repayment.principal_after_minor,
                "schedule_revision": repayment.loan_profile.schedule_revision,
            },
            status=status.HTTP_201_CREATED,
        )


class OriginatorSettlementCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="originator_claims_admin_settlements_create",
        request=OriginatorSettlementRequestSerializer,
        responses={201: OriginatorSettlementResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = OriginatorSettlementRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            settlement = finalize_originator_settlement(
                FinalizeOriginatorSettlementCommand(
                    actor=_actor(request),
                    originator_id=str(data["originator_id"]),
                    currency=str(data["currency"]),
                    purchase_ids=[str(item) for item in data["purchase_ids"]],
                    repayment_ids=[str(item) for item in data["repayment_ids"]],
                    booking_date=data["booking_date"],
                    value_date=data["value_date"],
                    collection_account_identifier=str(data["collection_account_identifier"]),
                    bank_reference=str(data.get("bank_reference", "")),
                    payment_reference=str(data.get("payment_reference", "")),
                    evidence_reference=str(data.get("evidence_reference", "")),
                    notes=str(data.get("notes", "")),
                    idempotency_key=str(data["idempotency_key"]),
                )
            )
        except (OriginatorClaimsAuthorizationError, OriginatorClaimsValidationError) as exc:
            return _error_response(exc)
        return Response(
            {
                "settlement_id": str(settlement.id),
                "originator_id": str(settlement.originator_id),
                "currency": settlement.currency_id,
                "amount_minor": settlement.amount_minor,
                "purchase_count": settlement.purchase_count,
                "repayment_count": settlement.repayment_count,
                "purchase_amount_minor": settlement.purchase_amount_minor,
                "servicing_amount_minor": settlement.servicing_amount_minor,
                "bank_operation_id": str(settlement.bank_operation_id),
                "journal_entry_id": str(settlement.journal_entry_id),
                "settled_at": settlement.settled_at,
            },
            status=status.HTTP_201_CREATED,
        )
