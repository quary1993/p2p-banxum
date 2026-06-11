import type {
  AdminOperationsDashboard,
  AdminTask,
  AdminTaskEvent,
  AuditEvent,
  BorrowerEntity,
  DocumentTemplateVersion,
  KycAdminCase,
  Loan
} from "../api/generated/banxumApi";

export const adminDashboardFixture: AdminOperationsDashboard = {
  as_of: "1970-01-01T00:00:00Z",
  as_of_date: "1970-01-01",
  due_window_days: 7,
  queue_limit: 12,
  summary: {},
  currency_summaries: [],
  queues: {
    admin_tasks: [],
    kyc_reviews: [],
    bank_operations_pending: [],
    withdrawals_requested: [],
    forced_withdrawals_requested: [],
    balance_ageing_actions: [],
    funding_loans: [],
    servicing_due: [],
    loan_risk: [],
    secondary_listing_approvals: [],
    fx_settlement_deltas: [],
    failed_emails: [],
    reconciliation_breaks: []
  }
};

export const adminTasksFixture: AdminTask[] = [];

export const adminTaskEventsFixture: Record<string, AdminTaskEvent[]> = {};

export const kycManualReviewFixture: KycAdminCase[] = [];

export const borrowersFixture: BorrowerEntity[] = [];

export const loansFixture: Loan[] = [];

export const documentVersionsFixture: DocumentTemplateVersion[] = [];

export const auditEventsFixture: AuditEvent[] = [];

export const adminFormDefaults = {
  investorUserId: "",
  borrowerId: "",
  loanId: "",
  kycCaseId: "",
  withdrawalId: "",
  secondaryListingId: "",
  collectionAccount: "",
  payoutIban: "",
  payoutAccountName: "",
  borrowerName: "",
  borrowerPayeeAccount: "",
  borrowerLegalName: "",
  adminEmail: "",
  adminFullName: ""
};
