from __future__ import annotations

from django.urls import path

from backend.apps.platform_core.api.views import (
    AdminLoanStatusDaysView,
    AdminPlatformFeaturesView,
    AdminSettlementCalendarConfirmView,
    AdminSettlementCalendarDayAddView,
    AdminSettlementCalendarDayRemoveView,
    AdminSettlementCalendarView,
    AdminStoryImageUploadView,
    HealthView,
    QaDevModeAdvanceView,
    QaDevModeEnableView,
    QaDevModeRevertView,
    QaDevModeSnapshotView,
    QaDevModeStateView,
    StoryImageContentView,
)

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("qa/dev-mode/", QaDevModeStateView.as_view(), name="qa-dev-mode-state"),
    path("qa/dev-mode/enable/", QaDevModeEnableView.as_view(), name="qa-dev-mode-enable"),
    path("qa/dev-mode/advance/", QaDevModeAdvanceView.as_view(), name="qa-dev-mode-advance"),
    path("qa/dev-mode/revert/", QaDevModeRevertView.as_view(), name="qa-dev-mode-revert"),
    path("qa/dev-mode/snapshot/", QaDevModeSnapshotView.as_view(), name="qa-dev-mode-snapshot"),
    path(
        "admin/loan-status-days/",
        AdminLoanStatusDaysView.as_view(),
        name="admin-loan-status-days",
    ),
    path(
        "admin/settlement-calendars/",
        AdminSettlementCalendarView.as_view(),
        name="admin-settlement-calendar",
    ),
    path(
        "admin/settlement-calendars/days/",
        AdminSettlementCalendarDayAddView.as_view(),
        name="admin-settlement-calendar-day-add",
    ),
    path(
        "admin/settlement-calendars/days/remove/",
        AdminSettlementCalendarDayRemoveView.as_view(),
        name="admin-settlement-calendar-day-remove",
    ),
    path(
        "admin/settlement-calendars/confirm/",
        AdminSettlementCalendarConfirmView.as_view(),
        name="admin-settlement-calendar-confirm",
    ),
    path(
        "admin/platform-features/",
        AdminPlatformFeaturesView.as_view(),
        name="admin-platform-features",
    ),
    path(
        "admin/story-images/",
        AdminStoryImageUploadView.as_view(),
        name="admin-story-image-upload",
    ),
    path(
        "story-images/<uuid:image_id>/",
        StoryImageContentView.as_view(),
        name="story-image-content",
    ),
]
