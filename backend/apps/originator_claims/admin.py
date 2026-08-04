from __future__ import annotations

from django.contrib import admin

from backend.apps.originator_claims.models import (
    LoanOriginator,
    OriginatorClaimEntitlement,
    OriginatorClaimEvent,
    OriginatorClaimPurchase,
    OriginatorClaimQuote,
    OriginatorLoanImport,
    OriginatorLoanPaymentRow,
    OriginatorLoanProfile,
    OriginatorLoanScheduleRow,
    OriginatorSettlement,
    OriginatorSettlementPurchase,
)


@admin.register(LoanOriginator)
class LoanOriginatorAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("legal_name", "public_name", "jurisdiction", "status", "settlement_iban")
    list_filter = ("status", "jurisdiction")
    search_fields = ("legal_name", "public_name", "registration_number")


@admin.register(OriginatorLoanProfile)
class OriginatorLoanProfileAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "loan",
        "originator",
        "opportunity_status",
        "target_yield_bps",
        "unsold_principal_minor",
        "maturity_date",
    )
    list_filter = ("opportunity_status", "originator")
    search_fields = ("loan__title", "originator__legal_name", "borrower_display_name")


for model in (
    OriginatorLoanImport,
    OriginatorLoanScheduleRow,
    OriginatorLoanPaymentRow,
    OriginatorClaimQuote,
    OriginatorClaimPurchase,
    OriginatorClaimEntitlement,
    OriginatorSettlement,
    OriginatorSettlementPurchase,
    OriginatorClaimEvent,
):
    admin.site.register(model)
