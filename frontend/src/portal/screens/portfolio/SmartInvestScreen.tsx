// IP of Webby-Soft SRL.
// Smart Invest (design #/auto-invest, route /smart-invest, U33 slice S3): not set up, active with matches,
// active with zero matches, paused, and the setup/edit wizard. Matches come from the server's matching;
// each "Review investment" opens the opportunity page, where the investor confirms each investment on
// its own (U33-DEC-19: no batch approval, nothing reserved). "Pause Smart Invest" keeps the preferences
// and removes the matches, marks and alerts; "Resume Smart Invest" calculates the matches again. Editing
// a paused rule keeps it paused. No risk rating anywhere (U33-DEC-16).
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  getV1InvestorSmartInvestRetrieveQueryKey,
  useV1InvestorSmartInvestPauseCreate,
  useV1InvestorSmartInvestResumeCreate,
  useV1InvestorSmartInvestUpdate,
  type SmartInvestOpportunity,
  type SmartInvestResponse
} from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { isFixturePreview, useComingSoonLoansData, useMarketplaceLoansData, useSmartInvestData } from "../../../investorPortal/data";
import { formatDecimal, formatMoneyLabel, useNumberFormat } from "../../../investorPortal/format";
import { Button, Dialog, EmptyState, NiIcon, PageHead } from "../../components";
import { SmartInvestWizard } from "./SmartInvestWizard";
import { errorMessage, isReadonlyView } from "./parts/errors";
import { OpportunityCard } from "./parts/OpportunityCard";
import { SmartInvestChannelsDialog } from "./parts/SmartInvestChannelsDialog";
import {
  SMART_CURRENCIES,
  preferencesFromRule,
  previewPaused,
  previewResponse,
  previewResumed,
  requestFromPreferences,
  smartState,
  type SmartPreferences
} from "./parts/smartInvestModel";
import { channelsLine, preferenceSummary } from "./parts/smartSummary";
import { usePreviewVariant } from "./parts/urlState";
import { PageError, PageLoading, SelectFilter } from "./parts/ui";
import "./portfolio.css";

type SortKey = "closing" | "rate" | "term" | "funded";

function sortMatches(matches: SmartInvestOpportunity[], key: SortKey) {
  const funded = (match: SmartInvestOpportunity) => (match.principal_minor > 0 ? match.committed_principal_minor / match.principal_minor : 0);
  return [...matches].sort((left, right) => {
    if (key === "rate") return (right.yield_bps || right.interest_rate_bps) - (left.yield_bps || left.interest_rate_bps);
    if (key === "term") return left.term_months - right.term_months;
    if (key === "funded") return funded(right) - funded(left);
    return (left.funding_deadline ?? "9999-12-31").localeCompare(right.funding_deadline ?? "9999-12-31");
  });
}

export function SmartInvestScreen() {
  const t = useT();
  useNumberFormat();
  const queryClient = useQueryClient();
  const smartQuery = useSmartInvestData();
  const loansQuery = useMarketplaceLoansData();
  const soonQuery = useComingSoonLoansData();
  const updateMutation = useV1InvestorSmartInvestUpdate();
  const pauseMutation = useV1InvestorSmartInvestPauseCreate();
  const resumeMutation = useV1InvestorSmartInvestResumeCreate();
  const preview = usePreviewVariant();
  const [wizard, setWizard] = useState<"setup" | "edit" | null>(null);
  const [whyOpen, setWhyOpen] = useState(false);
  const [channelsOpen, setChannelsOpen] = useState(false);
  const [sort, setSort] = useState<SortKey>("closing");
  const [error, setError] = useState("");

  if (smartQuery.isError && !smartQuery.data) {
    return <PageError className="si-page" message={t("Your Smart Invest preferences could not be loaded. Retry once the connection is restored.")} onRetry={() => void smartQuery.refetch()} title={t("Smart Invest")} />;
  }
  if (!smartQuery.data) return <PageLoading className="si-page" title={t("Smart Invest")} />;

  const data = smartQuery.data;
  const loans = loansQuery.data ?? [];
  // Preview mode matches Coming soon opportunities too (U33-DEC-17).
  const previewLoans = [...loans, ...(soonQuery.data ?? [])];
  // Preview variants for review: ?preview=not-set-up, ?preview=zero-matches, ?preview=paused.
  const rule = preview === "not-set-up" ? null : preview === "paused" && data.rule ? { ...data.rule, is_active: false, state: "paused" as const } : data.rule;
  const matches = preview === "zero-matches" ? [] : data.matches;
  // U33-DEC-17: Coming soon matches follow the open ones and are not in the open count.
  const soonMatches = preview === "zero-matches" ? [] : [...(data.coming_soon_matches ?? [])].sort((a, b) => (a.planned_opening_date ?? "9999").localeCompare(b.planned_opening_date ?? "9999") || a.loan_id.localeCompare(b.loan_id));
  const state = smartState(rule);
  const preferences = preferencesFromRule(rule);
  const originators = Array.from(
    new Map(loans.filter((loan) => loan.originator_id && loan.originator_name).map((loan) => [loan.originator_id as string, loan.originator_name as string])).entries()
  ).map(([id, name]) => ({ id, name })).sort((left, right) => left.name.localeCompare(right.name));
  const saving = updateMutation.isPending || pauseMutation.isPending || resumeMutation.isPending;
  const readonly = isReadonlyView();

  const save = async (next: SmartPreferences) => {
    setError("");
    if (readonly) {
      setError(t("Smart Invest cannot be changed in a read-only view."));
      return;
    }
    try {
      const response = isFixturePreview
        ? previewResponse(next, previewLoans, rule, undefined, data.notification_channels)
        : await updateMutation.mutateAsync({ data: requestFromPreferences(next) });
      queryClient.setQueryData(getV1InvestorSmartInvestRetrieveQueryKey(), response);
      setWizard(null);
    } catch (failure) {
      setError(errorMessage(failure));
    }
  };
  const changeState = async (next: "pause" | "resume") => {
    setError("");
    if (readonly) {
      setError(t("Smart Invest cannot be changed in a read-only view."));
      return;
    }
    try {
      let response: SmartInvestResponse;
      if (isFixturePreview) response = next === "pause" ? previewPaused(rule, previewLoans, data.notification_channels) : previewResumed(rule, previewLoans, data.notification_channels);
      else response = next === "pause" ? await pauseMutation.mutateAsync() : await resumeMutation.mutateAsync();
      queryClient.setQueryData(getV1InvestorSmartInvestRetrieveQueryKey(), response);
    } catch (failure) {
      setError(errorMessage(failure));
    }
  };
  // Design amountSummary(): the usual amount in each selected currency, or "Choose for each investment".
  const amountSummary = preferences.preferredAmount === null
    ? t("Choose for each investment")
    : preferences.currencies.map((currency) => formatMoneyLabel(currency, Math.round((preferences.preferredAmount ?? 0) * 100))).join(" / ");

  if (wizard) {
    return (
      <SmartInvestWizard
        error={error}
        initial={wizard === "edit" ? preferences : { ...preferences, currencies: [...SMART_CURRENCIES] }}
        loans={loans}
        mode={wizard}
        onCancel={() => {
          setError("");
          setWizard(null);
        }}
        onSave={(next) => void save(next)}
        originators={originators}
        saving={saving}
      />
    );
  }

  if (state === "paused") {
    return (
      <main className="si-page si-inactive-page">
        <PageHead title={t("Smart Invest")} />
        <div className="si-state-panel si-paused">
          <h2 className="h4"><span aria-hidden="true" className="si-state-pause-dot" />{t("Smart Invest is paused.")}</h2>
          <p>{t("Your preferences are saved. Resume to see opportunities that match them.")}</p>
          <dl className="si-state-saved">
            <div><dt>{t("Preferred investment amount")}</dt><dd>{amountSummary}</dd></div>
            <div><dt>{t("Minimum annual interest rate")}</dt><dd>{preferences.minRate === null ? t("No preference") : t("{rate} per year", { rate: `${formatDecimal(preferences.minRate, 1)}%` })}</dd></div>
            <div><dt>{t("Maximum investment duration")}</dt><dd>{preferences.maxTerm === null ? t("No preference") : t("{count} months", { count: preferences.maxTerm })}</dd></div>
          </dl>
          {error ? <p className="u33-error" role="alert">{error}</p> : null}
          <div className="si-state-actions">
            <button className="btn si-state-primary" disabled={readonly || saving} onClick={() => void changeState("resume")} type="button">
              {resumeMutation.isPending ? t("Resuming...") : t("Resume Smart Invest")} <NiIcon name="arrow-right" />
            </button>
            <button className="btn btn-outline-light" disabled={readonly} onClick={() => setWizard("edit")} type="button">
              <NiIcon name="edit" /> {t("Edit preferences")}
            </button>
          </div>
        </div>
      </main>
    );
  }

  if (state !== "active") {
    return (
      <main className="si-page si-inactive-page">
        <PageHead title={t("Smart Invest")} />
        <div className="si-state-panel si-first-use">
          <div className="si-state-lead">
            <div className="si-state-symbol"><NiIcon name="repeat" /></div>
            <div>
              <h2 className="h4">{t("A simpler way to find investments.")}</h2>
              <p>{t("Choose your preferences. Smart Invest finds matching opportunities and can notify you of new matches.")}</p>
              <div className="si-state-actions">
                <button className="btn si-state-primary" disabled={readonly} onClick={() => setWizard("setup")} type="button">
                  {t("Set up Smart Invest")} <NiIcon name="arrow-right" />
                </button>
                <small>{t("You review and confirm each investment.")}</small>
              </div>
            </div>
          </div>
        </div>
      </main>
    );
  }

  const summary = preferenceSummary(preferences, originators);
  const sorted = sortMatches(matches, sort);
  return (
    <main className="si-page si-results-page r65-smart-results">
      <PageHead subtitle={t("Opportunities that match your preferences. You review and confirm each investment.")} title={t("Smart Invest")} />
      <div className="si-preferences card card-bordered">
        <div className="si-pref-main">
          <span className="si-active"><i />{t("Active")}</span>
          <div>
            <strong>{t("Your preferences")}</strong>
            <p>{summary}</p>
          </div>
        </div>
        <div className="si-pref-actions">
          <Button disabled={readonly} icon="edit" onClick={() => setWizard("edit")} size="sm">{t("Edit preferences")}</Button>
          <button className="si-link" disabled={readonly || saving} onClick={() => void changeState("pause")} type="button">{t("Pause Smart Invest")}</button>
        </div>
      </div>
      {error ? <p className="u33-error" role="alert">{error}</p> : null}
      <div className="si-results-toolbar">
        <div>
          <strong>{matches.length + soonMatches.length === 1 ? t("1 opportunity") : t("{count} opportunities", { count: matches.length + soonMatches.length })}</strong>
          <span> · {t("{count} open", { count: matches.length })} · {t("{count} coming soon", { count: soonMatches.length })}</span>
        </div>
        <div className="si-results-tools">
          <button className="si-link" data-action="si-why" onClick={() => setWhyOpen(true)} type="button">
            {t("Why these matches?")} <NiIcon name="info" />
          </button>
          {matches.length > 1 ? (
            <SelectFilter
              ariaLabel={t("Sort opportunities")}
              className="bxm-op-sort"
              label=""
              onChange={setSort}
              options={[
                { value: "closing", label: t("Closing soonest") },
                { value: "rate", label: t("Highest interest") },
                { value: "term", label: t("Shortest term") },
                { value: "funded", label: t("Most funded") }
              ]}
              selectClassName="bxm-op-select"
              value={sort}
            />
          ) : null}
        </div>
      </div>
      <div className="bxm-op-results">
        {matches.length + soonMatches.length === 0 ? (
          <div className="card card-bordered u33-state-card">
            <EmptyState actions={<Button disabled={readonly} icon="edit" onClick={() => setWizard("edit")}>{t("Edit preferences")}</Button>} icon="search" title={t("No matching opportunities yet")}>
              {t("You can adjust your preferences or wait for new opportunities.")}
            </EmptyState>
          </div>
        ) : (
          <div className="si-results-grid">
            {[...sorted, ...soonMatches].map((match) => <OpportunityCard key={match.loan_id} match={match} preferredAmount={preferences.preferredAmount} />)}
          </div>
        )}
      </div>
      {/* U33-DEC-30: the in-app and email match alerts have their own switches. */}
      <div className="si-notifications">
        <div>
          <NiIcon name="bell" />
          <span>{channelsLine(data.notification_channels)}</span>
        </div>
        <button className="si-link" data-action="si-notifications" onClick={() => setChannelsOpen(true)} type="button">
          {t("Notification settings")} <NiIcon name="chevron-right" />
        </button>
      </div>
      {channelsOpen ? <SmartInvestChannelsDialog current={data} onClose={() => setChannelsOpen(false)} /> : null}
      {whyOpen ? (
        <Dialog bodyClassName="u104-explanation" onClose={() => setWhyOpen(false)} size="sm" title={t("Why these matches?")}>
          <p>{t("These opportunities are open now and meet every preference you set: {summary}.", { summary })}</p>
          <p>{t("Within the security types, one matching type is enough. Smart Invest never invests or reserves money for you; you review and confirm each investment.")}</p>
          {preferences.preferredAmount !== null ? <p>{t("Your usual amount and your balance do not remove opportunities from the matches. When you cannot invest your usual amount in one of them, its card tells you why.")}</p> : null}
        </Dialog>
      ) : null}
    </main>
  );
}

