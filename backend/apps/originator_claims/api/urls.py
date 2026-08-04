from __future__ import annotations

from django.urls import path

from backend.apps.originator_claims.api import views

urlpatterns = [
    path("admin/originators/", views.OriginatorListCreateView.as_view()),
    path("admin/originators/<uuid:originator_id>/", views.OriginatorDetailView.as_view()),
    path("admin/loans/", views.OriginatorLoanCreateView.as_view()),
    path("admin/loans/<uuid:loan_id>/", views.OriginatorLoanDetailView.as_view()),
    path("admin/loans/<uuid:loan_id>/publish/", views.OriginatorLoanPublishView.as_view()),
    path("admin/loans/<uuid:loan_id>/hold/", views.OriginatorLoanHoldView.as_view()),
    path(
        "admin/loans/<uuid:loan_id>/repayments/",
        views.OriginatorBorrowerRepaymentCreateView.as_view(),
    ),
    path("loans/<uuid:loan_id>/quote/", views.OriginatorClaimQuoteView.as_view()),
    path("quotes/<uuid:quote_id>/purchase/", views.OriginatorClaimPurchaseView.as_view()),
    path("admin/settlements/outstanding/", views.OriginatorSettlementQueueView.as_view()),
    path("admin/settlements/", views.OriginatorSettlementCreateView.as_view()),
]
