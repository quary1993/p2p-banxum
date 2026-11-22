// IP of Webby-Soft SRL.
// Profile & Settings -> Preferences (design: Display panel with Appearance, Language, Number format and
// Time zone, then "Close your account"). Appearance is saved per browser; the language (U33-DEC-31,
// English or Deutsch) and the number format (U33-DEC-32) apply at once and are saved in the account;
// one time reference, Europe/Zurich, no selector. "Close account" sends a closure request to the team
// (U33-DEC-28): the receipt (reference and email) is not the closure itself, which is confirmed by
// a separate email after the team's checks.
import { useState } from "react";

import { useQueryClient } from "@tanstack/react-query";

import {
  getV1AuthMeRetrieveQueryKey,
  useV1AuthPreferencesDisplayPartialUpdate,
  useV1InvestorPortalSupportRequestsCreate,
  type InvestorSupportRequestReceipt
} from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { INTERFACE_LANGUAGES, isMultilanguageEnabled, parseInterfaceLanguage, usePreferredLanguage } from "../../../../i18n/language";
import { isFixturePreview } from "../../../../investorPortal/data";
import { useNumberFormat, type NumberFormat } from "../../../../investorPortal/format";
import { useSetInterfaceLanguage } from "../../../../investorPortal/languagePreference";
import { useAppearance, type Appearance } from "../../../appearance";
import { Dialog, NiIcon } from "../../../components";
import { errorMessage, idempotencyKey } from "../../portfolio/parts/errors";
import { supportEmail } from "../accountLinks";
import { PsPanel, SettingsRow } from "../parts/ui";
import type { AccountData } from "./useAccountData";

const APPEARANCE_OPTIONS: Array<[Appearance, string]> = [["light", "Light"], ["dark", "Dark"]];
const NUMBER_FORMAT_OPTIONS: Array<[NumberFormat, string, string]> = [
  ["european", "European", "1.234,56"],
  ["swiss", "Swiss", "1’234.56"]
];

function CloseAccountDialog({ onClose }: { onClose: () => void }) {
  const t = useT();
  const [requestKey] = useState(() => idempotencyKey("account-closure"));
  const [receipt, setReceipt] = useState<InvestorSupportRequestReceipt | null>(null);
  const [previewSent, setPreviewSent] = useState(false);
  const mutation = useV1InvestorPortalSupportRequestsCreate();
  const send = () => {
    if (isFixturePreview) {
      setPreviewSent(true);
      return;
    }
    mutation.mutate({ data: { kind: "account_closure", idempotency_key: requestKey } }, { onSuccess: setReceipt });
  };
  if (receipt || previewSent) {
    return (
      <Dialog className="p73-modal" onClose={onClose} size="sm" title={t("Request account closure")}>
        <div className="hp-message-result" role="status">
          <NiIcon name="mail" />
          <h3>{t("Request received")}</h3>
          {receipt ? (
            <>
              <p>{t("Your reference is {reference}.", { reference: receipt.reference })}</p>
              <p>{t("Your account is not closed yet. We sent a confirmation to {email}, and we write again when the account is closed.", { email: receipt.receipt_email })}</p>
            </>
          ) : (
            <p>{t("Demo: nothing was sent.")}</p>
          )}
          <button className="btn btn-primary" onClick={onClose} type="button">{t("Done")}</button>
        </div>
      </Dialog>
    );
  }
  return (
    <Dialog busy={mutation.isPending} className="p73-modal" onClose={onClose} size="sm" title={t("Request account closure")}>
      <p className="p73-intro">{t("Closing an account starts with a request to our team. We check your balances, investments and any open obligations first, and we confirm by email when the account is closed.")}</p>
      <ul className="acc-close-list">
        <li>{t("Receiving your request does not close the account yet.")}</li>
        <li>{t("Investments that are still running and money in your account are settled first.")}</li>
        <li>{t("Records that the law requires, and those needed to settle open obligations, are kept.")}</li>
      </ul>
      {mutation.isError ? (
        <p className="hp-message-error" role="alert">
          {t("Your request was not sent: {reason}", { reason: errorMessage(mutation.error) })} {t("Try again, or write to {email}.", { email: supportEmail })}
        </p>
      ) : null}
      <div className="p73-modal-actions">
        <button className="btn p73-back" onClick={onClose} type="button">{t("Cancel")}</button>
        <button className="btn p73-next" disabled={mutation.isPending} onClick={send} type="button">
          {mutation.isPending ? t("Sending...") : mutation.isError ? t("Try again") : t("Send closure request")}
        </button>
      </div>
    </Dialog>
  );
}

export function PreferencesTab({ account }: { account: AccountData }) {
  const t = useT();
  const { appearance, setAppearance } = useAppearance();
  const { format, setFormat: setLocalFormat } = useNumberFormat();
  const [closing, setClosing] = useState(false);
  const queryClient = useQueryClient();
  const saveFormat = useV1AuthPreferencesDisplayPartialUpdate();
  const language = usePreferredLanguage();
  const setLanguage = useSetInterfaceLanguage();
  // U33-DEC-32: the choice applies at once and is saved in the account (all devices, emails, reports).
  const setFormat = (next: NumberFormat) => {
    setLocalFormat(next);
    if (isFixturePreview || account.readonly) return;
    saveFormat.mutate({ data: { number_format: next } }, { onSuccess: () => void queryClient.invalidateQueries({ queryKey: getV1AuthMeRetrieveQueryKey() }) });
  };
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
          {/* Hidden while multilanguage is paused (IMPLEMENTATION_PLAN 18.0). */}
          {isMultilanguageEnabled() ? <SettingsRow
            actions={
              <select
                aria-label={t("Language")}
                className="form-select bxm-row-select"
                onChange={(event) => {
                  const next = parseInterfaceLanguage(event.target.value);
                  if (next) setLanguage(next);
                }}
                value={language}
              >
                {/* Each language is named in its own language (design). */}
                {INTERFACE_LANGUAGES.map((option) => (
                  <option key={option.value} lang={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            }
            title={t("Language")}
          /> : null}
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
      {closing ? <CloseAccountDialog onClose={() => setClosing(false)} /> : null}
    </>
  );
}
