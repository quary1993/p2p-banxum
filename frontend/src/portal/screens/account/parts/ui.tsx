// IP of Webby-Soft SRL.
// Building blocks of the U33 Profile & Settings screens (design: main.ps-page): the panel
// (section.ps-panel), its rows (.ps-settings-rows > .card-inner), the green/muted status dot
// (.ps-status), a notice line, and the code/PIN fields and action row of the p73 dialogs.
// Kept in this area (SCREENS_COMMON: new shared primitives go to screens/<area>/parts/).
import { useId, useState, type ReactNode } from "react";

import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import type { SensitivePin } from "../../../../investorPortal/pinState";
import { Button } from "../../../components";

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

/** A password in a p73 dialog (18.5): Show/Hide, the browser's password manager attributes. */
export function PasswordField({
  label,
  value,
  onChange,
  error,
  hint,
  autoComplete = "current-password",
  autoFocus = false
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  hint?: ReactNode;
  autoComplete?: "current-password" | "new-password";
  autoFocus?: boolean;
}) {
  const t = useT();
  const id = useId();
  const [shown, setShown] = useState(false);
  return (
    <div className="acc-code-field acc-password-field">
      <div className="acc-code-label-row">
        <label className="p73-code-label" htmlFor={id}>{label}</label>
        <span className="acc-code-tools">
          <button aria-controls={id} aria-label={shown ? t("Hide password") : t("Show password")} aria-pressed={shown} className="acc-text-button" onClick={() => setShown((current) => !current)} type="button">
            {shown ? t("Hide") : t("Show")}
          </button>
        </span>
      </div>
      <input
        aria-describedby={error || hint ? `${id}-note` : undefined}
        aria-invalid={error ? true : undefined}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        className={`form-control form-control-lg ${error ? "is-invalid" : ""}`.trim()}
        id={id}
        maxLength={128}
        onChange={(event) => onChange(event.target.value)}
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

/**
 * The second factor of an operation next to its email code: the PIN (with the lock notice and
 * "Forgot PIN?"), or, for an investor with an authenticator app, the app code (D-1, 18.5).
 */
export function OperationFactorField({ pin, lockTime }: { pin: SensitivePin; lockTime: string }) {
  const t = useT();
  if (pin.factor === "app") {
    return (
      <>
        {pin.lockedUntil !== null ? (
          <Notice title={t("Authenticator codes paused")} tone="danger">
            {lockTime ? t("Too many wrong codes. You can try again after {time}.", { time: lockTime }) : t("Too many wrong codes. Try again later.")}
          </Notice>
        ) : null}
        <CodeField
          error={pin.error || undefined}
          hint={isFixturePreview ? t("Demo: any 6 digits") : t("The 6-digit code shown in your authenticator app.")}
          label={t("Authenticator code")}
          onChange={pin.setValue}
          value={pin.value}
        />
      </>
    );
  }
  return (
    <>
      {pin.lockedUntil !== null ? (
        <Notice action={<Button onClick={pin.openForgot} size="sm">{t("Forgot PIN?")}</Button>} title={t("PIN locked")} tone="danger">
          {lockTime
            ? t("Too many wrong PINs. You can try again after {time}, or set a new PIN now.", { time: lockTime })
            : t("Too many wrong PINs. Try again later, or set a new PIN now.")}
        </Notice>
      ) : null}
      <PinCodeField
        aside={pin.lockedUntil === null ? <button className="acc-text-button" onClick={pin.openForgot} type="button">{t("Forgot PIN?")}</button> : null}
        disabled={pin.lockedUntil !== null}
        error={pin.error || undefined}
        hint={isFixturePreview ? t("Demo: any 6 digits that are not all the same or a straight run") : t("The 6-digit PIN of your account.")}
        label={t("PIN")}
        onChange={pin.setValue}
        value={pin.value}
      />
    </>
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
