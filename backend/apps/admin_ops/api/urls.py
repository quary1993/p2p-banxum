from __future__ import annotations

from django.urls import path

from backend.apps.admin_ops.api.views import (
    AdminBorrowerLookupView,
    AdminDocumentTemplateVersionLookupView,
    AdminInvestorLookupView,
    AdminKycCaseLookupView,
    AdminLoanLookupView,
    AdminOperationsDashboardView,
    AdminPrimaryOrderLookupView,
    AdminSecondaryListingLookupView,
    AdminTaskDetailView,
    AdminTaskEventListView,
    AdminTaskListCreateView,
    AdminUserDirectoryView,
    AdminUserDocumentArtifactView,
    AdminUserDocumentsView,
    AdminUserLookupView,
    AdminWithdrawalLookupView,
    AuditEventListView,
    ReadOnlyImpersonationStartView,
    ReconciliationBreakTaskSyncView,
)

urlpatterns = [
    path("dashboard/", AdminOperationsDashboardView.as_view(), name="admin-dashboard"),
    path("users/", AdminUserDirectoryView.as_view(), name="admin-user-directory"),
    path(
        "users/<uuid:user_id>/readonly-impersonation/",
        ReadOnlyImpersonationStartView.as_view(),
        name="admin-user-readonly-impersonation-start",
    ),
    path(
        "users/<uuid:user_id>/documents/",
        AdminUserDocumentsView.as_view(),
        name="admin-user-documents",
    ),
    path(
        "users/<uuid:user_id>/documents/<uuid:acceptance_id>/artifact/",
        AdminUserDocumentArtifactView.as_view(),
        name="admin-user-document-artifact",
    ),
    path("lookups/users/", AdminUserLookupView.as_view(), name="admin-user-lookup"),
    path("lookups/investors/", AdminInvestorLookupView.as_view(), name="admin-investor-lookup"),
    path("lookups/borrowers/", AdminBorrowerLookupView.as_view(), name="admin-borrower-lookup"),
    path("lookups/loans/", AdminLoanLookupView.as_view(), name="admin-loan-lookup"),
    path("lookups/kyc-cases/", AdminKycCaseLookupView.as_view(), name="admin-kyc-case-lookup"),
    path(
        "lookups/withdrawal-requests/",
        AdminWithdrawalLookupView.as_view(),
        name="admin-withdrawal-lookup",
    ),
    path(
        "lookups/primary-orders/",
        AdminPrimaryOrderLookupView.as_view(),
        name="admin-primary-order-lookup",
    ),
    path(
        "lookups/secondary-listings/",
        AdminSecondaryListingLookupView.as_view(),
        name="admin-secondary-listing-lookup",
    ),
    path(
        "lookups/document-template-versions/",
        AdminDocumentTemplateVersionLookupView.as_view(),
        name="admin-document-template-version-lookup",
    ),
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
