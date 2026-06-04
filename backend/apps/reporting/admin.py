from __future__ import annotations

from typing import Any, cast

from django.contrib import admin
from django.db.models import Model, QuerySet
from django.http import HttpRequest

from backend.apps.reporting.models import ReportEvent, ReportRun


class ReadOnlyReportAdminMixin:
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return True

    def has_delete_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        return False

    def get_readonly_fields(self, request: HttpRequest, obj: Model | None = None) -> list[str]:
        fields = [field.name for field in cast(Any, self).model._meta.fields]
        return fields

    def get_actions(self, request: HttpRequest) -> dict[str, Any]:
        return {}


@admin.register(ReportRun)
class ReportRunAdmin(ReadOnlyReportAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "id",
        "report_type",
        "output_format",
        "redaction_mode",
        "start_date",
        "end_date",
        "row_count",
        "generated_at",
    )
    list_filter = ("report_type", "output_format", "redaction_mode")
    search_fields = ("id", "content_sha256", "generated_by_admin_id")
    ordering = ("-generated_at", "-id")

    def get_queryset(self, request: HttpRequest) -> QuerySet[ReportRun]:
        return super().get_queryset(request)


@admin.register(ReportEvent)
class ReportEventAdmin(ReadOnlyReportAdminMixin, admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("id", "report_run", "event_type", "actor_user_id", "occurred_at")
    list_filter = ("event_type",)
    search_fields = ("id", "report_run__id", "actor_user_id")
    ordering = ("-occurred_at", "-id")

    def get_queryset(self, request: HttpRequest) -> QuerySet[ReportEvent]:
        return super().get_queryset(request)
