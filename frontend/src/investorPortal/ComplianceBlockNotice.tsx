// IP of Webby-Soft SRL.
// 18.10 (Q12): why a new investment is paused, with a link to Settings > Declarations.
import { useT } from "../i18n";
import { PortalLink } from "../portal/components";
import { STATUS_LOADING, STATUS_UNAVAILABLE, type ComplianceBlock } from "./complianceBlock";

export function ComplianceBlockNotice({ block }: { block: ComplianceBlock | null }) {
  const t = useT();
  if (!block) return null;
  if (block.reason === STATUS_LOADING) {
    return (
      <p className="u33-muted" role="status">
        {t(block.message)}
      </p>
    );
  }
  if (block.reason === STATUS_UNAVAILABLE) {
    return (
      <div className="alert alert-danger" role="alert">
        <p className="mb-0">{t(block.message)}</p>
      </div>
    );
  }
  return (
    <div className="alert alert-warning" role="alert">
      <p className="mb-1">{block.message}</p>
      <PortalLink className="link" params={{ tab: "declarations" }} to="settings">
        {block.reason === "compliance_review_open" ? t("See your declarations") : t("Complete your declarations")}
      </PortalLink>
    </div>
  );
}
