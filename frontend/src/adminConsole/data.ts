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
  useV1DocumentsAdminTemplatesVersionsList,
  useV1EntitiesAdminBorrowersList,
  useV1FxAdminDeltaReportRetrieve,
  useV1FxAdminRealizedSettlementReportRetrieve,
  useV1KycAdminManualReviewsList,
  useV1LedgerAdminInvestorBalanceSummaryRetrieve,
  useV1LoansAdminLoansList,
  useV1ServicingAdminRiskNotesList,
  type AdminLookupResult,
  type V1AdminOpsAuditEventsListParams,
  type V1AdminOpsTasksListParams,
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
  type V1LoansAdminLoansListParams,
  type V1ServicingAdminRiskNotesListParams
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
  adminTasksFixture
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
  return useV1AdminOpsTasksList(params, {
    query: adminPreviewQuery(adminTasksFixture)
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

export function useDocumentTemplateVersionsData(params: V1DocumentsAdminTemplatesVersionsListParams) {
  const fixture = documentVersionsFixture.filter((version) => {
    if (version.template.category !== params.category) return false;
    if (params.language && version.template.language !== params.language) return false;
    if (params.template_key && version.template.template_key !== params.template_key) return false;
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
        investable_minor: 9800000,
        withdraw_only_minor: 4100000,
        overdue_minor: 2250000,
        frozen_minor: 0,
        penalty_mode_minor: 0
      }),
      enabled: !isFixturePreview && enabled
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
