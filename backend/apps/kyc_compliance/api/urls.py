from __future__ import annotations

from django.urls import path

from backend.apps.kyc_compliance.api.views import (
    DiditWebhookView,
    KycSessionCreateView,
    KycStatusView,
)

urlpatterns = [
    path("status/", KycStatusView.as_view(), name="kyc-status"),
    path("session/", KycSessionCreateView.as_view(), name="kyc-session-create"),
    path("webhooks/didit/", DiditWebhookView.as_view(), name="kyc-didit-webhook"),
]
