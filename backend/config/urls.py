"""Root URL configuration."""

from __future__ import annotations

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/django/", admin.site.urls),
    path("api/v1/", include("backend.apps.platform_core.api.urls")),
    path("api/v1/auth/", include("backend.apps.accounts_auth.api.urls")),
    path("api/v1/kyc/", include("backend.apps.kyc_compliance.api.urls")),
    path("api/v1/admin-ops/", include("backend.apps.admin_ops.api.urls")),
    path("api/v1/entities/", include("backend.apps.entities.api.urls")),
    path("api/v1/loans/", include("backend.apps.loans.api.urls")),
    path("api/v1/marketplace/primary/", include("backend.apps.marketplace_primary.api.urls")),
    path("api/v1/ledger/", include("backend.apps.ledger.api.urls")),
    path("api/v1/servicing/", include("backend.apps.servicing.api.urls")),
    path("api/v1/documents/", include("backend.apps.documents.api.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
