from __future__ import annotations

from typing import Any

from rest_framework import serializers


class HealthResponseSerializer(serializers.Serializer[Any]):
    status = serializers.CharField()
    platform = serializers.CharField()
    operator = serializers.CharField()
    timezone = serializers.CharField()
    environment = serializers.CharField()
