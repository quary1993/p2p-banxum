from __future__ import annotations

from django.urls import path

from backend.apps.platform_core.api.views import (
    HealthView,
    QaDevModeAdvanceView,
    QaDevModeEnableView,
    QaDevModeRevertView,
    QaDevModeStateView,
)

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("qa/dev-mode/", QaDevModeStateView.as_view(), name="qa-dev-mode-state"),
    path("qa/dev-mode/enable/", QaDevModeEnableView.as_view(), name="qa-dev-mode-enable"),
    path("qa/dev-mode/advance/", QaDevModeAdvanceView.as_view(), name="qa-dev-mode-advance"),
    path("qa/dev-mode/revert/", QaDevModeRevertView.as_view(), name="qa-dev-mode-revert"),
]
