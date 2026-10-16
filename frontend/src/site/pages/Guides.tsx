// IP of Webby-Soft SRL.
// Guides and news (design: pages_more.js guides() and pages_home.js guideCard()).
import { Eyebrow, NiIcon, PageHead, SiteLink, SubscribeBlock } from "../components";
import { siteGuides, type SiteGuide } from "../content";
import { date } from "../format";

/** Article card of the guide grids (design guideCard), also used by the guide page. */
export function GuideCard({ guide }: { guide: SiteGuide }) {
  return (
    <SiteLink className="site-article-card" href={`/guides/${guide.id}`}>
      <div className="site-photo is-wide">
        <NiIcon name={guide.icon} />
        <span>Illustration</span>
      </div>
      <div className="site-article-meta">
        <span>{guide.kind}</span>
        <span>{date(guide.date)}</span>
      </div>
      <h3 className="site-article-title">{guide.title}</h3>
      <p className="site-small mb-0">{guide.summary}</p>
    </SiteLink>
  );
}

export function Guides() {
  return (
    <>
      <PageHead
        eyebrow="Guides"
        lead="How lending to companies works, what to check and what we learn along the way."
        title="Guides and news"
      />
      <section className="site-section no-rule" style={{ paddingTop: 0 }}>
        <div className="site-wrap">
          <div className="site-projects">
            {siteGuides.map((guide) => (
              <GuideCard guide={guide} key={guide.id} />
            ))}
          </div>
        </div>
      </section>
      <section className="site-section is-paper">
        <div className="site-wrap site-split is-center">
          <div>
            <Eyebrow>Newsletter</Eyebrow>
            <h2 className="site-h2">New projects and guides by email</h2>
          </div>
          <div>
            <SubscribeBlock id="guides" source="guides" />
          </div>
        </div>
      </section>
    </>
  );
}
