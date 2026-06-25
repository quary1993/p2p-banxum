from __future__ import annotations

from typing import Any

from rest_framework import serializers


class HealthResponseSerializer(serializers.Serializer[Any]):
    status = serializers.CharField()
    platform = serializers.CharField()
    operator = serializers.CharField()
    timezone = serializers.CharField()
    environment = serializers.CharField()


class QaDevModeStateSerializer(serializers.Serializer[Any]):
    allowed = serializers.BooleanField()
    is_enabled = serializers.BooleanField()
    current_time = serializers.DateTimeField(allow_null=True)
    entered_at = serializers.DateTimeField(allow_null=True)
    entered_by_user_id = serializers.UUIDField(allow_null=True)
    snapshot_created_at = serializers.DateTimeField(allow_null=True)
    has_snapshot = serializers.BooleanField()
    note = serializers.CharField(allow_blank=True)
    last_advanced_at = serializers.DateTimeField(allow_null=True)
    last_advance_summary = serializers.JSONField()
    max_advance_days = serializers.IntegerField()
    environment = serializers.CharField()


class QaDevModeEnableRequestSerializer(serializers.Serializer[Any]):
    note = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class QaDevModeAdvanceRequestSerializer(serializers.Serializer[Any]):
    days = serializers.IntegerField(min_value=1, max_value=120)


class QaDevModeRevertRequestSerializer(serializers.Serializer[Any]):
    confirmation = serializers.CharField(max_length=64)
