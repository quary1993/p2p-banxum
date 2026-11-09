// IP of Webby-Soft SRL.
// Hooks of the U33 public site: media queries (the design switches to its mobile edition below
// 1120 px), reduced motion and "in view" (the design's IntersectionObserver checks).
import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type RefObject } from "react";

/** Below this width the design shows its mobile edition (unified-public.js, mobile.js). */
export const NARROW_QUERY = "(max-width:1119px)";
export const PHONE_QUERY = "(max-width:767px)";
export const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function mediaList(query: string): MediaQueryList | null {
  return typeof window !== "undefined" && typeof window.matchMedia === "function" ? window.matchMedia(query) : null;
}

/** Whether a media query matches now; re-renders when it changes. False without matchMedia. */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (listener) => {
      const list = mediaList(query);
      list?.addEventListener?.("change", listener);
      return () => list?.removeEventListener?.("change", listener);
    },
    () => mediaList(query)?.matches ?? false,
    () => false
  );
}

/** The mobile edition's layout (below 1120 px). */
export function useNarrow() {
  return useMediaQuery(NARROW_QUERY);
}

export function useReducedMotion() {
  return useMediaQuery(REDUCED_MOTION_QUERY);
}

/**
 * Whether an element is in view, with the design's threshold (55 % visible). Without
 * IntersectionObserver (tests) it counts as in view.
 */
export function useInView(ref: RefObject<Element | null>, threshold = 0.55) {
  const [inView, setInView] = useState(() => typeof IntersectionObserver === "undefined");
  useEffect(() => {
    const element = ref.current;
    if (!element || typeof IntersectionObserver === "undefined") return undefined;
    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries.find((item) => item.target === element) ?? entries[0];
        setInView(Boolean(entry?.isIntersecting && entry.intersectionRatio >= threshold));
      },
      { threshold: [0, threshold] }
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref, threshold]);
  return inView;
}

/** Scrolls to a section of the current page (smooth unless the visitor prefers less motion). */
export function scrollToSection(id: string) {
  const element = document.getElementById(id);
  if (!element) return false;
  const reduced = typeof window.matchMedia === "function" && window.matchMedia(REDUCED_MOTION_QUERY).matches;
  element.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  return true;
}

/**
 * A one-shot animation timeline (design money-flow.js, mobile-money-flow.js): starts the first
 * time the element is in view, pauses out of view or in a hidden tab, and can be replayed. With
 * reduced motion it stays at its end and cannot be replayed. Returns the elapsed milliseconds.
 */
export function useTimeline(ref: RefObject<Element | null>, duration: number, active = true) {
  const reduced = useReducedMotion();
  const inView = useInView(ref);
  const [elapsed, setElapsed] = useState(duration);
  const [run, setRun] = useState(0);
  const [hidden, setHidden] = useState(() => typeof document !== "undefined" && document.hidden);
  const elapsedRef = useRef(duration);
  const started = useRef(false);

  useEffect(() => {
    const onVisibility = () => setHidden(document.hidden);
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  useEffect(() => {
    if (reduced) {
      started.current = true;
      elapsedRef.current = duration;
      setElapsed(duration);
    } else if (active && inView && !started.current) {
      started.current = true;
      elapsedRef.current = 0;
      setElapsed(0);
      setRun((value) => value + 1);
    }
  }, [active, inView, reduced, duration]);

  const running = active && inView && !reduced && !hidden && elapsed < duration;
  useEffect(() => {
    if (!running) return undefined;
    let last: number | null = null;
    let frame = 0;
    const tick = (now: number) => {
      if (last !== null) elapsedRef.current = Math.min(duration, elapsedRef.current + now - last);
      last = now;
      setElapsed(elapsedRef.current);
      if (elapsedRef.current < duration) frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, [running, run, duration]);

  const replay = useCallback(() => {
    if (reduced) return;
    started.current = true;
    elapsedRef.current = 0;
    setElapsed(0);
    setRun((value) => value + 1);
  }, [reduced]);

  return { elapsed, running, reduced, replay };
}
