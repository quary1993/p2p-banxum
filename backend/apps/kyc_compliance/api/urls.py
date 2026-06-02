from __future__ import annotations

from django.urls import path

from backend.apps.kyc_compliance.api.views import (
    DiditWebhookView,
    KycAdminManualReviewDecisionView,
    KycAdminManualReviewListView,
    KycSessionCreateView,
    KycStatusView,
)

urlpatterns = [
    path("status/", KycStatusView.as_view(), name="kyc-status"),
    path("session/", KycSessionCreateView.as_view(), name="kyc-session-create"),
    path(
        "admin/manual-reviews/",
        KycAdminManualReviewListView.as_view(),
        name="kyc-admin-manual-review-list",
    ),
    path(
        "admin/cases/<uuid:case_id>/manual-review/",
        KycAdminManualReviewDecisionView.as_view(),
        name="kyc-admin-manual-review-decision",
    ),
    path("webhooks/didit/", DiditWebhookView.as_view(), name="kyc-didit-webhook"),
]
