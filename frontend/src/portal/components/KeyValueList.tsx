// IP of Webby-Soft SRL.
// Label/value rows as the design writes them: <dl><div><dt/><dd/></div>...</dl>. The screen's own
// class (e.g. "ap-breakdown") gives the layout; rows without a value are left out (no invented data).
import type { ReactNode } from "react";

export type KeyValueItem = { label: ReactNode; value: ReactNode; key?: string; info?: ReactNode };

export function KeyValueList({ items, className = "" }: { items: KeyValueItem[]; className?: string }) {
  const rows = items.filter((item) => item.value !== null && item.value !== undefined && item.value !== "");
  if (rows.length === 0) return null;
  return (
    <dl className={className || undefined}>
      {rows.map((item, index) => (
        <div key={item.key ?? index}>
          <dt>{item.label}{item.info ? <> {item.info}</> : null}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
