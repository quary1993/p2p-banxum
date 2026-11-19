// IP of Webby-Soft SRL.
// U33 status pill (design: span.bxm-tag + is-open | is-solid | is-late | is-default | is-muted | is-type),
// with the design's status-to-style mapping (INV_STATUS / statusOf in the prototype).
import type { ReactNode } from "react";

import { useT } from "../../i18n";

export type TagStatus =
  | "open"
  | "comingSoon"
  | "reserved"
  | "active"
  | "late"
  | "default"
  | "repaid"
  | "sold"
  | "funded"
  | "repaying"
  | "listed"
  | "pending";
export type TagTone = "neutral" | "open" | "solid" | "late" | "default" | "muted" | "type";

const toneClass: Record<TagTone, string> = {
  neutral: "",
  open: "is-open",
  solid: "is-solid",
  late: "is-late",
  default: "is-default",
  muted: "is-muted",
  type: "is-type"
};
// Open is green, finished funding is black, pending states stay neutral, Late amber, Default red.
const statusTone: Record<TagStatus, TagTone> = {
  open: "open",
  comingSoon: "neutral",
  reserved: "neutral",
  active: "solid",
  late: "late",
  default: "default",
  repaid: "muted",
  sold: "muted",
  funded: "solid",
  repaying: "solid",
  listed: "neutral",
  pending: "neutral"
};
const statusLabel: Record<TagStatus, string> = {
  open: "Open",
  comingSoon: "Coming soon",
  reserved: "Reserved",
  active: "On schedule",
  late: "Late",
  default: "Default",
  repaid: "Repaid",
  sold: "Sold",
  funded: "Fully funded",
  repaying: "Repaying",
  listed: "Listed for sale",
  // C03: from the due date of an unpaid installment until the payment is recorded.
  pending: "Pending"
};

/** A status pill: pass `status` for the standard label and colour, or `tone` + children. */
export function StatusTag({ status, tone, children, className = "" }: { status?: TagStatus; tone?: TagTone; children?: ReactNode; className?: string }) {
  const t = useT();
  const resolvedTone = tone ?? (status ? statusTone[status] : "neutral");
  return (
    <span className={`bxm-tag ${toneClass[resolvedTone]} ${className}`.replace(/\s+/g, " ").trim()}>
      {children ?? (status ? t(statusLabel[status]) : null)}
    </span>
  );
}
