from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import login
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.accounts_auth.api.request_meta import client_ip, user_agent
from backend.apps.accounts_auth.api.serializers import (
    AuthenticatedUserResponseSerializer,
    MagicLinkConsumeSerializer,
    MagicLinkRequestSerializer,
    NaturalPersonRegistrationRequestSerializer,
    NaturalPersonRegistrationResponseSerializer,
    PhoneVerificationConfirmRequestSerializer,
    PhoneVerificationConfirmResponseSerializer,
    PhoneVerificationRequestResponseSerializer,
    serialize_user,
)
from backend.apps.accounts_auth.api.throttles import (
    MagicLinkRequestThrottle,
    NaturalPersonRegistrationThrottle,
    PhoneVerificationConfirmThrottle,
    PhoneVerificationRequestThrottle,
)
from backend.apps.accounts_auth.models import User
from backend.apps.accounts_auth.services import (
    DuplicateEmailError,
    InvalidOrExpiredCodeError,
    InvalidOrExpiredTokenError,
    InvalidTermsAcceptanceError,
    MagicLinkConsumeCommand,
    MagicLinkRequestCommand,
    PhoneAlreadyVerifiedError,
    PhoneVerificationConfirmCommand,
    PhoneVerificationRequestCommand,
    PhoneVerificationThrottleError,
    RegisterNaturalPersonCommand,
    TooManyCodeAttemptsError,
    confirm_phone_verification,
    consume_magic_link,
    issue_magic_link,
    register_natural_person_lender,
    request_phone_verification,
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
        return Response({"user": serialize_user(user)}, status=status.HTTP_201_CREATED)


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


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: AuthenticatedUserResponseSerializer})
    def get(self, request: Request) -> Response:
        return Response({"user": serialize_user(cast(User, request.user))})


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
            return Response({"detail": str(exc)}, status=status.HTTP_429_TOO_MANY_REQUESTS)
        except InvalidOrExpiredCodeError as exc:
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

        user = User.objects.get(id=cast(User, request.user).id)
        return Response({"user": serialize_user(user)})
