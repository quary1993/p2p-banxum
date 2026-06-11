from __future__ import annotations

from django.urls import path

from backend.apps.investor_portal.api.views import (
    InvestorActivityView,
    InvestorBalancesView,
    InvestorDashboardView,
    InvestorDepositInstructionsView,
    InvestorDocumentDownloadView,
    InvestorDocumentsView,
    InvestorFxHistoryView,
    InvestorNotificationsView,
    InvestorPortfolioView,
    InvestorPrimaryOrdersView,
    InvestorSecondaryMarketActivityView,
)

urlpatterns = [
    path("dashboard/", InvestorDashboardView.as_view(), name="investor-portal-dashboard"),
    path("balances/", InvestorBalancesView.as_view(), name="investor-portal-balances"),
    path(
        "deposit-instructions/",
        InvestorDepositInstructionsView.as_view(),
        name="investor-portal-deposit-instructions",
    ),
    path("documents/", InvestorDocumentsView.as_view(), name="investor-portal-documents"),
    path(
        "documents/download/",
        InvestorDocumentDownloadView.as_view(),
        name="investor-portal-document-download",
    ),
    path(
        "notifications/",
        InvestorNotificationsView.as_view(),
        name="investor-portal-notifications",
    ),
    path("portfolio/", InvestorPortfolioView.as_view(), name="investor-portal-portfolio"),
    path("activity/", InvestorActivityView.as_view(), name="investor-portal-activity"),
    path("primary-orders/", InvestorPrimaryOrdersView.as_view(), name="investor-portal-orders"),
    path(
        "secondary-market/",
        InvestorSecondaryMarketActivityView.as_view(),
        name="investor-portal-secondary-market",
    ),
    path("fx/", InvestorFxHistoryView.as_view(), name="investor-portal-fx"),
]
