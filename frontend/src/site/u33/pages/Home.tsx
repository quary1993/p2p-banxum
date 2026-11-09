// IP of Webby-Soft SRL.
/*
 * U33 home page (design index.html with complete.js, calculator*.js, persuasion.js,
 * money-flow.js, security-opportunities.js and the mobile edition's mobile.js,
 * mobile-money-flow.js, polish-main.js): hero, investment flow, opportunities with the
 * calculator, security, how it works, questions, closing call to action.
 *
 * Live data instead of the design's three sample loans: the opportunities, the calculator, the
 * security example and the hero rate come from the public projects API (open projects first,
 * at most three, U33-DEC-39); the hero falls back to the statistics' average rate when nothing
 * is open. Texts follow the reconciliation decisions: U33-DEC-38 (collateral or guarantees, no
 * "protected"), U33-DEC-01 (confirmation with the PIN), U33-DEC-35 (valuation statement),
 * U33-DEC-12 (0% investment fees, special operations may cost).
 */
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type RefObject } from "react";

import { t, useT } from "../../../i18n";
import { useSiteTitle } from "../../context";
import { usePublicProjects, usePublicStatistics, type PublicProject } from "../../data";
import { dateShort, dateKey, num, siteToday } from "../../format";
import { projectView, type ProjectView } from "../../projects";
import { GLYPHS } from "../glyphs";
import { useInView, useNarrow, useReducedMotion, useTimeline } from "../hooks";
import {
  assetName,
  calculatorAmountText,
  estimate,
  homeOpportunities,
  ltvText,
  maxOpenRateBps,
  parseCalculatorAmount,
  paymentSummary,
  rateText,
  securityFigure,
  securityGlyph,
  securityTitle,
  splitCents,
  wholeAmount
} from "../loans";
import { Flag, HomeSectionLink, MobileLtv, Ni, PublicLink } from "../ui";

const LOGO = "/brand/banxum-logo.svg";

export function Home() {
  useSiteTitle(null);
  const projects = usePublicProjects();
  const statistics = usePublicStatistics();
  const today = siteToday();
  const views = useMemo(() => (projects.data ?? []).map((p) => projectView(p, today)), [projects.data, today]);
  const shown = useMemo(() => homeOpportunities(views), [views]);
  const maxRate = maxOpenRateBps(views);
  const average = statistics.data?.average_interest_rate_bps ?? null;
  const heroRate = maxRate ?? average;
  const flowRate = heroRate ?? 800;

  return (
    <>
      <Hero average={maxRate === null && average !== null} rateBps={heroRate} />
      <MoneyFlow rateBps={flowRate} />
      <Opportunities error={projects.isError} loading={projects.isPending} onRetry={() => void projects.refetch()} views={shown} />
      <SecuritySection views={views} />
      <HowItWorks />
      <Questions />
      <ClosingCall />
    </>
  );
}

// ---------------------------------------------------------------------------------------------
// Hero

function Hero({ rateBps, average }: { rateBps: number | null; average: boolean }) {
  const t = useT();
  const narrow = useNarrow();
  const rate = rateBps === null ? null : rateText(rateBps);
  return (
    <section aria-labelledby="hero-title" className="hero">
      <div className="eyebrow">
        <span aria-hidden="true" className="swiss-flag" />
        <span>{t("Swiss Investment Platform")}</span>
      </div>
      <h1 id="hero-title">
        <span>{t("Invest in business loans.")}</span>{" "}
        {narrow ? (
          <span className="secured">
            <span className="security-phrase">{t("Secured by")}</span>{" "}
            <span className="asset-phrase">{t("collateral or guarantees.")}</span>
          </span>
        ) : (
          <span className="secured">{t("Secured by collateral or guarantees.")}</span>
        )}
      </h1>
      <p className="hero-description">{t("Earn in EUR and CHF.")}</p>
      <HomeSectionLink className="primary" section="opportunities">
        {t("View investment opportunities")} <Ni glyph="arrow" />
      </HomeSectionLink>
      <div aria-label={t("Investment features")} className="benefits">
        <div className="benefit interest">
          <p
            aria-label={
              rate === null
                ? t("Annual interest")
                : average
                  ? t("Average annual interest {rate} percent", { rate })
                  : t("Annual interest up to {rate} percent", { rate })
            }
            className="benefit-value rate"
            id="hero-rate"
          >
            {average || rate === null ? null : <span className="rate-prefix">{t("Up to")}</span>}
            <span id="hero-max-rate">{rate ?? "–"}</span>
            {rate === null ? null : <span className="percent">%</span>}
          </p>
          <h2>{average ? t("Average annual interest") : t("Annual interest")}</h2>
        </div>
        <div className="benefit fees">
          <p className="benefit-value">
            0<span className="percent">%</span>
          </p>
          <h2>{t("Investment fees")}</h2>
        </div>
        <div className="benefit assets">
          <p className="benefit-value asset-value">{t("Secured")}</p>
          <h2>{t("Every loan is secured by collateral or guarantees.")}</h2>
          <p className="benefit-detail">{t("Collateral does not guarantee repayment.")}</p>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------------------------
// Investment flow (money-flow.js; mobile-money-flow.js below 1120 px)

const FLOW_MS = 4800;
const PRINCIPAL = 20000;

const clamp = (value: number) => Math.max(0, Math.min(1, value));
const ease = (value: number) => value * value * (3 - 2 * value);

/** The return path of the desktop flow: down from the business, round the corner, into the receipt. */
function returnPosition(progress: number): [number, number] {
  const vertical = 42;
  const corner = 45.45;
  const horizontal = 251;
  const distance = progress * (vertical + corner + horizontal);
  if (distance <= vertical) return [704, 163 + distance];
  if (distance < vertical + corner) {
    const step = (distance - vertical) / corner;
    return [704 - 28 * step * step, 205 + 56 * step - 28 * step * step];
  }
  return [676 - (distance - vertical - corner), 233];
}

function MoneyFlow({ rateBps }: { rateBps: number }) {
  const t = useT();
  const narrow = useNarrow();
  const shellRef = useRef<HTMLDivElement>(null);
  const { elapsed, running, reduced, replay } = useTimeline(shellRef, FLOW_MS);
  const rate = rateText(rateBps);
  const earned = num((PRINCIPAL * rateBps) / 10000, 0);
  const principal = num(PRINCIPAL, 0);
  const phase = (start: number, end: number) => clamp((elapsed - start) / (end - start));
  const step = elapsed < 1600 ? 1 : elapsed < 2640 ? 2 : 3;
  const settled = elapsed >= 4480;
  const finished = elapsed >= FLOW_MS;
  const [rx, ry] = settled ? [425, 233] : returnPosition(ease(phase(2640, 4480)));
  const outgoingX = settled ? 348 : 160 + 380 * ease(phase(0, 1600));
  const returnTransform = `translate(${rx.toFixed(2)} ${ry.toFixed(2)})`;
  const returnOpacity = settled ? 1 : phase(1760, 1960);
  const description = t(
    "A simplified one-year example at {rate}% annual interest: EUR {principal} invested, EUR {principal} returned with EUR {earned} interest. This illustrates the investment flow, not the payment schedule of a particular loan.",
    { rate, principal, earned }
  );

  return (
    <section aria-labelledby="story-title" className="investment-story money-flow-story content-shell" id="investment-flow">
      <div className="story-copy">
        <h2 id="story-title">
          {t("Invest in loans.")}
          <br />{" "}
          <span>{t("Earn the interest.")}</span>
        </h2>
      </div>
      <div
        className={`scene-shell${narrow ? " has-mobile-money-flow" : ""}${!running && !finished ? " is-paused" : ""}`}
        data-elapsed={Math.round(elapsed)}
        data-finished={String(finished)}
        data-playing={String(running)}
        data-step={step}
        id="money-flow"
        ref={shellRef}
      >
        <div className="scene-brand">
          <span />
          <img alt="Banxum" src={LOGO} width="86" />
          <span />
        </div>
        <svg aria-labelledby="money-flow-title money-flow-description" className="receipt-circuit" role="img" viewBox="0 0 760 350">
          <title id="money-flow-title">{t("Your investment goes to a business and returns with interest.")}</title>
          <desc id="money-flow-description">{description}</desc>
          <g aria-hidden="true" fill="none" stroke="#BDC7CE" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.4">
            <path d="M109 101H587" id="money-outbound-path" style={{ opacity: 1 }} />
            <path d="m579 95 8 6-8 6" stroke="#6C7A84" />
            <path
              d="M648 136V220Q648 248 620 248H450"
              id="money-inbound-path"
              style={{ opacity: settled ? 1 : 0.45 + 0.55 * phase(2480, 2800) }}
            />
            <path d="m458 242-8 6 8 6" stroke="#6C7A84" />
          </g>
          <g aria-hidden="true" fill="#111214" fontSize="21" fontWeight="500" letterSpacing="-.4" textAnchor="middle">
            <text x="57" y="107">
              {t("You")}
            </text>
            <text x="648" y="107">
              {t("Business")}
            </text>
          </g>
          <text aria-hidden="true" fill="#65717B" fontSize="13" textAnchor="middle" x="348" y="59">
            {t("Your investment")}
          </text>
          <g
            aria-hidden="true"
            id="money-outgoing"
            style={{ opacity: settled ? phase(4480, 4800) : 1 - phase(1600, 1760) }}
            textAnchor="middle"
            transform={`translate(${outgoingX.toFixed(2)} 82.00)`}
          >
            <rect className="transfer-paper" height="28" rx="4" width="120" x="-60" y="-21" />
            <text fill="#343C42" fontSize="20">
              <tspan fontSize="12">EUR </tspan>
              {principal}
            </text>
          </g>
          <rect aria-hidden="true" fill="#FFF" height="146" rx="22" stroke="#DFE5E9" width="426" x="24" y="154" />
          <text aria-hidden="true" fill="#111214" fontSize="14" fontWeight="500" letterSpacing="-.15" x="49" y="185">
            {t("Back to your account")}
          </text>
          <path aria-hidden="true" d="M49 201H425" fill="none" stroke="#E6EBEE" />
          <g aria-hidden="true" id="money-receipt-labels" style={{ opacity: settled ? 1 : 0.35 + 0.65 * phase(4000, 4480) }}>
            <text fill="#343C42" fontSize="15" x="49" y="232">
              {t("Your investment")}
            </text>
            <text fill="#1C7946" fontSize="15" x="49" y="271">
              {t("Interest")}
            </text>
          </g>
          <text
            aria-hidden="true"
            fill="#59636D"
            fontSize="12"
            id="money-return-caption"
            style={{ opacity: settled ? phase(4480, 4800) : 0 }}
            textAnchor="middle"
            x="546"
            y="227"
          >
            {t("Investment")}
            <tspan fill="#1C7946">{` + ${t("interest")}`}</tspan>
          </text>
          <defs>
            <mask height="350" id="money-receipt-paper-mask" maskUnits="userSpaceOnUse" width="760" x="0" y="0">
              <rect fill="#FFF" height="350" width="760" />
              <rect fill="#000" height="146" rx="22" stroke="#000" strokeWidth="2" width="426" x="24" y="154" />
            </mask>
          </defs>
          <g aria-hidden="true" mask="url(#money-receipt-paper-mask)">
            <rect
              className="return-paper"
              height="69"
              id="money-return-paper"
              rx="4"
              style={{ opacity: returnOpacity }}
              transform={returnTransform}
              width="124"
              x="-121"
              y="-23"
            />
          </g>
          <g aria-hidden="true" id="money-return" style={{ opacity: returnOpacity }} textAnchor="end" transform={returnTransform}>
            <text fill="#111214" fontSize="22" letterSpacing="-.35">
              <tspan fill="#65717B" fontSize="12" letterSpacing="0">
                EUR{" "}
              </tspan>
              {principal}
            </text>
            <g id="money-interest" style={{ opacity: settled ? 1 : phase(2080, 2480) }}>
              <text fill="#1C7946" fontSize="24" letterSpacing="-.45" y="38">
                <tspan fontSize="16">+ </tspan>
                <tspan fontSize="12" letterSpacing="0">
                  EUR{" "}
                </tspan>
                {earned}
              </text>
            </g>
          </g>
        </svg>
        <div className="flow-caption">
          <p className="scene-note">
            {t("1-year example")} · <span id="money-example-rate">{`${rate}%`}</span> {t("annual interest")}
          </p>
          <div className="flow-controls">
            <button aria-label={t("Replay investment flow")} hidden={reduced} id="money-flow-replay" onClick={replay} type="button">
              <span aria-hidden="true">↻</span> {t("Replay")}
            </button>
          </div>
        </div>
        {narrow ? <MobileMoneyFlow earned={earned} principal={principal} rate={rate} rateBps={rateBps} /> : null}
      </div>
    </section>
  );
}

/** The mobile edition's flow (mobile-money-flow.js): vertical, with its own short animation. */
function MobileMoneyFlow({ rate, principal, earned }: { rate: string; rateBps: number; principal: string; earned: string }) {
  const t = useT();
  const ref = useRef<HTMLDivElement>(null);
  const phone = useMobilePhone();
  const { elapsed, running, reduced, replay } = useTimeline(ref, FLOW_MS, phone);
  const phase = (start: number, end: number) => clamp((elapsed - start) / (end - start));
  const settled = elapsed >= 4480;
  const step = elapsed < 1600 ? 1 : elapsed < 2640 ? 2 : 3;
  return (
    <div
      className="mobile-money-flow"
      data-elapsed={Math.round(elapsed)}
      data-finished={String(elapsed >= FLOW_MS)}
      data-playing={String(running)}
      data-step={step}
      id="mobile-money-flow"
      ref={ref}
    >
      <svg aria-labelledby="mobile-money-title mobile-money-description" className="mobile-receipt-circuit" role="img" viewBox="0 0 340 350">
        <title id="mobile-money-title">{t("Your investment goes to a business and returns with interest.")}</title>
        <desc id="mobile-money-description">
          {t(
            "A simplified one-year example at {rate}% annual interest: EUR {principal} invested, EUR {principal} returned with EUR {earned} interest. This illustrates the investment flow, not the payment schedule of a particular loan.",
            { rate, principal, earned }
          )}
        </desc>
        <g aria-hidden="true">
          <g fill="none" stroke="#BDC7CE" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.4">
            <path d="M63 77H234" />
            <path d="m228 72 6 5-6 5" stroke="#6C7A84" />
            <path d="M282 102V154" />
            <path d="m277 148 5 6 5-6" stroke="#6C7A84" />
          </g>
          <g fill="#111214" fontSize="19" fontWeight="500" letterSpacing="-.35" textAnchor="middle">
            <text x="30" y="83">
              {t("You")}
            </text>
            <text x="282" y="83">
              {t("Business")}
            </text>
          </g>
          <text fill="#65717B" fontSize="14" textAnchor="middle" x="158" y="22">
            {t("Your investment")}
          </text>
          <g
            id="mobile-money-outgoing"
            style={{ opacity: settled ? phase(4480, 4800) : 1 - phase(1440, 1760) }}
            textAnchor="middle"
            transform={`translate(${settled ? 158 : 88 + 154 * ease(phase(0, 1600))} 53)`}
          >
            <rect fill="#F5F6F7" height="28" rx="4" width="116" x="-58" y="-21" />
            <text fill="#343C42" fontSize="21" letterSpacing="-.35">
              <tspan fontSize="14" letterSpacing="0">
                EUR{" "}
              </tspan>
              {principal}
            </text>
          </g>
          <rect fill="#FFF" height="165" rx="20" stroke="#DFE5E9" width="320" x="10" y="175" />
          <text fill="#111214" fontSize="16" fontWeight="500" letterSpacing="-.2" x="32" y="207">
            {t("Back to your account")}
          </text>
          <path d="M32 225H308" fill="none" stroke="#E6EBEE" />
          <g id="mobile-money-receipt-labels" style={{ opacity: 0.4 + 0.6 * phase(3840, 4480) }}>
            <text fill="#343C42" fontSize="15" x="32" y="262">
              {t("Your investment")}
            </text>
            <text fill="#1C7946" fontSize="15" x="32" y="308">
              {t("Interest")}
            </text>
          </g>
          <g
            id="mobile-money-receipt-values"
            style={{ opacity: phase(3840, 4480) }}
            textAnchor="end"
            transform={`translate(0 ${8 * (1 - ease(phase(3840, 4480)))})`}
          >
            <text fill="#111214" fontSize="23" letterSpacing="-.45" x="308" y="262">
              <tspan fill="#65717B" fontSize="14" letterSpacing="0">
                EUR{" "}
              </tspan>
              {principal}
            </text>
            <text fill="#1C7946" fontSize="25" letterSpacing="-.5" x="308" y="308">
              <tspan fontSize="17">+ </tspan>
              <tspan fontSize="14" letterSpacing="0">
                EUR{" "}
              </tspan>
              {earned}
            </text>
          </g>
          <g
            id="mobile-money-return"
            style={{ opacity: phase(1760, 2000) * (1 - phase(3840, 4320)) }}
            textAnchor="end"
            transform={`translate(308 ${112 + 40 * ease(phase(2640, 4000))})`}
          >
            <rect fill="#F5F6F7" height="60" rx="5" width="118" x="-115" y="-23" />
            <text fill="#111214" fontSize="20" letterSpacing="-.35">
              <tspan fill="#65717B" fontSize="14" letterSpacing="0">
                EUR{" "}
              </tspan>
              {principal}
            </text>
            <g id="mobile-money-interest" style={{ opacity: phase(2080, 2480) }}>
              <text fill="#1C7946" fontSize="22" letterSpacing="-.4" y="31">
                <tspan fontSize="16">+ </tspan>
                <tspan fontSize="14" letterSpacing="0">
                  EUR{" "}
                </tspan>
                {earned}
              </text>
            </g>
          </g>
        </g>
      </svg>
      <p className="mobile-flow-note">{t("1-year example · {rate}% annual interest", { rate })}</p>
      <div className="mobile-flow-controls">
        <button aria-label={t("Replay investment flow")} hidden={reduced} id="mobile-money-replay" onClick={replay} type="button">
          <span aria-hidden="true">↻</span> {t("Replay")}
        </button>
      </div>
    </div>
  );
}

function useMobilePhone() {
  const [phone, setPhone] = useState(() => typeof window.matchMedia === "function" && window.matchMedia("(max-width:767px)").matches);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return undefined;
    const list = window.matchMedia("(max-width:767px)");
    const update = () => setPhone(list.matches);
    list.addEventListener("change", update);
    return () => list.removeEventListener("change", update);
  }, []);
  return phone;
}

// ---------------------------------------------------------------------------------------------
// Opportunities (cards + calculator). Phones: a horizontal carousel with a pager (mobile.js).

function Opportunities({
  views,
  loading,
  error,
  onRetry
}: {
  views: ProjectView[];
  loading: boolean;
  error: boolean;
  onRetry: () => void;
}) {
  const t = useT();
  const narrow = useNarrow();
  const gridRef = useRef<HTMLDivElement>(null);
  const openViews = views.filter((view) => view.isOpen);
  return (
    <section aria-labelledby="opportunities-title" className="public-opportunities" data-section-divider="" id="opportunities">
      <div className="opportunities-heading">
        <div>
          <h2 id="opportunities-title">{t("Investment opportunities")}</h2>
          <p>{t("Business loans in EUR and CHF, secured by collateral or guarantees.")}</p>
        </div>
      </div>
      {views.length ? (
        <>
          {narrow && views.length > 1 ? <LoanPager count={views.length} gridRef={gridRef} /> : null}
          <div className="opportunity-grid" ref={gridRef}>
            {views.map((view) => (
              <LoanCard key={view.p.loan_id} view={view} />
            ))}
          </div>
        </>
      ) : (
        <div className="bxp-empty" role="status">
          {loading ? (
            <p>{t("Loading the current opportunities.")}</p>
          ) : error ? (
            <p>
              {t("The opportunities could not be loaded.")}{" "}
              <button className="bxp-text-button" onClick={onRetry} type="button">
                {t("Try again")}
              </button>
            </p>
          ) : (
            <>
              <h3>{t("No opportunity is open right now.")}</h3>
              <p>{t("New business loans are published here when they open for investment.")}</p>
              <PublicLink className="context-opportunity-link" href="/projects">
                {t("See all projects")} <Ni glyph="arrow" />
              </PublicLink>
            </>
          )}
        </div>
      )}
      {openViews.length ? <Calculator views={openViews} /> : null}
      <div className="opportunities-note">
        <p>
          {t("Projections are before tax and assume repayment as agreed.")}{" "}
          <PublicLink href="/projects">{t("All projects, including funded and repaid loans")}</PublicLink>
        </p>
      </div>
    </section>
  );
}

/** A loan card (design public-loan). */
function LoanCard({ view }: { view: ProjectView }) {
  const t = useT();
  const p = view.p;
  const payment = paymentSummary(p);
  const titleId = `loan-${p.loan_id}-title`;
  const figure = securityFigure(p);
  const minimum = p.minimum_investment_minor;
  return (
    <article aria-labelledby={titleId} className="public-loan" data-currency={p.currency}>
      <div className="loan-location">
        <span className="card-country">
          <Flag code={p.borrower_country} />
          <span>{p.borrower_sector || view.countryName}</span>
        </span>
        <span className="loan-currency">{p.currency}</span>
      </div>
      <h3 id={titleId}>{p.title}</h3>
      {p.investor_summary ? <p className="loan-purpose">{p.investor_summary}</p> : null}
      <div className="loan-terms">
        <div>
          <span className="loan-rate">
            {rateText(p.interest_rate_bps)}
            <span>%</span>
          </span>
          <span className="term-label">{t("Annual interest")}</span>
        </div>
        <div className="loan-duration">
          <span>
            {p.term_months} <small>{t("months")}</small>
          </span>
          <span className="term-label">{t("Investment term")}</span>
        </div>
      </div>
      <div className="card-payment">
        <Ni glyph="clock" />
        <span>
          <strong>{payment.title}</strong>
          <small>{view.isSoon ? t("Opens {date}", { date: dateShort(dateKey(p.published_at)) }) : payment.detail}</small>
        </span>
      </div>
      <div className="loan-security">
        <Ni className="security-symbol" glyph={securityGlyph(p.collateral_type)} />
        <div>
          <span className="security-kicker">{t("SECURITY")}</span>
          <strong>{securityTitle(p)}</strong>
          {figure ? <span className="security-detail">{t("Loan-to-value: {ltv}", { ltv: ltvText(figure.ltv) })}</span> : null}
        </div>
      </div>
      <div className="loan-footer">
        {minimum !== null && view.isOpen ? (
          <span>
            {t("From")} <strong>{`${p.currency} ${wholeAmount(minimum)}`}</strong>
          </span>
        ) : (
          <span>{view.isSoon ? t("Coming soon") : null}</span>
        )}
        <PublicLink aria-label={t("View details: {title}", { title: p.title })} href={`/projects/${encodeURIComponent(p.loan_id)}`}>
          {t("View details")} <Ni glyph="arrow" />
        </PublicLink>
      </div>
    </article>
  );
}

/** The phone carousel's pager (mobile.js mobile-loan-pager): follows the scroll position. */
function LoanPager({ count, gridRef }: { count: number; gridRef: RefObject<HTMLDivElement | null> }) {
  const t = useT();
  const reduced = useReducedMotion();
  const [index, setIndex] = useState(0);

  useEffect(() => {
    const grid = gridRef.current;
    if (!grid) return undefined;
    let frame = 0;
    const update = () => {
      frame = 0;
      const cards = [...grid.querySelectorAll<HTMLElement>(".public-loan")];
      if (!cards.length) return;
      const left = grid.getBoundingClientRect().left + parseFloat(getComputedStyle(grid).paddingLeft || "0");
      const best = cards.reduce(
        (bestIndex, card, cardIndex) =>
          Math.abs(card.getBoundingClientRect().left - left) < Math.abs(cards[bestIndex].getBoundingClientRect().left - left)
            ? cardIndex
            : bestIndex,
        0
      );
      setIndex(best);
    };
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    grid.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    update();
    return () => {
      grid.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [gridRef, count]);

  const move = (step: number) => {
    const grid = gridRef.current;
    const cards = grid ? [...grid.querySelectorAll<HTMLElement>(".public-loan")] : [];
    const target = Math.max(0, Math.min(cards.length - 1, index + step));
    if (!grid || !cards[target]) return;
    grid.scrollTo({ left: cards[target].offsetLeft - cards[0].offsetLeft, behavior: reduced ? "instant" : "smooth" });
  };

  return (
    <div aria-label={t("Browse investment opportunities")} className="mobile-loan-pager" role="group">
      <button aria-label={t("Previous investment opportunity")} disabled={index === 0} onClick={() => move(-1)} type="button">
        <Ni glyph="arrow" />
      </button>
      <output aria-label={t("Opportunity {index} of {count}", { index: index + 1, count })} aria-live="polite">
        {`${index + 1} / ${count}`}
      </output>
      <button aria-label={t("Next investment opportunity")} disabled={index >= count - 1} onClick={() => move(1)} type="button">
        <Ni glyph="arrow" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Calculator (calculator.js + calculator-choices.js; polish-main.js selection line on phones)

const ROTATION_MS = 4000;
const TYPE_MS = 85;
const DEMO_HOLD_MS = 6600;
const DEFAULT_AMOUNT = 10000;

function Calculator({ views }: { views: ProjectView[] }) {
  const t = useT();
  const narrow = useNarrow();
  const reduced = useReducedMotion();
  const sectionRef = useRef<HTMLElement>(null);
  const inView = useInView(sectionRef);
  const [selectedId, setSelectedId] = useState(views[0].p.loan_id);
  const [text, setText] = useState(() => calculatorAmountText(Math.max(DEFAULT_AMOUNT, minimumMajor(views[0].p))));
  const [adjusted, setAdjusted] = useState(false);
  const [interacted, setInteracted] = useState(false);
  const [demo, setDemo] = useState<{ shown: string; written: boolean } | null>(null);
  const [changing, setChanging] = useState(0);
  const demoStarted = useRef(false);
  const choiceRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const previousKey = useRef("");

  const selected = views.find((view) => view.p.loan_id === selectedId) ?? views[0];
  const p = selected.p;
  const amount = parseCalculatorAmount(text);
  const minimum = minimumMajor(p);
  const remaining = p.remaining_capacity_minor / 100;
  let message = "";
  if (!text.trim()) message = t("Enter an investment amount.");
  else if (!Number.isFinite(amount)) message = t("Enter an amount with up to two decimal places.");
  else if (amount < minimum) message = t("The minimum for this opportunity is {amount}.", { amount: `${p.currency} ${num(minimum, 0)}` });
  else if (amount > remaining) message = t("The remaining amount of this opportunity is {amount}.", { amount: `${p.currency} ${num(remaining, 0)}` });
  const result = message ? null : estimate(p, amount);
  const rotation = interacted ? "stopped" : reduced ? "reduced" : inView ? "running" : "paused";

  // The "result changing" pulse when the estimate changes (not on the first one).
  useEffect(() => {
    const key = `${selectedId}:${amount}`;
    if (result && previousKey.current && previousKey.current !== key) setChanging((value) => value + 1);
    if (result) previousKey.current = key;
  }, [selectedId, amount, result]);

  const choose = useCallback(
    (view: ProjectView, automatic = false) => {
      setSelectedId(view.p.loan_id);
      const current = parseCalculatorAmount(text);
      const raise = text.trim() !== "" && Number.isFinite(current) && current < minimumMajor(view.p);
      if (raise) setText(calculatorAmountText(minimumMajor(view.p)));
      setAdjusted(raise);
      if (!automatic) setDemo(null);
    },
    [text]
  );

  const takeControl = () => {
    if (!interacted) setInteracted(true);
    setDemo(null);
  };

  // Rotation through the opportunities every 4 s while in view and untouched.
  useEffect(() => {
    if (rotation !== "running" || views.length < 2) return undefined;
    const timer = window.setTimeout(() => {
      const index = views.findIndex((view) => view.p.loan_id === selectedId);
      choose(views[(index + 1) % views.length], true);
    }, ROTATION_MS);
    return () => window.clearTimeout(timer);
  }, [rotation, selectedId, views, choose]);

  // The typing demonstration of the amount, once, the first time the calculator is in view.
  useEffect(() => {
    if (demoStarted.current || interacted || reduced || !inView) return undefined;
    demoStarted.current = true;
    const full = text;
    const timers: number[] = [];
    setDemo({ shown: "", written: false });
    for (let i = 1; i <= full.length; i += 1) {
      timers.push(window.setTimeout(() => setDemo({ shown: full.slice(0, i), written: i === full.length }), i * TYPE_MS));
    }
    timers.push(window.setTimeout(() => setDemo(null), full.length * TYPE_MS + DEMO_HOLD_MS));
    return () => timers.forEach((timer) => window.clearTimeout(timer));
    // The demonstration types the amount shown when it starts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inView, interacted, reduced]);

  const onChoiceKey = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let next: number;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (index + 1) % views.length;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (index + views.length - 1) % views.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = views.length - 1;
    else return;
    event.preventDefault();
    takeControl();
    choose(views[next]);
    choiceRefs.current[next]?.focus();
  };

  const months = p.term_months;
  const timing =
    result?.repayment === "bullet"
      ? t("Capital and interest paid at maturity.")
      : result?.repayment === "interest-only"
        ? t("Monthly interest payments; your investment is repaid at maturity.")
        : t("Monthly payments include interest and repayment of your investment.");
  const totalLabel = planIsBullet(p) ? t("Total repayment at maturity") : t("Total repayments over {months} months", { months });
  const [whole, cents] = result ? splitCents(result.interestTotal) : ["—", ""];

  return (
    <section
      aria-labelledby="calculator-title"
      className="interest-calculator with-opportunity-choices"
      data-opportunity={p.loan_id}
      data-rotation={rotation}
      onFocusCapture={(event) => {
        if ((event.target as HTMLElement).closest("#investment-amount, [data-calculator-loan]")) takeControl();
      }}
      onPointerDownCapture={() => {
        if (!narrow) takeControl();
      }}
      ref={sectionRef}
    >
      <div className="calculator-controls">
        <h2 id="calculator-title">{t("What could your capital earn?")}</h2>
        <div aria-label={t("Choose an opportunity")} className="calculator-choices" role="radiogroup">
          {views.map((view, index) => {
            const active = view.p.loan_id === selected.p.loan_id;
            return (
              <button
                aria-checked={active}
                className="calculator-choice"
                data-calculator-loan={view.p.loan_id}
                key={view.p.loan_id}
                onClick={() => {
                  takeControl();
                  choose(view);
                }}
                onKeyDown={(event) => onChoiceKey(event, index)}
                ref={(element) => {
                  choiceRefs.current[index] = element;
                }}
                role="radio"
                tabIndex={active ? 0 : -1}
                type="button"
              >
                <span className="choice-top">
                  <Flag code={view.p.borrower_country} decorative />
                  <span>{view.p.currency}</span>
                  <i aria-hidden="true" className="choice-selected ni">
                    {GLYPHS.check}
                  </i>
                </span>
                <strong>{view.p.title}</strong>
                <span className="choice-terms">
                  <b>{t("{rate}% p.a.", { rate: rateText(view.p.interest_rate_bps) })}</b>
                  <span>{t("{months} months", { months: view.p.term_months })}</span>
                </span>
              </button>
            );
          })}
        </div>
        {narrow ? (
          <p className="calculator-selection">
            <strong>{t("{rate}% annual interest", { rate: rateText(p.interest_rate_bps) })}</strong>
            <span>{t("{months} months", { months })}</span>
          </p>
        ) : null}
        <label htmlFor="investment-amount">{t("Your investment")}</label>
        <div className="amount-input">
          <span id="input-currency">{p.currency}</span>
          <span className={`amount-field${demo ? " is-demonstrating" : ""}${demo?.written ? " is-written" : ""}`}>
            <input
              aria-describedby="minimum-note amount-error"
              aria-invalid={Boolean(message)}
              autoComplete="off"
              id="investment-amount"
              inputMode="decimal"
              onBlur={() => {
                if (!message && Number.isFinite(amount)) setText(calculatorAmountText(amount));
              }}
              onChange={(event) => {
                takeControl();
                setAdjusted(false);
                setText(event.target.value);
              }}
              type="text"
              value={text}
            />
            <span aria-hidden="true" className="amount-demo">
              <span id="amount-demo-text">{demo?.shown ?? ""}</span>
              <i className="amount-demo-caret" />
            </span>
          </span>
        </div>
        <p className="minimum-note" id="minimum-note">
          {t("Minimum for this opportunity: {amount}", { amount: `${p.currency} ${num(minimum, 0)}` })}
          <span hidden={!adjusted} id="minimum-adjustment">
            {` · ${t("Set to minimum")}`}
          </span>
        </p>
        <p className="amount-error" hidden={!message} id="amount-error" role="status">
          {message}
        </p>
      </div>
      <div
        aria-atomic="true"
        aria-live={rotation === "running" ? "off" : "polite"}
        className={`calculator-result${changing ? " result-changing" : ""}`}
        key={changing}
      >
        <p className="result-label">
          {t("Projected interest")} <span id="estimate-term">{t("over {months} months", { months })}</span>
        </p>
        <p className="interest-amount">
          <span className="amount-currency" id="result-currency">
            {p.currency}
          </span>
          <span id="interest-value">
            {whole}
            {cents ? <span className="cents">{cents}</span> : null}
          </span>
        </p>
        <p className="repayment-timing" id="repayment-timing">
          {timing}
        </p>
        <div className="calculator-totals">
          <div>
            <span id="principal-label">{t("Investment")}</span>
            <strong id="principal-value">{result ? `${p.currency} ${num(result.principalTotal)}` : "—"}</strong>
          </div>
          <div>
            <span id="total-label">{totalLabel}</span>
            <strong id="total-value">{result ? `${p.currency} ${num(result.total)}` : "—"}</strong>
          </div>
        </div>
        <div className="calculator-period">
          <span>{t("0% investment fees")}</span>
          <PublicLink
            aria-label={t("View opportunity: {title}", { title: p.title })}
            className="context-opportunity-link"
            href={`/projects/${encodeURIComponent(p.loan_id)}`}
            id="calculator-opportunity-link"
          >
            {t("View opportunity")} <Ni glyph="arrow" />
          </PublicLink>
        </div>
      </div>
    </section>
  );
}

function minimumMajor(p: PublicProject) {
  return (p.minimum_investment_minor ?? 0) / 100;
}

function planIsBullet(p: PublicProject) {
  return p.repayment_type === "interest_only_then_bullet";
}

// ---------------------------------------------------------------------------------------------
// Security (security-opportunities.js; the mobile edition adds the HTML bars)

const SECURITY_EXAMPLES = 3;
const BAR_WIDTH = 482;
const COLLATERAL_MOTION_MS = 1650;

function SecuritySection({ views }: { views: ProjectView[] }) {
  const t = useT();
  const examples = useMemo(() => {
    const withFigure = views.filter((view) => securityFigure(view.p));
    const ordered = [...homeOpportunities(withFigure, SECURITY_EXAMPLES), ...withFigure];
    return ordered.filter((view, index) => ordered.indexOf(view) === index).slice(0, SECURITY_EXAMPLES);
  }, [views]);
  return (
    <section aria-labelledby="security-title" className="security-section" data-section-divider="" id="security">
      <div className="security-layout">
        <div className="security-message">
          <h2 id="security-title">
            {t("Collateral or guarantees")}
            <br />{" "}
            {t("behind every loan.")}
          </h2>
          <div className="banxum-role">
            <div>
              <strong>{t("Loan and asset value on the same scale.")}</strong>
            </div>
          </div>
        </div>
        {examples.length ? <SecurityExample examples={examples} /> : null}
      </div>
    </section>
  );
}

function SecurityExample({ examples }: { examples: ProjectView[] }) {
  const t = useT();
  const narrow = useNarrow();
  const reduced = useReducedMotion();
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [fade, setFade] = useState(0);
  const figureRef = useRef<HTMLDivElement>(null);
  const inView = useInView(figureRef);
  const played = useRef(false);
  const timer = useRef(0);
  const previousRef = useRef<HTMLButtonElement>(null);
  const nextRef = useRef<HTMLButtonElement>(null);

  const play = useCallback(() => {
    if (reduced) return;
    window.clearTimeout(timer.current);
    setPlaying(false);
    window.requestAnimationFrame(() => {
      setPlaying(true);
      timer.current = window.setTimeout(() => setPlaying(false), COLLATERAL_MOTION_MS);
    });
  }, [reduced]);

  useEffect(() => {
    if (inView && !played.current) {
      played.current = true;
      play();
    }
  }, [inView, play]);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const view = examples[Math.min(index, examples.length - 1)];
  const p = view.p;
  const figure = securityFigure(p);
  if (!figure) return null;
  const count = examples.length;
  const show = (next: number) => {
    if (next < 0 || next >= count || next === index) return;
    window.clearTimeout(timer.current);
    setPlaying(false);
    setIndex(next);
    if (!reduced) setFade((value) => value + 1);
    // Keep the focus on a usable control at the ends of the list.
    window.setTimeout(() => {
      if (document.activeElement === nextRef.current && next === count - 1) previousRef.current?.focus({ preventScroll: true });
      if (document.activeElement === previousRef.current && next === 0) nextRef.current?.focus({ preventScroll: true });
    }, 0);
  };
  const loan = wholeAmount(figure.loanMinor);
  const value = wholeAmount(figure.valueMinor);
  const ltv = ltvText(figure.ltv);
  const markerX = (BAR_WIDTH * figure.ltv) / 100;
  const isProperty = p.collateral_type === "real_estate";
  const fadeClass = fade ? " bxp-fade-in" : "";

  return (
    <article aria-labelledby="security-example-title" className="security-example" data-opportunity={p.loan_id} id="security-opportunities">
      <div className="example-top">
        <div className="security-example-labels">
          <span>{t("SECURITY OVERVIEW")}</span>
          <span className="example-label">{view.isOpen ? t("Open opportunity") : t("Published loan")}</span>
        </div>
        {count > 1 ? (
          <nav
            aria-label={t("Browse collateral examples")}
            className="opportunity-pager"
            onKeyDown={(event) => {
              if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
                event.preventDefault();
                show(index + (event.key === "ArrowRight" ? 1 : -1));
              }
            }}
          >
            <button
              aria-label={index > 0 ? t("Previous opportunity: {title}", { title: examples[index - 1].p.title }) : t("Previous opportunity")}
              className="opportunity-step previous"
              disabled={index === 0}
              id="security-previous"
              onClick={() => show(index - 1)}
              ref={previousRef}
              title={index > 0 ? examples[index - 1].p.title : ""}
              type="button"
            >
              <Ni glyph="arrow" />
            </button>
            <span aria-label={t("Opportunity {index} of {count}", { index: index + 1, count })} className="opportunity-position" id="security-position">
              {index + 1} <span aria-hidden="true">/</span> {count}
            </span>
            <button
              aria-label={index < count - 1 ? t("Next opportunity: {title}", { title: examples[index + 1].p.title }) : t("Next opportunity")}
              className="opportunity-step next"
              disabled={index === count - 1}
              id="security-next"
              onClick={() => show(index + 1)}
              ref={nextRef}
              title={index < count - 1 ? examples[index + 1].p.title : ""}
              type="button"
            >
              <Ni glyph="arrow" />
            </button>
          </nav>
        ) : null}
      </div>
      <div className={`security-card-heading${fadeClass}`} key={`heading-${fade}`}>
        <h3 id="security-example-title">{p.title}</h3>
        <div className="collateral-summary">
          <Ni glyph={securityGlyph(p.collateral_type)} id="security-asset-icon" />
          <div>
            <strong id="security-collateral-name">{securityTitle(p)}</strong>
            <span className="security-asset-meta">
              <span id="security-country">
                <Flag className="" code={p.borrower_country} />
              </span>
              <span id="security-asset-name">{assetName(p.collateral_type)}</span>
            </span>
          </div>
        </div>
      </div>
      <div
        aria-label={t(
          "{title}: loan {currency} {loan}, {label} {currency} {value}. Loan-to-value {ltv}. Both bars use the same scale.",
          { title: p.title, currency: p.currency, loan, label: figure.valueLabel.toLowerCase(), value, ltv }
        )}
        className={`deal-comparison collateral-bands security-ltv-figure${playing ? " motion-playing" : ""}`}
        data-motion="collateral"
        ref={figureRef}
        role="group"
      >
        <svg aria-hidden="true" className="security-ltv" viewBox="0 0 482 220">
          <defs>
            <linearGradient id="security-graphite" x1="0" x2="1" y1="0" y2=".6">
              <stop stopColor="#3e4a54" />
              <stop offset="1" stopColor="#202b35" />
            </linearGradient>
          </defs>
          <text className="ltv-label" x="0" y="17">
            {t("Loan amount")}
          </text>
          <text className={`ltv-amount${fadeClass}`} id="security-loan-amount" key={`loan-${fade}`} x="0" y="51">
            <tspan className="ltv-currency">{`${p.currency} `}</tspan>
            <tspan>{loan}</tspan>
          </text>
          <rect
            className="security-ltv-bar loan-bar"
            height="14"
            rx="5"
            style={{ ["--bar-width" as string]: `${figure.ltv}%` }}
            width={markerX.toFixed(2)}
            x="0"
            y="71"
          />
          <g className="security-ltv-marker" id="security-loan-marker" style={{ transform: `translateX(${markerX.toFixed(2)}px)` }}>
            <path d="M0 85V132" stroke="#b3bdc5" strokeDasharray="2 4" strokeWidth="1" />
            <text className={`ltv-ratio${fadeClass}`} id="security-ratio" key={`ratio-${fade}`} x="12" y="81">
              {ltv}
            </text>
            <text className="ltv-ratio-label" x="12" y="99">
              {t("Loan-to-value")}
            </text>
          </g>
          <rect className="security-ltv-bar property-bar" fill="url(#security-graphite)" height="14" rx="5" width="482" x="0" y="132" />
          <text className="ltv-label" id="security-value-label" x="0" y="183">
            {figure.valueLabel}
          </text>
          <text className={`ltv-amount${fadeClass}`} id="security-collateral-amount" key={`value-${fade}`} textAnchor="end" x="482" y="187">
            <tspan className="ltv-currency">{`${p.currency} `}</tspan>
            <tspan>{value}</tspan>
          </text>
          <text className="ltv-full-value" textAnchor="end" x="470" y="143">
            100%
          </text>
        </svg>
        {narrow ? <MobileLtv currency={p.currency} figure={figure} loan={loan} value={value} /> : null}
        <button
          aria-label={t("Replay collateral comparison")}
          className="motion-replay security-ltv-replay"
          data-replay="collateral"
          disabled={reduced}
          onClick={play}
          type="button"
        >
          {t("Replay")} <span aria-hidden="true">↻</span>
        </button>
      </div>
      <div className="security-card-footer">
        <p className="property-valuation-note" hidden={!isProperty} id="security-property-valuation">
          {t("Each property value comes from a named valuation report in the credit file.")}
        </p>
        <PublicLink
          aria-label={t("View opportunity: {title}", { title: p.title })}
          className="context-opportunity-link"
          href={`/projects/${encodeURIComponent(p.loan_id)}`}
          id="security-opportunity-link"
        >
          {t("View opportunity")} <Ni glyph="arrow" />
        </PublicLink>
      </div>
      <span aria-atomic="true" aria-live="polite" className="security-live" id="security-selection-status" role="status">
        {fade ? t("{index} of {count}. {title}. Loan-to-value {ltv}.", { index: index + 1, count, title: p.title, ltv }) : ""}
      </span>
    </article>
  );
}

// ---------------------------------------------------------------------------------------------
// How it works (static illustrations; step 3 confirms with the personal PIN, U33-DEC-01)

function HowItWorks() {
  const t = useT();
  return (
    <section aria-labelledby="how-title" className="how-section" data-section-divider="" id="how-it-works">
      <div className="how-intro">
        <h2 id="how-title">{t("Explore first. Invest when you’re ready.")}</h2>
      </div>
      <ol className="steps">
        <li className="step">
          <div className="step-marker">
            <span>01</span>
            <i aria-hidden="true" />
          </div>
          <h3>
            {t("Explore")}
            <br /> {t("opportunities")}
          </h3>
          <div aria-label={t("Example of a public opportunity")} className="step-visual loan-example" role="img">
            <div className="mini-top">
              <span>{t("Switzerland · Real estate")}</span>
              <span className="mini-pill">CHF</span>
            </div>
            <h4>{t("Residential development")}</h4>
            <div className="mini-loan-terms">
              <div>
                <strong>
                  7.5<span>%</span>
                </strong>
                <small>{t("Annual interest")}</small>
              </div>
              <div>
                <b>18</b>
                <small>{t("months")}</small>
              </div>
            </div>
            <div className="mini-security">
              <Ni glyph="building" />
              <div>
                {t("Property mortgage")}
                <small>{t("First-ranking security")}</small>
              </div>
            </div>
            <div className="mini-details">
              {t("View details")} <Ni glyph="arrow" />
            </div>
          </div>
          <p className="step-outcome">{t("Explore without an account.")}</p>
        </li>
        <li className="step">
          <div className="step-marker">
            <span>02</span>
            <i aria-hidden="true" />
          </div>
          <h3>
            {t("Open and verify")}
            <br /> {t("your account")}
          </h3>
          <div aria-label={t("Illustration of account verification")} className="step-visual account-example" role="img">
            <h4>{t("Your account")}</h4>
            <p className="mini-subtitle">{t("Ready for your first investment.")}</p>
            {[t("Account security"), t("Personal profile"), t("Identity verification")].map((label) => (
              <div className="mini-check-row" key={label}>
                <Ni className="check-circle" glyph="check" />
                <span>{label}</span>
              </div>
            ))}
          </div>
          <p className="step-outcome">{t("Ready to fund your account.")}</p>
        </li>
        <li className="step">
          <div className="step-marker">
            <span>03</span>
            <i aria-hidden="true" />
          </div>
          <h3>
            {t("Fund and confirm")}
            <br /> {t("your investment")}
          </h3>
          <div aria-label={t("Illustration of personal investment confirmation")} className="step-visual confirm-example" role="img">
            <div className="mini-top">
              <span>{t("Your investment")}</span>
              <Ni glyph="lock" />
            </div>
            <p className="mini-investment">
              <small>CHF</small> 25,000
            </p>
            <p className="code-label">{t("Your PIN")}</p>
            <div aria-hidden="true" className="code-example">
              {Array.from({ length: 6 }, (_, index) => (
                <span key={index}>•</span>
              ))}
            </div>
            <div className="mini-sign">{t("Confirm with your PIN")}</div>
          </div>
          <p className="step-outcome">{t("Every investment needs your approval.")}</p>
        </li>
        <li className="step">
          <div className="step-marker last">
            <span>04</span>
          </div>
          <h3>
            {t("Follow")}
            <br /> {t("your investment")}
          </h3>
          <div aria-label={t("Example of a repayment schedule")} className="step-visual track-example" role="img">
            <div className="mini-top">
              <span>{t("Your investment")}</span>
              <span className="mini-pill">{t("Active")}</span>
            </div>
            <h4>{t("Repayment schedule")}</h4>
            <p className="mini-subtitle">{t("Residential development")}</p>
            <dl className="mini-schedule">
              <div>
                <dt>{t("Capital")}</dt>
                <dd>CHF 25,000</dd>
              </div>
              <div>
                <dt>{t("Projected interest")}</dt>
                <dd>CHF 2,815.07</dd>
              </div>
            </dl>
            <p className="mini-maturity">
              <Ni glyph="clock" />
              <span>
                {t("Paid at maturity")}
                <small>{t("18 months in this example")}</small>
              </span>
            </p>
          </div>
          <p className="step-outcome">{t("Capital and interest shown separately.")}</p>
        </li>
      </ol>
    </section>
  );
}

// ---------------------------------------------------------------------------------------------
// Questions & answers (one answer open at a time, the first one open)

function questions() {
  return [
    {
      q: t("What can I review before investing?"),
      a: t(
        "Explore each loan’s interest rate, term, repayments and collateral without an account. The company’s identity and full credit file become available after your identity is verified."
      )
    },
    {
      q: t("How are opportunities selected?"),
      a: t(
        "Banxum assesses the business, the collateral and the loan terms before deciding what to list. External specialists support the review where needed."
      )
    },
    {
      q: t("What is the minimum investment?"),
      a: t("Usually EUR 1,000 or CHF 1,000. Each opportunity shows its own minimum before you invest.")
    },
    {
      q: t("What fees will I pay?"),
      a: t("No fees to invest or receive repayments. Special operations may carry separate charges, explained before you proceed.")
    },
    {
      q: t("When will I receive interest and repayments?"),
      a: t(
        "Payments go to your Banxum account, monthly or at the end of the loan, depending on the opportunity. The schedule distinguishes interest from repayment of the money you invested."
      )
    },
    {
      q: t("Can I access my money before the loan ends?"),
      a: t(
        "You can offer your investment for sale to another investor on Banxum’s resale market. Selling depends on finding a buyer and agreeing a price."
      )
    },
    {
      q: t("Why do companies borrow through Banxum?"),
      a: t(
        "Companies use Banxum for flexible financing and direct attention to their business. We assess the purpose of the loan and how it will be repaid, then structure the financing around those needs."
      )
    },
    {
      q: t("What happens if a borrower cannot repay?"),
      a: t(
        "Banxum manages follow-up and recovery, including action to enforce collateral where appropriate. Recovery may be incomplete; you could lose part or all of your investment."
      )
    }
  ];
}

function Questions() {
  const t = useT();
  const [open, setOpen] = useState(0);
  const items = questions();
  return (
    <div className="faq-preview">
      <section aria-labelledby="faq-title" className="faq-section" data-section-divider="" id="faq">
        <div className="faq-intro">
          <h2 id="faq-title">
            {t("Questions")}
            <br /> {t("& answers")}
          </h2>
        </div>
        <div className="faq-list">
          {items.map((item, index) => (
            <details
              className="faq-item"
              key={item.q}
              name="banxum-questions"
              onToggle={(event) => {
                const isOpen = (event.currentTarget as HTMLDetailsElement).open;
                setOpen((current) => (isOpen ? index : current === index ? -1 : current));
              }}
              open={open === index}
            >
              <summary>
                {item.q}
                <span aria-hidden="true" className="faq-toggle" />
              </summary>
              <div className="faq-answer">
                <p>{item.a}</p>
              </div>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Closing call to action (the About page's "conversation" band, for opening an account)

function ClosingCall() {
  const t = useT();
  return (
    <section aria-labelledby="closing-title" className="bxp-closing">
      <h2 id="closing-title">{t("Ready when you are.")}</h2>
      <div className="bxp-closing-actions">
        <PublicLink className="bxp-closing-secondary" href="/contact">
          {t("Talk to Banxum")}
        </PublicLink>
        <PublicLink className="button-primary" href="/register">
          {t("Open an account")} <Ni glyph="arrow" />
        </PublicLink>
      </div>
    </section>
  );
}
