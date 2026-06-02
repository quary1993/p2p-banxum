from __future__ import annotations

from django.urls import path

from backend.apps.servicing.api.views import BorrowerRepaymentRecordView

urlpatterns = [
    path(
        "admin/borrower-repayments/",
        BorrowerRepaymentRecordView.as_view(),
        name="servicing-borrower-repayment-record",
    ),
]
