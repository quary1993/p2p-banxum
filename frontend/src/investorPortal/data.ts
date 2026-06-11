import {
  useV1InvestorPortalActivityRetrieve,
  useV1InvestorPortalBalancesRetrieve,
  useV1InvestorPortalDashboardRetrieve,
  useV1InvestorPortalDepositInstructionsRetrieve,
  useV1InvestorPortalDocumentsRetrieve,
  useV1InvestorPortalFxRetrieve,
  useV1InvestorPortalNotificationsRetrieve,
  useV1InvestorPortalPortfolioRetrieve,
  useV1InvestorPortalPrimaryOrdersRetrieve,
  useV1InvestorPortalSecondaryMarketRetrieve,
  useV1MarketplacePrimaryLoansList,
  useV1MarketplacePrimaryLoansRetrieve,
  useV1MarketplaceSecondaryListingsList
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
  secondaryListingsFixture
} from "./fixtures";
import { portalFixture } from "./fixtures";

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

function previewQuery<T>(fixture: T) {
  return {
    ...queryDefaults,
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
    bic: instruction.bic,
    bank_name: instruction.bank,
    collection_account_identifier: `${instruction.currency}-COLLECTION`,
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
    status: notification.unread ? "pending" : "sent",
    title: notification.title,
    body: notification.body,
    created_at: `${portalFixture.today}T00:00:00Z`,
    sent_at: notification.unread ? null : `${portalFixture.today}T00:00:00Z`,
    unread: notification.unread,
    metadata: { tone: notification.tone, time: notification.time }
  })),
  unread_count: portalFixture.notifications.filter((notification) => notification.unread).length
};

export function useDashboardData() {
  return useV1InvestorPortalDashboardRetrieve({
    query: previewQuery(dashboardFixture)
  });
}

export function useBalancesData() {
  return useV1InvestorPortalBalancesRetrieve({
    query: previewQuery(balancesFixture)
  });
}

export function useDepositInstructionsData() {
  return useV1InvestorPortalDepositInstructionsRetrieve({
    query: previewQuery(depositInstructionsFixture)
  });
}

export function useDocumentsData() {
  return useV1InvestorPortalDocumentsRetrieve({
    query: previewQuery(documentsFixture)
  });
}

export function useNotificationsData(limit = 50) {
  return useV1InvestorPortalNotificationsRetrieve(
    { limit },
    { query: previewQuery(notificationsFixture) }
  );
}

export function usePortfolioData(includeInactive = true) {
  return useV1InvestorPortalPortfolioRetrieve(
    { include_inactive: includeInactive },
    { query: previewQuery(portfolioFixture) }
  );
}

export function useActivityData(limit = 50) {
  return useV1InvestorPortalActivityRetrieve(
    { limit },
    { query: previewQuery(activityFixture) }
  );
}

export function usePrimaryOrdersData(limit = 50) {
  return useV1InvestorPortalPrimaryOrdersRetrieve(
    { limit },
    { query: previewQuery(primaryOrdersFixture) }
  );
}

export function useSecondaryActivityData(limit = 50) {
  return useV1InvestorPortalSecondaryMarketRetrieve(
    { limit },
    { query: previewQuery(secondaryActivityFixture) }
  );
}

export function useFxData(limit = 50) {
  return useV1InvestorPortalFxRetrieve(
    { limit },
    { query: previewQuery(fxFixture) }
  );
}

export function useMarketplaceLoansData() {
  return useV1MarketplacePrimaryLoansList(undefined, {
    query: previewQuery(marketplaceLoansFixture)
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
