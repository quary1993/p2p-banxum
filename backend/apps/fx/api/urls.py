from __future__ import annotations

from django.urls import path

from backend.apps.fx.api.views import (
    FxDeltaReportView,
    FxExternalSettlementDeclareView,
    FxQuoteExecuteView,
    FxQuoteIssueView,
    FxRealizedSettlementReportView,
)

urlpatterns = [
    path("quotes/", FxQuoteIssueView.as_view(), name="fx-quote-issue"),
    path("quotes/<uuid:quote_id>/execute/", FxQuoteExecuteView.as_view(), name="fx-quote-execute"),
    path("admin/delta-report/", FxDeltaReportView.as_view(), name="fx-delta-report"),
    path(
        "admin/external-settlements/",
        FxExternalSettlementDeclareView.as_view(),
        name="fx-external-settlement-declare",
    ),
    path(
        "admin/realized-settlement-report/",
        FxRealizedSettlementReportView.as_view(),
        name="fx-realized-settlement-report",
    ),
]
