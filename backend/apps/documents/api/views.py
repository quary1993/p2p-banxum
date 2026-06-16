from __future__ import annotations

from typing import Any, cast

from django.db.models import CharField, Model, Q
from django.db.models.functions import Cast
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.apps.documents.api.serializers import (
    AdminDocumentTemplateVersionListQuerySerializer,
    DocumentAcceptanceArtifactRequestSerializer,
    DocumentAcceptanceCreateRequestSerializer,
    DocumentAcceptanceEvidenceSerializer,
    DocumentArtifactResponseSerializer,
    DocumentCurrentTemplateQuerySerializer,
    DocumentTemplateVersionCreateRequestSerializer,
    DocumentTemplateVersionPublishRequestSerializer,
    DocumentTemplateVersionSerializer,
    PublicDocumentTemplateVersionSerializer,
    serialize_acceptance,
    serialize_public_template_version,
    serialize_rendered_artifact,
    serialize_template_version,
)
from backend.apps.documents.models import DocumentTemplateVersion
from backend.apps.documents.services import (
    AcceptDocumentTermsCommand,
    CreateDocumentTemplateVersionCommand,
    DocumentAuthorizationError,
    DocumentValidationError,
    PublishDocumentTemplateVersionCommand,
    RenderDocumentAcceptanceArtifactCommand,
    accept_document_terms,
    create_document_template_version,
    get_current_document_template,
    publish_document_template_version,
    render_document_acceptance_artifact,
)
from backend.apps.platform_core.api.request_meta import client_ip, user_agent
from backend.apps.platform_core.domain.access import is_superadmin_actor


def _superadmin_forbidden_response() -> Response:
    return Response(
        {"detail": "Only an active superadmin can manage document templates."},
        status=status.HTTP_403_FORBIDDEN,
    )


class CurrentDocumentTemplateView(APIView):
    authentication_classes: list[type] = []
    permission_classes: list[type] = []

    @extend_schema(
        parameters=[DocumentCurrentTemplateQuerySerializer],
        responses={200: PublicDocumentTemplateVersionSerializer},
    )
    def get(self, request: Request) -> Response:
        serializer = DocumentCurrentTemplateQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            version = get_current_document_template(
                category=data["category"],
                template_key=data["template_key"],
                language=data["language"],
            )
        except DocumentValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_public_template_version(version), status=status.HTTP_200_OK)


class AdminDocumentTemplateVersionListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[AdminDocumentTemplateVersionListQuerySerializer],
        responses={200: DocumentTemplateVersionSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        if not is_superadmin_actor(request.user):
            return _superadmin_forbidden_response()
        serializer = AdminDocumentTemplateVersionListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        versions = (
            DocumentTemplateVersion.objects.select_related("template")
            .filter(
                template__category=data["category"],
                template__template_key=data["template_key"],
                template__language=data["language"],
            )
            .order_by("-version_number", "-created_at", "-id")
        )
        query = data.get("q", "").strip()
        if query:
            versions = versions.annotate(id_text=Cast("id", output_field=CharField())).filter(
                Q(id_text__icontains=query)
                | Q(title__icontains=query)
                | Q(content_hash__icontains=query)
                | Q(legal_review_reference__icontains=query)
                | Q(template__name__icontains=query)
                | Q(template__template_key__icontains=query)
            )
        return Response(
            [serialize_template_version(version) for version in versions[: data["limit"]]],
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=DocumentTemplateVersionCreateRequestSerializer,
        responses={201: DocumentTemplateVersionSerializer},
    )
    def post(self, request: Request) -> Response:
        if not is_superadmin_actor(request.user):
            return _superadmin_forbidden_response()
        serializer = DocumentTemplateVersionCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            version = create_document_template_version(
                CreateDocumentTemplateVersionCommand(
                    actor=cast(Model, request.user),
                    category=data["category"],
                    template_key=data["template_key"],
                    language=data["language"],
                    name=data["name"],
                    description=data.get("description", ""),
                    title=data["title"],
                    body=data["body"],
                    checkbox_labels=data["checkbox_labels"],
                    variable_schema=data.get("variable_schema"),
                    publish_now=data.get("publish_now", False),
                    legal_review_reference=data.get("legal_review_reference", ""),
                    metadata=data.get("metadata"),
                    note=data.get("note", ""),
                )
            )
        except DocumentAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except DocumentValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_template_version(version), status=status.HTTP_201_CREATED)


class AdminDocumentTemplateVersionPublishView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=DocumentTemplateVersionPublishRequestSerializer,
        responses={200: DocumentTemplateVersionSerializer},
    )
    def post(self, request: Request, template_version_id: str) -> Response:
        if not is_superadmin_actor(request.user):
            return _superadmin_forbidden_response()
        serializer = DocumentTemplateVersionPublishRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            version = publish_document_template_version(
                PublishDocumentTemplateVersionCommand(
                    actor=cast(Model, request.user),
                    template_version_id=template_version_id,
                    legal_review_reference=data.get("legal_review_reference", ""),
                    metadata=data.get("metadata"),
                    note=data.get("note", ""),
                )
            )
        except DocumentAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except DocumentValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_template_version(version), status=status.HTTP_200_OK)


class DocumentAcceptanceCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=DocumentAcceptanceCreateRequestSerializer,
        responses={201: DocumentAcceptanceEvidenceSerializer},
    )
    def post(self, request: Request) -> Response:
        serializer = DocumentAcceptanceCreateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            acceptance = accept_document_terms(
                AcceptDocumentTermsCommand(
                    actor=cast(Model, request.user),
                    category=data["category"],
                    template_key=data["template_key"],
                    language=data["language"],
                    expected_template_version_id=(
                        str(data["expected_template_version_id"])
                        if data.get("expected_template_version_id")
                        else None
                    ),
                    accepted_checkbox_labels=data["accepted_checkbox_labels"],
                    context_type=data["context_type"],
                    context_id=data["context_id"],
                    data_snapshot=data.get("data_snapshot"),
                    ip_address=client_ip(request),
                    user_agent=user_agent(request),
                    idempotency_key=data["idempotency_key"],
                    metadata=data.get("metadata"),
                )
            )
        except DocumentAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except DocumentValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_acceptance(acceptance), status=status.HTTP_201_CREATED)


class DocumentAcceptanceArtifactView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=DocumentAcceptanceArtifactRequestSerializer,
        responses={200: DocumentArtifactResponseSerializer},
    )
    def post(self, request: Request, acceptance_id: str) -> Response:
        serializer = DocumentAcceptanceArtifactRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data: dict[str, Any] = serializer.validated_data
        try:
            artifact = render_document_acceptance_artifact(
                RenderDocumentAcceptanceArtifactCommand(
                    actor=cast(Model, request.user),
                    acceptance_id=acceptance_id,
                    output_format=data.get("output_format", "pdf"),
                    purpose="investor_download",
                    metadata={"request_path": request.path},
                )
            )
        except DocumentAuthorizationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except DocumentValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_rendered_artifact(artifact), status=status.HTTP_200_OK)
