// IP of Webby-Soft SRL.
// "Sell investment" (design data-action="market-sell", dialog .s106-modal), "Edit listing" and "Cancel
// listing". U33-DEC-06/07: the whole position, a price of 0-102% of the outstanding principal (a premium of
// at most 2%), in whole basis points; the seller fee is min(2% x price, 2% x outstanding principal) and
// accrued interest has no fee ("No fees" next to it). Fee, accrued interest and the net come from the
// server's quote. Discount warnings above 10% and from 20% never block. The seller accepts the listing
// terms and confirms with the email code + PIN.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState, type CSSProperties } from "react";

import {
  ActionEnum,
  CategoryEnum,
  useV1DocumentsAcceptancesCreate,
  useV1DocumentsTemplatesCurrentRetrieve,
  useV1MarketplaceSecondaryListingsCancelCreate,
  useV1MarketplaceSecondaryListingsCreate,
  useV1MarketplaceSecondaryListingsEditCreate,
  useV1MarketplaceSecondaryListingsPricingPreviewRetrieve,
  type Holding,
  type HoldingOpenSecondaryListing,
  type SecondaryMarketListingPricingPreview
} from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { isFixturePreview } from "../../../investorPortal/data";
import { formatMoneyMinor, formatRateBps, parseMoneyInputToMinorUnits, useNumberFormat } from "../../../investorPortal/format";
import { Button, Dialog, NiIcon } from "../../components";
import { ConfirmFields } from "./parts/ConfirmFields";
import { confirmationReady, useActionConfirmation } from "./parts/confirmation";
import { TermsLink } from "./parts/documents";
import { errorMessage, idempotencyKey, templateLabels } from "./parts/errors";
import { discountTone, MAX_PRICE_BPS, MIN_PRICE_BPS, PAR_PRICE_BPS, PREVIEW_FEE_BPS, previewSellerFee, priceBpsForAmount, priceMinorForBps, SLIDER_STEP_BPS } from "./parts/sellPricing";

type Pricing = Pick<SecondaryMarketListingPricingPreview, "price_bps" | "transfer_price_minor" | "accrued_interest_minor" | "maker_fee_bps" | "minimum_maker_fee_minor" | "maker_fee_minor" | "seller_net_proceeds_minor">;

function usePricing(holding: Holding, priceBps: number) {
  const valid = priceBps >= MIN_PRICE_BPS && priceBps <= MAX_PRICE_BPS;
  const query = useV1MarketplaceSecondaryListingsPricingPreviewRetrieve(
    { holding_id: holding.id, price_bps: priceBps },
    { query: { enabled: !isFixturePreview && valid, retry: false, staleTime: 30_000 } }
  );
  if (!valid) return { pricing: null, query };
  if (isFixturePreview) {
    const transfer = priceMinorForBps(holding.current_principal_minor, priceBps);
    const fee = previewSellerFee(transfer, holding.current_principal_minor);
    return {
      pricing: { price_bps: priceBps, transfer_price_minor: transfer, accrued_interest_minor: 0, maker_fee_bps: PREVIEW_FEE_BPS, minimum_maker_fee_minor: 0, maker_fee_minor: fee, seller_net_proceeds_minor: transfer - fee } satisfies Pricing,
      query
    };
  }
  return { pricing: query.data?.price_bps === priceBps ? query.data : null, query };
}

function adjustmentText(priceBps: number, t: ReturnType<typeof useT>) {
  if (priceBps === PAR_PRICE_BPS) return t("No discount or premium");
  if (priceBps > PAR_PRICE_BPS) return t("{percent} premium", { percent: formatRateBps(priceBps - PAR_PRICE_BPS) });
  return t("{percent} discount", { percent: formatRateBps(PAR_PRICE_BPS - priceBps) });
}

function feeExplanation(pricing: Pricing, currency: string, t: ReturnType<typeof useT>) {
  const rate = formatRateBps(pricing.maker_fee_bps);
  // A listing made before U33-DEC-07 keeps the minimum fee it accepted until it is edited.
  const base = pricing.minimum_maker_fee_minor > 0
    ? t("{rate} of the selling price, capped at {rate} of the remaining investment value, at least {minimum}.", { rate, minimum: `${currency} ${formatMoneyMinor(pricing.minimum_maker_fee_minor, currency)}` })
    : t("{rate} of the selling price, capped at {rate} of the remaining investment value.", { rate });
  return [base, t("Accrued interest is excluded. The fee is charged only when sold.")];
}

function InfoDetails({ label, paragraphs }: { label: string; paragraphs: string[] }) {
  return (
    <details className="s106-info">
      <summary aria-label={label}><NiIcon name="info" /></summary>
      <div>{paragraphs.map((text) => <p key={text}>{text}</p>)}</div>
    </details>
  );
}

function Breakdown({ pricing, currency, t }: { pricing: Pricing | null; currency: string; t: ReturnType<typeof useT> }) {
  const money = (amount: number) => `${currency} ${formatMoneyMinor(amount, currency)}`;
  return (
    <>
      <dl className="s106-breakdown">
        <div>
          <dt>
            {t("Accrued interest")} <span>· {t("No fees")}</span>
            <InfoDetails label={t("About accrued interest")} paragraphs={[t("Interest earned since the last payment. Paid separately by the buyer, on top of the selling price. No fee is charged on it.")]} />
          </dt>
          <dd className="s106-interest">{pricing ? `+ ${money(pricing.accrued_interest_minor)}` : "…"}</dd>
        </div>
        <div>
          <dt>
            {t("Selling fee")} {pricing ? <span>· {formatRateBps(pricing.maker_fee_bps)}</span> : null}
            {pricing ? <InfoDetails label={t("About selling fee")} paragraphs={feeExplanation(pricing, currency, t)} /> : null}
          </dt>
          <dd>{pricing ? `− ${money(pricing.maker_fee_minor)}` : "…"}</dd>
        </div>
      </dl>
      <div className="s106-net">
        <span>{t("You receive if sold")}</span>
        <output>
          <small>{currency}</small> <strong>{pricing ? formatMoneyMinor(pricing.seller_net_proceeds_minor, currency) : "…"}</strong>
        </output>
      </div>
    </>
  );
}

function DiscountWarning({ priceBps, holding, t }: { priceBps: number; holding: Holding; t: ReturnType<typeof useT> }) {
  const tone = discountTone(priceBps);
  if (tone === "none") return null;
  const transfer = priceMinorForBps(holding.current_principal_minor, priceBps);
  const below = `${holding.currency} ${formatMoneyMinor(holding.current_principal_minor - transfer, holding.currency)}`;
  return (
    <aside className={`s106-warning ${tone}`} role="status">
      <NiIcon name="alert-circle" />
      <div>
        <strong>{tone === "high" ? t("Far below investment value") : t("Significantly below investment value")}</strong>
        <p>{t("{amount} less than your investment value, before fees.", { amount: below })}{tone === "high" ? ` ${t("Check the price before you continue.")}` : ""}</p>
      </div>
    </aside>
  );
}

type Attempt = { priceBps: number; acceptanceKey: string; listingKey: string; acceptanceId: string | null };

function newAttempt(priceBps: number, isEdit: boolean): Attempt {
  return {
    priceBps,
    acceptanceKey: idempotencyKey(isEdit ? "secondary-listing-edit-acceptance" : "secondary-listing-acceptance"),
    listingKey: idempotencyKey(isEdit ? "secondary-listing-edit" : "secondary-listing"),
    acceptanceId: null
  };
}

export function SellInvestmentDialog({ holding, listing, onClose }: { holding: Holding; listing: HoldingOpenSecondaryListing | null; onClose: () => void }) {
  const t = useT();
  useNumberFormat();
  const queryClient = useQueryClient();
  const isEdit = listing !== null;
  const currency = holding.currency;
  const principal = holding.current_principal_minor;
  const initialBps = Math.min(MAX_PRICE_BPS, listing?.price_bps ?? PAR_PRICE_BPS);
  const [step, setStep] = useState<"price" | "review" | "done">("price");
  const [priceBps, setPriceBps] = useState(initialBps);
  const [priceText, setPriceText] = useState(() => formatMoneyMinor(priceMinorForBps(principal, initialBps), currency));
  const [priceError, setPriceError] = useState("");
  const [ack, setAck] = useState(false);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState<Attempt>(() => newAttempt(initialBps, isEdit));
  const editingText = useRef(false);
  const priceId = useId();
  const adjustmentId = useId();
  const { pricing, query: pricingQuery } = usePricing(holding, priceBps);
  const termsQuery = useV1DocumentsTemplatesCurrentRetrieve({ category: CategoryEnum.secondary_market_listing }, { query: { enabled: !isFixturePreview, retry: false } });
  const acceptanceMutation = useV1DocumentsAcceptancesCreate();
  const createMutation = useV1MarketplaceSecondaryListingsCreate();
  const editMutation = useV1MarketplaceSecondaryListingsEditCreate();
  const confirmation = useActionConfirmation(ActionEnum.secondary_market_listing);
  const busy = acceptanceMutation.isPending || createMutation.isPending || editMutation.isPending;

  // The amount field follows the server's price for the chosen basis points, unless it is being typed.
  useEffect(() => {
    if (!editingText.current && pricing) setPriceText(formatMoneyMinor(pricing.transfer_price_minor, currency));
  }, [currency, pricing]);
  // One email code for the confirmation step, sent when the seller reaches it.
  const requested = useRef(false);
  useEffect(() => {
    if (step !== "review" || requested.current || isFixturePreview) return;
    requested.current = true;
    confirmation.requestCode();
  }, [confirmation, step]);

  const choosePrice = (bps: number) => {
    const clamped = Math.min(MAX_PRICE_BPS, Math.max(MIN_PRICE_BPS, Math.round(bps)));
    setPriceBps(clamped);
    setPriceError("");
    setAttempt(newAttempt(clamped, isEdit));
    setAck(false);
  };
  const applyText = (text: string) => {
    const parsed = parseMoneyInputToMinorUnits(text, currency);
    if (parsed.error) {
      setPriceError(parsed.error);
      return;
    }
    const maximum = priceMinorForBps(principal, MAX_PRICE_BPS);
    if (parsed.amountMinor > maximum) {
      setPriceError(t("Maximum selling price: {amount} (2% premium).", { amount: `${currency} ${formatMoneyMinor(maximum, currency)}` }));
      return;
    }
    if (parsed.amountMinor < 0) {
      setPriceError(t("Enter a valid price of zero or more."));
      return;
    }
    choosePrice(priceBpsForAmount(parsed.amountMinor, principal));
  };

  const pricingFailed = !isFixturePreview && pricingQuery.isError;
  const termsMissing = !isFixturePreview && (!termsQuery.data || templateLabels(termsQuery.data).length === 0);
  const fillPercent = (priceBps / MAX_PRICE_BPS) * 100;

  const submit = async () => {
    setError("");
    if (isFixturePreview) {
      if (confirmation.pin.previewAccepts()) setStep("done");
      return;
    }
    const labels = templateLabels(termsQuery.data);
    if (!termsQuery.data || labels.length === 0) {
      setError(t("The current listing terms are not available. Try again later."));
      return;
    }
    if (!confirmation.codeId) {
      setError(t("Request an email code before confirming the listing."));
      return;
    }
    if (!pricing) {
      setError(t("The price is still being calculated."));
      return;
    }
    // The acceptance records the reviewed price: it is reused only for a retry of exactly this price.
    let current = attempt.priceBps === priceBps ? attempt : newAttempt(priceBps, isEdit);
    try {
      const acceptanceId = current.acceptanceId ?? (await acceptanceMutation.mutateAsync({
        data: {
          category: CategoryEnum.secondary_market_listing,
          expected_template_version_id: termsQuery.data.id,
          accepted_checkbox_labels: labels,
          context_type: "secondary_market_listing",
          context_id: holding.id,
          data_snapshot: {
            holding_id: holding.id,
            listing_id: listing?.id ?? "",
            action: isEdit ? "edit" : "create",
            price_bps: priceBps,
            current_principal_minor: principal,
            currency,
            transfer_price_minor: pricing.transfer_price_minor,
            accrued_interest_minor: pricing.accrued_interest_minor,
            maker_fee_minor: pricing.maker_fee_minor,
            seller_net_proceeds_minor: pricing.seller_net_proceeds_minor
          },
          idempotency_key: current.acceptanceKey
        }
      })).id;
      current = { ...current, acceptanceId };
      setAttempt(current);
      const authorization = {
        price_bps: priceBps,
        document_acceptance_id: acceptanceId,
        idempotency_key: current.listingKey,
        sensitive_action_code_id: confirmation.codeId,
        sensitive_action_code: code,
        pin: confirmation.pin.value
      };
      if (listing) await editMutation.mutateAsync({ listingId: listing.id, data: authorization });
      else await createMutation.mutateAsync({ data: { holding_id: holding.id, ...authorization } });
      void queryClient.invalidateQueries();
      setStep("done");
    } catch (failure) {
      if (confirmation.pin.handleError(failure)) return;
      setError(errorMessage(failure));
    }
  };

  if (step === "done") {
    return (
      <Dialog
        bodyClassName="s106-body"
        className="s106-modal"
        footer={<Button onClick={onClose} variant="primary">{t("Done")}</Button>}
        onClose={onClose}
        size="sm"
        title={isEdit ? t("Listing updated") : t("Listing published")}
      >
        <p className="s106-project">{holding.loan.loan_title}</p>
        <p className="s106-note">{isEdit ? t("Buyers now see your new price. A buyer must purchase your investment for the sale to complete.") : t("Your investment is on the resale market. A buyer must purchase it for the sale to complete.")}</p>
      </Dialog>
    );
  }

  if (step === "review") {
    return (
      <Dialog bodyClassName="s106-body" busy={busy} className="p73-modal s106-modal" onClose={onClose} size="sm" title={isEdit ? t("Confirm new price") : t("Confirm listing")}>
        <p className="s106-project">{holding.loan.loan_title}</p>
        <div className="s106-review">
          <div className="s106-review-price">
            <div>
              <span>{t("Selling price")}</span>
              <small>{adjustmentText(priceBps, t)}</small>
            </div>
            <div className="s106-money">
              <small>{currency}</small> <strong>{pricing ? formatMoneyMinor(pricing.transfer_price_minor, currency) : "…"}</strong>
            </div>
          </div>
          <Breakdown currency={currency} pricing={pricing} t={t} />
        </div>
        <DiscountWarning holding={holding} priceBps={priceBps} t={t} />
        <label className="u33-check u33-acceptance">
          <input checked={ack} onChange={(event) => setAck(event.target.checked)} type="checkbox" />
          <span>
            {t("I accept the")} <TermsLink category="secondary_market_listing">{t("seller listing terms")}</TermsLink> {isEdit ? t("and confirm the new price for my entire investment.") : t("and confirm that I list my entire investment.")}
          </span>
        </label>
        {!isFixturePreview && termsQuery.data ? <p className="u33-terms-version">{t("Version {version} of {title}.", { version: termsQuery.data.version_number, title: termsQuery.data.title })}</p> : null}
        <ConfirmFields code={code} confirmation={confirmation} onCodeChange={setCode} onContinue={() => void submit()} />
        <p className="s106-note">{t("A buyer must purchase your investment for the sale to complete.")}</p>
        {confirmation.error || error ? <p className="s106-error" role="alert">{confirmation.error || error}</p> : null}
        <div className="s106-actions">
          <button className="s106-secondary" disabled={busy} onClick={() => { setError(""); setAttempt(newAttempt(priceBps, isEdit)); setStep("price"); }} type="button">{t("Back")}</button>
          <button className="s106-confirm" disabled={!ack || busy || !pricing || termsMissing || !confirmationReady(confirmation, code)} onClick={() => void submit()} type="button">
            {busy ? t("Confirming...") : isEdit ? t("Confirm new price") : t("Confirm listing")}
          </button>
        </div>
      </Dialog>
    );
  }

  const tone = priceBps > PAR_PRICE_BPS ? "premium" : discountTone(priceBps);
  return (
    <Dialog bodyClassName="s106-body" className="s106-modal" onClose={onClose} title={isEdit ? t("Edit listing") : t("Sell investment")}>
      <p className="s106-project">{holding.loan.loan_title}</p>
      <div className="s106-position">
        <div>
          <span>
            {t("Investment value")}
            <InfoDetails label={t("About investment value")} paragraphs={[t("The invested amount still to be repaid, excluding interest.")]} />
          </span>
          <small>{t("Entire investment")}</small>
        </div>
        <div className="s106-money">
          <small>{currency}</small> <strong>{formatMoneyMinor(principal, currency)}</strong>
        </div>
      </div>
      <form
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          if (pricing && !priceError) setStep("review");
        }}
      >
        <section className="s106-price" data-tone={tone}>
          <div className="s106-price-heading">
            <label htmlFor={priceId}>{t("Selling price")}</label>
            <span>{t("Up to 2% premium")}</span>
          </div>
          <div className="s106-price-field">
            <span>{currency}</span>
            <input
              aria-describedby={adjustmentId}
              aria-invalid={priceError ? true : false}
              autoComplete="off"
              id={priceId}
              inputMode="decimal"
              onBlur={() => {
                editingText.current = false;
                applyText(priceText);
              }}
              onChange={(event) => {
                editingText.current = true;
                setPriceText(event.target.value);
                setPriceError("");
              }}
              onFocus={() => {
                editingText.current = true;
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  editingText.current = false;
                  applyText(priceText);
                }
              }}
              type="text"
              value={priceText}
            />
            <label aria-label={t("Edit selling price")} htmlFor={priceId}><NiIcon name="edit-alt" /></label>
          </div>
          <p className="s106-adjustment" id={adjustmentId}>{adjustmentText(priceBps, t)}</p>
          <div className="s106-slider" style={{ "--fill": `${fillPercent}%` } as CSSProperties}>
            <input
              aria-label={t("Selling price")}
              aria-valuetext={`${currency} ${formatMoneyMinor(pricing?.transfer_price_minor ?? priceMinorForBps(principal, priceBps), currency)}, ${adjustmentText(priceBps, t)}`}
              max={MAX_PRICE_BPS / 100}
              min={MIN_PRICE_BPS / 100}
              onChange={(event) => {
                editingText.current = false;
                choosePrice(Number(event.target.value) * 100);
              }}
              step={SLIDER_STEP_BPS / 100}
              type="range"
              value={priceBps / 100}
            />
            <i aria-hidden="true" className="s106-par" style={{ left: `${(PAR_PRICE_BPS / MAX_PRICE_BPS) * 100}%` }} />
          </div>
          <div className="s106-range-labels">
            <span>{t("100% discount")}</span>
            <span>{t("2% premium")}</span>
          </div>
          {priceError ? <p className="s106-error" role="alert">{priceError}</p> : null}
          {pricingFailed ? <p className="s106-error" role="alert">{t("The price could not be calculated: {reason}", { reason: errorMessage(pricingQuery.error) })}</p> : null}
          <DiscountWarning holding={holding} priceBps={priceBps} t={t} />
        </section>
        <Breakdown currency={currency} pricing={pricing} t={t} />
        <p className="s106-note">{t("A buyer must purchase your investment for the sale to complete.")}</p>
        <div className="s106-actions">
          <button className="s106-secondary" onClick={onClose} type="button">{t("Cancel")}</button>
          <button className="s106-primary" disabled={!pricing || Boolean(priceError) || termsMissing} type="submit">
            {t("Review listing")} <NiIcon name="arrow-right" />
          </button>
        </div>
        {termsMissing && !termsQuery.isPending ? <p className="s106-error" role="alert">{t("The current listing terms are not available. Try again later.")}</p> : null}
      </form>
    </Dialog>
  );
}

export function CancelListingDialog({ holding, listing, onClose }: { holding: Holding; listing: HoldingOpenSecondaryListing; onClose: () => void }) {
  const t = useT();
  useNumberFormat();
  const queryClient = useQueryClient();
  const reasonId = useId();
  const [reason, setReason] = useState(t("Cancelled by investor."));
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [key] = useState(() => idempotencyKey("secondary-listing-cancel"));
  const mutation = useV1MarketplaceSecondaryListingsCancelCreate();
  const cancel = async () => {
    setError("");
    if (!reason.trim()) {
      setError(t("Enter a reason for the cancellation."));
      return;
    }
    if (isFixturePreview) {
      setDone(true);
      return;
    }
    try {
      await mutation.mutateAsync({ listingId: listing.id, data: { reason: reason.trim(), idempotency_key: key } });
      await queryClient.invalidateQueries();
      setDone(true);
    } catch (failure) {
      setError(errorMessage(failure));
    }
  };
  if (done) {
    return (
      <Dialog bodyClassName="s106-body" className="s106-modal" footer={<Button onClick={onClose} variant="primary">{t("Done")}</Button>} onClose={onClose} size="sm" title={t("Listing cancelled")}>
        <p className="s106-project">{holding.loan.loan_title}</p>
        <p className="s106-note">{t("The investment is no longer on the resale market. It stays in your portfolio and can be listed again.")}</p>
      </Dialog>
    );
  }
  return (
    <Dialog bodyClassName="s106-body" busy={mutation.isPending} className="s106-modal" onClose={onClose} size="sm" title={t("Cancel listing")}>
      <p className="s106-project">{holding.loan.loan_title}</p>
      <div className="s106-review">
        <div className="s106-review-price">
          <div>
            <span>{t("Listed price")}</span>
            <small>{adjustmentText(listing.price_bps, t)}</small>
          </div>
          <div className="s106-money"><small>{holding.currency}</small> <strong>{formatMoneyMinor(listing.transfer_price_minor, holding.currency)}</strong></div>
        </div>
      </div>
      <p className="s106-note">{t("Cancelling removes the listing. The investment is not sold and stays in your portfolio.")}</p>
      <label className="s106-code-label" htmlFor={reasonId}>{t("Reason")}</label>
      <textarea className="form-control" id={reasonId} onChange={(event) => setReason(event.target.value)} rows={2} value={reason} />
      {error ? <p className="s106-error" role="alert">{error}</p> : null}
      <div className="s106-actions">
        <button className="s106-secondary" disabled={mutation.isPending} onClick={onClose} type="button">{t("Keep listing")}</button>
        <button className="s106-confirm" disabled={mutation.isPending || !reason.trim()} onClick={() => void cancel()} type="button">{mutation.isPending ? t("Cancelling...") : t("Cancel listing")}</button>
      </div>
    </Dialog>
  );
}
