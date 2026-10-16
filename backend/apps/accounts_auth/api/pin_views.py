"""IP of Webby-Soft SRL. PIN endpoints under /api/v1/auth/pin/ (ACC-DEC-009)."""

from __future__ import annotations

from typing import Any, cast

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.accounts_auth.api.request_meta import client_ip, user_agent
from backend.apps.accounts_auth.api.serializers import (
    PinChangeRequestSerializer,
    PinErrorResponseSerializer,
    PinResetConfirmRequestSerializer,
    PinResetStartResponseSerializer,
    PinSetRequestSerializer,
    PinStatusResponseSerializer,
    serialize_pin_status,
)
from backend.apps.accounts_auth.api.throttles import PinResetStartThrottle, PinThrottle
from backend.apps.accounts_auth.models import User
from backend.apps.accounts_auth.pin_services import (
    ChangePinCommand,
    ConfirmPinResetCommand,
    PhoneCodeAttemptsError,
    PhoneCodeInvalidError,
    PinError,
    SetPinCommand,
    StartPinResetCommand,
    change_pin,
    confirm_pin_reset,
    pin_status_for_user,
    set_first_pin,
    start_pin_reset,
)
from backend.apps.accounts_auth.services import (
    AccountsAuthError,
    InvalidOrExpiredCodeError,
    PhoneVerificationProviderError,
    PhoneVerificationThrottleError,
    TooManyCodeAttemptsError,
)

PIN_ERROR_RESPONSES = {
    400: OpenApiResponse(PinErrorResponseSerializer, description="pin_invalid, pin_weak, ..."),
    403: OpenApiResponse(PinErrorResponseSerializer, description="pin_not_available"),
    409: OpenApiResponse(PinErrorResponseSerializer, description="pin_required, ..."),
    423: OpenApiResponse(PinErrorResponseSerializer, description="pin_locked"),
}


def _pin_flow_error_response(exc: AccountsAuthError) -> Response:
    """One error body for the PIN flows: ``detail`` for people, ``code`` for the portal."""

    if isinstance(exc, PinError):
        return Response(exc.payload(), status=exc.http_status)
    if isinstance(exc, PhoneCodeAttemptsError):
        return Response(
            {"detail": str(exc), "code": exc.code},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    if isinstance(exc, PhoneCodeInvalidError):
        return Response({"detail": str(exc), "code": exc.code}, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, TooManyCodeAttemptsError):
        return Response(
            {
                "detail": "Too many wrong email codes. Send a new email code.",
                "code": "email_code_attempts_exceeded",
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    if isinstance(exc, InvalidOrExpiredCodeError):
        return Response(
            {
                "detail": "The email code is wrong or expired. Check it or send a new one.",
                "code": "email_code_invalid",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    if isinstance(exc, PhoneVerificationThrottleError):
        payload: dict[str, Any] = {"detail": str(exc), "code": "phone_code_throttled"}
        if exc.retry_after_seconds is not None:
            payload["retry_after_seconds"] = exc.retry_after_seconds
        return Response(payload, status=status.HTTP_429_TOO_MANY_REQUESTS)
    if isinstance(exc, PhoneVerificationProviderError):
        return Response(
            {"detail": "SMS codes cannot be sent right now. Try again in a few minutes."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _status_payload(user: User) -> dict[str, Any]:
    return {"pin": serialize_pin_status(pin_status_for_user(user))}


def _pin_user(request: Request) -> User:
    # IsAuthenticated: the session user is a User. The services refuse non-investors.
    return cast(User, request.user)


class PinStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: PinStatusResponseSerializer})
    def get(self, request: Request) -> Response:
        return Response(_status_payload(_pin_user(request)))


class PinSetView(APIView):
    """First PIN: at registration without an email code, otherwise with ``pin_setup``."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [PinThrottle]

    @extend_schema(
        request=PinSetRequestSerializer,
        responses={201: PinStatusResponseSerializer, **PIN_ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        serializer = PinSetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        user = _pin_user(request)
        try:
            set_first_pin(
                SetPinCommand(
                    user=user,
                    new_pin=data["new_pin"],
                    new_pin_confirmation=data["new_pin_confirmation"],
                    sensitive_action_code_id=str(data.get("sensitive_action_code_id") or ""),
                    sensitive_action_code=str(data.get("sensitive_action_code") or ""),
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except AccountsAuthError as exc:
            return _pin_flow_error_response(exc)
        return Response(_status_payload(user), status=status.HTTP_201_CREATED)


class PinChangeView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [PinThrottle]

    @extend_schema(
        request=PinChangeRequestSerializer,
        responses={200: PinStatusResponseSerializer, **PIN_ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        serializer = PinChangeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        user = _pin_user(request)
        try:
            change_pin(
                ChangePinCommand(
                    user=user,
                    pin=data["pin"],
                    new_pin=data["new_pin"],
                    new_pin_confirmation=data["new_pin_confirmation"],
                    sensitive_action_code_id=str(data["sensitive_action_code_id"]),
                    sensitive_action_code=data["sensitive_action_code"],
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except AccountsAuthError as exc:
            return _pin_flow_error_response(exc)
        return Response(_status_payload(user))


class PinResetStartView(APIView):
    """Forgot PIN, step 1: an SMS code to the verified phone (the email code is requested
    through /auth/sensitive-action-code/request/ with ``pin_reset``)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [PinResetStartThrottle]

    @extend_schema(
        request=None,
        responses={202: PinResetStartResponseSerializer, **PIN_ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        try:
            result = start_pin_reset(
                StartPinResetCommand(
                    user=_pin_user(request),
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except AccountsAuthError as exc:
            return _pin_flow_error_response(exc)
        return Response(
            {
                "phone_challenge_id": str(result.challenge.id),
                "expires_at": result.challenge.expires_at.isoformat(),
                "phone_last_digits": result.phone_last_digits,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class PinResetConfirmView(APIView):
    """Forgot PIN, step 2: email code, SMS code and the new PIN twice; clears the lock."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [PinThrottle]

    @extend_schema(
        request=PinResetConfirmRequestSerializer,
        responses={200: PinStatusResponseSerializer, **PIN_ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        serializer = PinResetConfirmRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        user = _pin_user(request)
        try:
            confirm_pin_reset(
                ConfirmPinResetCommand(
                    user=user,
                    phone_challenge_id=str(data["phone_challenge_id"]),
                    phone_code=data["phone_code"],
                    new_pin=data["new_pin"],
                    new_pin_confirmation=data["new_pin_confirmation"],
                    sensitive_action_code_id=str(data["sensitive_action_code_id"]),
                    sensitive_action_code=data["sensitive_action_code"],
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                )
            )
        except AccountsAuthError as exc:
            return _pin_flow_error_response(exc)
        return Response(_status_payload(user))
