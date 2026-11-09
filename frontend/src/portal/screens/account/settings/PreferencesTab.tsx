// IP of Webby-Soft SRL.
// Profile & Settings -> Preferences (design: Display panel with Appearance, Language, Number format and
// Time zone, then "Close your account"). Appearance and number format are saved per browser (S1
// hooks); English is the only language until Phase 17.8 (U33-DEC-31); one time reference,
// Europe/Zurich, no selector (U33-DEC-32). "Close account" sends a closure request to support by
// email until the request endpoint exists (U33-DEC-28): the request is not the closure itself.
import { useState } from "react";

import { useT } from "../../../../i18n";
import { useNumberFormat, type NumberFormat } from "../../../../investorPortal/format";
import { useAppearance, type Appearance } from "../../../appearance";
import { brandDisplayName } from "../../../brand";
import { Dialog } from "../../../components";
import { supportMailto } from "../accountLinks";
import { PsPanel, SettingsRow } from "../parts/ui";
import type { AccountData } from "./useAccountData";

const APPEARANCE_OPTIONS: Array<[Appearance, string]> = [["light", "Light"], ["dark", "Dark"]];
const NUMBER_FORMAT_OPTIONS: Array<[NumberFormat, string, string]> = [
  ["european", "European", "1.234,56"],
  ["swiss", "Swiss", "1’234.56"]
];

function CloseAccountDialog({ account, onClose }: { account: AccountData; onClose: () => void }) {
  const t = useT();
  const brand = brandDisplayName();
  const href = supportMailto({
    subject: t("Account closure request"),
    body: t("Please close my {brand} account.", { brand }),
    reference: account.reference
  });
  return (
    <Dialog className="p73-modal" onClose={onClose} size="sm" title={t("Request account closure")}>
      <p className="p73-intro">{t("Closing an account starts with a request to our team. We check your balances, investments and any open obligations first, and we confirm by email when the account is closed.")}</p>
      <ul className="acc-close-list">
        <li>{t("Receiving your request does not close the account yet.")}</li>
        <li>{t("Investments that are still running and money in your account are settled first.")}</li>
        <li>{t("Records that the law requires, and those needed to settle open obligations, are kept.")}</li>
      </ul>
      <p className="p73-intro">{t("The request is an email to support from your email app, with your investor reference.")}</p>
      <div className="p73-modal-actions">
        <button className="btn p73-back" onClick={onClose} type="button">{t("Cancel")}</button>
        <a className="btn p73-next" href={href} onClick={() => window.setTimeout(onClose, 0)}>{t("Write closure request")}</a>
      </div>
    </Dialog>
  );
}

export function PreferencesTab({ account }: { account: AccountData }) {
  const t = useT();
  const { appearance, setAppearance } = useAppearance();
  const { format, setFormat } = useNumberFormat();
  const [closing, setClosing] = useState(false);
  return (
    <>
      <PsPanel title={t("Display")}>
        <div className="ps-settings-rows">
          <SettingsRow
            actions={
              <div aria-labelledby="p30-appearance-label" className="bxm-seg p30-appearance-options" role="group">
                {APPEARANCE_OPTIONS.map(([value, label]) => (
                  <button aria-pressed={appearance === value} data-p30-theme={value} key={value} onClick={() => setAppearance(value)} type="button">
                    {t(label)}
                  </button>
                ))}
              </div>
            }
            className="p30-appearance-row"
            title={<span id="p30-appearance-label">{t("Appearance")}</span>}
          />
          <SettingsRow
            actions={
              <select aria-label={t("Language")} className="form-select bxm-row-select" onChange={() => undefined} value="en">
                <option value="en">English</option>
                <option disabled value="de">{t("Deutsch · Soon")}</option>
              </select>
            }
            description={t("German is coming soon.")}
            title={t("Language")}
          />
          <SettingsRow
            actions={
              <div aria-label={t("Number format")} className="bxm-seg bxm-number-formats" role="group">
                {NUMBER_FORMAT_OPTIONS.map(([value, label, example]) => (
                  <button aria-pressed={format === value} data-format={value} key={value} onClick={() => setFormat(value)} title={t(label)} type="button">
                    <span className="number-format-label">{t(label)}</span>
                    <span className="number-format-example">{example}</span>
                  </button>
                ))}
              </div>
            }
            title={t("Number format")}
          />
          <SettingsRow note="Europe/Zurich" title={t("Time zone")} />
        </div>
      </PsPanel>
      <section className="ps-close-account">
        <div>
          <h2>{t("Close your account")}</h2>
          <p>{t("You can ask us to close your account. We check your balances, investments and open obligations first; the account is closed only after that check. Records required by law are kept.")}</p>
        </div>
        <button className="btn btn-outline-light" disabled={account.readonly} onClick={() => setClosing(true)} type="button">{t("Close account")}</button>
      </section>
      {closing ? <CloseAccountDialog account={account} onClose={() => setClosing(false)} /> : null}
    </>
  );
}
