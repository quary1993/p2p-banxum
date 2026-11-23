// IP of Webby-Soft SRL.
/*
 * Guides in the U33 public design (U33-DEC-39, Q24, D-10). The design has no guide pages; they use
 * the design's legal page blocks (Q23): the page hero, the two-column layout with the index and
 * the document card. The October cards' "Illustration" placeholders are not carried over.
 * - /guides: every guide as a numbered section of the card (kind, date, title, summary, link),
 *   and the newsletter sign-up.
 * - /guides/:id: the guide split at its headings ("On this page"), the other guides, and the
 *   links to the projects. An unknown id is the 404.
 */
import { useT } from "../../../i18n";
import { SiteHtml } from "../../components";
import { siteGuides, type SiteGuide } from "../../content";
import { useSiteTitle } from "../../context";
import { date } from "../../format";
import type { SitePageProps } from "../../SitePages";
import { Subscribe } from "../Subscribe";
import { Ni, PublicLink } from "../ui";
import { NotFound } from "./Notice";

export function Guides() {
  const t = useT();
  useSiteTitle(t("Guides"));
  return (
    <div className="content-shell legal-view bxp-guides">
      <section aria-labelledby="guides-title" className="page-hero legal-hero">
        <p className="page-kicker">{t("GUIDES")}</p>
        <h1 className="page-title" id="guides-title">
          {t("Guides and news")}
        </h1>
        <p className="page-lead">{t("How lending to companies works, what to check and what we learn along the way.")}</p>
      </section>
      <div className="legal-document-layout">
        <aside className="legal-contents">
          <p className="page-kicker">{t("ON THIS PAGE")}</p>
          <nav aria-label={t("Guides")} className="legal-jump-nav">
            {siteGuides.map((guide, index) => (
              <PublicLink href={`/guides/${guide.id}`} key={guide.id}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                {guide.title}
              </PublicLink>
            ))}
          </nav>
          <PublicLink className="legal-related" href="/help">
            {t("Questions and answers")} <Ni glyph="arrow" />
          </PublicLink>
        </aside>
        <div aria-label={t("Guides and news")} className="legal-outline bxp-legal-document">
          {siteGuides.map((guide, index) => (
            <GuideRow guide={guide} index={index} key={guide.id} />
          ))}
        </div>
      </div>
      <section aria-labelledby="guides-newsletter-title" className="bxp-projects-more is-single">
        <div className="bxp-panel">
          <h2 id="guides-newsletter-title">{t("New projects and guides by email")}</h2>
          <p>{t("Projects are often funded within days. We tell you when a new one opens.")}</p>
          <Subscribe id="guides" source="guides" />
        </div>
      </section>
    </div>
  );
}

function GuideRow({ guide, index }: { guide: SiteGuide; index: number }) {
  const t = useT();
  return (
    <section className="legal-outline-section bxp-guide-row">
      <span aria-hidden="true" className="legal-section-number">
        {String(index + 1).padStart(2, "0")}
      </span>
      <div>
        <p className="bxp-guide-meta">
          <span>{t(guide.kind)}</span>
          <span>{date(guide.date)}</span>
        </p>
        <h2>
          <PublicLink href={`/guides/${guide.id}`}>{guide.title}</PublicLink>
        </h2>
        <p>{guide.summary}</p>
        <PublicLink className="text-link" href={`/guides/${guide.id}`}>
          {t("Read the guide")} <Ni glyph="arrow" />
        </PublicLink>
      </div>
    </section>
  );
}

export function Guide({ params }: SitePageProps) {
  const t = useT();
  const guide = siteGuides.find((item) => item.id === params.id);
  useSiteTitle(guide ? guide.title : t("Not found"));
  if (!guide) return <NotFound />;
  const parts = guide.body.split(/<h2>(.*?)<\/h2>/);
  const intro = parts[0].trim();
  const sections: { heading: string; html: string }[] = [];
  for (let i = 1; i < parts.length; i += 2) sections.push({ heading: parts[i], html: parts[i + 1] ?? "" });
  const sectionId = (index: number) => `guide-section-${index + 1}`;
  const others = siteGuides.filter((item) => item.id !== guide.id);
  return (
    <div className="content-shell legal-view bxp-guides">
      <section aria-labelledby="guide-title" className="page-hero legal-hero">
        <p className="page-kicker">
          <PublicLink href="/guides">{t("GUIDES")}</PublicLink>
          {" · "}
          {t(guide.kind).toUpperCase()}
        </p>
        <h1 className="page-title" id="guide-title">
          {guide.title}
        </h1>
        <p className="page-lead">{guide.summary}</p>
        <div className="legal-draft-note">
          <p className="bxp-legal-meta">
            <span>{date(guide.date)}</span>
          </p>
        </div>
      </section>
      <div className="legal-document-layout">
        <aside className="legal-contents">
          {sections.length ? (
            <>
              <p className="page-kicker">{t("ON THIS PAGE")}</p>
              <nav aria-label={t("{title} contents", { title: guide.title })} className="legal-jump-nav">
                {sections.map((section, index) => (
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
          <PublicLink className="legal-related" href="/projects">
            {t("See open projects")} <Ni glyph="arrow" />
          </PublicLink>
          {others.length ? (
            <div className="bxp-legal-documents">
              <p className="page-kicker">{t("OTHER GUIDES")}</p>
              <ul aria-label={t("Other guides")}>
                {others.map((item) => (
                  <li key={item.id}>
                    <PublicLink href={`/guides/${item.id}`}>{item.title}</PublicLink>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </aside>
        <div aria-label={guide.title} className="legal-outline bxp-legal-document">
          {intro ? <SiteHtml className="legal-outline-intro bxp-legal-intro" html={intro} /> : null}
          {sections.map((section, index) => (
            <section className="legal-outline-section" id={sectionId(index)} key={sectionId(index)}>
              <span aria-hidden="true" className="legal-section-number">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <h2>{section.heading}</h2>
                <SiteHtml html={section.html} />
              </div>
            </section>
          ))}
        </div>
      </div>
      <div className="legal-bottom-links">
        <PublicLink className="text-link" href="/guides">
          {t("All guides")} <Ni glyph="arrow" />
        </PublicLink>
        <PublicLink className="text-link" href="/register">
          {t("Open account")} <Ni glyph="arrow" />
        </PublicLink>
      </div>
    </div>
  );
}
