from __future__ import annotations

from django.urls import path

from backend.apps.ledger.api.views import (
    InvestorBalanceSummaryView,
    LenderDepositDeclareView,
    ReconciliationSnapshotCreateView,
)

urlpatterns = [
    path(
        "admin/lender-deposits/",
        LenderDepositDeclareView.as_view(),
        name="ledger-lender-deposit-declare",
    ),
    path(
        "admin/investor-balance-summary/",
        InvestorBalanceSummaryView.as_view(),
        name="ledger-investor-balance-summary",
    ),
    path(
        "admin/reconciliation-snapshots/",
        ReconciliationSnapshotCreateView.as_view(),
        name="ledger-reconciliation-snapshot-create",
    ),
]
