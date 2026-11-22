// IP of Webby-Soft SRL.
// Account access (every route of a signed-in investor whose account an admin restricted, locked or
// closed): the reason and the remedy (contact support), in the design's empty-state style
// (U33-DEC-29: reason and remedy that fit the state). The investor is signed in here, so the state
// can be named; before sign-in nothing reveals whether an account exists.
import "./account.css";

import { useV1AuthMeRetrieve } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { isFixturePreview } from "../../../investorPortal/data";
import { EmptyState, PageHead } from "../../components";
import { supportEmail, supportMailto } from "./accountLinks";
import { PREVIEW_INVESTOR_REFERENCE } from "./settings/useAccountData";

export function AccountBlockedScreen({ status }: { status: string }) {
  const t = useT();
  const me = useV1AuthMeRetrieve({ query: { enabled: !isFixturePreview, retry: false, staleTime: 60_000 } });
  const reference = isFixturePreview ? PREVIEW_INVESTOR_REFERENCE : (me.data?.user?.investor_reference ?? null);
  const title = status === "locked" ? t("Your account is locked") : status === "closed" ? t("Your account is closed") : t("Your account is restricted");
  const message = status === "closed"
    ? t("This account has been closed. If you have questions, contact support at {email}.", { email: supportEmail })
    : status === "locked"
      ? t("You cannot view or move money while your account is locked. Please contact support at {email} for further details.", { email: supportEmail })
      : t("You cannot view or move money while your account is restricted. Please contact support at {email} for further details.", { email: supportEmail });
  return (
    <main className="ps-page acc-blocked-page">
      <PageHead subtitle={t("Your balances, investments and loans are not available right now.")} title={t("Account access")} />
      <section aria-label={t("Account status")} className="ps-panel acc-blocked-panel">
        <EmptyState
          actions={<a className="btn btn-primary" href={supportMailto({ subject: t("Account access"), reference })}>{t("Contact support")}</a>}
          icon="lock"
          title={title}
        >
          {message}
        </EmptyState>
      </section>
    </main>
  );
}
