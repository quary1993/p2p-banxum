// IP of Webby-Soft SRL.
// Underlined section tabs (design: nav.dp-tabs / .ps-tabs / .rs-tabs with a.active[aria-current]).
// Route tabs are links (shareable addresses); view tabs are buttons with aria-pressed.
import type { ReactNode } from "react";

import type { RouteName } from "../../investorPortal/types";
import { PortalLink } from "./navigation";
import { clickOnSpace } from "./keyboard";

export type TabItem<V extends string> = {
  value: V;
  label: ReactNode;
  /** A route: the tab is a link to it. Without one the tab is a button calling onChange. */
  to?: RouteName;
  params?: Record<string, string>;
};

export function Tabs<V extends string>({
  items,
  value,
  onChange,
  label,
  variant = "dp-tabs"
}: {
  items: TabItem<V>[];
  value: V;
  onChange?: (value: V) => void;
  /** Accessible name of the navigation. */
  label: string;
  /** The design's tab style class: dp-tabs (documents), ps-tabs (payments), rs-tabs (resale). */
  variant?: string;
}) {
  return (
    <nav aria-label={label} className={variant}>
      {items.map((item) => {
        const active = item.value === value;
        return item.to ? (
          <PortalLink aria-current={active ? "page" : undefined} className={active ? "active" : ""} key={item.value} onNavigate={() => onChange?.(item.value)} params={item.params} to={item.to}>
            {item.label}
          </PortalLink>
        ) : (
          <a
            aria-pressed={active}
            className={active ? "active" : ""}
            href="#"
            key={item.value}
            onClick={(event) => {
              event.preventDefault();
              onChange?.(item.value);
            }}
            onKeyDown={clickOnSpace}
            role="button"
          >
            {item.label}
          </a>
        );
      })}
    </nav>
  );
}
