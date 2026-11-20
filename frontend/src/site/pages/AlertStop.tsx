// IP of Webby-Soft SRL.
/*
 * Q14 (2026-11-13): /alerts/stop?token=... from the "Stop these alerts" link of a Smart Invest,
 * "Tell me when it opens" or "Save for later" email. No sign-in. The token is posted once, on
 * arrival (link scanners that only fetch the page stop nothing), and the page says exactly what
 * stopped. Built like the newsletter link pages (page head and a site box).
 */
import { useCallback, useEffect, useRef, useState } from "react";

import type { AlertStopResult } from "../../api/generated/banxumApi";
import { ApiClientError } from "../../api/client/httpClient";
import { PageHead, SiteLink } from "../components";
import { useSiteNav } from "../context";
import { errorDetail, useAlertStop } from "../data";

type Outcome = { status: "pending" } | { status: "done"; result: AlertStopResult } | { status: "error"; error: unknown };

const TITLES: Record<AlertStopResult["kind"], string> = {
  smart_invest: "Smart Invest emails stopped",
  opening_alert: "Opening alert stopped",
  saved_reminder: "Reminder emails stopped"
};

function isInvalidToken(error: unknown) {
  if (!(error instanceof ApiClientError) || error.status !== 400) return false;
  return (error.payload as { code?: unknown } | null)?.code === "invalid_token";
}

export function AlertStop() {
  const { query } = useSiteNav();
  // Read once: the token is then removed from the address bar and the history (audit step 1,
  // D5), so a copied link or a referrer does not carry it.
  const [token] = useState(() => (query.get("token") ?? "").trim());
  const stop = useAlertStop().mutateAsync;
  const [outcome, setOutcome] = useState<Outcome>({ status: "pending" });
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

  let box;
  if (!token || (outcome.status === "error" && isInvalidToken(outcome.error))) {
    box = (
      <>
        <h2 className="site-h4">This link is not valid or is too old.</h2>
        <p className="site-text mb-0">Sign in and change your alerts in the platform.</p>
        <div className="site-actions">
          <SiteLink className="btn btn-lg btn-primary" href="/login">Log in</SiteLink>
        </div>
      </>
    );
  } else if (outcome.status === "error") {
    box = (
      <>
        <h2 className="site-h4">Something went wrong.</h2>
        <p className="site-text">{errorDetail(outcome.error, "Please try again in a moment.")}</p>
        <div className="site-actions">
          <button className="btn btn-lg btn-primary" onClick={post} type="button">Try again</button>
        </div>
      </>
    );
  } else if (outcome.status === "done") {
    box = (
      <>
        <h2 className="site-h4">{TITLES[outcome.result.kind]}</h2>
        <p className="site-text mb-0">{outcome.result.message}</p>
      </>
    );
  } else {
    box = <p className="site-text mb-0">Stopping these alerts…</p>;
  }

  return (
    <>
      <PageHead eyebrow="Alerts" title="Stop these alerts" />
      <section className="site-section no-rule" style={{ paddingTop: 0 }}>
        <div className="site-wrap">
          <div className="site-box is-ink-rule site-narrow" role="status">
            {box}
          </div>
        </div>
      </section>
    </>
  );
}
