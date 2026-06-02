from __future__ import annotations

from django.urls import path

from backend.apps.ledger.api.views import (
    BalanceAgeingScanView,
    InvestorBalanceSummaryView,
    InvestorPayoutInstructionRegisterView,
    InvestorWithdrawalCancelView,
    InvestorWithdrawalFinalizeView,
    InvestorWithdrawalRequestCreateView,
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
        "admin/payout-instructions/",
        InvestorPayoutInstructionRegisterView.as_view(),
        name="ledger-investor-payout-instruction-register",
    ),
    path(
        "admin/investor-balance-summary/",
        InvestorBalanceSummaryView.as_view(),
        name="ledger-investor-balance-summary",
    ),
    path(
        "withdrawal-requests/",
        InvestorWithdrawalRequestCreateView.as_view(),
        name="ledger-investor-withdrawal-request-create",
    ),
    path(
        "admin/withdrawal-requests/<uuid:withdrawal_request_id>/finalize/",
        InvestorWithdrawalFinalizeView.as_view(),
        name="ledger-investor-withdrawal-finalize",
    ),
    path(
        "admin/withdrawal-requests/<uuid:withdrawal_request_id>/cancel/",
        InvestorWithdrawalCancelView.as_view(),
        name="ledger-investor-withdrawal-cancel",
    ),
    path(
        "admin/reconciliation-snapshots/",
        ReconciliationSnapshotCreateView.as_view(),
        name="ledger-reconciliation-snapshot-create",
    ),
    path(
        "admin/balance-ageing-scans/",
        BalanceAgeingScanView.as_view(),
        name="ledger-balance-ageing-scan",
    ),
]
