// IP of Webby-Soft SRL.
// Newsletter confirmation link (/newsletter/confirm?token=...), not in the design: see NewsletterLink.tsx.
import { NewsletterLinkPage } from "./NewsletterLink";

export function NewsletterConfirm() {
  return <NewsletterLinkPage kind="confirm" />;
}
