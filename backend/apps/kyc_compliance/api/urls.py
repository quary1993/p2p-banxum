from __future__ import annotations

from django.urls import path

from backend.apps.kyc_compliance.api.declaration_views import (
    ComplianceReviewDecisionView,
    ComplianceReviewListView,
    InvestorComplianceFileView,
    InvestorDeclarationView,
    InvestorReverificationCompleteView,
    InvestorReverificationView,
    StaffRolesView,
)
from backend.apps.kyc_compliance.api.views import (
    DiditWebhookView,
    KycAdminManualReviewDecisionView,
    KycAdminManualReviewListView,
    KycSessionCreateView,
    KycStatusView,
)

urlpatterns = [
    path("status/", KycStatusView.as_view(), name="kyc-status"),
    path("session/", KycSessionCreateView.as_view(), name="kyc-session-create"),
    path(
        "admin/manual-reviews/",
        KycAdminManualReviewListView.as_view(),
        name="kyc-admin-manual-review-list",
    ),
    path(
        "admin/cases/<uuid:case_id>/manual-review/",
        KycAdminManualReviewDecisionView.as_view(),
        name="kyc-admin-manual-review-decision",
    ),
    path("webhooks/didit/", DiditWebhookView.as_view(), name="kyc-didit-webhook"),
    # 18.10: declarations, compliance reviews, re-verification dates, staff roles.
    path("declarations/", InvestorDeclarationView.as_view(), name="kyc-declarations"),
    path(
        "admin/compliance/reviews/",
        ComplianceReviewListView.as_view(),
        name="kyc-admin-compliance-reviews",
    ),
    path(
        "admin/compliance/reviews/<uuid:review_id>/decision/",
        ComplianceReviewDecisionView.as_view(),
        name="kyc-admin-compliance-review-decision",
    ),
    path(
        "admin/compliance/investors/<uuid:investor_id>/",
        InvestorComplianceFileView.as_view(),
        name="kyc-admin-compliance-investor",
    ),
    path(
        "admin/compliance/investors/<uuid:investor_id>/reverification/",
        InvestorReverificationView.as_view(),
        name="kyc-admin-compliance-reverification",
    ),
    path(
        "admin/compliance/investors/<uuid:investor_id>/reverification/complete/",
        InvestorReverificationCompleteView.as_view(),
        name="kyc-admin-compliance-reverification-complete",
    ),
    path(
        "admin/staff-roles/<uuid:user_id>/", StaffRolesView.as_view(), name="kyc-admin-staff-roles"
    ),
]
