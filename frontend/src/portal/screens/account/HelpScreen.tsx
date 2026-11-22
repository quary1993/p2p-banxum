// IP of Webby-Soft SRL.
// Help (design: main.tr-page.hp-page): search, topics, the common questions and the support box,
// "How investing works" and "Contact support" dialogs. Answers are true for today's platform
// (help/helpContent.ts); the holding time comes from the balances API.
import "./account.css";

import { useState } from "react";

import { useT } from "../../../i18n";
import { autoReturnDays } from "../../../investorPortal/balanceAgeing";
import { useBalancesData, useFxFeature } from "../../../investorPortal/data";
import { brandDisplayName } from "../../brand";
import { Button, Dialog, NiIcon, PageHead, PortalLink } from "../../components";
import { supportEmail } from "./accountLinks";
import { HELP_TOPICS, helpQuestions, matchesHelpQuestion, type HelpTopic } from "./help/helpContent";
import { ContactSupportDialog } from "./parts/ContactSupportDialog";

function HowInvestingWorksDialog({ onClose }: { onClose: () => void }) {
  const t = useT();
  const brand = brandDisplayName();
  const steps = [
    [t("Choose an opportunity and an amount"), t("Choose an amount from your available {brand} balance, in the loan's currency.", { brand })],
    [t("Review and confirm your investment"), t("Read the documents and the risk information, accept them and confirm with your PIN and an email code. Your money stays reserved until funding closes.")],
    [t("Your investment begins when funding closes"), t("If the minimum funding is reached, your investment starts. If not, the reserved money becomes available again in your {brand} account.", { brand })],
    [t("Receive repayments in your {brand} account", { brand }), t("The payment schedule shows when principal and interest are due. Your share of each payment received from the borrower is credited to your {brand} balance; you can invest it again or withdraw it.", { brand })]
  ];
  return (
    <Dialog bodyClassName="hp-modal-body" className="hp-modal" onClose={onClose} size="lg" title={t("How investing works")}>
      <ol className="pd-investing-steps">
        {steps.map(([title, text], index) => (
          <li key={title}>
            <span aria-hidden="true" className="pd-step-number">{index + 1}</span>
            <div>
              <h3>{title}</h3>
              <p>{text}</p>
            </div>
          </li>
        ))}
      </ol>
      <p className="pd-investing-security">{t("Collateral and guarantees can help recover money if a borrower does not repay. Full and timely repayment is not guaranteed.")}</p>
    </Dialog>
  );
}

export function HelpScreen() {
  const t = useT();
  const fx = useFxFeature();
  const balances = useBalancesData();
  const days = autoReturnDays(balances.data?.auto_return_after_days);
  const questions = helpQuestions(t, { days, brand: brandDisplayName(), fxEnabled: fx.enabled });
  const [topic, setTopic] = useState<"all" | HelpTopic>("all");
  const [search, setSearch] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [dialog, setDialog] = useState<{ kind: "how" } | { kind: "contact"; topic?: string } | null>(null);
  const visible = questions.filter((item) => matchesHelpQuestion(item, topic, search));
  const count = visible.length;
  const resetSearch = () => {
    setSearch("");
    setTopic("all");
  };

  return (
    <main className="tr-page hp-page">
      <PageHead
        actions={<Button icon="info" onClick={() => setDialog({ kind: "how" })}>{t("How investing works")}</Button>}
        title={t("Help")}
      />
      <div className="tr-toolbar hp-toolbar">
        <div className="tr-search">
          <NiIcon name="search" />
          <input
            aria-label={t("Search for an answer")}
            autoComplete="off"
            className="form-control"
            id="hp-search"
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("Search for an answer")}
            type="search"
            value={search}
          />
          {search ? (
            <button aria-label={t("Clear search")} id="hp-clear" onClick={() => setSearch("")} type="button">
              <NiIcon name="cross-sm" />
            </button>
          ) : null}
        </div>
      </div>
      <nav aria-label={t("Help topics")} className="hp-topics">
        {HELP_TOPICS.map(([key, label]) => (
          <button aria-pressed={topic === key} className={topic === key ? "active" : ""} data-hp-topic={key} key={key} onClick={() => setTopic(key)} type="button">
            {t(label)}
          </button>
        ))}
      </nav>
      <div className="hp-layout">
        <section aria-label={t("Questions and answers")}>
          <div className="hp-list-head">
            <h2>{t("Common questions")}</h2>
            <span id="hp-result-count" role="status" aria-live="polite">
              {search.trim() ? (count === 1 ? t("1 answer found") : t("{count} answers found", { count })) : ""}
            </span>
          </div>
          <div className="hp-questions">
            {questions.map((item) => {
              const shown = visible.includes(item);
              const open = shown && openId === item.id;
              return (
                <details className="hp-question" data-question={item.id} hidden={!shown} key={item.id} open={open}>
                  <summary
                    aria-expanded={open}
                    onClick={(event) => {
                      event.preventDefault();
                      setOpenId(open ? null : item.id);
                    }}
                  >
                    {item.question}
                    <NiIcon name="chevron-down" />
                  </summary>
                  <div className="hp-answer">
                    <p>{item.answer}</p>
                    {item.more ? (
                      <details className="hp-more">
                        <summary>{item.more.title}</summary>
                        <p>{item.more.text}</p>
                      </details>
                    ) : null}
                    <div className="hp-answer-links">
                      {item.links.map((link) => (
                        <PortalLink key={link.label} params={link.params} to={link.to}>
                          {link.label}
                          <NiIcon name="arrow-right" />
                        </PortalLink>
                      ))}
                      {item.contact ? (
                        <button onClick={() => setDialog({ kind: "contact", topic: item.contact })} type="button">
                          {t("Contact support")}
                          <NiIcon name="arrow-right" />
                        </button>
                      ) : null}
                    </div>
                  </div>
                </details>
              );
            })}
          </div>
          {count === 0 ? (
            <div className="hp-empty r75-empty" id="hp-empty">
              <NiIcon name="search" />
              <h3>{t("No answers found")}</h3>
              <p>{t("Try another phrase or browse all questions.")}</p>
              <div>
                <button className="btn btn-outline-light" id="hp-reset" onClick={resetSearch} type="button">{t("Show all questions")}</button>
                <button className="btn btn-primary" onClick={() => setDialog({ kind: "contact" })} type="button">{t("Contact support")}</button>
              </div>
            </div>
          ) : null}
        </section>
        <aside>
          <div className="hp-support rss-help-support">
            <NiIcon className="hp-support-icon" name="mail" />
            <h2>{t("Need more help?")}</h2>
            <p>{t("Send us a message about your account or an investment.")}</p>
            <button className="btn btn-primary" onClick={() => setDialog({ kind: "contact" })} type="button">
              {t("Contact support")}
              <NiIcon name="arrow-right" />
            </button>
            <dl>
              <dt>{t("Email")}</dt>
              <dd><a href={`mailto:${supportEmail}`}>{supportEmail}</a></dd>
            </dl>
          </div>
        </aside>
      </div>
      {dialog?.kind === "how" ? <HowInvestingWorksDialog onClose={() => setDialog(null)} /> : null}
      {dialog?.kind === "contact" ? <ContactSupportDialog onClose={() => setDialog(null)} topic={dialog.topic} /> : null}
    </main>
  );
}
