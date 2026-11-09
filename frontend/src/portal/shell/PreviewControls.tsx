// IP of Webby-Soft SRL.
// Preview mode only (VITE_PREVIEW fixtures): a small floating panel for reviewers, out of the design's
// header. "UX state" switches the fixture account state; Appearance and Number format preview the
// investor preferences that Profile & Settings -> Preferences will offer (slice S5).
import { useState } from "react";

import { useT } from "../../i18n";
import { useNumberFormat, type NumberFormat } from "../../investorPortal/format";
import type { DemoAccountState } from "../../investorPortal/types";
import { useAppearance, type Appearance } from "../appearance";

const STATES: Array<[DemoAccountState, string]> = [
  ["active", "Active investor"],
  ["kyc_pending", "KYC pending"],
  ["frozen", "Day-60 freeze"],
  ["restricted", "Restricted account"],
  ["no_pin", "No PIN yet"]
];

export function PreviewControls({ state, onStateChange }: { state: DemoAccountState; onStateChange: (state: DemoAccountState) => void }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const { appearance, setAppearance } = useAppearance();
  const { format, setFormat } = useNumberFormat();
  return (
    <div className={`u33-preview-controls ${open ? "is-open" : ""}`.trim()}>
      <button aria-expanded={open} className="u33-preview-toggle" onClick={() => setOpen((value) => !value)} type="button">
        {t("Preview")}
      </button>
      {open ? (
        <div className="u33-preview-panel" role="group" aria-label={t("Preview controls")}>
          <label>
            <span>{t("UX state")}</span>
            <select aria-label={t("UX state")} onChange={(event) => onStateChange(event.target.value as DemoAccountState)} value={state}>
              {STATES.map(([value, label]) => <option key={value} value={value}>{t(label)}</option>)}
            </select>
          </label>
          <label>
            <span>{t("Appearance")}</span>
            <select aria-label={t("Appearance")} onChange={(event) => setAppearance(event.target.value as Appearance)} value={appearance}>
              <option value="light">{t("Light")}</option>
              <option value="dark">{t("Dark")}</option>
            </select>
          </label>
          <label>
            <span>{t("Number format")}</span>
            <select aria-label={t("Number format")} onChange={(event) => setFormat(event.target.value as NumberFormat)} value={format}>
              <option value="european">{t("European")} 1.234,56</option>
              <option value="swiss">{t("Swiss")} 1’234.56</option>
            </select>
          </label>
        </div>
      ) : null}
    </div>
  );
}
