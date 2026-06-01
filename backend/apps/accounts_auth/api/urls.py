from __future__ import annotations

from django.urls import path

from backend.apps.accounts_auth.api.views import (
    CurrentUserView,
    MagicLinkConsumeView,
    MagicLinkRequestView,
    NaturalPersonRegistrationView,
)

urlpatterns = [
    path("register/natural-person/", NaturalPersonRegistrationView.as_view(), name="auth-register"),
    path("magic-link/request/", MagicLinkRequestView.as_view(), name="auth-magic-link-request"),
    path("magic-link/consume/", MagicLinkConsumeView.as_view(), name="auth-magic-link-consume"),
    path("me/", CurrentUserView.as_view(), name="auth-me"),
]
