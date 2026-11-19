from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import logout
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.accounts_auth.api.origin import SameSiteRequestOnly
from backend.apps.accounts_auth.api.permissions import IsSuperAdminUser
from backend.apps.accounts_auth.api.request_meta import client_ip, user_agent
from backend.apps.accounts_auth.api.serializers import (
    AccountAccessChangeRequestSerializer,
    AccountAccessChangeResponseSerializer,
    AdminUserCreateRequestSerializer,
    AuthenticatedUserResponseSerializer,
    CurrentUserResponseSerializer,
    DisplayPreferencesUpdateRequestSerializer,
    MagicLinkConsumeSerializer,
    MagicLinkRequestSerializer,
    MarketingConsentUpdateRequestSerializer,
    NaturalPersonRegistrationRequestSerializer,
    NaturalPersonRegistrationResponseSerializer,
    PhoneVerificationConfirmRequestSerializer,
    PhoneVerificationConfirmResponseSerializer,
    PhoneVerificationRequestResponseSerializer,
    PhoneVerificationRequestSerializer,
    RevokeOtherSessionsResponseSerializer,
    SensitiveActionCodeRequestResponseSerializer,
    SensitiveActionCodeRequestSerializer,
    SignInHistoryResponseSerializer,
    UserSessionsResponseSerializer,
    serialize_account_access_event,
    serialize_user,
)
from backend.apps.accounts_auth.api.throttles import (
    NaturalPersonRegistrationThrottle,
    PhoneVerificationConfirmThrottle,
    PhoneVerificationRequestThrottle,
    RegistrationLinkThrottle,
)
from backend.apps.accounts_auth.models import (
    AccountAccessReason,
    AccountStatus,
    SensitiveAction,
    SignInMethod,
    User,
)
from backend.apps.accounts_auth.security_sessions import (
    SESSION_RECORD_KEY,
    SessionNotFoundError,
    end_current_session,
    list_open_sessions,
    list_sign_in_history,
    retention_days,
    revoke_other_sessions,
    revoke_session,
)
from backend.apps.accounts_auth.services import (
    AccountAccessControlError,
    AccountLoginBlockedError,
    AccountsAuthError,
    AdminAuthorizationError,
    ChangeAccountAccessCommand,
    CreateAdminUserCommand,
    DuplicateEmailError,
    InvalidOrExpiredCodeError,
    InvalidOrExpiredTokenError,
    InvalidPasswordError,
    InvalidRegistrationDataError,
    InvalidTermsAcceptanceError,
    MagicLinkConsumeCommand,
    MagicLinkRequestCommand,
    OperationDetailsError,
    PhoneAlreadyVerifiedError,
    PhoneVerificationConfirmCommand,
    PhoneVerificationProviderError,
    PhoneVerificationRequestCommand,
    PhoneVerificationThrottleError,
    RegisterNaturalPersonCommand,
    SensitiveActionCodeCommand,
    SensitiveActionCodeThrottleError,
    TooManyCodeAttemptsError,
    UpdateDisplayPreferencesCommand,
    UpdateMarketingConsentCommand,
    change_account_access,
    confirm_phone_verification,
    consume_magic_link,
    create_admin_user,
    issue_magic_link,
    issue_sensitive_action_code,
    register_natural_person_lender,
    request_phone_verification,
    send_registration_follow_up_email,
    update_display_preferences,
    update_marketing_consent,
)
from backend.apps.accounts_auth.session_lifetime import start_authenticated_session
from backend.apps.platform_core.domain.time import business_date, now_utc


class NaturalPersonRegistrationView(APIView):
    authentication_classes: list[type] = []
    permission_classes = [SameSiteRequestOnly]
    throttle_classes = [NaturalPersonRegistrationThrottle]

    @extend_schema(
        request=NaturalPersonRegistrationRequestSerializer,
        responses={202: NaturalPersonRegistrationResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = NaturalPersonRegistrationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = register_natural_person_lender(
                RegisterNaturalPersonCommand(
                    email=data["email"],
                    full_name=data["full_name"],
                    phone_number=data["phone_number"],
                    terms_version=data["terms_version"],
                    terms_hash=data["terms_hash"],
                    registration_document_template_version_id=(
                        str(data["registration_document_template_version_id"])
                        if data.get("registration_document_template_version_id")
                        else None
                    ),
                    risk_document_template_version_id=(
                        str(data["risk_document_template_version_id"])
                        if data.get("risk_document_template_version_id")
                        else None
                    ),
                    accepted_checkbox_labels=data.get("accepted_checkbox_labels"),
                    accepted_risk_checkbox_labels=data.get("accepted_risk_checkbox_labels"),
                    document_idempotency_key=data.get("document_idempotency_key") or None,
                    risk_document_idempotency_key=(
                        data.get("risk_document_idempotency_key") or None
                    ),
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                    marketing_consent=data["marketing_consent"],
                    password=str(data["password"]),
                )
            )
        except (InvalidTermsAcceptanceError, InvalidRegistrationDataError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # The link that confirms the email address goes out with the registration, so the
        # client needs no second request. An address that already has an account gets the
        # same answer and an email that says so; nothing stored changes (audit A-50 / A-57).
        send_registration_follow_up_email(
            result,
            ip_address=client_ip(request),
            user_agent=user_agent(request),
        )
        return Response(
            {"status": "accepted", "email_login_sent": True},
            status=status.HTTP_202_ACCEPTED,
        )


class RegistrationLinkResendView(APIView):
    """18.5: send the registration link again. Always 202 (no account enumeration); only an
    account without a second factor gets a link (the others sign in with the password)."""

    authentication_classes: list[type] = []
    permission_classes = [SameSiteRequestOnly]
    throttle_classes = [RegistrationLinkThrottle]

    @extend_schema(request=MagicLinkRequestSerializer, responses={202: None})
    def post(self, request: Request) -> Response:
        serializer = MagicLinkRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            issue_magic_link(
                MagicLinkRequestCommand(
                    email=str(serializer.validated_data["email"]),
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except AccountsAuthError:
            pass
        return Response(status=status.HTTP_202_ACCEPTED)


class RegistrationEmailConfirmView(APIView):
    """18.5: the link sent at registration confirms the email address and signs in, only
    while the account has no second factor yet (to set one up)."""

    authentication_classes: list[type] = []
    permission_classes = [SameSiteRequestOnly]

    @extend_schema(
        request=MagicLinkConsumeSerializer,
        responses={200: AuthenticatedUserResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = MagicLinkConsumeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            user = consume_magic_link(
                MagicLinkConsumeCommand(
                    raw_token=data["token"],
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except AccountLoginBlockedError as exc:
            return Response(
                {"detail": str(exc), "code": f"account_{exc.account_status}"},
                status=status.HTTP_403_FORBIDDEN,
            )
        except InvalidOrExpiredTokenError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        start_authenticated_session(  # noqa: SLF001
            request._request, user, method=SignInMethod.REGISTRATION_LINK
        )
        return Response({"user": serialize_user(user)})


class SensitiveActionCodeRequestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=SensitiveActionCodeRequestSerializer,
        responses={202: SensitiveActionCodeRequestResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = SensitiveActionCodeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = issue_sensitive_action_code(
                SensitiveActionCodeCommand(
                    user=cast(User, request.user),
                    action=SensitiveAction(data["action"]),
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                    operation=dict(data.get("operation") or {}) or None,
                )
            )
        except SensitiveActionCodeThrottleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        except OperationDetailsError as exc:
            return Response(
                {"detail": str(exc), "code": "operation_details_invalid"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except InvalidOrExpiredCodeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "code_id": str(result.code_record.id),
                "action": result.code_record.action,
                "status": "code_sent",
                "expires_at": result.code_record.expires_at.isoformat(),
                "operation_summary": result.code_record.operation_summary,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class AdminUserCreateView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdminUser]

    @extend_schema(
        request=AdminUserCreateRequestSerializer,
        responses={201: AuthenticatedUserResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = AdminUserCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            user = create_admin_user(
                CreateAdminUserCommand(
                    actor=cast(User, request.user),
                    email=data["email"],
                    password=data["password"],
                    full_name=data["full_name"],
                )
            )
        except DuplicateEmailError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except AdminAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except InvalidPasswordError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"user": serialize_user(user)}, status=status.HTTP_201_CREATED)


class AccountAccessChangeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=AccountAccessChangeRequestSerializer,
        responses={200: AccountAccessChangeResponseSerializer},
    )
    def post(self, request: Request, user_id: str) -> Response:
        serializer = AccountAccessChangeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            event = change_account_access(
                ChangeAccountAccessCommand(
                    actor=cast(User, request.user),
                    user_id=user_id,
                    new_status=AccountStatus(data["new_status"]),
                    reason_code=AccountAccessReason(data["reason_code"]),
                    note=data.get("note", ""),
                    evidence_summary=data.get("evidence_summary", ""),
                    clean_account_confirmed=data["clean_account_confirmed"],
                )
            )
        except AdminAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except AccountAccessControlError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        event.user.refresh_from_db()
        return Response(
            {
                "user": serialize_user(event.user),
                "event": serialize_account_access_event(event),
            },
            status=status.HTTP_200_OK,
        )


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: CurrentUserResponseSerializer})
    def get(self, request: Request) -> Response:
        from backend.apps.platform_core.services.qa_dev_mode import qa_controls_available

        return Response(
            {
                "user": serialize_user(cast(User, request.user)),
                "qa_controls_available": qa_controls_available(request.user),
                "platform_business_date": business_date(now_utc()).isoformat(),
            }
        )


class MarketingConsentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=MarketingConsentUpdateRequestSerializer,
        responses={200: AuthenticatedUserResponseSerializer},
    )
    def patch(self, request: Request) -> Response:
        serializer = MarketingConsentUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = update_marketing_consent(
                UpdateMarketingConsentCommand(
                    user=cast(User, request.user),
                    marketing_consent=serializer.validated_data["marketing_consent"],
                )
            )
        except AccountsAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response({"user": serialize_user(user)})


class LogoutView(APIView):
    permission_classes: list[type] = []

    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        end_current_session(request._request)  # noqa: SLF001
        logout(request._request)  # noqa: SLF001
        return Response(status=status.HTTP_204_NO_CONTENT)


class PhoneVerificationRequestView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PhoneVerificationRequestThrottle]

    @extend_schema(
        request=PhoneVerificationRequestSerializer,
        responses={202: PhoneVerificationRequestResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        serializer = PhoneVerificationRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        try:
            result = request_phone_verification(
                PhoneVerificationRequestCommand(
                    user=user,
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                    phone_number=serializer.validated_data.get("phone_number") or None,
                )
            )
        except PhoneAlreadyVerifiedError:
            return Response(
                {
                    "challenge_id": None,
                    "status": "verified",
                    "expires_at": None,
                    "phone_verified": True,
                },
                status=status.HTTP_200_OK,
            )
        except PhoneVerificationThrottleError as exc:
            payload: dict[str, Any] = {"detail": str(exc)}
            if exc.retry_after_seconds is not None:
                payload["retry_after_seconds"] = exc.retry_after_seconds
            return Response(payload, status=status.HTTP_429_TOO_MANY_REQUESTS)
        except PhoneVerificationProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except InvalidOrExpiredCodeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except AccountsAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "challenge_id": str(result.challenge.id),
                "status": result.challenge.status,
                "expires_at": result.challenge.expires_at.isoformat(),
                "phone_verified": False,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class PhoneVerificationConfirmView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PhoneVerificationConfirmThrottle]

    @extend_schema(
        request=PhoneVerificationConfirmRequestSerializer,
        responses={200: PhoneVerificationConfirmResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = PhoneVerificationConfirmRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            confirm_phone_verification(
                PhoneVerificationConfirmCommand(
                    user=cast(User, request.user),
                    challenge_id=str(data["challenge_id"]),
                    raw_code=data["code"],
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except InvalidOrExpiredCodeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except TooManyCodeAttemptsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        except PhoneVerificationProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except AccountsAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.get(id=cast(User, request.user).id)
        return Response({"user": serialize_user(user)})


def _current_session_record_id(request: Request) -> str:
    session = getattr(request._request, "session", None)  # noqa: SLF001
    return str(session.get(SESSION_RECORD_KEY, "")) if session is not None else ""


class UserSessionsView(APIView):
    """U33-DEC-25: the signed-in browsers of the account, this one first."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSessionsResponseSerializer})
    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        sessions = list_open_sessions(user, current_id=_current_session_record_id(request))
        return Response({"sessions": sessions})


class UserSessionRevokeView(APIView):
    """End one other signed-in session; that browser is signed out on its next request."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request, session_id: str) -> Response:
        try:
            revoke_session(
                cast(User, request.user),
                session_id=str(session_id),
                current_id=_current_session_record_id(request),
            )
        except SessionNotFoundError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserSessionsRevokeOthersView(APIView):
    """End every signed-in session of the account except this one."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: RevokeOtherSessionsResponseSerializer})
    def post(self, request: Request) -> Response:
        count = revoke_other_sessions(
            cast(User, request.user), current_id=_current_session_record_id(request)
        )
        return Response({"sessions_ended": count})


class SignInHistoryView(APIView):
    """U33-DEC-25: the account's recent sign-ins (date, device, place, method, result)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SignInHistoryResponseSerializer})
    def get(self, request: Request) -> Response:
        events = list_sign_in_history(cast(User, request.user))
        return Response({"events": events, "retention_days": retention_days()})


class DisplayPreferencesView(APIView):
    """U33-DEC-31/-32: the language and number format saved in the account."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=DisplayPreferencesUpdateRequestSerializer,
        responses={200: AuthenticatedUserResponseSerializer},
    )
    def patch(self, request: Request) -> Response:
        serializer = DisplayPreferencesUpdateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = update_display_preferences(
                UpdateDisplayPreferencesCommand(
                    user=cast(User, request.user),
                    number_format=serializer.validated_data.get("number_format"),
                    language=serializer.validated_data.get("language"),
                )
            )
        except AccountsAuthError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"user": serialize_user(user)})
