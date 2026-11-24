// IP of Webby-Soft SRL.
/*
 * Help in the U33 public design (U33-DEC-39, Q24, D-10). The design has no Help page: the home page
 * keeps a selection of the questions; this page has all of them and the content of the retired
 * How it works page. Built from the design's blocks (Q23): the legal page hero and two-column
 * layout ("On this page" index, document card) and the home page's Q&A list.
 *
 * Behaviour (as before): the search filters the questions on their whole text (question and
 * answer), opens every match, hides the topics without a match and shows "No question matches"
 * when nothing is left. ?q= fills the search on arrival; ?topic= marks the topic and scrolls to
 * it; /help#how-it-works (the retired /how-it-works address) scrolls to How it works. A new
 * address shows the page afresh (empty search or ?q=, every question closed).
 *
 * No support hours or phone number (U33-DEC-35: not confirmed for publication).
 */
import { useEffect, useMemo, useState, type MouseEvent, type ReactNode } from "react";

import { useT } from "../../../i18n";
import { siteCompany, siteFaq } from "../../content";
import { useSiteNav, useSiteTitle } from "../../context";
import { siteHtml, useStaticLinkClick } from "../../links";
import { MarketplaceDiagram } from "../../pages/HowItWorks";
import { Ni, PublicLink } from "../ui";

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

const HOW_ID = "how-it-works";

export function Help() {
  const { search } = useSiteNav();
  // A new query string is a new page (search reset, questions closed).
  return <HelpPage key={search} />;
}

function HelpPage() {
  const t = useT();
  useSiteTitle(t("Help"));
  const { query } = useSiteNav();
  const topic = query.get("topic");
  const initialQuery = query.get("q") ?? "";
  const onStaticLinkClick = useStaticLinkClick();

  const [value, setValue] = useState(initialQuery);
  // Questions opened by the visitor or by a search (each match opens and stays open).
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

  // ?topic= and #how-it-works: to the part once the page is shown (a passive effect runs after
  // the shell's scroll to the top of a new page).
  useEffect(() => {
    const target =
      topic && siteFaq.some((group) => group.id === topic)
        ? document.getElementById(`help-${topic}`)
        : window.location.hash === `#${HOW_ID}`
          ? document.getElementById(HOW_ID)
          : null;
    target?.scrollIntoView({ block: "start" });
  }, [topic]);

  const shown = hits ? hits.size : questionTexts().size;
  const jump = (id: string) => (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="content-shell legal-view bxp-help">
      <section aria-labelledby="help-title" className="page-hero legal-hero">
        <p className="page-kicker">{t("HELP")}</p>
        <h1 className="page-title" id="help-title">
          {t("Questions and answers")}
        </h1>
        <p className="page-lead">{t("Everything about accounts, investing, payments and risks. Search, or choose a topic.")}</p>
        <label className="bxp-search">
          <span className="sr-only">{t("Search the questions")}</span>
          <input
            id="bxp-help-q"
            onChange={(event) => onSearch(event.target.value)}
            placeholder={t("Search the questions, e.g. minimum, tax, late")}
            type="search"
            value={value}
          />
        </label>
      </section>
      <div className="legal-document-layout">
        <aside className="legal-contents">
          <p className="page-kicker">{t("TOPICS")}</p>
          <nav aria-label={t("Topics")} className="legal-jump-nav">
            {siteFaq.map((group, index) => (
              <a
                aria-current={topic === group.id ? "location" : undefined}
                href={`/help?topic=${group.id}`}
                key={group.id}
                onClick={jump(`help-${group.id}`)}
              >
                <span>{String(index + 1).padStart(2, "0")}</span>
                {group.title}
              </a>
            ))}
            <a href={`/help#${HOW_ID}`} onClick={jump(HOW_ID)}>
              <span>{String(siteFaq.length + 1).padStart(2, "0")}</span>
              {t("How it works")}
            </a>
          </nav>
          <PublicLink className="legal-related" href="/contact">
            {t("Contact Banxum")} <Ni glyph="arrow" />
          </PublicLink>
          <div className="bxp-legal-documents">
            <p className="page-kicker">{t("MORE")}</p>
            <ul aria-label={t("More pages")}>
              <li>
                <PublicLink href="/guides">{t("Guides")}</PublicLink>
              </li>
              <li>
                <PublicLink href="/projects">{t("All projects")}</PublicLink>
              </li>
              <li>
                <PublicLink href="/statistics">{t("Statistics")}</PublicLink>
              </li>
              <li>
                <PublicLink href="/companies">{t("For borrowers")}</PublicLink>
              </li>
              <li>
                <PublicLink href="/legal/risk">{t("Risk information")}</PublicLink>
              </li>
            </ul>
          </div>
        </aside>
        <div aria-label={t("Questions and answers")} className="legal-outline bxp-legal-document bxp-help-document" onClick={onStaticLinkClick}>
          {siteFaq.map((group, groupIndex) => {
            const groupHits = group.items.filter((_, index) => !hits || hits.has(itemKey(group.id, index))).length;
            return (
              <section className="legal-outline-section" data-faq-group={group.id} hidden={groupHits === 0} id={`help-${group.id}`} key={group.id}>
                <span aria-hidden="true" className="legal-section-number">
                  {String(groupIndex + 1).padStart(2, "0")}
                </span>
                <div>
                  <h2>{group.title}</h2>
                  <div className="faq-list">
                    {group.items.map((item, index) => {
                      const key = itemKey(group.id, index);
                      return (
                        <details
                          className="faq-item"
                          hidden={hits ? !hits.has(key) : undefined}
                          key={key}
                          onToggle={(event) => setItemOpen(key, event.currentTarget.open)}
                          open={open.has(key)}
                        >
                          <summary>
                            {item.q}
                            <span aria-hidden="true" className="faq-toggle" />
                          </summary>
                          <div className="faq-answer" dangerouslySetInnerHTML={{ __html: siteHtml(item.a) }} />
                        </details>
                      );
                    })}
                  </div>
                </div>
              </section>
            );
          })}
          <p className="bxp-help-none" hidden={shown > 0} id="bxp-help-none">
            {t("No question matches. Try another word, or")} <PublicLink href="/contact">{t("ask us")}</PublicLink>.
          </p>
        </div>
      </div>
      <HowItWorksPart />
      <section aria-labelledby="help-contact-title" className="bxp-help-contact">
        <div>
          <p className="page-kicker">{t("STILL HAVE A QUESTION?")}</p>
          <h2 id="help-contact-title">{t("Write to us.")}</h2>
          <p>
            {t("Email")} <a href={`mailto:${siteCompany.email}`}>{siteCompany.email}</a> {t("or use the contact form. A member of our team replies by email.")}
          </p>
        </div>
        <PublicLink className="button-primary" href="/contact">
          {t("Contact form")} <Ni glyph="arrow" />
        </PublicLink>
      </section>
    </div>
  );
}

function HowStep({ index, title, children }: { index: string; title: string; children: ReactNode }) {
  return (
    <li>
      <span className="bxp-how-index">{index}</span>
      <div>
        <h3>{title}</h3>
        <p>{children}</p>
      </div>
    </li>
  );
}

/**
 * Q24 (2026-11-13): the content of the retired How it works page, in the document card layout.
 * The texts follow the current rules: confirmation with the email code and the PIN or the
 * authenticator code (D-1), funding close with the minimum subscription, the 56-day return,
 * resale at 0-102% with the capped 2% fee (U33-DEC-06/07), no signature step before D-12.
 */
function HowItWorksPart() {
  const t = useT();
  return (
    <section aria-labelledby={`${HOW_ID}-title`} className="bxp-how" id={HOW_ID}>
      <div className="bxp-how-head">
        <p className="page-kicker">{t("HOW IT WORKS")}</p>
        <h2 className="section-title" id={`${HOW_ID}-title`}>
          {t("From your first transfer to the last repayment.")}
        </h2>
        <p className="page-lead">{t("You lend to companies by buying shares of their loans. Here is each step, what you own and where your money is.")}</p>
      </div>
      <div className="legal-outline bxp-legal-document">
        <section className="legal-outline-section">
          <span aria-hidden="true" className="legal-section-number">
            01
          </span>
          <div>
            <h2>{t("How you invest")}</h2>
            <ol className="bxp-how-steps">
              <HowStep index="01" title={t("Open your account")}>
                {t("Your details, a password and a second factor (an SMS code or an authenticator app), then an online identity check with your ID and a selfie. Before your first investment you give a few declarations and add a verified bank account in your name.")}
              </HowStep>
              <HowStep index="02" title={t("Add funds")}>
                {t("A bank transfer in CHF or EUR from an account in your name, with your personal reference. It arrives in your own segregated wallet. No Banxum fee; your bank may charge for the transfer.")}
              </HowStep>
              <HowStep index="03" title={t("Invest")}>
                {t("Choose a project and an amount from your available balance, review the terms and confirm with the code we email you and your PIN (or your authenticator code). The amount is reserved until the funding closes.")}
              </HowStep>
              <HowStep index="04" title={t("Get repaid")}>
                {t("Interest counts every day from the pay-out to the borrower. Each repayment is credited to your balance, to invest again or to withdraw.")}
              </HowStep>
            </ol>
          </div>
        </section>
        <section className="legal-outline-section">
          <span aria-hidden="true" className="legal-section-number">
            02
          </span>
          <div>
            <h2>{t("A share of a claim, in your name")}</h2>
            <p>
              {t(
                "Investors fund loans through Banxum: new loans granted by Garanta and existing claims from loan originators. You receive a share of the claim against the company, under the investment and assignment terms you accept before you confirm. Garanta collects the repayments and credits them to your balance with interest."
              )}
            </p>
            <div className="bxp-diagram">
              <MarketplaceDiagram />
            </div>
          </div>
        </section>
        <section className="legal-outline-section">
          <span aria-hidden="true" className="legal-section-number">
            03
          </span>
          <div>
            <h2>{t("Where your money is at each step")}</h2>
            <p>{t("Every investor has a segregated wallet with a CHF and a EUR balance. Garanta is not a bank: money waiting in the wallet earns no interest and stays at most until day 56.")}</p>
            <ol className="bxp-how-steps">
              <HowStep index="01" title={t("Available")}>
                {t("Your transfer arrives in your wallet, kept apart from Garanta’s own money and recorded in your name, as available balance.")}
              </HowStep>
              <HowStep index="02" title={t("Reserved")}>
                {t("When you invest, the amount is reserved for that loan. If the loan does not reach its minimum funding by the funding deadline, the reservation is released and the money is available again.")}
              </HowStep>
              <HowStep index="03" title={t("Invested")}>
                {t("When the funding closes, you hold your share of the claim. The loan is paid out to the borrower, and interest counts every day from the pay-out.")}
              </HowStep>
              <HowStep index="04" title={t("Repaid")}>
                {t("Each repayment is credited to your balance when the company pays. You invest it again or withdraw it to your verified bank account.")}
              </HowStep>
              <HowStep index="05" title={t("Returned")}>
                {t("Money you do not invest by day 56 goes back to your verified bank account (the return starts on day 57, or earlier when the bank is closed on that day).")}
              </HowStep>
            </ol>
          </div>
        </section>
        <section className="legal-outline-section">
          <span aria-hidden="true" className="legal-section-number">
            04
          </span>
          <div>
            <h2>{t("Selling early: the resale market")}</h2>
            <p>
              {t(
                "You can offer your whole share of a loan that is paid on time to other investors, at a price from 0% to 102% of the outstanding principal (a discount, or at most a 2% premium). The buyer also pays the interest accrued since the last payment. A sale is not guaranteed: someone has to buy."
              )}
            </p>
          </div>
        </section>
        <section className="legal-outline-section">
          <span aria-hidden="true" className="legal-section-number">
            05
          </span>
          <div>
            <h2>{t("Fees for investors")}</h2>
            <p>
              {t(
                "No Banxum fee for your wallet, for adding or withdrawing money, for investing or on interest and repayments. When you sell on the resale market, you pay 2% of the price, at most 2% of the outstanding principal; buyers pay no fee. If a loan is in recovery, real external costs (lawyer, court, enforcement) can be deducted from what is recovered; Banxum takes no recovery fee. Your bank may charge for transfers."
              )}
            </p>
          </div>
        </section>
      </div>
      <p className="bxp-risk-line">{t("Capital at risk. Collateral does not guarantee repayment.")}</p>
    </section>
  );
}
