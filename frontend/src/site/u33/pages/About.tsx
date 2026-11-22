// IP of Webby-Soft SRL.
/*
 * U33 About page (design about.html): the Swiss group and its affiliations, who does what
 * (you choose, Banxum manages; recovery separate) and the conversation band.
 *
 * Differences with the design (reconciliation decisions): the co-investment block ("Banxum
 * invests its own capital in every opportunity") is left out until real participation data
 * exists (U33-DEC-15); "secured by real assets" reads "secured by collateral or guarantees"
 * (U33-DEC-38).
 */
import { useT } from "../../../i18n";
import { useSiteTitle } from "../../context";
import { Ni, PublicLink } from "../ui";

const LOGO = "/brand/banxum-logo.svg";

export function About() {
  const t = useT();
  useSiteTitle(t("About Banxum"));
  return (
    <>
      <section aria-labelledby="group-title" className="group-intro">
        <div className="group-copy">
          <h1 id="group-title">
            {t("An international")}
            <br />{" "}
            {t("financial group")}
            <br />{" "}
            <span>{t("based in Switzerland.")}</span>
          </h1>
          <p>{t("Connecting investors with business loans secured by collateral or guarantees.")}</p>
        </div>
        <aside aria-labelledby="institution-title" className="institution-card">
          <div className="institution-country">
            <span aria-hidden="true" className="swiss-flag" />
            <h2 id="institution-title">{t("Switzerland")}</h2>
          </div>
          <p className="affiliation-label">{t("Affiliations of our Swiss operating company")}</p>
          <a
            aria-label={t("VQF — Self-regulatory organisation recognised by FINMA. Opens VQF website in a new tab.")}
            className="affiliation-row"
            href="https://www.vqf.ch/en/faq"
            rel="noopener noreferrer"
            target="_blank"
          >
            <div>
              <strong>VQF</strong>
              <span>{t("Self-regulatory organisation")}</span>
              <small>{t("Recognised by FINMA")}</small>
            </div>
            <Ni glyph="arrow" />
          </a>
          <a
            aria-label={t("FINOS — Swiss financial ombudsman. Opens FINOS website in a new tab.")}
            className="affiliation-row"
            href="https://www.finos.ch"
            rel="noopener noreferrer"
            target="_blank"
          >
            <div>
              <strong>FINOS</strong>
              <span>{t("Swiss financial ombudsman")}</span>
            </div>
            <Ni glyph="arrow" />
          </a>
        </aside>
      </section>
      <section aria-labelledby="service-title" className="service-section">
        <h2 id="service-title">
          {t("You choose your investment.")}
          <br />{" "}
          <span>{t("We manage it.")}</span>
        </h2>
        <div className="responsibility-board">
          <div className="investor-choice">
            <h3>{t("You")}</h3>
            <div className="choice-line">
              <span>{t("Loan")}</span>
              <strong>{t("You choose")}</strong>
            </div>
            <div className="choice-line">
              <span>{t("Amount")}</span>
              <strong>{t("You decide")}</strong>
            </div>
            <p className="choice-note">{t("Every investment needs your approval.")}</p>
          </div>
          <div className="banxum-responsibility">
            <div className="manager-heading">
              <img alt="Banxum" src={LOGO} width="102" />
            </div>
            <div className="management-layout">
              <ol className="management-stages">
                <li>
                  <div className="stage-node">
                    <span>01</span>
                  </div>
                  <h3>{t("Assessment")}</h3>
                  <p>
                    {t("The business, collateral")}
                    <br /> {t("and loan terms.")}
                  </p>
                </li>
                <li>
                  <div className="stage-node">
                    <span>02</span>
                  </div>
                  <h3>
                    {t("Loan")}
                    <br /> {t("administration")}
                  </h3>
                  <p>
                    {t("Documentation and")}
                    <br /> {t("borrower follow-up.")}
                  </p>
                </li>
                <li>
                  <div className="stage-node">
                    <span>03</span>
                  </div>
                  <h3>
                    {t("Payment")}
                    <br /> {t("collection")}
                  </h3>
                  <p>
                    {t("Payments collected")}
                    <br /> {t("for your account.")}
                  </p>
                </li>
              </ol>
              <aside aria-labelledby="recovery-title" className="recovery-support">
                <h3 id="recovery-title">{t("Recovery, if needed")}</h3>
                <p>{t("Banxum manages recovery and collateral enforcement.")}</p>
              </aside>
            </div>
          </div>
        </div>
      </section>
      <section aria-labelledby="conversation-title" className="conversation">
        <h2 id="conversation-title">{t("Talk to Banxum.")}</h2>
        <PublicLink className="button-primary" href="/contact">
          {t("Request a conversation")} <Ni glyph="arrow" />
        </PublicLink>
      </section>
    </>
  );
}
