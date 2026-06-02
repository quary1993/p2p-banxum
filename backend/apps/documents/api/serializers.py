from __future__ import annotations

from typing import Any

from rest_framework import serializers

from backend.apps.documents.models import (
    DocumentAcceptanceEvidence,
    DocumentCategory,
    DocumentTemplate,
    DocumentTemplateVersion,
)


class DocumentTemplateSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    category = serializers.CharField()
    template_key = serializers.CharField()
    language = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    current_published_version_id = serializers.UUIDField(allow_null=True)
    created_by_superadmin_id = serializers.UUIDField()
    updated_by_superadmin_id = serializers.UUIDField(allow_null=True)
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class DocumentTemplateVersionSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    template = DocumentTemplateSerializer()
    version_number = serializers.IntegerField()
    status = serializers.CharField()
    title = serializers.CharField()
    body = serializers.CharField()
    checkbox_labels = serializers.JSONField()
    variable_schema = serializers.JSONField()
    content_hash = serializers.CharField()
    created_by_superadmin_id = serializers.UUIDField()
    source_version_id = serializers.UUIDField(allow_null=True)
    published_at = serializers.DateTimeField(allow_null=True)
    legal_review_reference = serializers.CharField()
    metadata = serializers.JSONField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class DocumentAcceptanceEvidenceSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    user_id = serializers.UUIDField()
    category = serializers.CharField()
    template_id = serializers.UUIDField(source="template.id")
    template_version_id = serializers.UUIDField(source="template_version.id")
    template_version_number = serializers.IntegerField()
    template_hash = serializers.CharField()
    context_type = serializers.CharField()
    context_id = serializers.CharField()
    accepted_checkbox_labels = serializers.JSONField()
    data_snapshot = serializers.JSONField()
    accepted_at = serializers.DateTimeField()
    ip_address = serializers.IPAddressField(allow_null=True)
    user_agent = serializers.CharField()
    idempotency_key = serializers.CharField(allow_null=True)
    metadata = serializers.JSONField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class DocumentCurrentTemplateQuerySerializer(serializers.Serializer[Any]):
    category = serializers.ChoiceField(choices=DocumentCategory.choices)
    template_key = serializers.CharField(required=False, default="default", max_length=128)
    language = serializers.CharField(required=False, default="en", max_length=8)


class DocumentTemplateVersionCreateRequestSerializer(serializers.Serializer[Any]):
    category = serializers.ChoiceField(choices=DocumentCategory.choices)
    template_key = serializers.CharField(required=False, default="default", max_length=128)
    language = serializers.CharField(required=False, default="en", max_length=8)
    name = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True)
    title = serializers.CharField(max_length=255)
    body = serializers.CharField()
    checkbox_labels = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    variable_schema = serializers.JSONField(required=False)
    publish_now = serializers.BooleanField(required=False, default=False)
    legal_review_reference = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)
    note = serializers.CharField(required=False, allow_blank=True)


class DocumentTemplateVersionPublishRequestSerializer(serializers.Serializer[Any]):
    legal_review_reference = serializers.CharField(required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False)
    note = serializers.CharField(required=False, allow_blank=True)


class DocumentAcceptanceCreateRequestSerializer(serializers.Serializer[Any]):
    category = serializers.ChoiceField(choices=DocumentCategory.choices)
    template_key = serializers.CharField(required=False, default="default", max_length=128)
    language = serializers.CharField(required=False, default="en", max_length=8)
    expected_template_version_id = serializers.UUIDField(required=False)
    accepted_checkbox_labels = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False,
    )
    context_type = serializers.CharField(max_length=64)
    context_id = serializers.CharField(max_length=128)
    data_snapshot = serializers.JSONField(required=False)
    idempotency_key = serializers.CharField(max_length=160)
    metadata = serializers.JSONField(required=False)


def serialize_template(template: DocumentTemplate) -> dict[str, Any]:
    return dict(DocumentTemplateSerializer(template).data)


def serialize_template_version(version: DocumentTemplateVersion) -> dict[str, Any]:
    return dict(DocumentTemplateVersionSerializer(version).data)


def serialize_acceptance(acceptance: DocumentAcceptanceEvidence) -> dict[str, Any]:
    return dict(DocumentAcceptanceEvidenceSerializer(acceptance).data)
