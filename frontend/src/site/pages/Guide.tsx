// IP of Webby-Soft SRL.
// One guide or news article (design: pages_more.js guide()). Unknown ids show the design's 404.
import { Eyebrow, NiIcon, SiteHtml, SiteLink } from "../components";
import { siteGuides } from "../content";
import { useSiteTitle } from "../context";
import { date } from "../format";
import type { SitePageProps } from "../SitePages";
import { GuideCard } from "./Guides";
import { NotFound } from "./NotFound";

const NARROW = { marginLeft: "auto", marginRight: "auto" };

export function Guide({ params }: SitePageProps) {
  const guide = siteGuides.find((item) => item.id === params.id);
  useSiteTitle(guide ? guide.title : "Not found");
  if (!guide) return <NotFound />;
  const more = siteGuides.filter((item) => item.id !== guide.id).slice(0, 3);
  return (
    <>
      <section className="site-page-head">
        <div className="site-wrap site-narrow" style={NARROW}>
          <nav aria-label="Breadcrumb" className="site-crumbs">
            <SiteLink href="/guides">Guides</SiteLink>
            <span>/</span>
            <span>{guide.kind}</span>
          </nav>
          <div className="site-article-meta">
            <span>{guide.kind}</span>
            <span>{date(guide.date)}</span>
          </div>
          <h1 className="site-h1">{guide.title}</h1>
          <p className="site-lead">{guide.summary}</p>
        </div>
      </section>
      <section className="site-section no-rule" style={{ paddingTop: 0 }}>
        <div className="site-wrap site-narrow" style={NARROW}>
          <div className="site-photo is-wide mb-5">
            <NiIcon name={guide.icon} />
            <span>Illustration</span>
          </div>
          <SiteHtml className="site-prose" html={guide.body} />
          <div className="site-box is-ink-rule mt-5">
            <h2 className="site-h4">Ready to look at the projects?</h2>
            <p className="site-text">Open projects show the same facts described here.</p>
            <div className="site-actions">
              <SiteLink className="btn btn-lg btn-primary" href="/projects">
                See open projects
              </SiteLink>
              <SiteLink className="btn btn-lg btn-site-outline" href="/register">
                Open account
              </SiteLink>
            </div>
          </div>
        </div>
      </section>
      <section className="site-section">
        <div className="site-wrap">
          <div className="site-section-head is-single">
            <div>
              <Eyebrow>More</Eyebrow>
              <h2 className="site-h2">Other guides</h2>
            </div>
          </div>
          <div className="site-projects">
            {more.map((item) => (
              <GuideCard guide={item} key={item.id} />
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
