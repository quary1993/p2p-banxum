from __future__ import annotations

from django.urls import path

from backend.apps.marketplace_primary.api.views import (
    MarketplaceLoanDetailView,
    PrimaryInvestmentOrderAllocateView,
    PrimaryInvestmentOrderCreateView,
    PrimaryInvestmentOrderReleaseView,
    PrimaryLoanCloseView,
    PublicMarketplaceLoanListView,
)

urlpatterns = [
    path("loans/", PublicMarketplaceLoanListView.as_view(), name="marketplace-primary-loans"),
    path(
        "loans/<uuid:loan_id>/",
        MarketplaceLoanDetailView.as_view(),
        name="marketplace-primary-loan-detail",
    ),
    path(
        "orders/",
        PrimaryInvestmentOrderCreateView.as_view(),
        name="marketplace-primary-order-create",
    ),
    path(
        "orders/<uuid:order_id>/allocate-balance/",
        PrimaryInvestmentOrderAllocateView.as_view(),
        name="marketplace-primary-order-allocate",
    ),
    path(
        "admin/orders/<uuid:order_id>/release-balance/",
        PrimaryInvestmentOrderReleaseView.as_view(),
        name="marketplace-primary-order-release",
    ),
    path(
        "admin/loans/<uuid:loan_id>/close-funding/",
        PrimaryLoanCloseView.as_view(),
        name="marketplace-primary-loan-close-funding",
    ),
]
