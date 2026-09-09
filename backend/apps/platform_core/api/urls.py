from __future__ import annotations

from django.urls import path

from backend.apps.platform_core.api.views import (
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
