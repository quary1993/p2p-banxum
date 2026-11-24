// IP of Webby-Soft SRL.
// One resale offer (design: the opportunity page in resale context, main.r69-page with aside.r69-purchase),
// reached with "View offer" (/secondary-market?offer=<id>). The purchase uses today's flow (BuyListingModal
// of the old screen): the fresh listing price, the buyer terms (U33-DEC-14: the buyer agreement), the email
// code + PIN, and a "price changed" answer that reloads the price for a new review. Nothing is charged
// before the server confirms.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import {
  ActionEnum,
  CategoryEnum,
  getV1MarketplaceSecondaryListingsListQueryKey,
  useV1DocumentsAcceptancesCreate,
  useV1DocumentsTemplatesCurrentRetrieve,
  useV1MarketplaceSecondaryListingsPurchaseCreate,
  type SecondaryMarketBuyerListingDetail
} from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { frozenActionReason, useFrozenAccount } from "../../../investorPortal/accountState";
import { isFixturePreview, useBalancesData, useLoanDetailData, useSecondaryListingDetailData } from "../../../investorPortal/data";
import { formatDate, formatMoneyMinor, formatRateBps, useNumberFormat } from "../../../investorPortal/format";
import { currentLoanPrincipalMinor, loanLtvBps } from "../../../investorPortal/portfolioCollateral";
import { Button, ButtonLink, Dialog, EmptyState, NiIcon, PortalLink, StatusTag } from "../../components";
import { borrowerDisclosure, collateralLabel, frequencyWords, placeName } from "../invest/loanFacts";
import { ConfirmFields } from "./parts/ConfirmFields";
import { confirmationReady, useActionConfirmation } from "./parts/confirmation";
import { TermsLink } from "./parts/documents";
import { errorMessage, idempotencyKey, isPriceChangedError, isReadonlyView, templateLabels } from "./parts/errors";
import { investmentTypeText, priceAdjustmentText, projectedReturnText, repaymentText, tileIcon } from "./parts/labels";
import { SecuritySection } from "./parts/SecuritySection";
import { ResaleHelpDialog } from "./parts/ResaleHelpDialog";
import { InfoButton } from "./parts/ui";

/** Repayment types with periodic payments (design: "Remaining monthly payments", with the loan's frequency). */
const PERIODIC_REPAYMENTS = new Set(["equal_installments", "amortizing_principal_interest", "bullet_periodic_interest", "interest_only_then_bullet", "interest_only_then_amortizing"]);

const PAGE_CLASS = "bxm-invest-desktop ip-page l8-opportunity r34-project-entry r36-opportunity r69-page";

export function ResaleOfferView({ listingId, onBack, onMine }: { listingId: string; onBack: () => void; onMine: () => void }) {
  const t = useT();
  const detailQuery = useSecondaryListingDetailData(listingId);
  const detail = detailQuery.data && (isFixturePreview || detailQuery.data.id === listingId) ? detailQuery.data : undefined;
  const back = (
    <div className="l8-back-row">
      <a
        className="ip-back"
        href={window.location.pathname}
        onClick={(event) => {
          event.preventDefault();
          onBack();
        }}
      >
        <NiIcon name="arrow-left" />
        {t("Resale market")}
      </a>
    </div>
  );
  if (!detail) {
    return (
      <main className={PAGE_CLASS}>
        {back}
        <section className="ip-panel">
          {detailQuery.isError ? (
            <EmptyState actions={<Button onClick={() => void detailQuery.refetch()}>{t("Retry")}</Button>} icon="alert-circle" title={t("This offer could not be loaded")}>
              {t("It may have been sold or withdrawn. Retry, or go back to the resale market.")}
            </EmptyState>
          ) : (
            <p className="u33-muted" role="status">{t("Loading the offer...")}</p>
          )}
        </section>
      </main>
    );
  }
  return <OfferPage back={back} detail={detail} onMine={onMine} refetch={() => void detailQuery.refetch()} refreshing={detailQuery.isFetching} />;
}

function OfferPage({ detail, back, onMine, refetch, refreshing }: { detail: SecondaryMarketBuyerListingDetail; back: ReactNode; onMine: () => void; refetch: () => void; refreshing: boolean }) {
  const t = useT();
  useNumberFormat();
  const scheduleId = useId();
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [buying, setBuying] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const balances = useBalancesData().data;
  const frozenAccount = useFrozenAccount();
  // The loan's public detail adds what the listing does not carry: sector, project text, security
  // description and value (design: the offer page shows them like the opportunity page).
  const loanQuery = useLoanDetailData(detail.loan_id);
  const loan = loanQuery.data?.loan_id === detail.loan_id ? loanQuery.data : undefined;
  const disclosure = loan ? borrowerDisclosure(loan) : {};
  const meta = [detail.borrower_name, placeName(disclosure.city, disclosure.country || detail.borrower_country), disclosure.business_classification || disclosure.industry_activity || ""].filter(Boolean);
  const story = loan ? loan.purpose_description || loan.investor_summary || collateralLabel(loan.purpose) : "";
  const currency = detail.currency;
  const money = (amount: number) => `${currency} ${formatMoneyMinor(amount, currency)}`;
  const isOwn = detail.is_own_listing;
  const late = detail.loan_status_at_listing === "late" || detail.days_past_due > 0;
  const adjustmentMinor = detail.transfer_price_minor - detail.current_principal_minor;
  const rows = [...detail.investment_schedule].sort((left, right) => left.due_date.localeCompare(right.due_date));
  const next = rows[0];
  const remainingInterest = rows.reduce((sum, row) => sum + row.projected_interest_minor, 0);
  const availableMinor = balances?.summaries.find((summary) => summary.currency === currency)?.investable_minor ?? 0;
  const shortfall = Math.max(0, detail.buyer_total_cost_minor - availableMinor);
  const blockedReason = frozenAccount.frozen
    ? `${frozenActionReason(frozenAccount)} ${t("You can still review every offer.")}`
    : isReadonlyView()
      ? t("This is a read-only view. Offers can be reviewed, but purchases are disabled.")
      : "";

  return (
    <main className={PAGE_CLASS}>
      {back}
      <section className="ip-panel">
        <header className="ip-project l8-project-header">
          <span className="ip-project-icon"><NiIcon name={tileIcon(detail.collateral_type)} /></span>
          <div>
            <h1>{detail.loan_title}</h1>
            <p>
              {meta.join(" · ")}
              {meta.length > 0 ? " · " : ""}
              <span className="r58-claim"><span className="l8-type">{investmentTypeText(detail.product_type)}</span></span>{" "}
              {late ? (
                <StatusTag tone="late">{detail.days_past_due > 0 ? t("Late payment · {days} days", { days: detail.days_past_due }) : t("Late payment")}</StatusTag>
              ) : (
                <span className="l8-open is-solid r58-project-status">{t("Repaying")}</span>
              )}
            </p>
          </div>
        </header>
        <div className="l8-op-grid">
          <section className="l8-information">
            <div className="l8-terms">
              <div>
                <strong>{formatRateBps(detail.yield_bps ?? detail.interest_rate_bps)}</strong>
                <span>{t("Annual interest rate")}</span>
              </div>
              <div>
                <strong>{detail.remaining_term_months} <small>{detail.remaining_term_months === 1 ? t("month") : t("months")}</small></strong>
                <span>{t("Remaining term")}</span>
              </div>
            </div>
            <p className="l8-repayment">{repaymentText(detail.repayment_type, detail.payment_frequency)}</p>
            {story ? (
              <div className="l8-project-story">
                <h2>{t("About this project")}</h2>
                <p>{story}</p>
              </div>
            ) : null}
            {detail.public_disclosure_note ? (
              <div className="alert alert-warning alert-icon u33-offer-disclosure">
                <NiIcon name="alert-circle" />
                {detail.public_disclosure_note}
              </div>
            ) : null}
            {detail.latest_public_note ? (
              <div className="l8-project-story">
                <h2>{t("Latest loan update")}</h2>
                <p>{detail.latest_public_note.title} <time dateTime={detail.latest_public_note.occurred_at}>({formatDate(detail.latest_public_note.occurred_at)})</time></p>
              </div>
            ) : null}
            {detail.originator_name ? (
              <p className="r36-originator">
                {t("Originator")}: <strong>{detail.originator_name}</strong>
              </p>
            ) : null}
            <SecuritySection
              collateralType={detail.collateral_type}
              collateralValueMinor={loan?.collateral_value_minor ?? null}
              currency={currency}
              description={loan?.collateral_description ?? ""}
              loanId={detail.loan_id}
              loanPrincipalMinor={loan ? currentLoanPrincipalMinor(loan) ?? loan.principal_minor : null}
              ltvBps={loan ? loanLtvBps(loan) : detail.ltv_bps}
              variant="offer"
            />
            <div className="r58-project-actions">
              <div className="r58-action-row">
                <ButtonLink className="r34-credit-file" icon="folder" params={{ loanId: detail.loan_id }} to="loan">{t("Open credit file")}</ButtonLink>
                {rows.length > 0 ? (
                  <button aria-controls={scheduleId} aria-expanded={scheduleOpen} className="r36-schedule-toggle r60-frequency" onClick={() => setScheduleOpen((value) => !value)} type="button">
                    <NiIcon name="calendar" />
                    <span className="r36-toggle-copy">
                      <strong>{t("Payment schedule")}</strong>
                      <small>{PERIODIC_REPAYMENTS.has(detail.repayment_type) ? t("Remaining {frequency} payments", { frequency: frequencyWords(detail.payment_frequency).adverb }) : t("Remaining payments")}</small>
                    </span>
                    <span className="r36-chevron"><NiIcon name={scheduleOpen ? "chevron-up" : "chevron-down"} /></span>
                  </button>
                ) : null}
              </div>
            </div>
          </section>
          <aside className="l8-funding r69-purchase">
            <h2>{t("Your purchase")}</h2>
            <p className="r69-caption">{t("You buy the entire listed position.")}</p>
            <span className="r69-label">{t("Total price")}</span>
            <div className="r69-total">
              <strong><small>{currency}</small> {formatMoneyMinor(detail.buyer_total_cost_minor, currency)}</strong>
              <InfoButton
                className={`r69-discount p99-price-trigger${detail.discount_premium_bps === 0 ? " is-neutral" : ""}`}
                content={<p>{t("Discount or premium applies to the outstanding principal.")} {t("The total price includes accrued interest.")}</p>}
                label={t("About the price")}
                title={t("Total price")}
              >
                <span>{priceAdjustmentText(detail.discount_premium_bps)}</span>
              </InfoButton>
            </div>
            <details className="r69-breakdown">
              <summary>
                {t("Price breakdown")}
                <NiIcon name="chevron-down" />
              </summary>
              <div className="r69-lines">
                <div className="r69-line"><span>{t("Outstanding principal")}</span><strong>{money(detail.current_principal_minor)}</strong></div>
                {adjustmentMinor !== 0 ? (
                  <div className="r69-line"><span>{adjustmentMinor < 0 ? t("Discount") : t("Premium")}</span><strong>{adjustmentMinor < 0 ? `− ${money(-adjustmentMinor)}` : `+ ${money(adjustmentMinor)}`}</strong></div>
                ) : null}
                <div className="r69-line"><span>{t("Purchase price")}</span><strong>{money(detail.transfer_price_minor)}</strong></div>
                <div className="r69-line"><span>{t("Accrued interest")}</span><strong>+ {money(detail.accrued_interest_minor)}</strong></div>
                {detail.taker_fee_minor !== 0 ? <div className="r69-line"><span>{t("Buyer fee")}</span><strong>+ {money(detail.taker_fee_minor)}</strong></div> : null}
              </div>
            </details>
            <div className="r69-return">
              <div>
                <span className="r69-label">{t("Outstanding principal")}</span>
                <strong>{money(detail.current_principal_minor)}</strong>
              </div>
              {detail.projected_yield_bps !== null ? (
                <div>
                  <span className="r69-label">
                    {t("Projected annual return")}
                    <InfoButton
                      className="r69-info"
                      content={<p>{t("The yearly return of the remaining scheduled payments compared with the total price you pay. A projection, not a guarantee: it changes with early repayments, late payments or recoveries.")}</p>}
                      label={t("About projected annual return")}
                      title={t("Projected annual return")}
                    />
                  </span>
                  <strong className="r69-yield">{projectedReturnText(detail.projected_yield_bps)}</strong>
                </div>
              ) : null}
            </div>
            {next ? (
              <div className="r69-next">
                <div className="r69-line"><span>{t("Next scheduled payment")}</span><strong>{money(next.projected_total_minor)}</strong></div>
                <small>{next.projected_principal_minor > 0 ? t("{date} · principal and interest", { date: formatDate(next.due_date) }) : t("{date} · interest", { date: formatDate(next.due_date) })}</small>
              </div>
            ) : null}
            {isOwn ? (
              <div className="r69-balance">
                <p className="r69-final">{t("This is your listing. You cannot buy it.")}</p>
                <button className="link" onClick={onMine} type="button">{t("Manage it under My listings")}</button>
              </div>
            ) : (
              <div className="r69-balance">
                <div className="r69-line"><span>{t("Available balance")}</span><strong>{money(availableMinor)}</strong></div>
                {shortfall > 0 ? (
                  <div className="r69-shortfall">
                    <span>{t("{amount} needed to buy", { amount: money(shortfall) })}</span>
                    <PortalLink to="balances">{t("Add funds")} <NiIcon name="arrow-right" /></PortalLink>
                  </div>
                ) : null}
                <button className={`r69-buy${shortfall > 0 || blockedReason ? "" : " is-ready"}`} disabled={shortfall > 0 || Boolean(blockedReason)} onClick={() => setBuying(true)} type="button">
                  {shortfall > 0 || blockedReason ? <NiIcon name="lock-alt" /> : null}
                  {t("Buy for {amount}", { amount: money(detail.buyer_total_cost_minor) })}
                </button>
                <p className="r69-final">{blockedReason || t("Review the agreements and confirm with your email code and PIN.")}</p>
              </div>
            )}
          </aside>
        </div>
        {rows.length > 0 ? (
          <details className="pd-inline-details l8-schedule r50-motion-schedule" id={scheduleId} onToggle={(event) => setScheduleOpen(event.currentTarget.open)} open={scheduleOpen}>
            <summary aria-expanded={scheduleOpen}>
              {t("Payment schedule")}
              <NiIcon name="chevron-down" />
            </summary>
            <div className="r50-schedule-body">
              <div className="pd-disclosure-body">
                <div className="r36-schedule-head">
                  <div>
                    <h2>{t("Remaining repayments")}</h2>
                    <p>{t("Offered position · {amount} outstanding · {count}", { amount: money(detail.current_principal_minor), count: rows.length === 1 ? t("1 payment") : t("{count} payments", { count: rows.length }) })}</p>
                  </div>
                  <div className="r36-total-interest">
                    <span>{t("Projected remaining interest")}</span>
                    <strong>{money(remainingInterest)}</strong>
                  </div>
                </div>
                <div aria-label={t("Remaining payment schedule for this position")} className="pd-schedule-table" role="region" tabIndex={0}>
                  <table className="table bxm-table">
                    <thead>
                      <tr>
                        <th scope="col">{t("Due")}</th>
                        <th className="text-end" scope="col">{t("Principal")}</th>
                        <th className="text-end" scope="col">{t("Interest")}</th>
                        <th className="text-end" scope="col">{t("Total")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row) => (
                        <tr key={row.loan_installment_id}>
                          <td>{formatDate(row.due_date)}</td>
                          <td className="text-end">{formatMoneyMinor(row.projected_principal_minor, currency)}</td>
                          <td className="text-end">{formatMoneyMinor(row.projected_interest_minor, currency)}</td>
                          <td className="text-end"><strong>{formatMoneyMinor(row.projected_total_minor, currency)}</strong></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="u33-muted">{t("Your projected share of the remaining borrower payments. It can change after early repayments, late payments or recoveries.")}</p>
              </div>
            </div>
          </details>
        ) : null}
        <div className="l8-resources">
          <button aria-haspopup="dialog" className="l8-how p99-market-help" onClick={() => setHelpOpen(true)} type="button">
            <NiIcon name="info" />
            <span>{t("How resale works")}</span>
          </button>
        </div>
      </section>
      {helpOpen ? <ResaleHelpDialog buyerFeeFree={detail.taker_fee_bps === 0 && detail.taker_fee_minor === 0} onClose={() => setHelpOpen(false)} /> : null}
      {buying ? <PurchaseDialog detail={detail} onClose={() => setBuying(false)} refetch={refetch} refreshing={refreshing} /> : null}
    </main>
  );
}

function PurchaseDialog({ detail, onClose, refetch, refreshing }: { detail: SecondaryMarketBuyerListingDetail; onClose: () => void; refetch: () => void; refreshing: boolean }) {
  const t = useT();
  useNumberFormat();
  const queryClient = useQueryClient();
  const [ack, setAck] = useState(false);
  const [riskAck, setRiskAck] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [priceChanged, setPriceChanged] = useState("");
  const [done, setDone] = useState(false);
  // The acceptance records the reviewed economics: reused only for a retry of exactly the same price.
  const [acceptance, setAcceptance] = useState<{ id: string; reviewKey: string } | null>(null);
  const [acceptanceKey, setAcceptanceKey] = useState(() => idempotencyKey("secondary-purchase-acceptance"));
  const [purchaseKey, setPurchaseKey] = useState(() => idempotencyKey("secondary-purchase"));
  const noticeRef = useRef<HTMLDivElement>(null);
  const acceptanceMutation = useV1DocumentsAcceptancesCreate();
  const purchaseMutation = useV1MarketplaceSecondaryListingsPurchaseCreate();
  // 18.5: the email code confirms this listing at this total cost only (a new price needs a new code).
  const confirmation = useActionConfirmation(ActionEnum.secondary_market_purchase, {
    listing_id: detail.id,
    currency: detail.currency,
    amount_minor: detail.buyer_total_cost_minor
  });
  const termsQuery = useV1DocumentsTemplatesCurrentRetrieve({ category: CategoryEnum.secondary_market_purchase }, { query: { enabled: !isFixturePreview, retry: false } });
  const busy = acceptanceMutation.isPending || purchaseMutation.isPending;
  const currency = detail.currency;
  const money = (amount: number) => `${currency} ${formatMoneyMinor(amount, currency)}`;
  const needsRiskAck = detail.risk_acknowledgement_required;
  useEffect(() => {
    if (priceChanged) noticeRef.current?.scrollIntoView({ block: "center" });
  }, [priceChanged]);

  const submit = async () => {
    setError("");
    setPriceChanged("");
    if (detail.is_own_listing) {
      setError(t("This is your own listing. You cannot buy it."));
      return;
    }
    if (isFixturePreview) {
      if (confirmation.pin.previewAccepts()) setDone(true);
      return;
    }
    const labels = templateLabels(termsQuery.data);
    if (!termsQuery.data || labels.length === 0) {
      setError(t("The current buyer terms are not available. Try again later."));
      return;
    }
    if (!confirmation.codeId) {
      setError(t("Request an email code before confirming the purchase."));
      return;
    }
    // The buyer accepts exactly the prices shown, from the fresh offer; the server charges them or refuses.
    const reviewed = { price_bps: detail.price_bps, current_principal_minor: detail.current_principal_minor, buyer_total_cost_minor: detail.buyer_total_cost_minor };
    const reviewKey = `${reviewed.price_bps}:${reviewed.current_principal_minor}:${reviewed.buyer_total_cost_minor}`;
    try {
      const accepted = acceptance && acceptance.reviewKey === reviewKey
        ? acceptance
        : {
            id: (await acceptanceMutation.mutateAsync({
              data: {
                category: CategoryEnum.secondary_market_purchase,
                expected_template_version_id: termsQuery.data.id,
                accepted_checkbox_labels: labels,
                context_type: "secondary_market_purchase",
                context_id: detail.id,
                data_snapshot: {
                  listing_id: detail.id,
                  currency,
                  price_bps: reviewed.price_bps,
                  current_principal_minor: reviewed.current_principal_minor,
                  transfer_price_minor: detail.transfer_price_minor,
                  accrued_interest_minor: detail.accrued_interest_minor,
                  taker_fee_minor: detail.taker_fee_minor,
                  buyer_total_cost_minor: reviewed.buyer_total_cost_minor
                },
                idempotency_key: `${acceptanceKey}:${reviewKey}`
              }
            })).id,
            reviewKey
          };
      setAcceptance(accepted);
      await purchaseMutation.mutateAsync({
        listingId: detail.id,
        data: {
          document_acceptance_id: accepted.id,
          risk_acknowledgement_accepted: needsRiskAck ? riskAck : true,
          idempotency_key: purchaseKey,
          expected_buyer_total_cost_minor: reviewed.buyer_total_cost_minor,
          expected_price_bps: reviewed.price_bps,
          expected_current_principal_minor: reviewed.current_principal_minor,
          sensitive_action_code_id: confirmation.codeId,
          sensitive_action_code: code,
          pin: confirmation.pin.value
        }
      });
      void queryClient.invalidateQueries();
      setDone(true);
    } catch (failure) {
      if (isPriceChangedError(failure)) {
        // Nothing was charged. Load the new price and ask for a new review and acceptance; the code stays.
        setPriceChanged(errorMessage(failure));
        setAcceptance(null);
        setAcceptanceKey(idempotencyKey("secondary-purchase-acceptance"));
        setPurchaseKey(idempotencyKey("secondary-purchase"));
        setAck(false);
        setRiskAck(false);
        refetch();
        void queryClient.invalidateQueries({ queryKey: getV1MarketplaceSecondaryListingsListQueryKey() });
        return;
      }
      if (confirmation.pin.handleError(failure)) return;
      setError(errorMessage(failure));
    }
  };

  if (done) {
    return (
      <Dialog bodyClassName="s106-body" className="s106-modal" footer={<ButtonLink to="portfolio" variant="primary">{t("My investments")}</ButtonLink>} onClose={onClose} size="sm" title={t("Purchase confirmed")}>
        <p className="s106-project">{detail.loan_title}</p>
        <p className="s106-note">{t("The investment appears in My investments once the transfer is recorded. Its future payments go to your Banxum balance.")}</p>
      </Dialog>
    );
  }

  return (
    <Dialog bodyClassName="s106-body" busy={busy} className="p73-modal s106-modal" onClose={onClose} size="sm" title={t("Confirm purchase")}>
      <p className="s106-project">{detail.loan_title}</p>
      {priceChanged ? (
        <div className="alert alert-warning alert-icon" ref={noticeRef} role="alert">
          <NiIcon name="alert-circle" />
          <div><strong>{t("Price changed")}</strong> {priceChanged} {t("Nothing was charged.")}</div>
        </div>
      ) : null}
      <div className="s106-review">
        <div className="s106-review-price">
          <div>
            <span>{t("Total price")}</span>
            <small>{priceAdjustmentText(detail.discount_premium_bps)}</small>
          </div>
          <div className="s106-money"><small>{currency}</small> <strong>{formatMoneyMinor(detail.buyer_total_cost_minor, currency)}</strong></div>
        </div>
        <dl className="s106-breakdown">
          <div><dt>{t("Outstanding principal")}</dt><dd>{money(detail.current_principal_minor)}</dd></div>
          <div><dt>{t("Purchase price")}</dt><dd>{money(detail.transfer_price_minor)}</dd></div>
          <div><dt>{t("Accrued interest")}</dt><dd className="s106-interest">+ {money(detail.accrued_interest_minor)}</dd></div>
          {detail.taker_fee_minor !== 0 ? <div><dt>{t("Buyer fee")}</dt><dd>+ {money(detail.taker_fee_minor)}</dd></div> : null}
        </dl>
      </div>
      {needsRiskAck ? (
        <>
          <div className="alert alert-danger alert-icon"><NiIcon name="alert-circle" /> {t("This investment has late payments. You may receive less than the outstanding principal, or nothing.")}</div>
          <label className="u33-check u33-acceptance">
            <input checked={riskAck} onChange={(event) => setRiskAck(event.target.checked)} type="checkbox" />
            <span>{t("I understand that this investment has late payments and a higher risk of partial or total loss.")}</span>
          </label>
        </>
      ) : null}
      <label className="u33-check u33-acceptance">
        <input checked={ack} onChange={(event) => setAck(event.target.checked)} type="checkbox" />
        <span>{t("I accept the")} <TermsLink category="secondary_market_purchase">{t("buyer terms and the assignment of this investment")}</TermsLink>.</span>
      </label>
      {!isFixturePreview && termsQuery.data ? <p className="u33-terms-version">{t("Version {version} of {title}.", { version: termsQuery.data.version_number, title: termsQuery.data.title })}</p> : null}
      <ConfirmFields code={code} confirmation={confirmation} onCodeChange={setCode} onContinue={() => void submit()} />
      <p className="s106-note">{t("Request the email code once you have reviewed the price and the terms and want to buy.")}</p>
      {confirmation.error || error ? <p className="s106-error" role="alert">{confirmation.error || error}</p> : null}
      <div className="s106-actions">
        <button className="s106-secondary" disabled={busy} onClick={onClose} type="button">{t("Cancel")}</button>
        <button className="s106-confirm" disabled={!ack || (needsRiskAck && !riskAck) || busy || refreshing || !confirmationReady(confirmation, code)} onClick={() => void submit()} type="button">
          {busy ? t("Confirming...") : t("Confirm purchase")}
        </button>
      </div>
    </Dialog>
  );
}
