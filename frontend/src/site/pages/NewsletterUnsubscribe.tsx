// IP of Webby-Soft SRL.
// One-click unsubscribe link (/newsletter/unsubscribe?token=...), not in the design: see NewsletterLink.tsx.
import { NewsletterLinkPage } from "./NewsletterLink";

export function NewsletterUnsubscribe() {
  return <NewsletterLinkPage kind="unsubscribe" />;
}
