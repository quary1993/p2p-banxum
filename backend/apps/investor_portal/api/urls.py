from __future__ import annotations

from django.urls import path

from backend.apps.investor_portal.api.views import (
    InvestorActivityView,
    InvestorBalancesView,
    InvestorDashboardView,
    InvestorFxHistoryView,
    InvestorPortfolioView,
    InvestorPrimaryOrdersView,
    InvestorSecondaryMarketActivityView,
)

urlpatterns = [
    path("dashboard/", InvestorDashboardView.as_view(), name="investor-portal-dashboard"),
    path("balances/", InvestorBalancesView.as_view(), name="investor-portal-balances"),
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
