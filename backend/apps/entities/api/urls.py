from __future__ import annotations

from django.urls import path

from backend.apps.entities.api.views import (
    BorrowerDocumentListCreateView,
    BorrowerEntityDetailView,
    BorrowerEntityListCreateView,
    BorrowerEventListView,
    BorrowerInvestorDisclosurePreviewView,
)

urlpatterns = [
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
