from __future__ import annotations

from typing import Any, cast

from django.db import models
from django.db.models import Model, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.entities import credit_file
from backend.apps.entities.api.serializers import (
    BorrowerDebtFacilityListSerializer,
    BorrowerDebtFacilityRequestSerializer,
    BorrowerDebtFacilitySerializer,
    BorrowerDocumentCreateRequestSerializer,
    BorrowerDocumentMetadataRequestSerializer,
    BorrowerDocumentSerializer,
    BorrowerEntityCreateRequestSerializer,
    BorrowerEntityEventSerializer,
    BorrowerEntityListQuerySerializer,
    BorrowerEntitySerializer,
    BorrowerEntityUpdateRequestSerializer,
    BorrowerExternalDebtEndRequestSerializer,
    BorrowerExternalDebtRequestSerializer,
    BorrowerFinancialYearListSerializer,
    BorrowerFinancialYearRequestSerializer,
    BorrowerFinancialYearSerializer,
    BorrowerInvestorDisclosureSerializer,
    CreditFileMoveRequestSerializer,
    SnbReferenceRateSerializer,
    SwissCreditorModeOverviewSerializer,
    SwissCreditorModeRequestSerializer,
    serialize_borrower_document,
    serialize_borrower_entity,
    serialize_borrower_event,
)
from backend.apps.entities.creditor_regime import (
    RecordExternalDebtCommand,
    SetCreditorModeCommand,
    creditor_mode_overview,
    end_external_debt,
    record_external_debt,
    record_snb_rate,
    set_creditor_mode,
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
from backend.apps.platform_core.models import SnbReferenceRate


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
        queryset = queryset.filter(
            models.Q(legal_name__icontains=query)
            | models.Q(registration_number__icontains=query)
            | models.Q(country__icontains=query)
            | models.Q(business_classification__icontains=query)
            | models.Q(registered_address__icontains=query)
            | models.Q(contact_info__icontains=query)
        )
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
                    city=data.get("city", ""),
                    employees=data.get("employees"),
                    employees_year=data.get("employees_year"),
                    registration_number=data.get("registration_number", ""),
                    uid=data.get("uid", ""),
                    business_classification=data.get("business_classification", ""),
                    business_classification_public=data.get(
                        "business_classification_public", False
                    ),
                    registered_address=data.get("registered_address", ""),
                    registered_address_public=data.get("registered_address_public", False),
                    operating_address=data.get("operating_address", ""),
                    contact_info=data.get("contact_info", ""),
                    contact_info_public=data.get("contact_info_public", False),
                    industry_activity=data.get("industry_activity", ""),
                    ownership_structure=data.get("ownership_structure", ""),
                    beneficial_owners=data.get("beneficial_owners"),
                    directors_officers=data.get("directors_officers"),
                    authorized_signatories=data.get("authorized_signatories"),
                    bank_account_details=data.get("bank_account_details"),
                    kyb_aml_observations=data.get("kyb_aml_observations", ""),
                    financial_risk=data.get("financial_risk", ""),
                    financials_currency=data.get("financials_currency", ""),
                    assets_minor=data.get("assets_minor"),
                    liabilities_minor=data.get("liabilities_minor"),
                    revenue_last_year_minor=data.get("revenue_last_year_minor"),
                    profit_last_year_minor=data.get("profit_last_year_minor"),
                    investor_story=data.get("investor_story"),
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
                    city=data.get("city"),
                    employees=data.get("employees"),
                    employees_year=data.get("employees_year"),
                    clear_employees=bool(data.get("clear_employees", False)),
                    registration_number=data.get("registration_number"),
                    uid=data.get("uid"),
                    business_classification=data.get("business_classification"),
                    business_classification_public=data.get("business_classification_public"),
                    registered_address=data.get("registered_address"),
                    registered_address_public=data.get("registered_address_public"),
                    operating_address=data.get("operating_address"),
                    contact_info=data.get("contact_info"),
                    contact_info_public=data.get("contact_info_public"),
                    industry_activity=data.get("industry_activity"),
                    ownership_structure=data.get("ownership_structure"),
                    beneficial_owners=data.get("beneficial_owners"),
                    directors_officers=data.get("directors_officers"),
                    authorized_signatories=data.get("authorized_signatories"),
                    bank_account_details=data.get("bank_account_details"),
                    kyb_aml_observations=data.get("kyb_aml_observations"),
                    financial_risk=data.get("financial_risk"),
                    financials_currency=data.get("financials_currency"),
                    assets_minor=data.get("assets_minor"),
                    liabilities_minor=data.get("liabilities_minor"),
                    revenue_last_year_minor=data.get("revenue_last_year_minor"),
                    profit_last_year_minor=data.get("profit_last_year_minor"),
                    investor_story=data.get("investor_story"),
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


def _credit_file_error(exc: Exception) -> Response:
    if isinstance(exc, credit_file.CreditFileAuthorizationError):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _financial_year_command(
    request: Request, borrower_id: str, financial_year_id: str | None
) -> credit_file.SaveFinancialYearCommand:
    serializer = BorrowerFinancialYearRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data: dict[str, Any] = serializer.validated_data
    return credit_file.SaveFinancialYearCommand(
        actor=cast(Model, request.user),
        borrower_id=str(borrower_id),
        financial_year_id=financial_year_id,
        year=data["year"],
        period_end=data["period_end"],
        currency=data["currency"],
        amounts=dict(data["amounts"]),
        source_document_id=str(data["source_document_id"]) if data["source_document_id"] else None,
    )


class BorrowerFinancialYearListView(APIView):
    """U33-DEC-20: the borrower's financial years (GET) or record one (POST)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: BorrowerFinancialYearListSerializer})
    def get(self, request: Request, borrower_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            rows = credit_file.list_financial_years(
                actor=cast(Model, request.user), borrower_id=str(borrower_id)
            )
        except credit_file.CreditFileError as exc:
            return _credit_file_error(exc)
        return Response({"financial_years": rows})

    @extend_schema(
        request=BorrowerFinancialYearRequestSerializer,
        responses={201: BorrowerFinancialYearSerializer},
    )
    def post(self, request: Request, borrower_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            row = credit_file.save_financial_year(
                _financial_year_command(request, borrower_id, None)
            )
        except credit_file.CreditFileError as exc:
            return _credit_file_error(exc)
        return Response(row, status=status.HTTP_201_CREATED)


class BorrowerFinancialYearDetailView(APIView):
    """U33-DEC-20: change (PUT) or remove (DELETE) a financial year."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=BorrowerFinancialYearRequestSerializer,
        responses={200: BorrowerFinancialYearSerializer},
    )
    def put(self, request: Request, borrower_id: str, financial_year_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            row = credit_file.save_financial_year(
                _financial_year_command(request, borrower_id, str(financial_year_id))
            )
        except credit_file.CreditFileError as exc:
            return _credit_file_error(exc)
        return Response(row)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request: Request, borrower_id: str, financial_year_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            credit_file.remove_financial_year(
                actor=cast(Model, request.user),
                borrower_id=str(borrower_id),
                financial_year_id=str(financial_year_id),
            )
        except credit_file.CreditFileError as exc:
            return _credit_file_error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _debt_facility_command(
    request: Request, borrower_id: str, facility_id: str | None
) -> credit_file.SaveDebtFacilityCommand:
    serializer = BorrowerDebtFacilityRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data: dict[str, Any] = serializer.validated_data
    return credit_file.SaveDebtFacilityCommand(
        actor=cast(Model, request.user),
        borrower_id=str(borrower_id),
        facility_id=facility_id,
        facility_type=data["facility_type"],
        currency=data["currency"],
        balance_minor=data["balance_minor"],
        current_portion_minor=data["current_portion_minor"],
        security_description=data["security_description"],
        as_at=data["as_at"],
        source_document_id=str(data["source_document_id"]) if data["source_document_id"] else None,
    )


class BorrowerDebtFacilityListView(APIView):
    """U33-DEC-20: the borrower's existing debt (GET) or add a facility (POST)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: BorrowerDebtFacilityListSerializer})
    def get(self, request: Request, borrower_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            rows = credit_file.list_debt_facilities(
                actor=cast(Model, request.user), borrower_id=str(borrower_id)
            )
        except credit_file.CreditFileError as exc:
            return _credit_file_error(exc)
        return Response({"debt_facilities": rows})

    @extend_schema(
        request=BorrowerDebtFacilityRequestSerializer,
        responses={201: BorrowerDebtFacilitySerializer},
    )
    def post(self, request: Request, borrower_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            row = credit_file.save_debt_facility(_debt_facility_command(request, borrower_id, None))
        except credit_file.CreditFileError as exc:
            return _credit_file_error(exc)
        return Response(row, status=status.HTTP_201_CREATED)


class BorrowerDebtFacilityMoveView(APIView):
    """U33-DEC-20: move a facility one place up or down."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=CreditFileMoveRequestSerializer,
        responses={200: BorrowerDebtFacilityListSerializer},
    )
    def post(self, request: Request, borrower_id: str, facility_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = CreditFileMoveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            rows = credit_file.move_debt_facility(
                actor=cast(Model, request.user),
                borrower_id=str(borrower_id),
                facility_id=str(facility_id),
                direction=serializer.validated_data["direction"],
            )
        except credit_file.CreditFileError as exc:
            return _credit_file_error(exc)
        return Response({"debt_facilities": rows})


class BorrowerDebtFacilityDetailView(APIView):
    """U33-DEC-20: change (PUT) or remove (DELETE) a facility."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=BorrowerDebtFacilityRequestSerializer,
        responses={200: BorrowerDebtFacilitySerializer},
    )
    def put(self, request: Request, borrower_id: str, facility_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            row = credit_file.save_debt_facility(
                _debt_facility_command(request, borrower_id, str(facility_id))
            )
        except credit_file.CreditFileError as exc:
            return _credit_file_error(exc)
        return Response(row)

    @extend_schema(request=None, responses={204: None})
    def delete(self, request: Request, borrower_id: str, facility_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        try:
            credit_file.remove_debt_facility(
                actor=cast(Model, request.user),
                borrower_id=str(borrower_id),
                facility_id=str(facility_id),
            )
        except credit_file.CreditFileError as exc:
            return _credit_file_error(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BorrowerDocumentMetadataView(APIView):
    """U33-DEC-20: set the library metadata of a borrower document."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=BorrowerDocumentMetadataRequestSerializer,
        responses={200: BorrowerDocumentSerializer},
    )
    def post(self, request: Request, borrower_id: str, document_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = BorrowerDocumentMetadataRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            document = credit_file.set_document_metadata(
                credit_file.DocumentMetadataCommand(
                    actor=cast(Model, request.user),
                    borrower_id=str(borrower_id),
                    document_id=str(document_id),
                    **data,
                )
            )
        except credit_file.CreditFileError as exc:
            return _credit_file_error(exc)
        return Response(serialize_borrower_document(document))


def _regime_error(exc: Exception) -> Response:
    code = (
        status.HTTP_403_FORBIDDEN
        if isinstance(exc, BorrowerAuthorizationError)
        else status.HTTP_400_BAD_REQUEST
    )
    return Response({"detail": str(exc)}, status=code)


class SwissCreditorModeView(APIView):
    """18.9: the creditor mode of a Swiss borrower UID (overview and change/confirm)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="entities_admin_creditor_mode_retrieve",
        responses={200: SwissCreditorModeOverviewSerializer},
    )
    def get(self, request: Request, uid: str) -> Response:
        try:
            payload = creditor_mode_overview(actor=cast(Model, request.user), uid=uid)
        except (BorrowerAuthorizationError, BorrowerValidationError) as exc:
            return _regime_error(exc)
        return Response(SwissCreditorModeOverviewSerializer(payload).data)

    @extend_schema(
        operation_id="entities_admin_creditor_mode_update",
        request=SwissCreditorModeRequestSerializer,
        responses={200: SwissCreditorModeOverviewSerializer},
    )
    def post(self, request: Request, uid: str) -> Response:
        serializer = SwissCreditorModeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            set_creditor_mode(
                SetCreditorModeCommand(
                    actor=cast(Model, request.user),
                    uid=uid,
                    mode=str(data["mode"]),
                    note=str(data.get("note", "")),
                )
            )
            payload = creditor_mode_overview(actor=cast(Model, request.user), uid=uid)
        except (BorrowerAuthorizationError, BorrowerValidationError) as exc:
            return _regime_error(exc)
        return Response(SwissCreditorModeOverviewSerializer(payload).data)


class BorrowerExternalDebtCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="entities_admin_external_debts_create",
        request=BorrowerExternalDebtRequestSerializer,
        responses={201: SwissCreditorModeOverviewSerializer},
    )
    def post(self, request: Request, uid: str) -> Response:
        serializer = BorrowerExternalDebtRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            record_external_debt(
                RecordExternalDebtCommand(
                    actor=cast(Model, request.user),
                    uid=uid,
                    creditor_name=str(data["creditor_name"]),
                    creditor_identification=str(data["creditor_identification"]),
                    creditor_is_bank=bool(data["creditor_is_bank"]),
                    financing_id=str(data["financing_id"]),
                    identical_terms_group=str(data.get("identical_terms_group", "")),
                    principal_minor=int(data["principal_minor"]),
                    currency=str(data["currency"]),
                    start_date=data["start_date"],
                    declaration_document_id=(
                        str(data["declaration_document_id"])
                        if data.get("declaration_document_id")
                        else None
                    ),
                    declaration_reference=str(data.get("declaration_reference", "")),
                    notes=str(data.get("notes", "")),
                )
            )
            payload = creditor_mode_overview(actor=cast(Model, request.user), uid=uid)
        except (BorrowerAuthorizationError, BorrowerValidationError) as exc:
            return _regime_error(exc)
        return Response(
            SwissCreditorModeOverviewSerializer(payload).data, status=status.HTTP_201_CREATED
        )


class BorrowerExternalDebtEndView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="entities_admin_external_debts_end",
        request=BorrowerExternalDebtEndRequestSerializer,
        responses={200: SwissCreditorModeOverviewSerializer},
    )
    def post(self, request: Request, debt_id: str) -> Response:
        serializer = BorrowerExternalDebtEndRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            debt = end_external_debt(
                actor=cast(Model, request.user),
                debt_id=str(debt_id),
                ended_on=serializer.validated_data["ended_on"],
            )
            payload = creditor_mode_overview(actor=cast(Model, request.user), uid=str(debt.uid))
        except (BorrowerAuthorizationError, BorrowerValidationError) as exc:
            return _regime_error(exc)
        return Response(SwissCreditorModeOverviewSerializer(payload).data)


class SnbReferenceRateListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="entities_admin_snb_rates_list",
        responses={200: SnbReferenceRateSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return Response({"detail": "Admin access required."}, status=403)
        rates = SnbReferenceRate.objects.order_by("-rate_date", "currency")[:60]
        return Response(SnbReferenceRateSerializer(rates, many=True).data)

    @extend_schema(
        operation_id="entities_admin_snb_rates_create",
        request=SnbReferenceRateSerializer,
        responses={201: SnbReferenceRateSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = SnbReferenceRateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            rate = record_snb_rate(
                actor=cast(Model, request.user),
                currency=str(data["currency"]),
                rate_date=data["rate_date"],
                chf_per_unit=str(data["chf_per_unit"]),
                source=str(data["source"]),
            )
        except (BorrowerAuthorizationError, BorrowerValidationError) as exc:
            return _regime_error(exc)
        return Response(SnbReferenceRateSerializer(rate).data, status=status.HTTP_201_CREATED)
