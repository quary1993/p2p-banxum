// IP of Webby-Soft SRL.
// 18.10 (Q12): new investments pause without declarations, while a necessary compliance review is
// open, or after the re-verification date. The server refuses them too; this tells the screens
// why before the investor confirms (ComplianceBlockNotice shows it).
import { useV1KycDeclarationsRetrieve } from "../api/generated/banxumApi";
import { isFixturePreview } from "./data";

export type ComplianceBlock = { reason: string; message: string };

const KNOWN_BLOCKS = new Set(["declaration_missing", "compliance_review_open", "reverification_due"]);

/** The current block reason and its message, or null when the investor can invest. */
export function useComplianceBlock(): ComplianceBlock | null {
  const status = useV1KycDeclarationsRetrieve({ query: { enabled: !isFixturePreview, retry: false, staleTime: 30_000 } });
  const reason = status.data?.investment_block ?? "";
  if (!reason || !KNOWN_BLOCKS.has(reason)) return null;
  return { reason, message: status.data?.investment_block_message ?? "" };
}
