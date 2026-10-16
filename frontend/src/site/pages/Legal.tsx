// IP of Webby-Soft SRL.
/*
 * Legal pages (design: pages_more.js legal() and imprint()): side navigation with the six design
 * documents, the document meta line and the body in .site-prose.
 *
 * The backend's published templates live at the same addresses as before (the investor flows
 * link to them, see App.tsx LegalDocLink):
 * - /legal/terms and /legal/registration: the published "registration" template (the Terms and
 *   Conditions users accept), "Terms of use" active; the design outline while none is published.
 * - /legal/risk and /legal/risk-disclosure: the published "risk_disclosure" template, "Risk
 *   information" active; the design text while none is published.
 * - /legal/primary-market-investment, /legal/secondary-market-listing,
 *   /legal/secondary-market-purchase: the published template, no active navigation item.
 * Preview mode (fixtures) never asks the backend and shows the design texts. Every other
 * /legal/<x> is the design's 404.
 */
import { useState, type MouseEvent, type ReactNode } from "react";

import type { CategoryEnum, PublicDocumentTemplateVersion } from "../../api/generated/banxumApi";
import { PageHead, SiteHtml, SiteLink } from "../components";
import { siteCompany, siteLegal, type SiteLegalDoc } from "../content";
import { useSiteTitle, useSiteToast } from "../context";
import { errorDetail, isNotFound } from "../data";
import { date, dateKey } from "../format";
import {
  downloadLegalTemplatePdf,
  legalSupportEmail,
  legalTemplateCategory,
  legalTemplatesLive,
  legalTemplateTitles,
  renderLegalBody,
  useLegalTemplate
} from "../legalDocuments";
import type { SitePageProps } from "../SitePages";
import { NotFound } from "./NotFound";

/** Design documents whose text is a published backend template once there is one. */
const DESIGN_TEMPLATES: Record<string, CategoryEnum> = { terms: "registration", risk: "risk_disclosure" };
const TEMPLATE_DESIGNS: Partial<Record<CategoryEnum, string>> = { registration: "terms", risk_disclosure: "risk" };

type LegalRoute = { design: SiteLegalDoc | null; category: CategoryEnum | null };

/** The design document and/or backend category of /legal/<slug>; null for an unknown address. */
function legalRoute(slug: string): LegalRoute | null {
  const design = siteLegal.find((item) => item.id === slug);
  if (design) return { design, category: DESIGN_TEMPLATES[design.id] ?? null };
  const category = legalTemplateCategory(slug);
  if (!category) return null;
  const designId = TEMPLATE_DESIGNS[category];
  return { design: siteLegal.find((item) => item.id === designId) ?? null, category };
}

function onPrint(event: MouseEvent<HTMLAnchorElement>) {
  event.preventDefault();
  window.print();
}

export function Legal({ params }: SitePageProps) {
  const route = legalRoute(params.doc ?? "");
  const template = useLegalTemplate(route?.category ?? null);
  const published = route?.category && legalTemplatesLive ? template.data : undefined;
  const title = route
    ? route.design
      ? route.design.title
      : (published?.title ?? legalTemplateTitles[route.category as CategoryEnum])
    : null;
  useSiteTitle(title ?? "Not found");
  if (!route || !title) return <NotFound />;
  const { design, category } = route;

  let body: ReactNode;
  if (category && legalTemplatesLive && !(design && isNotFound(template.error))) {
    if (published) body = <TemplateBody category={category} doc={published} />;
    else if (template.isPending) body = <p>Loading the current published document…</p>;
    else if (isNotFound(template.error))
      body = (
        <div className="site-callout">
          The current version of this document is being prepared and will appear on this page once it is published.
          Questions in the meantime: <a href={`mailto:${legalSupportEmail}`}>{legalSupportEmail}</a>.
        </div>
      );
    else
      body = (
        <div className="site-callout">
          The current published document could not be loaded.{" "}
          <a
            href="#"
            onClick={(event) => {
              event.preventDefault();
              void template.refetch();
            }}
          >
            Retry
          </a>
          , or contact <a href={`mailto:${legalSupportEmail}`}>{legalSupportEmail}</a>.
        </div>
      );
  } else if (design) {
    body = <DesignBody doc={design} />;
  } else {
    body = (
      <div className="site-callout">Preview mode: the text of this document loads from the published server template.</div>
    );
  }

  return (
    <>
      <PageHead eyebrow="Legal" title={title} />
      <section className="site-section no-rule" style={{ paddingTop: 0 }}>
        <div className="site-wrap site-sidebar-layout">
          <ul aria-label="Legal pages" className="site-side-nav">
            {siteLegal.map((item) => (
              <li key={item.id}>
                <SiteLink
                  aria-current={item.id === design?.id ? "page" : undefined}
                  className={item.id === design?.id ? "active" : ""}
                  href={`/legal/${item.id}`}
                >
                  {item.title}
                </SiteLink>
              </li>
            ))}
          </ul>
          <div className="site-prose">{body}</div>
        </div>
      </section>
    </>
  );
}

/** A design document: meta line (version, date, Print) and the design text, outline or imprint. */
function DesignBody({ doc }: { doc: SiteLegalDoc }) {
  return (
    <>
      {doc.version && doc.date ? (
        <div className="site-doc-meta">
          <span>Version {doc.version}</span>
          <span>Valid from {date(doc.date)}</span>
          <a href="#" onClick={onPrint}>
            Print
          </a>
        </div>
      ) : null}
      {doc.imprint ? (
        <Imprint />
      ) : doc.body ? (
        <SiteHtml html={doc.body} />
      ) : (
        <>
          <div className="site-callout">Outline of the {doc.title.toLowerCase()}. The text follows from the lawyers.</div>
          <ol>
            {(doc.outline ?? []).map((heading) => (
              <li key={heading}>
                <strong>{heading}</strong>
              </li>
            ))}
          </ol>
        </>
      )}
    </>
  );
}

/** A published backend template: meta line (version, publication date, Print, Download PDF) and the text. */
function TemplateBody({ category, doc }: { category: CategoryEnum; doc: PublicDocumentTemplateVersion }) {
  const toast = useSiteToast();
  const [downloading, setDownloading] = useState(false);
  const labels = Array.isArray(doc.checkbox_labels) ? (doc.checkbox_labels as unknown[]).map(String) : [];

  const onDownload = async (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    if (downloading) return;
    setDownloading(true);
    try {
      await downloadLegalTemplatePdf(category);
    } catch (error) {
      toast(errorDetail(error, "The PDF could not be downloaded. Please try again."), "ni-alert-circle");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <>
      <div className="site-doc-meta">
        <span>Version {doc.version_number}</span>
        {doc.published_at ? <span>Valid from {date(dateKey(doc.published_at))}</span> : null}
        <a href="#" onClick={onPrint}>
          Print
        </a>
        <a aria-disabled={downloading || undefined} href="#" onClick={onDownload}>
          {downloading ? "Preparing PDF…" : "Download PDF"}
        </a>
      </div>
      {renderLegalBody(doc.body)}
      {labels.length > 0 ? (
        <>
          <h2>You will be asked to confirm</h2>
          <ul>
            {labels.map((label) => (
              <li key={label}>{label}</li>
            ))}
          </ul>
        </>
      ) : null}
    </>
  );
}

/** Design imprint(): company details, the bank and the closing paragraph, exactly as the design. */
function Imprint() {
  const co = siteCompany;
  return (
    <>
      <dl className="site-kv mb-4">
        <div>
          <dt>Operator of banxum.com</dt>
          <dd>{co.name}</dd>
        </div>
        <div>
          <dt>Address</dt>
          <dd>
            {co.street}
            <br />
            {co.city}
          </dd>
        </div>
        <div>
          <dt>UID and VAT</dt>
          <dd>{co.uid}</dd>
        </div>
        <div>
          <dt>LEI</dt>
          <dd>{co.lei}</dd>
        </div>
        <div>
          <dt>Commercial register</dt>
          <dd>Canton of Bern</dd>
        </div>
        <div>
          <dt>Board of directors</dt>
          <dd>To be added</dd>
        </div>
        <div>
          <dt>Share capital</dt>
          <dd>{co.capital}</dd>
        </div>
        <div>
          <dt>Self-regulatory organisation</dt>
          <dd>VQF, member number to be added</dd>
        </div>
        <div>
          <dt>Ombudsman</dt>
          <dd>FINOS, Finanzombudsstelle Schweiz</dd>
        </div>
        <div>
          <dt>Email</dt>
          <dd>
            <a href={`mailto:${co.email}`}>{co.email}</a>
          </dd>
        </div>
      </dl>
      <h2>Bank</h2>
      <dl className="site-kv mb-4">
        <div>
          <dt>Bank</dt>
          <dd>{co.bank.name}</dd>
        </div>
        <div>
          <dt>IBAN CHF</dt>
          <dd>{co.bank.CHF}</dd>
        </div>
        <div>
          <dt>IBAN EUR</dt>
          <dd>{co.bank.EUR}</dd>
        </div>
        <div>
          <dt>SWIFT</dt>
          <dd>{co.bank.swift}</dd>
        </div>
      </dl>
      <p>
        Banxum® is a registered trademark. The Banxum platform is owned and operated by {co.name}, a Swiss financial
        company. The contents of this site are information, not investment advice. The sample figures of this prototype
        are invented.
      </p>
    </>
  );
}
