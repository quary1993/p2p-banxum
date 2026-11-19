// IP of Webby-Soft SRL.
// The addresses of Profile & Settings (design: #/settings/:tab). /settings is Personal details;
// /settings/verification and /settings/agreements open Personal details with that section expanded,
// as the design's routes do. App.tsx maps these paths to the "settings" route with a `tab` param.
export const SETTINGS_TABS = ["personal", "security", "declarations", "bank-accounts", "notifications", "preferences"] as const;
export type SettingsTab = (typeof SETTINGS_TABS)[number];

export const SETTINGS_SECTIONS = ["verification", "agreements"] as const;
export type SettingsSection = (typeof SETTINGS_SECTIONS)[number];

/** True for a path segment that /settings/<segment> accepts. */
export function isSettingsPathSegment(segment: string): boolean {
  return (SETTINGS_TABS as readonly string[]).includes(segment) || (SETTINGS_SECTIONS as readonly string[]).includes(segment);
}

/** The tab (and the expanded section of Personal details) of a `tab` route param. */
export function settingsView(param: string | undefined): { tab: SettingsTab; section: SettingsSection | null } {
  if (param && (SETTINGS_TABS as readonly string[]).includes(param)) return { tab: param as SettingsTab, section: null };
  if (param && (SETTINGS_SECTIONS as readonly string[]).includes(param)) return { tab: "personal", section: param as SettingsSection };
  return { tab: "personal", section: null };
}
