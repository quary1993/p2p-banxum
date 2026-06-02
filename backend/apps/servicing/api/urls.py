from __future__ import annotations

from django.urls import path

from backend.apps.servicing.api.views import (
    BorrowerRepaymentRecordView,
    LoanServicingStatusScanView,
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
]
