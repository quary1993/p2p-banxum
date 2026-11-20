// IP of Webby-Soft SRL.
// 18.10 (Q12): new investments pause without declarations, while a necessary compliance review is
// open, or after the re-verification date. The server refuses them too; this tells the screens
// why before the investor confirms (ComplianceBlockNotice shows it).
import { useV1KycDeclarationsRetrieve } from "../api/generated/banxumApi";
import { isFixturePreview } from "./data";

export type ComplianceBlock = { reason: string; message: string };

const KNOWN_BLOCKS = new Set(["declaration_missing", "compliance_review_open", "reverification_due"]);

function useComplianceStatus() {
  return useV1KycDeclarationsRetrieve({ query: { enabled: !isFixturePreview, retry: false, staleTime: 30_000 } });
}

/** Audit S7-7: the status is not known yet, or could not be loaded. The confirmation stays
 * disabled until the server answered (the server checks again in any case). */
export const STATUS_LOADING = "status_loading";
export const STATUS_UNAVAILABLE = "status_unavailable";

/** The current block reason and its message, or null when the investor can invest. Loading,
 * an error or an unknown reason from the server also block (fail closed). */
export function useComplianceBlock(): ComplianceBlock | null {
  const status = useComplianceStatus();
  if (isFixturePreview) return null;
  if (status.isError) return { reason: STATUS_UNAVAILABLE, message: "We could not check your compliance status. Reload the page or try again in a moment." };
  if (!status.data) return { reason: STATUS_LOADING, message: "Checking your compliance status…" };
  const reason = status.data.investment_block ?? "";
  if (!reason) return null;
  const message = status.data.investment_block_message || "New investments are paused. See your declarations.";
  return { reason: KNOWN_BLOCKS.has(reason) ? reason : "unknown", message };
}

/** 18.11 "re-verification in progress": the date set by compliance, when one is open. */
export function useReverificationDate(): string | null {
  const status = useComplianceStatus();
  const value = status.data?.reverification_due_date;
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
}
