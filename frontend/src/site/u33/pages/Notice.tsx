// IP of Webby-Soft SRL.
/*
 * Short public pages in the U33 public design (not in the design; Q24, D-10, built with the
 * legal page hero and a document card, Q23):
 * - the 404 for every unknown address (the bad URL stays in the address bar);
 * - the two newsletter email links: /newsletter/confirm?token=... (double opt-in) and
 *   /newsletter/unsubscribe?token=... (one click);
 * - /alerts/stop?token=... from the "Stop these alerts" link of Smart Invest, opening-alert and
 *   saved-reminder emails (Q14), without sign-in.
 * A token is posted once, on arrival (a ref keeps StrictMode's second effect run from posting it
 * again; link scanners that only fetch the page change nothing); a link without a token is not
 * valid. The alert token is removed from the address bar (audit step 1, D5).
 */
import { useCallback, useEffect, useRef, useState, type MouseEvent, type ReactNode } from "react";

import type { AlertStopResult } from "../../../api/generated/banxumApi";
import { ApiClientError } from "../../../api/client/httpClient";
import { useT } from "../../../i18n";
import { useSiteNav, useSiteTitle } from "../../context";
import { errorDetail, fieldErrors, useAlertStop, useNewsletterConfirm, useNewsletterUnsubscribe } from "../../data";
import { Ni, PublicLink } from "../ui";

function NoticeLayout({ kicker, title, lead, children }: { kicker: string; title: string; lead?: string; children?: ReactNode }) {
  return (
    <div className="content-shell legal-view bxp-notice">
      <section aria-labelledby="notice-title" className="page-hero legal-hero">
        <p className="page-kicker">{kicker}</p>
        <h1 className="page-title" id="notice-title">
          {title}
        </h1>
        {lead ? <p className="page-lead">{lead}</p> : null}
      </section>
      {children ? (
        <div className="bxp-notice-card" role="status">
          {children}
        </div>
      ) : null}
    </div>
  );
}

export function NotFound() {
  const t = useT();
  useSiteTitle(t("Not found"));
  return (
    <NoticeLayout kicker="404" lead={t("The link may be old, or the project may have been removed.")} title={t("This page does not exist")}>
      <div className="bxp-actions">
        <PublicLink className="button-primary" href="/">
          {t("Home")} <Ni glyph="arrow" />
        </PublicLink>
        <PublicLink className="text-link" href="/projects">
          {t("All projects")} <Ni glyph="arrow" />
        </PublicLink>
      </div>
    </NoticeLayout>
  );
}

// ---------------------------------------------------------------------------------------------
// Newsletter links

type NewsletterKind = "confirm" | "unsubscribe";
type Outcome<T> = { status: "pending" } | { status: "done"; result: T } | { status: "error"; error: unknown };

/** The answer for a token the server does not accept (400 invalid_token). */
function isInvalidNewsletterToken(error: unknown) {
  if (!(error instanceof ApiClientError) || error.status !== 400) return false;
  const payload = error.payload as { code?: unknown } | null;
  return payload?.code === "invalid_token" || Boolean(fieldErrors(error).token);
}

/** To the newsletter sign-up of All projects (its email field), from any page. */
function useSubscribeAgain() {
  const { navigate } = useSiteNav();
  return (event: MouseEvent<HTMLAnchorElement>) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate("/projects");
    window.setTimeout(() => {
      const input = document.getElementById("bxp-subscribe-projects");
      input?.scrollIntoView({ block: "center" });
      input?.focus({ preventScroll: true });
    }, 0);
  };
}

export function NewsletterLinkPage({ kind }: { kind: NewsletterKind }) {
  const t = useT();
  useSiteTitle(t("New projects by email"));
  const { query } = useSiteNav();
  const token = (query.get("token") ?? "").trim();
  const confirm = useNewsletterConfirm();
  const unsubscribe = useNewsletterUnsubscribe();
  const send = (kind === "confirm" ? confirm : unsubscribe).mutateAsync;
  // The outcome is kept here, not read from the mutation: StrictMode's second effect run
  // detaches the mutation observer from the call already made, which would stay "pending".
  const [outcome, setOutcome] = useState<Outcome<null>>({ status: "pending" });
  const posted = useRef(false);
  const subscribeAgain = useSubscribeAgain();

  const post = useCallback(() => {
    setOutcome({ status: "pending" });
    send({ token }).then(
      () => setOutcome({ status: "done", result: null }),
      (error: unknown) => setOutcome({ status: "error", error })
    );
  }, [send, token]);

  useEffect(() => {
    if (!token || posted.current) return;
    posted.current = true;
    post();
  }, [post, token]);

  let box: ReactNode;
  if (!token || (outcome.status === "error" && isInvalidNewsletterToken(outcome.error))) {
    box = (
      <>
        <h2>{t("This link is not valid or has expired.")}</h2>
        <p>
          <a href="/projects#newsletter" onClick={subscribeAgain}>
            {t("Subscribe again")}
          </a>
        </p>
      </>
    );
  } else if (outcome.status === "error") {
    box = (
      <>
        <h2>{t("Something went wrong.")}</h2>
        <p>{errorDetail(outcome.error, t("Please try again in a moment."))}</p>
        <div className="bxp-actions">
          <button className="button-primary" onClick={post} type="button">
            {t("Try again")}
          </button>
        </div>
      </>
    );
  } else if (outcome.status === "done") {
    box =
      kind === "confirm" ? (
        <>
          <h2>{t("Your subscription is confirmed.")}</h2>
          <p>{t("Once or twice a month, when new projects open. You can unsubscribe with one click.")}</p>
          <div className="bxp-actions">
            <PublicLink className="button-primary" href="/projects">
              {t("See open projects")} <Ni glyph="arrow" />
            </PublicLink>
          </div>
        </>
      ) : (
        <>
          <h2>{t("You are unsubscribed.")}</h2>
          <p>{t("You will not get new projects by email any more.")}</p>
        </>
      );
  } else {
    box = <p>{kind === "confirm" ? t("Confirming your subscription…") : t("Unsubscribing…")}</p>;
  }

  return (
    <NoticeLayout kicker={t("NEWSLETTER")} title={t("New projects by email")}>
      {box}
    </NoticeLayout>
  );
}

// ---------------------------------------------------------------------------------------------
// Stop these alerts (Q14)

const ALERT_TITLES: Record<AlertStopResult["kind"], string> = {
  smart_invest: "Smart Invest emails stopped",
  opening_alert: "Opening alert stopped",
  saved_reminder: "Reminder emails stopped"
};

function isInvalidAlertToken(error: unknown) {
  if (!(error instanceof ApiClientError) || error.status !== 400) return false;
  return (error.payload as { code?: unknown } | null)?.code === "invalid_token";
}

export function AlertStop() {
  const t = useT();
  useSiteTitle(t("Stop these alerts"));
  const { query } = useSiteNav();
  // Read once: the token is then removed from the address bar and the history.
  const [token] = useState(() => (query.get("token") ?? "").trim());
  const stop = useAlertStop().mutateAsync;
  const [outcome, setOutcome] = useState<Outcome<AlertStopResult>>({ status: "pending" });
  const posted = useRef(false);

  const post = useCallback(() => {
    setOutcome({ status: "pending" });
    stop({ token }).then(
      (result) => setOutcome({ status: "done", result }),
      (error: unknown) => setOutcome({ status: "error", error })
    );
  }, [stop, token]);

  useEffect(() => {
    if (!token || posted.current) return;
    posted.current = true;
    if (window.location.search.includes("token=")) {
      window.history.replaceState(window.history.state, "", window.location.pathname);
    }
    post();
  }, [post, token]);

  let box: ReactNode;
  if (!token || (outcome.status === "error" && isInvalidAlertToken(outcome.error))) {
    box = (
      <>
        <h2>{t("This link is not valid or is too old.")}</h2>
        <p>{t("Sign in and change your alerts in the platform.")}</p>
        <div className="bxp-actions">
          <PublicLink className="button-primary" href="/login">
            {t("Log in")} <Ni glyph="arrow" />
          </PublicLink>
        </div>
      </>
    );
  } else if (outcome.status === "error") {
    box = (
      <>
        <h2>{t("Something went wrong.")}</h2>
        <p>{errorDetail(outcome.error, t("Please try again in a moment."))}</p>
        <div className="bxp-actions">
          <button className="button-primary" onClick={post} type="button">
            {t("Try again")}
          </button>
        </div>
      </>
    );
  } else if (outcome.status === "done") {
    box = (
      <>
        <h2>{t(ALERT_TITLES[outcome.result.kind])}</h2>
        <p>{outcome.result.message}</p>
      </>
    );
  } else {
    box = <p>{t("Stopping these alerts…")}</p>;
  }

  return (
    <NoticeLayout kicker={t("ALERTS")} title={t("Stop these alerts")}>
      {box}
    </NoticeLayout>
  );
}
