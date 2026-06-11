from __future__ import annotations

from django.urls import path

from backend.apps.admin_ops.api.views import (
    AdminOperationsDashboardView,
    AdminTaskDetailView,
    AdminTaskEventListView,
    AdminTaskListCreateView,
    AuditEventListView,
    ReconciliationBreakTaskSyncView,
)

urlpatterns = [
    path("dashboard/", AdminOperationsDashboardView.as_view(), name="admin-dashboard"),
    path(
        "reconciliation-break-tasks/sync/",
        ReconciliationBreakTaskSyncView.as_view(),
        name="admin-reconciliation-break-task-sync",
    ),
    path("tasks/", AdminTaskListCreateView.as_view(), name="admin-task-list-create"),
    path("tasks/<uuid:task_id>/", AdminTaskDetailView.as_view(), name="admin-task-detail"),
    path(
        "tasks/<uuid:task_id>/events/",
        AdminTaskEventListView.as_view(),
        name="admin-task-events",
    ),
    path("audit-events/", AuditEventListView.as_view(), name="admin-audit-event-list"),
]
