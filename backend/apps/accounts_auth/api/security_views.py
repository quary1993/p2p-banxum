"""IP of Webby-Soft SRL. 18.5 endpoints: investor sign-in (password + second factor), forgotten
password, assisted recovery, the Security tab, and the admin sign-in with an authenticator app.

Every error body has ``detail`` (for people) and ``code`` (for the portal).
"""

from __future__ import annotations

from typing import Any, cast

from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.accounts_auth import factor_sms, two_factor
from backend.apps.accounts_auth.api.origin import SameSiteRequestOnly
from backend.apps.accounts_auth.api.permissions import IsAdminPortalUser, IsSuperAdminUser
from backend.apps.accounts_auth.api.request_meta import client_ip, user_agent
from backend.apps.accounts_auth.api.security_serializers import (
    AdminEnrollmentRequestSerializer,
    AdminSignInConfirmRequestSerializer,
    AdminSignInStartResponseSerializer,
    AssistedRecoveryCaseSerializer,
    AssistedRecoveryCompleteRequestSerializer,
    AssistedRecoveryEvidenceRequestSerializer,
    AssistedRecoveryListSerializer,
    AssistedRecoveryOpenRequestSerializer,
    AuthenticatedUserSerializer,
    AuthenticatorConfirmRequestSerializer,
    AuthenticatorEnrollmentResponseSerializer,
    ChallengeRequestSerializer,
    FactorCodeRequestSerializer,
    FactorStepResponseSerializer,
    PasswordChangeRequestSerializer,
    PasswordForgotRequestSerializer,
    PasswordResetCompleteRequestSerializer,
    RecoveryCodesRequestSerializer,
    RecoveryCodesResponseSerializer,
    SecurityConfirmResponseSerializer,
    SecurityConfirmStartRequestSerializer,
    SecurityOverviewSerializer,
    SignInRequestSerializer,
    SignInResponseSerializer,
    SignInVerifyRequestSerializer,
    StatusResponseSerializer,
    TokenRequestSerializer,
    TwoFactorErrorSerializer,
)
from backend.apps.accounts_auth.api.serializers import AuthenticatedUserResponseSerializer
from backend.apps.accounts_auth.api.serializers import serialize_user as user_payload
from backend.apps.accounts_auth.api.throttles import (
    AdminLoginConfirmThrottle,
    AdminLoginStartThrottle,
    PasswordResetRequestThrottle,
    SecurityChangeThrottle,
    SignInThrottle,
    SignInVerifyThrottle,
    admin_login_failure_backoff,
    email_ip_identifier,
    sign_in_failure_backoff,
)
from backend.apps.accounts_auth.factors import factor_kind
from backend.apps.accounts_auth.models import (
    AssistedRecoveryCase,
    AuthenticatorApp,
    RecoveryCode,
    SignInMethod,
    User,
)
from backend.apps.accounts_auth.security_sessions import (
    SESSION_RECORD_KEY,
    describe_user_agent,
)
from backend.apps.accounts_auth.services import (
    AdminLoginInvalidCredentialsError,
    InvalidOrExpiredCodeError,
    PhoneVerificationProviderError,
    PhoneVerificationThrottleError,
    SensitiveActionCodeThrottleError,
)
from backend.apps.accounts_auth.session_lifetime import start_authenticated_session

ERRORS = {
    400: OpenApiResponse(TwoFactorErrorSerializer),
    403: OpenApiResponse(TwoFactorErrorSerializer),
    423: OpenApiResponse(TwoFactorErrorSerializer),
    429: OpenApiResponse(TwoFactorErrorSerializer),
}


def _error(exc: Exception) -> Response:
    if isinstance(exc, two_factor.TwoFactorError):
        return Response(exc.payload(), status=exc.http_status)
    if isinstance(exc, factor_sms.FactorSmsError):
        return Response(
            {"detail": str(exc), "code": exc.code},
            status=429 if exc.code == "sms_code_attempts" else 400,
        )
    if isinstance(exc, PhoneVerificationThrottleError):
        payload: dict[str, Any] = {"detail": str(exc), "code": "sms_throttled"}
        if exc.retry_after_seconds is not None:
            payload["retry_after_seconds"] = exc.retry_after_seconds
        return Response(payload, status=status.HTTP_429_TOO_MANY_REQUESTS)
    if isinstance(exc, PhoneVerificationProviderError):
        return Response(
            {
                "detail": "The SMS service is not available. Try again later.",
                "code": "sms_unavailable",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    raise exc


_HANDLED = (
    two_factor.TwoFactorError,
    factor_sms.FactorSmsError,
    PhoneVerificationThrottleError,
    PhoneVerificationProviderError,
)


def _current_session_id(request: Request) -> str:
    return str(request.session.get(SESSION_RECORD_KEY, "") or "")


def _set_trusted_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        two_factor.TRUSTED_COOKIE_NAME,
        token,
        max_age=int(getattr(settings, "AUTH_TRUSTED_DEVICE_DAYS", 30)) * 24 * 60 * 60,
        secure=bool(getattr(settings, "SESSION_COOKIE_SECURE", False)),
        httponly=True,
        samesite="Lax",
    )


def _factor_step(step: two_factor.SignInStep) -> dict[str, Any]:
    return {
        "status": step.status,
        "method": step.method,
        "challenge_id": step.challenge_id,
        "phone_last_digits": step.phone_last_digits,
    }


# --- Investor sign-in ------------------------------------------------------------------------


class SignInView(APIView):
    """Step 1: email and password. Answers ``signed_in`` (remembered browser),
    ``factor_required`` (type the app or SMS code next) or ``enrollment_required`` (signed in;
    set up a second factor before anything else)."""

    authentication_classes: list[type] = []
    permission_classes = [SameSiteRequestOnly]
    throttle_classes = [SignInThrottle]

    @extend_schema(
        request=SignInRequestSerializer, responses={200: SignInResponseSerializer, **ERRORS}
    )
    def post(self, request: Request) -> Response:
        serializer = SignInRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        backoff = sign_in_failure_backoff()
        backoff_key = email_ip_identifier(request, str(data["email"]))
        wait = backoff.retry_after(backoff_key)
        if wait is not None:
            return Response(
                {
                    "detail": f"Too many attempts. Try again in {wait} seconds.",
                    "code": "sign_in_throttled",
                    "retry_after_seconds": wait,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(wait)},
            )
        try:
            step = two_factor.start_sign_in(
                email=str(data["email"]),
                password=str(data["password"]),
                trusted_token=str(request.COOKIES.get(two_factor.TRUSTED_COOKIE_NAME, "") or ""),
                ip_address=client_ip(request),
                user_agent=user_agent(request),
            )
        except _HANDLED as exc:
            if isinstance(exc, two_factor.TwoFactorError) and exc.code == "invalid_credentials":
                backoff.record_failure(backoff_key)
            return _error(exc)
        backoff.reset(backoff_key)
        if step.status in {"signed_in", "enrollment_required"}:
            start_authenticated_session(  # noqa: SLF001
                request._request, step.user, method=step.sign_in_method
            )
            return Response({**_factor_step(step), "user": user_payload(step.user)})
        return Response({**_factor_step(step), "user": None})


class SignInVerifyView(APIView):
    """Step 2: the app or SMS code, or a recovery code. ``trust_device`` remembers this
    browser for 30 days (the password is still asked)."""

    authentication_classes: list[type] = []
    permission_classes = [SameSiteRequestOnly]
    throttle_classes = [SignInVerifyThrottle]

    @extend_schema(
        request=SignInVerifyRequestSerializer,
        responses={200: AuthenticatedUserSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = SignInVerifyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            user, method = two_factor.complete_sign_in(
                challenge_id=str(data["challenge_id"]),
                code=str(data.get("code") or ""),
                recovery_code=str(data.get("recovery_code") or ""),
                ip_address=client_ip(request),
                user_agent=user_agent(request),
            )
        except _HANDLED as exc:
            return _error(exc)
        if not user.can_login:
            return Response(
                {
                    "detail": "Your account cannot sign in. Contact support.",
                    "code": "account_blocked",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        start_authenticated_session(request._request, user, method=method)  # noqa: SLF001
        response = Response({"user": user_payload(user)})
        if data.get("trust_device"):
            label, _kind = describe_user_agent(user_agent(request))
            _set_trusted_cookie(response, two_factor.trust_device(user, device_label=label))
        return response


class SignInResendSmsView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [SameSiteRequestOnly]
    throttle_classes = [SignInVerifyThrottle]

    @extend_schema(
        request=ChallengeRequestSerializer, responses={202: StatusResponseSerializer, **ERRORS}
    )
    def post(self, request: Request) -> Response:
        serializer = ChallengeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            two_factor.resend_sms(
                challenge_id=str(serializer.validated_data["challenge_id"]),
                ip_address=client_ip(request),
                user_agent=user_agent(request),
            )
        except _HANDLED as exc:
            return _error(exc)
        return Response({"status": "sms_sent"}, status=status.HTTP_202_ACCEPTED)


# --- Forgotten password ----------------------------------------------------------------------


class PasswordForgotView(APIView):
    """Always answers 202 (no account enumeration); the link works once, for 30 minutes."""

    authentication_classes: list[type] = []
    permission_classes = [SameSiteRequestOnly]
    throttle_classes = [PasswordResetRequestThrottle]

    @extend_schema(
        request=PasswordForgotRequestSerializer, responses={202: StatusResponseSerializer}
    )
    def post(self, request: Request) -> Response:
        serializer = PasswordForgotRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        two_factor.request_password_reset(
            email=str(serializer.validated_data["email"]), ip_address=client_ip(request)
        )
        return Response({"status": "accepted"}, status=status.HTTP_202_ACCEPTED)


class PasswordResetStartView(APIView):
    """Open the link: the second factor is asked next (an SMS code is sent now)."""

    authentication_classes: list[type] = []
    permission_classes = [SameSiteRequestOnly]
    throttle_classes = [SignInVerifyThrottle]

    @extend_schema(
        request=TokenRequestSerializer, responses={200: FactorStepResponseSerializer, **ERRORS}
    )
    def post(self, request: Request) -> Response:
        serializer = TokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            step = two_factor.start_password_reset(
                raw_token=str(serializer.validated_data["token"]),
                ip_address=client_ip(request),
                user_agent=user_agent(request),
            )
        except _HANDLED as exc:
            return _error(exc)
        return Response(_factor_step(step))


class PasswordResetCompleteView(APIView):
    """The new password with the second factor (or a recovery code). All devices sign out."""

    authentication_classes: list[type] = []
    permission_classes = [SameSiteRequestOnly]
    throttle_classes = [SignInVerifyThrottle]

    @extend_schema(
        request=PasswordResetCompleteRequestSerializer,
        responses={200: StatusResponseSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = PasswordResetCompleteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            two_factor.complete_password_reset(
                raw_token=str(data["token"]),
                new_password=str(data["new_password"]),
                challenge_id=str(data.get("challenge_id") or ""),
                code=str(data.get("code") or ""),
                recovery_code=str(data.get("recovery_code") or ""),
                ip_address=client_ip(request),
                user_agent=user_agent(request),
            )
        except _HANDLED as exc:
            return _error(exc)
        return Response({"status": "password_reset"})


# --- Assisted recovery (investor side) -------------------------------------------------------


class AssistedRecoveryDisputeView(APIView):
    """ "This was not me": stops the recovery at once and alerts support."""

    authentication_classes: list[type] = []
    permission_classes = [SameSiteRequestOnly]
    throttle_classes = [SignInVerifyThrottle]

    @extend_schema(
        request=TokenRequestSerializer, responses={200: StatusResponseSerializer, **ERRORS}
    )
    def post(self, request: Request) -> Response:
        serializer = TokenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            two_factor.dispute_assisted_recovery(raw_token=str(serializer.validated_data["token"]))
        except _HANDLED as exc:
            return _error(exc)
        return Response({"status": "recovery_stopped"})


class AssistedRecoveryCompleteView(APIView):
    """The single-use link after the 24-hour wait: a new password, then (signed in) a new
    second factor."""

    authentication_classes: list[type] = []
    permission_classes = [SameSiteRequestOnly]
    throttle_classes = [SignInVerifyThrottle]

    @extend_schema(
        request=AssistedRecoveryCompleteRequestSerializer,
        responses={200: AuthenticatedUserSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = AssistedRecoveryCompleteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            user = two_factor.complete_assisted_recovery(
                raw_token=str(data["token"]), new_password=str(data["new_password"])
            )
        except _HANDLED as exc:
            return _error(exc)
        start_authenticated_session(  # noqa: SLF001
            request._request, user, method=SignInMethod.PASSWORD_ONLY
        )
        return Response({"user": user_payload(user)})


# --- Security tab ----------------------------------------------------------------------------


def _signed_in_user(request: Request) -> User:
    return cast(User, request.user)


def _overview(user: User) -> dict[str, Any]:
    app = (
        AuthenticatorApp.objects.filter(
            user=user, confirmed_at__isnull=False, disabled_at__isnull=True
        )
        .order_by("-confirmed_at")
        .first()
    )
    restriction = two_factor.active_restriction(user.pk)
    return {
        "second_factor": factor_kind(user),
        "phone_last_digits": two_factor.phone_last_digits(user),
        "authenticator_added_at": app.confirmed_at if app is not None else None,
        "recovery_codes_remaining": two_factor.recovery_codes_remaining(user),
        "recovery_codes_issued": RecoveryCode.objects.filter(user=user).exists(),
        "password_set": user.has_usable_password(),
        "password_changed_at": user.password_changed_at,
        "trusted_devices": two_factor.list_trusted_devices(user),
        "restriction": (
            {"reason": restriction.reason, "ends_at": restriction.ends_at}
            if restriction is not None
            else None
        ),
    }


class SecurityOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SecurityOverviewSerializer})
    def get(self, request: Request) -> Response:
        return Response(SecurityOverviewSerializer(_overview(_signed_in_user(request))).data)


class SecurityConfirmStartView(APIView):
    """A security change starts with the password; the factor is asked next."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [SecurityChangeThrottle]

    @extend_schema(
        request=SecurityConfirmStartRequestSerializer,
        responses={200: FactorStepResponseSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = SecurityConfirmStartRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            step = two_factor.start_security_confirmation(
                user=_signed_in_user(request),
                password=str(serializer.validated_data["password"]),
                ip_address=client_ip(request),
                user_agent=user_agent(request),
            )
        except _HANDLED as exc:
            return _error(exc)
        return Response(_factor_step(step))


class SecurityConfirmVerifyView(APIView):
    """The factor of a security change; answers a confirmation valid 10 minutes, once."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [SecurityChangeThrottle]

    @extend_schema(
        request=FactorCodeRequestSerializer,
        responses={200: SecurityConfirmResponseSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = FactorCodeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            confirmation = two_factor.complete_security_confirmation(
                user=_signed_in_user(request),
                challenge_id=str(data["challenge_id"]),
                code=str(data.get("code") or ""),
                recovery_code=str(data.get("recovery_code") or ""),
                ip_address=client_ip(request),
                user_agent=user_agent(request),
            )
        except _HANDLED as exc:
            return _error(exc)
        return Response({"confirmation_id": confirmation})


class SecurityConfirmResendSmsView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [SecurityChangeThrottle]

    @extend_schema(
        request=ChallengeRequestSerializer, responses={202: StatusResponseSerializer, **ERRORS}
    )
    def post(self, request: Request) -> Response:
        serializer = ChallengeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            two_factor.resend_sms(
                challenge_id=str(serializer.validated_data["challenge_id"]),
                user=_signed_in_user(request),
                ip_address=client_ip(request),
                user_agent=user_agent(request),
            )
        except _HANDLED as exc:
            return _error(exc)
        return Response({"status": "sms_sent"}, status=status.HTTP_202_ACCEPTED)


class PasswordChangeView(APIView):
    """Changing the password signs out the other devices and forgets remembered browsers."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [SecurityChangeThrottle]

    @extend_schema(
        request=PasswordChangeRequestSerializer,
        responses={200: SecurityOverviewSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = PasswordChangeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        user = _signed_in_user(request)
        try:
            two_factor.change_password(
                user=user,
                new_password=str(data["new_password"]),
                security_confirmation_id=str(data["confirmation_id"]),
                keep_session_id=_current_session_id(request),
            )
        except _HANDLED as exc:
            return _error(exc)
        # The password hash is part of the session; keep this browser signed in.
        update_session_auth_hash(request._request, user)  # noqa: SLF001
        return Response(SecurityOverviewSerializer(_overview(user)).data)


class AuthenticatorStartView(APIView):
    """A new app secret to scan (QR code from ``otpauth_uri``) or type."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [SecurityChangeThrottle]

    @extend_schema(
        request=None, responses={200: AuthenticatorEnrollmentResponseSerializer, **ERRORS}
    )
    def post(self, request: Request) -> Response:
        user = _signed_in_user(request)
        if not two_factor.is_investor(user):
            return Response(
                {"detail": "Admins set up the app when they sign in.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(two_factor.start_authenticator_enrollment(user))


class AuthenticatorConfirmView(APIView):
    """The first code from the app activates it. An account with a factor needs a fresh
    security confirmation; the app then replaces the PIN and the SMS code (D-1)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [SecurityChangeThrottle]

    @extend_schema(
        request=AuthenticatorConfirmRequestSerializer,
        responses={200: SecurityOverviewSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = AuthenticatorConfirmRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        user = _signed_in_user(request)
        if not two_factor.is_investor(user):
            return Response(
                {"detail": "Admins set up the app when they sign in.", "code": "forbidden"},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            two_factor.confirm_authenticator_enrollment(
                user=user,
                enrollment_id=str(data["enrollment_id"]),
                code=str(data["code"]),
                security_confirmation_id=str(data.get("confirmation_id") or ""),
                keep_session_id=_current_session_id(request),
            )
        except _HANDLED as exc:
            return _error(exc)
        return Response(SecurityOverviewSerializer(_overview(user)).data)


class RecoveryCodesView(APIView):
    """10 new recovery codes, shown once; older unused codes stop working."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [SecurityChangeThrottle]

    @extend_schema(
        request=RecoveryCodesRequestSerializer,
        responses={200: RecoveryCodesResponseSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = RecoveryCodesRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = _signed_in_user(request)
        if not factor_kind(user):
            return Response(
                {"detail": "Set up your second factor first.", "code": "no_second_factor"},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            codes = two_factor.issue_recovery_codes(
                user=user,
                security_confirmation_id=str(
                    serializer.validated_data.get("confirmation_id") or ""
                ),
            )
        except _HANDLED as exc:
            return _error(exc)
        return Response({"codes": codes})


class TrustedDeviceRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: SecurityOverviewSerializer})
    def post(self, request: Request, device_id: str) -> Response:
        user = _signed_in_user(request)
        two_factor.revoke_trusted_devices(user, device_id=device_id, reason="investor")
        return Response(SecurityOverviewSerializer(_overview(user)).data)


# --- Admin sign-in -----------------------------------------------------------------------------


class AdminSignInStartView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [SameSiteRequestOnly]
    throttle_classes = [AdminLoginStartThrottle]

    @extend_schema(
        request=SignInRequestSerializer,
        responses={202: AdminSignInStartResponseSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = SignInRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        # Wrong passwords slow down only this (email, IP) pair (audit A-47).
        backoff = admin_login_failure_backoff()
        backoff_key = email_ip_identifier(request, str(data["email"]))
        wait = backoff.retry_after(backoff_key)
        if wait is not None:
            return Response(
                {
                    "detail": f"Too many failed admin login attempts. Try again in {wait} seconds.",
                    "code": "admin_login_throttled",
                    "retry_after_seconds": wait,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(wait)},
            )
        try:
            step = two_factor.start_admin_sign_in(
                email=str(data["email"]),
                password=str(data["password"]),
                ip_address=client_ip(request),
                user_agent=user_agent(request),
            )
        except AdminLoginInvalidCredentialsError as exc:
            backoff.record_failure(backoff_key)
            return Response(
                {"detail": str(exc), "code": "invalid_credentials"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except SensitiveActionCodeThrottleError as exc:
            return Response({"detail": str(exc), "code": "email_code_throttled"}, status=429)
        except InvalidOrExpiredCodeError as exc:
            return Response({"detail": str(exc), "code": "invalid_credentials"}, status=400)
        backoff.reset(backoff_key)
        enrollment = step.enrollment or {}
        return Response(
            {
                "status": step.status,
                "challenge_id": step.challenge_id,
                "code_id": step.code_id,
                "expires_at": step.code_expires_at.isoformat() if step.code_expires_at else None,
                "enrollment_id": enrollment.get("enrollment_id", ""),
                "secret": enrollment.get("secret", ""),
                "otpauth_uri": enrollment.get("otpauth_uri", ""),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class AdminSignInConfirmView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [SameSiteRequestOnly]
    throttle_classes = [AdminLoginConfirmThrottle]

    @extend_schema(
        request=AdminSignInConfirmRequestSerializer,
        responses={200: AuthenticatedUserResponseSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = AdminSignInConfirmRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            user = two_factor.complete_admin_sign_in(
                challenge_id=str(data["challenge_id"]),
                code=str(data["code"]),
                ip_address=client_ip(request),
                user_agent=user_agent(request),
            )
        except _HANDLED as exc:
            return _error(exc)
        start_authenticated_session(  # noqa: SLF001
            request._request, user, method=SignInMethod.ADMIN_PASSWORD_APP
        )
        return Response({"user": user_payload(user)})


class AdminSignInEnrollView(APIView):
    """First admin sign-in (or after a reset): the email code and the first app code."""

    authentication_classes: list[type] = []
    permission_classes = [SameSiteRequestOnly]
    throttle_classes = [AdminLoginConfirmThrottle]

    @extend_schema(
        request=AdminEnrollmentRequestSerializer,
        responses={200: AuthenticatedUserResponseSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = AdminEnrollmentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            user = two_factor.complete_admin_enrollment(
                code_id=str(data["code_id"]),
                email_code=str(data["email_code"]),
                enrollment_id=str(data["enrollment_id"]),
                code=str(data["code"]),
                ip_address=client_ip(request),
                user_agent=user_agent(request),
            )
        except _HANDLED as exc:
            return _error(exc)
        start_authenticated_session(  # noqa: SLF001
            request._request, user, method=SignInMethod.ADMIN_PASSWORD_APP
        )
        return Response({"user": user_payload(user)})


class AdminAuthenticatorResetView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdminUser]

    @extend_schema(request=None, responses={200: StatusResponseSerializer, **ERRORS})
    def post(self, request: Request, user_id: str) -> Response:
        try:
            two_factor.reset_admin_authenticator(actor=request.user, admin_user_id=user_id)
        except _HANDLED as exc:
            return _error(exc)
        return Response({"status": "authenticator_reset"})


# --- Assisted recovery (support side) --------------------------------------------------------


def _case_payload(case: AssistedRecoveryCase) -> dict[str, Any]:
    return {
        "id": str(case.id),
        "user_id": str(case.user_id),
        "user_email": str(case.user.email),
        "status": case.status,
        "request_note": case.request_note,
        "identity_evidence": case.identity_evidence,
        "requested_by_admin_id": str(case.requested_by_admin_id or ""),
        "identity_confirmed_by_admin_id": str(case.identity_confirmed_by_admin_id or ""),
        "approved_by_admin_id": str(case.approved_by_admin_id or ""),
        "created_at": case.created_at,
        "wait_until": case.wait_until,
        "link_sent_at": case.link_sent_at,
        "completed_at": case.completed_at,
        "cancelled_at": case.cancelled_at,
    }


class AdminAssistedRecoveryListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminPortalUser]

    @extend_schema(responses={200: AssistedRecoveryListSerializer})
    def get(self, request: Request) -> Response:
        cases = two_factor.list_assisted_recoveries(
            status=str(request.query_params.get("status", ""))
        )
        return Response(
            AssistedRecoveryListSerializer(
                {"results": [_case_payload(case) for case in cases]}
            ).data
        )

    @extend_schema(
        request=AssistedRecoveryOpenRequestSerializer,
        responses={201: AssistedRecoveryCaseSerializer, **ERRORS},
    )
    def post(self, request: Request) -> Response:
        serializer = AssistedRecoveryOpenRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            case = two_factor.open_assisted_recovery(
                actor=request.user,
                user_id=str(serializer.validated_data["user_id"]),
                note=str(serializer.validated_data["note"]),
            )
        except _HANDLED as exc:
            return _error(exc)
        return Response(
            AssistedRecoveryCaseSerializer(_case_payload(case)).data, status=status.HTTP_201_CREATED
        )


class AdminAssistedRecoveryIdentityView(APIView):
    permission_classes = [IsAuthenticated, IsAdminPortalUser]

    @extend_schema(
        request=AssistedRecoveryEvidenceRequestSerializer,
        responses={200: AssistedRecoveryCaseSerializer, **ERRORS},
    )
    def post(self, request: Request, case_id: str) -> Response:
        serializer = AssistedRecoveryEvidenceRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            case = two_factor.confirm_assisted_identity(
                actor=request.user,
                case_id=case_id,
                evidence=str(serializer.validated_data["evidence"]),
            )
        except _HANDLED as exc:
            return _error(exc)
        return Response(AssistedRecoveryCaseSerializer(_case_payload(case)).data)


class AdminAssistedRecoveryApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdminPortalUser]

    @extend_schema(request=None, responses={200: AssistedRecoveryCaseSerializer, **ERRORS})
    def post(self, request: Request, case_id: str) -> Response:
        try:
            case = two_factor.approve_assisted_recovery(actor=request.user, case_id=case_id)
        except _HANDLED as exc:
            return _error(exc)
        return Response(AssistedRecoveryCaseSerializer(_case_payload(case)).data)
