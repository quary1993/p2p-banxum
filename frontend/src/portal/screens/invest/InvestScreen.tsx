// IP of Webby-Soft SRL.
/*
 * Review & sign (design #/projects/:id/invest?step=review, slice S2), route /marketplace/:loanId/invest.
 * The amount stays editable (Enter or leaving the field applies it, Escape restores it; a new amount
 * clears the acceptances and starts a new order attempt), the projected interest and the investor's
 * schedule come from the loan schedule, two unchecked acceptances (U33-DEC-14), and the confirmation
 * dialog with today's email code + PIN. Direct loans and Loan Originator subscriptions place a primary
 * order; legacy originator claims are bought through an executable quote. Each investment is confirmed
 * on its own (U33-DEC-19). Whether the page may take an order is decided once when it opens
 * (FRONTCODE-24): a loan that fills meanwhile keeps the flow so the result shows.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import {
  ActionEnum,
  CategoryEnum,
  useOriginatorClaimsLoansQuoteCreate,
  useOriginatorClaimsQuotesPurchaseCreate,
  useV1DocumentsAcceptancesCreate,
  useV1DocumentsTemplatesCurrentRetrieve,
  useV1MarketplacePrimaryOrdersAllocateBalanceCreate,
  useV1MarketplacePrimaryOrdersCreate,
  type MarketplaceLoanDetail,
  type OriginatorClaimPurchaseResponse,
  type OriginatorClaimQuoteResponse,
  type PrimaryInvestmentOrder
} from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { useFrozenAccount } from "../../../investorPortal/accountState";
import { isFixturePreview, useBalancesData, useLoanDetailData } from "../../../investorPortal/data";
import { formatDate, formatDateTime, formatMoneyLabel, formatRateBps, parseMoneyInputToMinorUnits, useNumberFormat } from "../../../investorPortal/format";
import { currencyBalanceMinor } from "../../../investorPortal/investLimits";
import { isSwissInvestorLimitError, swissInvestorLimitMessage } from "../../../investorPortal/investorLimit";
import { isNotFoundError } from "../../../investorPortal/session";
import type { DemoAccountState } from "../../../investorPortal/types";
import { Button, Dialog, EmptyState, NiIcon, PageHead, PortalLink } from "../../components";
import {
  apiErrorMessage,
  checkInvestAmount,
  checkInvestAmountMinor,
  investBlockedReason,
  isOrderNotPendingError,
  newClaimPurchaseAttempt,
  newPrimaryOrderAttempt,
  primaryOrderOutcome,
  templateLabels,
  type ClaimPurchaseAttempt,
  type PrimaryOrderAttempt
} from "./investRules";
import {
  eligibleLots,
  isOpenLoan,
  isReadonlyView,
  loanAvailableMinor,
  loanYieldBps,
  placesInfo,
  scheduleShare,
  sumAvailableMinor,
  usesImmediateClaimAssignment,
  usesOriginatorSubscription
} from "./loanFacts";
import { Acceptances, ConfirmDialog, ResultPage, ReviewAmount, ReviewFrame, SignActions } from "./parts/ReviewParts";
import { ScheduleTable } from "./parts/ScheduleTable";
import type { SensitiveActionKit } from "./parts/sensitiveAction";
import "./invest.css";

type Props = {
  loanId: string;
  initialAmount?: string;
  demoState: DemoAccountState;
  sensitiveAction: SensitiveActionKit;
  onAddFunds: () => void;
};

export function InvestScreen({ loanId, initialAmount, demoState, sensitiveAction, onAddFunds }: Props) {
  const t = useT();
  const loanQuery = useLoanDetailData(loanId);
  const frozenAccount = useFrozenAccount();
  const loan = loanQuery.data;
  if (loanQuery.isError && !loan) {
    const notFound = isNotFoundError(loanQuery.error);
    return (
      <main className="bxm-invest-desktop ip-page rp-page u33-invest-state">
        <PortalLink className="ip-back" to="market"><NiIcon name="arrow-left" />{t("Investment opportunities")}</PortalLink>
        <PageHead title={t("Review & sign")} />
        <EmptyState
          actions={notFound ? null : <Button onClick={() => void loanQuery.refetch()} variant="primary">{t("Retry")}</Button>}
          icon={notFound ? "search" : "alert-circle"}
          title={notFound ? t("This loan does not exist, or it is no longer shown to investors.") : t("We could not load this opportunity")}
        />
      </main>
    );
  }
  if (!loan) {
    return (
      <main className="bxm-invest-desktop ip-page rp-page u33-invest-state">
        <EmptyState icon="clock" title={t("Loading the opportunity")} />
      </main>
    );
  }
  // Frozen accounts and the read-only view cannot place orders: say so before any code is sent.
  const blocked = investBlockedReason(demoState, frozenAccount);
  if (blocked && !isReadonlyView()) {
    return <Unavailable detail={blocked} loan={loan} title={frozenAccount.frozen ? t("Financial actions frozen") : t("Investing is not available yet")} />;
  }
  return (
    <ReviewEntry
      initialAmount={initialAmount}
      key={`${loan.loan_id}:${initialAmount ?? ""}`}
      loan={loan}
      onAddFunds={onAddFunds}
      sensitiveAction={sensitiveAction}
    />
  );
}

function Unavailable({ loan, title, detail }: { loan: MarketplaceLoanDetail; title: string; detail: string }) {
  const t = useT();
  return (
    <main className="bxm-invest-desktop ip-page rp-page u33-invest-state">
      <PortalLink className="ip-back" params={{ loanId: loan.loan_id }} to="loan"><NiIcon name="arrow-left" />{t("Back to opportunity")}</PortalLink>
      <PageHead subtitle={loan.title} title={t("Review & sign")} />
      <EmptyState
        actions={
          <>
            <PortalLink className="btn btn-primary" to="market">{t("Investment opportunities")}</PortalLink>{" "}
            <PortalLink className="btn btn-outline-light" params={{ loanId: loan.loan_id }} to="loan">{t("Back to the loan")}</PortalLink>
          </>
        }
        icon="lock"
        title={title}
      >
        {detail}
      </EmptyState>
    </main>
  );
}

function ReviewEntry({ loan, initialAmount, sensitiveAction, onAddFunds }: { loan: MarketplaceLoanDetail; initialAmount?: string; sensitiveAction: SensitiveActionKit; onAddFunds: () => void }) {
  const t = useT();
  const [unavailable] = useState(() => {
    if (isReadonlyView()) return { title: t("Read-only view"), detail: t("This is a read-only investor view. You can see the loan, but you cannot invest.") };
    if (!isOpenLoan(loan)) return { title: t("This loan is not open for investment"), detail: t("It is closed or fully funded. You can still read the loan page and its credit file, or choose another opportunity.") };
    return null;
  });
  if (unavailable) return <Unavailable detail={unavailable.detail} loan={loan} title={unavailable.title} />;
  return usesImmediateClaimAssignment(loan)
    ? <ClaimPurchaseReview initialAmount={initialAmount} kit={sensitiveAction} loan={loan} onAddFunds={onAddFunds} />
    : <OrderReview initialAmount={initialAmount} kit={sensitiveAction} loan={loan} onAddFunds={onAddFunds} />;
}

/** The investor's funds for this loan: everything in the currency, and what this funding window may use. */
function useLoanFunds(loan: MarketplaceLoanDetail) {
  const balances = useBalancesData().data;
  return { loaded: Boolean(balances), balanceMinor: currencyBalanceMinor(balances?.lots, loan.currency), eligibleMinor: sumAvailableMinor(eligibleLots(balances?.lots, loan)) };
}

/** Funds that do not limit the amount: used until the balances have loaded, so that an amount applied
 *  early gets no false "Add funds" error; the live check runs again when the balances arrive. */
const fundsNotLoaded = { balanceMinor: Number.MAX_SAFE_INTEGER, eligibleMinor: Number.MAX_SAFE_INTEGER };

function initialAmountMinor(initialAmount: string | undefined, currency: string) {
  if (!initialAmount) return null;
  const parsed = parseMoneyInputToMinorUnits(initialAmount, currency);
  return !parsed.error && parsed.amountMinor > 0 ? parsed.amountMinor : null;
}

/** Applied amount with its check: the parent keeps one amount; a change resets the acceptances. */
function useReviewAmount(loan: MarketplaceLoanDetail, initialAmount: string | undefined, onChange: (amountMinor: number) => void) {
  const t = useT();
  const funds = useLoanFunds(loan);
  const [appliedMinor, setAppliedMinor] = useState<number | null>(() => initialAmountMinor(initialAmount, loan.currency));
  const [error, setError] = useState<{ message: string; shortfall: boolean } | null>(null);
  const [status, setStatus] = useState("");
  // The applied amount is checked again against live data (capacity, balance) on every render.
  const checkFunds = funds.loaded ? funds : fundsNotLoaded;
  const check = appliedMinor === null ? null : checkInvestAmountMinor(appliedMinor, loan, checkFunds);
  const liveError = check && !check.ok ? { message: check.message, shortfall: check.shortfallMinor !== undefined } : null;
  const apply = (text: string) => {
    const result = checkInvestAmount(text, loan, checkFunds);
    if (!result.ok) {
      setError({ message: result.message, shortfall: result.shortfallMinor !== undefined });
      return;
    }
    setError(null);
    if (result.amountMinor !== appliedMinor) {
      setAppliedMinor(result.amountMinor);
      onChange(result.amountMinor);
      setStatus(t("Amount updated to {amount}. Confirm the statements again.", { amount: formatMoneyLabel(loan.currency, result.amountMinor) }));
    }
  };
  return {
    appliedMinor,
    // Confirming needs the real balance check.
    valid: funds.loaded && appliedMinor !== null && !error && check?.ok === true,
    error: error ?? liveError,
    status,
    apply,
    cancel: () => setError(null)
  };
}

function OrderReview({ loan, initialAmount, kit, onAddFunds }: { loan: MarketplaceLoanDetail; initialAmount?: string; kit: SensitiveActionKit; onAddFunds: () => void }) {
  const t = useT();
  useNumberFormat();
  const queryClient = useQueryClient();
  const subscription = usesOriginatorSubscription(loan);
  const [terms, setTerms] = useState(false);
  const [risks, setRisks] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [placedOrder, setPlacedOrder] = useState<PrimaryInvestmentOrder | null>(null);
  const [done, setDone] = useState(false);
  const [attempt, setAttempt] = useState<PrimaryOrderAttempt>(() => newPrimaryOrderAttempt(initialAmountMinor(initialAmount, loan.currency) ?? 0));
  const amount = useReviewAmount(loan, initialAmount, (amountMinor) => {
    // A new amount needs a new order, a new acceptance and new keys (audit A-15).
    setAttempt(newPrimaryOrderAttempt(amountMinor));
    setTerms(false);
    setRisks(false);
    setError("");
  });
  const amountMinor = amount.appliedMinor ?? 0;
  const orderMutation = useV1MarketplacePrimaryOrdersCreate();
  const acceptanceMutation = useV1DocumentsAcceptancesCreate();
  const allocateMutation = useV1MarketplacePrimaryOrdersAllocateBalanceCreate();
  const { useCode, useAutoRequest } = kit;
  const codeRequest = useCode(ActionEnum.primary_investment);
  useAutoRequest(codeRequest, confirmOpen);
  const termsQuery = useV1DocumentsTemplatesCurrentRetrieve(
    { category: CategoryEnum.primary_market_investment },
    { query: { enabled: !isFixturePreview, retry: false } }
  );
  const submitting = orderMutation.isPending || acceptanceMutation.isPending || allocateMutation.isPending;
  const share = amountMinor > 0 ? scheduleShare(loan, amountMinor) : null;
  const places = placesInfo(loan);

  const confirm = async () => {
    setError("");
    if (isFixturePreview) {
      if (codeRequest.pin.previewAccepts()) {
        setConfirmOpen(false);
        setDone(true);
      }
      return;
    }
    const labels = templateLabels(termsQuery.data);
    if (!termsQuery.data || labels.length === 0) {
      setError(t("Current investment terms are not available. Retry after the document template is published."));
      return;
    }
    if (!codeRequest.codeId) {
      setError(t("Request an email code before confirming the investment."));
      return;
    }
    // Reuse the order and acceptance only for a retry of exactly this amount.
    let current = attempt.amountMinor === amountMinor ? attempt : newPrimaryOrderAttempt(amountMinor);
    try {
      const orderId = current.orderId ?? (await orderMutation.mutateAsync({ data: { loan_id: loan.loan_id, amount_minor: amountMinor, idempotency_key: current.orderKey } })).id;
      current = { ...current, orderId };
      setAttempt(current);
      const acceptanceId = current.acceptanceId ?? (await acceptanceMutation.mutateAsync({
        data: {
          category: CategoryEnum.primary_market_investment,
          expected_template_version_id: termsQuery.data.id,
          accepted_checkbox_labels: labels,
          context_type: "primary_order",
          context_id: orderId,
          data_snapshot: { loan_id: loan.loan_id, amount_minor: amountMinor, currency: loan.currency },
          idempotency_key: current.acceptanceKey
        }
      })).id;
      current = { ...current, acceptanceId };
      setAttempt(current);
      const order = await allocateMutation.mutateAsync({
        orderId,
        data: {
          document_acceptance_id: acceptanceId,
          idempotency_key: current.allocationKey,
          sensitive_action_code_id: codeRequest.codeId,
          sensitive_action_code: code,
          pin: codeRequest.pin.value
        }
      });
      void queryClient.invalidateQueries();
      setPlacedOrder(order);
      setConfirmOpen(false);
      setDone(true);
    } catch (mutationError) {
      if (codeRequest.pin.handleError(mutationError)) return;
      if (isOrderNotPendingError(mutationError)) setAttempt(newPrimaryOrderAttempt(amountMinor));
      // The last place of a Swiss-borrower loan went to someone else: reload the places.
      if (isSwissInvestorLimitError(mutationError)) void queryClient.invalidateQueries();
      setError(apiErrorMessage(mutationError));
    }
  };

  if (done) {
    const outcome = placedOrder
      ? primaryOrderOutcome(placedOrder, loan, subscription)
      : primaryOrderOutcome({ status: "balance_allocated", allocated_amount_minor: amountMinor, requested_amount_minor: amountMinor, closed_reason: "" } as PrimaryInvestmentOrder, loan, subscription);
    const allocated = placedOrder ? placedOrder.allocated_amount_minor : amountMinor;
    return (
      <ResultPage
        amountLabel={outcome.kind === "refused" ? t("Amount invested") : outcome.kind === "invested" ? t("Amount invested") : t("Amount reserved")}
        amountMinor={allocated}
        lastStepLabel={t("Reserved")}
        loan={loan}
        // The order's own reference and time from the server (the platform clock, not the browser's).
        reference={placedOrder ? `${placedOrder.id.slice(0, 8).toUpperCase()} · ${formatDate(placedOrder.allocated_at ?? placedOrder.created_at)}` : undefined}
        refused={outcome.kind === "refused"}
        showNext={outcome.kind === "reserved" || outcome.kind === "partial"}
        text={outcome.text}
        title={outcome.title}
      />
    );
  }

  const ready = amount.valid && terms && risks && !places?.fullForViewer;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (ready) {
      setError("");
      setCode("");
      setConfirmOpen(true);
    }
  };

  return (
    <>
      <ReviewFrame
        agreement={
          <>
            <Acceptances
              onRisks={setRisks}
              onTerms={setTerms}
              risks={risks}
              templateNote={!isFixturePreview && termsQuery.data
                ? t("Documents open in a new tab. Your acceptance is recorded against {title} v{version}, the time, the amount and the loan.", { title: termsQuery.data.title, version: termsQuery.data.version_number })
                : undefined}
              terms={terms}
              termsLabel={t("I accept the investment terms and the assignment of my share of the loan claim.")}
            />
            {!isFixturePreview && termsQuery.isError ? <div className="alert alert-danger" role="alert">{t("The current investment terms could not be loaded.")}</div> : null}
            <SignActions disabled={!ready} label={t("Confirm investment")} />
          </>
        }
        lastStepLabel={t("Reserved")}
        loan={loan}
        onSubmit={submit}
        summary={
          <>
            <ReviewAmount
              action={amount.error?.shortfall ? <button className="btn btn-sm btn-outline-light" onClick={onAddFunds} type="button">{t("Add funds")}</button> : null}
              appliedMinor={amount.appliedMinor}
              currency={loan.currency}
              error={amount.error?.message ?? ""}
              onApply={amount.apply}
              onCancel={amount.cancel}
              status={amount.status}
            />
            <p className="u33-invest-places-note u33-invest-review-hint">
              {t("Minimum {minimum} · {available} available in this opportunity", { minimum: formatMoneyLabel(loan.currency, loan.minimum_investment_minor), available: formatMoneyLabel(loan.currency, loanAvailableMinor(loan)) })}
            </p>
            {places?.fullForViewer ? (
              <p className="ra28-error u33-invest-full" role="alert">{t("{reason} Choose another opportunity.", { reason: swissInvestorLimitMessage(places.maxInvestors) })}</p>
            ) : places ? (
              <p className="u33-invest-places-note">
                {places.existingInvestor && places.placesLeft === 0
                  ? t("Swiss borrower: at most {count} investors. You already invest in this loan, so you can add to it.", { count: places.maxInvestors })
                  : t("Swiss borrower: at most {count} investors. {left} left.", { count: places.maxInvestors, left: places.placesLeft === 1 ? t("1 place") : t("{count} places", { count: places.placesLeft }) })}
              </p>
            ) : null}
            <div id="iv-summary">
              <div className="ip-terms">
                <div className="ip-term"><strong>{formatRateBps(loanYieldBps(loan))}</strong><span>{subscription ? t("Investor interest rate") : t("Annual interest rate")}</span></div>
                <div className="ip-term"><strong>{loan.term_months} <small>{t("months")}</small></strong><span>{t("Duration")}</span></div>
              </div>
              {share && share.rows.length > 0 ? (
                <section aria-label={t("Projected repayments")} className="r34-returns">
                  <div className="ip-summary-line ip-interest">
                    <span>{t("Projected total interest")}</span>
                    <div className="fp2-interest-line">
                      <strong>{formatMoneyLabel(loan.currency, share.interestMinor)}</strong>
                      <span className="fp2-duration">{share.rows.length === 1 ? t("1 payment") : t("Total over {count} payments", { count: share.rows.length })}</span>
                    </div>
                  </div>
                  <div className="ip-summary-line r79-first-payment fp2-first">
                    <span>{t("Projected first payment")}</span>
                    <div className="fp2-first-line">
                      <strong>{formatMoneyLabel(loan.currency, share.rows[0].totalMinor)}</strong>
                      <span aria-hidden="true" className="fp2-dot">·</span>
                      <span className="fp2-date">{formatDate(share.rows[0].dueDate)}</span>
                    </div>
                  </div>
                </section>
              ) : null}
              {share && share.rows.length > 0 ? (
                <button aria-haspopup="dialog" className="ip-schedule r52-schedule-toggle" onClick={() => setScheduleOpen(true)} type="button">
                  <NiIcon name="calendar" />
                  <span className="r36-toggle-copy">
                    <strong>{t("Payment schedule")}</strong>
                    <small>{subscription ? t("Your share of the installments after the funding deadline.") : t("Your share of each installment.")}</small>
                  </span>
                  <span className="r36-chevron"><NiIcon name="arrow-up-right" /></span>
                </button>
              ) : null}
              <div className="ip-money-summary">
                <div className="ip-summary-line rl29-replaced-fee"><span>{t("Investment fees")}</span><strong>{t("None")}</strong></div>
              </div>
            </div>
          </>
        }
      />
      {scheduleOpen && share ? (
        <Dialog className="u33-invest-schedule-dialog" onClose={() => setScheduleOpen(false)} size="lg" title={t("Your payment schedule")}>
          <p className="bxm-muted">
            {subscription
              ? t("Projected for {amount}. Only installments after the funding deadline count; the first one after it belongs to the Loan Originator. Your interest share is {share} of the borrower's interest.", { amount: formatMoneyLabel(loan.currency, amountMinor), share: formatRateBps(loan.investor_interest_participation_bps ?? 0) })
              : t("Projected for {amount}, assuming the loan funds in full. If it closes at its minimum, the schedule is recalculated. Repayments are credited to your Banxum balance and are not guaranteed.", { amount: formatMoneyLabel(loan.currency, amountMinor) })}
          </p>
          <ScheduleTable
            currency={loan.currency}
            label={t("Your payment schedule")}
            rows={share.rows.map((row) => ({ key: `${row.installment}-${row.dueDate}`, dueDate: row.dueDate, principalMinor: row.principalMinor, interestMinor: row.interestMinor + row.penaltyMinor, totalMinor: row.totalMinor }))}
          />
        </Dialog>
      ) : null}
      {confirmOpen ? (
        <ConfirmDialog
          amountLabel={t("Investment amount")}
          amountMinor={amountMinor}
          busy={submitting}
          busyLabel={t("Confirming...")}
          code={code}
          codeRequest={codeRequest}
          confirmLabel={t("Confirm and reserve")}
          error={error}
          intro={subscription ? t("Confirm your reservation for the Loan Originator funding round.") : t("Confirm your investment reservation.")}
          kit={kit}
          loan={loan}
          note={t("Your funds are reserved after confirmation.")}
          onClose={() => setConfirmOpen(false)}
          onCode={setCode}
          onConfirm={() => void confirm()}
          title={t("Confirm your investment")}
        />
      ) : null}
    </>
  );
}

function ClaimPurchaseReview({ loan, initialAmount, kit, onAddFunds }: { loan: MarketplaceLoanDetail; initialAmount?: string; kit: SensitiveActionKit; onAddFunds: () => void }) {
  const t = useT();
  useNumberFormat();
  const queryClient = useQueryClient();
  const [terms, setTerms] = useState(false);
  const [risks, setRisks] = useState(false);
  const [quote, setQuote] = useState<OriginatorClaimQuoteResponse | null>(null);
  const [claimAttempt, setClaimAttempt] = useState<ClaimPurchaseAttempt | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [quoteError, setQuoteError] = useState("");
  const [done, setDone] = useState(false);
  const amount = useReviewAmount(loan, initialAmount, () => {
    // New economics: a new quote, accepted again (audit A-37).
    setQuote(null);
    setClaimAttempt(null);
    setTerms(false);
    setRisks(false);
    setQuoteError("");
  });
  const amountMinor = amount.appliedMinor ?? 0;
  const quoteMutation = useOriginatorClaimsLoansQuoteCreate();
  const purchaseMutation = useOriginatorClaimsQuotesPurchaseCreate();
  // The purchase as the server booked it (reference, time and amount paid on the result page).
  const [purchase, setPurchase] = useState<OriginatorClaimPurchaseResponse | null>(null);
  const acceptanceMutation = useV1DocumentsAcceptancesCreate();
  const { useCode, useAutoRequest } = kit;
  const codeRequest = useCode(ActionEnum.primary_investment);
  useAutoRequest(codeRequest, confirmOpen);
  const termsQuery = useV1DocumentsTemplatesCurrentRetrieve(
    { category: CategoryEnum.primary_market_investment },
    { query: { enabled: !isFixturePreview, retry: false } }
  );
  const places = placesInfo(loan);
  const busy = quoteMutation.isPending || acceptanceMutation.isPending || purchaseMutation.isPending;

  const applyQuote = (next: OriginatorClaimQuoteResponse) => {
    setQuote(next);
    setClaimAttempt(newClaimPurchaseAttempt(next.quote_id));
    setTerms(false);
    setRisks(false);
  };
  const requestQuote = async () => {
    setQuoteError("");
    if (!amount.valid) return;
    if (isFixturePreview) {
      const assigned = Math.min(amountMinor, loan.remaining_capacity_minor);
      applyQuote({
        quote_id: "preview-originator-quote",
        loan_id: loan.loan_id,
        currency: loan.currency,
        requested_cash_minor: amountMinor,
        executable_cash_minor: amountMinor,
        assigned_principal_minor: assigned,
        outstanding_principal_at_pricing_minor: loan.principal_minor,
        share_ppm: loan.principal_minor > 0 ? Math.round((assigned * 1_000_000) / loan.principal_minor) : 0,
        target_yield_bps: loan.yield_bps,
        premium_discount_minor: amountMinor - assigned,
        rounding_remainder_minor: 0,
        entitlement_start_at: new Date().toISOString(),
        expires_at: new Date(Date.now() + 5 * 60_000).toISOString(),
        cash_flows: (loan.originator_schedule ?? []).filter((row) => Date.parse(row.due_date) > Date.now()).map((row) => ({
          installment_number: row.installment_number,
          accrual_start_date: row.accrual_start_date,
          due_date: row.due_date,
          principal_minor: loan.principal_minor > 0 ? Math.round((row.principal_minor * assigned) / loan.principal_minor) : 0,
          interest_minor: loan.principal_minor > 0 ? Math.round((row.interest_minor * assigned) / loan.principal_minor) : 0,
          penalty_minor: 0,
          total_minor: loan.principal_minor > 0 ? Math.round((row.total_minor * assigned) / loan.principal_minor) : 0,
          days_to_payment: Math.max(0, Math.ceil((Date.parse(row.due_date) - Date.now()) / 86_400_000)),
          present_value_minor: 0
        }))
      });
      return;
    }
    try {
      applyQuote(await quoteMutation.mutateAsync({ loanId: loan.loan_id, data: { requested_cash_minor: amountMinor } }));
    } catch (mutationError) {
      if (isSwissInvestorLimitError(mutationError)) void queryClient.invalidateQueries();
      setQuoteError(apiErrorMessage(mutationError));
    }
  };
  const reprice = () => {
    setQuote(null);
    setClaimAttempt(null);
    setTerms(false);
    setRisks(false);
    setError("");
  };

  const confirm = async () => {
    if (!quote) return;
    setError("");
    if (isFixturePreview) {
      if (codeRequest.pin.previewAccepts()) {
        setConfirmOpen(false);
        setDone(true);
      }
      return;
    }
    const labels = templateLabels(termsQuery.data);
    if (!termsQuery.data || labels.length === 0) {
      setError(t("Current investment terms are not available. Retry after the document template is published."));
      return;
    }
    if (!codeRequest.codeId) {
      setError(t("Request an email code before confirming the purchase."));
      return;
    }
    let current = claimAttempt?.quoteId === quote.quote_id ? claimAttempt : newClaimPurchaseAttempt(quote.quote_id);
    try {
      const acceptance = current.acceptanceId
        ? { id: current.acceptanceId }
        : await acceptanceMutation.mutateAsync({
            data: {
              category: CategoryEnum.primary_market_investment,
              expected_template_version_id: termsQuery.data.id,
              accepted_checkbox_labels: labels,
              context_type: "originator_claim_quote",
              context_id: quote.quote_id,
              data_snapshot: {
                loan_id: loan.loan_id,
                originator_claim_quote_id: quote.quote_id,
                requested_cash_minor: quote.requested_cash_minor,
                executable_cash_minor: quote.executable_cash_minor,
                assigned_principal_minor: quote.assigned_principal_minor,
                currency: quote.currency,
                target_yield_bps: quote.target_yield_bps
              },
              idempotency_key: current.acceptanceKey
            }
          });
      current = { ...current, acceptanceId: acceptance.id };
      setClaimAttempt(current);
      const booked = await purchaseMutation.mutateAsync({
        quoteId: quote.quote_id,
        data: {
          document_acceptance_id: acceptance.id,
          sensitive_action_code_id: codeRequest.codeId,
          sensitive_action_code: code,
          pin: codeRequest.pin.value,
          idempotency_key: current.purchaseKey
        }
      });
      setPurchase(booked);
      void queryClient.invalidateQueries();
      setConfirmOpen(false);
      setDone(true);
    } catch (mutationError) {
      if (codeRequest.pin.handleError(mutationError)) return;
      if (isSwissInvestorLimitError(mutationError)) void queryClient.invalidateQueries();
      setError(apiErrorMessage(mutationError));
    }
  };

  if (done && quote) {
    return (
      <ResultPage
        amountLabel={t("Amount paid")}
        amountMinor={purchase ? purchase.cash_consideration_minor : quote.executable_cash_minor}
        lastStepLabel={t("Purchased")}
        loan={loan}
        reference={purchase ? `${purchase.purchase_id.slice(0, 8).toUpperCase()} · ${formatDateTime(purchase.purchased_at)}` : undefined}
        refused={false}
        showNext={false}
        text={t("The assigned claim is now in your portfolio. Repayments are credited to your Banxum balance. Your acceptance record is in Documents.")}
        title={t("Claim purchased")}
      />
    );
  }

  const ready = Boolean(quote) && terms && risks && amount.valid && !places?.fullForViewer;
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!quote) {
      void requestQuote();
      return;
    }
    if (ready) {
      setError("");
      setCode("");
      setConfirmOpen(true);
    }
  };
  const flowRows = (quote?.cash_flows ?? []).map((flow) => ({ key: `${flow.installment_number}-${flow.due_date}`, dueDate: flow.due_date, principalMinor: flow.principal_minor, interestMinor: flow.interest_minor, totalMinor: flow.total_minor }));

  return (
    <>
      <ReviewFrame
        agreement={
          quote ? (
            <>
              <Acceptances
                onRisks={setRisks}
                onTerms={setTerms}
                risks={risks}
                terms={terms}
                termsLabel={t("I accept the investment terms and the immediate assignment of the claim.")}
              />
              {!isFixturePreview && termsQuery.isError ? <div className="alert alert-danger" role="alert">{t("The current investment terms could not be loaded.")}</div> : null}
              <SignActions
                disabled={!ready}
                extra={<button className="link u33-invest-reprice" onClick={reprice} type="button">{t("Reprice")}</button>}
                label={t("Confirm purchase")}
              />
            </>
          ) : (
            <>
              <div className="rp-consents">
                <h3>{t("Executable quote")}</h3>
                <p>{t("This is an existing loan sold by {originator}. Banxum prices the remaining payments to the yield shown and assigns the claim to you immediately after confirmation. A quote stays executable for five minutes.", { originator: loan.originator_name || t("the loan originator") })}</p>
                {quoteError ? <div className="alert alert-danger" role="alert">{quoteError}</div> : null}
              </div>
              <div className="rl29-sign-actions">
                <button className="ip-continue" disabled={!amount.valid || busy || Boolean(places?.fullForViewer)} type="submit">
                  {quoteMutation.isPending ? t("Pricing...") : t("Get executable quote")}
                </button>
              </div>
            </>
          )
        }
        lastStepLabel={t("Purchased")}
        loan={loan}
        onSubmit={submit}
        summary={
          <>
            <ReviewAmount
              action={amount.error?.shortfall ? <button className="btn btn-sm btn-outline-light" onClick={onAddFunds} type="button">{t("Add funds")}</button> : null}
              appliedMinor={amount.appliedMinor}
              currency={loan.currency}
              error={amount.error?.message ?? ""}
              onApply={amount.apply}
              onCancel={amount.cancel}
              status={amount.status}
            />
            <div id="iv-summary">
              <div className="ip-terms">
                <div className="ip-term"><strong>{formatRateBps(loan.yield_bps)}</strong><span>{t("Target yield (effective annual)")}</span></div>
                <div className="ip-term">
                  {loan.remaining_term_days !== null
                    ? <><strong>{loan.remaining_term_days} <small>{t("days")}</small></strong><span>{t("Remaining term")}</span></>
                    : <><strong>{loan.term_months} <small>{t("months")}</small></strong><span>{t("Duration")}</span></>}
                </div>
              </div>
              {quote ? (
                <>
                  <div className="ip-money-summary">
                    <div className="ip-summary-line"><span>{t("Cash price")}</span><strong>{formatMoneyLabel(quote.currency, quote.executable_cash_minor)}</strong></div>
                    <div className="ip-summary-line"><span>{t("Principal assigned")}</span><strong>{formatMoneyLabel(quote.currency, quote.assigned_principal_minor)}</strong></div>
                    <div className="ip-summary-line"><span>{quote.premium_discount_minor >= 0 ? t("Premium") : t("Discount")}</span><strong>{formatMoneyLabel(quote.currency, Math.abs(quote.premium_discount_minor))}</strong></div>
                    <div className="ip-summary-line"><span>{t("Quote expires")}</span><strong>{formatDateTime(quote.expires_at)}</strong></div>
                  </div>
                  {flowRows.length > 0 ? (
                    <button aria-haspopup="dialog" className="ip-schedule r52-schedule-toggle" onClick={() => setScheduleOpen(true)} type="button">
                      <NiIcon name="calendar" />
                      <span className="r36-toggle-copy"><strong>{t("Your quoted payments")}</strong><small>{t("{count} payments", { count: flowRows.length })}</small></span>
                      <span className="r36-chevron"><NiIcon name="arrow-up-right" /></span>
                    </button>
                  ) : null}
                </>
              ) : null}
              <div className="ip-money-summary">
                <div className="ip-summary-line rl29-replaced-fee"><span>{t("Investment fees")}</span><strong>{t("None")}</strong></div>
              </div>
            </div>
          </>
        }
      />
      {scheduleOpen && quote ? (
        <Dialog className="u33-invest-schedule-dialog" onClose={() => setScheduleOpen(false)} size="lg" title={t("Your quoted payments")}>
          <p className="bxm-muted">{t("The payments of the claim share in this quote. Repayments are credited to your Banxum balance and are not guaranteed.")}</p>
          <ScheduleTable currency={quote.currency} label={t("Your quoted payments")} rows={flowRows} />
        </Dialog>
      ) : null}
      {confirmOpen && quote ? (
        <ConfirmDialog
          amountLabel={t("Cash price")}
          amountMinor={quote.executable_cash_minor}
          busy={busy}
          busyLabel={t("Purchasing...")}
          code={code}
          codeRequest={codeRequest}
          confirmLabel={t("Purchase claim")}
          error={error}
          intro={t("A successful confirmation assigns the claim to you immediately.")}
          kit={kit}
          loan={loan}
          note={t("The quote expires {time}.", { time: formatDateTime(quote.expires_at) })}
          onClose={() => setConfirmOpen(false)}
          onCode={setCode}
          onConfirm={() => void confirm()}
          title={t("Confirm your claim purchase")}
        />
      ) : null}
    </>
  );
}
