// IP of Webby-Soft SRL.
// Building blocks of the U33 Profile & Settings screens (design: main.ps-page): the panel
// (section.ps-panel), its rows (.ps-settings-rows > .card-inner), the green/muted status dot
// (.ps-status), a notice line, and the code/PIN fields and action row of the p73 dialogs.
// Kept in this area (SCREENS_COMMON: new shared primitives go to screens/<area>/parts/).
import { useId, useState, type ReactNode } from "react";

import { useT } from "../../../../i18n";

/** section.ps-panel with its header (title and an optional status on the right). */
export function PsPanel({ title, status, className = "", children }: { title: ReactNode; status?: ReactNode; className?: string; children: ReactNode }) {
  const headingId = useId();
  return (
    <section aria-labelledby={headingId} className={`ps-panel ${className}`.trim()}>
      <header className="ps-panel-head">
        <h2 id={headingId}>{title}</h2>
        {status}
      </header>
      {children}
    </section>
  );
}

/** One row of a panel: title and description on the left, a note and actions on the right. */
export function SettingsRow({
  title,
  titleExtra,
  description,
  note,
  actions,
  className = ""
}: {
  title: ReactNode;
  titleExtra?: ReactNode;
  description?: ReactNode;
  note?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`card-inner ${className}`.trim()}>
      <div className="between-center flex-wrap flex-md-nowrap g-3">
        <div className="bxm-row-text">
          <h6>{title}{titleExtra ? <> {titleExtra}</> : null}</h6>
          {description ? <p>{description}</p> : null}
        </div>
        {note || actions ? (
          <div className="bxm-row-actions">
            {note ? <span className="bxm-row-note">{note}</span> : null}
            {actions}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/** The design's status with a dot: green ("Verified", "On") or muted ("Pending verification"). */
export function PsStatus({ muted = false, children }: { muted?: boolean; children: ReactNode }) {
  return (
    <span className={`ps-status ${muted ? "is-muted" : ""}`.trim()}>
      <i aria-hidden="true" />
      {children}
    </span>
  );
}

/** A short notice line (saved, could not save...). `role` makes it announced. */
export function Notice({ tone = "info", title, children, action }: { tone?: "info" | "success" | "danger" | "warning"; title?: ReactNode; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className={`acc-notice alert-${tone}`} role={tone === "danger" ? "alert" : "status"}>
      <div>
        {title ? <strong>{title}</strong> : null}
        {children ? <p>{children}</p> : null}
      </div>
      {action}
    </div>
  );
}

/**
 * A 6-digit code field of the p73 dialogs (email code, SMS code): label, the large spaced input
 * (.p73-code), an optional "Send code" button and the error line.
 */
export function CodeField({
  label,
  value,
  onChange,
  error,
  hint,
  requestLabel,
  requestDisabled = false,
  onRequest,
  autoFocus = false
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  hint?: ReactNode;
  requestLabel?: string;
  requestDisabled?: boolean;
  onRequest?: () => void;
  autoFocus?: boolean;
}) {
  const id = useId();
  return (
    <div className="acc-code-field">
      <div className="acc-code-label-row">
        <label className="p73-code-label" htmlFor={id}>{label}</label>
        {requestLabel && onRequest ? (
          <button className="acc-text-button" disabled={requestDisabled} onClick={onRequest} type="button">{requestLabel}</button>
        ) : null}
      </div>
      <input
        aria-describedby={error || hint ? `${id}-note` : undefined}
        aria-invalid={error ? true : undefined}
        autoComplete="one-time-code"
        autoFocus={autoFocus}
        className={`form-control form-control-lg bxm-otp p73-code ${error ? "is-invalid" : ""}`.trim()}
        id={id}
        inputMode="numeric"
        maxLength={6}
        onChange={(event) => onChange(event.target.value.replace(/\D/g, "").slice(0, 6))}
        placeholder="000000"
        value={value}
      />
      {error ? (
        <div className="invalid-feedback" id={`${id}-note`} role="alert">{error}</div>
      ) : hint ? (
        <p className="acc-field-hint" id={`${id}-note`}>{hint}</p>
      ) : null}
    </div>
  );
}

/** The 6-digit PIN in a p73 dialog: masked like a password, with Show/Hide and optional extra link. */
export function PinCodeField({
  label,
  value,
  onChange,
  error,
  hint,
  disabled = false,
  autoFocus = false,
  aside
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  hint?: ReactNode;
  disabled?: boolean;
  autoFocus?: boolean;
  aside?: ReactNode;
}) {
  const t = useT();
  const id = useId();
  const [shown, setShown] = useState(false);
  return (
    <div className="acc-code-field">
      <div className="acc-code-label-row">
        <label className="p73-code-label" htmlFor={id}>{label}</label>
        <span className="acc-code-tools">
          <button aria-label={shown ? t("Hide {label}", { label }) : t("Show {label}", { label })} aria-pressed={shown} className="acc-text-button" disabled={disabled} onClick={() => setShown((current) => !current)} type="button">
            {shown ? t("Hide") : t("Show")}
          </button>
          {aside}
        </span>
      </div>
      <input
        aria-describedby={error || hint ? `${id}-note` : undefined}
        aria-invalid={error ? true : undefined}
        autoComplete="off"
        autoFocus={autoFocus}
        className={`form-control form-control-lg bxm-otp p73-code ${error ? "is-invalid" : ""}`.trim()}
        disabled={disabled}
        id={id}
        inputMode="numeric"
        maxLength={6}
        onChange={(event) => onChange(event.target.value.replace(/\D/g, "").slice(0, 6))}
        placeholder="••••••"
        type={shown ? "text" : "password"}
        value={value}
      />
      {error ? (
        <div className="invalid-feedback" id={`${id}-note`} role="alert">{error}</div>
      ) : hint ? (
        <p className="acc-field-hint" id={`${id}-note`}>{hint}</p>
      ) : null}
    </div>
  );
}

/** Cancel + primary action of a p73 dialog. */
export function DialogActions({
  onCancel,
  cancelLabel,
  primaryLabel,
  onPrimary,
  primaryDisabled = false,
  primaryType = "button"
}: {
  onCancel?: () => void;
  cancelLabel?: string;
  primaryLabel: string;
  onPrimary?: () => void;
  primaryDisabled?: boolean;
  primaryType?: "button" | "submit";
}) {
  const t = useT();
  return (
    <div className="p73-modal-actions">
      {onCancel ? <button className="btn p73-back" onClick={onCancel} type="button">{cancelLabel ?? t("Cancel")}</button> : null}
      <button className="btn p73-next" disabled={primaryDisabled} onClick={onPrimary} type={primaryType}>{primaryLabel}</button>
    </div>
  );
}
