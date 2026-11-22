// IP of Webby-Soft SRL.
// The Didit return page (/kyc/callback). A browser with the investor session continues to the live
// verification status; a browser without it is the second device of a QR hand-off: the first device
// picks up the result by itself.
import { useEffect } from "react";

import { useV1AuthMeRetrieve } from "../../../../api/generated/banxumApi";
import { useT } from "../../../../i18n";
import { isFixturePreview } from "../../../../investorPortal/data";
import { usePortalNav } from "../../../components";
import { AuthCard, AuthLayout } from "./AuthLayout";
import { registerFlowStorageKey, removeStoredObject } from "./authState";

export function KycReturnScreen() {
  const t = useT();
  const nav = usePortalNav();
  const authMeQuery = useV1AuthMeRetrieve({ query: { enabled: !isFixturePreview, retry: false, staleTime: 0 } });
  const sessionUser = authMeQuery.data?.user;

  // The Didit redirect lands on /kyc/callback, which the app router does not know; every exit must
  // first restore the root path.
  const leaveTo = (name: "login" | "kyc") => {
    window.history.replaceState({}, "", "/");
    nav.go(name);
  };

  useEffect(() => {
    if (!sessionUser) return;
    // This browser holds the investor session: verification was completed on the same device.
    removeStoredObject(registerFlowStorageKey);
    window.history.replaceState({}, "", "/");
    nav.go("kyc");
    // nav changes identity on every App render; the session decides.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionUser]);

  if (!isFixturePreview && (authMeQuery.isPending || sessionUser)) {
    return (
      <AuthLayout>
        <AuthCard icon="clock" intro={t("Returning you to your verification status.")} title={t("Finishing identity verification")} />
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <AuthCard
        icon="checkCircle"
        intro={t("You can close this tab and return to the device where you started registration. It continues by itself as soon as the verification result arrives.")}
        success
        title={t("Identity check submitted")}
      >
        <p className="ca-foot-link">
          {t("Want to continue on this device instead?")}
          <a href="/login" onClick={(event) => { event.preventDefault(); leaveTo("login"); }}>{t("Log in here")}</a>
        </p>
      </AuthCard>
    </AuthLayout>
  );
}
