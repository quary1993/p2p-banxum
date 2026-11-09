// IP of Webby-Soft SRL.
// API error helpers of the portfolio area (same readings as App.tsx).
import { ApiClientError } from "../../../../api/client/httpClient";
import type { PublicDocumentTemplateVersion } from "../../../../api/generated/banxumApi";
import { t } from "../../../../i18n";
import { readReadonlyImpersonationToken } from "../../../../api/client/impersonation";

export function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return t("Request failed. Retry once the connection is restored.");
}

/** 409 from a resale purchase: the price differs from the reviewed one; nothing was charged. */
export function isPriceChangedError(error: unknown) {
  if (!(error instanceof ApiClientError) || error.status !== 409) return false;
  const payload = error.payload as { code?: unknown } | null | undefined;
  return payload?.code === "secondary_price_changed";
}

/** The checkbox labels of a terms version, as the acceptance endpoint records them. */
export function templateLabels(template: PublicDocumentTemplateVersion | undefined) {
  return Array.isArray(template?.checkbox_labels)
    ? template.checkbox_labels.filter((label): label is string => typeof label === "string")
    : [];
}

export function idempotencyKey(prefix: string) {
  const random = typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : Math.random().toString(36).slice(2);
  return `${prefix}:${random}`;
}

/** A superadmin's read-only view of an investor: every money action is disabled. */
export function isReadonlyView() {
  return Boolean(readReadonlyImpersonationToken());
}

/** The public page of a terms category ("/legal/secondary-market-listing"), opened before confirming. */
export function legalDocumentPath(category: string) {
  return `/legal/${category.replace(/_/g, "-")}`;
}
