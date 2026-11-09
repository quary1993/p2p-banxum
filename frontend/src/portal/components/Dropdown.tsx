// IP of Webby-Soft SRL.
// U33 dropdown (design: li.dropdown > a.dropdown-toggle + .dropdown-menu.dropdown-menu-end.show),
// placed bottom-end under the toggle as Bootstrap/Popper does in the design. Closes on an outside
// click, Escape (focus back on the toggle) or after a choice. Content is free: lists, cards, forms.
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

import { useDismissable } from "./useDismissable";

export function Dropdown({
  toggle,
  toggleLabel,
  toggleClassName = "",
  className = "",
  menuClassName = "",
  menuSize = "md",
  children,
  onOpenChange,
  as = "li",
  id
}: {
  /** Content of the toggle (avatar and name, a bell icon...). */
  toggle: ReactNode;
  /** Accessible name when the toggle has no visible text. */
  toggleLabel?: string;
  toggleClassName?: string;
  /** Classes of the wrapper next to "dropdown" (design: user-dropdown, notification-dropdown). */
  className?: string;
  /** Classes of the menu next to "dropdown-menu" (design: dropdown-menu-s1, nd-dropdown). */
  menuClassName?: string;
  menuSize?: "sm" | "md" | "lg" | "xl";
  /** Menu content; a function receives close() for items that act and close. */
  children: ReactNode | ((close: () => void) => ReactNode);
  onOpenChange?: (open: boolean) => void;
  as?: "li" | "div";
  /** The design's id where its CSS selects on it (#bxm-user-dropdown). */
  id?: string;
}) {
  const { open, setOpen, rootRef } = useDismissable<HTMLLIElement & HTMLDivElement>();
  const toggleRef = useRef<HTMLAnchorElement>(null);
  const [placement, setPlacement] = useState<CSSProperties>({});
  const close = useCallback(() => setOpen(false), [setOpen]);
  useEffect(() => onOpenChange?.(open), [onOpenChange, open]);
  // Bottom-end under the toggle, 2px below it (Popper's placement in the design).
  useLayoutEffect(() => {
    if (!open || !rootRef.current || !toggleRef.current) return;
    const root = rootRef.current.getBoundingClientRect();
    const toggleBox = toggleRef.current.getBoundingClientRect();
    setPlacement({
      position: "absolute",
      inset: "0px 0px auto auto",
      margin: 0,
      transform: `translate(${Math.round(toggleBox.right - root.right)}px, ${Math.round(toggleBox.bottom - root.top + 2)}px)`
    });
  }, [open, rootRef]);
  const Wrapper = as;
  return (
    <Wrapper className={`dropdown ${className}`.trim()} id={id} ref={rootRef}>
      <a
        aria-expanded={open}
        aria-haspopup="true"
        aria-label={toggleLabel}
        className={`dropdown-toggle ${toggleClassName} ${open ? "show" : ""}`.replace(/\s+/g, " ").trim()}
        href="#"
        onClick={(event) => {
          event.preventDefault();
          setOpen((value) => !value);
        }}
        ref={toggleRef}
        role="button"
      >
        {toggle}
      </a>
      {open ? (
        <div className={`dropdown-menu dropdown-menu-${menuSize} dropdown-menu-end ${menuClassName} show`.replace(/\s+/g, " ").trim()} data-popper-placement="bottom-end" style={placement}>
          {typeof children === "function" ? children(close) : children}
        </div>
      ) : null}
    </Wrapper>
  );
}
