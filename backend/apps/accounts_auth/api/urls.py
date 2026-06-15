from __future__ import annotations

from django.urls import path

from backend.apps.accounts_auth.api.views import (
    AccountAccessChangeView,
    AdminLoginConfirmView,
    AdminLoginStartView,
    AdminUserCreateView,
    CurrentUserView,
    LogoutView,
    MagicLinkConsumeView,
    MagicLinkRequestView,
    NaturalPersonRegistrationView,
    PhoneVerificationConfirmView,
    PhoneVerificationRequestView,
    SensitiveActionCodeRequestView,
)

urlpatterns = [
    path("register/natural-person/", NaturalPersonRegistrationView.as_view(), name="auth-register"),
    path("magic-link/request/", MagicLinkRequestView.as_view(), name="auth-magic-link-request"),
    path("magic-link/consume/", MagicLinkConsumeView.as_view(), name="auth-magic-link-consume"),
    path("admin/login/start/", AdminLoginStartView.as_view(), name="auth-admin-login-start"),
    path("admin/login/confirm/", AdminLoginConfirmView.as_view(), name="auth-admin-login-confirm"),
    path("admin/users/", AdminUserCreateView.as_view(), name="auth-admin-user-create"),
    path(
        "admin/users/<uuid:user_id>/access/",
        AccountAccessChangeView.as_view(),
        name="auth-admin-user-access-change",
    ),
    path("phone/request/", PhoneVerificationRequestView.as_view(), name="auth-phone-request"),
    path("phone/confirm/", PhoneVerificationConfirmView.as_view(), name="auth-phone-confirm"),
    path(
        "sensitive-action-code/request/",
        SensitiveActionCodeRequestView.as_view(),
        name="auth-sensitive-action-code-request",
    ),
    path("me/", CurrentUserView.as_view(), name="auth-me"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
]
