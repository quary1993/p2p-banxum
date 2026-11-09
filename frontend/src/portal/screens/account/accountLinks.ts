// IP of Webby-Soft SRL.
// Support contact of the account screens (U33-DEC-35/36: support by email until the Help message and
// closure-request endpoints exist, Phase 17.2). The address is configurable (AGENTS.md branding rule),
// the same env value as the rest of the app.
export const supportEmail: string = import.meta.env.VITE_SUPPORT_EMAIL ?? "support@banxum.com";

/**
 * A mailto: link to support with a subject and body. The investor reference (never a name, code or
 * PIN) lets the team find the account; the email itself is not proof of identity (U33-DEC-26).
 */
export function supportMailto({ subject, body, reference }: { subject?: string; body?: string; reference?: string | null } = {}) {
  const lines = [body ?? "", reference ? `Investor reference: ${reference}` : ""].filter(Boolean);
  const params = new URLSearchParams();
  if (subject) params.set("subject", subject);
  if (lines.length > 0) params.set("body", lines.join("\n\n"));
  const query = params.toString().replace(/\+/g, "%20");
  return `mailto:${supportEmail}${query ? `?${query}` : ""}`;
}

/** Topics of the Contact support dialog (design: Help -> Contact support). */
export const SUPPORT_TOPICS = ["An investment", "My account", "Documents or taxes", "Security", "Something else"] as const;
