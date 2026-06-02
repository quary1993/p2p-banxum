from __future__ import annotations

from django.urls import path

from backend.apps.loans.api.views import (
    LoanDetailView,
    LoanEventListView,
    LoanListCreateView,
    LoanScheduleView,
    PublishLoanView,
)

urlpatterns = [
    path("admin/loans/", LoanListCreateView.as_view(), name="loan-list-create"),
    path("admin/loans/<uuid:loan_id>/", LoanDetailView.as_view(), name="loan-detail"),
    path("admin/loans/<uuid:loan_id>/publish/", PublishLoanView.as_view(), name="loan-publish"),
    path("admin/loans/<uuid:loan_id>/schedule/", LoanScheduleView.as_view(), name="loan-schedule"),
    path("admin/loans/<uuid:loan_id>/events/", LoanEventListView.as_view(), name="loan-events"),
]
