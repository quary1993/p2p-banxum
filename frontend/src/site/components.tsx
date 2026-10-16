// IP of Webby-Soft SRL.
/*
 * Shared blocks of the public site, ported 1:1 from the design (shell.js and core.js): same
 * markup and classes, so the generated site.css styles them. Pure helpers live in projects.ts
 * (statusOf, timeText, securityShort, repaymentShort, recordTag, projectView), format.ts and
 * links.ts (siteHtml, useStaticLinkClick); hooks and contexts in context.ts (useSiteNav,
 * useSiteToast, useSiteTitle); the cookie choice in cookies.ts. Keeping non-components out of
 * this file keeps React Fast Refresh working.
 */
import { Fragment, useState, type AnchorHTMLAttributes, type FormEvent, type ReactNode } from "react";

import { setNewsletterSubscribed, useNewsletterSubscribed, useSiteNav, useSiteToast } from "./context";
import type { FaqItem } from "./content";
import { errorDetail, fieldErrors, useNewsletterSubscribe, type NewsletterSource } from "./data";
import { money, moneyMinor, pct, pctBps, SITE_MINIMUM } from "./format";
import { isPlainLeftClick, siteHtml, useStaticLinkClick } from "./links";
import { placeLine, securityShort, statusOf, timeText, type ProjectView } from "./projects";

// ---------------------------------------------------------------------------------------------
// Links

type SiteLinkProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & { href: string };

/** <a href="/path"> that navigates in the app on a plain left click (design: href="#/path"). */
export function SiteLink({ href, onClick, children, ...rest }: SiteLinkProps) {
  const { navigate } = useSiteNav();
  return (
    <a
      {...rest}
      href={href}
      onClick={(event) => {
        onClick?.(event);
        if (!isPlainLeftClick(event) || rest.target) return;
        event.preventDefault();
        navigate(href);
      }}
    >
      {children}
    </a>
  );
}
type SiteHtmlProps = { html: string; className?: string; as?: "div" | "p" | "span" };

/**
 * Trusted static HTML from content.ts (never API or user data), with the design's internal
 * links opened in the app by a delegated click handler.
 */
export function SiteHtml({ html, className, as: Tag = "div" }: SiteHtmlProps) {
  const onClick = useStaticLinkClick();
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: siteHtml(html) }} onClick={onClick} />;
}

// ---------------------------------------------------------------------------------------------
// Small blocks

/** Nioicon glyph: <em class="icon ni ni-x">. Only the glyphs in assets/nioicon-site.woff2 exist. */
export function NiIcon({ name }: { name: string }) {
  return <em className={`icon ni ${name}`} />;
}

/** The design's bxm-tag ("Open", "Risk B", "Late 12 days"). */
export function Tag({ label, cls }: { label: string; cls?: string }) {
  return <span className={`bxm-tag ${cls || ""}`}>{label}</span>;
}

export function Progress({ percent }: { percent: number }) {
  return (
    <div aria-valuemax={100} aria-valuemin={0} aria-valuenow={Math.round(percent)} className="bxm-progress" role="progressbar">
      <span style={{ width: `${Math.min(100, percent).toFixed(1)}%` }} />
    </div>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <span className="site-eyebrow">{children}</span>;
}

export function RiskLine() {
  return (
    <p className="site-risk-line">
      Lending to companies puts your capital at risk. Read the <SiteLink href="/legal/risk">risk information</SiteLink>.
    </p>
  );
}

export type Crumb = { label: string; href?: string };

/** Page head of the inner pages: crumbs, eyebrow, title, lead and actions. */
export function PageHead({
  crumbs,
  eyebrow,
  title,
  lead,
  actions
}: {
  crumbs?: Crumb[];
  eyebrow?: ReactNode;
  title: ReactNode;
  lead?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="site-page-head">
      <div className="site-wrap">
        {crumbs ? (
          <nav aria-label="Breadcrumb" className="site-crumbs">
            {crumbs.map((crumb, index) =>
              crumb.href ? (
                <Fragment key={index}>
                  <SiteLink href={crumb.href}>{crumb.label}</SiteLink>
                  <span>/</span>
                </Fragment>
              ) : (
                <span key={index}>{crumb.label}</span>
              )
            )}
          </nav>
        ) : null}
        {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
        <h1 className="site-h1">{title}</h1>
        {lead ? <p className="site-lead">{lead}</p> : null}
        {actions ? <div className="site-actions mt-4">{actions}</div> : null}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------------------------
// Flags: drawn inline (shell.js FLAGS). CHF with the Swiss flag, EUR with the EU flag.

const EU_STARS = Array.from({ length: 12 }, (_, i) => {
  const a = (i * Math.PI) / 6;
  return { cx: (10 + 4.2 * Math.sin(a)).toFixed(2), cy: (7 - 4.2 * Math.cos(a)).toFixed(2) };
});

const FLAGS: Record<string, () => ReactNode> = {
  CH: () => (
    <svg height="14" viewBox="0 0 14 14" width="14">
      <rect fill="#DA291C" height="14" width="14" />
      <rect fill="#fff" height="8.4" width="2.4" x="5.8" y="2.8" />
      <rect fill="#fff" height="2.4" width="8.4" x="2.8" y="5.8" />
    </svg>
  ),
  EU: () => (
    <svg height="14" viewBox="0 0 20 14" width="20">
      <rect fill="#003399" height="14" width="20" />
      {EU_STARS.map((star, index) => (
        <circle cx={star.cx} cy={star.cy} fill="#FFCC00" key={index} r="0.62" />
      ))}
    </svg>
  ),
  DE: () => (
    <svg height="14" viewBox="0 0 20 14" width="20">
      <rect fill="#000" height="4.67" width="20" />
      <rect fill="#DD0000" height="4.67" width="20" y="4.67" />
      <rect fill="#FFCE00" height="4.67" width="20" y="9.33" />
    </svg>
  ),
  AT: () => (
    <svg height="14" viewBox="0 0 20 14" width="20">
      <rect fill="#ED2939" height="14" width="20" />
      <rect fill="#fff" height="4.67" width="20" y="4.67" />
    </svg>
  ),
  RO: () => (
    <svg height="14" viewBox="0 0 20 14" width="20">
      <rect fill="#002B7F" height="14" width="6.67" />
      <rect fill="#FCD116" height="14" width="6.67" x="6.67" />
      <rect fill="#CE1126" height="14" width="6.67" x="13.33" />
    </svg>
  ),
  IT: () => (
    <svg height="14" viewBox="0 0 20 14" width="20">
      <rect fill="#009246" height="14" width="6.67" />
      <rect fill="#fff" height="14" width="6.67" x="6.67" />
      <rect fill="#CE2B37" height="14" width="6.67" x="13.33" />
    </svg>
  )
};

/** Flag of a country code (CH, EU, DE, AT, RO, IT); nothing for other codes, like the design. */
export function Flag({ code, label }: { code: string; label?: string }) {
  const draw = FLAGS[code];
  if (!draw) return null;
  return (
    <span aria-label={label || code} className="site-flag" role="img">
      {draw()}
    </span>
  );
}

export function CurrencyFlag({ currency }: { currency: string }) {
  return currency === "CHF" ? <Flag code="CH" label="Swiss franc" /> : <Flag code="EU" label="Euro" />;
}

// ---------------------------------------------------------------------------------------------
// Projects

/** Project card of the grids (design projectCard). */
export function ProjectCard({ view }: { view: ProjectView }) {
  const { p, isOpen, isSoon } = view;
  const st = statusOf(view);
  const minimum = isOpen
    ? moneyMinor(p.minimum_investment_minor ?? 0, p.currency)
    : isSoon
      ? p.minimum_investment_minor !== null
        ? moneyMinor(p.minimum_investment_minor, p.currency)
        : money(SITE_MINIMUM, p.currency)
      : "–";
  return (
    <SiteLink className={`site-project${isOpen ? " is-open" : ""}`} href={`/projects/${encodeURIComponent(p.loan_id)}`}>
      <div className="site-project-top">
        <div className="site-project-tags">
          <Tag cls={st.cls} label={st.label} /> <Tag cls="is-muted" label={`Risk ${p.risk_rating}`} />
        </div>
        <span className="site-project-country">
          <Flag code={p.borrower_country} label={view.countryName} />
          {p.borrower_country ? `${p.borrower_country} · ${p.currency}` : p.currency}
        </span>
      </div>
      <h3 className="site-project-title">{p.title}</h3>
      <div className="site-project-place">{placeLine(view)}</div>
      <div className="site-project-rate">
        <strong>{pctBps(p.interest_rate_bps)}</strong>
        <span>interest a year</span>
      </div>
      <Progress percent={view.percent} />
      <div className="site-project-progress">
        <span>
          {pct(view.percent, 0)} of {moneyMinor(p.principal_minor, p.currency)}
        </span>
        <span>{timeText(view)}</span>
      </div>
      <dl className="site-project-facts">
        <div>
          <dt>Term</dt>
          <dd>{p.term_months} months</dd>
        </div>
        <div>
          <dt>{isOpen ? "Minimum now" : "Minimum"}</dt>
          <dd>{minimum}</dd>
        </div>
        <div>
          <dt>Security</dt>
          <dd>{securityShort(p)}</dd>
        </div>
        <div>
          <dt>Investors</dt>
          <dd>{p.investors_count}</dd>
        </div>
      </dl>
    </SiteLink>
  );
}

/** Calm stand-in for a project grid: loading, failed (with a retry link) or empty. */
export function ProjectsBox({ children }: { children: ReactNode }) {
  return (
    <div className="site-box">
      <p className="mb-0">{children}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Questions

/** Questions as <details>; answers are static HTML from content.ts. */
export function FaqList({ items, openFirst = false }: { items: FaqItem[]; openFirst?: boolean }) {
  const onClick = useStaticLinkClick();
  return (
    <div className="site-faq" onClick={onClick}>
      {items.map((item, index) => (
        <details className="site-faq-item" key={item.q} open={openFirst && index === 0 ? true : undefined}>
          <summary>{item.q}</summary>
          <div className="site-faq-answer" dangerouslySetInnerHTML={{ __html: siteHtml(item.a) }} />
        </details>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------------------------
// Ink band "How you start": Home uses the default title "Choose. Build. Follow."; other pages
// can give their own eyebrow and title, the steps stay the same.

export function CtaBand({ eyebrow, title }: { eyebrow?: string; title?: string }) {
  return (
    <section className="site-cta-band bxm-ink" id="start">
      <div className="site-wrap">
        <Eyebrow>{eyebrow || "How you start"}</Eyebrow>
        <h2 className={title ? "site-h1" : "site-display"} style={{ maxWidth: 880 }}>
          {title || "Choose. Build. Follow."}
        </h2>
        <div className="site-cta-steps">
          <div>
            <small>01</small>
            <strong>Choose</strong>
            <span>
              Open your account in 2 minutes, with an online identity check. Then choose the projects you like: company,
              rate, term and security on one page.
            </span>
          </div>
          <div>
            <small>02</small>
            <strong>Build</strong>
            <span>
              Add CHF or EUR to your own segregated wallet and invest from 1,000 in each loan you pick. Spread your money
              across companies, sectors and countries.
            </span>
          </div>
          <div>
            <small>03</small>
            <strong>Follow</strong>
            <span>
              See every payment in your account. Interest counts every day, and repayments are credited to your balance,
              to invest again or withdraw. No fees.
            </span>
          </div>
        </div>
        <div className="site-actions">
          <SiteLink className="btn btn-lg btn-site-white" href="/register">
            Open account
          </SiteLink>
          <SiteLink className="btn btn-lg btn-site-ghost" href="/projects">
            See the projects
          </SiteLink>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------------------------
// Newsletter: new projects by email, with double opt-in (useNewsletterSubscribe).

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function SubscribeBlock({
  id = "main",
  button = "Get new projects",
  source = "other"
}: {
  id?: string;
  button?: string;
  source?: NewsletterSource;
}) {
  const subscribed = useNewsletterSubscribed();
  const toast = useSiteToast();
  const subscribe = useNewsletterSubscribe();
  const [email, setEmail] = useState("");
  const [invalid, setInvalid] = useState(false);
  // The design adds the message once and leaves it in place; CSS shows it only next to .is-invalid.
  const [feedback, setFeedback] = useState<string | null>(null);
  const inputId = `site-sub-${id}`;

  if (subscribed) {
    return (
      <div className="site-note-ok">
        <strong>Almost done.</strong> We sent a confirmation link to {subscribed}. New projects arrive once you confirm.{" "}
        <a
          href="#"
          onClick={(event) => {
            event.preventDefault();
            subscribe.reset();
            setEmail("");
            setNewsletterSubscribed(null);
          }}
        >
          Use another address
        </a>
      </div>
    );
  }

  const showError = (message: string) => {
    setInvalid(true);
    setFeedback(message);
    document.getElementById(inputId)?.focus();
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (subscribe.isPending) return;
    const value = email.trim();
    if (!EMAIL_PATTERN.test(value)) {
      showError("Enter a valid email address.");
      return;
    }
    subscribe.mutate(
      { email: value, source },
      {
        onSuccess: () => {
          setNewsletterSubscribed(value);
          toast("Check your inbox to confirm.");
        },
        onError: (error) => {
          if (fieldErrors(error).email) showError("Enter a valid email address.");
          else toast(errorDetail(error, "Something went wrong. Please try again."), "ni-alert-circle");
        }
      }
    );
  };

  return (
    <>
      <form className="site-subscribe" noValidate onSubmit={onSubmit}>
        <label className="visually-hidden" htmlFor={inputId}>
          Email address
        </label>
        <input
          autoComplete="email"
          className={`form-control${invalid ? " is-invalid" : ""}`}
          id={inputId}
          onChange={(event) => {
            setEmail(event.target.value);
            setInvalid(false);
          }}
          placeholder="Your email address"
          required
          type="email"
          value={email}
        />
        {feedback ? <div className="invalid-feedback w-100 order-last">{feedback}</div> : null}
        <button className="btn btn-lg btn-primary" disabled={subscribe.isPending} type="submit">
          {button}
        </button>
      </form>
      <p className="site-small mt-2 mb-0">
        Once or twice a month, when new projects open. You can unsubscribe with one click.{" "}
        <SiteLink href="/legal/privacy">Privacy</SiteLink>
      </p>
    </>
  );
}
