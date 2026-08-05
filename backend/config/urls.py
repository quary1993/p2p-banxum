"""Root URL configuration."""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.urls.resolvers import URLPattern, URLResolver
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns: list[URLPattern | URLResolver] = [
    path("api/v1/", include("backend.apps.platform_core.api.urls")),
    path("api/v1/auth/", include("backend.apps.accounts_auth.api.urls")),
    path("api/v1/kyc/", include("backend.apps.kyc_compliance.api.urls")),
    path("api/v1/admin-ops/", include("backend.apps.admin_ops.api.urls")),
    path("api/v1/entities/", include("backend.apps.entities.api.urls")),
    path("api/v1/loans/", include("backend.apps.loans.api.urls")),
    path("api/v1/marketplace/primary/", include("backend.apps.marketplace_primary.api.urls")),
    path("api/v1/originator-claims/", include("backend.apps.originator_claims.api.urls")),
    path("api/v1/marketplace/secondary/", include("backend.apps.secondary_market.api.urls")),
    path("api/v1/ledger/", include("backend.apps.ledger.api.urls")),
    path("api/v1/servicing/", include("backend.apps.servicing.api.urls")),
    path("api/v1/fx/", include("backend.apps.fx.api.urls")),
    path("api/v1/documents/", include("backend.apps.documents.api.urls")),
    path("api/v1/reporting/", include("backend.apps.reporting.api.urls")),
    path("api/v1/investor/portal/", include("backend.apps.investor_portal.api.urls")),
    path("api/v1/investor/smart-invest/", include("backend.apps.smart_invest.api.urls")),
]

if settings.DJANGO_ADMIN_ENABLED:
    urlpatterns.append(path("admin/django/", admin.site.urls))

if settings.API_DOCS_ENABLED:
    urlpatterns.extend(
        [
            path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
            path(
                "api/docs/",
                SpectacularSwaggerView.as_view(url_name="schema"),
                name="swagger-ui",
            ),
        ]
    )
