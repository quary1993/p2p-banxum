from __future__ import annotations

from django.urls import path

from backend.apps.entities.api.views import (
    BorrowerDebtFacilityDetailView,
    BorrowerDebtFacilityListView,
    BorrowerDebtFacilityMoveView,
    BorrowerDocumentListCreateView,
    BorrowerDocumentMetadataView,
    BorrowerEntityDetailView,
    BorrowerEntityListCreateView,
    BorrowerEventListView,
    BorrowerExternalDebtCreateView,
    BorrowerExternalDebtEndView,
    BorrowerFinancialYearDetailView,
    BorrowerFinancialYearListView,
    BorrowerInvestorDisclosurePreviewView,
    SnbReferenceRateListCreateView,
    SwissCreditorModeView,
)

urlpatterns = [
    # 18.9: Swiss creditor modes per borrower UID, external debts and SNB reference rates.
    path("admin/creditor-modes/<str:uid>/", SwissCreditorModeView.as_view()),
    path(
        "admin/creditor-modes/<str:uid>/external-debts/",
        BorrowerExternalDebtCreateView.as_view(),
    ),
    path(
        "admin/external-debts/<uuid:debt_id>/end/",
        BorrowerExternalDebtEndView.as_view(),
    ),
    path("admin/snb-rates/", SnbReferenceRateListCreateView.as_view()),
    path("admin/borrowers/", BorrowerEntityListCreateView.as_view(), name="borrower-list-create"),
    path(
        "admin/borrowers/<uuid:borrower_id>/",
        BorrowerEntityDetailView.as_view(),
        name="borrower-detail",
    ),
    path(
        "admin/borrowers/<uuid:borrower_id>/documents/",
        BorrowerDocumentListCreateView.as_view(),
        name="borrower-documents",
    ),
    path(
        "admin/borrowers/<uuid:borrower_id>/documents/<uuid:document_id>/metadata/",
        BorrowerDocumentMetadataView.as_view(),
        name="borrower-document-metadata",
    ),
    path(
        "admin/borrowers/<uuid:borrower_id>/financial-years/",
        BorrowerFinancialYearListView.as_view(),
        name="borrower-financial-years",
    ),
    path(
        "admin/borrowers/<uuid:borrower_id>/financial-years/<uuid:financial_year_id>/",
        BorrowerFinancialYearDetailView.as_view(),
        name="borrower-financial-year",
    ),
    path(
        "admin/borrowers/<uuid:borrower_id>/debt-facilities/",
        BorrowerDebtFacilityListView.as_view(),
        name="borrower-debt-facilities",
    ),
    path(
        "admin/borrowers/<uuid:borrower_id>/debt-facilities/<uuid:facility_id>/",
        BorrowerDebtFacilityDetailView.as_view(),
        name="borrower-debt-facility",
    ),
    path(
        "admin/borrowers/<uuid:borrower_id>/debt-facilities/<uuid:facility_id>/move/",
        BorrowerDebtFacilityMoveView.as_view(),
        name="borrower-debt-facility-move",
    ),
    path(
        "admin/borrowers/<uuid:borrower_id>/events/",
        BorrowerEventListView.as_view(),
        name="borrower-events",
    ),
    path(
        "admin/borrowers/<uuid:borrower_id>/investor-disclosure-preview/",
        BorrowerInvestorDisclosurePreviewView.as_view(),
        name="borrower-investor-disclosure-preview",
    ),
]
