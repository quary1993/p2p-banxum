// IP of Webby-Soft SRL.
/*
 * Questions and answers (design: pages_more.js help()).
 *
 * Behaviour as the design: the search filters the questions on their whole text (question and
 * answer), opens every match, hides the topics without a match and shows "No question matches"
 * when nothing is left. ?q= fills the search on arrival; ?topic= marks the topic in the side
 * navigation and scrolls to it. A new address (a topic link) shows the page afresh, like the
 * design's re-render: empty search (or ?q=), every question closed.
 */
import { useEffect, useMemo, useState } from "react";

import { NiIcon, PageHead, SiteLink } from "../components";
import { siteCompany, siteFaq } from "../content";
import { useSiteNav } from "../context";
import { siteHtml, useStaticLinkClick } from "../links";

/** Text of a static HTML answer, as the browser reads it (textContent). */
function htmlText(html: string) {
  const element = document.createElement("div");
  element.innerHTML = html;
  return element.textContent ?? "";
}

function itemKey(groupId: string, index: number) {
  return `${groupId}-${index}`;
}

let searchTexts: Map<string, string> | null = null;

/** The text each question is searched in (question and answer, lower case), by item key. */
function questionTexts() {
  if (!searchTexts) {
    searchTexts = new Map();
    for (const group of siteFaq) {
      group.items.forEach((item, index) => searchTexts?.set(itemKey(group.id, index), `${item.q}\n${htmlText(item.a)}`.toLowerCase()));
    }
  }
  return searchTexts;
}

/** Keys of the questions that contain the search text; null for an empty search (all shown). */
function findQuestions(value: string): Set<string> | null {
  const q = value.trim().toLowerCase();
  if (!q) return null;
  return new Set([...questionTexts()].filter(([, text]) => text.includes(q)).map(([key]) => key));
}

export function Help() {
  const { search } = useSiteNav();
  // A new query string is a new page in the design (search reset, questions closed).
  return <HelpPage key={search} />;
}

function HelpPage() {
  const { query } = useSiteNav();
  const topic = query.get("topic");
  const initialQuery = query.get("q") ?? "";
  const onStaticLinkClick = useStaticLinkClick();

  const [value, setValue] = useState(initialQuery);
  // Questions opened by the visitor or by a search (the design opens each match and leaves it open).
  const [open, setOpen] = useState<Set<string>>(() => findQuestions(initialQuery) ?? new Set());
  const hits = useMemo(() => findQuestions(value), [value]);

  const onSearch = (next: string) => {
    setValue(next);
    const found = findQuestions(next);
    if (found) setOpen((current) => new Set([...current, ...found]));
  };

  const setItemOpen = (key: string, isOpen: boolean) =>
    setOpen((current) => {
      if (current.has(key) === isOpen) return current;
      const next = new Set(current);
      if (isOpen) next.add(key);
      else next.delete(key);
      return next;
    });

  // ?topic=: to the topic once the page is shown (a passive effect runs after the shell's
  // scroll to the top of a new page).
  useEffect(() => {
    if (!topic || !siteFaq.some((group) => group.id === topic)) return;
    document.querySelector(`[data-faq-group="${topic}"]`)?.scrollIntoView({ block: "start" });
  }, [topic]);

  const shown = hits ? hits.size : questionTexts().size;

  return (
    <>
      <PageHead
        eyebrow="Help"
        lead="Everything about accounts, investing, payments and risks. Search, or choose a topic."
        title="Questions and answers"
      />
      <section className="site-section no-rule" style={{ paddingTop: 0 }}>
        <div className="site-wrap">
          <div className="site-help-search mb-5">
            <NiIcon name="ni-search" />
            <input
              aria-label="Search the questions"
              className="form-control"
              id="site-help-q"
              onChange={(event) => onSearch(event.target.value)}
              placeholder="Search the questions, e.g. minimum, tax, late"
              type="search"
              value={value}
            />
          </div>
          <div className="site-sidebar-layout">
            <ul aria-label="Topics" className="site-side-nav">
              {siteFaq.map((group) => (
                <li key={group.id}>
                  <SiteLink
                    aria-current={topic === group.id ? "location" : undefined}
                    className={topic === group.id ? "active" : ""}
                    href={`/help?topic=${group.id}`}
                  >
                    {group.title}
                  </SiteLink>
                </li>
              ))}
              <li>
                <SiteLink href="/companies">For companies</SiteLink>
              </li>
            </ul>
            <div>
              {siteFaq.map((group) => {
                const groupHits = group.items.filter((_, index) => !hits || hits.has(itemKey(group.id, index))).length;
                return (
                  <div
                    className="mb-5"
                    data-faq-group={group.id}
                    hidden={groupHits === 0}
                    key={group.id}
                    style={{ scrollMarginTop: 96 }}
                  >
                    <h2 className="site-h3 mb-3">{group.title}</h2>
                    <div className="site-faq" onClick={onStaticLinkClick}>
                      {group.items.map((item, index) => {
                        const key = itemKey(group.id, index);
                        return (
                          <details
                            className="site-faq-item"
                            hidden={hits ? !hits.has(key) : undefined}
                            key={key}
                            onToggle={(event) => setItemOpen(key, event.currentTarget.open)}
                            open={open.has(key)}
                          >
                            <summary>{item.q}</summary>
                            <div className="site-faq-answer" dangerouslySetInnerHTML={{ __html: siteHtml(item.a) }} />
                          </details>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
              <p className="site-text" hidden={shown > 0} id="site-help-none">
                No question matches. Try another word, or <SiteLink href="/contact">ask us</SiteLink>.
              </p>
              <div className="site-box is-ink-rule mt-5">
                <h2 className="site-h4">Still have a question?</h2>
                <p className="site-text">
                  Write to <a href={`mailto:${siteCompany.email}`}>{siteCompany.email}</a> or call {siteCompany.phone},{" "}
                  {siteCompany.hours}.
                </p>
                <SiteLink className="btn btn-lg btn-primary" href="/contact">
                  Contact form
                </SiteLink>
              </div>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
