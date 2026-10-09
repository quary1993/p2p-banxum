// Platform business date for screens that have no `as_of` of their own (audit A-66).
// The investor shell records `platform_business_date` from /auth/me before any portal screen
// renders; under the QA clock it differs from the browser's date. The browser date is only a
// last resort before the server has answered.
import { businessDateKey, zurichDateKey } from "./format";

let rememberedBusinessDate = "";

export function rememberPlatformBusinessDate(value: string | null | undefined) {
  if (value) rememberedBusinessDate = businessDateKey(value);
}

/** "YYYY-MM-DD" Europe/Zurich business date: from `asOf` when given, else the platform date. */
export function platformTodayKey(asOf?: string | null) {
  if (asOf) return businessDateKey(asOf);
  return rememberedBusinessDate || zurichDateKey(new Date());
}

/**
 * The platform business date as a local-midnight Date, for calendar code that compares it with
 * other local-midnight dates parsed from "YYYY-MM-DD" (so the browser's time zone cancels out).
 */
export function platformTodayLocalDate(asOf?: string | null) {
  const [year, month, day] = platformTodayKey(asOf).split("-").map(Number);
  return new Date(year, month - 1, day);
}
