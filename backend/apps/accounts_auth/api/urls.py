from __future__ import annotations

from django.urls import path

from backend.apps.accounts_auth.api.views import (
    CurrentUserView,
    MagicLinkConsumeView,
    MagicLinkRequestView,
    NaturalPersonRegistrationView,
    PhoneVerificationConfirmView,
    PhoneVerificationRequestView,
)

urlpatterns = [
    path("register/natural-person/", NaturalPersonRegistrationView.as_view(), name="auth-register"),
    path("magic-link/request/", MagicLinkRequestView.as_view(), name="auth-magic-link-request"),
    path("magic-link/consume/", MagicLinkConsumeView.as_view(), name="auth-magic-link-consume"),
    path("phone/request/", PhoneVerificationRequestView.as_view(), name="auth-phone-request"),
    path("phone/confirm/", PhoneVerificationConfirmView.as_view(), name="auth-phone-confirm"),
    path("me/", CurrentUserView.as_view(), name="auth-me"),
]
