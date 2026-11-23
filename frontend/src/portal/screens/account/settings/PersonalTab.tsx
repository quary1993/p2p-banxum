// IP of Webby-Soft SRL.
// Profile & Settings -> Personal details (design: .ps-personal-grid with Contact details and
// Identity, the "Verification details" disclosure with "Next review by" (the 18.10 re-verification
// date) and the "Accepted agreements" row to Documents). Verified data is read-only with "Contact
// support to change" (U33-DEC-26); the address, date of birth and nationality are shown when Didit
// verified them (18.3, Vlad E-08), never asked for or invented. Declarations have their own tab (18.10).
import { t, useT } from "../../../../i18n";
import { useReverificationDate } from "../../../../investorPortal/complianceBlock";
import { formatDate } from "../../../../investorPortal/format";
import { NiIcon, PortalLink } from "../../../components";
import { supportMailto } from "../accountLinks";
import { PsPanel, PsStatus } from "../parts/ui";
import type { SettingsSection } from "./settingsTabs";
import { investorTypeLabel, kycStatusView, type AccountData } from "./useAccountData";

const historyIcon = { done: "check-circle", pending: "clock", action: "alert-circle" } as const;

// Didit gives ISO 3166 alpha-3 codes; the common ones read as names, others stay as the code.
const NATIONALITIES: Record<string, string> = {
  CHE: "Swiss", CH: "Swiss", LIE: "Liechtenstein", LI: "Liechtenstein", DEU: "German", DE: "German",
  AUT: "Austrian", AT: "Austrian", FRA: "French", FR: "French", ITA: "Italian", IT: "Italian", ROU: "Romanian", RO: "Romanian"
};

function nationalityName(code: string) {
  if (!code) return "";
  return t(NATIONALITIES[code.toUpperCase()] ?? code.toUpperCase());
}

function HistoryItem({ tone, title, status, description }: { tone: keyof typeof historyIcon; title: string; status: string; description?: string }) {
  return (
    <li className={`acc-history-${tone}`}>
      <span>
        <NiIcon name={historyIcon[tone]} />
        {title}
      </span>
      <div>
        {status}
        {description ? <small>{description}</small> : null}
      </div>
    </li>
  );
}

export function PersonalTab({ account, section }: { account: AccountData; section: SettingsSection | null }) {
  const t = useT();
  const reviewDate = useReverificationDate();
  const kyc = kycStatusView(account.kycStatus);
  const verified = account.kycStatus === "approved";
  const changeHref = supportMailto({
    subject: t("Change of personal details"),
    body: t("Please tell us which detail should change. We will verify your identity before we change anything."),
    reference: account.reference
  });
  const identityRows = [
    { label: t("Full name"), value: account.name },
    { label: t("Date of birth"), value: account.verifiedBirthDate ? formatDate(account.verifiedBirthDate) : "" },
    { label: t("Nationality"), value: nationalityName(account.verifiedNationality) },
    { label: t("Address"), value: account.verifiedAddress },
    { label: t("Investor type"), value: investorTypeLabel(account.accountType) ? t(investorTypeLabel(account.accountType)) : "" },
    { label: t("Investor ID"), value: account.reference ?? "" }
  ].filter((row) => row.value);

  return (
    <>
      <div className="ps-personal-grid">
        <PsPanel title={t("Contact details")}>
          <div className="ps-panel-body ps-contact-list">
            {account.email ? (
              <div className="ps-contact-row">
                <div>
                  <span>{t("Email")}</span>
                  <strong>{account.email}</strong>
                </div>
              </div>
            ) : null}
            {account.phoneVerified !== undefined ? (
              <div className="ps-contact-row">
                <div>
                  <span>{t("Phone")}</span>
                  <strong>
                    {account.phoneVerified
                      ? account.phoneLastDigits
                        ? t("Verified · ending in {digits}", { digits: account.phoneLastDigits })
                        : t("Verified")
                      : t("Not verified yet")}
                  </strong>
                </div>
              </div>
            ) : null}
            {/* U33-DEC-26: no free editing; one "Contact support to change" access instead of the design's Edit buttons. */}
            <div className="ps-contact-row acc-contact-change">
              <a className="btn btn-outline-light" href={changeHref}>{t("Contact support to change")}</a>
            </div>
          </div>
        </PsPanel>
        <PsPanel
          status={account.kycStatus ? (verified ? <PsStatus>{t("Verified")}</PsStatus> : <PsStatus muted>{t("Verification pending")}</PsStatus>) : null}
          title={t("Identity")}
        >
          <div className="ps-panel-body">
            {identityRows.length > 0 ? (
              <dl className="ps-identity-grid">
                {identityRows.map((row) => (
                  <div key={row.label}>
                    <dt>{row.label}</dt>
                    <dd>{row.value}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
            <p className="ps-panel-note">{t("These details come from your verified identity document or account registration. Contact support if they need to change.")}</p>
          </div>
        </PsPanel>
      </div>

      <details className="ps-disclosure ps-verification" id="settings-verification" open={section === "verification" || undefined}>
        <summary>
          <span>
            <strong>{t("Verification details")}</strong>
            {/* Design: "Next review by {date}" (18.10 re-verification date); else the identity check status. */}
            {reviewDate ? (
              <small>{t("Next review by {date}", { date: formatDate(reviewDate) })}</small>
            ) : kyc.label ? (
              <small>{t("Identity check: {status}", { status: t(kyc.label) })}</small>
            ) : null}
          </span>
          <NiIcon name="chevron-down" />
        </summary>
        <div className="ps-disclosure-body">
          <ol className="ps-check-history">
            <HistoryItem status={t("Done")} title={t("Account created")} tone="done" description={t("Email confirmed and registration terms accepted.")} />
            {account.phoneVerified !== undefined ? (
              <HistoryItem
                description={account.phoneVerified ? t("Confirmed with an SMS code.") : t("Confirm your mobile number with an SMS code.")}
                status={account.phoneVerified ? t("Done") : t("Not done yet")}
                title={t("Phone verified")}
                tone={account.phoneVerified ? "done" : "action"}
              />
            ) : null}
            {kyc.label ? (
              <HistoryItem description={t(kyc.description)} status={t(kyc.label)} title={t("Identity check with Didit")} tone={kyc.tone} />
            ) : null}
            {account.kycStatus ? (
              <HistoryItem
                description={account.financialAccess ? t("You can add funds, invest and withdraw.") : t("Adding funds and investing open after your identity check is approved.")}
                status={account.financialAccess ? t("Open") : t("Not open yet")}
                title={t("Financial access")}
                tone={account.financialAccess ? "done" : "pending"}
              />
            ) : null}
          </ol>
          {!verified ? (
            <div className="ps-update-rows">
              <div className="card-inner">
                <div className="between-center flex-wrap flex-md-nowrap g-3">
                  <div className="bxm-row-text">
                    <h6>{t("Identity verification")}</h6>
                    <p>{t("See the status of your identity check and continue it with Didit when needed.")}</p>
                  </div>
                  <div className="bxm-row-actions">
                    <PortalLink className="btn btn-outline-light" to="kyc">{t("Open verification")}</PortalLink>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </details>

      {/* Design: one row to the accepted agreements in Documents (#/documents/legal). */}
      <PortalLink className="ps-disclosure rss-agreements-link" id="settings-agreements" params={{ tab: "platform" }} to="documents">
        <strong>{t("Accepted agreements")}</strong>
        <span>
          {t("View in Documents")} <NiIcon name="arrow-right" />
        </span>
      </PortalLink>
    </>
  );
}
