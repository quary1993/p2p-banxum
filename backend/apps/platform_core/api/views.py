from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.platform_core.api.serializers import HealthResponseSerializer


class HealthView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(responses=HealthResponseSerializer)
    def get(self, request):  # type: ignore[no-untyped-def]
        return Response(
            {
                "status": "ok",
                "platform": settings.PLATFORM_BRAND_NAME,
                "operator": settings.LEGAL_OPERATOR_NAME,
                "timezone": settings.TIME_ZONE,
                "environment": settings.ENVIRONMENT,
            }
        )
