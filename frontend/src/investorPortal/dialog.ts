// Keyboard and focus behaviour shared by dialogs, sheets and tab lists (audit A-61).
import { QueryClientContext } from "@tanstack/react-query";
import {
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useSyncExternalStore,
  type KeyboardEvent as ReactKeyboardEvent,
  type RefObject
} from "react";

// Arrow keys, Home and End move between tabs (roving tabindex), as in the WAI-ARIA tabs pattern.
export function handleTabListKeyDown(event: ReactKeyboardEvent<HTMLElement>) {
  const keys = ["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp", "Home", "End"];
  if (!keys.includes(event.key)) return;
  const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('[role="tab"]:not([disabled])'));
  const current = tabs.findIndex((tab) => tab === document.activeElement);
  if (tabs.length === 0 || current < 0) return;
  event.preventDefault();
  const next = event.key === "Home"
    ? 0
    : event.key === "End"
      ? tabs.length - 1
      : (current + (event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : -1) + tabs.length) % tabs.length;
  tabs[next].focus();
  tabs[next].click();
}

/** Props for the panel shown by a Tabs component with `idPrefix`. */
export function tabPanelProps(idPrefix: string, value: string) {
  return {
    "aria-labelledby": `${idPrefix}-tab-${value}`,
    id: `${idPrefix}-panel-${value}`,
    role: "tabpanel" as const,
    tabIndex: 0
  };
}
// ---- Dialog behaviour shared by Modal and the full-screen sheets ----------------------------------
// Only the top-most open dialog reacts to Escape and Tab; focus moves into a dialog when it opens,
// stays inside while it is open, and returns to the opener when it closes. While a money action is
// running (a mutation is pending, or the caller says busy) Escape and the backdrop do nothing.

const openDialogStack: symbol[] = [];
let scrollLockCount = 0;

const focusableSelector = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type=hidden])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])"
].join(",");

function focusableWithin(root: HTMLElement) {
  return Array.from(root.querySelectorAll<HTMLElement>(focusableSelector)).filter(
    (element) => !element.closest("[inert]") && element.getAttribute("aria-hidden") !== "true"
  );
}

function noopSubscribe() {
  return () => undefined;
}

/** Number of pending mutations; 0 outside a QueryClientProvider. */
export function usePendingMutationCount() {
  const client = useContext(QueryClientContext);
  const subscribe = useCallback(
    (listener: () => void) => (client ? client.getMutationCache().subscribe(listener) : noopSubscribe()),
    [client]
  );
  const snapshot = () => (client ? client.isMutating() : 0);
  return useSyncExternalStore(subscribe, snapshot, snapshot);
}

export function useDialog({
  dialogRef,
  onDismiss,
  busy = false
}: {
  dialogRef: RefObject<HTMLElement | null>;
  onDismiss: () => void;
  busy?: boolean;
}) {
  const pendingMutations = usePendingMutationCount();
  const blocked = busy || pendingMutations > 0;
  const dismissRef = useRef(onDismiss);
  const blockedRef = useRef(blocked);
  useLayoutEffect(() => {
    dismissRef.current = onDismiss;
    blockedRef.current = blocked;
  });

  useEffect(() => {
    const token = Symbol("dialog");
    openDialogStack.push(token);
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    scrollLockCount += 1;
    document.body.style.overflow = "hidden";
    const dialog = dialogRef.current;
    if (dialog) {
      const preferred = dialog.querySelector<HTMLElement>("[data-autofocus]");
      const candidates = focusableWithin(dialog).filter((element) => !element.classList.contains("ui-tooltip-anchor"));
      const inBody = candidates.find((element) => element.closest(".modal-body, .ls-scroll, .si-wiz-body"));
      const target = preferred ?? inBody ?? candidates.find((element) => !element.classList.contains("x-btn")) ?? candidates[0];
      if (target) target.focus({ preventScroll: true });
      else {
        if (!dialog.hasAttribute("tabindex")) dialog.setAttribute("tabindex", "-1");
        dialog.focus({ preventScroll: true });
      }
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (openDialogStack[openDialogStack.length - 1] !== token) return;
      const root = dialogRef.current;
      if (event.key === "Escape") {
        if (event.defaultPrevented) return;
        event.preventDefault();
        if (!blockedRef.current) dismissRef.current();
        return;
      }
      if (event.key !== "Tab" || !root) return;
      const focusable = focusableWithin(root);
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (!root.contains(active)) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && (active === first || active === root)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      const index = openDialogStack.indexOf(token);
      if (index >= 0) openDialogStack.splice(index, 1);
      scrollLockCount = Math.max(0, scrollLockCount - 1);
      if (scrollLockCount === 0) document.body.style.overflow = "";
      if (opener && opener.isConnected) opener.focus({ preventScroll: true });
    };
    // Runs once per opened dialog: moving focus again on every render would fight the user.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    blocked,
    /** Backdrop click handler: dismisses unless an action is running. */
    dismissFromBackdrop: () => {
      if (!blocked) onDismiss();
    }
  };
}
