// IP of Webby-Soft SRL.
// The U33 layout of the screens outside the investor app (design: create-account module, .u04-account
// > .ca-shell): header with the logo, "Back to website", the Light/Dark switch and the language, the
// optional registration step bar, the centred card and the footer. Used by sign-in, registration,
// the post-login "Create your PIN" screen and the Didit return page. Mounts U33Skin layout="auth".
import "../account.css";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { useV1AuthMeRetrieve } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { INTERFACE_LANGUAGES, isMultilanguageEnabled, parseInterfaceLanguage, usePreferredLanguage } from "../../../../i18n/language";
import { isFixturePreview } from "../../../../investorPortal/data";
import { useSetInterfaceLanguage } from "../../../../investorPortal/languagePreference";
import { useAppearance } from "../../../appearance";
import { brandDisplayName, isBanxumBrand, operatorName } from "../../../brand";
import { PortalLink, usePortalNav } from "../../../components";
import { U33Skin } from "../../../U33Skin";

// Nioicon glyphs as the create-account module writes them (<i class="ca-icon">glyph</i>). "document"
// uses file-text: the design's own document glyph is not in the U33 Nioicon subset.
const GLYPHS = {
  mail: "",
  phone: "",
  shield: "",
  check: "",
  checkCircle: "",
  right: "",
  left: "",
  lock: "",
  user: "",
  document: "",
  clock: "",
  sun: "",
  moon: "",
  help: "",
  external: "",
  alert: ""
} as const;
export type CaIconName = keyof typeof GLYPHS;

export function CaIcon({ name }: { name: CaIconName }) {
  return <i aria-hidden="true" className="ca-icon">{GLYPHS[name]}</i>;
}

/** The registration steps of the design: details, email & phone, PIN, identity. */
const REGISTER_STEPS = ["Your details", "Email & phone", "Security PIN", "Identity"] as const;

function Journey({ current, done }: { current: number; done: boolean }) {
  const t = useT();
  const stateOf = (index: number) => (done || index < current ? "ca-complete" : index === current ? "ca-current" : "");
  return (
    <>
      <ol aria-label={t("Registration steps")} className="ca-journey">
        {REGISTER_STEPS.map((label, index) => (
          <li aria-current={index === current && !done ? "step" : undefined} className={stateOf(index)} key={label}>
            <span className="ca-step-circle">{done || index < current ? <CaIcon name="check" /> : index + 1}</span>
            <span>{t(label)}</span>
          </li>
        ))}
      </ol>
      <div className="ca-mobile-progress">
        <div className="ca-meta">
          <span>{t("Step {step} of {count}", { step: current + 1, count: REGISTER_STEPS.length })}</span>
          <span>{t(REGISTER_STEPS[current])}</span>
        </div>
        <div aria-hidden="true" className="ca-tracks">
          {REGISTER_STEPS.map((label, index) => <span className={stateOf(index)} key={label} />)}
        </div>
      </div>
    </>
  );
}

/**
 * The logo leads to the main page: the Overview for a signed-in investor, the public home page
 * otherwise. Reads the session the page already has and never refetches a failed check on mount: a
 * refetch here resets the portal's session gate, which remounts the login screen in a loop (audit A-03).
 */
function BrandHomeLink() {
  const t = useT();
  const authMe = useV1AuthMeRetrieve({
    query: { enabled: !isFixturePreview, retry: false, retryOnMount: false, refetchOnMount: false, refetchOnWindowFocus: false, staleTime: 60_000 }
  });
  const user = authMe.data?.user;
  const signedIn = Boolean(user) && !["admin", "superadmin"].includes(user?.account_type ?? "");
  const brand = brandDisplayName();
  return (
    <PortalLink aria-label={signedIn ? t("{brand} overview", { brand }) : t("{brand} home", { brand })} className="ca-brand-link" to={signedIn ? "dashboard" : "public"}>
      {isBanxumBrand() ? <img alt="" className="ca-logo" src="/brand/banxum-logo.svg" /> : <span className="ca-brand-text">{brand}</span>}
    </PortalLink>
  );
}

export function AuthLayout({ children, step, stepsDone = false }: { children: ReactNode; step?: number; stepsDone?: boolean }) {
  const t = useT();
  const nav = usePortalNav();
  const { appearance, setAppearance } = useAppearance();
  const language = usePreferredLanguage();
  const setLanguage = useSetInterfaceLanguage();
  const brand = brandDisplayName();
  return (
    <U33Skin layout="auth">
      <div className="u04-account">
        <div className={step === undefined ? "ca-shell acc-no-journey" : "ca-shell"}>
          <header className="ca-site-head">
            <BrandHomeLink />
            <div className="ca-tools">
              <a
                className="ca-head-back"
                href={nav.hrefFor("public")}
                onClick={(event) => {
                  if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                  event.preventDefault();
                  nav.go("public");
                }}
              >
                <CaIcon name="left" />
                {t("Back to website")}
              </a>
              <button
                aria-label={appearance === "dark" ? t("Switch to Light") : t("Switch to Dark")}
                className="ca-theme"
                onClick={() => setAppearance(appearance === "dark" ? "light" : "dark")}
                type="button"
              >
                <CaIcon name={appearance === "dark" ? "sun" : "moon"} />
              </button>
              {/* U33-DEC-31: saved in this browser now and in the account after sign-in. Hidden while
                  multilanguage is paused (IMPLEMENTATION_PLAN 18.0). */}
              {isMultilanguageEnabled() ? <select
                aria-label={t("Language")}
                onChange={(event) => {
                  const next = parseInterfaceLanguage(event.target.value);
                  if (next) setLanguage(next);
                }}
                value={language}
              >
                {INTERFACE_LANGUAGES.map((option) => (
                  <option key={option.value} lang={option.value} value={option.value}>{option.short}</option>
                ))}
              </select> : null}
            </div>
          </header>
          {step !== undefined ? <Journey current={step} done={stepsDone} /> : null}
          <main>{children}</main>
          <footer className="ca-page-foot">
            <span>{t("{brand} · A brand of {operator}", { brand, operator: operatorName })}</span>
            <a href="/help">
              <CaIcon name="help" />
              {t("Help")}
            </a>
            <a href="/legal/privacy">{t("Privacy")}</a>
          </footer>
        </div>
      </div>
    </U33Skin>
  );
}

/** One screen of the flow: the narrow card with its feature icon, title and intro (design: .ca-card.ca-narrow). */
export function AuthCard({ icon, success = false, title, intro, children, wide = false, testId }: { icon?: CaIconName; success?: boolean; title: ReactNode; intro?: ReactNode; children?: ReactNode; wide?: boolean; testId?: string }) {
  return (
    <div className={wide ? "ca-card ca-details-form" : "ca-card ca-narrow"} data-testid={testId}>
      {icon ? (
        <div className={`ca-feature-icon ${success ? "ca-success" : ""}`.trim()}>
          <CaIcon name={icon} />
        </div>
      ) : null}
      <h1>{title}</h1>
      {intro ? <p className="ca-intro">{intro}</p> : null}
      {children}
    </div>
  );
}

/** "Sent to / Your mobile" box (design: .ca-recipient), with an optional Change button. */
export function Recipient({ icon, label, value, action }: { icon: CaIconName; label: ReactNode; value: ReactNode; action?: ReactNode }) {
  return (
    <div className="ca-recipient">
      <CaIcon name={icon} />
      <div>
        <small>{label}</small>
        <strong>{value}</strong>
      </div>
      {action}
    </div>
  );
}

/**
 * Six code cells over one numeric input (design: .ca-code-field): SMS code or PIN. A PIN is masked
 * with dots and has Show/Hide.
 */
export function CaCodeField({ id, label, value, onChange, masked = false, autoFocus = false, disabled = false, describedBy }: { id: string; label: string; value: string; onChange: (value: string) => void; masked?: boolean; autoFocus?: boolean; disabled?: boolean; describedBy?: string }) {
  const t = useT();
  const inputRef = useRef<HTMLInputElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);
  const digits = value.slice(0, 6);
  return (
    <div className="ca-code-field">
      <div className="ca-pin-label">
        <label htmlFor={id}>{label}</label>
        {masked ? (
          <button aria-label={shown ? t("Hide {label}", { label }) : t("Show {label}", { label })} aria-pressed={shown} onClick={() => setShown(!shown)} type="button">
            {shown ? t("Hide") : t("Show")}
          </button>
        ) : null}
      </div>
      <div className="ca-code-entry">
        <div aria-hidden="true" className="ca-code-cells">
          {Array.from({ length: 6 }, (_, index) => (
            <span key={index}>{digits[index] ? (masked && !shown ? "•" : digits[index]) : ""}</span>
          ))}
        </div>
        <input
          aria-describedby={describedBy}
          autoComplete={masked ? "new-password" : "one-time-code"}
          disabled={disabled}
          id={id}
          inputMode="numeric"
          maxLength={6}
          name={id}
          onChange={(event) => onChange(event.target.value.replace(/\D/g, "").slice(0, 6))}
          pattern="[0-9]{6}"
          ref={inputRef}
          type={masked && !shown ? "password" : "text"}
          value={digits}
        />
      </div>
    </div>
  );
}

/** The design's error line (.ca-error); empty renders nothing visible. */
export function CaError({ id, children }: { id?: string; children?: ReactNode }) {
  return (
    <div className="ca-error" id={id} role="alert" tabIndex={-1}>
      {children}
    </div>
  );
}

/** A native <dialog> as the create-account module uses it (company, help, provider notes). */
export function CaDialog({ title, onClose, children }: { title: ReactNode; onClose: () => void; children: ReactNode }) {
  const t = useT();
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return undefined;
    try {
      if (typeof dialog.showModal === "function" && !dialog.open) dialog.showModal();
      else dialog.setAttribute("open", "");
    } catch {
      dialog.setAttribute("open", "");
    }
    return () => {
      try {
        if (typeof dialog.close === "function" && dialog.open) dialog.close();
      } catch {
        // Already closed.
      }
    };
  }, []);
  return (
    <dialog aria-labelledby="ca-modal-title" onCancel={(event) => { event.preventDefault(); onClose(); }} ref={ref}>
      <h2 id="ca-modal-title">{title}</h2>
      {children}
      <button className="ca-secondary" onClick={onClose} type="button">{t("Close")}</button>
    </dialog>
  );
}

/** A waiting state in the auth layout ("Checking your session"). */
export function AuthLoading({ title }: { title: string }) {
  const t = useT();
  return (
    <AuthLayout>
      <AuthCard icon="clock" title={title}>
        <p className="ca-email-note" role="status">{t("One moment, please.")}</p>
      </AuthCard>
    </AuthLayout>
  );
}
