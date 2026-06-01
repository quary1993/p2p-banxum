from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import login
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.accounts_auth.api.serializers import (
    AuthenticatedUserResponseSerializer,
    MagicLinkConsumeSerializer,
    MagicLinkRequestSerializer,
    NaturalPersonRegistrationRequestSerializer,
    NaturalPersonRegistrationResponseSerializer,
    serialize_user,
)
from backend.apps.accounts_auth.models import User
from backend.apps.accounts_auth.services import (
    DuplicateEmailError,
    InvalidOrExpiredTokenError,
    MagicLinkConsumeCommand,
    MagicLinkRequestCommand,
    RegisterNaturalPersonCommand,
    consume_magic_link,
    issue_magic_link,
    register_natural_person_lender,
)


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return str(forwarded_for).split(",")[0].strip()
    remote_addr = request.META.get("REMOTE_ADDR")
    return str(remote_addr) if remote_addr else None


def _user_agent(request: Request) -> str:
    return str(request.META.get("HTTP_USER_AGENT", ""))


class NaturalPersonRegistrationView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

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
                    ip_address=_client_ip(request),
                    user_agent=_user_agent(request),
                    marketing_consent=data["marketing_consent"],
                )
            )
        except DuplicateEmailError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({"user": serialize_user(user)}, status=status.HTTP_201_CREATED)


class MagicLinkRequestView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(request=MagicLinkRequestSerializer, responses={202: None})
    def post(self, request: Request) -> Response:
        serializer = MagicLinkRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            issue_magic_link(
                MagicLinkRequestCommand(
                    email=data["email"],
                    ip_address=_client_ip(request),
                    user_agent=_user_agent(request),
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
                    ip_address=_client_ip(request),
                    user_agent=_user_agent(request),
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
