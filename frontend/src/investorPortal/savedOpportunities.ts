// IP of Webby-Soft SRL.
// U33-DEC-18: Save for later. The opportunity and, when the investor chose one, the amount are saved
// in the account (all devices, Overview). Saving reserves no money or place and accepts no agreement.
// The saved amount is never changed: when it no longer fits, the screens explain why.
import { useQueryClient } from "@tanstack/react-query";

import {
  getV1MarketplacePrimarySavedRetrieveQueryKey,
  useV1MarketplacePrimaryLoansSavedDestroy,
  useV1MarketplacePrimaryLoansSavedUpdate,
  type MarketplaceLoanPreview,
  type SavedOpportunity,
  type SavedOpportunityList
} from "../api/generated/banxumApi";
import { t } from "../i18n";
import { isFixturePreview } from "./data";
import { savedOpportunitiesFixture } from "./fixtures";
import { readReadonlyImpersonationToken } from "../api/client/impersonation";

function availableMinor(loan: MarketplaceLoanPreview) {
  return loan.fillable_amount_minor ?? loan.remaining_capacity_minor;
}

/** Preview mode only: the saved item the server would answer. */
export function previewSavedOpportunity(loan: MarketplaceLoanPreview, amountMinor: number | null): SavedOpportunity {
  const now = new Date().toISOString();
  const available = availableMinor(loan);
  return {
    loan_id: loan.loan_id,
    title: loan.title,
    product_type: loan.product_type,
    currency: loan.currency,
    borrower_display_name: loan.borrower_display_name,
    collateral_type: loan.collateral_type,
    amount_minor: amountMinor,
    saved_at: now,
    updated_at: now,
    is_open: true,
    funding_deadline: loan.funding_deadline,
    minimum_investment_minor: loan.minimum_investment_minor,
    available_minor: available,
    amount_check: amountMinor === null ? "none" : amountMinor < loan.minimum_investment_minor ? "below_minimum" : amountMinor > available ? "above_available" : "ok"
  };
}

export function useSavedOpportunityActions() {
  const queryClient = useQueryClient();
  const put = useV1MarketplacePrimaryLoansSavedUpdate();
  const remove = useV1MarketplacePrimaryLoansSavedDestroy();
  const key = getV1MarketplacePrimarySavedRetrieveQueryKey();
  const current = () => queryClient.getQueryData<SavedOpportunityList>(key)?.saved ?? (isFixturePreview ? savedOpportunitiesFixture.saved : []);
  const store = (saved: SavedOpportunity[]) => queryClient.setQueryData<SavedOpportunityList>(key, { saved });
  const refuseReadonly = () => {
    if (readReadonlyImpersonationToken()) throw new Error(t("Saved opportunities cannot be changed in a read-only view."));
  };

  return {
    busy: put.isPending || remove.isPending,
    async save(loan: MarketplaceLoanPreview, amountMinor: number | null) {
      refuseReadonly();
      const item = isFixturePreview
        ? previewSavedOpportunity(loan, amountMinor)
        : await put.mutateAsync({ loanId: loan.loan_id, data: { amount_minor: amountMinor } });
      store([item, ...current().filter((saved) => saved.loan_id !== loan.loan_id)]);
      if (!isFixturePreview) void queryClient.invalidateQueries({ queryKey: key });
      return item;
    },
    async remove(loanId: string) {
      refuseReadonly();
      if (!isFixturePreview) await remove.mutateAsync({ loanId });
      store(current().filter((saved) => saved.loan_id !== loanId));
      if (!isFixturePreview) void queryClient.invalidateQueries({ queryKey: key });
    }
  };
}
