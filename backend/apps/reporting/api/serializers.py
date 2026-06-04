from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.reporting.models import (
    ReportOutputFormat,
    ReportPeriodPreset,
    ReportRedactionMode,
    ReportRun,
    ReportType,
)


class ReportGenerateRequestSerializer(serializers.Serializer[Any]):
    report_type = serializers.ChoiceField(choices=ReportType.choices)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    period_preset = serializers.ChoiceField(
        choices=ReportPeriodPreset.choices,
        required=False,
        default=ReportPeriodPreset.CUSTOM,
    )
    period_anchor_date = serializers.DateField(required=False)
    output_format = serializers.ChoiceField(
        choices=ReportOutputFormat.choices,
        required=False,
        default=ReportOutputFormat.CSV,
    )
    redaction_mode = serializers.ChoiceField(
        choices=ReportRedactionMode.choices,
        required=False,
        default=ReportRedactionMode.REDACTED,
    )
    filters = serializers.JSONField(required=False)
    destination_note = serializers.CharField(required=False, allow_blank=True)


class ReportRunSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    report_type = serializers.CharField()
    output_format = serializers.CharField()
    redaction_mode = serializers.CharField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    generated_by_admin_id = serializers.UUIDField()
    generated_at = serializers.DateTimeField()
    definition_version = serializers.CharField()
    filters = serializers.JSONField()
    row_count = serializers.IntegerField()
    content_sha256 = serializers.CharField()
    manifest = serializers.JSONField()
    destination_note = serializers.CharField()
    metadata = serializers.JSONField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class ReportGenerateResponseSerializer(serializers.Serializer[Any]):
    report_run = ReportRunSerializer()
    content_type = serializers.CharField()
    filename = serializers.CharField()
    content_encoding = serializers.CharField()
    content = serializers.CharField()
    manifest = serializers.JSONField()


def serialize_report_run(report_run: ReportRun) -> dict[str, Any]:
    return {
        "id": str(report_run.id),
        "report_type": report_run.report_type,
        "output_format": report_run.output_format,
        "redaction_mode": report_run.redaction_mode,
        "start_date": report_run.start_date.isoformat(),
        "end_date": report_run.end_date.isoformat(),
        "generated_by_admin_id": str(report_run.generated_by_admin_id),
        "generated_at": report_run.generated_at.isoformat(),
        "definition_version": report_run.definition_version,
        "filters": report_run.filters,
        "row_count": report_run.row_count,
        "content_sha256": report_run.content_sha256,
        "manifest": report_run.manifest,
        "destination_note": report_run.destination_note,
        "metadata": report_run.metadata,
        "created_at": report_run.created_at.isoformat(),
        "updated_at": report_run.updated_at.isoformat(),
    }
