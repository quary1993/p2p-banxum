// IP of Webby-Soft SRL.
// Verification (/verification, and the screen every route shows until financial access is open): the
// identity check status from today's KYC data in the design's Profile & Settings language (ps-panel
// with the check history). Didit stays the provider; the decision date and self-declarations wait
// for backend data (U33-DEC-27, Phase 17.7). The provider's flags are never named to the investor.
import "./account.css";

import { useEffect, useState } from "react";

import { useV1AuthMeRetrieve, useV1KycSessionCreate, useV1KycStatusRetrieve } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { isFixturePreview } from "../../../investorPortal/data";
import { operatorName } from "../../brand";
import { Button, NiIcon, PageHead, usePortalNav } from "../../components";
import { supportMailto } from "./accountLinks";
import { Notice, PsPanel, PsStatus } from "./parts/ui";
import { kycStatusView, PREVIEW_INVESTOR_REFERENCE } from "./settings/useAccountData";

/** The loading state of the verification gate (before the first KYC answer). */
export function VerificationLoading() {
  const t = useT();
  return (
    <main className="ps-page acc-kyc-page">
      <PageHead title={t("Verification")} />
      <p className="ps-intro" role="status">{t("Loading your verification status...")}</p>
    </main>
  );
}

const historyIcon = { done: "check-circle", pending: "clock", action: "alert-circle" } as const;

export function KycStatusScreen() {
  const t = useT();
  const nav = usePortalNav();
  const statusQuery = useV1KycStatusRetrieve({
    query: {
      enabled: !isFixturePreview,
      retry: false,
      // The portal gate already asked; never re-run a failed lookup just because this screen mounted.
      retryOnMount: false,
      // While capture is still open (possibly on another device), poll until the provider answers.
      refetchInterval: (query) => {
        const caseStatus = query.state.data?.status;
        return caseStatus === "not_started" || caseStatus === "pending" ? 4000 : false;
      }
    }
  });
  const me = useV1AuthMeRetrieve({ query: { enabled: !isFixturePreview, retry: false, staleTime: 60_000 } });
  const sessionMutation = useV1KycSessionCreate();
  const [error, setError] = useState("");
  const data = statusQuery.data;
  const kycStatus = isFixturePreview ? "manual_review" : data?.status;
  const approved = kycStatus === "approved";
  const waiting = kycStatus === "pending";
  // A case that waits for a compliance decision cannot be restarted by the investor; a new check is
  // open only when it was never started, expired, or compliance asked for it.
  const canStart =
    !isFixturePreview &&
    !data?.manual_review_required &&
    (kycStatus === "not_started" || kycStatus === "expired" || kycStatus === "reverification_required");
  const financialAccess = isFixturePreview || data?.financial_access_allowed === true;
  const phoneVerified = isFixturePreview ? true : data?.phone_verified;
  const reference = isFixturePreview ? PREVIEW_INVESTOR_REFERENCE : (me.data?.user?.investor_reference ?? null);
  const view = kycStatusView(kycStatus);

  useEffect(() => {
    if (!isFixturePreview && data?.financial_access_allowed) nav.go("dashboard");
    // nav changes identity on every render of the shell; the access flag decides.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data?.financial_access_allowed]);

  const start = () => {
    setError("");
    if (isFixturePreview) return;
    sessionMutation.mutate(undefined, {
      onSuccess: (response) => {
        if (response.verification_url) window.location.assign(response.verification_url);
      },
      onError: (mutationError) => setError(mutationError instanceof Error ? mutationError.message : t("Request failed. Retry once the connection is restored."))
    });
  };

  if (!isFixturePreview && statusQuery.isPending && statusQuery.dataUpdatedAt === 0 && statusQuery.errorUpdatedAt === 0) {
    return <VerificationLoading />;
  }

  const title = approved
    ? t("Verification approved")
    : canStart
      ? t("Identity verification required")
      : waiting
        ? t("Waiting for the verification result")
        : t("Verification under review");
  const message = approved
    ? t("Your identity has been verified. Adding funds and investing are open when your phone and your account are in order too.")
    : canStart
      ? t("Verify your identity with Didit, our identity verification provider. When you have finished, this page waits for the result.")
      : waiting
        ? t("Your identity check has been submitted. We are waiting for Didit and {operator} compliance to confirm the result. This page updates by itself. If nothing changes, contact support.", { operator: operatorName })
        : t("Your verification is under review by {operator} compliance. Adding funds and investing stay closed until the review is complete. No action is needed from you in the meantime.", { operator: operatorName });

  const steps: Array<{ tone: keyof typeof historyIcon; title: string; status: string; description?: string }> = [
    { tone: "done", title: t("Account created"), status: t("Done"), description: t("Email confirmed and registration terms accepted.") },
    ...(phoneVerified === undefined
      ? []
      : [{ tone: (phoneVerified ? "done" : "action") as keyof typeof historyIcon, title: t("Phone verified"), status: phoneVerified ? t("Done") : t("Not done yet") }]),
    ...(view.label ? [{ tone: view.tone, title: t("Identity check with Didit"), status: t(view.label), description: t(view.description) }] : []),
    {
      tone: financialAccess ? "done" : "pending",
      title: t("Financial access"),
      status: financialAccess ? t("Open") : t("Not open yet"),
      description: financialAccess ? t("You can add funds, invest and withdraw.") : t("Adding funds and investing open after your identity check is approved.")
    }
  ];

  return (
    <main className="ps-page acc-kyc-page">
      <PageHead title={t("Verification")} />
      <div className="ps-content">
        {statusQuery.isError && !isFixturePreview ? (
          <Notice
            action={<Button disabled={statusQuery.isFetching} onClick={() => void statusQuery.refetch()} size="sm">{t("Retry")}</Button>}
            title={t("Could not load KYC status")}
            tone="danger"
          >
            {t("The verification service did not answer.")}
          </Notice>
        ) : null}
        <PsPanel status={view.label ? (approved ? <PsStatus>{t(view.label)}</PsStatus> : <PsStatus muted>{t(view.label)}</PsStatus>) : null} title={title}>
          <div className="ps-panel-body">
            <p className="acc-kyc-message">{message}</p>
            <ol className="ps-check-history">
              {steps.map((step) => (
                <li className={`acc-history-${step.tone}`} key={step.title}>
                  <span>
                    <NiIcon name={historyIcon[step.tone]} />
                    {step.title}
                  </span>
                  <div>
                    {step.status}
                    {step.description ? <small>{step.description}</small> : null}
                  </div>
                </li>
              ))}
            </ol>
            <div className="acc-kyc-actions">
              {canStart ? (
                <Button disabled={sessionMutation.isPending} onClick={start} variant="primary">
                  {sessionMutation.isPending ? t("Starting Didit...") : t("Start identity verification")}
                </Button>
              ) : null}
              {financialAccess ? <Button onClick={() => nav.go("dashboard")} variant={canStart ? "secondary" : "primary"}>{t("Back to overview")}</Button> : null}
              <a className="btn btn-outline-light" href={supportMailto({ subject: t("Identity verification"), reference })}>{t("Contact support")}</a>
            </div>
            {error ? <Notice title={t("Could not start the identity check")} tone="danger">{error}</Notice> : null}
          </div>
        </PsPanel>
      </div>
    </main>
  );
}
