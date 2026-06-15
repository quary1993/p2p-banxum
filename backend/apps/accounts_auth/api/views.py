from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import login, logout
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.accounts_auth.api.permissions import IsSuperAdminUser
from backend.apps.accounts_auth.api.request_meta import client_ip, user_agent
from backend.apps.accounts_auth.api.serializers import (
    AccountAccessChangeRequestSerializer,
    AccountAccessChangeResponseSerializer,
    AdminLoginConfirmRequestSerializer,
    AdminLoginStartRequestSerializer,
    AdminLoginStartResponseSerializer,
    AdminUserCreateRequestSerializer,
    AuthenticatedUserResponseSerializer,
    MagicLinkConsumeSerializer,
    MagicLinkRequestSerializer,
    NaturalPersonRegistrationRequestSerializer,
    NaturalPersonRegistrationResponseSerializer,
    PhoneVerificationConfirmRequestSerializer,
    PhoneVerificationConfirmResponseSerializer,
    PhoneVerificationRequestResponseSerializer,
    SensitiveActionCodeRequestResponseSerializer,
    SensitiveActionCodeRequestSerializer,
    serialize_account_access_event,
    serialize_user,
)
from backend.apps.accounts_auth.api.throttles import (
    AdminLoginConfirmThrottle,
    AdminLoginStartThrottle,
    MagicLinkRequestThrottle,
    NaturalPersonRegistrationThrottle,
    PhoneVerificationConfirmThrottle,
    PhoneVerificationRequestThrottle,
)
from backend.apps.accounts_auth.models import (
    AccountAccessReason,
    AccountStatus,
    SensitiveAction,
    User,
)
from backend.apps.accounts_auth.services import (
    AccountAccessControlError,
    AccountsAuthError,
    AdminAuthorizationError,
    AdminLoginConfirmCommand,
    AdminLoginInvalidCredentialsError,
    AdminLoginStartCommand,
    ChangeAccountAccessCommand,
    CreateAdminUserCommand,
    DuplicateEmailError,
    InvalidOrExpiredCodeError,
    InvalidOrExpiredTokenError,
    InvalidPasswordError,
    InvalidTermsAcceptanceError,
    MagicLinkConsumeCommand,
    MagicLinkRequestCommand,
    PhoneAlreadyVerifiedError,
    PhoneVerificationConfirmCommand,
    PhoneVerificationProviderError,
    PhoneVerificationRequestCommand,
    PhoneVerificationThrottleError,
    RegisterNaturalPersonCommand,
    SensitiveActionCodeCommand,
    SensitiveActionCodeThrottleError,
    TooManyCodeAttemptsError,
    change_account_access,
    confirm_admin_login,
    confirm_phone_verification,
    consume_magic_link,
    create_admin_user,
    issue_magic_link,
    issue_sensitive_action_code,
    register_natural_person_lender,
    request_phone_verification,
    start_admin_login,
)


class NaturalPersonRegistrationView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []
    throttle_classes = [NaturalPersonRegistrationThrottle]

    @extend_schema(
        request=NaturalPersonRegistrationRequestSerializer,
        responses={201: NaturalPersonRegistrationResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = NaturalPersonRegistrationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            user = register_natural_person_lender(
                RegisterNaturalPersonCommand(
                    email=data["email"],
                    full_name=data["full_name"],
                    phone_number=data["phone_number"],
                    terms_version=data["terms_version"],
                    terms_hash=data["terms_hash"],
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                    marketing_consent=data["marketing_consent"],
                )
            )
        except DuplicateEmailError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        except InvalidTermsAcceptanceError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        # Issue the first sign-in magic link as part of registration so the
        # client does not need a second request that can race the per-IP/email
        # magic-link throttle. Registration must still succeed if issuance
        # fails; the client can fall back to the explicit resend endpoint.
        email_login_sent = True
        try:
            issue_magic_link(
                MagicLinkRequestCommand(
                    email=user.email,
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except AccountsAuthError:
            email_login_sent = False
        return Response(
            {"user": serialize_user(user), "email_login_sent": email_login_sent},
            status=status.HTTP_201_CREATED,
        )


class MagicLinkRequestView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []
    throttle_classes = [MagicLinkRequestThrottle]

    @extend_schema(request=MagicLinkRequestSerializer, responses={202: None})
    def post(self, request: Request) -> Response:
        serializer = MagicLinkRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            issue_magic_link(
                MagicLinkRequestCommand(
                    email=data["email"],
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except InvalidOrExpiredTokenError:
            pass
        return Response(status=status.HTTP_202_ACCEPTED)


class MagicLinkConsumeView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

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
        except InvalidOrExpiredTokenError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        login(
            request._request,  # noqa: SLF001
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )
        return Response({"user": serialize_user(user)})


class AdminLoginStartView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []
    throttle_classes = [AdminLoginStartThrottle]

    @extend_schema(
        request=AdminLoginStartRequestSerializer,
        responses={202: AdminLoginStartResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = AdminLoginStartRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = start_admin_login(
                AdminLoginStartCommand(
                    email=data["email"],
                    password=data["password"],
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except (AdminLoginInvalidCredentialsError, InvalidOrExpiredCodeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except SensitiveActionCodeThrottleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        return Response(
            {
                "code_id": str(result.code_record.id),
                "status": "code_sent",
                "expires_at": result.code_record.expires_at.isoformat(),
            },
            status=status.HTTP_202_ACCEPTED,
        )


class AdminLoginConfirmView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []
    throttle_classes = [AdminLoginConfirmThrottle]

    @extend_schema(
        request=AdminLoginConfirmRequestSerializer,
        responses={200: AuthenticatedUserResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = AdminLoginConfirmRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            user = confirm_admin_login(
                AdminLoginConfirmCommand(
                    code_id=str(data["code_id"]),
                    raw_code=data["code"],
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except (AdminLoginInvalidCredentialsError, InvalidOrExpiredCodeError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except TooManyCodeAttemptsError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        login(
            request._request,  # noqa: SLF001
            user,
            backend="django.contrib.auth.backends.ModelBackend",
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
                )
            )
        except SensitiveActionCodeThrottleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        except InvalidOrExpiredCodeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "code_id": str(result.code_record.id),
                "action": result.code_record.action,
                "status": "code_sent",
                "expires_at": result.code_record.expires_at.isoformat(),
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

    @extend_schema(responses={200: AuthenticatedUserResponseSerializer})
    def get(self, request: Request) -> Response:
        return Response({"user": serialize_user(cast(User, request.user))})


class LogoutView(APIView):
    permission_classes: list[type] = []

    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        logout(request._request)  # noqa: SLF001
        return Response(status=status.HTTP_204_NO_CONTENT)


class PhoneVerificationRequestView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PhoneVerificationRequestThrottle]

    @extend_schema(request=None, responses={202: PhoneVerificationRequestResponseSerializer})
    def post(self, request: Request) -> Response:
        user = cast(User, request.user)
        try:
            result = request_phone_verification(
                PhoneVerificationRequestCommand(
                    user=user,
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
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
