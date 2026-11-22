// IP of Webby-Soft SRL.
/*
 * U33 legal pages (design terms.html, privacy.html, risks.html): the page hero, "On this page"
 * with the numbered sections, the document card and the links below. The texts are the real
 * ones, never the design's placeholders:
 * - /legal/terms and /legal/registration: the published "registration" template (the Terms and
 *   Conditions users accept); the outline of content.ts while none is published.
 * - /legal/risk and /legal/risk-disclosure: the published "risk_disclosure" template; the risk
 *   text of content.ts while none is published. The risk page keeps the design's risk hero.
 * - /legal/privacy, /legal/cookies, /legal/imprint, /legal/complaints: content.ts.
 * - /legal/primary-market-investment, /legal/secondary-market-listing,
 *   /legal/secondary-market-purchase: the published template.
 * Preview mode (fixtures) never asks the backend and shows the content.ts texts. Any other
 * /legal/<x> is the 404 (SitePages checks isPublicLegalDocument).
 */
import { useState, type MouseEvent, type ReactNode } from "react";

import type { CategoryEnum, PublicDocumentTemplateVersion } from "../../../api/generated/banxumApi";
import { t as tr, useT } from "../../../i18n";
import { SiteHtml } from "../../components";
import { siteCompany, type SiteLegalDoc } from "../../content";
import { useSiteTitle, useSiteToast } from "../../context";
import { errorDetail, isNotFound } from "../../data";
import { date, dateKey } from "../../format";
import {
  downloadLegalTemplatePdf,
  legalDocumentSections,
  legalSupportEmail,
  legalTemplatesLive,
  legalTemplateTitles,
  renderLegalBlocks,
  useLegalTemplate
} from "../../legalDocuments";
import type { SitePageProps } from "../../SitePages";
import { legalRoute } from "../legalRoutes";
import { HomeSectionLink, Ni, PublicLink } from "../ui";

/** The U33 names of the documents (design footer and legal pages). */
const U33_TITLES: Record<string, string> = {
  terms: "Terms & conditions",
  privacy: "Privacy policy",
  risk: "Risk information",
  cookies: "Cookie policy",
  imprint: "Imprint",
  complaints: "Complaints"
};

const LEADS: Record<string, string> = {
  terms: "The framework for using Banxum.",
  privacy: "Clarity about your personal information.",
  cookies: "How the site uses cookies, and your choice.",
  imprint: "The company that operates Banxum.",
  complaints: "How to tell us when something went wrong."
};

/** The document order of "Other documents". */
const DOCUMENT_ORDER = ["terms", "privacy", "risk", "cookies", "complaints", "imprint"];

type Section = { heading: string; body: ReactNode };
type DocumentView = {
  status: ReactNode;
  intro: ReactNode;
  sections: Section[];
  /** A message instead of the sections (loading, not published, error). */
  message?: ReactNode;
};

export function Legal({ params }: SitePageProps) {
  const t = useT();
  const toast = useSiteToast();
  const route = legalRoute(params.doc ?? "");
  const template = useLegalTemplate(route?.category ?? null);
  const [downloading, setDownloading] = useState(false);
  const published = route?.category && legalTemplatesLive ? template.data : undefined;
  const designId = route?.design?.id ?? null;
  const title = route
    ? designId
      ? t(U33_TITLES[designId] ?? route.design?.title ?? "")
      : (published?.title ?? t(legalTemplateTitles[route.category as CategoryEnum]))
    : "";
  useSiteTitle(title || null);
  if (!route) return null;
  const { design, category } = route;

  const onDownload = async (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    if (downloading || !category) return;
    setDownloading(true);
    try {
      await downloadLegalTemplatePdf(category);
    } catch (error) {
      toast(errorDetail(error, t("The PDF could not be downloaded. Please try again.")), "ni-alert-circle");
    } finally {
      setDownloading(false);
    }
  };

  let view: DocumentView;
  if (category && legalTemplatesLive && !(design && isNotFound(template.error))) {
    if (published) view = templateView(published, downloading, onDownload);
    else if (template.isPending) view = { status: null, intro: null, sections: [], message: <p>{t("Loading the current published document…")}</p> };
    else if (isNotFound(template.error))
      view = {
        status: <span className="legal-status">{t("Being prepared")}</span>,
        intro: null,
        sections: [],
        message: (
          <p>
            {t("The current version of this document is being prepared and will appear on this page once it is published.")}{" "}
            {t("Questions in the meantime:")} <a href={`mailto:${legalSupportEmail}`}>{legalSupportEmail}</a>.
          </p>
        )
      };
    else
      view = {
        status: null,
        intro: null,
        sections: [],
        message: (
          <p>
            {t("The current published document could not be loaded.")}{" "}
            <a
              href="#"
              onClick={(event) => {
                event.preventDefault();
                void template.refetch();
              }}
            >
              {t("Retry")}
            </a>
            {", "}
            {t("or contact")} <a href={`mailto:${legalSupportEmail}`}>{legalSupportEmail}</a>.
          </p>
        )
      };
  } else if (design) {
    view = designView(design);
  } else {
    view = {
      status: null,
      intro: null,
      sections: [],
      message: <p>{t("Preview mode: the text of this document loads from the published server template.")}</p>
    };
  }

  const isRisk = designId === "risk";
  const prefix = designId ?? category ?? "legal";
  const sectionId = (index: number) => `${prefix}-section-${index + 1}`;
  const related =
    designId === "terms"
      ? { href: "/legal/risk", label: t("Read risk information") }
      : designId === "risk" || designId === "privacy"
        ? { href: "/legal/terms", label: t("Terms & conditions") }
        : { href: "/legal/risk", label: t("Read risk information") };
  const others = DOCUMENT_ORDER.filter((id) => id !== designId);

  return (
    <div className={`content-shell legal-view${isRisk ? " risk-view" : ""}`}>
      {isRisk ? (
        <section aria-labelledby="legal-title" className="page-hero risk-hero">
          <div>
            <p className="page-kicker">{t("RISK INFORMATION")}</p>
            <h1 className="page-title" id="legal-title">
              {t("Understand the risks.")}
              <br />{" "}
              {t("Make your own decision.")}
            </h1>
            <p className="page-lead">
              {t("Business lending carries risk.")}
              <br />{" "}
              {t("Know what can affect your capital and repayments.")}
            </p>
          </div>
          <aside aria-label={t("Capital at risk")} className="paper-panel capital-risk">
            <span className="capital-risk-label">{t("CAPITAL AT RISK")}</span>
            <p>
              {t("You could lose")}
              <br />{" "}
              {t("part or all of")}
              <br />{" "}
              {t("your investment.")}
            </p>
            <span className="capital-risk-note">{t("Collateral does not guarantee repayment.")}</span>
          </aside>
        </section>
      ) : (
        <section aria-labelledby="legal-title" className="page-hero legal-hero">
          <p className="page-kicker">{t("LEGAL INFORMATION")}</p>
          <h1 className="page-title" id="legal-title">
            {title}
          </h1>
          {designId && LEADS[designId] ? <p className="page-lead">{t(LEADS[designId])}</p> : null}
          {view.status ? <div className="legal-draft-note">{view.status}</div> : null}
        </section>
      )}
      {isRisk && view.status ? <div className="legal-draft-note bxp-risk-status">{view.status}</div> : null}
      <div className="legal-document-layout">
        <aside className="legal-contents">
          {view.sections.length ? (
            <>
              <p className="page-kicker">{t("ON THIS PAGE")}</p>
              <nav aria-label={t("{title} contents", { title })} className="legal-jump-nav">
                {view.sections.map((section, index) => (
                  <a
                    href={`#${sectionId(index)}`}
                    key={sectionId(index)}
                    onClick={(event) => {
                      event.preventDefault();
                      document.getElementById(sectionId(index))?.scrollIntoView({ behavior: "smooth", block: "start" });
                    }}
                  >
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    {section.heading}
                  </a>
                ))}
              </nav>
            </>
          ) : null}
          <PublicLink className="legal-related" href={related.href}>
            {related.label} <Ni glyph="arrow" />
          </PublicLink>
          <div className="bxp-legal-documents">
            <p className="page-kicker">{t("OTHER DOCUMENTS")}</p>
            <ul aria-label={t("Legal pages")}>
              {others.map((id) => (
                <li key={id}>
                  <PublicLink href={`/legal/${id}`}>{t(U33_TITLES[id])}</PublicLink>
                </li>
              ))}
            </ul>
          </div>
        </aside>
        <div aria-label={title} className="legal-outline bxp-legal-document">
          {view.message ? (
            <div className="bxp-legal-message">{view.message}</div>
          ) : (
            <>
              {view.intro ? <div className="legal-outline-intro bxp-legal-intro">{view.intro}</div> : null}
              {view.sections.map((section, index) => (
                <section className="legal-outline-section" id={sectionId(index)} key={sectionId(index)}>
                  <span aria-hidden="true" className="legal-section-number">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div>
                    <h2>{section.heading}</h2>
                    {section.body}
                  </div>
                </section>
              ))}
            </>
          )}
        </div>
      </div>
      {isRisk ? <RiskReview /> : null}
      <div className="legal-bottom-links">
        {isRisk ? (
          <>
            <p>{t("Have a question before you decide?")}</p>
            <PublicLink className="text-link" href="/contact">
              {t("Request a conversation")} <Ni glyph="arrow" />
            </PublicLink>
          </>
        ) : (
          <>
            <PublicLink className="text-link" href={designId === "privacy" ? "/legal/cookies" : designId === "terms" ? "/legal/privacy" : "/legal/terms"}>
              {designId === "privacy" ? t("Cookie policy") : designId === "terms" ? t("Privacy policy") : t("Terms & conditions")} <Ni glyph="arrow" />
            </PublicLink>
            <PublicLink className="text-link" href="/contact">
              {t("Contact Banxum")} <Ni glyph="arrow" />
            </PublicLink>
          </>
        )}
      </div>
    </div>
  );
}

/** The design risk page's "Before you invest" band. */
function RiskReview() {
  const t = useT();
  return (
    <section aria-labelledby="review-risk-title" className="risk-review section-gap">
      <div>
        <p className="page-kicker">{t("BEFORE YOU INVEST")}</p>
        <h2 className="section-title" id="review-risk-title">
          {t("Review the full picture.")}
        </h2>
        <p className="body-copy muted">{t("The company’s identity and full credit file become available after your identity has been verified.")}</p>
        <HomeSectionLink className="text-link" section="opportunities">
          {t("Explore opportunities")} <Ni glyph="arrow" />
        </HomeSectionLink>
      </div>
      <ul className="risk-review-list">
        <li>
          <span>{t("Business & repayment")}</span>
          <small>{t("How the loan is intended to be repaid.")}</small>
        </li>
        <li>
          <span>{t("Security & valuation")}</span>
          <small>{t("The asset, its stated value and the rights attached to it.")}</small>
        </li>
        <li>
          <span>{t("Loan documents")}</span>
          <small>{t("The terms and obligations of the individual opportunity.")}</small>
        </li>
      </ul>
    </section>
  );
}

function onPrint(event: MouseEvent<HTMLAnchorElement>) {
  event.preventDefault();
  window.print();
}

/** A published backend template: version, publication date, Print, Download PDF and its sections. */
function templateView(doc: PublicDocumentTemplateVersion, downloading: boolean, onDownload: (event: MouseEvent<HTMLAnchorElement>) => void): DocumentView {
  const { intro, sections } = legalDocumentSections(doc.body);
  const labels = Array.isArray(doc.checkbox_labels) ? (doc.checkbox_labels as unknown[]).map(String) : [];
  const all: Section[] = sections.map((section) => ({ heading: section.heading, body: renderLegalBlocks(section.blocks) }));
  if (labels.length) {
    all.push({
      heading: tr("You will be asked to confirm"),
      body: (
        <ul>
          {labels.map((label) => (
            <li key={label}>{label}</li>
          ))}
        </ul>
      )
    });
  }
  return {
    status: (
      <>
        <span className="legal-status">{tr("Version {version}", { version: doc.version_number })}</span>
        <p className="bxp-legal-meta">
          {doc.published_at ? <span>{tr("Valid from {date}", { date: date(dateKey(doc.published_at)) })}</span> : null}
          <a href="#" onClick={onPrint}>
            {tr("Print")}
          </a>
          <a aria-disabled={downloading || undefined} href="#" onClick={onDownload}>
            {downloading ? tr("Preparing PDF…") : tr("Download PDF")}
          </a>
        </p>
      </>
    ),
    intro: intro.length ? renderLegalBlocks(intro) : null,
    sections: all
  };
}

/** A content.ts document: its text (split at its headings), its outline or the imprint. */
function designView(doc: SiteLegalDoc): DocumentView {
  const meta =
    doc.version && doc.date ? (
      <>
        <span className="legal-status">{tr("Version {version}", { version: doc.version })}</span>
        <p className="bxp-legal-meta">
          <span>{tr("Valid from {date}", { date: date(doc.date) })}</span>
          <a href="#" onClick={onPrint}>
            {tr("Print")}
          </a>
        </p>
      </>
    ) : null;
  if (doc.imprint) return { status: null, intro: null, sections: imprintSections() };
  if (doc.body) {
    const parts = doc.body.split(/<h2>(.*?)<\/h2>/);
    const intro = parts[0].trim();
    const sections: Section[] = [];
    for (let i = 1; i < parts.length; i += 2) {
      sections.push({ heading: parts[i], body: <SiteHtml html={parts[i + 1] ?? ""} /> });
    }
    return { status: meta, intro: intro ? <SiteHtml html={intro} /> : null, sections };
  }
  return {
    status: (
      <>
        {meta}
        <p className="bxp-legal-outline-note">{tr("Outline. The full text follows from the lawyers.")}</p>
      </>
    ),
    intro: <p>{tr("What the final document will cover")}</p>,
    sections: (doc.outline ?? []).map((heading) => ({ heading, body: null }))
  };
}

/** The imprint: company details, the bank and the closing paragraph (content.ts siteCompany). */
function imprintSections(): Section[] {
  const co = siteCompany;
  const rows = (items: [string, ReactNode][]) => (
    <dl className="bxp-kv">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
  return [
    {
      heading: tr("Operator"),
      body: rows([
        [tr("Operator of banxum.com"), co.name],
        [
          tr("Address"),
          <>
            {co.street}
            <br />{" "}
            {co.city}
          </>
        ],
        [tr("UID and VAT"), co.uid],
        [tr("LEI"), co.lei],
        [tr("Commercial register"), tr("Canton of Bern")],
        [tr("Board of directors"), tr("To be added")],
        [tr("Share capital"), co.capital],
        [tr("Self-regulatory organisation"), tr("VQF, member number to be added")],
        [tr("Ombudsman"), tr("FINOS, Finanzombudsstelle Schweiz")],
        [tr("Email"), <a href={`mailto:${co.email}`}>{co.email}</a>]
      ])
    },
    {
      heading: tr("Bank"),
      body: rows([
        [tr("Bank"), co.bank.name],
        [tr("IBAN CHF"), co.bank.CHF],
        [tr("IBAN EUR"), co.bank.EUR],
        [tr("SWIFT"), co.bank.swift]
      ])
    },
    {
      // The closing paragraph as the October imprint (owner decision 2026-10-15: unchanged).
      heading: tr("Notice"),
      body: (
        <p>
          {tr(
            "Banxum® is a registered trademark. The Banxum platform is owned and operated by {company}, a Swiss financial company. The contents of this site are information, not investment advice. The sample figures of this prototype are invented.",
            { company: co.name }
          )}
        </p>
      )
    }
  ];
}

