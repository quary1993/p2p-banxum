from __future__ import annotations

from django.urls import path

from backend.apps.accounts_auth.api.pin_views import (
    PinChangeView,
    PinResetConfirmView,
    PinResetStartView,
    PinSetView,
    PinStatusView,
)
from backend.apps.accounts_auth.api.security_views import (
    AdminAssistedRecoveryApproveView,
    AdminAssistedRecoveryIdentityView,
    AdminAssistedRecoveryListView,
    AdminAuthenticatorResetView,
    AdminSignInConfirmView,
    AdminSignInEnrollView,
    AdminSignInStartView,
    AssistedRecoveryCompleteView,
    AssistedRecoveryDisputeView,
    AuthenticatorConfirmView,
    AuthenticatorStartView,
    PasswordChangeView,
    PasswordForgotView,
    PasswordResetCompleteView,
    PasswordResetStartView,
    RecoveryCodesView,
    SecurityConfirmResendSmsView,
    SecurityConfirmStartView,
    SecurityConfirmVerifyView,
    SecurityOverviewView,
    SignInResendSmsView,
    SignInVerifyView,
    SignInView,
    TrustedDeviceRevokeView,
)
from backend.apps.accounts_auth.api.views import (
    AccountAccessChangeView,
    AdminUserCreateView,
    CurrentUserView,
    DisplayPreferencesView,
    LogoutView,
    MarketingConsentView,
    NaturalPersonRegistrationView,
    PhoneVerificationConfirmView,
    PhoneVerificationRequestView,
    RegistrationEmailConfirmView,
    SensitiveActionCodeRequestView,
    SignInHistoryView,
    UserSessionRevokeView,
    UserSessionsRevokeOthersView,
    UserSessionsView,
)

urlpatterns = [
    path("register/natural-person/", NaturalPersonRegistrationView.as_view(), name="auth-register"),
    path(
        "register/confirm-email/",
        RegistrationEmailConfirmView.as_view(),
        name="auth-register-confirm-email",
    ),
    # 18.5 investor sign-in: password, then the app or SMS code (or a recovery code).
    path("login/", SignInView.as_view(), name="auth-login"),
    path("login/verify/", SignInVerifyView.as_view(), name="auth-login-verify"),
    path("login/resend-sms/", SignInResendSmsView.as_view(), name="auth-login-resend-sms"),
    path("password/forgot/", PasswordForgotView.as_view(), name="auth-password-forgot"),
    path(
        "password/reset/start/", PasswordResetStartView.as_view(), name="auth-password-reset-start"
    ),
    path(
        "password/reset/complete/",
        PasswordResetCompleteView.as_view(),
        name="auth-password-reset-complete",
    ),
    path(
        "account-recovery/not-me/",
        AssistedRecoveryDisputeView.as_view(),
        name="auth-account-recovery-dispute",
    ),
    path(
        "account-recovery/complete/",
        AssistedRecoveryCompleteView.as_view(),
        name="auth-account-recovery-complete",
    ),
    path("security/", SecurityOverviewView.as_view(), name="auth-security"),
    path(
        "security/confirm/start/",
        SecurityConfirmStartView.as_view(),
        name="auth-security-confirm-start",
    ),
    path(
        "security/confirm/verify/",
        SecurityConfirmVerifyView.as_view(),
        name="auth-security-confirm-verify",
    ),
    path(
        "security/confirm/resend-sms/",
        SecurityConfirmResendSmsView.as_view(),
        name="auth-security-confirm-resend-sms",
    ),
    path("security/password/", PasswordChangeView.as_view(), name="auth-security-password"),
    path(
        "security/authenticator/start/",
        AuthenticatorStartView.as_view(),
        name="auth-security-authenticator-start",
    ),
    path(
        "security/authenticator/confirm/",
        AuthenticatorConfirmView.as_view(),
        name="auth-security-authenticator-confirm",
    ),
    path(
        "security/recovery-codes/", RecoveryCodesView.as_view(), name="auth-security-recovery-codes"
    ),
    path(
        "security/trusted-devices/<uuid:device_id>/revoke/",
        TrustedDeviceRevokeView.as_view(),
        name="auth-security-trusted-device-revoke",
    ),
    # Admins: password + authenticator app (the first sign-in also needs an email code).
    path("admin/login/start/", AdminSignInStartView.as_view(), name="auth-admin-login-start"),
    path("admin/login/confirm/", AdminSignInConfirmView.as_view(), name="auth-admin-login-confirm"),
    path("admin/login/enroll/", AdminSignInEnrollView.as_view(), name="auth-admin-login-enroll"),
    path("admin/users/", AdminUserCreateView.as_view(), name="auth-admin-user-create"),
    path(
        "admin/users/<uuid:user_id>/authenticator/reset/",
        AdminAuthenticatorResetView.as_view(),
        name="auth-admin-user-authenticator-reset",
    ),
    path(
        "admin/account-recoveries/",
        AdminAssistedRecoveryListView.as_view(),
        name="auth-admin-account-recoveries",
    ),
    path(
        "admin/account-recoveries/<uuid:case_id>/confirm-identity/",
        AdminAssistedRecoveryIdentityView.as_view(),
        name="auth-admin-account-recovery-identity",
    ),
    path(
        "admin/account-recoveries/<uuid:case_id>/approve/",
        AdminAssistedRecoveryApproveView.as_view(),
        name="auth-admin-account-recovery-approve",
    ),
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
    path("pin/status/", PinStatusView.as_view(), name="auth-pin-status"),
    path("pin/set/", PinSetView.as_view(), name="auth-pin-set"),
    path("pin/change/", PinChangeView.as_view(), name="auth-pin-change"),
    path("pin/reset/start/", PinResetStartView.as_view(), name="auth-pin-reset-start"),
    path("pin/reset/confirm/", PinResetConfirmView.as_view(), name="auth-pin-reset-confirm"),
    path("me/", CurrentUserView.as_view(), name="auth-me"),
    path("preferences/marketing/", MarketingConsentView.as_view(), name="auth-marketing-consent"),
    path("preferences/display/", DisplayPreferencesView.as_view(), name="auth-display-preferences"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("sessions/", UserSessionsView.as_view(), name="auth-sessions"),
    path(
        "sessions/revoke-others/",
        UserSessionsRevokeOthersView.as_view(),
        name="auth-sessions-revoke-others",
    ),
    path(
        "sessions/<uuid:session_id>/revoke/",
        UserSessionRevokeView.as_view(),
        name="auth-session-revoke",
    ),
    path("sign-in-history/", SignInHistoryView.as_view(), name="auth-sign-in-history"),
]
