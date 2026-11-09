// IP of Webby-Soft SRL.
// Resale market (design #/secondary, route /secondary-market, U33 slice S3): Available offers (EUR/CHF,
// sort by projected return, discount or remaining term) and My listings (edit, cancel, completed sales
// and purchases), "How resale works", and the consolidated offer page (?offer=<id>) with the purchase.
// Projected annual return is the server's figure (projected_yield_bps); it is left out when the server
// has none.
import { useState, type MouseEvent } from "react";

import type { Holding, HoldingOpenSecondaryListing, SecondaryMarketActivityEntryPortal, SecondaryMarketBuyerListing } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { frozenActionReason, useFrozenAccount } from "../../../investorPortal/accountState";
import { usePortfolioData, useSecondaryActivityData, useSecondaryListingsData } from "../../../investorPortal/data";
import { formatDate, formatRateBps, useNumberFormat } from "../../../investorPortal/format";
import { Button, ButtonLink, CurrencySwitch, EmptyState, NiIcon, PageHead, StatusTag, Tabs } from "../../components";
import { ResaleOfferView } from "./ResaleOfferView";
import { CancelListingDialog, SellInvestmentDialog } from "./SellInvestmentDialog";
import { isReadonlyView } from "./parts/errors";
import { sortedCurrencies } from "./parts/investmentModel";
import { investmentTypeText, monthsText, priceAdjustmentText, securityLabel, tileIcon } from "./parts/labels";
import { useMoneyText } from "./parts/money";
import { ResaleHelpDialog } from "./parts/ResaleHelpDialog";
import { usePreviewVariant, useQueryParams } from "./parts/urlState";
import { InfoButton, ProjectTile, SelectFilter } from "./parts/ui";
import "./portfolio.css";

type SortKey = "yield" | "price" | "term";

function sortListings(listings: SecondaryMarketBuyerListing[], key: SortKey) {
  return [...listings].sort((left, right) => {
    if (key === "yield") return (right.projected_yield_bps ?? -Infinity) - (left.projected_yield_bps ?? -Infinity);
    if (key === "price") return left.discount_premium_bps - right.discount_premium_bps;
    return left.remaining_term_months - right.remaining_term_months;
  });
}

export function ResaleMarketScreen({ initialTab }: { initialTab?: string }) {
  const t = useT();
  const [params, setParams] = useQueryParams();
  const offerId = params.get("offer");
  if (offerId) return <ResaleOfferView listingId={offerId} onBack={() => setParams({ offer: null })} onMine={() => setParams({ offer: null, tab: "mine" })} />;
  return <ResaleList initialTab={initialTab} key="list" onOffer={(id) => setParams({ offer: id })} params={params} setParams={setParams} t={t} />;
}

function ResaleList({
  initialTab,
  params,
  setParams,
  onOffer,
  t
}: {
  initialTab?: string;
  params: URLSearchParams;
  setParams: ReturnType<typeof useQueryParams>[1];
  onOffer: (id: string) => void;
  t: ReturnType<typeof useT>;
}) {
  const listingsQuery = useSecondaryListingsData();
  const portfolioQuery = usePortfolioData(true);
  const activityQuery = useSecondaryActivityData();
  const preview = usePreviewVariant();
  const [helpOpen, setHelpOpen] = useState(false);
  const legacyMine = initialTab === "sell" || initialTab === "mine" || initialTab === "activity";
  const tab = params.get("tab") === "mine" || (legacyMine && params.get("tab") !== "buy") ? "mine" : "buy";
  const sort: SortKey = params.get("sort") === "price" ? "price" : params.get("sort") === "term" ? "term" : "yield";
  const empty = preview === "empty";
  const listings = empty ? [] : listingsQuery.data ?? [];
  const holdings = empty ? [] : portfolioQuery.data?.holdings ?? [];
  // The investor's own listings are never offered to them (audit A-35); they are under My listings.
  const ownIds = new Set([
    ...listings.filter((listing) => listing.is_own_listing).map((listing) => listing.id),
    ...holdings.flatMap((holding) => (holding.open_secondary_listing ? [holding.open_secondary_listing.id] : []))
  ]);
  const available = listings.filter((listing) => !ownIds.has(listing.id));
  const currencies = sortedCurrencies(available.map((listing) => listing.currency));
  const currencyParam = params.get("cur");
  const currency = currencyParam && currencies.includes(currencyParam) ? currencyParam : null;
  const rows = sortListings(available.filter((listing) => currency === null || listing.currency === currency), sort);
  const buyerFeeFree = listings.length > 0 ? listings.every((listing) => listing.taker_fee_bps === 0 && listing.taker_fee_minor === 0) : null;
  const loading = tab === "buy" ? listingsQuery.isPending && !listingsQuery.data : portfolioQuery.isPending && !portfolioQuery.data;
  const failed = tab === "buy" ? listingsQuery.isError && !listingsQuery.data : portfolioQuery.isError && !portfolioQuery.data;

  return (
    <main className="bxm-resale">
      <PageHead
        actions={
          <Button aria-haspopup="dialog" className="btn-sm p99-market-help" icon="info" onClick={() => setHelpOpen(true)}>
            {t("How resale works")}
          </Button>
        }
        subtitle={t("Buy investments from other investors, or manage your listings.")}
        title={t("Resale market")}
      />
      <div className="rs-toolbar">
        <Tabs
          items={[
            { value: "buy", label: t("Available") },
            { value: "mine", label: t("My listings") }
          ]}
          label={t("Resale market views")}
          onChange={(value) => setParams({ tab: value === "buy" ? null : value }, { replace: true })}
          value={tab}
          variant="rs-tabs"
        />
        {tab === "buy" ? (
          <div className="rs-controls">
            {currencies.length > 1 ? (
              <CurrencySwitch onChange={(value: string) => setParams({ cur: value === "All" ? null : value }, { replace: true })} options={["All", ...currencies]} value={currency ?? "All"} />
            ) : null}
            <SelectFilter
              className="rs-sort"
              label={t("Sort")}
              onChange={(value) => setParams({ sort: value === "yield" ? null : value }, { replace: true })}
              options={[
                { value: "yield", label: t("Highest projected return") },
                { value: "price", label: t("Highest discount") },
                { value: "term", label: t("Shortest remaining term") }
              ]}
              value={sort}
            />
          </div>
        ) : null}
      </div>
      {failed ? (
        <div className="card card-bordered u33-state-card">
          <EmptyState
            actions={<Button onClick={() => void (tab === "buy" ? listingsQuery.refetch() : portfolioQuery.refetch())}>{t("Retry")}</Button>}
            icon="alert-circle"
            title={tab === "buy" ? t("The offers could not be loaded") : t("Your listings could not be loaded")}
          >
            {t("Retry once the connection is restored.")}
          </EmptyState>
        </div>
      ) : loading ? (
        <div className="card card-bordered u33-state-card"><div className="card-inner"><p className="u33-muted" role="status">{t("Loading...")}</p></div></div>
      ) : tab === "buy" ? (
        rows.length === 0 ? (
          <div className="card card-bordered u33-state-card">
            <EmptyState icon="exchange" title={t("No investments for sale right now")}>
              {currency ? t("There are no offers in {currency}. Choose All to see every offer.", { currency }) : t("New offers appear here when investors list their investments.")}
            </EmptyState>
          </div>
        ) : (
          <OffersTable onOffer={onOffer} rows={rows} t={t} />
        )
      ) : (
        <MyListings activity={empty ? [] : activityQuery.data?.entries ?? []} holdings={holdings} t={t} />
      )}
      {helpOpen ? <ResaleHelpDialog buyerFeeFree={buyerFeeFree} onClose={() => setHelpOpen(false)} /> : null}
    </main>
  );
}

function OffersTable({ rows, onOffer, t }: { rows: SecondaryMarketBuyerListing[]; onOffer: (id: string) => void; t: ReturnType<typeof useT> }) {
  const money = useMoneyText();
  useNumberFormat();
  return (
    <table className="rs-table r31m-resale-table r67-table">
      <caption className="visually-hidden">{t("Investments offered by other investors. Open an offer for its details and the purchase.")}</caption>
      <thead>
        <tr>
          <th scope="col">{t("Investment")}</th>
          <th scope="col">{t("Outstanding principal")}</th>
          <th scope="col">
            {t("Total price")}
            <InfoButton
              className="r67-price-info"
              content={<p>{t("Discount or premium applies to the outstanding principal.")} {t("The total price includes accrued interest.")}</p>}
              label={t("About total price")}
              title={t("Total price")}
            />
          </th>
          <th scope="col"><span title={t("Projected annual return based on the asking price and remaining term.")}>{t("Projected annual return")}</span></th>
          <th scope="col">{t("Remaining term")}</th>
          <th scope="col"><span className="visually-hidden">{t("Offer")}</span></th>
        </tr>
      </thead>
      <tbody>
        {rows.map((listing) => {
          const late = listing.loan_status_at_listing === "late" || listing.days_past_due > 0;
          const open = (event: MouseEvent) => {
            event.preventDefault();
            onOffer(listing.id);
          };
          return (
            <tr data-offer-id={listing.id} key={listing.id}>
              <td>
                <div className="rs-investment">
                  <ProjectTile as="span" collateralType={listing.collateral_type} />
                  <div>
                    <a className="r67-project-link" href={`?offer=${encodeURIComponent(listing.id)}`} onClick={open}>
                      <strong>{listing.loan_title}</strong>
                    </a>
                    <small className="r67-country">
                      <span>{listing.originator_name ? `${investmentTypeText(listing.product_type)} · ${listing.originator_name}` : investmentTypeText(listing.product_type)}</span>
                    </small>
                    <span className="r67-security">
                      <NiIcon name={tileIcon(listing.collateral_type)} />
                      <span>{securityLabel(listing.collateral_type)}</span>
                    </span>
                    {late ? <StatusTag className="u33-offer-late" tone="late">{listing.days_past_due > 0 ? t("Late payment · {days} days", { days: listing.days_past_due }) : t("Late payment")}</StatusTag> : null}
                  </div>
                </div>
              </td>
              <td><span className="rs-capital">{money(listing.currency, listing.current_principal_minor)}</span></td>
              <td>
                <strong className="rs-total">{money(listing.currency, listing.buyer_total_cost_minor)}</strong>
                <small className={`r31m-price-adjustment${listing.discount_premium_bps < 0 ? " is-discount" : ""}`}>{priceAdjustmentText(listing.discount_premium_bps)}</small>
              </td>
              <td><span className="rs-return">{listing.projected_yield_bps === null ? "—" : formatRateBps(listing.projected_yield_bps)}</span></td>
              <td><span className="rs-time">{monthsText(listing.remaining_term_months)}</span></td>
              <td>
                <button className="btn btn-sm btn-primary r67-view" onClick={() => onOffer(listing.id)} type="button">
                  {t("View offer")} <NiIcon name="arrow-right" />
                  <span className="visually-hidden"> {listing.loan_title}</span>
                </button>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function MyListings({ holdings, activity, t }: { holdings: Holding[]; activity: SecondaryMarketActivityEntryPortal[]; t: ReturnType<typeof useT> }) {
  const money = useMoneyText();
  useNumberFormat();
  const frozenAccount = useFrozenAccount();
  const blockedReason = frozenAccount.frozen ? frozenActionReason(frozenAccount) : isReadonlyView() ? t("This is a read-only view. Resale actions are disabled.") : "";
  const [dialog, setDialog] = useState<{ kind: "edit" | "cancel"; holding: Holding; listing: HoldingOpenSecondaryListing } | null>(null);
  const listed = holdings.filter((holding) => holding.open_secondary_listing && ["active", "approval_requested"].includes(holding.open_secondary_listing.status));
  const completed = activity.filter((entry) => entry.action === "sale" || entry.action === "buy");
  return (
    <div className="rs-own-list">
      {listed.length === 0 ? (
        <div className="card card-bordered">
          <div className="bxm-empty r75-empty">
            <NiIcon name="coins" />
            <p>{t("No active listings. To sell, open an investment marked On schedule in My investments and select Sell investment.")}</p>
            <ButtonLink className="r75-my-investments" to="portfolio" variant="secondary">{t("My investments")}</ButtonLink>
          </div>
        </div>
      ) : (
        <table className="rs-table r31m-resale-table u33-own-table">
          <caption className="visually-hidden">{t("Your investments listed on the resale market.")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("Investment")}</th>
              <th scope="col">{t("Outstanding principal")}</th>
              <th scope="col">{t("Selling price")}</th>
              <th scope="col">{t("You receive if sold")}</th>
              <th scope="col">{t("Listed on")}</th>
              <th scope="col"><span className="visually-hidden">{t("Actions")}</span></th>
            </tr>
          </thead>
          <tbody>
            {listed.map((holding) => {
              const listing = holding.open_secondary_listing as HoldingOpenSecondaryListing;
              const pending = listing.status !== "active";
              return (
                <tr key={listing.id}>
                  <td>
                    <div className="rs-investment">
                      <ProjectTile as="span" collateralType={holding.loan.collateral_type} />
                      <div>
                        <strong>{holding.loan.loan_title}</strong>
                        <small className="r67-country"><span>{holding.loan.borrower_name}</span></small>
                        <StatusTag status={pending ? undefined : "listed"} tone={pending ? "neutral" : undefined}>{pending ? t("Awaiting approval") : undefined}</StatusTag>
                      </div>
                    </div>
                  </td>
                  <td><span className="rs-capital">{money(holding.currency, holding.current_principal_minor)}</span></td>
                  <td>
                    <strong className="rs-total">{money(holding.currency, listing.transfer_price_minor)}</strong>
                    <small className={`r31m-price-adjustment${listing.price_bps < 10_000 ? " is-discount" : ""}`}>{priceAdjustmentText(listing.price_bps - 10_000)}</small>
                  </td>
                  <td><span className="rs-capital">{money(holding.currency, listing.seller_net_proceeds_minor)}</span></td>
                  <td><span className="rs-time">{listing.listed_at ? formatDate(listing.listed_at) : "—"}</span></td>
                  <td>
                    <div className="u33-row-actions">
                      <Button disabled={Boolean(blockedReason)} onClick={() => setDialog({ kind: "edit", holding, listing })} size="sm" title={blockedReason || undefined}>{t("Edit")}</Button>
                      <Button disabled={Boolean(blockedReason)} onClick={() => setDialog({ kind: "cancel", holding, listing })} size="sm" title={blockedReason || undefined}>{t("Cancel listing")}</Button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      {blockedReason && listed.length > 0 ? <p className="u33-muted u33-blocked-note">{blockedReason}</p> : null}
      {completed.length > 0 ? (
        <section aria-labelledby="rs-completed-title" className="u33-resale-activity">
          <h2 id="rs-completed-title">{t("Completed sales and purchases")}</h2>
          <table className="rs-table r31m-resale-table">
            <thead>
              <tr>
                <th scope="col">{t("Date")}</th>
                <th scope="col">{t("Investment")}</th>
                <th scope="col">{t("Type")}</th>
                <th scope="col">{t("Principal")}</th>
                <th scope="col">{t("Amount")}</th>
              </tr>
            </thead>
            <tbody>
              {completed.map((entry) => (
                <tr key={entry.id}>
                  <td><span className="rs-time">{formatDate(entry.occurred_at)}</span></td>
                  <td><strong>{entry.loan_title}</strong></td>
                  <td>{entry.action === "sale" ? t("Sale") : t("Purchase")}</td>
                  <td><span className="rs-capital">{money(entry.currency, entry.principal_minor)}</span></td>
                  <td><strong className="rs-total">{money(entry.currency, entry.cash_amount_minor)}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
      {dialog?.kind === "edit" ? <SellInvestmentDialog holding={dialog.holding} listing={dialog.listing} onClose={() => setDialog(null)} /> : null}
      {dialog?.kind === "cancel" ? <CancelListingDialog holding={dialog.holding} listing={dialog.listing} onClose={() => setDialog(null)} /> : null}
    </div>
  );
}
