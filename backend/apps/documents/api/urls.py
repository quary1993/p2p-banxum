from __future__ import annotations

from django.urls import path

from backend.apps.documents.api.views import (
    AdminDocumentTemplateVersionListCreateView,
    AdminDocumentTemplateVersionPublishView,
    CurrentDocumentTemplateView,
    DocumentAcceptanceArtifactView,
    DocumentAcceptanceCreateView,
)

urlpatterns = [
    path(
        "templates/current/",
        CurrentDocumentTemplateView.as_view(),
        name="document-template-current",
    ),
    path(
        "admin/templates/versions/",
        AdminDocumentTemplateVersionListCreateView.as_view(),
        name="document-template-version-list-create",
    ),
    path(
        "admin/templates/versions/<uuid:template_version_id>/publish/",
        AdminDocumentTemplateVersionPublishView.as_view(),
        name="document-template-version-publish",
    ),
    path(
        "acceptances/",
        DocumentAcceptanceCreateView.as_view(),
        name="document-acceptance-create",
    ),
    path(
        "acceptances/<uuid:acceptance_id>/artifact/",
        DocumentAcceptanceArtifactView.as_view(),
        name="document-acceptance-artifact",
    ),
]
