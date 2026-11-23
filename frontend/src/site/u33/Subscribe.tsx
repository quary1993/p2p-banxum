// IP of Webby-Soft SRL.
/*
 * Newsletter sign-up in the U33 public style (not in the design; Q24 keeps the newsletter, Q14 its
 * rules; built with the U33 form look, Q23). Same behaviour as the October block: email check,
 * double opt-in ("Almost done": the confirmation link is sent), "Use another address".
 */
import { useState, type FormEvent } from "react";

import { useT } from "../../i18n";
import { setNewsletterSubscribed, useNewsletterSubscribed, useSiteToast } from "../context";
import { errorDetail, fieldErrors, useNewsletterSubscribe, type NewsletterSource } from "../data";
import { PublicLink } from "./ui";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function Subscribe({ id, source }: { id: string; source: NewsletterSource }) {
  const t = useT();
  const subscribed = useNewsletterSubscribed();
  const toast = useSiteToast();
  const subscribe = useNewsletterSubscribe();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const inputId = `bxp-subscribe-${id}`;

  if (subscribed) {
    return (
      <p className="bxp-subscribe-done" role="status">
        <strong>{t("Almost done.")}</strong> {t("We sent a confirmation link to {email}. New projects arrive once you confirm.", { email: subscribed })}{" "}
        <button
          className="bxp-text-button"
          onClick={() => {
            subscribe.reset();
            setEmail("");
            setNewsletterSubscribed(null);
          }}
          type="button"
        >
          {t("Use another address")}
        </button>
      </p>
    );
  }

  const showError = (message: string) => {
    setError(message);
    document.getElementById(inputId)?.focus();
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (subscribe.isPending) return;
    const value = email.trim();
    if (!EMAIL_PATTERN.test(value)) {
      showError(t("Enter a valid email address."));
      return;
    }
    subscribe.mutate(
      { email: value, source },
      {
        onSuccess: () => {
          setNewsletterSubscribed(value);
          toast(t("Check your inbox to confirm."));
        },
        onError: (failure) => {
          if (fieldErrors(failure).email) showError(t("Enter a valid email address."));
          else toast(errorDetail(failure, t("Something went wrong. Please try again.")), "ni-alert-circle");
        }
      }
    );
  };

  return (
    <>
      <form className="bxp-subscribe" noValidate onSubmit={onSubmit}>
        <label className="sr-only" htmlFor={inputId}>
          {t("Email address")}
        </label>
        <input
          aria-describedby={error ? `${inputId}-error` : undefined}
          aria-invalid={error ? true : undefined}
          autoComplete="email"
          id={inputId}
          onChange={(event) => {
            setEmail(event.target.value);
            setError(null);
          }}
          placeholder={t("Your email address")}
          required
          type="email"
          value={email}
        />
        <button className="button-primary" disabled={subscribe.isPending} type="submit">
          {t("Get new projects")}
        </button>
      </form>
      {error ? (
        <p className="bxp-field-error" id={`${inputId}-error`}>
          {error}
        </p>
      ) : null}
      <p className="bxp-small">
        {t("Once or twice a month, when new projects open. You can unsubscribe with one click.")}{" "}
        <PublicLink href="/legal/privacy">{t("Privacy")}</PublicLink>
      </p>
    </>
  );
}
