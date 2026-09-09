from __future__ import annotations

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, get_user_model, login, logout
from django.http import FileResponse, Http404
from django.utils.crypto import constant_time_compare
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.platform_core.api.serializers import (
    HealthResponseSerializer,
    QaDevModeAdvanceRequestSerializer,
    QaDevModeEnableRequestSerializer,
    QaDevModeRestoreResponseSerializer,
    QaDevModeRevertRequestSerializer,
    QaDevModeStateSerializer,
    StoryImageSerializer,
    StoryImageUploadSerializer,
)
from backend.apps.platform_core.domain.access import is_admin_actor
from backend.apps.platform_core.models.story_images import StoryImage
from backend.apps.platform_core.services.qa_dev_mode import (
    AdvanceQaDevModeTimeCommand,
    CreateQaSnapshotCommand,
    EnableQaDevModeCommand,
    QaDevModeAuthorizationError,
    QaDevModeValidationError,
    RevertQaDevModeCommand,
    advance_qa_dev_mode_time,
    create_qa_snapshot,
    enable_qa_dev_mode,
    get_qa_dev_mode_state,
    qa_controls_available,
    qa_deployment_available,
    revert_qa_dev_mode,
    serialize_qa_dev_mode_state,
)
from backend.apps.platform_core.services.qa_guard import QaEnvironmentBusy, qa_environment_guard
from backend.apps.platform_core.services.story_images import (
    StoreStoryImageCommand,
    StoryImageError,
    store_story_image,
    story_image_payload,
)


class HealthView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(responses=HealthResponseSerializer)
    def get(self, request):  # type: ignore[no-untyped-def]
        return Response(
            {
                "status": "ok",
                "platform": settings.PLATFORM_BRAND_NAME,
                "operator": settings.LEGAL_OPERATOR_NAME,
                "timezone": settings.TIME_ZONE,
                "environment": settings.ENVIRONMENT,
            }
        )


def _qa_error_response(exc: Exception) -> Response:
    if isinstance(exc, QaDevModeAuthorizationError):
        return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class QaAdminPermission(BasePermission):
    message = "Only an active admin can manage QA mode."

    def has_permission(self, request, view):  # type: ignore[no-untyped-def]
        if not qa_deployment_available():
            raise Http404
        return is_admin_actor(request.user)


class QaDevModeStateView(APIView):
    permission_classes = [IsAuthenticated, QaAdminPermission]

    @extend_schema(responses={200: QaDevModeStateSerializer})
    def get(self, request):  # type: ignore[no-untyped-def]
        state = get_qa_dev_mode_state()
        return Response(QaDevModeStateSerializer(serialize_qa_dev_mode_state(state)).data)


class QaDevModeEnableView(APIView):
    permission_classes = [IsAuthenticated, QaAdminPermission]

    @extend_schema(
        request=QaDevModeEnableRequestSerializer,
        responses={200: QaDevModeStateSerializer},
    )
    def post(self, request):  # type: ignore[no-untyped-def]
        serializer = QaDevModeEnableRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            state = enable_qa_dev_mode(
                EnableQaDevModeCommand(
                    actor=request.user,
                    note=serializer.validated_data.get("note", ""),
                )
            )
        except (QaDevModeAuthorizationError, QaDevModeValidationError) as exc:
            return _qa_error_response(exc)
        return Response(QaDevModeStateSerializer(serialize_qa_dev_mode_state(state)).data)


class QaDevModeAdvanceView(APIView):
    permission_classes = [IsAuthenticated, QaAdminPermission]

    @extend_schema(
        request=QaDevModeAdvanceRequestSerializer,
        responses={200: QaDevModeStateSerializer},
    )
    def post(self, request):  # type: ignore[no-untyped-def]
        serializer = QaDevModeAdvanceRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            state = advance_qa_dev_mode_time(
                AdvanceQaDevModeTimeCommand(
                    actor=request.user,
                    days=serializer.validated_data["days"],
                )
            )
        except (QaDevModeAuthorizationError, QaDevModeValidationError) as exc:
            return _qa_error_response(exc)
        return Response(QaDevModeStateSerializer(serialize_qa_dev_mode_state(state)).data)


class QaDevModeSnapshotView(APIView):
    permission_classes = [IsAuthenticated, QaAdminPermission]

    @extend_schema(request=None, responses={200: QaDevModeStateSerializer})
    def post(self, request):  # type: ignore[no-untyped-def]
        try:
            state = create_qa_snapshot(CreateQaSnapshotCommand(actor=request.user))
        except (QaDevModeAuthorizationError, QaDevModeValidationError) as exc:
            return _qa_error_response(exc)
        return Response(QaDevModeStateSerializer(serialize_qa_dev_mode_state(state)).data)


class QaDevModeRevertView(APIView):
    permission_classes = [IsAuthenticated, QaAdminPermission]

    @extend_schema(
        request=QaDevModeRevertRequestSerializer,
        responses={200: QaDevModeRestoreResponseSerializer},
    )
    def post(self, request):  # type: ignore[no-untyped-def]
        serializer = QaDevModeRevertRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with qa_environment_guard(exclusive=True):
                actor = request.user
                session_hash = actor.get_session_auth_hash()
                target = revert_qa_dev_mode(
                    RevertQaDevModeCommand(
                        actor=actor,
                        confirmation=serializer.validated_data["confirmation"],
                        target=serializer.validated_data["target"],
                    )
                )
                restored = get_user_model().objects.filter(pk=actor.pk).first()
                requires_login = True
                if hasattr(request._request, "session"):
                    backend = request.session.get(
                        BACKEND_SESSION_KEY, "django.contrib.auth.backends.ModelBackend"
                    )
                    if (
                        restored is not None
                        and qa_controls_available(restored)
                        and constant_time_compare(session_hash, restored.get_session_auth_hash())
                    ):
                        # Renew only the caller using the restored roles and credentials.
                        request.session.flush()
                        login(request._request, restored, backend=backend)
                        requires_login = False
                    else:
                        logout(request._request)
        except (QaDevModeAuthorizationError, QaDevModeValidationError, QaEnvironmentBusy) as exc:
            return _qa_error_response(exc)
        state = get_qa_dev_mode_state()
        return Response(
            QaDevModeRestoreResponseSerializer(
                {
                    **serialize_qa_dev_mode_state(state),
                    "requires_login": requires_login,
                    "restored_target": target,
                }
            ).data
        )


class AdminStoryImageUploadView(APIView):
    """Admin-only intake for story images (verified, re-encoded, <= 1 MB)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=StoryImageUploadSerializer, responses={201: StoryImageSerializer})
    def post(self, request):  # type: ignore[no-untyped-def]
        if not is_admin_actor(request.user):
            return Response({"detail": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)
        serializer = StoryImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]
        try:
            image = store_story_image(
                StoreStoryImageCommand(
                    upload=upload,
                    original_filename=str(getattr(upload, "name", "") or ""),
                    uploaded_by_id=str(request.user.id),
                )
            )
        except StoryImageError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            StoryImageSerializer(story_image_payload(image)).data,
            status=status.HTTP_201_CREATED,
        )


class StoryImageContentView(APIView):
    """Serve a story image to any signed-in user; never public, never cached shared."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={(200, "image/jpeg"): bytes})
    def get(self, request, image_id):  # type: ignore[no-untyped-def]
        try:
            image = StoryImage.objects.get(id=image_id)
        except (StoryImage.DoesNotExist, ValueError, TypeError) as exc:
            raise Http404 from exc
        try:
            handle = image.file.open("rb")
        except (FileNotFoundError, OSError) as exc:
            raise Http404 from exc
        response = FileResponse(handle, content_type=image.content_type)
        response["Cache-Control"] = "private, max-age=3600"
        response["Content-Disposition"] = f'inline; filename="{image.id}.jpg"'
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response
