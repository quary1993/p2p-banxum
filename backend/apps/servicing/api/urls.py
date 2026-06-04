from __future__ import annotations

from django.urls import path

from backend.apps.servicing.api.views import (
    BorrowerRepaymentRecordView,
    LoanRiskNoteAdminListCreateView,
    LoanServicingStatusScanView,
    LoanWriteOffRecordView,
    PublicLoanRiskNoteListView,
)

urlpatterns = [
    path(
        "admin/borrower-repayments/",
        BorrowerRepaymentRecordView.as_view(),
        name="servicing-borrower-repayment-record",
    ),
    path(
        "admin/status-scan/",
        LoanServicingStatusScanView.as_view(),
        name="servicing-status-scan",
    ),
    path(
        "admin/risk-notes/",
        LoanRiskNoteAdminListCreateView.as_view(),
        name="servicing-admin-risk-notes",
    ),
    path(
        "loan-risk-notes/",
        PublicLoanRiskNoteListView.as_view(),
        name="servicing-public-risk-notes",
    ),
    path(
        "admin/write-offs/",
        LoanWriteOffRecordView.as_view(),
        name="servicing-write-off-record",
    ),
]
