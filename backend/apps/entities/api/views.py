from __future__ import annotations

from typing import Any, cast

from django.db.models import Model, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.entities.api.serializers import (
    BorrowerDocumentCreateRequestSerializer,
    BorrowerDocumentSerializer,
    BorrowerEntityCreateRequestSerializer,
    BorrowerEntityEventSerializer,
    BorrowerEntityListQuerySerializer,
    BorrowerEntitySerializer,
    BorrowerEntityUpdateRequestSerializer,
    BorrowerInvestorDisclosureSerializer,
    serialize_borrower_document,
    serialize_borrower_entity,
    serialize_borrower_event,
)
from backend.apps.entities.models import BorrowerEntity
from backend.apps.entities.services import (
    AddBorrowerDocumentCommand,
    BorrowerAuthorizationError,
    BorrowerValidationError,
    CreateBorrowerEntityCommand,
    UpdateBorrowerEntityCommand,
    add_borrower_document,
    borrower_investor_disclosure,
    create_borrower_entity,
    update_borrower_entity,
)
from backend.apps.platform_core.domain.access import is_admin_actor


def _admin_forbidden_response() -> Response:
    return Response(
        {"detail": "Only an active admin can manage borrower entities."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _borrower_queryset_from_query(data: dict[str, Any]) -> QuerySet[BorrowerEntity]:
    queryset = BorrowerEntity.objects.all()
    for field in ("kyb_status", "entity_type", "country"):
        if data.get(field):
            queryset = queryset.filter(**{field: data[field]})
    if "compliance_hold" in data:
        queryset = queryset.filter(compliance_hold=data["compliance_hold"])
    if data.get("q"):
        query = data["q"]
        queryset = queryset.filter(legal_name__icontains=query)
    return queryset


class BorrowerEntityListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[BorrowerEntityListQuerySerializer],
        responses={200: BorrowerEntitySerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = BorrowerEntityListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        borrowers = _borrower_queryset_from_query(data)
        return Response(
            [serialize_borrower_entity(borrower) for borrower in borrowers[: data["limit"]]],
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=BorrowerEntityCreateRequestSerializer,
        responses={201: BorrowerEntitySerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = BorrowerEntityCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            borrower = create_borrower_entity(
                CreateBorrowerEntityCommand(
                    actor=cast(Model, request.user),
                    legal_name=data["legal_name"],
                    year_founded=data["year_founded"],
                    entity_type=data["entity_type"],
                    kyb_status=data["kyb_status"],
                    compliance_hold=data["compliance_hold"],
                    country=data.get("country", ""),
                    registration_number=data.get("registration_number", ""),
                    registered_address=data.get("registered_address", ""),
                    operating_address=data.get("operating_address", ""),
                    industry_activity=data.get("industry_activity", ""),
                    ownership_structure=data.get("ownership_structure", ""),
                    beneficial_owners=data.get("beneficial_owners"),
                    directors_officers=data.get("directors_officers"),
                    authorized_signatories=data.get("authorized_signatories"),
                    bank_account_details=data.get("bank_account_details"),
                    financials_currency=data.get("financials_currency", ""),
                    assets_minor=data.get("assets_minor"),
                    liabilities_minor=data.get("liabilities_minor"),
                    revenue_last_year_minor=data.get("revenue_last_year_minor"),
                    profit_last_year_minor=data.get("profit_last_year_minor"),
                    note=data.get("note", ""),
                    evidence_summary=data.get("evidence_summary", ""),
                )
            )
        except BorrowerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except BorrowerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_borrower_entity(borrower), status=status.HTTP_201_CREATED)


class BorrowerEntityDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: BorrowerEntitySerializer})
    def get(self, request: Request, borrower_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        borrower = BorrowerEntity.objects.filter(id=borrower_id).first()
        if borrower is None:
            return Response(
                {"detail": "Borrower entity does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(serialize_borrower_entity(borrower), status=status.HTTP_200_OK)

    @extend_schema(
        request=BorrowerEntityUpdateRequestSerializer,
        responses={200: BorrowerEntitySerializer},
    )
    def patch(self, request: Request, borrower_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = BorrowerEntityUpdateRequestSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            borrower = update_borrower_entity(
                UpdateBorrowerEntityCommand(
                    actor=cast(Model, request.user),
                    borrower_id=borrower_id,
                    legal_name=data.get("legal_name"),
                    year_founded=data.get("year_founded"),
                    entity_type=data.get("entity_type"),
                    kyb_status=data.get("kyb_status"),
                    compliance_hold=data.get("compliance_hold"),
                    country=data.get("country"),
                    registration_number=data.get("registration_number"),
                    registered_address=data.get("registered_address"),
                    operating_address=data.get("operating_address"),
                    industry_activity=data.get("industry_activity"),
                    ownership_structure=data.get("ownership_structure"),
                    beneficial_owners=data.get("beneficial_owners"),
                    directors_officers=data.get("directors_officers"),
                    authorized_signatories=data.get("authorized_signatories"),
                    bank_account_details=data.get("bank_account_details"),
                    financials_currency=data.get("financials_currency"),
                    assets_minor=data.get("assets_minor"),
                    liabilities_minor=data.get("liabilities_minor"),
                    revenue_last_year_minor=data.get("revenue_last_year_minor"),
                    profit_last_year_minor=data.get("profit_last_year_minor"),
                    clear_assets=bool(data.get("clear_assets", False)),
                    clear_liabilities=bool(data.get("clear_liabilities", False)),
                    clear_revenue_last_year=bool(data.get("clear_revenue_last_year", False)),
                    clear_profit_last_year=bool(data.get("clear_profit_last_year", False)),
                    note=data.get("note", ""),
                    evidence_summary=data.get("evidence_summary", ""),
                )
            )
        except BorrowerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except BorrowerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_borrower_entity(borrower), status=status.HTTP_200_OK)


class BorrowerDocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: BorrowerDocumentSerializer(many=True)})
    def get(self, request: Request, borrower_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        borrower = BorrowerEntity.objects.filter(id=borrower_id).first()
        if borrower is None:
            return Response(
                {"detail": "Borrower entity does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            [serialize_borrower_document(document) for document in borrower.documents.all()],
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=BorrowerDocumentCreateRequestSerializer,
        responses={201: BorrowerDocumentSerializer},
    )
    def post(self, request: Request, borrower_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = BorrowerDocumentCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            document = add_borrower_document(
                AddBorrowerDocumentCommand(
                    actor=cast(Model, request.user),
                    borrower_id=borrower_id,
                    stored_file_id=str(data["stored_file_id"]),
                    document_type=data["document_type"],
                    display_name=data["display_name"],
                    description=data.get("description", ""),
                    investor_visible=data["investor_visible"],
                    note=data.get("note", ""),
                )
            )
        except BorrowerAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except BorrowerValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_borrower_document(document), status=status.HTTP_201_CREATED)


class BorrowerEventListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: BorrowerEntityEventSerializer(many=True)})
    def get(self, request: Request, borrower_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        borrower = BorrowerEntity.objects.filter(id=borrower_id).first()
        if borrower is None:
            return Response(
                {"detail": "Borrower entity does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            [serialize_borrower_event(event) for event in borrower.events.all()],
            status=status.HTTP_200_OK,
        )


class BorrowerInvestorDisclosurePreviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: BorrowerInvestorDisclosureSerializer})
    def get(self, request: Request, borrower_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        borrower = BorrowerEntity.objects.filter(id=borrower_id).first()
        if borrower is None:
            return Response(
                {"detail": "Borrower entity does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(borrower_investor_disclosure(borrower), status=status.HTTP_200_OK)
