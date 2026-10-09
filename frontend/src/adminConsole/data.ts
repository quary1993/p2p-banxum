import {
  useV1AdminOpsAuditEventsList,
  useV1AdminOpsDashboardRetrieve,
  useV1AdminOpsLookupsBorrowersList,
  useV1AdminOpsLookupsDocumentTemplateVersionsList,
  useV1AdminOpsLookupsInvestorsList,
  useV1AdminOpsLookupsKycCasesList,
  useV1AdminOpsLookupsLoansList,
  useV1AdminOpsLookupsPrimaryOrdersList,
  useV1AdminOpsLookupsSecondaryListingsList,
  useV1AdminOpsLookupsUsersList,
  useV1AdminOpsLookupsWithdrawalRequestsList,
  useV1AdminOpsTasksEventsList,
  useV1AdminOpsTasksList,
  useV1AdminOpsUsersRetrieve,
  useV1DocumentsAdminTemplatesVersionsList,
  useV1EntitiesAdminBorrowersList,
  useV1FxAdminDeltaReportRetrieve,
  useV1FxAdminRealizedSettlementReportRetrieve,
  useV1KycAdminManualReviewsList,
  useV1LedgerAdminCollectionAccountsList,
  useV1LedgerAdminInvestorBalanceSummaryRetrieve,
  useV1LedgerAdminPayoutInstructionsList,
  useV1LedgerAdminPayoutInstructionsRetrieve,
  useV1LedgerAdminWithdrawalRequestsHistoryRetrieve,
  useV1LoansAdminLoansList,
  useV1LoansAdminLoansRetrieve,
  useV1ServicingAdminRiskNotesList,
  type AdminLookupResult,
  type AdminPayoutInstructionRow,
  type CollectionAccount,
  type V1AdminOpsAuditEventsListParams,
  type V1AdminOpsTasksListParams,
  type V1AdminOpsUsersRetrieveParams,
  type V1AdminOpsDashboardRetrieveParams,
  type V1AdminOpsLookupsBorrowersListParams,
  type V1AdminOpsLookupsDocumentTemplateVersionsListParams,
  type V1AdminOpsLookupsInvestorsListParams,
  type V1AdminOpsLookupsKycCasesListParams,
  type V1AdminOpsLookupsLoansListParams,
  type V1AdminOpsLookupsPrimaryOrdersListParams,
  type V1AdminOpsLookupsSecondaryListingsListParams,
  type V1AdminOpsLookupsUsersListParams,
  type V1AdminOpsLookupsWithdrawalRequestsListParams,
  type V1DocumentsAdminTemplatesVersionsListParams,
  type V1EntitiesAdminBorrowersListParams,
  type V1FxAdminDeltaReportRetrieveParams,
  type V1FxAdminRealizedSettlementReportRetrieveParams,
  type V1LedgerAdminInvestorBalanceSummaryRetrieveParams,
  type V1LedgerAdminPayoutInstructionsListParams,
  type V1LedgerAdminWithdrawalRequestsHistoryRetrieveParams,
  type V1LoansAdminLoansListParams,
  type V1ServicingAdminRiskNotesListParams,
  useV1MarketplaceSecondaryAdminListingsList,
  type V1MarketplaceSecondaryAdminListingsListParams
} from "../api/generated/banxumApi";
import { isFixturePreview } from "../investorPortal/data";
import {
  adminDashboardFixture,
  auditEventsFixture,
  borrowersFixture,
  documentVersionsFixture,
  kycManualReviewFixture,
  loansFixture,
  adminTaskEventsFixture,
  adminTasksFixture,
  adminUserDirectoryFixture,
  adminSecondaryListingsFixture,
  adminWithdrawalHistoryFixture
} from "./adminFixtures";

const adminQueryDefaults = {
  enabled: !isFixturePreview,
  retry: false,
  staleTime: 0
};

export function adminPreviewQuery<T>(fixture: T) {
  return {
    ...adminQueryDefaults,
    // Admin preview fixtures are review-only placeholder data. Never use
    // initialData here; live admin screens must fetch immediately.
    placeholderData: isFixturePreview ? fixture : undefined
  };
}

const emptyLookupFixture: AdminLookupResult[] = [];

export function isWithdrawalQueueItem(item: {
  kind: string;
  object_type: string;
}): boolean {
  // The dashboard API emits kind="withdrawal_request" with
  // object_type="InvestorWithdrawalRequest" (the model name). Accept either so
  // the executable-withdrawal affordances cannot silently disappear again if
  // one of the two fields changes shape.
  return (
    item.object_type === "InvestorWithdrawalRequest" || item.kind === "withdrawal_request"
  );
}

/** Display name of an admin task type. Payout-IBAN checks are called "IBAN verification". */
export function taskTypeLabel(taskType: string) {
  if (taskType === "payout_instruction_verification") return "IBAN Verification";
  return taskType.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function statusLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

/** "Open → Resolved" only for a real status change; other task edits carry no status pair. */
export function taskEventStatusText(event: { previous_status: string; new_status: string }) {
  if (event.previous_status && event.new_status && event.previous_status !== event.new_status) {
    return `${statusLabel(event.previous_status)} → ${statusLabel(event.new_status)}`;
  }
  if (!event.previous_status && event.new_status) return statusLabel(event.new_status);
  return "";
}

/**
 * Dashboard queues overlap: a forced withdrawal is returned both in
 * "withdrawals_requested" (every requested withdrawal) and in
 * "forced_withdrawals_requested" (the forced subset). Lists and counts that
 * merge queues must show each record once.
 */
export function uniqueQueueItems<T extends { kind: string; id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = `${item.kind}:${item.id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function lookupEnabled(params: { q?: string; iban?: string } | undefined, enabled = true) {
  const qReady = (params?.q ?? "").trim().length >= 3;
  const ibanReady = (params?.iban ?? "").replace(/\s/g, "").length >= 3;
  return enabled && !isFixturePreview && (qReady || ibanReady);
}

export function useAdminOperationsDashboardData(
  params: V1AdminOpsDashboardRetrieveParams = { due_window_days: 7, limit: 12 }
) {
  return useV1AdminOpsDashboardRetrieve(params, {
    query: adminPreviewQuery(adminDashboardFixture)
  });
}

export function useAdminTasksData(params: V1AdminOpsTasksListParams = { limit: 100 }) {
  const financeTaskTypes = new Set([
    "payment_reconciliation",
    "payout_instruction_verification",
    "fx_settlement"
  ]);
  const fixture = adminTasksFixture.filter((task) => {
    if (params.status && task.status !== params.status) return false;
    if (params.task_type && task.task_type !== params.task_type) return false;
    if (params.priority && task.priority !== params.priority) return false;
    if (params.pending_only && task.is_terminal) return false;
    if (params.workstream === "finance" && !financeTaskTypes.has(task.task_type)) return false;
    return true;
  });
  return useV1AdminOpsTasksList(params, {
    query: adminPreviewQuery(fixture)
  });
}

export function useAdminSecondaryListingsData(params: V1MarketplaceSecondaryAdminListingsListParams = { limit: 100 }) {
  return useV1MarketplaceSecondaryAdminListingsList(params, {
    query: adminPreviewQuery(
      params.status
        ? adminSecondaryListingsFixture.filter((row) => row.status === params.status)
        : adminSecondaryListingsFixture
    )
  });
}

export function useAdminUsersDirectoryData(
  params: V1AdminOpsUsersRetrieveParams = { limit: 25, offset: 0 },
  enabled = true
) {
  return useV1AdminOpsUsersRetrieve(params, {
    query: {
      ...adminPreviewQuery({
        ...adminUserDirectoryFixture,
        limit: params.limit ?? 25,
        offset: params.offset ?? 0
      }),
      enabled: !isFixturePreview && enabled
    }
  });
}

export function useAdminTaskEventsData(taskId: string | null) {
  const fixture = taskId ? (adminTaskEventsFixture[taskId] ?? []) : [];
  return useV1AdminOpsTasksEventsList(taskId ?? "preview-no-task", {
    query: {
      ...adminPreviewQuery(fixture),
      enabled: !isFixturePreview && Boolean(taskId)
    }
  });
}

export function useAdminUserLookupData(params: V1AdminOpsLookupsUsersListParams, enabled = true) {
  return useV1AdminOpsLookupsUsersList(params, {
    query: {
      ...adminPreviewQuery(emptyLookupFixture),
      enabled: lookupEnabled(params, enabled)
    }
  });
}

export function useAdminInvestorLookupData(params: V1AdminOpsLookupsInvestorsListParams, enabled = true) {
  return useV1AdminOpsLookupsInvestorsList(params, {
    query: {
      ...adminPreviewQuery(emptyLookupFixture),
      enabled: lookupEnabled(params, enabled)
    }
  });
}

export function useAdminBorrowerLookupData(params: V1AdminOpsLookupsBorrowersListParams, enabled = true) {
  return useV1AdminOpsLookupsBorrowersList(params, {
    query: {
      ...adminPreviewQuery(emptyLookupFixture),
      enabled: lookupEnabled(params, enabled)
    }
  });
}

export function useAdminLoanLookupData(params: V1AdminOpsLookupsLoansListParams, enabled = true) {
  return useV1AdminOpsLookupsLoansList(params, {
    query: {
      ...adminPreviewQuery(emptyLookupFixture),
      enabled: lookupEnabled(params, enabled) || (!isFixturePreview && enabled && Boolean(params.borrower_id))
    }
  });
}

export function useAdminKycCaseLookupData(params: V1AdminOpsLookupsKycCasesListParams, enabled = true) {
  return useV1AdminOpsLookupsKycCasesList(params, {
    query: {
      ...adminPreviewQuery(emptyLookupFixture),
      enabled: lookupEnabled(params, enabled)
    }
  });
}

export function useAdminWithdrawalLookupData(params: V1AdminOpsLookupsWithdrawalRequestsListParams, enabled = true) {
  return useV1AdminOpsLookupsWithdrawalRequestsList(params, {
    query: {
      ...adminPreviewQuery(emptyLookupFixture),
      enabled: lookupEnabled(params, enabled)
    }
  });
}

export function useAdminPrimaryOrderLookupData(params: V1AdminOpsLookupsPrimaryOrdersListParams, enabled = true) {
  return useV1AdminOpsLookupsPrimaryOrdersList(params, {
    query: {
      ...adminPreviewQuery(emptyLookupFixture),
      enabled: lookupEnabled(params, enabled)
    }
  });
}

export function useAdminSecondaryListingLookupData(params: V1AdminOpsLookupsSecondaryListingsListParams, enabled = true) {
  return useV1AdminOpsLookupsSecondaryListingsList(params, {
    query: {
      ...adminPreviewQuery(emptyLookupFixture),
      enabled: lookupEnabled(params, enabled)
    }
  });
}

export function useAdminDocumentTemplateVersionLookupData(
  params: V1AdminOpsLookupsDocumentTemplateVersionsListParams,
  enabled = true
) {
  return useV1AdminOpsLookupsDocumentTemplateVersionsList(params, {
    query: {
      ...adminPreviewQuery(emptyLookupFixture),
      enabled: lookupEnabled(params, enabled) || (!isFixturePreview && enabled && Boolean(params.category))
    }
  });
}

export function useKycManualReviewsData() {
  return useV1KycAdminManualReviewsList({
    query: adminPreviewQuery(kycManualReviewFixture)
  });
}

export function useBorrowersData(params: V1EntitiesAdminBorrowersListParams = { limit: 100 }) {
  return useV1EntitiesAdminBorrowersList(params, {
    query: adminPreviewQuery(borrowersFixture)
  });
}

export function useLoansData(params: V1LoansAdminLoansListParams = { limit: 100 }) {
  return useV1LoansAdminLoansList(params, {
    query: adminPreviewQuery(loansFixture)
  });
}

/** One loan by id, for a Manage link that points outside the current list filters. */
export function useAdminLoanData(loanId: string, enabled: boolean) {
  return useV1LoansAdminLoansRetrieve(loanId || "preview-no-loan", {
    query: {
      ...adminPreviewQuery(loansFixture.find((loan) => loan.id === loanId)),
      enabled: !isFixturePreview && enabled && Boolean(loanId)
    }
  });
}

export function useDocumentTemplateVersionsData(params: V1DocumentsAdminTemplatesVersionsListParams) {
  const fixture = documentVersionsFixture.filter((version) => {
    if (version.template.category !== params.category) return false;
    if (params.language && version.template.language !== params.language) return false;
    if (params.template_key && version.template.template_key !== params.template_key) return false;
    if (params.q) {
      const q = params.q.toLowerCase();
      return [
        version.id,
        version.title,
        version.content_hash,
        version.legal_review_reference,
        version.template.name,
        version.template.template_key
      ].some((value) => value.toLowerCase().includes(q));
    }
    return true;
  });
  return useV1DocumentsAdminTemplatesVersionsList(params, {
    query: adminPreviewQuery(fixture)
  });
}

export function useAuditEventsData(params: V1AdminOpsAuditEventsListParams = { limit: 100 }) {
  return useV1AdminOpsAuditEventsList(params, {
    query: adminPreviewQuery(auditEventsFixture)
  });
}

export function useInvestorBalanceSummaryData(
  params: V1LedgerAdminInvestorBalanceSummaryRetrieveParams,
  enabled: boolean
) {
  return useV1LedgerAdminInvestorBalanceSummaryRetrieve(params, {
    query: {
      ...adminPreviewQuery({
        investor_user_id: params.investor_user_id,
        currency: params.currency,
        total_available_minor: 17150000,
        investable_minor: 14900000,
        withdraw_only_minor: 0,
        overdue_minor: 2250000,
        frozen_minor: 0,
        penalty_mode_minor: 0
      }),
      enabled: !isFixturePreview && enabled
    }
  });
}

export function useAdminWithdrawalHistoryData(params: V1LedgerAdminWithdrawalRequestsHistoryRetrieveParams) {
  const limit = params.limit ?? 50;
  const offset = params.offset ?? 0;
  const search = (params.q ?? "").trim().toLowerCase();
  const rows = adminWithdrawalHistoryFixture.filter((row) => {
    if (params.status && row.status !== params.status) return false;
    if (params.currency && row.currency !== params.currency) return false;
    if (params.is_forced !== undefined && params.is_forced !== null && row.is_forced !== params.is_forced) return false;
    if (search) {
      return [row.id, row.investor_name, row.investor_email, row.investor_reference, row.destination_iban]
        .some((value) => value.toLowerCase().includes(search));
    }
    return true;
  });
  return useV1LedgerAdminWithdrawalRequestsHistoryRetrieve(params, {
    query: adminPreviewQuery({ count: rows.length, limit, offset, results: rows.slice(offset, offset + limit) })
  });
}

const collectionAccountsFixture: CollectionAccount[] = [
  {
    currency: "CHF",
    collection_account_identifier: "BANXUM-CHF-COLLECTION",
    iban: "CH1183019GARANTAFI001",
    qr_iban: "",
    account_holder_name: "Garanta Finanzgruppe AG",
    bank_name: "Yapeal"
  },
  {
    currency: "EUR",
    collection_account_identifier: "BANXUM-EUR-COLLECTION",
    iban: "CH8183019GARANTAFI002",
    qr_iban: "",
    account_holder_name: "Garanta Finanzgruppe AG",
    bank_name: "Yapeal"
  }
];

/** Configured collection account per currency (one per currency at launch). */
export function useCollectionAccountsData() {
  return useV1LedgerAdminCollectionAccountsList({
    query: { ...adminPreviewQuery(collectionAccountsFixture), staleTime: 60_000 }
  });
}

export function collectionAccountFor(accounts: CollectionAccount[] | undefined, currency: string) {
  const code = currency.trim().toUpperCase();
  return (accounts ?? []).find((account) => account.currency === code && account.collection_account_identifier);
}

const payoutInstructionFixture: AdminPayoutInstructionRow[] = [
  {
    id: "preview-payout-1",
    investor_user_id: "preview-investor-1",
    investor_name: "Anna Keller",
    investor_email: "anna.keller@example.test",
    investor_reference: "L4F8K2Q9R",
    currency: "CHF",
    destination_iban: "CH5604835012345678009",
    destination_account_name: "Anna Keller",
    state: "pending",
    origin: "investor_request",
    verified_at: null,
    verified_by_admin_id: null,
    evidence_reference: "",
    other_investor_count: 0,
    open_withdrawal_count: 0,
    revocation_reason: "",
    revoked_at: null,
    created_at: "2026-04-20T09:10:00+02:00",
    updated_at: "2026-04-20T09:10:00+02:00"
  }
];

export function useAdminPayoutInstructionsData(params: V1LedgerAdminPayoutInstructionsListParams) {
  const rows = payoutInstructionFixture.filter((row) => !params.state || row.state === params.state);
  return useV1LedgerAdminPayoutInstructionsList(params, {
    query: adminPreviewQuery({ count: rows.length, limit: params.limit ?? 50, offset: 0, results: rows })
  });
}

export function useAdminPayoutInstructionData(instructionId: string, enabled: boolean) {
  return useV1LedgerAdminPayoutInstructionsRetrieve(instructionId, {
    query: {
      ...adminPreviewQuery(payoutInstructionFixture[0]),
      enabled: !isFixturePreview && enabled && Boolean(instructionId)
    }
  });
}

export function useFxDeltaReportData(params: V1FxAdminDeltaReportRetrieveParams, enabled: boolean) {
  return useV1FxAdminDeltaReportRetrieve(params, {
    query: {
      ...adminPreviewQuery({
        start_date: params.start_date,
        end_date: params.end_date,
        exchange_count: 5,
        source_sold_by_currency_minor: { CHF: 44000000 },
        gross_target_bought_by_currency_minor: { EUR: 46190000 },
        target_credited_by_currency_minor: { EUR: 45500000 },
        fees_by_currency_minor: { EUR: 69000 },
        net_external_settlement_by_currency_minor: { CHF: -44000000, EUR: 46190000 }
      }),
      enabled: !isFixturePreview && enabled
    }
  });
}

export function useFxRealizedSettlementReportData(
  params: V1FxAdminRealizedSettlementReportRetrieveParams,
  enabled: boolean
) {
  return useV1FxAdminRealizedSettlementReportRetrieve(params, {
    query: {
      ...adminPreviewQuery({
        start_date: params.start_date,
        end_date: params.end_date,
        settlement_count: 1,
        expected_sold_by_currency_minor: { CHF: 44000000 },
        actual_sold_by_currency_minor: { CHF: 44020000 },
        expected_bought_by_currency_minor: { EUR: 46190000 },
        actual_bought_by_currency_minor: { EUR: 46175000 },
        fees_by_currency_minor: { EUR: 69000 },
        residual_by_currency_minor: { CHF: -20000, EUR: 15000 }
      }),
      enabled: !isFixturePreview && enabled
    }
  });
}

export function useLoanRiskNotesData(params: V1ServicingAdminRiskNotesListParams, enabled: boolean) {
  return useV1ServicingAdminRiskNotesList(params, {
    query: {
      ...adminPreviewQuery([]),
      enabled: !isFixturePreview && enabled
    }
  });
}

const objectTypeNames: Record<string, string> = {
  investorpayoutinstruction: "Payout IBAN",
  investorwithdrawalrequest: "Withdrawal request",
  admin_task: "Admin task",
  admintask: "Admin task"
};

/** Readable name of a related object type ("InvestorPayoutInstruction" -> "Payout IBAN"). */
export function objectTypeLabel(value: string | null | undefined) {
  if (!value) return "-";
  const known = objectTypeNames[value.toLowerCase()];
  if (known) return known;
  const words = value
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_.-]+/g, " ")
    .trim()
    .toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
