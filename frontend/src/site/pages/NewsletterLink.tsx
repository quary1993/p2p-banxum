// IP of Webby-Soft SRL.
/*
 * The two newsletter email links (not in the design): /newsletter/confirm?token=... (double
 * opt-in) and /newsletter/unsubscribe?token=... (one click). Built from the design's blocks: the
 * page head and a site box with a short text. The token is posted once, on arrival (a ref keeps
 * StrictMode's second effect run from posting it again); a link without a token is not valid.
 */
import { useCallback, useEffect, useRef, useState, type MouseEvent } from "react";

import { PageHead, SiteLink } from "../components";
import { useSiteNav } from "../context";
import { errorDetail, fieldErrors, useNewsletterConfirm, useNewsletterUnsubscribe } from "../data";
import { ApiClientError } from "../../api/client/httpClient";

type Kind = "confirm" | "unsubscribe";
type Outcome = { status: "pending" } | { status: "done" } | { status: "error"; error: unknown };

const TEXTS: Record<Kind, { pending: string; done: string; doneText: string }> = {
  confirm: {
    pending: "Confirming your subscription…",
    done: "Your subscription is confirmed.",
    doneText: "Once or twice a month, when new projects open. You can unsubscribe with one click."
  },
  unsubscribe: {
    pending: "Unsubscribing…",
    done: "You are unsubscribed.",
    doneText: "You will not get new projects by email any more."
  }
};

/** The answer for a token the server does not accept (400 invalid_token). */
function isInvalidToken(error: unknown) {
  if (!(error instanceof ApiClientError) || error.status !== 400) return false;
  const payload = error.payload as { code?: unknown } | null;
  return payload?.code === "invalid_token" || Boolean(fieldErrors(error).token);
}

/** To the newsletter block of the home page (its email field), from any page. */
function useSubscribeAgain() {
  const { navigate } = useSiteNav();
  return (event: MouseEvent<HTMLAnchorElement>) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    navigate("/");
    window.setTimeout(() => {
      const input = document.getElementById("site-sub-home");
      input?.scrollIntoView({ block: "center" });
      input?.focus({ preventScroll: true });
    }, 0);
  };
}

export function NewsletterLinkPage({ kind }: { kind: Kind }) {
  const { query } = useSiteNav();
  const token = (query.get("token") ?? "").trim();
  const confirm = useNewsletterConfirm();
  const unsubscribe = useNewsletterUnsubscribe();
  const send = (kind === "confirm" ? confirm : unsubscribe).mutateAsync;
  // The outcome is kept here, not read from the mutation: StrictMode's second effect run
  // detaches the mutation observer from the call already made, which would stay "pending".
  const [outcome, setOutcome] = useState<Outcome>({ status: "pending" });
  const posted = useRef(false);
  const subscribeAgain = useSubscribeAgain();
  const texts = TEXTS[kind];

  const post = useCallback(() => {
    setOutcome({ status: "pending" });
    send({ token }).then(
      () => setOutcome({ status: "done" }),
      (error: unknown) => setOutcome({ status: "error", error })
    );
  }, [send, token]);

  useEffect(() => {
    if (!token || posted.current) return;
    posted.current = true;
    post();
  }, [post, token]);

  let box;
  if (!token || (outcome.status === "error" && isInvalidToken(outcome.error))) {
    box = (
      <>
        <h2 className="site-h4">This link is not valid or has expired.</h2>
        <p className="site-text mb-0">
          <a href="/#site-sub-home" onClick={subscribeAgain}>
            Subscribe again
          </a>
        </p>
      </>
    );
  } else if (outcome.status === "error") {
    box = (
      <>
        <h2 className="site-h4">Something went wrong.</h2>
        <p className="site-text">{errorDetail(outcome.error, "Please try again in a moment.")}</p>
        <div className="site-actions">
          <button className="btn btn-lg btn-primary" onClick={post} type="button">
            Try again
          </button>
        </div>
      </>
    );
  } else if (outcome.status === "done") {
    box = (
      <>
        <h2 className="site-h4">{texts.done}</h2>
        <p className={kind === "confirm" ? "site-text" : "site-text mb-0"}>{texts.doneText}</p>
        {kind === "confirm" ? (
          <div className="site-actions">
            <SiteLink className="btn btn-lg btn-primary" href="/projects">
              See open projects
            </SiteLink>
          </div>
        ) : null}
      </>
    );
  } else {
    box = <p className="site-text mb-0">{texts.pending}</p>;
  }

  return (
    <>
      <PageHead eyebrow="Newsletter" title="New projects by email" />
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
