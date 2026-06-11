from __future__ import annotations

from typing import Any, cast

from django.db.models import Model, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.admin_ops.api.serializers import (
    AdminDashboardQuerySerializer,
    AdminOperationsDashboardSerializer,
    AdminTaskCreateRequestSerializer,
    AdminTaskEventSerializer,
    AdminTaskListQuerySerializer,
    AdminTaskSerializer,
    AdminTaskUpdateRequestSerializer,
    AuditEventQuerySerializer,
    AuditEventSerializer,
    ReconciliationBreakTaskSyncRequestSerializer,
    ReconciliationBreakTaskSyncResponseSerializer,
    serialize_admin_task,
    serialize_admin_task_event,
    serialize_audit_event,
)
from backend.apps.admin_ops.models import AdminTask
from backend.apps.admin_ops.services import (
    AdminTaskAuthorizationError,
    AdminTaskValidationError,
    CreateAdminTaskCommand,
    GetAdminDashboardCommand,
    SyncReconciliationBreakTasksCommand,
    UpdateAdminTaskCommand,
    create_admin_task,
    get_admin_operations_dashboard,
    sync_reconciliation_break_tasks,
    update_admin_task,
)
from backend.apps.platform_core.domain.access import actor_ref_for_user, is_admin_actor
from backend.apps.platform_core.models import AuditEvent
from backend.apps.platform_core.services.audit import AuditCommand, record_audit_event


def _admin_forbidden_response() -> Response:
    return Response(
        {"detail": "Only an active admin can access admin operations."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _task_queryset_from_query(data: dict[str, Any]) -> QuerySet[AdminTask]:
    queryset = AdminTask.objects.select_related("assigned_admin", "created_by").all()
    for field in ("status", "task_type", "priority", "related_object_type", "related_object_id"):
        if data.get(field):
            queryset = queryset.filter(**{field: data[field]})
    if data.get("assigned_admin_id"):
        queryset = queryset.filter(assigned_admin_id=data["assigned_admin_id"])
    if data.get("due_before"):
        queryset = queryset.filter(due_at__lte=data["due_before"])
    if data.get("due_after"):
        queryset = queryset.filter(due_at__gte=data["due_after"])
    return queryset


def _audit_search_filters(data: dict[str, Any]) -> dict[str, str | int]:
    filters: dict[str, str | int] = {}
    for key, value in data.items():
        if value is not None and value != "":
            filters[key] = value if isinstance(value, int) else str(value)
    return filters


class AdminTaskListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[AdminTaskListQuerySerializer],
        responses={200: AdminTaskSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = AdminTaskListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        queryset = _task_queryset_from_query(data)
        return Response(
            [serialize_admin_task(task) for task in queryset[: data["limit"]]],
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=AdminTaskCreateRequestSerializer,
        responses={201: AdminTaskSerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = AdminTaskCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            task = create_admin_task(
                CreateAdminTaskCommand(
                    actor=cast(Model, request.user),
                    task_type=data["task_type"],
                    title=data["title"],
                    priority=data["priority"],
                    assigned_admin_id=(
                        str(data["assigned_admin_id"]) if data.get("assigned_admin_id") else None
                    ),
                    due_at=data.get("due_at"),
                    notes=data.get("notes", ""),
                    related_object_type=data.get("related_object_type", ""),
                    related_object_id=data.get("related_object_id", ""),
                )
            )
        except AdminTaskAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except AdminTaskValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_admin_task(task), status=status.HTTP_201_CREATED)


class AdminOperationsDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[AdminDashboardQuerySerializer],
        responses={200: AdminOperationsDashboardSerializer},
    )
    def get(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = AdminDashboardQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        dashboard = get_admin_operations_dashboard(
            GetAdminDashboardCommand(
                actor=cast(Model, request.user),
                as_of=data.get("as_of"),
                due_window_days=data["due_window_days"],
                queue_limit=data["limit"],
            )
        )
        return Response(dashboard, status=status.HTTP_200_OK)


class ReconciliationBreakTaskSyncView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ReconciliationBreakTaskSyncRequestSerializer,
        responses={200: ReconciliationBreakTaskSyncResponseSerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = ReconciliationBreakTaskSyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            result = sync_reconciliation_break_tasks(
                SyncReconciliationBreakTasksCommand(
                    actor=cast(Model, request.user),
                    limit=data["limit"],
                )
            )
        except AdminTaskAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            {
                "created_count": result["created_count"],
                "existing_count": result["existing_count"],
                "skipped_count": result["skipped_count"],
                "tasks": [serialize_admin_task(task) for task in result["tasks"]],
            },
            status=status.HTTP_200_OK,
        )


class AdminTaskDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: AdminTaskSerializer})
    def get(self, request: Request, task_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        task = AdminTask.objects.filter(id=task_id).first()
        if task is None:
            return Response(
                {"detail": "Admin task does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(serialize_admin_task(task), status=status.HTTP_200_OK)

    @extend_schema(
        request=AdminTaskUpdateRequestSerializer,
        responses={200: AdminTaskSerializer},
    )
    def patch(self, request: Request, task_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = AdminTaskUpdateRequestSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        assigned_admin_id = data.get("assigned_admin_id")
        due_at = data.get("due_at")
        try:
            task = update_admin_task(
                UpdateAdminTaskCommand(
                    actor=cast(Model, request.user),
                    task_id=task_id,
                    task_type=data.get("task_type"),
                    title=data.get("title"),
                    priority=data.get("priority"),
                    status=data.get("status"),
                    assigned_admin_id=str(assigned_admin_id) if assigned_admin_id else None,
                    clear_assigned_admin=bool(
                        data.get("clear_assigned_admin")
                        or ("assigned_admin_id" in data and assigned_admin_id is None)
                    ),
                    due_at=due_at,
                    clear_due_at=bool(
                        data.get("clear_due_at") or ("due_at" in data and due_at is None)
                    ),
                    notes=data.get("notes"),
                    completion_note=data.get("completion_note"),
                )
            )
        except AdminTaskAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except AdminTaskValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_admin_task(task), status=status.HTTP_200_OK)


class AdminTaskEventListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: AdminTaskEventSerializer(many=True)})
    def get(self, request: Request, task_id: str) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        task = AdminTask.objects.filter(id=task_id).first()
        if task is None:
            return Response(
                {"detail": "Admin task does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            [serialize_admin_task_event(event) for event in task.events.all()],
            status=status.HTTP_200_OK,
        )


class AuditEventListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[AuditEventQuerySerializer],
        responses={200: AuditEventSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        if not is_admin_actor(request.user):
            return _admin_forbidden_response()
        serializer = AuditEventQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        queryset = AuditEvent.objects.all()
        for field in ("action", "target_type", "target_id", "actor_type", "actor_id"):
            if data.get(field):
                queryset = queryset.filter(**{field: data[field]})
        if data.get("occurred_from"):
            queryset = queryset.filter(occurred_at__gte=data["occurred_from"])
        if data.get("occurred_to"):
            queryset = queryset.filter(occurred_at__lte=data["occurred_to"])
        events = list(queryset[: data["limit"]])
        record_audit_event(
            AuditCommand(
                actor=actor_ref_for_user(request.user),
                action="audit_event.search_performed",
                target_type="AuditEvent",
                metadata={
                    "filters": _audit_search_filters(data),
                    "result_count": len(events),
                },
            )
        )
        return Response(
            [serialize_audit_event(event) for event in events],
            status=status.HTTP_200_OK,
        )
