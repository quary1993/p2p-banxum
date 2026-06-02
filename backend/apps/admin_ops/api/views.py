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
    AdminTaskCreateRequestSerializer,
    AdminTaskEventSerializer,
    AdminTaskListQuerySerializer,
    AdminTaskSerializer,
    AdminTaskUpdateRequestSerializer,
    AuditEventQuerySerializer,
    AuditEventSerializer,
    serialize_admin_task,
    serialize_admin_task_event,
    serialize_audit_event,
)
from backend.apps.admin_ops.models import AdminTask
from backend.apps.admin_ops.services import (
    AdminTaskAuthorizationError,
    AdminTaskValidationError,
    CreateAdminTaskCommand,
    UpdateAdminTaskCommand,
    create_admin_task,
    update_admin_task,
)
from backend.apps.platform_core.models import AuditEvent


def _is_admin_request_user(user: Any) -> bool:
    return (
        bool(getattr(user, "is_active", False))
        and bool(getattr(user, "is_staff", False))
        and str(getattr(user, "account_type", "")) in {"admin", "superadmin"}
        and str(getattr(user, "status", "")) not in {"restricted", "locked", "closed"}
    )


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


class AdminTaskListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[AdminTaskListQuerySerializer],
        responses={200: AdminTaskSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        if not _is_admin_request_user(request.user):
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
        if not _is_admin_request_user(request.user):
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


class AdminTaskDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: AdminTaskSerializer})
    def get(self, request: Request, task_id: str) -> Response:
        if not _is_admin_request_user(request.user):
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
        if not _is_admin_request_user(request.user):
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
        if not _is_admin_request_user(request.user):
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
        if not _is_admin_request_user(request.user):
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
        return Response(
            [serialize_audit_event(event) for event in queryset[: data["limit"]]],
            status=status.HTTP_200_OK,
        )
