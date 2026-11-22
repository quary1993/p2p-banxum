// IP of Webby-Soft SRL.
/*
 * Light/Dark appearance of the U33 investor area (plan/22: desktop/mobile and Light/Dark).
 *
 * The choice is saved in localStorage (wrapped in try/catch: private windows and blocked storage
 * fall back to Light). U33Skin applies it as document.documentElement.dataset.theme while the
 * investor area is mounted and removes it on unmount, so the public site and the admin console
 * keep their own look. The control lives in Profile & Settings -> Preferences (slice S5); the
 * design has no permanent theme switch in the header (docs/02_DESIGN.md "Antet").
 */
import { useCallback, useSyncExternalStore } from "react";

export type Appearance = "light" | "dark";

export const APPEARANCES: readonly Appearance[] = ["light", "dark"];
const STORAGE_KEY = "banxum.appearance";

function isAppearance(value: unknown): value is Appearance {
  return value === "light" || value === "dark";
}

/** The saved appearance, Light when nothing valid is saved or storage is unavailable. */
export function readAppearancePreference(): Appearance {
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return isAppearance(saved) ? saved : "light";
  } catch {
    return "light";
  }
}

let current: Appearance | null = null;
const listeners = new Set<() => void>();

function snapshot(): Appearance {
  if (current === null) current = readAppearancePreference();
  return current;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Saves and applies a new appearance (all mounted users of useAppearance re-render). */
export function setAppearancePreference(next: Appearance) {
  if (!isAppearance(next) || next === snapshot()) return;
  current = next;
  try {
    window.localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // The choice still applies for this visit.
  }
  listeners.forEach((listener) => listener());
}

/** The investor's appearance and a setter. */
export function useAppearance(): { appearance: Appearance; setAppearance: (next: Appearance) => void } {
  const appearance = useSyncExternalStore(subscribe, snapshot, snapshot);
  const setAppearance = useCallback((next: Appearance) => setAppearancePreference(next), []);
  return { appearance, setAppearance };
}

/** Test helper: forgets the cached choice. */
export function resetAppearanceForTests() {
  current = null;
  listeners.forEach((listener) => listener());
}
