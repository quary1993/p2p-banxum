from __future__ import annotations

from typing import Any, cast

from django.db.models import Model
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.platform_core.api.impersonation import (
    ReadOnlyImpersonationError,
    readonly_read_actor_from_request,
)
from backend.apps.smart_invest.api.serializers import (
    SmartInvestResponseSerializer,
    SmartInvestRuleSaveRequestSerializer,
)
from backend.apps.smart_invest.services import (
    SaveSmartInvestRuleCommand,
    SmartInvestAuthorizationError,
    SmartInvestValidationError,
    deactivate_smart_invest_rule,
    get_smart_invest,
    save_smart_invest_rule,
)


def _error_response(exc: Exception) -> Response:
    status_code = (
        status.HTTP_403_FORBIDDEN
        if isinstance(exc, SmartInvestAuthorizationError)
        else status.HTTP_400_BAD_REQUEST
    )
    return Response({"detail": str(exc)}, status=status_code)


class SmartInvestView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SmartInvestResponseSerializer})
    def get(self, request: Request) -> Response:
        try:
            actor, _audit_actor = readonly_read_actor_from_request(request)
            payload = get_smart_invest(actor=actor)
        except ReadOnlyImpersonationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except (SmartInvestAuthorizationError, SmartInvestValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)

    @extend_schema(
        request=SmartInvestRuleSaveRequestSerializer,
        responses={200: SmartInvestResponseSerializer},
    )
    def put(self, request: Request) -> Response:
        serializer = SmartInvestRuleSaveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            payload = save_smart_invest_rule(
                SaveSmartInvestRuleCommand(actor=cast(Model, request.user), **data)
            )
        except (SmartInvestAuthorizationError, SmartInvestValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class SmartInvestDeactivateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: SmartInvestResponseSerializer})
    def post(self, request: Request) -> Response:
        try:
            payload = deactivate_smart_invest_rule(actor=cast(Model, request.user))
        except (SmartInvestAuthorizationError, SmartInvestValidationError) as exc:
            return _error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)
