import { useQueryClient } from "@tanstack/react-query";

import {
  getV1InvestorPortalNotificationsRetrieveQueryKey,
  useV1InvestorPortalActivityRetrieve,
  useV1InvestorPortalBalancesRetrieve,
  useV1InvestorPortalDashboardRetrieve,
  useV1InvestorPortalDepositInstructionsRetrieve,
  useV1InvestorPortalDocumentsRetrieve,
  useV1InvestorPortalFxRetrieve,
  useV1InvestorPortalNotificationsReadAllCreate,
  useV1InvestorPortalNotificationsReadCreate,
  useV1InvestorPortalNotificationsRetrieve,
  useV1InvestorPortalPortfolioRetrieve,
  useV1InvestorPortalPrimaryOrdersRetrieve,
  useV1InvestorPortalSecondaryMarketRetrieve,
  useV1MarketplacePrimaryLoansList,
  useV1MarketplacePrimaryLoansRetrieve,
  useV1MarketplaceSecondaryListingsRetrieve,
  useV1MarketplaceSecondaryListingsList,
  useV1InvestorSmartInvestRetrieve
} from "../api/generated/banxumApi";
import type {
  InvestorDepositInstructions,
  InvestorDocuments,
  InvestorNotifications
} from "../api/generated/banxumApi";
import {
  activityFixture,
  balancesFixture,
  dashboardFixture,
  fxFixture,
  loanDetailsFixture,
  marketplaceLoansFixture,
  portfolioFixture,
  primaryOrdersFixture,
  secondaryActivityFixture,
  secondaryListingDetailsFixture,
  secondaryListingsFixture,
  smartInvestFixture
} from "./fixtures";
import { portalFixture } from "./fixtures";
import { markNotificationsRead } from "./notifications";

export const isFixturePreview =
  import.meta.env.VITE_PREVIEW === "true" || import.meta.env.MODE === "test";

if (import.meta.env.PROD && isFixturePreview) {
  throw new Error("Fixture preview data is disabled in production builds.");
}

const queryDefaults = {
  enabled: !isFixturePreview,
  retry: false,
  staleTime: 0
};

function previewQuery<T>(fixture: T, enabled = true) {
  return {
    ...queryDefaults,
    enabled: !isFixturePreview && enabled,
    // Preview fixtures are review-only placeholder data. Do not switch this to
    // initialData; live mode must fetch immediately and never cache dummy values.
    placeholderData: isFixturePreview ? fixture : undefined
  };
}

const depositInstructionsFixture: InvestorDepositInstructions = {
  as_of: `${portalFixture.today}T00:00:00Z`,
  instructions: portalFixture.depositInstructions.map((instruction) => ({
    currency: instruction.currency,
    account_holder_name: "Garanta Finanzgruppe AG",
    iban: instruction.iban,
    qr_iban: instruction.qrIban ?? "",
    bic: instruction.bic,
    bank_name: instruction.bank,
    collection_account_identifier: `${instruction.currency}-COLLECTION`,
    qr_bill_payload: instruction.qrBillPayload ?? "",
    payment_reference: instruction.reference,
    notes: "Use the exact payment reference so finance can reconcile the deposit.",
    is_configured: true
  })),
  reference_rule:
    "The payment reference is unique to the investor and currency and must be included unchanged in the bank transfer reference/description."
};

const documentsFixture: InvestorDocuments = {
  as_of: `${portalFixture.today}T00:00:00Z`,
  disclaimer:
    "Statements and annual tax-information files are informational only and are not tax advice.",
  documents: portalFixture.documents.map((document) => ({
    id: document.id,
    document_kind:
      document.type === "Statement"
        ? "account_statement"
        : document.type === "Tax"
          ? "annual_tax_information"
          : "acceptance_evidence",
    title: document.title,
    document_type: document.type,
    version: document.version,
    date: `${document.date}T00:00:00Z`,
    context_label: document.context,
    output_formats:
      document.type === "Statement" || document.type === "Tax"
        ? ["pdf", "csv", "zip"]
        : ["pdf", "csv"],
    generated_on_request: document.type === "Statement" || document.type === "Tax",
    content_hash:
      document.type === "Agreement" || document.type === "Risk"
        ? "preview-content-hash"
        : undefined
  }))
};

const notificationsFixture: InvestorNotifications = {
  notifications: portalFixture.notifications.map((notification) => ({
    id: notification.id,
    notification_source: "preview",
    topic: "email.preview",
    status: "sent",
    title: notification.title,
    body: notification.body,
    created_at: `${portalFixture.today}T00:00:00Z`,
    sent_at: `${portalFixture.today}T00:00:00Z`,
    unread: notification.unread,
    navigation_target: notification.target ?? "none",
    navigation_target_id: notification.targetId ?? "",
    metadata: { tone: notification.tone, time: notification.time }
  })),
  unread_count: portalFixture.notifications.filter((notification) => notification.unread).length
};

export function useDashboardData(enabled = true) {
  return useV1InvestorPortalDashboardRetrieve({
    query: previewQuery(dashboardFixture, enabled)
  });
}

export function useBalancesData(enabled = true) {
  return useV1InvestorPortalBalancesRetrieve({
    query: previewQuery(balancesFixture, enabled)
  });
}

export function useDepositInstructionsData(enabled = true) {
  return useV1InvestorPortalDepositInstructionsRetrieve({
    query: previewQuery(depositInstructionsFixture, enabled)
  });
}

export function useDocumentsData(enabled = true) {
  return useV1InvestorPortalDocumentsRetrieve({
    query: previewQuery(documentsFixture, enabled)
  });
}

// Preview mode keeps "mark as read" per session in the query client, so lists opened later agree.
const previewNotificationReadsKey = ["preview", "notification-reads"] as const;
type PreviewNotificationReads = { all: boolean; ids: string[] };

export function useNotificationsData(limit = 50, enabled = true) {
  const queryClient = useQueryClient();
  const previewReads = isFixturePreview
    ? queryClient.getQueryData<PreviewNotificationReads>(previewNotificationReadsKey)
    : undefined;
  const fixture = previewReads
    ? markNotificationsRead(notificationsFixture, previewReads.all ? "all" : previewReads.ids)
    : notificationsFixture;
  return useV1InvestorPortalNotificationsRetrieve(
    { limit },
    { query: previewQuery(fixture, enabled) }
  );
}

/**
 * Mark-as-read actions for the header menu and the Notifications page. Both lists and the unread
 * counter update at once; live mode then refetches the server state, preview mode keeps it locally.
 */
export function useNotificationReadActions() {
  const queryClient = useQueryClient();
  const markOne = useV1InvestorPortalNotificationsReadCreate();
  const markAll = useV1InvestorPortalNotificationsReadAllCreate();
  const notificationsKey = getV1InvestorPortalNotificationsRetrieveQueryKey().slice(0, 1);
  const applyLocally = (ids: string[] | "all") => {
    queryClient.setQueriesData<InvestorNotifications>({ queryKey: notificationsKey }, (current) =>
      markNotificationsRead(current ?? notificationsFixture, ids)
    );
    if (isFixturePreview) {
      queryClient.setQueryDefaults(previewNotificationReadsKey, { gcTime: Infinity });
      queryClient.setQueryData<PreviewNotificationReads>(previewNotificationReadsKey, (current) => ({
        all: ids === "all" || Boolean(current?.all),
        ids: ids === "all" ? current?.ids ?? [] : [...(current?.ids ?? []), ...ids]
      }));
    }
  };
  const sync = async (request: () => Promise<unknown>) => {
    if (isFixturePreview) return;
    try {
      await request();
    } finally {
      await queryClient.invalidateQueries({ queryKey: notificationsKey });
    }
  };
  return {
    markRead: (notificationId: string) => {
      applyLocally([notificationId]);
      return sync(() => markOne.mutateAsync({ notificationId }));
    },
    markAllRead: () => {
      applyLocally("all");
      return sync(() => markAll.mutateAsync());
    },
    pending: markOne.isPending || markAll.isPending
  };
}

export function usePortfolioData(includeInactive = true, enabled = true) {
  return useV1InvestorPortalPortfolioRetrieve(
    { include_inactive: includeInactive },
    { query: previewQuery(portfolioFixture, enabled) }
  );
}

export function useActivityData(limit = 50, enabled = true) {
  return useV1InvestorPortalActivityRetrieve(
    { limit },
    { query: previewQuery(activityFixture, enabled) }
  );
}

export function usePrimaryOrdersData(limit = 50, enabled = true) {
  return useV1InvestorPortalPrimaryOrdersRetrieve(
    { limit },
    { query: previewQuery(primaryOrdersFixture, enabled) }
  );
}

export function useSecondaryActivityData(limit = 50, enabled = true) {
  return useV1InvestorPortalSecondaryMarketRetrieve(
    { limit },
    { query: previewQuery(secondaryActivityFixture, enabled) }
  );
}

export function useFxData(limit = 50, enabled = true) {
  return useV1InvestorPortalFxRetrieve(
    { limit },
    { query: previewQuery(fxFixture, enabled) }
  );
}

export function useMarketplaceLoansData() {
  return useV1MarketplacePrimaryLoansList({ limit: 250 }, {
    query: previewQuery(marketplaceLoansFixture)
  });
}

export function useSmartInvestData(enabled = true) {
  return useV1InvestorSmartInvestRetrieve({
    query: previewQuery(smartInvestFixture, enabled)
  });
}

export function useLoanDetailData(loanId: string) {
  const fixture =
    loanDetailsFixture.find((loan) => loan.loan_id === loanId) ?? loanDetailsFixture[0];

  return useV1MarketplacePrimaryLoansRetrieve(loanId, {
    query: previewQuery(fixture)
  });
}

export function useSecondaryListingsData() {
  return useV1MarketplaceSecondaryListingsList(undefined, {
    query: previewQuery(secondaryListingsFixture)
  });
}

export function useSecondaryListingDetailData(listingId: string) {
  const fixture =
    secondaryListingDetailsFixture.find((listing) => listing.id === listingId) ??
    secondaryListingDetailsFixture[0];

  return useV1MarketplaceSecondaryListingsRetrieve(listingId, {
    query: previewQuery(fixture, Boolean(listingId))
  });
}
