// IP of Webby-Soft SRL.
/*
 * Home (design: pages_home.js home()), built on three ideas: "Your capital. Your choice." (the
 * projects funding now), "Choose. Build. Follow." (how you start) and "CHF and EUR. In one
 * place." (the wallet). In between: 0% fees, the open projects and the Swiss regulation.
 *
 * Data: usePublicProjects() (carousel and "Open now", most funded first) and
 * usePublicStatistics() (the figures line). The wallet preview is a static example, as in the
 * design. While the projects load or fail there is no carousel and the grid shows a calm box.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  CtaBand,
  CurrencyFlag,
  Eyebrow,
  FaqList,
  Flag,
  NiIcon,
  ProjectCard,
  ProjectsBox,
  RiskLine,
  SiteLink,
  SubscribeBlock
} from "../components";
import { siteCompany, topFaqItems } from "../content";
import { usePublicProjects, usePublicStatistics, type PublicStatistics } from "../data";
import { DAY_BASIS, moneyMinor, moneyShortMinor, num, numMinor, pct, pctBps, round2, siteToday } from "../format";
import { openProjects, projectView, securityShort, soonProjects, timeText, type ProjectView } from "../projects";

export function Home() {
  const projectsQuery = usePublicProjects();
  const statsQuery = usePublicStatistics();
  const today = siteToday();
  const views = useMemo(() => (projectsQuery.data ?? []).map((p) => projectView(p, today)), [projectsQuery.data, today]);
  const open = openProjects(views);
  const soon = soonProjects(views);
  const ready = projectsQuery.isSuccess;
  const company = siteCompany;

  return (
    <>
      <section className="site-hero">
        <div className="site-wrap site-hero-grid">
          <div>
            <Eyebrow>
              <Flag code="CH" label="Switzerland" />
              Swiss-regulated financial platform · CHF and EUR
            </Eyebrow>
            <h1 className="site-display">Your capital. Your choice.</h1>
            <p className="site-lead">
              Lend to companies in Switzerland and the EU, one project at a time. You choose each loan from CHF 1,000 or
              EUR 1,000, see the security and the terms first, and pay no fees.
            </p>
            <div className="site-actions">
              <SiteLink className="btn btn-lg btn-primary" href="/register">
                Open account
              </SiteLink>
              <SiteLink className="btn btn-lg btn-site-outline" href="/projects">
                See open projects
              </SiteLink>
            </div>
            <div className="site-trust">
              <span>
                <NiIcon name="ni-shield-check" />
                Regulated in Switzerland · VQF · FINOS
              </span>
              <span>
                <NiIcon name="ni-file-check" />
                Audited · share capital CHF 1.1 million
              </span>
              <span>
                <NiIcon name="ni-clock" />
                Account open in 2 minutes
              </span>
            </div>
            <RiskLine />
          </div>
          <div>{open.length ? <Carousel views={open} /> : null}</div>
        </div>
      </section>

      <section className="site-section is-tint" id="fees">
        <div className="site-wrap site-split is-center">
          <div>
            <Eyebrow>Fees</Eyebrow>
            <div className="site-zero">
              <strong className="site-accent">0%</strong>
              <span>fees for investors</span>
            </div>
            <h2 className="site-h2">No fees between you and your interest</h2>
            <p className="site-lead mt-4">
              Opening your wallet, adding money, investing, receiving interest and repayments, withdrawing: all free.
            </p>
          </div>
          <div className="site-box">
            <table className="site-table site-fee-table">
              <thead>
                <tr>
                  <th>For investors</th>
                  <th className="is-num">Fee</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Opening and keeping your wallet</td>
                  <td className="is-num">0.00</td>
                </tr>
                <tr>
                  <td>Adding money, in CHF or EUR</td>
                  <td className="is-num">0.00</td>
                </tr>
                <tr>
                  <td>Investing in a loan</td>
                  <td className="is-num">0.00</td>
                </tr>
                <tr>
                  <td>Interest and repayments</td>
                  <td className="is-num">0.00</td>
                </tr>
                <tr>
                  <td>Withdrawals to your bank</td>
                  <td className="is-num">0.00</td>
                </tr>
                <tr>
                  <td>
                    Selling early on the secondary market
                    <span className="site-table-sub">Paid by the seller, only if the sale happens</span>
                  </td>
                  <td className="is-num">2% of the price</td>
                </tr>
              </tbody>
            </table>
            <p className="site-small mt-3 mb-0">Your bank may charge for its own transfers.</p>
          </div>
        </div>
      </section>

      <section className="site-section">
        <div className="site-wrap">
          <div className="site-section-head">
            <div>
              <Eyebrow>Open now</Eyebrow>
              <h2 className="site-h2">Projects looking for investors</h2>
            </div>
            <p className="site-text mb-0">
              Every project has the same page: company, amount, rate, term and security. Compare them on the same points and
              decide yourself.
            </p>
          </div>
          {ready && open.length ? (
            <div className="site-projects">
              {open.slice(0, 3).map((view) => (
                <ProjectCard key={view.p.loan_id} view={view} />
              ))}
            </div>
          ) : (
            <ProjectsBox>
              {projectsQuery.isPending ? (
                "Loading the open projects."
              ) : projectsQuery.isError ? (
                <>
                  The projects could not be loaded.{" "}
                  <a
                    href="#"
                    onClick={(event) => {
                      event.preventDefault();
                      void projectsQuery.refetch();
                    }}
                  >
                    Try again
                  </a>
                </>
              ) : (
                <>
                  No project is open for investment right now.{" "}
                  <SiteLink href="/projects?status=all">See all projects</SiteLink>
                </>
              )}
            </ProjectsBox>
          )}
          <div className="d-flex flex-wrap justify-content-between align-items-center gap-3 mt-5">
            <SiteLink className="btn btn-lg btn-site-outline" href="/projects">
              {ready ? `All ${open.length} open projects` : "See open projects"}
            </SiteLink>
            {soon.length ? (
              <span className="site-small">
                {`${soon.length} more opening soon: ${soon.map((view) => view.p.title).join(", ")}.`}
              </span>
            ) : null}
          </div>
          {statsQuery.data ? <FiguresNote stats={statsQuery.data} /> : null}
        </div>
      </section>

      <CtaBand />

      <section className="site-section" id="regulated">
        <div className="site-wrap">
          <div className="site-section-head">
            <div>
              <Eyebrow>
                <Flag code="CH" label="Switzerland" />
                Regulated in Switzerland
              </Eyebrow>
              <h2 className="site-h2">Swiss-regulated financial platform</h2>
            </div>
            <p className="site-text mb-0">
              Banxum® is a registered trademark. The platform is owned and operated by {company.name}, a Swiss financial
              company: supervised for its financial activities, answerable to an independent ombudsman, audited every year.
            </p>
          </div>
          <div className="site-cells is-4">
            <div>
              <span className="site-proof-mark">VQF</span>
              <h3 className="site-h4">Member of VQF</h3>
              <p className="site-text mb-0">
                The self-regulatory organisation recognised by FINMA supervises Garanta&apos;s financial activities and its
                anti-money-laundering duties.
              </p>
            </div>
            <div>
              <span className="site-proof-mark">FINOS</span>
              <h3 className="site-h4">Affiliated to FINOS</h3>
              <p className="site-text mb-0">
                The Swiss financial ombudsman. If you disagree with us, it mediates free of charge.
              </p>
            </div>
            <div>
              <span className="site-proof-mark">Audited</span>
              <h3 className="site-h4">Audited data</h3>
              <p className="site-text mb-0">
                Garanta&apos;s accounts and the platform&apos;s data are audited every year by an independent auditor.
              </p>
            </div>
            <div>
              <span className="site-proof-mark">CHF 1.1m</span>
              <h3 className="site-h4">Share capital</h3>
              <p className="site-text mb-0">{company.capital} of share capital behind the company that runs Banxum.</p>
            </div>
          </div>
          <SiteLink className="site-link-arrow mt-4" href="/about">
            About Garanta and how your money is protected
          </SiteLink>
        </div>
      </section>

      <section className="site-section is-paper" id="wallet">
        <div className="site-wrap site-split is-center">
          <WalletPreview />
          <div>
            <Eyebrow>
              <CurrencyFlag currency="CHF" />
              <CurrencyFlag currency="EUR" />
              Multi-currency
            </Eyebrow>
            <h2 className="site-h2">
              CHF and EUR.
              <br />
              In one place.
            </h2>
            <p className="site-lead mt-4">One account, two currencies, no conversion: Swiss loans in francs, EU loans in euros.</p>
            <ol className="site-numbered mt-4">
              <li>
                <span className="site-numbered-index">01</span>
                <div>
                  <h3 className="site-h4">From CHF 1,000 or EUR 1,000</h3>
                  <p>
                    The minimum in both currencies. Some loans ask for more, and loans from loan originators can have their own
                    minimum; the project page shows the current minimum.
                  </p>
                </div>
              </li>
              <li>
                <span className="site-numbered-index">02</span>
                <div>
                  <h3 className="site-h4">Interest calculated every day</h3>
                  <p>
                    Principal × rate ÷ 365 for each day your money is lent, paid on the dates of the schedule, and to the day if
                    you sell early.
                  </p>
                </div>
              </li>
              <li>
                <span className="site-numbered-index">03</span>
                <div>
                  <h3 className="site-h4">Your own segregated wallet</h3>
                  <p>
                    A CHF and a EUR balance in your name, kept apart from Garanta&apos;s money. What you do not invest goes back
                    to your bank after 58 days.
                  </p>
                </div>
              </li>
            </ol>
            <SiteLink className="btn btn-lg btn-primary mt-4" href="/register">
              Open account
            </SiteLink>
          </div>
        </div>
      </section>

      <section className="site-section">
        <div className="site-wrap site-split">
          <div>
            <Eyebrow>Questions</Eyebrow>
            <h2 className="site-h2">Frequently asked questions</h2>
            <p className="site-lead mt-4">
              Not answered here? See <SiteLink href="/help">all questions</SiteLink> or write to{" "}
              <a href={`mailto:${company.email}`}>{company.email}</a>.
            </p>
          </div>
          <FaqList items={topFaqItems().slice(0, 6)} openFirst />
        </div>
      </section>

      <section className="site-section is-paper">
        <div className="site-wrap site-split is-center">
          <div>
            <Eyebrow>Not ready yet?</Eyebrow>
            <h2 className="site-h2">New projects by email</h2>
          </div>
          <div>
            <SubscribeBlock id="home" source="home" />
          </div>
        </div>
      </section>
    </>
  );
}

/** "7 loans funded · CHF 300k and EUR 735k lent · 8.1% average interest." (design text, live figures). */
function FiguresNote({ stats }: { stats: PublicStatistics }) {
  const lent = (currency: "CHF" | "EUR") =>
    moneyShortMinor(stats.by_currency.find((row) => row.currency === currency)?.lent_minor ?? 0, currency);
  const average = stats.average_interest_rate_bps === null ? "" : ` · ${pctBps(stats.average_interest_rate_bps)} average interest`;
  return (
    <p className="site-figures-note mt-4">
      {`${stats.loans_funded} loans funded · ${lent("CHF")} and ${lent("EUR")} lent${average}. `}
      <SiteLink href="/statistics">All statistics, including late payments and defaults</SiteLink>
    </p>
  );
}

// ---------------------------------------------------------------------------------------------
// Carousel of the projects funding now (design carousel() + initCarousel()): a scroll-snap
// track (swipe on phones), arrows, dots and the arrow keys. It moves on by itself every six
// seconds and stops while pointed at or focused, after a touch, with the pause button, or when
// the visitor prefers reduced motion.

const AUTOPLAY_MS = 6000;

function prefersReducedMotion() {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function Carousel({ views }: { views: ProjectView[] }) {
  const count = views.length;
  const trackRef = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(() => !prefersReducedMotion());
  // Values the timers read: the slide shown, the slide the arrows or dots asked for (scroll
  // positions on the way do not change the dots), pointer/focus inside, autoplay on.
  const live = useRef({ index: 0, target: null as number | null, hover: false, playing, settle: 0, targetTimer: 0 });
  live.current.playing = playing;
  const shown = Math.min(index, count - 1);

  const go = useCallback(
    (i: number) => {
      const state = live.current;
      const next = ((i % count) + count) % count;
      state.index = next;
      state.target = next;
      window.clearTimeout(state.targetTimer);
      state.targetTimer = window.setTimeout(() => (state.target = null), 2000);
      const track = trackRef.current;
      track?.scrollTo?.({ left: next * track.clientWidth, behavior: "smooth" });
      setIndex(next);
    },
    [count]
  );

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return undefined;
    const state = live.current;
    const onScroll = () => {
      window.clearTimeout(state.settle);
      state.settle = window.setTimeout(() => {
        const i = Math.round(track.scrollLeft / (track.clientWidth || 1));
        if (state.target !== null) {
          if (i === state.target) state.target = null;
          return;
        }
        if (i !== state.index) {
          state.index = i;
          setIndex(i);
        }
      }, 120);
    };
    track.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      track.removeEventListener("scroll", onScroll);
      window.clearTimeout(state.settle);
      window.clearTimeout(state.targetTimer);
    };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const state = live.current;
      if (state.playing && !state.hover && !document.hidden) go(state.index + 1);
    }, AUTOPLAY_MS);
    return () => window.clearInterval(timer);
  }, [go]);

  const hover = (value: boolean) => () => {
    live.current.hover = value;
  };

  return (
    <div
      aria-label="Projects funding now"
      aria-roledescription="carousel"
      className="site-carousel"
      id="site-carousel"
      onBlur={hover(false)}
      onFocus={hover(true)}
      onMouseEnter={hover(true)}
      onMouseLeave={hover(false)}
      onTouchStart={() => setPlaying(false)}
      role="region"
    >
      <div
        aria-label="Use the arrow keys to see the other projects"
        className="site-carousel-track"
        onKeyDown={(event) => {
          if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
            event.preventDefault();
            go(live.current.index + (event.key === "ArrowRight" ? 1 : -1));
          }
        }}
        ref={trackRef}
        tabIndex={0}
      >
        {views.map((view, i) => (
          <HeroCard count={count} index={i} key={view.p.loan_id} view={view} />
        ))}
      </div>
      <div className="site-carousel-nav">
        <div className="site-carousel-dots">
          {views.map((view, i) => (
            <button
              aria-current={i === shown ? "true" : undefined}
              aria-label={`Project ${i + 1}: ${view.p.title}`}
              className={i === shown ? "active" : ""}
              data-index={i}
              key={view.p.loan_id}
              onClick={() => go(i)}
              type="button"
            />
          ))}
        </div>
        <span aria-live="polite" className="site-carousel-count">{`${shown + 1} / ${count}`}</span>
        <div className="site-carousel-btns">
          <button
            aria-label={playing ? "Pause" : "Play"}
            className="site-carousel-btn"
            data-play=""
            onClick={() => setPlaying((value) => !value)}
            type="button"
          >
            <NiIcon name={playing ? "ni-pause" : "ni-play"} />
          </button>
          <button aria-label="Previous project" className="site-carousel-btn" data-dir="-1" onClick={() => go(live.current.index - 1)} type="button">
            <NiIcon name="ni-arrow-left" />
          </button>
          <button aria-label="Next project" className="site-carousel-btn" data-dir="1" onClick={() => go(live.current.index + 1)} type="button">
            <NiIcon name="ni-arrow-right" />
          </button>
        </div>
      </div>
    </div>
  );
}

function HeroCard({ view, index, count }: { view: ProjectView; index: number; count: number }) {
  const { p } = view;
  return (
    <SiteLink
      aria-label={`${index + 1} of ${count}: ${p.title}`}
      aria-roledescription="slide"
      className="site-hero-card bxm-ink bxm-grid"
      href={`/projects/${encodeURIComponent(p.loan_id)}`}
      role="group"
    >
      <div className="site-hero-card-top">
        <span className="site-live">
          <i aria-hidden="true" />
          Funding now
        </span>
        <span>{timeText(view)}</span>
      </div>
      <h2 className="site-hero-card-title">{p.title}</h2>
      <div className="site-hero-card-place">
        <Flag code={p.borrower_country} label={view.countryName} />
        {view.countryName ? `${view.countryName} · ${p.currency}` : p.currency}
      </div>
      <div className="site-hero-rate">
        <strong>{pctBps(p.interest_rate_bps)}</strong>
        <span>interest a year</span>
      </div>
      <div className="site-progress-ink">
        <span style={{ width: `${Math.min(100, view.percent).toFixed(1)}%` }} />
      </div>
      <div className="site-hero-card-progress">
        <span>{`${pct(view.percent, 0)} funded`}</span>
        <span className="site-num">{`${moneyMinor(p.committed_principal_minor, p.currency)} / ${numMinor(p.principal_minor)}`}</span>
      </div>
      <dl className="site-hero-card-facts">
        <div>
          <dt>Term</dt>
          <dd>{p.term_months} months</dd>
        </div>
        <div>
          <dt>Security</dt>
          <dd>{securityShort(p)}</dd>
        </div>
        <div>
          <dt>Minimum now</dt>
          <dd>{moneyMinor(p.minimum_investment_minor ?? 0, p.currency)}</dd>
        </div>
      </dl>
    </SiteLink>
  );
}

// ---------------------------------------------------------------------------------------------
// Example wallet (static, as in the design): CHF and EUR balances and the interest of today
// (daily calculation: invested × rate ÷ 365).

const WALLETS = [
  { currency: "CHF", available: 3200, invested: 9280, rate: 6.9 },
  { currency: "EUR", available: 820, invested: 35040, rate: 8.6 }
];

function WalletPreview() {
  return (
    <div aria-label="Example of an investor wallet" className="site-preview">
      <Eyebrow>Your wallet · example</Eyebrow>
      <div className="site-wallets">
        {WALLETS.map((wallet) => (
          <div className="site-wallet" key={wallet.currency}>
            <div className="site-wallet-head">
              <CurrencyFlag currency={wallet.currency} />
              <strong>{wallet.currency} wallet</strong>
            </div>
            <div className="site-wallet-amount">{`${wallet.currency} ${num(wallet.available + wallet.invested)}`}</div>
            <dl>
              <div>
                <dt>Available</dt>
                <dd>{num(wallet.available)}</dd>
              </div>
              <div>
                <dt>Invested</dt>
                <dd>{num(wallet.invested)}</dd>
              </div>
              <div>
                <dt>Interest today</dt>
                <dd className="site-wallet-today">+{num(round2((wallet.invested * wallet.rate) / 100 / DAY_BASIS))}</dd>
              </div>
            </dl>
          </div>
        ))}
      </div>
      <table className="site-table mt-4">
        <thead>
          <tr>
            <th>Next payments</th>
            <th className="is-num">Rate</th>
            <th>Due</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Logistics hall</td>
            <td className="is-num">6.2%</td>
            <td>1 Oct</td>
          </tr>
          <tr>
            <td>Stock refinancing</td>
            <td className="is-num">8.0%</td>
            <td>5 Oct</td>
          </tr>
          <tr>
            <td>Farm machinery</td>
            <td className="is-num">9.0%</td>
            <td>
              <span className="bxm-status-late">Late 5 days</span>
            </td>
          </tr>
          <tr>
            <td>Bakery chain · no. 6</td>
            <td className="is-num">6.0%</td>
            <td>
              <span className="bxm-success-text">Paid on time</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
