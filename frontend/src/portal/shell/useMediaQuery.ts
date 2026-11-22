// IP of Webby-Soft SRL.
// True while a media query matches (the shell's phone layout: the design's max-width 1199px).
import { useSyncExternalStore } from "react";

export function useMediaQuery(query: string) {
  const subscribe = (listener: () => void) => {
    if (typeof window === "undefined" || !window.matchMedia) return () => undefined;
    const list = window.matchMedia(query);
    list.addEventListener("change", listener);
    return () => list.removeEventListener("change", listener);
  };
  const snapshot = () => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia(query).matches : false);
  return useSyncExternalStore(subscribe, snapshot, () => false);
}

/** The design switches to the phone shell (off-canvas menu, two-row header) below 1200px. */
export const MOBILE_SHELL_QUERY = "(max-width: 1199px)";
