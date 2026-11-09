// IP of Webby-Soft SRL.
// Investment page (design #/investments/:id, route /portfolio/:holdingId, U33 slice S3). A holding shows
// its state (on schedule, payment due, late, default, repaid, sold), outstanding principal, interest
// received and to be received, the next payment, the "All payments" schedule, details, security,
// documents and "Sell investment" when today's rules allow it. An open primary order (In funding) uses
// the same address with its order id and shows the reserved state.
import { useState, type ReactNode } from "react";

import type { Holding, PrimaryOrderPortal } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { frozenActionReason, useFrozenAccount } from "../../../investorPortal/accountState";
import { useLoanDetailData, usePortfolioData, usePrimaryOrdersData, useSecondaryActivityData } from "../../../investorPortal/data";
import { formatDate, formatMoneyMinor, formatRateBps, useNumberFormat } from "../../../investorPortal/format";
import { currentLoanPrincipalMinor, loanLtvBps } from "../../../investorPortal/portfolioCollateral";
import { Button, ButtonLink, EmptyState, InfoTip, NiIcon, PageHead, PortalLink } from "../../components";
import { CancelListingDialog, SellInvestmentDialog } from "./SellInvestmentDialog";
import { InvestmentDocuments } from "./parts/documents";
import { isReadonlyView } from "./parts/errors";
import { InvestmentPayments } from "./parts/InvestmentPayments";
import {
  completedOnDate,
  holdingState,
  interestReceivedMinor,
  investorRateBps,
  isOpenOrder,
  lifetimeInterestMinor,
  maturityDate,
  orderAmountMinor,
  principalReturnedMinor
} from "./parts/investmentModel";
import { investmentTypeText, monthsText, repaymentText, stateTag } from "./parts/labels";
import { LatePaymentUpdate, LoanNotes, RecoveryUpdate } from "./parts/LoanUpdates";
import { SecuritySection } from "./parts/SecuritySection";
import { BackLink, PageError, PageLoading } from "./parts/ui";
import "./portfolio.css";

const PAGE_CLASS = "rid-view r71-view";

export function InvestmentDetailScreen({ holdingId, focusSection }: { holdingId: string; focusSection?: string }) {
  const t = useT();
  const portfolioQuery = usePortfolioData(true);
  const ordersQuery = usePrimaryOrdersData();
  if (portfolioQuery.isError && !portfolioQuery.data) {
    return <PageError className={PAGE_CLASS} message={t("This investment could not be loaded. Retry once the connection is restored.")} onRetry={() => void portfolioQuery.refetch()} title={t("Investment")} />;
  }
  if (!portfolioQuery.data) return <PageLoading className={PAGE_CLASS} title={t("Investment")} />;
  const holding = portfolioQuery.data.holdings.find((candidate) => candidate.id === holdingId);
  if (holding) return <HoldingView focus={focusSection === "loan-notes"} holding={holding} key={holding.id} />;
  const order = ordersQuery.data?.orders.find((candidate) => candidate.id === holdingId && isOpenOrder(candidate));
  if (order) return <ReservedView key={order.id} order={order} />;
  if (ordersQuery.isPending && !ordersQuery.data) return <PageLoading className={PAGE_CLASS} title={t("Investment")} />;
  return (
    <main className={PAGE_CLASS}>
      <div className="nk-block-head nk-block-head-sm">
        <div className="nk-block-head-sub"><BackLink className="back-to" to="portfolio">{t("My investments")}</BackLink></div>
      </div>
      <PageHead title={t("Investment not found")} />
      <div className="card card-bordered u33-state-card">
        <EmptyState actions={<ButtonLink to="portfolio" variant="secondary">{t("Back to My investments")}</ButtonLink>} icon="search" title={t("We could not find this investment")}>
          {t("It is not in your portfolio. It may have been sold, or the link may be wrong.")}
        </EmptyState>
      </div>
    </main>
  );
}

function DetailHead({ title, subtitle, tag, tagClass, actions }: { title: string; subtitle: string; tag: { tone: string; label: string }; tagClass: string; actions: ReactNode[] }) {
  const t = useT();
  const toneClass = tag.tone === "neutral" ? "" : `is-${tag.tone}`;
  return (
    <div className="nk-block-head nk-block-head-sm">
      <div className="nk-block-head-sub"><BackLink className="back-to" to="portfolio">{t("My investments")}</BackLink></div>
      <div className="nk-block-between g-3">
        <div className="nk-block-head-content">
          <h1 className="nk-block-title page-title">{title}</h1>
          <div className="nk-block-des text-soft">
            <p>
              {subtitle} <span className={`bxm-tag ${toneClass} r71-status ${tagClass}`.replace(/\s+/g, " ").trim()}>{tag.label}</span>
            </p>
          </div>
        </div>
        <div className="nk-block-head-content" />
        {actions.length > 0 ? (
          <ul className="nk-block-tools g-3 rid-actions">
            {actions.map((action, index) => <li key={index}>{action}</li>)}
          </ul>
        ) : null}
      </div>
    </div>
  );
}

function Fact({ label, children, className = "", info }: { label: string; children: ReactNode; className?: string; info?: ReactNode }) {
  return (
    <div className={className || undefined}>
      <span className="r71-label">{label}{info}</span>
      <strong className="r71-value">{children}</strong>
    </div>
  );
}

function MoneyValue({ currency, amountMinor }: { currency: string; amountMinor: number }) {
  useNumberFormat();
  return <><small>{currency}</small> {formatMoneyMinor(amountMinor, currency)}</>;
}

function Record({ label, value, className = "" }: { label: string; value: ReactNode; className?: string }) {
  return (
    <div className="u102-record-field">
      <dt>{label}</dt>
      <dd className={className}>{value}</dd>
    </div>
  );
}

function HoldingView({ holding, focus }: { holding: Holding; focus: boolean }) {
  const t = useT();
  useNumberFormat();
  const frozenAccount = useFrozenAccount();
  const activityQuery = useSecondaryActivityData();
  const [dialog, setDialog] = useState<"sell" | "edit" | "cancel" | null>(null);
  const loan = holding.loan;
  const state = holdingState(holding);
  const tag = stateTag(state, loan.days_past_due);
  const currency = holding.currency;
  const money = (amount: number) => `${currency} ${formatMoneyMinor(amount, currency)}`;
  const listing = holding.open_secondary_listing && holding.open_secondary_listing.status === "active" ? holding.open_secondary_listing : null;
  const blockedReason = frozenAccount.frozen ? frozenActionReason(frozenAccount) : isReadonlyView() ? t("This is a read-only view. Resale actions are disabled.") : "";
  // Rule C18: only a holding of a performing (active) loan can be listed; there is no approval request.
  const canSell = state === "active" && !listing && !blockedReason;
  const sale = state === "sold" ? (activityQuery.data?.entries ?? []).find((entry) => entry.action === "sale" && entry.holding_id === holding.id) : undefined;
  const lifetime = lifetimeInterestMinor(holding);
  const maturity = maturityDate(holding);
  const isClaim = loan.product_type === "originator_claim";
  const inRecovery = state === "default" || state === "writtenOff";
  const finished = state === "repaid" || state === "sold";

  const actions: ReactNode[] = [];
  if (canSell) actions.push(<Button icon="coins" key="sell" onClick={() => setDialog("sell")}>{t("Sell investment")}</Button>);
  if (listing && !blockedReason) {
    actions.push(<Button icon="edit" key="edit" onClick={() => setDialog("edit")}>{t("Edit listing")}</Button>);
    actions.push(<Button icon="cross-circle-fill" key="cancel" onClick={() => setDialog("cancel")}>{t("Cancel listing")}</Button>);
  }
  actions.push(<ButtonLink icon="briefcase" key="project" params={{ loanId: loan.loan_id }} to="loan">{t("View project")}</ButtonLink>);

  const resaleNote = listing
    ? t("Listed on the resale market at {price}. A buyer must purchase it for the sale to complete.", { price: money(listing.transfer_price_minor) })
    : state === "funded"
      ? t("You can sell this investment on the resale market after the loan is paid out to the borrower.")
      : state === "active" && blockedReason
        ? blockedReason
        : "";

  return (
    <main className={PAGE_CLASS}>
      <DetailHead
        actions={actions}
        subtitle={loan.borrower_name}
        tag={tag}
        tagClass={state === "active" ? "r71-on-schedule" : state === "repaid" ? "r79-repaid" : ""}
        title={loan.loan_title}
      />
      {resaleNote ? (
        <div className={`alert ${listing ? "alert-info" : "alert-light"} alert-icon u33-resale-note`}>
          <NiIcon name={listing ? "exchange" : "info"} />
          {resaleNote}
        </div>
      ) : null}
      <div className="nk-block">
        <div className="card card-bordered rid-card r71-body">
          {inRecovery ? (
            <section aria-label={t("Investment summary")} className="r71-finances r79-state-summary r71-three-facts">
              <Fact label={t("Principal in recovery")}><MoneyValue amountMinor={holding.current_principal_minor} currency={currency} /></Fact>
              <Fact className="r71-earned" label={t("Interest received")}><MoneyValue amountMinor={interestReceivedMinor(holding)} currency={currency} /></Fact>
              <Fact className="r71-fact r79-state-fact" label={t("Days overdue")}>{loan.days_past_due}</Fact>
            </section>
          ) : finished ? (
            <section aria-label={t("Investment summary")} className="r71-finances r79-state-summary r71-three-facts">
              {state === "sold" ? (
                <Fact label={sale ? t("Sold for") : t("Principal returned")}><MoneyValue amountMinor={sale ? sale.cash_amount_minor : principalReturnedMinor(holding)} currency={currency} /></Fact>
              ) : (
                <Fact label={t("Principal repaid")}><MoneyValue amountMinor={principalReturnedMinor(holding)} currency={currency} /></Fact>
              )}
              <Fact className="r71-earned" label={t("Interest received")}><MoneyValue amountMinor={interestReceivedMinor(holding)} currency={currency} /></Fact>
              <Fact className="r71-fact r79-state-fact" label={state === "sold" ? t("Sold on") : t("Fully repaid on")}>
                {state === "sold" ? (sale ? formatDate(sale.occurred_at) : "—") : (completedOnDate(holding) ? formatDate(completedOnDate(holding)) : "—")}
              </Fact>
            </section>
          ) : (
            <section aria-label={t("Investment summary")} className="r71-finances">
              <Fact
                info={<InfoTip label={t("Outstanding principal")} title={t("Outstanding principal")}>{t("The invested amount still to be repaid, excluding interest.")}</InfoTip>}
                label={t("Outstanding principal")}
              >
                <MoneyValue amountMinor={holding.current_principal_minor} currency={currency} />
              </Fact>
              <Fact className="r71-earned" label={t("Interest received")}><MoneyValue amountMinor={interestReceivedMinor(holding)} currency={currency} /></Fact>
              <Fact className="r71-fact r71-rate" label={t("Annual interest rate")}>{formatRateBps(investorRateBps(loan))}</Fact>
              <Fact className="r71-fact" label={t("Maturity")}>{maturity ? formatDate(maturity) : "—"}</Fact>
            </section>
          )}

          {state === "late" || state === "due" ? <LatePaymentUpdate focus={focus} holding={holding} /> : null}
          {inRecovery ? <RecoveryUpdate focus={focus} holding={holding} /> : null}

          <InvestmentPayments holding={holding} />

          <section className="r71-secondary p73-secondary p99v2-secondary">
            <details className="rid-details">
              <summary className="u102-details-heading">
                <span className="u102-details-title">{t("Investment details")}</span>
                <NiIcon name="chevron-down" />
              </summary>
              <div className="rid-details-body">
                <div className="p99v2-facts">
                  <div className="p99v2-repayment">
                    <span>{t("Repayments")}</span>
                    <strong>{repaymentText(loan.repayment_type)}</strong>
                    <small>{t("Credited to your Banxum balance")}</small>
                  </div>
                  {lifetime !== null ? (
                    <div className="p99v2-interest">
                      <span>{t("Projected total interest")}</span>
                      <strong>{money(lifetime)}</strong>
                    </div>
                  ) : null}
                </div>
                <div className="p99v2-records u102-records">
                  <dl className="u102-record-row">
                    <Record label={t("Initial investment")} value={money(holding.original_principal_minor)} />
                    {isClaim && loan.maturity_date ? <Record label={t("Matures")} value={formatDate(loan.maturity_date)} /> : <Record label={t("Term")} value={monthsText(loan.term_months)} />}
                  </dl>
                  <dl className="u102-record-row">
                    <Record label={holding.source_type === "secondary_market" ? t("Bought on") : t("Invested on")} value={formatDate(holding.assignment_effective_at)} />
                    <Record label={t("Investment type")} value={investmentTypeText(loan.product_type, holding.source_type)} />
                  </dl>
                  {isClaim && loan.originator_name ? (
                    <dl className="u102-record-row u102-single">
                      <Record label={t("Originator")} value={loan.originator_name} />
                    </dl>
                  ) : null}
                  <dl className="u102-record-row u102-identifiers u102-single">
                    <Record label={t("Reference")} value={holding.id} />
                  </dl>
                </div>
                {isClaim && loan.originator_name && loan.skin_in_the_game_bps > 0 ? (
                  <p className="u33-muted u33-retained">
                    {t("{originator} keeps at least {share} of the loan's outstanding principal. This retained part is not offered to investors and shrinks as the principal is repaid.", { originator: loan.originator_name, share: formatRateBps(loan.skin_in_the_game_bps) })}
                  </p>
                ) : null}
              </div>
            </details>
            <div className="p99v2-access">
              <SecuritySection
                collateralType={loan.collateral_type}
                collateralValueMinor={loan.collateral_value_minor}
                currency={currency}
                description={loan.collateral_description}
                loanId={loan.loan_id}
                loanPrincipalMinor={currentLoanPrincipalMinor(loan) ?? loan.principal_minor}
                ltvBps={loanLtvBps(loan)}
              />
              <PortalLink className="p99v2-access-row p99v2-credit" params={{ loanId: loan.loan_id }} to="loan">
                <span className="p99v2-access-copy">
                  <strong>{t("Credit file")}</strong>
                  <span>{t("Business, financials and loan documents")}</span>
                </span>
                <NiIcon name="arrow-right" />
              </PortalLink>
            </div>
            {!(state === "late" || state === "due" || inRecovery) ? <LoanNotes focus={focus} loanId={loan.loan_id} /> : null}
            <InvestmentDocuments holdingId={holding.id} loanTitle={loan.loan_title} />
          </section>
        </div>
      </div>
      {dialog === "sell" || dialog === "edit" ? <SellInvestmentDialog holding={holding} listing={dialog === "edit" ? listing : null} onClose={() => setDialog(null)} /> : null}
      {dialog === "cancel" && listing ? <CancelListingDialog holding={holding} listing={listing} onClose={() => setDialog(null)} /> : null}
    </main>
  );
}

function ReservedView({ order }: { order: PrimaryOrderPortal }) {
  const t = useT();
  useNumberFormat();
  const loanQuery = useLoanDetailData(order.loan_id);
  const loan = loanQuery.data?.loan_id === order.loan_id ? loanQuery.data : undefined;
  const allocated = order.allocated_amount_minor > 0;
  const money = (amount: number) => `${order.currency} ${formatMoneyMinor(amount, order.currency)}`;
  const reservedOn = order.allocated_at ?? order.created_at;
  const closes = loan?.funding_deadline;
  return (
    <main className={PAGE_CLASS}>
      <DetailHead
        actions={[<ButtonLink icon="briefcase" key="project" params={{ loanId: order.loan_id }} to="loan">{t("View project")}</ButtonLink>]}
        subtitle={loan?.borrower_display_name || loan?.originator_name || ""}
        tag={{ tone: "neutral", label: allocated ? t("Reserved") : t("Requested") }}
        tagClass=""
        title={order.loan_title}
      />
      <div className="alert alert-warning alert-icon">
        <NiIcon name="clock" />
        {allocated
          ? closes
            ? t("Reserved from your Banxum balance on {date}. Funding closes on {closes}. If funding closes successfully, your investment starts and repayments follow the payment schedule.", { date: formatDate(reservedOn), closes: formatDate(closes) })
            : t("Reserved from your Banxum balance on {date}. If funding closes successfully, your investment starts and repayments follow the payment schedule.", { date: formatDate(reservedOn) })
          : t("Your order of {date} is recorded, but no balance is reserved for it yet. Only a reserved amount can become an investment when funding closes.", { date: formatDate(order.created_at) })}
      </div>
      <div className="nk-block">
        <div className="card card-bordered rid-card r31m-reserved r71-body">
          <section aria-label={t("Investment summary")} className="r71-finances r71-three-facts">
            <Fact label={allocated ? t("Reserved for this investment") : t("Requested amount")}><MoneyValue amountMinor={orderAmountMinor(order)} currency={order.currency} /></Fact>
            {loan ? <Fact className="r71-fact r71-rate" label={t("Annual interest rate")}>{formatRateBps(investorRateBps(loan))}</Fact> : null}
            {loan ? <Fact className="r71-fact" label={t("Term")}>{monthsText(loan.term_months)}</Fact> : null}
          </section>
          <section className="r71-secondary p73-secondary p99v2-secondary">
            <details className="rid-details">
              <summary className="u102-details-heading">
                <span className="u102-details-title">{t("Investment details")}</span>
                <NiIcon name="chevron-down" />
              </summary>
              <div className="rid-details-body">
                {loan ? (
                  <div className="p99v2-facts">
                    <div className="p99v2-repayment">
                      <span>{t("Repayments")}</span>
                      <strong>{repaymentText(loan.repayment_type)}</strong>
                      <small>{t("Payments start after closing")}</small>
                    </div>
                  </div>
                ) : null}
                <div className="p99v2-records u102-records">
                  <dl className="u102-record-row">
                    <Record label={allocated ? t("Reserved on") : t("Requested on")} value={formatDate(reservedOn)} />
                    {closes ? <Record label={t("Expected closing")} value={formatDate(closes)} /> : null}
                  </dl>
                  {order.allocated_amount_minor > 0 && order.allocated_amount_minor < order.requested_amount_minor ? (
                    <dl className="u102-record-row u102-single">
                      <Record label={t("Requested amount")} value={money(order.requested_amount_minor)} />
                    </dl>
                  ) : null}
                  {loan ? (
                    <dl className="u102-record-row">
                      <Record label={t("Investment type")} value={investmentTypeText(loan.product_type)} />
                      {loan.originator_name ? <Record label={t("Originator")} value={loan.originator_name} /> : null}
                    </dl>
                  ) : null}
                  <dl className="u102-record-row u102-identifiers u102-single">
                    <Record label={t("Reference")} value={order.id} />
                  </dl>
                </div>
              </div>
            </details>
            {loan ? (
              <div className="p99v2-access">
                <SecuritySection
                  collateralType={loan.collateral_type}
                  collateralValueMinor={loan.collateral_value_minor}
                  currency={order.currency}
                  description={loan.collateral_description}
                  loanId={loan.loan_id}
                  loanPrincipalMinor={loan.principal_minor}
                  ltvBps={loanLtvBps(loan)}
                />
              </div>
            ) : null}
            <InvestmentDocuments loanTitle={order.loan_title} orderId={order.id} />
          </section>
        </div>
      </div>
    </main>
  );
}
