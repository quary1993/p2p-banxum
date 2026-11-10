from __future__ import annotations

from django.urls import path

from backend.apps.loans.api.views import (
    LoanComingSoonView,
    LoanCreditCheckDetailView,
    LoanCreditCheckListView,
    LoanCreditCheckMoveView,
    LoanDetailView,
    LoanEventListView,
    LoanHistoryView,
    LoanListCreateView,
    LoanMonitoringView,
    LoanOriginalScheduleView,
    LoanReportingPlanView,
    LoanScheduleView,
    LoanSecurityDetailView,
    LoanSecurityListView,
    LoanSecurityMoveView,
    PublishLoanView,
)

urlpatterns = [
    path("admin/loans/", LoanListCreateView.as_view(), name="loan-list-create"),
    path("admin/loans/<uuid:loan_id>/", LoanDetailView.as_view(), name="loan-detail"),
    path("admin/loans/<uuid:loan_id>/publish/", PublishLoanView.as_view(), name="loan-publish"),
    path(
        "admin/loans/<uuid:loan_id>/credit-checks/",
        LoanCreditCheckListView.as_view(),
        name="loan-credit-checks",
    ),
    path(
        "admin/loans/<uuid:loan_id>/credit-checks/<uuid:check_id>/",
        LoanCreditCheckDetailView.as_view(),
        name="loan-credit-check",
    ),
    path(
        "admin/loans/<uuid:loan_id>/credit-checks/<uuid:check_id>/move/",
        LoanCreditCheckMoveView.as_view(),
        name="loan-credit-check-move",
    ),
    path(
        "admin/loans/<uuid:loan_id>/reporting-plan/",
        LoanReportingPlanView.as_view(),
        name="loan-reporting-plan",
    ),
    path(
        "admin/loans/<uuid:loan_id>/monitoring/",
        LoanMonitoringView.as_view(),
        name="loan-monitoring",
    ),
    path(
        "admin/loans/<uuid:loan_id>/securities/",
        LoanSecurityListView.as_view(),
        name="loan-securities",
    ),
    path(
        "admin/loans/<uuid:loan_id>/securities/<uuid:security_id>/",
        LoanSecurityDetailView.as_view(),
        name="loan-security",
    ),
    path(
        "admin/loans/<uuid:loan_id>/securities/<uuid:security_id>/move/",
        LoanSecurityMoveView.as_view(),
        name="loan-security-move",
    ),
    path(
        "admin/loans/<uuid:loan_id>/coming-soon/",
        LoanComingSoonView.as_view(),
        name="loan-coming-soon",
    ),
    path("admin/loans/<uuid:loan_id>/schedule/", LoanScheduleView.as_view(), name="loan-schedule"),
    path(
        "admin/loans/<uuid:loan_id>/original-schedule/",
        LoanOriginalScheduleView.as_view(),
        name="loan-original-schedule",
    ),
    path("admin/loans/<uuid:loan_id>/events/", LoanEventListView.as_view(), name="loan-events"),
    path("admin/loans/<uuid:loan_id>/history/", LoanHistoryView.as_view(), name="loan-history"),
]
