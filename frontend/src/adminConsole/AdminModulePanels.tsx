import { useEffect, useId, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  AccountAccessChangeRequestReasonCodeEnum,
  BorrowerEntityTypeEnum,
  BorrowerKybStatusEnum,
  CategoryEnum,
  CollateralTypeEnum,
  DecisionEnum,
  KycManualReviewDecisionRequestReasonCodeEnum,
  NewStatusEnum,
  NoteTypeEnum,
  PeriodPresetEnum,
  PurposeEnum,
  RedactionModeEnum,
  RepaymentTypeEnum,
  ReportGenerateRequestOutputFormatEnum,
  ReportTypeEnum,
  RiskRatingEnum,
  VisibilityEnum,
  AdminUserDocumentArtifactRequestOutputFormatEnum,
  useV1AuthAdminUsersAccessCreate,
  useV1AuthAdminUsersCreate,
  useV1AdminOpsUsersDocumentsArtifactCreate,
  useV1AdminOpsUsersDocumentsRetrieve,
  useV1AdminOpsUsersReadonlyImpersonationCreate,
  useV1DocumentsAdminTemplatesVersionsCreate,
  useV1DocumentsAdminTemplatesVersionsPublishCreate,
  useV1EntitiesAdminBorrowersCreate,
  useV1EntitiesAdminBorrowersPartialUpdate,
  useV1FxAdminExternalSettlementsCreate,
  useV1KycAdminCasesManualReviewCreate,
  useV1LedgerAdminBalanceAgeingScansCreate,
  useV1LedgerAdminBorrowerDisbursementsCreate,
  useV1LedgerAdminLenderDepositsCreate,
  useV1LedgerAdminPayoutInstructionsCreate,
  useV1LedgerAdminReconciliationSnapshotsCreate,
  useV1LedgerAdminWithdrawalRequestsCancelCreate,
  useV1LedgerAdminWithdrawalRequestsFinalizeCreate,
  useV1LoansAdminLoansCreate,
  useV1LoansAdminLoansOriginalScheduleList,
  useV1LoansAdminLoansPartialUpdate,
  useV1LoansAdminLoansPublishCreate,
  useV1LoansAdminLoansScheduleList,
  useOriginatorClaimsAdminLoansCreate,
  useOriginatorClaimsAdminLoansHold,
  useOriginatorClaimsAdminLoansPublish,
  useOriginatorClaimsAdminLoansRetrieve,
  useOriginatorClaimsAdminLoansUpdate,
  useOriginatorClaimsAdminLoanRepaymentsCreate,
  useOriginatorClaimsAdminOriginatorsCreate,
  useOriginatorClaimsAdminOriginatorsList,
  useOriginatorClaimsAdminOriginatorsUpdate,
  useOriginatorClaimsAdminSettlementsCreate,
  useOriginatorClaimsAdminSettlementsOutstandingList,
  useV1MarketplacePrimaryAdminLoansCancelFundingCreate,
  useV1MarketplacePrimaryAdminLoansExpiryScanCreate,
  useV1MarketplacePrimaryAdminOrdersReleaseBalanceCreate,
  useV1MarketplaceSecondaryAdminListingsApproveCreate,
  useV1MarketplaceSecondaryAdminListingsRejectCreate,
  useV1MarketplaceSecondaryAdminListingsRemoveCreate,
  useV1QaDevModeAdvanceCreate,
  useV1QaDevModeEnableCreate,
  useV1QaDevModeRetrieve,
  useV1QaDevModeRevertCreate,
  useV1ReportingAdminReportsCreate,
  useV1ServicingAdminBorrowerRepaymentsAdvancePreviewCreate,
  useV1ServicingAdminBorrowerRepaymentsCreate,
  useV1ServicingAdminRecoveriesCreate,
  useV1ServicingAdminRiskNotesCreate,
  useV1ServicingAdminStatusScanCreate,
  type AccountAccessChangeRequest,
  type AdminDashboardQueueItem,
  type AdminTask,
  type AccountAccessChangeRequestReasonCodeEnum as AccountAccessReasonCode,
  type AdminLookupResult,
  type AdvanceRepaymentScheduleRow,
  type AdminUserDocument,
  type AdminUserDocumentArtifactResponse,
  type AdminSecondaryMarketListingRow,
  type AdminUserDirectoryRow,
  type AdminUserCreateRequest,
  type BalanceAgeingScanRequest,
  type BorrowerEntity,
  type BorrowerDisbursementFinalizeRequest,
  type BorrowerEntityCreateRequest,
  type BorrowerEntityTypeEnum as BorrowerEntityType,
  type BorrowerKybStatusEnum as BorrowerKybStatus,
  type BorrowerRepaymentAdvancePreviewResponse,
  type BorrowerRepaymentRecordRequest,
  type CategoryEnum as DocumentCategory,
  type CollateralTypeEnum as LoanCollateralType,
  type DecisionEnum as KycDecision,
  type DocumentTemplateVersionCreateRequest,
  type FxExternalSettlementDeclareRequest,
  type InvestorPayoutInstructionRegisterRequest,
  type InvestorWithdrawalCancelRequest,
  type InvestorWithdrawalFinalizeRequest,
  type KycAdminCase,
  type KycManualReviewDecisionRequest,
  type KycManualReviewDecisionRequestReasonCodeEnum as KycReasonCode,
  type LenderDepositDeclareRequest,
  type Loan,
  type LoanCreateRequest,
  type LoanInstallment,
  type LoanOriginator,
  type LoanOriginatorCreate,
  type LoanRecoveryPaymentRecordRequest,
  type LoanRiskNoteCreateRequest,
  type LoanServicingStatusScanRequest,
  type NewStatusEnum as AccountNewStatus,
  type OriginalLoanScheduleRow,
  type OriginatorBorrowerRepaymentRequest,
  type OriginatorAdminLoanDetailResponse,
  type OriginatorLoanCreate,
  type OriginatorSettlementQueueRow,
  type OriginatorSettlementRequest,
  type PatchedLoanOriginatorUpdate,
  type PatchedOriginatorLoanCreate,
  type PatchedBorrowerEntityUpdateRequest,
  type PatchedLoanUpdateRequest,
  type PeriodPresetEnum as ReportPeriodPreset,
  type PurposeEnum as LoanPurpose,
  type QaDevModeState,
  type RepaymentTypeEnum as LoanRepaymentType,
  type PrimaryInvestmentOrderReleaseRequest,
  type PrimaryLoanCancellationRequest,
  type PrimaryLoanExpiryScanRequest,
  type ReconciliationSnapshotCreateRequest,
  type RedactionModeEnum as ReportRedactionMode,
  type ReportGenerateRequest,
  type ReportGenerateRequestOutputFormatEnum as ReportOutputFormat,
  type ReportGenerateResponse,
  type ReportTypeEnum as AdminReportType,
  type RiskRatingEnum as LoanRiskRating,
  type V1EntitiesAdminBorrowersListKybStatus as BorrowerListKybStatus,
  type V1LoansAdminLoansListStatus as LoanListStatus
} from "../api/generated/banxumApi";
import { writeReadonlyImpersonation } from "../api/client/impersonation";
import { isFixturePreview } from "../investorPortal/data";
import { formatDate, formatDateTime, formatMoneyMinor, formatRateBps } from "../investorPortal/format";
import { Banner, Button, Card, Chip, Empty, Field, Modal, Money, Tooltip, type Tone } from "../investorPortal/ui";
import { adminFormDefaults } from "./adminFixtures";
import {
  isWithdrawalQueueItem,
  useAuditEventsData,
  useAdminBorrowerLookupData,
  useAdminDocumentTemplateVersionLookupData,
  useAdminInvestorLookupData,
  useAdminKycCaseLookupData,
  useAdminLoanLookupData,
  useAdminPrimaryOrderLookupData,
  useAdminUserLookupData,
  useAdminSecondaryListingsData,
  useAdminOperationsDashboardData,
  useAdminTasksData,
  useAdminUsersDirectoryData,
  useAdminWithdrawalLookupData,
  useBorrowersData,
  useDocumentTemplateVersionsData,
  useFxDeltaReportData,
  useFxRealizedSettlementReportData,
  useInvestorBalanceSummaryData,
  useKycManualReviewsData,
  useLoansData
} from "./data";

type MutationLike = {
  isPending: boolean;
  error: unknown;
};

function copyAdminText(value: string) {
  const writeClipboard = navigator.clipboard?.writeText?.bind(navigator.clipboard);
  if (writeClipboard) {
    void writeClipboard(value);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "true");
  textarea.style.left = "-9999px";
  textarea.style.position = "fixed";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

function AdminCopyIdButton({ id, label }: { id: string; label: string }) {
  const [copied, setCopied] = useState(false);
  const accessibleLabel = copied ? "Copied" : label;
  return (
    <Tooltip content={accessibleLabel} focusable={false}>
      <Button
        aria-label={accessibleLabel}
        className="copy-id-btn icon-only"
        icon="copy"
        onClick={(event) => {
          event.stopPropagation();
          copyAdminText(id);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1400);
        }}
        size="sm"
        variant="ghost"
      />
    </Tooltip>
  );
}

const today = new Date().toLocaleDateString("en-CA", { timeZone: "Europe/Zurich" });
const defaultCollectionAccount = adminFormDefaults.collectionAccount;

function labelize(value: string | null | undefined) {
  if (!value) return "-";
  if (value === "written_off") return "Written Off";
  if (value === "recovery_write_off") return "Recovery/default";
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message;
  return "The request failed. Check the input, backend session, and audit logs.";
}

function idempotencyKey(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function refetchLive(refetch: () => Promise<unknown>) {
  if (!isFixturePreview) void refetch();
}

function intValue(value: string, fallback = 0) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

async function readTextFile(file: File | undefined) {
  return file ? file.text() : "";
}

function parseJsonObject(value: string, label: string) {
  try {
    const parsed: unknown = JSON.parse(value);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error(`${label} must be a JSON object.`);
    }
    return parsed as Record<string, unknown>;
  } catch (error) {
    if (error instanceof Error && error.message.endsWith("must be a JSON object.")) throw error;
    throw new Error(`${label} is not valid JSON.`, { cause: error });
  }
}

function parseJsonArray(value: string, label: string) {
  try {
    const parsed: unknown = JSON.parse(value || "[]");
    if (!Array.isArray(parsed)) throw new Error(`${label} must be a JSON list.`);
    return parsed;
  } catch (error) {
    if (error instanceof Error && error.message.endsWith("must be a JSON list.")) throw error;
    throw new Error(`${label} is not valid JSON.`, { cause: error });
  }
}

function recordValue(value: unknown) {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
}

function optionalMinorValue(value: string) {
  return value.trim() ? intValue(value) : null;
}

function bankAccountDetailsText(value: unknown) {
  if (!value || typeof value !== "object") return "";
  const maybeNotes = (value as { notes?: unknown }).notes;
  if (typeof maybeNotes === "string") return maybeNotes;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "";
  }
}

function bankAccountDetailsPayload(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return {};
  if (trimmed.startsWith("{")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) return parsed as Record<string, unknown>;
    } catch {
      return { notes: trimmed };
    }
  }
  return { notes: trimmed };
}

type DownloadableArtifact = Pick<
  ReportGenerateResponse | AdminUserDocumentArtifactResponse,
  "content" | "content_encoding" | "content_type" | "filename"
>;

function artifactContentBytes(response: DownloadableArtifact) {
  if (response.content_encoding.toLowerCase().includes("base64")) {
    const binary = window.atob(response.content);
    return Uint8Array.from(binary, (char) => char.charCodeAt(0));
  }
  return new TextEncoder().encode(response.content);
}

function downloadArtifact(response: DownloadableArtifact) {
  const blob = new Blob([artifactContentBytes(response)], {
    type: response.content_type || "application/octet-stream"
  });
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = response.filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

function downloadReportArtifact(response: ReportGenerateResponse) {
  downloadArtifact(response);
}

function statusTone(status: string): Tone {
  if (["approved", "active", "funded", "published", "repaid", "finalized", "current", "clean"].includes(status)) return "ok";
  if (["manual_review", "pending", "pending_review", "approval_requested", "late", "draft"].includes(status)) return "warn";
  if (["declined", "defaulted", "written_off", "locked", "closed", "restricted", "sanctions_hit"].includes(status)) return "bad";
  return "neutral";
}

function LoanFundingProgress({ loan }: { loan: Loan }) {
  const percent =
    loan.principal_minor > 0
      ? Math.min(100, Math.max(0, Math.round((loan.committed_principal_minor / loan.principal_minor) * 100)))
      : 0;

  return (
    <div className="admin-loan-funding-progress">
      <div className="admin-loan-funding-amounts">
        <span><Money amountMinor={loan.committed_principal_minor} currency={loan.currency} /></span>
        <span><Money amountMinor={loan.principal_minor} currency={loan.currency} /></span>
      </div>
      <div
        aria-label={`Funding progress for ${loan.title}`}
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={percent}
        className="admin-loan-funding-bar"
        role="progressbar"
      >
        <span style={{ width: `${percent}%` }} />
      </div>
      <div className="admin-loan-funding-caption">
        <span>Funded</span>
        <span>Total · {percent}% funded</span>
      </div>
    </div>
  );
}

function FieldGrid({ children }: { children: ReactNode }) {
  return <div className="admin-form-grid">{children}</div>;
}

function TextInput({
  label,
  value,
  onChange,
  required = false,
  type = "text",
  hint,
  placeholder,
  readOnly = false
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: string;
  hint?: string;
  placeholder?: string;
  readOnly?: boolean;
}) {
  return (
    <Field hint={hint} label={label}>
      <input
        aria-label={label}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        readOnly={readOnly}
        required={required}
        type={type}
        value={value}
      />
    </Field>
  );
}

function minorUnitPreview(value: string, currency: string) {
  const trimmed = value.trim();
  const normalizedCurrency = currency.trim().toUpperCase() || "CHF";
  if (!trimmed) return `Formatted amount: ${normalizedCurrency} -`;
  if (!/^-?\d+$/.test(trimmed)) return "Enter whole minor units only.";
  const parsed = Number.parseInt(trimmed, 10);
  if (!Number.isSafeInteger(parsed)) return "Amount is outside the safe display range.";
  return `Formatted amount: ${normalizedCurrency} ${formatMoneyMinor(parsed, normalizedCurrency)}`;
}

function MoneyMinorInput({
  label,
  value,
  onChange,
  currency,
  required = false,
  hint,
  placeholder,
  readOnly = false
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  currency: string;
  required?: boolean;
  hint?: string;
  placeholder?: string;
  readOnly?: boolean;
}) {
  const helper = [minorUnitPreview(value, currency), hint].filter(Boolean).join(" ");
  return (
    <Field hint={helper} label={label}>
      <input
        inputMode="numeric"
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        readOnly={readOnly}
        required={required}
        value={value}
      />
    </Field>
  );
}

function addMonthsToDateString(value: string, months: number) {
  const [yearRaw, monthRaw, dayRaw] = value.split("-").map((part) => Number.parseInt(part, 10));
  const year = Number.isFinite(yearRaw) ? yearRaw : new Date().getUTCFullYear();
  const month = Number.isFinite(monthRaw) ? monthRaw : 1;
  const day = Number.isFinite(dayRaw) ? dayRaw : 1;
  const targetMonthIndex = month - 1 + months;
  const lastDay = new Date(Date.UTC(year, targetMonthIndex + 1, 0)).getUTCDate();
  const date = new Date(Date.UTC(year, targetMonthIndex, Math.min(day, lastDay)));
  return date.toISOString().slice(0, 10);
}

function splitMinorAmount(totalMinor: number, parts: number, index: number) {
  if (parts <= 0) return 0;
  const base = Math.trunc(totalMinor / parts);
  const remainder = totalMinor - base * parts;
  return base + (index < remainder ? 1 : 0);
}

function previewScheduleRows(loan: Loan): LoanInstallment[] {
  const term = Math.max(1, loan.term_months || 1);
  // The loan's own schedule is generated from the financeable principal.
  const firstDueDate =
    loan.first_payment_date || addMonthsToDateString(loan.loan_start_date || loan.funding_deadline || today, 1);
  const schedulePrincipalMinor = loan.principal_minor;
  const totalInterestMinor =
    loan.total_scheduled_interest_minor ||
    Math.round((schedulePrincipalMinor * loan.interest_rate_bps * term) / 120000);
  return Array.from({ length: term }, (_, index) => {
    const principalMinor = splitMinorAmount(schedulePrincipalMinor, term, index);
    const interestMinor = splitMinorAmount(totalInterestMinor, term, index);
    return {
      id: `${loan.id}-preview-installment-${index + 1}`,
      schedule_version: loan.schedule_version || 1,
      installment_number: index + 1,
      due_date: addMonthsToDateString(firstDueDate, index),
      principal_minor: principalMinor,
      interest_minor: interestMinor,
      total_minor: principalMinor + interestMinor,
      paid_principal_minor: 0,
      paid_interest_minor: 0,
      outstanding_principal_minor: principalMinor,
      outstanding_interest_minor: interestMinor,
      outstanding_total_minor: principalMinor + interestMinor,
      is_paid: false,
      days_past_due: 0,
      status: "upcoming",
      row_type: "scheduled_installment",
      label: `Installment ${index + 1}`,
      payment_date: null,
      admin_overridden: false,
    };
  });
}

type ScheduleRowLike = {
  installment_number: number;
  due_date: string;
  principal_minor: number;
  interest_minor: number;
  total_minor: number;
  outstanding_after_minor: number;
};

function annuityScheduleRows(
  principalMinor: number,
  interestRateBps: number,
  termMonths: number,
  startDate: string,
  startNumber = 1,
  firstDueMonthOffset = 1
): ScheduleRowLike[] {
  const term = Math.max(1, Math.trunc(termMonths) || 1);
  const principal = Math.max(0, Math.trunc(principalMinor) || 0);
  const monthlyRate = interestRateBps / 120000;
  const paymentMinor =
    monthlyRate > 0
      ? Math.round((principal * monthlyRate) / (1 - Math.pow(1 + monthlyRate, -term)))
      : Math.round(principal / term);
  let outstanding = principal;
  return Array.from({ length: term }, (_, index) => {
    const interestMinor = Math.round(outstanding * monthlyRate);
    const isLast = index === term - 1;
    const principalPortion = isLast ? outstanding : Math.max(0, Math.min(outstanding, paymentMinor - interestMinor));
    outstanding -= principalPortion;
    return {
      installment_number: startNumber + index,
      due_date: addMonthsToDateString(startDate, firstDueMonthOffset + index),
      principal_minor: principalPortion,
      interest_minor: interestMinor,
      total_minor: principalPortion + interestMinor,
      outstanding_after_minor: outstanding
    };
  });
}

function originalPreviewScheduleRows(
  principalMinor: number,
  interestRateBps: number,
  termMonths: number,
  startDate: string,
  repaymentType: string,
  interestOnlyMonths: number
): ScheduleRowLike[] {
  const term = Math.max(1, Math.trunc(termMonths) || 1);
  const principal = Math.max(0, Math.trunc(principalMinor) || 0);
  const monthlyRate = interestRateBps / 120000;
  const monthlyInterest = Math.round(principal * monthlyRate);

  if (
    repaymentType === RepaymentTypeEnum.bullet_periodic_interest ||
    repaymentType === RepaymentTypeEnum.interest_only_then_bullet
  ) {
    let outstanding = principal;
    return Array.from({ length: term }, (_, index) => {
      const principalPortion = index === term - 1 ? outstanding : 0;
      outstanding -= principalPortion;
      return {
        installment_number: index + 1,
        due_date: addMonthsToDateString(startDate, index + 1),
        principal_minor: principalPortion,
        interest_minor: monthlyInterest,
        total_minor: principalPortion + monthlyInterest,
        outstanding_after_minor: outstanding
      };
    });
  }

  if (repaymentType === RepaymentTypeEnum.amortizing_principal_interest) {
    let outstanding = principal;
    return Array.from({ length: term }, (_, index) => {
      const principalPortion = splitMinorAmount(principal, term, index);
      const interestMinor = Math.round(outstanding * monthlyRate);
      outstanding -= principalPortion;
      return {
        installment_number: index + 1,
        due_date: addMonthsToDateString(startDate, index + 1),
        principal_minor: principalPortion,
        interest_minor: interestMinor,
        total_minor: principalPortion + interestMinor,
        outstanding_after_minor: Math.max(0, outstanding)
      };
    });
  }

  if (repaymentType === RepaymentTypeEnum.interest_only_then_amortizing) {
    const ioMonths = Math.trunc(interestOnlyMonths) || 0;
    if (ioMonths <= 0 || ioMonths >= term) return [];
    const interestOnlyRows = Array.from({ length: ioMonths }, (_, index) => ({
      installment_number: index + 1,
      due_date: addMonthsToDateString(startDate, index + 1),
      principal_minor: 0,
      interest_minor: monthlyInterest,
      total_minor: monthlyInterest,
      outstanding_after_minor: principal
    }));
    return [
      ...interestOnlyRows,
      ...annuityScheduleRows(
        principal,
        interestRateBps,
        term - ioMonths,
        startDate,
        ioMonths + 1,
        ioMonths + 1
      )
    ];
  }

  return annuityScheduleRows(principal, interestRateBps, term, startDate);
}

function previewOriginalScheduleRows(loan: Loan): OriginalLoanScheduleRow[] {
  if (!loan.is_refinancing || !loan.original_loan_start_date) return [];
  const paidNumbers = new Set(loan.pre_publication_paid_installments ?? []);
  return originalPreviewScheduleRows(
    loan.original_principal_minor,
    loan.original_interest_rate_bps ?? 0,
    loan.original_term_months ?? 1,
    loan.original_loan_start_date,
    loan.original_repayment_type ?? loan.repayment_type,
    loan.original_interest_only_months ?? 0
  ).map((row) => ({ ...row, paid_before_publication: paidNumbers.has(row.installment_number) }));
}

function isPastBusinessDate(value: string) {
  return value < today;
}

function dateDifferenceDays(later: string, earlier: string) {
  const laterTimestamp = Date.parse(`${later}T00:00:00Z`);
  const earlierTimestamp = Date.parse(`${earlier}T00:00:00Z`);
  if (!Number.isFinite(laterTimestamp) || !Number.isFinite(earlierTimestamp)) return 0;
  return Math.round((laterTimestamp - earlierTimestamp) / 86_400_000);
}

function lookupDisplay(option: AdminLookupResult) {
  return `${option.label}${option.meta ? ` - ${option.meta}` : ""} (${option.id})`;
}

function payloadRecord(option: AdminLookupResult | null | undefined) {
  if (!option || typeof option.payload !== "object" || option.payload === null) return {};
  return option.payload as Record<string, unknown>;
}

function payloadString(option: AdminLookupResult | null | undefined, key: string) {
  const value = payloadRecord(option)[key];
  return typeof value === "string" ? value : "";
}

function payloadNumber(option: AdminLookupResult | null | undefined, key: string) {
  const value = payloadRecord(option)[key];
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function compactInvestorReference(value: string) {
  return value.toUpperCase().match(/L[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{8,9}/)?.[0] ?? "";
}

function useDebouncedValue(value: string, delayMs = 250) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(timeout);
  }, [delayMs, value]);

  return debounced;
}

function AdminLookupInput({
  label,
  value,
  onChange,
  query,
  onQueryChange,
  options,
  loading,
  error,
  required = false,
  placeholder,
  hint,
  minLength = 3,
  onSelect
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  query: string;
  onQueryChange: (value: string) => void;
  options: AdminLookupResult[];
  loading?: boolean;
  error?: unknown;
  required?: boolean;
  placeholder?: string;
  hint?: string;
  minLength?: number;
  onSelect?: (option: AdminLookupResult) => void;
}) {
  const listId = useId();
  const selected = options.find((option) => option.id === value) ?? null;
  const queryIsUnselected = required && Boolean(query.trim()) && !value;
  const displayValue = query || (selected ? lookupDisplay(selected) : value);
  const helper = [
    value ? `Selected ID: ${value}` : hint || `Type at least ${minLength} characters to search.`,
    queryIsUnselected ? "Select a matching result before submitting." : "",
    loading ? "Searching..." : "",
    error ? errorMessage(error) : ""
  ].filter(Boolean).join(" ");

  function handleChange(rawValue: string) {
    const matched = options.find(
      (option) => option.id === rawValue || lookupDisplay(option) === rawValue
    );
    if (matched) {
      onChange(matched.id);
      onQueryChange(lookupDisplay(matched));
      onSelect?.(matched);
      return;
    }
    onQueryChange(rawValue);
    onChange("");
  }

  return (
    <Field hint={helper} label={label}>
      <input
        list={listId}
        onBlur={(event) => {
          const matched = options.find((option) => lookupDisplay(option) === event.target.value);
          if (matched) handleChange(lookupDisplay(matched));
        }}
        onChange={(event) => handleChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        aria-invalid={queryIsUnselected || undefined}
        onInvalid={(event) => {
          if (queryIsUnselected) {
            event.currentTarget.setCustomValidity("Select a matching result from the lookup before submitting.");
          }
        }}
        onInput={(event) => event.currentTarget.setCustomValidity("")}
        value={displayValue}
      />
      <datalist id={listId}>
        {options.map((option) => (
          <option key={option.id} value={lookupDisplay(option)} />
        ))}
      </datalist>
    </Field>
  );
}

function InvestorLookupInput({
  label = "Investor",
  value,
  onChange,
  query,
  onQueryChange,
  iban = "",
  status,
  required = false,
  placeholder,
  hint,
  onSelect,
  onResults
}: {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  query: string;
  onQueryChange: (value: string) => void;
  iban?: string;
  status?: string;
  required?: boolean;
  placeholder?: string;
  hint?: string;
  onSelect?: (option: AdminLookupResult) => void;
  onResults?: (options: AdminLookupResult[]) => void;
}) {
  const debouncedQuery = useDebouncedValue(query);
  const debouncedIban = useDebouncedValue(iban);
  const lookup = useAdminInvestorLookupData({ q: debouncedQuery, iban: debouncedIban, status, limit: 20 });
  useEffect(() => {
    onResults?.(lookup.data ?? []);
  }, [lookup.data, onResults]);
  return (
    <AdminLookupInput
      error={lookup.error}
      hint={hint || "Search by investor reference, full name, email, UUID, or matching payout IBAN."}
      label={label}
      loading={lookup.isFetching}
      onChange={onChange}
      onQueryChange={onQueryChange}
      onSelect={onSelect}
      options={lookup.data ?? []}
      placeholder={placeholder || "Reference, name, email, UUID, or IBAN"}
      query={query}
      required={required}
      value={value}
    />
  );
}

function UserLookupInput({
  value,
  onChange,
  query,
  onQueryChange,
  required = false,
  label = "User"
}: {
  value: string;
  onChange: (value: string) => void;
  query: string;
  onQueryChange: (value: string) => void;
  required?: boolean;
  label?: string;
}) {
  const debouncedQuery = useDebouncedValue(query);
  const lookup = useAdminUserLookupData({ q: debouncedQuery, limit: 20 });
  return (
    <AdminLookupInput
      error={lookup.error}
      hint="Search by UUID, full name, email, or investor reference."
      label={label}
      loading={lookup.isFetching}
      onChange={onChange}
      onQueryChange={onQueryChange}
      options={lookup.data ?? []}
      placeholder="Name, email, reference, or UUID"
      query={query}
      required={required}
      value={value}
    />
  );
}

function BorrowerLookupInput({
  value,
  onChange,
  query,
  onQueryChange,
  required = false,
  onSelect
}: {
  value: string;
  onChange: (value: string) => void;
  query: string;
  onQueryChange: (value: string) => void;
  required?: boolean;
  onSelect?: (option: AdminLookupResult) => void;
}) {
  const debouncedQuery = useDebouncedValue(query);
  const lookup = useAdminBorrowerLookupData({ q: debouncedQuery, limit: 20 });
  return (
    <AdminLookupInput
      error={lookup.error}
      hint="Search by borrower legal name, registration number, country, KYB status, or UUID."
      label="Borrower"
      loading={lookup.isFetching}
      onChange={onChange}
      onQueryChange={onQueryChange}
      onSelect={onSelect}
      options={lookup.data ?? []}
      placeholder="Borrower name, registration, or UUID"
      query={query}
      required={required}
      value={value}
    />
  );
}

function LoanLookupInput({
  value,
  onChange,
  query,
  onQueryChange,
  required = false,
  status,
  borrowerId,
  onSelect
}: {
  value: string;
  onChange: (value: string) => void;
  query: string;
  onQueryChange: (value: string) => void;
  required?: boolean;
  status?: string;
  borrowerId?: string;
  onSelect?: (option: AdminLookupResult) => void;
}) {
  const debouncedQuery = useDebouncedValue(query);
  const lookup = useAdminLoanLookupData({ q: debouncedQuery, status, borrower_id: borrowerId, limit: 20 });
  return (
    <AdminLookupInput
      error={lookup.error}
      hint="Search by loan title, borrower name, status, or UUID."
      label="Loan"
      loading={lookup.isFetching}
      onChange={onChange}
      onQueryChange={onQueryChange}
      onSelect={onSelect}
      options={lookup.data ?? []}
      placeholder="Loan title, borrower, status, or UUID"
      query={query}
      required={required}
      value={value}
    />
  );
}

function KycCaseLookupInput({
  value,
  onChange,
  query,
  onQueryChange,
  required = false,
  onSelect
}: {
  value: string;
  onChange: (value: string) => void;
  query: string;
  onQueryChange: (value: string) => void;
  required?: boolean;
  onSelect?: (option: AdminLookupResult) => void;
}) {
  const debouncedQuery = useDebouncedValue(query);
  const lookup = useAdminKycCaseLookupData({ q: debouncedQuery, limit: 20 });
  return (
    <AdminLookupInput
      error={lookup.error}
      hint="Search by person name, email, investor reference, subject reference, Didit session, or case UUID."
      label="KYC case"
      loading={lookup.isFetching}
      onChange={onChange}
      onQueryChange={onQueryChange}
      onSelect={onSelect}
      options={lookup.data ?? []}
      placeholder="Name, email, Didit session, reference, or UUID"
      query={query}
      required={required}
      value={value}
    />
  );
}

function WithdrawalLookupInput({
  value,
  onChange,
  query,
  onQueryChange,
  required = false,
  onSelect
}: {
  value: string;
  onChange: (value: string) => void;
  query: string;
  onQueryChange: (value: string) => void;
  required?: boolean;
  onSelect?: (option: AdminLookupResult) => void;
}) {
  const debouncedQuery = useDebouncedValue(query);
  const lookup = useAdminWithdrawalLookupData({ q: debouncedQuery, status: "requested", limit: 20 });
  return (
    <AdminLookupInput
      error={lookup.error}
      hint="Search by lender name, email, reference, withdrawal UUID, or IBAN suffix."
      label="Requested withdrawal"
      loading={lookup.isFetching}
      onChange={onChange}
      onQueryChange={onQueryChange}
      onSelect={onSelect}
      options={lookup.data ?? []}
      placeholder="Lender, amount context, date, IBAN suffix, or UUID"
      query={query}
      required={required}
      value={value}
    />
  );
}

function PrimaryOrderLookupInput({
  value,
  onChange,
  query,
  onQueryChange,
  required = false
}: {
  value: string;
  onChange: (value: string) => void;
  query: string;
  onQueryChange: (value: string) => void;
  required?: boolean;
}) {
  const debouncedQuery = useDebouncedValue(query);
  const lookup = useAdminPrimaryOrderLookupData({ q: debouncedQuery, limit: 20 });
  return (
    <AdminLookupInput
      error={lookup.error}
      hint="Search by investor name, email, reference, loan title, or order UUID."
      label="Primary order"
      loading={lookup.isFetching}
      onChange={onChange}
      onQueryChange={onQueryChange}
      options={lookup.data ?? []}
      placeholder="Investor, loan title, or order UUID"
      query={query}
      required={required}
      value={value}
    />
  );
}

function TemplateVersionLookupInput({
  value,
  onChange,
  query,
  onQueryChange,
  category,
  required = false
}: {
  value: string;
  onChange: (value: string) => void;
  query: string;
  onQueryChange: (value: string) => void;
  category?: string;
  required?: boolean;
}) {
  const debouncedQuery = useDebouncedValue(query);
  const lookup = useAdminDocumentTemplateVersionLookupData({ q: debouncedQuery, category, limit: 20 });
  return (
    <AdminLookupInput
      error={lookup.error}
      hint="Search by title, template key, legal review reference, or version UUID."
      label="Template version"
      loading={lookup.isFetching}
      onChange={onChange}
      onQueryChange={onQueryChange}
      options={lookup.data ?? []}
      placeholder="Template title, key, legal ref, or UUID"
      query={query}
      required={required}
      value={value}
    />
  );
}

function SelectInput<T extends string>({
  label,
  value,
  onChange,
  options,
  hint,
  optionLabel = labelize
}: {
  label: string;
  value: T;
  onChange: (value: T) => void;
  options: readonly T[];
  hint?: string;
  optionLabel?: (option: T) => string;
}) {
  return (
    <Field hint={hint} label={label}>
      <select onChange={(event) => onChange(event.target.value as T)} value={value}>
        {options.map((option) => (
          <option key={option} value={option}>
            {optionLabel(option)}
          </option>
        ))}
      </select>
    </Field>
  );
}

function TextAreaInput({
  label,
  value,
  onChange,
  required = false,
  rows = 3,
  hint,
  placeholder
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  rows?: number;
  hint?: string;
  placeholder?: string;
}) {
  return (
    <Field hint={hint} label={label}>
      <textarea
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        rows={rows}
        value={value}
      />
    </Field>
  );
}

function ActionFooter({
  mutation,
  previewMessage,
  successMessage,
  submitLabel
}: {
  mutation: MutationLike;
  previewMessage: string | null;
  successMessage?: string;
  submitLabel: string;
}) {
  return (
    <div className="admin-action-footer">
      {mutation.error ? (
        <Banner tone="bad" title="Action failed">
          {errorMessage(mutation.error)}
        </Banner>
      ) : null}
      {previewMessage ? (
        <Banner tone="info" title="Preview action recorded">
          {previewMessage}
        </Banner>
      ) : null}
      {successMessage ? (
        <Banner tone="ok" title="Action submitted">
          {successMessage}
        </Banner>
      ) : null}
      <Button disabled={mutation.isPending} type="submit" variant="primary">
        {submitLabel}
      </Button>
    </div>
  );
}

function PreviewNotice({ children }: { children: ReactNode }) {
  if (!isFixturePreview) return null;
  return (
    <Banner tone="info" title="Preview admin mode">
      {children}
    </Banner>
  );
}

function JsonPreview({ value }: { value: unknown }) {
  return <pre className="admin-json">{JSON.stringify(value, null, 2)}</pre>;
}

function OperationConfirmButton({
  children,
  title,
  description,
  details,
  confirmLabel,
  onConfirm,
  disabled = false,
  variant = "default"
}: {
  children: ReactNode;
  title: string;
  description: string;
  details: Array<{ label: string; value: ReactNode }>;
  confirmLabel: string;
  onConfirm: () => void;
  disabled?: boolean;
  variant?: "default" | "primary" | "danger";
}) {
  const [open, setOpen] = useState(false);

  function confirm() {
    onConfirm();
    setOpen(false);
  }

  return (
    <>
      <Button disabled={disabled} onClick={() => setOpen(true)} variant={variant}>
        {children}
      </Button>
      {open ? (
        <Modal title={title} onClose={() => setOpen(false)}>
          <div className="admin-confirm-body">
            <Banner tone={variant === "danger" ? "bad" : "warn"} title="Review before submitting">
              {description}
            </Banner>
            <div className="admin-detail-grid">
              {details.map((detail) => (
                <div className="admin-review-row" key={detail.label}>
                  <span>{detail.label}</span>
                  <strong>{detail.value}</strong>
                </div>
              ))}
            </div>
            <div className="modal-foot inline-foot">
              <Button onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={confirm} variant={variant === "danger" ? "danger" : "primary"}>
                {confirmLabel}
              </Button>
            </div>
          </div>
        </Modal>
      ) : null}
    </>
  );
}

function SectionHeader({
  title,
  description,
  action
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="admin-dashboard-head">
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}

function EntityTableHeader({
  title,
  description,
  search,
  onSearch,
  searchPlaceholder,
  filters,
  action
}: {
  title: string;
  description: string;
  search?: string;
  onSearch?: (value: string) => void;
  searchPlaceholder?: string;
  filters?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="admin-entity-head">
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      <div className="admin-entity-actions">
        {onSearch ? (
          <input
            aria-label={`Search ${title}`}
            className="admin-search-input"
            onChange={(event) => onSearch(event.target.value)}
            placeholder={searchPlaceholder || "Search"}
            value={search ?? ""}
          />
        ) : null}
        {filters}
        {action}
      </div>
    </div>
  );
}

function UnsupportedRemoveNote({ label }: { label: string }) {
  const explanation = `${label} records are retained for audit evidence.`;
  return (
    <Tooltip content={explanation} label={`No delete. ${explanation}`}>
      <span className="admin-action-note">No delete</span>
    </Tooltip>
  );
}

export function CompliancePanel() {
  const kycQuery = useKycManualReviewsData();
  const cases = useMemo(() => kycQuery.data ?? [], [kycQuery.data]);
  const [selectedCaseId, setSelectedCaseId] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 10;

  useEffect(() => {
    if (!selectedCaseId && cases[0]) setSelectedCaseId(cases[0].id);
  }, [cases, selectedCaseId]);

  const pageCount = Math.max(1, Math.ceil(cases.length / pageSize));
  useEffect(() => {
    if (page > pageCount - 1) setPage(0);
  }, [page, pageCount]);
  const pageCases = cases.slice(page * pageSize, page * pageSize + pageSize);

  return (
    <div className="admin-content">
      <PreviewNotice>Compliance cases are dummy Didit status mappings. Live mode reads only backend-owned KYC evidence.</PreviewNotice>
      <section className="admin-kpi-grid">
        <StatLike label="Manual review" value={cases.length} sub="Provider-routed cases" />
        <StatLike label="PEP/high risk" value={cases.filter((item) => item.detected_flags.some((flag) => flag.includes("pep") || flag.includes("high"))).length} sub="AML officer queue" />
        <StatLike label="Pending decision" value={cases.filter((item) => !item.decision_at).length} sub="No Garanta decision yet" />
        <StatLike label="Provider" value={cases[0]?.provider ?? "Didit"} sub="External KYC/KYB provider" />
      </section>

      <section className="admin-stack">
        <Card padded>
          <SectionHeader
            action={<Button icon="refresh" onClick={() => refetchLive(kycQuery.refetch)} size="sm">Refresh</Button>}
            description="Review KYC/KYB cases routed to Garanta manual review. Click a row to load it into the AML decision panel below. Sanctions and fraud blocks remain non-overridable server-side."
            title="KYC manual review"
          />
          {cases.length ? (
            <>
              <div className="table-wrap admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Reference</th>
                      <th>Status</th>
                      <th>Risk</th>
                      <th>Flags</th>
                      <th>Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageCases.map((item) => (
                      <tr
                        className={selectedCaseId === item.id ? "admin-selected-row" : ""}
                        key={item.id}
                        onClick={() => setSelectedCaseId(item.id)}
                      >
                        <td>
                          <strong>{item.user_full_name || labelize(item.subject_type)}</strong>
                          <span className="muted mono">{item.subject_reference || item.user_id || "-"}</span>
                        </td>
                        <td className="mono">{item.user_email || "-"}</td>
                        <td className="mono">{item.investor_reference || "-"}</td>
                        <td><Chip tone={statusTone(item.status)}>{labelize(item.status)}</Chip></td>
                        <td>{labelize(item.risk_classification)}</td>
                        <td>
                          <div className="row gap-4 wrap">
                            {item.detected_flags.length
                              ? item.detected_flags.map((flag) => <Chip key={flag} tone="warn">{labelize(flag)}</Chip>)
                              : "-"}
                          </div>
                        </td>
                        <td>{formatDateTime(item.updated_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {cases.length > pageSize ? (
                <div className="admin-pager">
                  <span className="muted">
                    Showing {page * pageSize + 1}&ndash;{Math.min(cases.length, (page + 1) * pageSize)} of {cases.length}
                  </span>
                  <div className="row gap-8">
                    <Button disabled={page === 0} onClick={() => setPage((current) => Math.max(0, current - 1))} size="sm">Previous</Button>
                    <span className="muted">Page {page + 1} of {pageCount}</span>
                    <Button disabled={page >= pageCount - 1} onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))} size="sm">Next</Button>
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <Empty icon="shield" title="No manual-review cases">
              KYC/KYB review items will appear when Didit routes a case to Garanta.
            </Empty>
          )}
        </Card>
        <ManualKycDecisionForm cases={cases} defaultCaseId={selectedCaseId} />
      </section>

    </div>
  );
}

type KycCaseDetail = {
  name: string;
  email: string;
  reference: string;
  subjectReference: string;
  subjectType: string;
  status: string;
  risk: string;
  flags: string[];
  blockingReason: string;
  providerSession: string;
  providerVerification: string;
  providerReport: string;
  amlScreening: string;
};

function buildKycCaseDetail(source: Record<string, unknown> | null | undefined): KycCaseDetail | null {
  if (!source) return null;
  const str = (key: string) => {
    const value = source[key];
    return typeof value === "string" ? value : value == null ? "" : String(value);
  };
  const flags = Array.isArray(source.detected_flags)
    ? source.detected_flags.filter((flag): flag is string => typeof flag === "string")
    : [];
  return {
    name: str("user_full_name"),
    email: str("user_email"),
    reference: str("investor_reference"),
    subjectReference: str("subject_reference"),
    subjectType: str("subject_type"),
    status: str("status"),
    risk: str("risk_classification"),
    flags,
    blockingReason: str("blocking_reason"),
    providerSession: str("provider_session_id"),
    providerVerification: str("provider_verification_id"),
    providerReport: str("provider_report_id"),
    amlScreening: str("aml_screening_id")
  };
}

function KycCaseDetailCard({ detail }: { detail: KycCaseDetail }) {
  const refs: Array<[string, string]> = [
    ["Reference", detail.reference],
    ["Subject", detail.subjectReference],
    ["Risk", detail.risk ? labelize(detail.risk) : ""],
    ["Report", detail.providerReport],
    ["AML screening", detail.amlScreening],
    ["Didit session", detail.providerSession],
    ["Verification", detail.providerVerification]
  ];
  return (
    <div className="kyc-detail">
      <div className="row spread wrap" style={{ gap: 8 }}>
        <div>
          <div className="col-strong">{detail.name || labelize(detail.subjectType) || "Selected case"}</div>
          <div className="muted mono" style={{ fontSize: 12 }}>{detail.email || detail.subjectReference || "-"}</div>
        </div>
        {detail.status ? <Chip tone={statusTone(detail.status)}>{labelize(detail.status)}</Chip> : null}
      </div>
      {detail.flags.length ? (
        <div className="row gap-4 wrap" style={{ marginTop: 8 }}>
          {detail.flags.map((flag) => <Chip key={flag} tone="warn">{labelize(flag)}</Chip>)}
        </div>
      ) : null}
      <div className="admin-context-bar" style={{ marginTop: 10 }}>
        {refs
          .filter(([, value]) => value)
          .map(([label, value]) => (
            <span key={label}>{label} <strong className="mono">{value}</strong></span>
          ))}
      </div>
      {detail.blockingReason ? (
        <p className="muted" style={{ fontSize: 12.5, margin: "8px 0 0" }}>{detail.blockingReason}</p>
      ) : null}
    </div>
  );
}

function ManualKycDecisionForm({ cases, defaultCaseId }: { cases: KycAdminCase[]; defaultCaseId: string }) {
  const [caseId, setCaseId] = useState(defaultCaseId);
  const [caseQuery, setCaseQuery] = useState(defaultCaseId);
  const [selectedOption, setSelectedOption] = useState<AdminLookupResult | null>(null);
  const [decision, setDecision] = useState<KycDecision>(DecisionEnum.approve);
  const [reasonCode, setReasonCode] = useState<KycReasonCode>(KycManualReviewDecisionRequestReasonCodeEnum.pep_review);
  const [note, setNote] = useState("");
  const [evidenceSummary, setEvidenceSummary] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1KycAdminCasesManualReviewCreate({
    mutation: {
      onSuccess: () => setSuccess("Manual-review decision was submitted and audited.")
    }
  });

  useEffect(() => {
    setCaseId(defaultCaseId);
    setCaseQuery(defaultCaseId);
  }, [defaultCaseId]);

  const tableCase = cases.find((item) => item.id === caseId) as unknown as Record<string, unknown> | undefined;
  const lookupPayload =
    selectedOption && selectedOption.id === caseId ? payloadRecord(selectedOption) : null;
  const detail = buildKycCaseDetail(tableCase ?? lookupPayload);

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: KycManualReviewDecisionRequest = { decision, reason_code: reasonCode, note, evidence_summary: evidenceSummary };
    if (isFixturePreview) {
      setPreview(`${labelize(decision)} recorded for ${detail?.name || caseId || "selected case"}.`);
      return;
    }
    mutation.mutate({ caseId, data });
  }

  return (
    <Card padded>
      <h2>Record AML decision</h2>
      <p>Select the case, review the person&apos;s details below, then record the decision. The backend enforces allowed status transitions.</p>
      <form className="admin-action-form" onSubmit={submit}>
        <KycCaseLookupInput
          onChange={setCaseId}
          onQueryChange={setCaseQuery}
          onSelect={setSelectedOption}
          query={caseQuery}
          required
          value={caseId}
        />
        {detail ? <KycCaseDetailCard detail={detail} /> : null}
        <FieldGrid>
          <SelectInput label="Decision" onChange={setDecision} options={Object.values(DecisionEnum)} value={decision} />
          <SelectInput label="Reason code" onChange={setReasonCode} options={Object.values(KycManualReviewDecisionRequestReasonCodeEnum)} value={reasonCode} />
        </FieldGrid>
        <TextAreaInput label="Officer note" onChange={setNote} value={note} />
        <TextAreaInput label="Evidence summary" onChange={setEvidenceSummary} value={evidenceSummary} />
        <ActionFooter mutation={mutation} previewMessage={preview} successMessage={success} submitLabel="Submit KYC decision" />
      </form>
    </Card>
  );
}

function AccountAccessForm({
  defaultUserId = "",
  defaultUserQuery = ""
}: {
  defaultUserId?: string;
  defaultUserQuery?: string;
}) {
  const [userId, setUserId] = useState(defaultUserId);
  const [userQuery, setUserQuery] = useState(defaultUserQuery || defaultUserId);
  const [newStatus, setNewStatus] = useState<AccountNewStatus>(NewStatusEnum.restricted);
  const [reasonCode, setReasonCode] = useState<AccountAccessReasonCode>(AccountAccessChangeRequestReasonCodeEnum.compliance_hold);
  const [note, setNote] = useState("");
  const [evidenceSummary, setEvidenceSummary] = useState("");
  const [cleanAccountConfirmed, setCleanAccountConfirmed] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1AuthAdminUsersAccessCreate({
    mutation: { onSuccess: () => setSuccess("Account access change was saved and audit-logged.") }
  });

  useEffect(() => {
    setUserId(defaultUserId);
    setUserQuery(defaultUserQuery || defaultUserId);
  }, [defaultUserId, defaultUserQuery]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: AccountAccessChangeRequest = {
      new_status: newStatus,
      reason_code: reasonCode,
      note,
      evidence_summary: evidenceSummary,
      clean_account_confirmed: cleanAccountConfirmed
    };
    if (isFixturePreview) {
      setPreview(`${labelize(newStatus)} status prepared for ${userId || "user"}.`);
      return;
    }
    mutation.mutate({ userId, data });
  }

  return (
    <Card padded>
      <SectionHeader
        description="Restrict, lock, reactivate or close a user account. Clean-account confirmation is an admin attestation until balance/holding checks are wired into this endpoint."
        title="Account access controls"
      />
      <form className="admin-action-form" onSubmit={submit}>
        <FieldGrid>
          <UserLookupInput
            label="User account"
            onChange={setUserId}
            onQueryChange={setUserQuery}
            query={userQuery}
            required
            value={userId}
          />
          <SelectInput label="New account status" onChange={setNewStatus} options={Object.values(NewStatusEnum)} value={newStatus} />
          <SelectInput label="Reason code" onChange={setReasonCode} options={Object.values(AccountAccessChangeRequestReasonCodeEnum)} value={reasonCode} />
        </FieldGrid>
        <TextAreaInput label="Admin note" onChange={setNote} value={note} />
        <TextAreaInput label="Evidence summary" onChange={setEvidenceSummary} value={evidenceSummary} />
        <label className="check-row">
          <input checked={cleanAccountConfirmed} onChange={(event) => setCleanAccountConfirmed(event.target.checked)} type="checkbox" />
          Clean/empty account checked where required for closure.
        </label>
        <ActionFooter mutation={mutation} previewMessage={preview} successMessage={success} submitLabel="Apply access change" />
      </form>
    </Card>
  );
}

function FinancePendingTasksTable({
  onSelectWithdrawal
}: {
  onSelectWithdrawal: (withdrawalId: string) => void;
}) {
  const taskQuery = useAdminTasksData({ pending_only: true, workstream: "finance", limit: 100 });
  const dashboardQuery = useAdminOperationsDashboardData({ due_window_days: 7, limit: 50 });
  const tasks = taskQuery.data ?? [];
  const queues = dashboardQuery.data?.queues;
  const queueItems: AdminDashboardQueueItem[] = queues
    ? [
        ...queues.bank_operations_pending,
        ...queues.withdrawals_requested,
        ...queues.forced_withdrawals_requested,
        ...queues.fx_settlement_deltas,
        ...queues.reconciliation_breaks
      ]
    : [];

  function selectWithdrawal(item: AdminDashboardQueueItem) {
    onSelectWithdrawal(item.object_id);
    window.setTimeout(() => {
      document.getElementById("admin-withdrawal-execution")?.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
    }, 0);
  }

  return (
    <Card padded>
      <div className="admin-panel-head">
        <div>
          <h2>Pending finance operations</h2>
          <p>Verification tasks and live bank, withdrawal, FX, and reconciliation queues requiring action.</p>
        </div>
        <Button
          icon="refresh"
          onClick={() => {
            refetchLive(taskQuery.refetch);
            refetchLive(dashboardQuery.refetch);
          }}
          size="sm"
        >
          Refresh
        </Button>
      </div>
      {taskQuery.error || dashboardQuery.error ? (
        <Banner tone="bad" title="Could not load pending finance work">
          {errorMessage(taskQuery.error || dashboardQuery.error)}
        </Banner>
      ) : null}
      {tasks.length || queueItems.length ? (
        <div className="table-wrap admin-table-wrap">
          <table className="admin-table admin-finance-work-table">
            <thead>
              <tr>
                <th>Work item</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Due</th>
                <th>Amount</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task: AdminTask) => (
                <tr key={`task-${task.id}`}>
                  <td>
                    <strong>{task.title}</strong>
                    <span className="mono muted">{labelize(task.task_type)}</span>
                  </td>
                  <td><Chip status={task.status}>{labelize(task.status)}</Chip></td>
                  <td><Chip dot={false} tone={task.priority === "high" || task.priority === "urgent" ? "warn" : "neutral"}>{labelize(task.priority)}</Chip></td>
                  <td className="mono">{task.due_at ? formatDateTime(task.due_at) : "-"}</td>
                  <td className="muted">-</td>
                  <td><span className="muted">Review in Tasks</span></td>
                </tr>
              ))}
              {queueItems.map((item) => (
                <tr key={`queue-${item.kind}-${item.id}`}>
                  <td>
                    <strong>{item.title}</strong>
                    <span className="mono muted">{labelize(item.kind)}</span>
                  </td>
                  <td><Chip status={item.status}>{labelize(item.status)}</Chip></td>
                  <td><Chip dot={false} tone={item.priority === "high" || item.priority === "urgent" ? "warn" : "neutral"}>{labelize(item.priority)}</Chip></td>
                  <td className="mono">{item.due_at ? formatDateTime(item.due_at) : item.due_date ? formatDate(item.due_date) : "-"}</td>
                  <td>{item.amount_minor === null ? <span className="muted">-</span> : <Money amountMinor={item.amount_minor} currency={item.currency} />}</td>
                  <td>
                    {isWithdrawalQueueItem(item) ? (
                      <Button onClick={() => selectWithdrawal(item)} size="sm">Resolve</Button>
                    ) : (
                      <span className="muted">Open from dashboard</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty icon="checkCircle" title="No pending finance operations">
          No finance task or operational queue currently requires action.
        </Empty>
      )}
    </Card>
  );
}

export function FinanceOpsPanel() {
  const [selectedWithdrawalId, setSelectedWithdrawalId] = useState("");
  return (
    <div className="admin-content">
      <PreviewNotice>Finance forms use dummy IDs in preview. Live submissions post to the ledger, FX and reconciliation services.</PreviewNotice>
      <FinancePendingTasksTable onSelectWithdrawal={setSelectedWithdrawalId} />
      <OriginatorSettlementQueue />
      <section className="admin-module-grid">
        <DepositForm />
        <PayoutInstructionForm />
        <BalanceSummaryLookup />
        <BalanceAgeingScanForm />
        <ReconciliationSnapshotForm />
        <WithdrawalOpsForm initialWithdrawalId={selectedWithdrawalId} />
        <BorrowerDisbursementForm />
        <FxAdminOps />
      </section>
    </div>
  );
}

function OriginatorSettlementQueue() {
  const queueQuery = useOriginatorClaimsAdminSettlementsOutstandingList({
    query: { enabled: !isFixturePreview, retry: false }
  });
  const rows: OriginatorSettlementQueueRow[] = queueQuery.data ?? [];
  const [selectedKey, setSelectedKey] = useState("");
  const selected = rows.find((row) => `${row.originator_id}:${row.currency}` === selectedKey)
    ?? rows[0];
  const [bookingDate, setBookingDate] = useState(today);
  const [valueDate, setValueDate] = useState(today);
  const [collectionAccount, setCollectionAccount] = useState(defaultCollectionAccount);
  const [bankReference, setBankReference] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const [evidenceReference, setEvidenceReference] = useState("");
  const [notes, setNotes] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useOriginatorClaimsAdminSettlementsCreate({
    mutation: {
      onSuccess: (response) => {
        setSuccess(`Settled ${response.currency} ${formatMoneyMinor(response.amount_minor, response.currency)} to the Loan Originator.`);
        void queueQuery.refetch();
      }
    }
  });

  function settle() {
    if (!selected) return;
    const data: OriginatorSettlementRequest = {
      originator_id: selected.originator_id,
      currency: selected.currency,
      purchase_ids: selected.purchase_ids,
      repayment_ids: selected.repayment_ids,
      booking_date: bookingDate,
      value_date: valueDate,
      collection_account_identifier: collectionAccount,
      bank_reference: bankReference,
      payment_reference: paymentReference,
      evidence_reference: evidenceReference,
      notes,
      idempotency_key: idempotencyKey("originator-settlement")
    };
    if (isFixturePreview) {
      setPreview("The selected originator purchase and servicing payables would be settled as one bank batch.");
      return;
    }
    mutation.mutate({ data });
  }

  return (
    <Card padded>
      <div className="row spread wrap gap-12">
        <div><h2>Loan Originator settlement queue</h2><p>Purchase proceeds and servicing proceeds accrue separately, then settle in an evidenced batch within five calendar days.</p></div>
        <Button icon="refresh" onClick={() => refetchLive(queueQuery.refetch)} size="sm">Refresh</Button>
      </div>
      {queueQuery.error ? <Banner tone="bad" title="Could not load originator payables">{errorMessage(queueQuery.error)}</Banner> : null}
      {rows.length ? (
        <div className="table-wrap admin-table-wrap">
          <table className="admin-table">
            <thead><tr><th>Originator</th><th>Currency</th><th>Total payable</th><th>Purchase proceeds</th><th>Servicing proceeds</th><th>Items</th><th>Settlement due</th><th /></tr></thead>
            <tbody>{rows.map((row) => {
              const key = `${row.originator_id}:${row.currency}`;
              return <tr className={selected && key === `${selected.originator_id}:${selected.currency}` ? "admin-selected-row" : ""} key={key} onClick={() => setSelectedKey(key)}><td><strong>{row.originator_name}</strong></td><td>{row.currency}</td><td><Money amountMinor={row.amount_minor} currency={row.currency} /></td><td><Money amountMinor={row.purchase_amount_minor} currency={row.currency} /></td><td><Money amountMinor={row.servicing_amount_minor} currency={row.currency} /></td><td>{row.purchase_count} purchases · {row.repayment_count} repayments</td><td>{formatDateTime(row.settlement_due_at)}</td><td><Button size="sm" onClick={(event) => { event.stopPropagation(); setSelectedKey(key); }}>Select</Button></td></tr>;
            })}</tbody>
          </table>
        </div>
      ) : (
        <Empty icon="checkCircle" title="No Loan Originator payables">Purchase and servicing payables awaiting batch settlement appear here.</Empty>
      )}
      {selected ? (
        <div className="admin-form-panel" style={{ marginTop: 16 }}>
          <div className="admin-context-bar"><strong>{selected.originator_name}</strong><span>{selected.currency}</span><Money amountMinor={selected.amount_minor} currency={selected.currency} /><span>Due {formatDateTime(selected.settlement_due_at)}</span></div>
          <FieldGrid>
            <TextInput label="Booking date" onChange={setBookingDate} required type="date" value={bookingDate} />
            <TextInput label="Value date" onChange={setValueDate} required type="date" value={valueDate} />
            <TextInput label="Collection account" onChange={setCollectionAccount} required value={collectionAccount} />
            <TextInput label="Bank reference" onChange={setBankReference} value={bankReference} />
            <TextInput label="Payment reference" onChange={setPaymentReference} value={paymentReference} />
            <TextInput label="Evidence reference" onChange={setEvidenceReference} value={evidenceReference} />
          </FieldGrid>
          <TextAreaInput label="Settlement notes" onChange={setNotes} value={notes} />
          <Button disabled={mutation.isPending} onClick={settle} variant="primary">{mutation.isPending ? "Settling..." : "Finalize originator batch settlement"}</Button>
          {mutation.error ? <Banner tone="bad" title="Settlement failed">{errorMessage(mutation.error)}</Banner> : null}
          {preview ? <Banner tone="info" title="Preview action">{preview}</Banner> : null}
          {success ? <Banner tone="ok" title="Settlement finalized">{success}</Banner> : null}
        </div>
      ) : null}
    </Card>
  );
}

function DepositForm() {
  const [investorUserId, setInvestorUserId] = useState(adminFormDefaults.investorUserId);
  const [investorQuery, setInvestorQuery] = useState(adminFormDefaults.investorUserId);
  const [amountMinor, setAmountMinor] = useState("2500000");
  const [currency, setCurrency] = useState("CHF");
  const [bookingDate, setBookingDate] = useState(today);
  const [valueDate, setValueDate] = useState(today);
  const [collectionAccount, setCollectionAccount] = useState(defaultCollectionAccount);
  const [payerName, setPayerName] = useState("");
  const [sourceIban, setSourceIban] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1LedgerAdminLenderDepositsCreate({
    mutation: { onSuccess: () => setSuccess("Deposit was ledgered and its source IBAN was added as a verified payout account.") }
  });

  function updateInvestorQuery(value: string) {
    setInvestorQuery(compactInvestorReference(value) || value);
  }

  function updatePaymentReference(value: string) {
    setPaymentReference(value);
    const compactReference = compactInvestorReference(value);
    if (compactReference && !investorUserId) setInvestorQuery(compactReference);
  }

  function updatePayerName(value: string) {
    setPayerName(value);
    if (!investorUserId && !investorQuery && value.trim().length >= 3) setInvestorQuery(value);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: LenderDepositDeclareRequest = {
      investor_user_id: investorUserId,
      amount_minor: intValue(amountMinor),
      currency,
      booking_date: bookingDate,
      value_date: valueDate,
      collection_account_identifier: collectionAccount,
      payer_name: payerName || undefined,
      payer_account_identifier: sourceIban,
      payment_reference: paymentReference || undefined,
      idempotency_key: idempotencyKey("deposit")
    };
    if (isFixturePreview) {
      setPreview(`${currency} ${formatMoneyMinor(data.amount_minor, currency)} deposit would be credited to ${investorUserId}.`);
      return;
    }
    mutation.mutate({ data });
  }

  return (
    <Card padded>
      <h2>Lender deposit</h2>
      <p>Declare a matched incoming transfer. Its valid source IBAN becomes a verified payout account for this investor.</p>
      <form className="admin-action-form" onSubmit={submit}>
        <FieldGrid>
          <InvestorLookupInput
            hint="Paste the bank-statement reference first when available. If omitted, search by payer first name/surname or email."
            label="Investor from bank reference"
            onChange={setInvestorUserId}
            onQueryChange={updateInvestorQuery}
            query={investorQuery}
            required
            value={investorUserId}
          />
          <MoneyMinorInput currency={currency} label="Amount minor units" onChange={setAmountMinor} required value={amountMinor} />
          <TextInput label="Currency" onChange={setCurrency} required value={currency} />
          <TextInput label="Booking date" onChange={setBookingDate} required type="date" value={bookingDate} />
          <TextInput label="Value date" onChange={setValueDate} required type="date" value={valueDate} />
          <TextInput label="Collection account" onChange={setCollectionAccount} required value={collectionAccount} />
        </FieldGrid>
        <FieldGrid>
          <TextInput label="Payer name" onChange={updatePayerName} value={payerName} />
          <TextInput
            hint="Required. Spaces are accepted; the server validates the country length and ISO 13616 checksum."
            label="Source IBAN"
            onChange={setSourceIban}
            required
            value={sourceIban}
          />
          <TextInput label="Payment reference" onChange={updatePaymentReference} value={paymentReference} />
        </FieldGrid>
        <ActionFooter mutation={mutation} previewMessage={preview} successMessage={success} submitLabel="Declare deposit" />
      </form>
    </Card>
  );
}

function PayoutInstructionForm() {
  const [investorUserId, setInvestorUserId] = useState(adminFormDefaults.investorUserId);
  const [investorQuery, setInvestorQuery] = useState(adminFormDefaults.investorUserId);
  const [investorMatches, setInvestorMatches] = useState<AdminLookupResult[]>([]);
  const [currency, setCurrency] = useState("CHF");
  const [iban, setIban] = useState(adminFormDefaults.payoutIban);
  const [name, setName] = useState(adminFormDefaults.payoutAccountName);
  const [verified, setVerified] = useState(true);
  const [notes, setNotes] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1LedgerAdminPayoutInstructionsCreate({
    mutation: { onSuccess: () => setSuccess("Payout IBAN was verified and added without removing existing verified accounts.") }
  });

  const ibanCollisionCount = investorMatches.reduce(
    (maxCount, option) => Math.max(maxCount, payloadNumber(option, "iban_match_count")),
    0
  );

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: InvestorPayoutInstructionRegisterRequest = {
      investor_user_id: investorUserId,
      currency,
      destination_iban: iban,
      destination_account_name: name,
      is_verified_usable: verified,
      notes
    };
    if (isFixturePreview) {
      setPreview(`Payout IBAN for ${investorUserId} would be marked ${verified ? "usable" : "not yet verified"}.`);
      return;
    }
    mutation.mutate({ data });
  }

  return (
    <Card padded>
      <h2>Payout instruction</h2>
      <p>Verify an additional IBAN used for withdrawals and day-60 forced returns. Existing verified IBANs remain usable.</p>
      <form className="admin-action-form" onSubmit={submit}>
        <FieldGrid>
          <InvestorLookupInput
            iban={iban}
            label="Investor / payout owner"
            onChange={setInvestorUserId}
            onQueryChange={setInvestorQuery}
            onResults={setInvestorMatches}
            query={investorQuery}
            required
            value={investorUserId}
          />
          <TextInput label="Currency" onChange={setCurrency} required value={currency} />
          <TextInput label="Destination IBAN" onChange={setIban} required value={iban} />
          <TextInput label="Account name" onChange={setName} required value={name} />
        </FieldGrid>
        {ibanCollisionCount > 1 ? (
          <Banner tone="warn" title="IBAN matches multiple investors">
            Review the matching investors before saving this payout instruction.
          </Banner>
        ) : null}
        <label className="check-row">
          <input checked={verified} onChange={(event) => setVerified(event.target.checked)} type="checkbox" />
          IBAN is usable and verified for this investor.
        </label>
        <TextAreaInput label="Notes" onChange={setNotes} value={notes} />
        <ActionFooter mutation={mutation} previewMessage={preview} successMessage={success} submitLabel="Register payout instruction" />
      </form>
    </Card>
  );
}

function BalanceSummaryLookup() {
  const [investorUserId, setInvestorUserId] = useState(adminFormDefaults.investorUserId);
  const [investorQuery, setInvestorQuery] = useState(adminFormDefaults.investorUserId);
  const [currency, setCurrency] = useState("CHF");
  const [submitted, setSubmitted] = useState(false);
  const query = useInvestorBalanceSummaryData({ investor_user_id: investorUserId, currency }, submitted && Boolean(investorUserId && currency));
  const summary = query.data;

  return (
    <Card padded>
      <h2>Investor balance lookup</h2>
      <p>Read the ledger-derived balance buckets used for ageing and withdrawal controls.</p>
      <form className="admin-action-form" onSubmit={(event) => { event.preventDefault(); setSubmitted(true); refetchLive(query.refetch); }}>
        <FieldGrid>
          <InvestorLookupInput
            label="Investor"
            onChange={setInvestorUserId}
            onQueryChange={setInvestorQuery}
            query={investorQuery}
            required
            value={investorUserId}
          />
          <TextInput label="Currency" onChange={setCurrency} required value={currency} />
        </FieldGrid>
        <Button type="submit" variant="primary">Load balance summary</Button>
      </form>
      {query.error ? <Banner tone="bad" title="Lookup failed">{errorMessage(query.error)}</Banner> : null}
      {summary ? (
        <div className="admin-mini-grid">
          <StatLike label="Available" value={<Money amountMinor={summary.total_available_minor} currency={summary.currency} />} />
          <StatLike label="Investable" value={<Money amountMinor={summary.investable_minor} currency={summary.currency} />} />
          <StatLike label="Withdraw-only" value={<Money amountMinor={summary.withdraw_only_minor} currency={summary.currency} />} />
          <StatLike label="Overdue" value={<Money amountMinor={summary.overdue_minor} currency={summary.currency} />} />
        </div>
      ) : null}
    </Card>
  );
}

function BalanceAgeingScanForm() {
  const [asOf, setAsOf] = useState("");
  const [currency, setCurrency] = useState("");
  const [dryRun, setDryRun] = useState(true);
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1LedgerAdminBalanceAgeingScansCreate({
    mutation: { onSuccess: (response) => setSuccess(`Scan completed with ${response.reminders_due.length} reminders and ${response.forced_withdrawal_requests.length} forced withdrawals.`) }
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: BalanceAgeingScanRequest = {
      as_of: asOf || undefined,
      currency: currency || undefined,
      dry_run: dryRun
    };
    if (isFixturePreview) {
      setPreview(`${dryRun ? "Dry-run" : "Live"} ageing scan would run for ${currency || "all currencies"}.`);
      return;
    }
    mutation.mutate({ data });
  }

  return (
    <Card padded>
      <h2>Balance ageing scan</h2>
      <p>Find reminder, forced-withdrawal and penalty-mode actions for 30/60-day balance lots.</p>
      <form className="admin-action-form" onSubmit={submit}>
        <FieldGrid>
          <TextInput label="As of timestamp" onChange={setAsOf} type="datetime-local" value={asOf} />
          <TextInput label="Currency filter" onChange={setCurrency} placeholder="Optional" value={currency} />
        </FieldGrid>
        <label className="check-row">
          <input checked={dryRun} onChange={(event) => setDryRun(event.target.checked)} type="checkbox" />
          Dry run only.
        </label>
        <ActionFooter mutation={mutation} previewMessage={preview} successMessage={success} submitLabel="Run ageing scan" />
      </form>
    </Card>
  );
}

function ReconciliationSnapshotForm() {
  const [currency, setCurrency] = useState("CHF");
  const [asOfDate, setAsOfDate] = useState(today);
  const [bankBalance, setBankBalance] = useState(isFixturePreview ? "100000000" : "");
  const [pendingException, setPendingException] = useState("0");
  const [notes, setNotes] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1LedgerAdminReconciliationSnapshotsCreate({
    mutation: { onSuccess: (response) => setSuccess(`Snapshot created. Difference: ${formatMoneyMinor(response.reconciliation_difference_minor, response.currency)} ${response.currency}.`) }
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: ReconciliationSnapshotCreateRequest = {
      currency,
      as_of_date: asOfDate,
      bank_stated_balance_minor: intValue(bankBalance),
      pending_exception_balance_minor: intValue(pendingException),
      notes
    };
    if (isFixturePreview) {
      setPreview(`${currency} reconciliation snapshot would compare bank balance ${formatMoneyMinor(data.bank_stated_balance_minor, currency)}.`);
      return;
    }
    mutation.mutate({ data });
  }

  return (
    <Card padded>
      <h2>Reconciliation snapshot</h2>
      <p>Compare bank-stated balances with ledger-derived investor liability, Garanta revenue and pending accounts.</p>
      <form className="admin-action-form" onSubmit={submit}>
        <FieldGrid>
          <TextInput label="Currency" onChange={setCurrency} required value={currency} />
          <TextInput label="As-of date" onChange={setAsOfDate} required type="date" value={asOfDate} />
          <MoneyMinorInput currency={currency} label="Bank stated balance minor" onChange={setBankBalance} required value={bankBalance} />
          <MoneyMinorInput currency={currency} label="Pending exceptions minor" onChange={setPendingException} value={pendingException} />
        </FieldGrid>
        <TextAreaInput label="Notes" onChange={setNotes} value={notes} />
        <ActionFooter mutation={mutation} previewMessage={preview} successMessage={success} submitLabel="Create snapshot" />
      </form>
    </Card>
  );
}

function WithdrawalOpsForm({ initialWithdrawalId = "" }: { initialWithdrawalId?: string }) {
  return (
    <Card id="admin-withdrawal-execution" padded>
      <h2>Withdrawal execution</h2>
      <p>Finalize executed withdrawals or cancel requested withdrawals before bank execution.</p>
      <WithdrawalExecutionForm initialWithdrawalId={initialWithdrawalId} />
    </Card>
  );
}

export function WithdrawalExecutionForm({
  initialWithdrawalId = "",
  allowLookup = true,
  onCompleted
}: {
  initialWithdrawalId?: string;
  allowLookup?: boolean;
  onCompleted?: () => void;
}) {
  const defaultWithdrawalId = initialWithdrawalId || adminFormDefaults.withdrawalId;
  const [withdrawalId, setWithdrawalId] = useState(defaultWithdrawalId);
  const [withdrawalQuery, setWithdrawalQuery] = useState(defaultWithdrawalId);
  const [bookingDate, setBookingDate] = useState(today);
  const [valueDate, setValueDate] = useState(today);
  const [collectionAccount, setCollectionAccount] = useState(defaultCollectionAccount);
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const finalize = useV1LedgerAdminWithdrawalRequestsFinalizeCreate({
    mutation: {
      onSuccess: () => {
        setSuccess("Withdrawal was finalized after bank execution.");
        onCompleted?.();
      }
    }
  });
  const cancel = useV1LedgerAdminWithdrawalRequestsCancelCreate({
    mutation: {
      onSuccess: () => {
        setSuccess("Withdrawal was cancelled and its reserved balance was released.");
        onCompleted?.();
      }
    }
  });

  useEffect(() => {
    if (!initialWithdrawalId) return;
    setWithdrawalId(initialWithdrawalId);
    setWithdrawalQuery(initialWithdrawalId);
    setPreview(null);
    setSuccess(null);
  }, [initialWithdrawalId]);

  function finalizeSubmit(event: FormEvent) {
    event.preventDefault();
    const data: InvestorWithdrawalFinalizeRequest = {
      booking_date: bookingDate,
      value_date: valueDate,
      collection_account_identifier: collectionAccount,
      admin_notes: reason,
      idempotency_key: idempotencyKey("withdrawal-finalize")
    };
    if (isFixturePreview) {
      setPreview(`Withdrawal ${withdrawalId} would be finalized after bank execution.`);
      return;
    }
    finalize.mutate({ withdrawalRequestId: withdrawalId, data });
  }

  function cancelSubmit() {
    const data: InvestorWithdrawalCancelRequest = {
      reason: reason || "Cancelled by admin before bank execution.",
      idempotency_key: idempotencyKey("withdrawal-cancel")
    };
    if (isFixturePreview) {
      setPreview(`Withdrawal ${withdrawalId} would be cancelled and funds released.`);
      return;
    }
    cancel.mutate({ withdrawalRequestId: withdrawalId, data });
  }

  return (
      <form className="admin-action-form" onSubmit={finalizeSubmit}>
        <FieldGrid>
          {allowLookup ? (
            <WithdrawalLookupInput
              onChange={setWithdrawalId}
              onQueryChange={setWithdrawalQuery}
              query={withdrawalQuery}
              required
              value={withdrawalId}
            />
          ) : (
            <Field label="Withdrawal request">
              <input readOnly value={withdrawalId} />
            </Field>
          )}
          <TextInput label="Booking date" onChange={setBookingDate} required type="date" value={bookingDate} />
          <TextInput label="Value date" onChange={setValueDate} required type="date" value={valueDate} />
          <TextInput label="Collection account" onChange={setCollectionAccount} required value={collectionAccount} />
        </FieldGrid>
        <TextAreaInput label="Admin note / cancel reason" onChange={setReason} value={reason} />
        {finalize.error || cancel.error ? <Banner tone="bad" title="Withdrawal action failed">{errorMessage(finalize.error || cancel.error)}</Banner> : null}
        {preview ? <Banner tone="info" title="Preview action recorded">{preview}</Banner> : null}
        {success ? <Banner tone="ok" title="Withdrawal action completed">{success}</Banner> : null}
        <div className="row gap-8 wrap">
          <Button disabled={finalize.isPending} type="submit" variant="primary">Finalize withdrawal</Button>
          <Button disabled={cancel.isPending} onClick={cancelSubmit} variant="danger">Cancel before execution</Button>
        </div>
      </form>
  );
}

function BorrowerDisbursementForm() {
  const [loanId, setLoanId] = useState(adminFormDefaults.loanId);
  const [loanQuery, setLoanQuery] = useState(adminFormDefaults.loanId);
  const [borrowerId, setBorrowerId] = useState(adminFormDefaults.borrowerId);
  const [borrowerQuery, setBorrowerQuery] = useState(adminFormDefaults.borrowerName);
  const [amountMinor, setAmountMinor] = useState(isFixturePreview ? "98000000" : "");
  const [feeMinor, setFeeMinor] = useState(isFixturePreview ? "2000000" : "");
  const [overrideNote, setOverrideNote] = useState("");
  const [currency, setCurrency] = useState("CHF");
  const [bookingDate, setBookingDate] = useState(today);
  const [valueDate, setValueDate] = useState(today);
  const [payeeName, setPayeeName] = useState(adminFormDefaults.borrowerName);
  const [payeeAccount, setPayeeAccount] = useState(adminFormDefaults.borrowerPayeeAccount);
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1LedgerAdminBorrowerDisbursementsCreate({
    mutation: { onSuccess: () => setSuccess("Borrower disbursement payable was cleared against collection cash.") }
  });

  function selectLoanOption(option: AdminLookupResult) {
    const selectedBorrowerId = payloadString(option, "borrower_id");
    const selectedBorrowerName = payloadString(option, "borrower_name");
    if (selectedBorrowerId) setBorrowerId(selectedBorrowerId);
    if (selectedBorrowerName) setBorrowerQuery(selectedBorrowerName);
    const selectedCurrency = payloadString(option, "currency");
    if (selectedCurrency) setCurrency(selectedCurrency);
  }

  function updateLoanId(value: string) {
    setLoanId(value);
    if (!value) {
      setBorrowerId("");
      setBorrowerQuery("");
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: BorrowerDisbursementFinalizeRequest = {
      loan_id: loanId,
      borrower_id: borrowerId,
      amount_minor: intValue(amountMinor),
      fee_minor: intValue(feeMinor),
      currency,
      booking_date: bookingDate,
      value_date: valueDate,
      collection_account_identifier: defaultCollectionAccount,
      payee_name: payeeName,
      payee_account_identifier: payeeAccount,
      override_note: overrideNote.trim() || undefined,
      idempotency_key: idempotencyKey("borrower-disbursement")
    };
    if (isFixturePreview) {
      setPreview(`Borrower disbursement ${formatMoneyMinor(data.amount_minor, currency)} ${currency} would be finalized for ${loanId}.`);
      return;
    }
    mutation.mutate({ data });
  }

  return (
    <Card padded>
      <h2>Borrower disbursement</h2>
      <p>Record external payout of an accepted funded loan to the borrower.</p>
      <form className="admin-action-form" onSubmit={submit}>
        <FieldGrid>
          <LoanLookupInput
            onChange={updateLoanId}
            onQueryChange={setLoanQuery}
            onSelect={selectLoanOption}
            query={loanQuery}
            required
            value={loanId}
          />
          {loanId ? (
            <Field hint={borrowerId ? `Derived borrower ID: ${borrowerId}` : "The selected loan did not expose a borrower."} label="Borrower">
              <input readOnly required value={borrowerQuery || borrowerId} />
            </Field>
          ) : (
            <BorrowerLookupInput
              onChange={setBorrowerId}
              onQueryChange={setBorrowerQuery}
              query={borrowerQuery}
              required
              value={borrowerId}
            />
          )}
          <MoneyMinorInput currency={currency} label="Amount minor units" onChange={setAmountMinor} required value={amountMinor} />
          <MoneyMinorInput currency={currency} label="BANXUM fee minor units" onChange={setFeeMinor} required value={feeMinor} />
          <TextInput label="Currency" onChange={setCurrency} required value={currency} />
          <TextInput label="Booking date" onChange={setBookingDate} required type="date" value={bookingDate} />
          <TextInput label="Value date" onChange={setValueDate} required type="date" value={valueDate} />
          <TextInput label="Payee name" onChange={setPayeeName} required value={payeeName} />
          <TextInput label="Payee account" onChange={setPayeeAccount} required value={payeeAccount} />
        </FieldGrid>
        <TextAreaInput
          hint="Contract defaults: fee = principal x success-fee bps, amount = principal - fee. A note is required when amounts differ from those defaults. Prefer Loans -> Manage -> Borrower disbursement for pre-filled defaults."
          label="Override note"
          onChange={setOverrideNote}
          value={overrideNote}
        />
        <ActionFooter mutation={mutation} previewMessage={preview} successMessage={success} submitLabel="Finalize disbursement" />
      </form>
    </Card>
  );
}

function FxAdminOps() {
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(today);
  const [loadReports, setLoadReports] = useState(false);
  const deltaQuery = useFxDeltaReportData({ start_date: startDate, end_date: endDate }, loadReports);
  const realizedQuery = useFxRealizedSettlementReportData({ start_date: startDate, end_date: endDate }, loadReports);
  const [soldCurrency, setSoldCurrency] = useState("CHF");
  const [boughtCurrency, setBoughtCurrency] = useState("EUR");
  const [soldAmount, setSoldAmount] = useState(isFixturePreview ? "44000000" : "");
  const [boughtAmount, setBoughtAmount] = useState(isFixturePreview ? "46190000" : "");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const settlementMutation = useV1FxAdminExternalSettlementsCreate({
    mutation: { onSuccess: () => setSuccess("FX external settlement was declared and linked to internal exchanges.") }
  });

  function declareSettlement(event: FormEvent) {
    event.preventDefault();
    const data: FxExternalSettlementDeclareRequest = {
      sold_currency: soldCurrency,
      bought_currency: boughtCurrency,
      sold_amount_minor: intValue(soldAmount),
      bought_amount_minor: intValue(boughtAmount),
      start_date: startDate,
      end_date: endDate,
      booking_date: endDate,
      value_date: endDate,
      collection_account_identifier: defaultCollectionAccount,
      notes: "Declared from admin finance ops screen.",
      idempotency_key: idempotencyKey("fx-settlement")
    };
    if (isFixturePreview) {
      setPreview(`${soldCurrency}/${boughtCurrency} settlement would declare sold ${formatMoneyMinor(data.sold_amount_minor, soldCurrency)} and bought ${formatMoneyMinor(data.bought_amount_minor, boughtCurrency)}.`);
      return;
    }
    settlementMutation.mutate({ data });
  }

  return (
    <Card padded className="admin-wide-card">
      <h2>FX settlement</h2>
      <p>Query platform FX deltas, compare realized bank execution and declare the external settlement.</p>
      <form className="admin-action-form" onSubmit={declareSettlement}>
        <FieldGrid>
          <TextInput label="Start date" onChange={setStartDate} required type="date" value={startDate} />
          <TextInput label="End date" onChange={setEndDate} required type="date" value={endDate} />
          <TextInput label="Sold currency" onChange={setSoldCurrency} required value={soldCurrency} />
          <TextInput label="Bought currency" onChange={setBoughtCurrency} required value={boughtCurrency} />
          <MoneyMinorInput currency={soldCurrency} label="Sold amount minor" onChange={setSoldAmount} required value={soldAmount} />
          <MoneyMinorInput currency={boughtCurrency} label="Bought amount minor" onChange={setBoughtAmount} required value={boughtAmount} />
        </FieldGrid>
        <div className="row gap-8 wrap">
          <Button onClick={() => { setLoadReports(true); refetchLive(deltaQuery.refetch); refetchLive(realizedQuery.refetch); }} type="button">
            Load reports
          </Button>
          <Button disabled={settlementMutation.isPending} type="submit" variant="primary">
            Declare settlement
          </Button>
        </div>
        {settlementMutation.error ? <Banner tone="bad" title="FX settlement failed">{errorMessage(settlementMutation.error)}</Banner> : null}
        {preview ? <Banner tone="info" title="Preview action recorded">{preview}</Banner> : null}
        {success ? <Banner tone="ok" title="Settlement submitted">{success}</Banner> : null}
      </form>
      <div className="admin-result-grid">
        <div>
          <h3>Internal delta</h3>
          {deltaQuery.data ? <JsonPreview value={deltaQuery.data} /> : <p className="muted">Load reports to view internal FX deltas.</p>}
        </div>
        <div>
          <h3>Realized settlement</h3>
          {realizedQuery.data ? <JsonPreview value={realizedQuery.data} /> : <p className="muted">Load reports to view realized settlement residuals.</p>}
        </div>
      </div>
    </Card>
  );
}

export function LoansPanel() {
  const [borrowerSearch, setBorrowerSearch] = useState("");
  const [originatorSearch, setOriginatorSearch] = useState("");
  const [borrowerKybStatus, setBorrowerKybStatus] = useState<BorrowerListKybStatus | "">("");
  const [loanSearch, setLoanSearch] = useState("");
  const [loanStatus, setLoanStatus] = useState<LoanListStatus | "">("");
  const debouncedBorrowerSearch = useDebouncedValue(borrowerSearch);
  const debouncedOriginatorSearch = useDebouncedValue(originatorSearch);
  const debouncedLoanSearch = useDebouncedValue(loanSearch);
  const borrowersQuery = useBorrowersData({
    limit: 100,
    q: debouncedBorrowerSearch || undefined,
    kyb_status: borrowerKybStatus || undefined
  });
  const loansQuery = useLoansData({
    limit: 100,
    q: debouncedLoanSearch || undefined,
    status: loanStatus || undefined
  });
  const originatorsQuery = useOriginatorClaimsAdminOriginatorsList(
    { query: debouncedOriginatorSearch || undefined },
    { query: { enabled: !isFixturePreview, retry: false } }
  );
  const borrowers = useMemo(() => borrowersQuery.data ?? [], [borrowersQuery.data]);
  const loans = useMemo(() => loansQuery.data ?? [], [loansQuery.data]);
  const originators = useMemo(() => originatorsQuery.data ?? [], [originatorsQuery.data]);
  const filteredOriginators = originators;
  const [selectedBorrowerId, setSelectedBorrowerId] = useState("");
  const [selectedLoanId, setSelectedLoanId] = useState("");
  const [managingLoan, setManagingLoan] = useState<Loan | null>(null);
  const [showBorrowerCreate, setShowBorrowerCreate] = useState(false);
  const [showLoanCreate, setShowLoanCreate] = useState(false);
  const [showOriginatorCreate, setShowOriginatorCreate] = useState(false);
  const [showOriginatorLoanCreate, setShowOriginatorLoanCreate] = useState(false);
  const [editingBorrower, setEditingBorrower] = useState<BorrowerEntity | null>(null);
  const [editingOriginator, setEditingOriginator] = useState<LoanOriginator | null>(null);
  const [editingLoan, setEditingLoan] = useState<Loan | null>(null);
  const selectedDirectLoan =
    loans.find((loan) => loan.id === selectedLoanId && loan.product_type === "direct")
    ?? loans.find((loan) => loan.product_type === "direct");
  const committedByCurrency = useMemo(() => {
    const totals = new Map<string, number>();
    for (const loan of loans) {
      totals.set(loan.currency, (totals.get(loan.currency) ?? 0) + loan.committed_principal_minor);
    }
    return [...totals.entries()];
  }, [loans]);

  useEffect(() => {
    if (!selectedBorrowerId && borrowers[0]) setSelectedBorrowerId(borrowers[0].id);
  }, [borrowers, selectedBorrowerId]);

  useEffect(() => {
    if (!selectedLoanId && loans[0]) setSelectedLoanId(loans[0].id);
  }, [loans, selectedLoanId]);

  return (
    <div className="admin-content">
      <PreviewNotice>Borrower and loan records are dummy setup data. Live actions call the backend entity, loan, marketplace and servicing modules.</PreviewNotice>
      <section className="admin-kpi-grid">
        <StatLike label="Borrowers" value={borrowers.length} sub={`${borrowers.filter((item) => item.can_transact).length} can transact`} />
        <StatLike label="Loan Originators" value={originators.length} sub={`${originators.filter((item) => item.status === "active").length} active`} />
        <StatLike label="Loans" value={loans.length} sub={`${loans.filter((item) => item.status === "published").length} published`} />
        <StatLike
          label="Committed"
          value={
            committedByCurrency.length ? (
              <span className="col gap-4">
                {committedByCurrency.map(([currency, amountMinor]) => (
                  <Money amountMinor={amountMinor} currency={currency} key={currency} />
                ))}
              </span>
            ) : (
              <Money amountMinor={0} currency="CHF" />
            )
          }
          sub="Committed principal across listed loans"
        />
        <StatLike label="Risk items" value={loans.filter((item) => ["late", "defaulted"].includes(item.status)).length} sub="Servicing attention" />
      </section>

      <section className="admin-stack">
        <Card padded>
          <EntityTableHeader
            action={(
              <div className="row gap-8 wrap">
                <Button icon="refresh" onClick={() => refetchLive(originatorsQuery.refetch)} size="sm">Refresh</Button>
                <Button icon="plus" onClick={() => setShowOriginatorCreate(true)} size="sm" variant="primary">Create Loan Originator</Button>
              </div>
            )}
            description="Offline-KYB accounting entities that own and sell final-borrower loan claims. They do not have portal login accounts."
            onSearch={setOriginatorSearch}
            search={originatorSearch}
            searchPlaceholder="Search public or legal name, or registration number"
            title="Loan Originators"
          />
          {originatorsQuery.error ? <Banner tone="bad" title="Could not load Loan Originators">{errorMessage(originatorsQuery.error)}</Banner> : null}
          {filteredOriginators.length ? (
            <div className="table-wrap admin-table-wrap">
              <table className="admin-table">
                <thead><tr><th>Originator</th><th>Registration</th><th>Jurisdiction</th><th>Status</th><th>Settlement account</th><th>Premium fee share</th><th>Actions</th></tr></thead>
                <tbody>
                  {filteredOriginators.map((originator) => (
                    <tr key={originator.id}>
                      <td><div className="col gap-4"><strong>{originator.public_name}</strong><span className="muted">{originator.legal_name}</span><AdminCopyIdButton id={originator.id} label="Copy Loan Originator ID" /></div></td>
                      <td>{originator.registration_number}</td>
                      <td>{originator.jurisdiction}</td>
                      <td><Chip tone={statusTone(originator.status ?? "inactive")}>{labelize(originator.status)}</Chip></td>
                      <td><div className="col gap-4"><span>{originator.settlement_account_name}</span><span className="mono muted">{originator.settlement_iban}</span></div></td>
                      <td>{formatRateBps(originator.default_premium_fee_bps ?? 5000)}</td>
                      <td><Button onClick={() => setEditingOriginator(originator)} size="sm">Edit</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty icon="market" title={originators.length ? "No matching Loan Originators" : "No Loan Originators"}>
              {originators.length ? "Adjust the search terms." : "Create and complete offline KYB for an originator before importing a claim loan."}
            </Empty>
          )}
        </Card>
        <Card padded>
          <EntityTableHeader
            action={
              <div className="row gap-8 wrap">
                <Button icon="refresh" onClick={() => refetchLive(borrowersQuery.refetch)} size="sm">Refresh</Button>
                <Button icon="plus" onClick={() => setShowBorrowerCreate(true)} size="sm" variant="primary">Create borrower</Button>
              </div>
            }
            description="Entity data is admin-entered. Borrower portal accounts do not exist."
            filters={
              <select
                aria-label="Filter borrowers by KYB status"
                onChange={(event) => setBorrowerKybStatus(event.target.value as BorrowerListKybStatus | "")}
                value={borrowerKybStatus}
              >
                <option value="">All KYB statuses</option>
                {Object.values(BorrowerKybStatusEnum).map((status) => (
                  <option key={status} value={status}>{labelize(status)}</option>
                ))}
              </select>
            }
            onSearch={setBorrowerSearch}
            search={borrowerSearch}
            searchPlaceholder="Search legal name, registration, classification, address, contact, country, UUID"
            title="Borrowers"
          />
          {borrowersQuery.error ? <Banner tone="bad" title="Could not load borrowers">{errorMessage(borrowersQuery.error)}</Banner> : null}
          {borrowers.length ? (
            <div className="table-wrap admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Entity</th>
                    <th>Classification</th>
                    <th>KYB</th>
                    <th>Country</th>
                    <th>Financials</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {borrowers.map((borrower) => (
                    <tr
                      className={selectedBorrowerId === borrower.id ? "admin-selected-row" : ""}
                      key={borrower.id}
                      onClick={() => setSelectedBorrowerId(borrower.id)}
                    >
                      <td><strong>{borrower.legal_name}</strong><span className="mono muted">{borrower.id}</span></td>
                      <td>
                        {borrower.business_classification ? (
                          <div className="col gap-4">
                            <span>{borrower.business_classification}</span>
                            {borrower.business_classification_public ? <Chip tone="ok">Public</Chip> : <Chip tone="neutral">Internal</Chip>}
                          </div>
                        ) : "-"}
                      </td>
                      <td><Chip tone={statusTone(borrower.kyb_status)}>{labelize(borrower.kyb_status)}</Chip></td>
                      <td>{borrower.country || "-"}</td>
                      <td>
                        <div className="col gap-4">
                          <span>Assets <Money amountMinor={borrower.assets_minor} currency={borrower.financials_currency} /></span>
                          <span>Revenue <Money amountMinor={borrower.revenue_last_year_minor} currency={borrower.financials_currency} /></span>
                        </div>
                      </td>
                      <td>
                        <div className="row gap-8 wrap" onClick={(event) => event.stopPropagation()}>
                          <Button onClick={() => setEditingBorrower(borrower)} size="sm">Edit</Button>
                          <UnsupportedRemoveNote label="Borrower" />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty icon="market" title="No borrowers">
              Create a borrower entity before drafting loans.
            </Empty>
          )}
        </Card>
        <Card padded>
          <EntityTableHeader
            action={
              <div className="row gap-8 wrap">
                <Button icon="refresh" onClick={() => refetchLive(loansQuery.refetch)} size="sm">Refresh</Button>
                <Button icon="plus" onClick={() => setShowLoanCreate(true)} size="sm" variant="primary">Create direct loan</Button>
                <Button icon="plus" onClick={() => setShowOriginatorLoanCreate(true)} size="sm">Import originator claim loan</Button>
              </div>
            }
            description="Direct loans use borrower KYB and a funding round. Originator claim loans use an immutable imported schedule, anonymized borrower snapshot, executable yield pricing, and immediate assignment."
            filters={
              <select
                aria-label="Filter loans by status"
                onChange={(event) => setLoanStatus(event.target.value as LoanListStatus | "")}
                value={loanStatus}
              >
                <option value="">All loan statuses</option>
                {["draft", "published", "funded", "active", "late", "defaulted", "repaid", "written_off", "cancelled"].map((status) => (
                  <option key={status} value={status}>{labelize(status)}</option>
                ))}
              </select>
            }
            onSearch={setLoanSearch}
            search={loanSearch}
            searchPlaceholder="Search title, borrower, originator, product, status, UUID"
            title="Loans"
          />
          {loansQuery.error ? <Banner tone="bad" title="Could not load loans">{errorMessage(loansQuery.error)}</Banner> : null}
          {loans.length ? (
            <div className="table-wrap admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Loan / counterparty</th>
                    <th>Product</th>
                    <th>Status</th>
                    <th>Progress</th>
                    <th>Yield</th>
                    <th>LTV</th>
                    <th>Availability date</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {loans.map((loan) => (
                    <tr
                      className={selectedLoanId === loan.id ? "admin-selected-row" : ""}
                      key={loan.id}
                      onClick={() => {
                        setSelectedLoanId(loan.id);
                        setSelectedBorrowerId(loan.borrower_id ?? "");
                      }}
                    >
                      <td>
                        <div className="col gap-4 admin-loan-name-cell">
                          <strong>{loan.title}</strong>
                          <span className="muted">
                            {loan.product_type === "originator_claim"
                              ? `Originator: ${loan.originator_name ?? "-"} · Borrower: ${loan.borrower_name ?? "Anonymized"}`
                              : `Borrower: ${loan.borrower_name ?? "-"}`}
                          </span>
                          <span className="mono muted">{loan.id}</span>
                        </div>
                      </td>
                      <td><Chip tone={loan.product_type === "originator_claim" ? "info" : "neutral"}>{loan.product_type === "originator_claim" ? "Originator claim" : "Direct"}</Chip></td>
                      <td><Chip tone={statusTone(loan.opportunity_status ?? loan.status)}>{labelize(loan.opportunity_status ?? loan.status)}</Chip></td>
                      <td><LoanFundingProgress loan={loan} /></td>
                      <td>{formatRateBps(loan.yield_bps)}</td>
                      <td>{loan.ltv_bps === null ? "-" : formatRateBps(loan.ltv_bps)}</td>
                      <td>{formatDate(loan.product_type === "originator_claim" ? loan.maturity_date : loan.funding_deadline)}</td>
                      <td>
                        <div className="row gap-8 wrap" onClick={(event) => event.stopPropagation()}>
                          {loan.product_type === "direct" ? <Button onClick={() => setEditingLoan(loan)} size="sm">Edit</Button> : null}
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={() => {
                              setSelectedLoanId(loan.id);
                              setManagingLoan(loan);
                            }}
                          >
                            Manage
                          </Button>
                          {loan.status !== "published" ? <UnsupportedRemoveNote label="Loan" /> : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty icon="docs" title="No loans">
              Draft loans will appear here once created.
            </Empty>
          )}
        </Card>
      </section>

      <section className="admin-stack">
        <SecondaryMarketApprovalsTable />
        <ServicingOpsForm
          defaultLoanId={selectedDirectLoan?.id ?? ""}
          defaultLoanTitle={selectedDirectLoan?.title ?? ""}
        />
      </section>
      {managingLoan ? (
        managingLoan.product_type === "originator_claim" ? (
          <OriginatorLoanManageModal
            loan={loans.find((item) => item.id === managingLoan.id) ?? managingLoan}
            originators={originators}
            onChanged={() => refetchLive(loansQuery.refetch)}
            onClose={() => setManagingLoan(null)}
          />
        ) : (
          <ManageLoanModal
            loan={loans.find((item) => item.id === managingLoan.id) ?? managingLoan}
            onChanged={() => refetchLive(loansQuery.refetch)}
            onClose={() => setManagingLoan(null)}
          />
        )
      ) : null}
      {showOriginatorCreate ? (
        <Modal title="Create Loan Originator" onClose={() => setShowOriginatorCreate(false)} wide>
          <LoanOriginatorForm onSaved={() => { setShowOriginatorCreate(false); refetchLive(originatorsQuery.refetch); }} />
        </Modal>
      ) : null}
      {editingOriginator ? (
        <Modal title={`Edit Loan Originator - ${editingOriginator.public_name}`} onClose={() => setEditingOriginator(null)} wide>
          <LoanOriginatorForm originator={editingOriginator} onSaved={() => { setEditingOriginator(null); refetchLive(originatorsQuery.refetch); }} />
        </Modal>
      ) : null}
      {showOriginatorLoanCreate ? (
        <Modal title="Import originator claim loan" onClose={() => setShowOriginatorLoanCreate(false)} wide>
          <OriginatorLoanCreateForm originators={originators} onCreated={() => { setShowOriginatorLoanCreate(false); refetchLive(loansQuery.refetch); }} />
        </Modal>
      ) : null}
      {showBorrowerCreate ? (
        <Modal title="Create borrower" onClose={() => setShowBorrowerCreate(false)}>
          <BorrowerCreateForm
            onCreated={() => {
              setShowBorrowerCreate(false);
              refetchLive(borrowersQuery.refetch);
            }}
          />
        </Modal>
      ) : null}
      {showLoanCreate ? (
        <Modal title="Create loan draft" onClose={() => setShowLoanCreate(false)}>
          <LoanCreateForm
            defaultBorrowerId={selectedBorrowerId}
            onCreated={() => {
              setShowLoanCreate(false);
              refetchLive(loansQuery.refetch);
            }}
          />
        </Modal>
      ) : null}
      {editingBorrower ? (
        <Modal title={`Edit borrower - ${editingBorrower.legal_name}`} onClose={() => setEditingBorrower(null)}>
          <BorrowerEditForm
            borrower={editingBorrower}
            onSaved={() => {
              setEditingBorrower(null);
              refetchLive(borrowersQuery.refetch);
            }}
          />
        </Modal>
      ) : null}
      {editingLoan ? (
        <Modal title={`Edit loan - ${editingLoan.title}`} onClose={() => setEditingLoan(null)}>
          <LoanEditForm
            loan={editingLoan}
            onSaved={() => {
              setEditingLoan(null);
              refetchLive(loansQuery.refetch);
            }}
          />
        </Modal>
      ) : null}
    </div>
  );
}

function LoanOriginatorForm({
  originator,
  onSaved
}: {
  originator?: LoanOriginator;
  onSaved?: () => void;
}) {
  const [legalName, setLegalName] = useState(originator?.legal_name ?? "");
  const [publicName, setPublicName] = useState(originator?.public_name ?? "");
  const [registrationNumber, setRegistrationNumber] = useState(originator?.registration_number ?? "");
  const [jurisdiction, setJurisdiction] = useState(originator?.jurisdiction ?? "CH");
  const [registeredAddress, setRegisteredAddress] = useState(originator?.registered_address ?? "");
  const [contactInfo, setContactInfo] = useState(originator?.contact_info ?? "");
  const [accountName, setAccountName] = useState(originator?.settlement_account_name ?? "");
  const [iban, setIban] = useState(originator?.settlement_iban ?? "");
  const [bic, setBic] = useState(originator?.settlement_bic ?? "");
  const [kybEvidence, setKybEvidence] = useState(originator?.kyb_evidence_reference ?? "");
  const [kybNotes, setKybNotes] = useState(originator?.kyb_aml_observations ?? "");
  const [riskNotes, setRiskNotes] = useState(originator?.risk_observations ?? "");
  const [status, setStatus] = useState<LoanOriginatorCreate["status"]>(originator?.status ?? "inactive");
  const [feeBps, setFeeBps] = useState(String(originator?.default_premium_fee_bps ?? 5000));
  const [preview, setPreview] = useState<string | null>(null);
  const createMutation = useOriginatorClaimsAdminOriginatorsCreate({ mutation: { onSuccess: onSaved } });
  const updateMutation = useOriginatorClaimsAdminOriginatorsUpdate({ mutation: { onSuccess: onSaved } });
  const mutation = originator ? updateMutation : createMutation;

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: LoanOriginatorCreate = {
      legal_name: legalName,
      public_name: publicName,
      registration_number: registrationNumber,
      jurisdiction,
      registered_address: registeredAddress,
      contact_info: contactInfo,
      settlement_account_name: accountName,
      settlement_iban: iban,
      settlement_bic: bic,
      kyb_evidence_reference: kybEvidence,
      kyb_aml_observations: kybNotes,
      risk_observations: riskNotes,
      status,
      default_premium_fee_bps: intValue(feeBps, 5000)
    };
    if (isFixturePreview) {
      setPreview(`${publicName || legalName} would be ${originator ? "updated" : "created"}.`);
      return;
    }
    if (originator) {
      const patchData: PatchedLoanOriginatorUpdate = data;
      updateMutation.mutate({ originatorId: originator.id, data: patchData });
    } else {
      createMutation.mutate({ data });
    }
  }

  return (
    <form className="admin-action-form" onSubmit={submit}>
      <Banner tone="neutral" title="Accounting entity, not a portal user">
        Complete KYB offline and retain the evidence reference. Activating the originator permits its reviewed claim loans to publish; it does not create login credentials.
      </Banner>
      <FieldGrid>
        <TextInput label="Legal name" onChange={setLegalName} required value={legalName} />
        <TextInput label="Public name" onChange={setPublicName} required value={publicName} />
        <TextInput label="Registration number" onChange={setRegistrationNumber} required value={registrationNumber} />
        <TextInput label="Jurisdiction" onChange={setJurisdiction} required value={jurisdiction} />
        <SelectInput label="Status" onChange={(value) => setStatus(value as LoanOriginatorCreate["status"])} options={["inactive", "active", "blocked"]} value={status ?? "inactive"} />
        <TextInput hint="Default 5000 = BANXUM receives 50% of the originator premium. Never investor-facing." label="BANXUM premium share bps" onChange={setFeeBps} required value={feeBps} />
        <TextInput label="Settlement account name" onChange={setAccountName} required value={accountName} />
        <TextInput label="Settlement IBAN" onChange={setIban} required value={iban} />
        <TextInput label="Settlement BIC" onChange={setBic} value={bic} />
        <TextInput label="KYB evidence reference" onChange={setKybEvidence} required value={kybEvidence} />
      </FieldGrid>
      <TextAreaInput label="Registered address" onChange={setRegisteredAddress} required value={registeredAddress} />
      <TextAreaInput label="Contact information" onChange={setContactInfo} value={contactInfo} />
      <TextAreaInput hint="Internal only." label="KYB / AML observations" onChange={setKybNotes} value={kybNotes} />
      <TextAreaInput hint="Internal only." label="Risk observations" onChange={setRiskNotes} value={riskNotes} />
      <ActionFooter mutation={mutation} previewMessage={preview} submitLabel={originator ? "Save Loan Originator" : "Create Loan Originator"} />
    </form>
  );
}

function OriginatorLoanCreateForm({
  originators,
  onCreated,
  loanId,
  detail
}: {
  originators: LoanOriginator[];
  onCreated?: () => void;
  loanId?: string;
  detail?: OriginatorAdminLoanDetailResponse;
}) {
  const activeOriginators = originators.filter((originator) => originator.status === "active");
  const snapshot = recordValue(detail?.borrower_snapshot);
  const [originatorId, setOriginatorId] = useState(detail?.originator_id ?? activeOriginators[0]?.id ?? "");
  const [title, setTitle] = useState(detail?.title ?? "");
  const [summary, setSummary] = useState(detail?.investor_summary ?? "");
  const [purpose, setPurpose] = useState<OriginatorLoanCreate["purpose"]>((detail?.purpose as OriginatorLoanCreate["purpose"] | undefined) ?? PurposeEnum.working_capital);
  const [purposeDescription, setPurposeDescription] = useState(detail?.purpose_description ?? "");
  const [currency, setCurrency] = useState(detail?.currency ?? "CHF");
  const [originalPrincipal, setOriginalPrincipal] = useState(detail ? String(detail.original_principal_minor) : "");
  const [couponBps, setCouponBps] = useState(detail ? String(detail.interest_rate_bps) : "");
  const [yieldBps, setYieldBps] = useState(detail ? String(detail.target_yield_bps) : "");
  const [minimumInvestment, setMinimumInvestment] = useState(detail ? String(detail.minimum_investment_minor) : "100000");
  const [repaymentType, setRepaymentType] = useState<OriginatorLoanCreate["repayment_type"]>((detail?.repayment_type as OriginatorLoanCreate["repayment_type"] | undefined) ?? RepaymentTypeEnum.equal_installments);
  const [interestOnlyMonths, setInterestOnlyMonths] = useState(detail ? String(detail.interest_only_months) : "0");
  const [collateralType, setCollateralType] = useState<OriginatorLoanCreate["collateral_type"]>((detail?.collateral_type as OriginatorLoanCreate["collateral_type"] | undefined) ?? CollateralTypeEnum.real_estate);
  const [collateralValue, setCollateralValue] = useState(detail ? String(detail.collateral_value_minor) : "0");
  const [collateralDescription, setCollateralDescription] = useState(detail?.collateral_description ?? "");
  const [riskRating, setRiskRating] = useState<OriginatorLoanCreate["risk_rating"]>((detail?.risk_rating as OriginatorLoanCreate["risk_rating"] | undefined) ?? RiskRatingEnum.B);
  const [asOfDate, setAsOfDate] = useState(detail?.import_as_of_date ?? today);
  const [csvContent, setCsvContent] = useState("");
  const [sourceFilename, setSourceFilename] = useState("");
  const [premiumFeeBps, setPremiumFeeBps] = useState(detail ? String(detail.premium_fee_bps) : "");
  const [skinBps, setSkinBps] = useState(detail ? String(detail.skin_in_the_game_bps ?? 0) : "0");
  const [borrowerLegalName, setBorrowerLegalName] = useState(String(snapshot.borrower_legal_name ?? ""));
  const [borrowerDisplayName, setBorrowerDisplayName] = useState(String(snapshot.borrower_display_name ?? "Anonymized borrower"));
  const [borrowerYearFounded, setBorrowerYearFounded] = useState(snapshot.year_founded == null ? "" : String(snapshot.year_founded));
  const [borrowerEntityType, setBorrowerEntityType] = useState(String(snapshot.entity_type ?? "company"));
  const [borrowerCountry, setBorrowerCountry] = useState(String(snapshot.country ?? "CH"));
  const [borrowerRegistration, setBorrowerRegistration] = useState(String(snapshot.registration_number ?? ""));
  const [businessClassification, setBusinessClassification] = useState(String(snapshot.business_classification ?? ""));
  const [businessClassificationPublic, setBusinessClassificationPublic] = useState(Boolean(snapshot.business_classification_public));
  const [registeredAddress, setRegisteredAddress] = useState(String(snapshot.registered_address ?? ""));
  const [registeredAddressPublic, setRegisteredAddressPublic] = useState(Boolean(snapshot.registered_address_public));
  const [operatingAddress, setOperatingAddress] = useState(String(snapshot.operating_address ?? ""));
  const [borrowerContact, setBorrowerContact] = useState(String(snapshot.contact_info ?? ""));
  const [borrowerContactPublic, setBorrowerContactPublic] = useState(Boolean(snapshot.contact_info_public));
  const [industryActivity, setIndustryActivity] = useState(String(snapshot.industry_activity ?? ""));
  const [ownershipStructure, setOwnershipStructure] = useState(String(snapshot.ownership_structure ?? ""));
  const [beneficialOwners, setBeneficialOwners] = useState(JSON.stringify(snapshot.beneficial_owners ?? [], null, 2));
  const [directorsOfficers, setDirectorsOfficers] = useState(JSON.stringify(snapshot.directors_officers ?? [], null, 2));
  const [authorizedSignatories, setAuthorizedSignatories] = useState(JSON.stringify(snapshot.authorized_signatories ?? [], null, 2));
  const [bankAccountDetails, setBankAccountDetails] = useState(JSON.stringify(snapshot.bank_account_details ?? {}, null, 2));
  const [kybAmlObservations, setKybAmlObservations] = useState(String(snapshot.kyb_aml_observations ?? ""));
  const [financialRisk, setFinancialRisk] = useState(String(snapshot.financial_risk ?? ""));
  const [financialsCurrency, setFinancialsCurrency] = useState(String(snapshot.financials_currency ?? currency));
  const [assetsMinor, setAssetsMinor] = useState(snapshot.assets_minor == null ? "" : String(snapshot.assets_minor));
  const [liabilitiesMinor, setLiabilitiesMinor] = useState(snapshot.liabilities_minor == null ? "" : String(snapshot.liabilities_minor));
  const [revenueMinor, setRevenueMinor] = useState(snapshot.revenue_last_year_minor == null ? "" : String(snapshot.revenue_last_year_minor));
  const [profitMinor, setProfitMinor] = useState(snapshot.profit_last_year_minor == null ? "" : String(snapshot.profit_last_year_minor));
  const [localError, setLocalError] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const createMutation = useOriginatorClaimsAdminLoansCreate({ mutation: { onSuccess: onCreated } });
  const updateMutation = useOriginatorClaimsAdminLoansUpdate({ mutation: { onSuccess: onCreated } });
  const mutation = loanId ? updateMutation : createMutation;

  async function chooseCsv(file: File | undefined) {
    setSourceFilename(file?.name ?? "");
    setCsvContent(await readTextFile(file));
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setLocalError("");
    try {
      if (!csvContent || !sourceFilename) throw new Error("Select the complete schedule and historical-payments CSV.");
      const normalizedSkinBps = skinBps.trim();
      if (!/^\d+$/.test(normalizedSkinBps)) {
        throw new Error("Skin in the game must be a whole number of basis points.");
      }
      const parsedSkinBps = Number(normalizedSkinBps);
      if (!Number.isSafeInteger(parsedSkinBps) || parsedSkinBps < 0 || parsedSkinBps > 9_999) {
        throw new Error("Skin in the game must be between 0 and 9,999 basis points.");
      }
      const data: OriginatorLoanCreate = {
        originator_id: originatorId,
        title,
        investor_summary: summary,
        purpose,
        purpose_description: purposeDescription,
        currency,
        original_principal_minor: intValue(originalPrincipal),
        interest_rate_bps: intValue(couponBps),
        target_yield_bps: intValue(yieldBps),
        minimum_investment_minor: intValue(minimumInvestment),
        repayment_type: repaymentType,
        interest_only_months: intValue(interestOnlyMonths),
        collateral_type: collateralType,
        collateral_value_minor: intValue(collateralValue),
        collateral_description: collateralDescription,
        risk_rating: riskRating,
        csv_content: csvContent,
        source_filename: sourceFilename,
        as_of_date: asOfDate,
        borrower_snapshot: {
          borrower_legal_name: borrowerLegalName,
          borrower_display_name: borrowerDisplayName,
          year_founded: optionalMinorValue(borrowerYearFounded),
          entity_type: borrowerEntityType,
          country: borrowerCountry,
          registration_number: borrowerRegistration,
          business_classification: businessClassification,
          business_classification_public: businessClassificationPublic,
          registered_address: registeredAddress,
          registered_address_public: registeredAddressPublic,
          operating_address: operatingAddress,
          contact_info: borrowerContact,
          contact_info_public: borrowerContactPublic,
          industry_activity: industryActivity,
          ownership_structure: ownershipStructure,
          beneficial_owners: parseJsonArray(beneficialOwners, "Beneficial owners"),
          directors_officers: parseJsonArray(directorsOfficers, "Directors and officers"),
          authorized_signatories: parseJsonArray(authorizedSignatories, "Authorized signatories"),
          bank_account_details: parseJsonObject(bankAccountDetails || "{}", "Bank account details"),
          kyb_aml_observations: kybAmlObservations,
          financial_risk: financialRisk,
          financials_currency: financialsCurrency.trim().toUpperCase(),
          assets_minor: optionalMinorValue(assetsMinor),
          liabilities_minor: optionalMinorValue(liabilitiesMinor),
          revenue_last_year_minor: optionalMinorValue(revenueMinor),
          profit_last_year_minor: optionalMinorValue(profitMinor)
        },
        premium_fee_bps: premiumFeeBps ? intValue(premiumFeeBps) : null,
        skin_in_the_game_bps: parsedSkinBps
      };
      if (isFixturePreview) {
        setPreview(`${title || "Originator claim loan"} would be ${loanId ? "replaced with a new immutable draft revision" : "imported as a draft"} after strict schedule/payment validation.`);
        return;
      }
      if (loanId) {
        updateMutation.mutate({ loanId, data: data as PatchedOriginatorLoanCreate });
      } else {
        createMutation.mutate({ data });
      }
    } catch (error) {
      setLocalError(errorMessage(error));
    }
  }

  return (
    <form className="admin-action-form" onSubmit={submit}>
      <Banner tone="warn" title="Full schedule replacement evidence">
        Upload the complete contractual schedule and all historical payments through the as-of date. The server validates principal conservation, dates, payment types, prepayments, maturity, and consistency with the selected repayment type. {loanId ? "Saving creates a new immutable import revision; the prior draft evidence remains retained." : "Examples are maintained in imports_examples/."}
      </Banner>
      {!activeOriginators.length ? <Banner tone="bad" title="No active Loan Originator">Activate an originator after offline KYB before creating or replacing a claim loan.</Banner> : null}
      <FieldGrid>
        <SelectInput
          label="Loan Originator"
          onChange={setOriginatorId}
          optionLabel={(id) => {
            const originator = originators.find((item) => item.id === id);
            return originator ? `${originator.public_name} (${originator.registration_number})` : id;
          }}
          options={activeOriginators.map((originator) => originator.id)}
          value={originatorId}
        />
        <TextInput label="Title" onChange={setTitle} required value={title} />
        <SelectInput label="Purpose" onChange={setPurpose} options={Object.values(PurposeEnum)} value={purpose} />
        <SelectInput label="Currency" onChange={setCurrency} options={["CHF", "EUR"]} value={currency} />
        <MoneyMinorInput currency={currency} label="Original final-borrower principal minor units" onChange={setOriginalPrincipal} required value={originalPrincipal} />
        <TextInput label="Underlying borrower coupon bps" onChange={setCouponBps} required value={couponBps} />
        <TextInput hint="Effective annual ACT/365. This remains constant while the executable cash price changes." label="Target investor yield bps" onChange={setYieldBps} required value={yieldBps} />
        <MoneyMinorInput currency={currency} label="Minimum investment minor units" onChange={setMinimumInvestment} required value={minimumInvestment} />
        <SelectInput label="Repayment type" onChange={setRepaymentType} options={Object.values(RepaymentTypeEnum)} value={repaymentType} />
        <TextInput label="Interest-only months" onChange={setInterestOnlyMonths} value={interestOnlyMonths} />
        <SelectInput label="Collateral type" onChange={setCollateralType} options={Object.values(CollateralTypeEnum)} value={collateralType} />
        <MoneyMinorInput currency={currency} label="Collateral value minor units" onChange={setCollateralValue} required value={collateralValue} />
        <SelectInput label="Risk rating" onChange={setRiskRating} options={Object.values(RiskRatingEnum)} value={riskRating} />
        <TextInput label="Import as-of date" onChange={setAsOfDate} required type="date" value={asOfDate} />
        <TextInput hint="Optional loan-specific override; blank inherits the originator default." label="BANXUM premium share bps" onChange={setPremiumFeeBps} value={premiumFeeBps} />
        <TextInput hint="Optional. Enter 0 to disable it, or 1-9,999 basis points. The required retained amount is rounded up to the nearest minor unit and cannot be sold." label="Skin in the game bps" onChange={setSkinBps} required type="number" value={skinBps} />
        <Field label="Schedule and payment CSV"><input accept=".csv,text/csv" onChange={(event) => void chooseCsv(event.target.files?.[0])} required type="file" /></Field>
      </FieldGrid>
      <TextAreaInput label="Investor summary" onChange={setSummary} required value={summary} />
      <TextAreaInput label="Purpose description" onChange={setPurposeDescription} value={purposeDescription} />
      <TextAreaInput label="Collateral description" onChange={setCollateralDescription} value={collateralDescription} />
      <h3>Final borrower snapshot</h3>
      <Banner tone="neutral" title="Private identity, controlled disclosure">The legal borrower identity, ownership, bank, KYB and risk fields remain internal. Investors receive the anonymized display name and only fields explicitly marked public.</Banner>
      <FieldGrid>
        <TextInput label="Legal business name (internal)" onChange={setBorrowerLegalName} required value={borrowerLegalName} />
        <TextInput label="Anonymized borrower name (public)" onChange={setBorrowerDisplayName} required value={borrowerDisplayName} />
        <TextInput label="Year founded" onChange={setBorrowerYearFounded} value={borrowerYearFounded} />
        <TextInput label="Entity type" onChange={setBorrowerEntityType} value={borrowerEntityType} />
        <TextInput label="Country" onChange={setBorrowerCountry} value={borrowerCountry} />
        <TextInput label="Registration number (internal)" onChange={setBorrowerRegistration} value={borrowerRegistration} />
        <TextInput label="Business classification" onChange={setBusinessClassification} value={businessClassification} />
        <TextInput label="Industry / activity" onChange={setIndustryActivity} value={industryActivity} />
        <TextInput label="Financials currency" onChange={setFinancialsCurrency} value={financialsCurrency} />
        <MoneyMinorInput currency={financialsCurrency || currency} label="Assets minor units" onChange={setAssetsMinor} value={assetsMinor} />
        <MoneyMinorInput currency={financialsCurrency || currency} label="Liabilities minor units" onChange={setLiabilitiesMinor} value={liabilitiesMinor} />
        <MoneyMinorInput currency={financialsCurrency || currency} label="Revenue last year minor units" onChange={setRevenueMinor} value={revenueMinor} />
        <MoneyMinorInput currency={financialsCurrency || currency} label="Profit last year minor units" onChange={setProfitMinor} value={profitMinor} />
      </FieldGrid>
      <label className="check-row"><input checked={businessClassificationPublic} onChange={(event) => setBusinessClassificationPublic(event.target.checked)} type="checkbox" />Show business classification to investors.</label>
      <TextAreaInput label="Registered address" onChange={setRegisteredAddress} value={registeredAddress} />
      <label className="check-row"><input checked={registeredAddressPublic} onChange={(event) => setRegisteredAddressPublic(event.target.checked)} type="checkbox" />Show registered address to investors.</label>
      <TextAreaInput label="Operating address (internal)" onChange={setOperatingAddress} value={operatingAddress} />
      <TextAreaInput label="Contact information" onChange={setBorrowerContact} value={borrowerContact} />
      <label className="check-row"><input checked={borrowerContactPublic} onChange={(event) => setBorrowerContactPublic(event.target.checked)} type="checkbox" />Show contact information to investors.</label>
      <TextAreaInput hint="Internal only." label="Ownership structure" onChange={setOwnershipStructure} value={ownershipStructure} />
      <FieldGrid>
        <TextAreaInput hint="JSON list; internal only." label="Beneficial owners" onChange={setBeneficialOwners} value={beneficialOwners} />
        <TextAreaInput hint="JSON list; internal only." label="Directors and officers" onChange={setDirectorsOfficers} value={directorsOfficers} />
        <TextAreaInput hint="JSON list; internal only." label="Authorized signatories" onChange={setAuthorizedSignatories} value={authorizedSignatories} />
        <TextAreaInput hint="JSON object; internal only." label="Bank account details" onChange={setBankAccountDetails} value={bankAccountDetails} />
      </FieldGrid>
      <TextAreaInput hint="Internal only." label="KYB / AML observations" onChange={setKybAmlObservations} value={kybAmlObservations} />
      <TextAreaInput hint="Internal only." label="Financial risk" onChange={setFinancialRisk} value={financialRisk} />
      {sourceFilename ? <Banner tone="info" title="CSV selected">{sourceFilename} · {csvContent.length.toLocaleString()} characters</Banner> : null}
      {localError ? <Banner tone="bad" title="Import not ready">{localError}</Banner> : null}
      <ActionFooter mutation={mutation} previewMessage={preview} submitLabel={loanId ? "Validate and replace draft" : "Validate and create draft"} />
    </form>
  );
}

function OriginatorLoanEvidenceReview({ detail }: { detail: OriginatorAdminLoanDetailResponse }) {
  const scheduleTotals = detail.schedule.reduce(
    (totals, row) => ({
      principal: totals.principal + row.principal_minor,
      interest: totals.interest + row.interest_minor,
      penalty: totals.penalty + row.penalty_minor,
      fee: totals.fee + row.fee_minor,
      total: totals.total + row.total_minor
    }),
    { principal: 0, interest: 0, penalty: 0, fee: 0, total: 0 }
  );
  return (
    <div className="admin-stack">
      <div className="admin-context-bar">
        <span>Import revision {detail.schedule_revision}</span>
        <span>{detail.source_filename}</span>
        <span>As of {formatDate(detail.import_as_of_date)}</span>
        <span className="mono">SHA-256 {detail.source_sha256.slice(0, 12)}...</span>
      </div>
      <div>
        <h3>Imported contractual schedule</h3>
        <div className="table-wrap admin-table-wrap">
          <table className="admin-table admin-schedule-table">
            <thead><tr><th>#</th><th>Accrual start</th><th>Due</th><th>Opening</th><th>Principal</th><th>Interest</th><th>Penalty</th><th>Legal / recovery costs</th><th>Total</th><th>Closing</th></tr></thead>
            <tbody>
              {detail.schedule.map((row) => (
                <tr key={row.installment_number}><td>{row.installment_number}</td><td>{formatDate(row.accrual_start_date)}</td><td>{formatDate(row.due_date)}</td><td><Money amountMinor={row.opening_principal_minor} currency={detail.currency} /></td><td><Money amountMinor={row.principal_minor} currency={detail.currency} /></td><td><Money amountMinor={row.interest_minor} currency={detail.currency} /></td><td><Money amountMinor={row.penalty_minor} currency={detail.currency} /></td><td><Money amountMinor={row.fee_minor} currency={detail.currency} /></td><td><Money amountMinor={row.total_minor} currency={detail.currency} /></td><td><Money amountMinor={row.closing_principal_minor} currency={detail.currency} /></td></tr>
              ))}
              <tr className="admin-schedule-total-row"><td colSpan={4}><strong>Totals</strong></td><td><strong><Money amountMinor={scheduleTotals.principal} currency={detail.currency} /></strong></td><td><strong><Money amountMinor={scheduleTotals.interest} currency={detail.currency} /></strong></td><td><strong><Money amountMinor={scheduleTotals.penalty} currency={detail.currency} /></strong></td><td><strong><Money amountMinor={scheduleTotals.fee} currency={detail.currency} /></strong></td><td><strong><Money amountMinor={scheduleTotals.total} currency={detail.currency} /></strong></td><td>-</td></tr>
            </tbody>
          </table>
        </div>
      </div>
      <div>
        <h3>Historical payments</h3>
        {detail.payment_history.length ? (
          <div className="table-wrap admin-table-wrap">
            <table className="admin-table"><thead><tr><th>Reference</th><th>Value date</th><th>Type</th><th>Principal</th><th>Interest</th><th>Penalty</th><th>Legal / recovery costs</th><th>Total</th><th>Principal after</th></tr></thead><tbody>{detail.payment_history.map((row) => <tr key={row.reference}><td className="mono">{row.reference}</td><td>{formatDate(row.value_date)}</td><td>{labelize(row.payment_type)}</td><td><Money amountMinor={row.principal_minor} currency={detail.currency} /></td><td><Money amountMinor={row.interest_minor} currency={detail.currency} /></td><td><Money amountMinor={row.penalty_minor} currency={detail.currency} /></td><td><Money amountMinor={row.fee_minor} currency={detail.currency} /></td><td><Money amountMinor={row.total_minor} currency={detail.currency} /></td><td><Money amountMinor={row.resulting_principal_minor} currency={detail.currency} /></td></tr>)}</tbody></table>
          </div>
        ) : <Empty icon="docs" title="No historical payments">The imported loan had no borrower payments before this revision's as-of date.</Empty>}
      </div>
    </div>
  );
}

function OriginatorLoanManageModal({
  loan,
  originators,
  onChanged,
  onClose
}: {
  loan: Loan;
  originators: LoanOriginator[];
  onChanged: () => void;
  onClose: () => void;
}) {
  const [action, setAction] = useState<"menu" | "edit" | "publish" | "hold" | "repayment">("menu");
  const [asOfDate, setAsOfDate] = useState(today);
  const [holdReason, setHoldReason] = useState("");
  const [csvContent, setCsvContent] = useState("");
  const [sourceFilename, setSourceFilename] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const [bookingDate, setBookingDate] = useState(today);
  const [valueDate, setValueDate] = useState(today);
  const [collectionAccount, setCollectionAccount] = useState(defaultCollectionAccount);
  const [payerName, setPayerName] = useState("");
  const [payerAccount, setPayerAccount] = useState("");
  const [bankReference, setBankReference] = useState("");
  const [bankPaymentReference, setBankPaymentReference] = useState("");
  const [evidenceReference, setEvidenceReference] = useState("");
  const [notes, setNotes] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const detailQuery = useOriginatorClaimsAdminLoansRetrieve(loan.id, {
    query: { enabled: !isFixturePreview, retry: false }
  });
  const detail = detailQuery.data;
  const publishMutation = useOriginatorClaimsAdminLoansPublish({ mutation: { onSuccess: () => { onChanged(); onClose(); } } });
  const holdMutation = useOriginatorClaimsAdminLoansHold({ mutation: { onSuccess: () => { onChanged(); onClose(); } } });
  const repaymentMutation = useOriginatorClaimsAdminLoanRepaymentsCreate({ mutation: { onSuccess: () => { onChanged(); onClose(); } } });

  async function chooseCsv(file: File | undefined) {
    setSourceFilename(file?.name ?? "");
    setCsvContent(await readTextFile(file));
  }

  function publish() {
    if (isFixturePreview) { setPreview("The reviewed originator claim would open in the primary market."); return; }
    publishMutation.mutate({ loanId: loan.id, data: { as_of_date: asOfDate } });
  }

  function hold() {
    if (isFixturePreview) { setPreview("The opportunity would close immediately and existing investor claims would remain serviced."); return; }
    holdMutation.mutate({ loanId: loan.id, data: { reason: holdReason } });
  }

  function repayment() {
    const data: OriginatorBorrowerRepaymentRequest = {
      csv_content: csvContent,
      source_filename: sourceFilename,
      as_of_date: asOfDate,
      payment_reference: paymentReference,
      booking_date: bookingDate,
      value_date: valueDate,
      collection_account_identifier: collectionAccount,
      payer_name: payerName,
      payer_account_identifier: payerAccount,
      bank_reference: bankReference,
      bank_payment_reference: bankPaymentReference,
      evidence_reference: evidenceReference,
      notes,
      idempotency_key: idempotencyKey("originator-borrower-repayment")
    };
    if (isFixturePreview) { setPreview("The full revised schedule/payment CSV would be validated, distributed by dated entitlement, and stored as a new immutable revision."); return; }
    repaymentMutation.mutate({ loanId: loan.id, data });
  }

  const mutationError = publishMutation.error || holdMutation.error || repaymentMutation.error;
  return (
    <Modal title={`Manage originator claim - ${loan.title}`} onClose={onClose} wide>
      <div className="admin-context-bar"><Chip tone="info">Originator claim</Chip><span>{loan.originator_name}</span><Chip tone={statusTone(loan.opportunity_status ?? loan.status)}>{labelize(loan.opportunity_status ?? loan.status)}</Chip><span>Outstanding <Money amountMinor={loan.current_outstanding_principal_minor} currency={loan.currency} /></span><span>Originator owned <Money amountMinor={detail?.unsold_principal_minor ?? loan.unsold_principal_minor ?? 0} currency={loan.currency} /></span>{detail ? <><span>Required retained <Money amountMinor={detail.retained_principal_minor} currency={loan.currency} /></span><span>Available to sell <Money amountMinor={detail.sellable_principal_minor} currency={loan.currency} /></span></> : null}<span>Yield {formatRateBps(loan.yield_bps)}</span></div>
      {action !== "menu" ? <Button onClick={() => setAction("menu")} size="sm">All actions</Button> : null}
      {action === "menu" ? (
        <div className="admin-action-choice-grid">
          {loan.opportunity_status === "draft" ? <button disabled={!detail} onClick={() => setAction("edit")} type="button"><strong>Edit draft and replace import</strong><span>Correct loan, private borrower, yield, collateral, or CSV data by creating a new immutable draft revision.</span></button> : null}
          {loan.opportunity_status === "draft" ? <button onClick={() => setAction("publish")} type="button"><strong>Publish opportunity</strong><span>Revalidate maturity, performance, active originator, schedule evidence and the 30-day close boundary.</span></button> : null}
          {loan.opportunity_status === "open" ? <button onClick={() => setAction("hold")} type="button"><strong>Place opportunity on hold</strong><span>Close new sales immediately while continuing to service claims already sold.</span></button> : null}
          {["active", "late", "defaulted"].includes(loan.status) ? <button onClick={() => setAction("repayment")} type="button"><strong>Record borrower repayment / schedule revision</strong><span>Upload the complete revised schedule and payment history. Distribute the banked cash using dated claim ownership.</span></button> : null}
        </div>
      ) : null}
      {action === "edit" && detail ? <OriginatorLoanCreateForm detail={detail} loanId={loan.id} originators={originators} onCreated={() => { void detailQuery.refetch(); onChanged(); setAction("menu"); }} /> : null}
      {action === "publish" ? <div className="admin-form-panel"><TextInput label="Review as-of date" onChange={setAsOfDate} required type="date" value={asOfDate} /><OperationConfirmButton confirmLabel="Publish originator claim" description="Publishing opens immediate claim purchases at the configured target yield. The executable price remains dynamic." details={[{ label: "Loan", value: loan.title }, { label: "Originator", value: loan.originator_name ?? "-" }, { label: "Yield", value: formatRateBps(loan.yield_bps) }, { label: "Maturity", value: formatDate(loan.maturity_date) }]} onConfirm={publish} title="Publish originator claim opportunity" variant="primary">Review and publish</OperationConfirmButton></div> : null}
      {action === "hold" ? <div className="admin-form-panel"><TextAreaInput label="Hold reason" onChange={setHoldReason} required value={holdReason} /><OperationConfirmButton confirmLabel="Close opportunity" description="No further primary-market claim sales will be allowed. Existing investors continue to be serviced." details={[{ label: "Loan", value: loan.title }, { label: "Unsold principal", value: <Money amountMinor={loan.unsold_principal_minor ?? 0} currency={loan.currency} /> }, { label: "Reason", value: holdReason || "Required" }]} disabled={!holdReason.trim()} onConfirm={hold} title="Place originator claim on hold" variant="danger">Review and close</OperationConfirmButton></div> : null}
      {action === "repayment" ? (
        <div className="admin-form-panel">
          <Banner tone="warn" title="Bank cash and full replacement evidence required">The payment amount and components come from the imported payment row. The new CSV must contain the complete current schedule plus complete historical payments, including this unique reference.</Banner>
          <FieldGrid><TextInput label="Import as-of date" onChange={setAsOfDate} required type="date" value={asOfDate} /><TextInput label="Unique payment reference" onChange={setPaymentReference} required value={paymentReference} /><TextInput label="Booking date" onChange={setBookingDate} required type="date" value={bookingDate} /><TextInput label="Value date" onChange={setValueDate} required type="date" value={valueDate} /><TextInput label="Collection account" onChange={setCollectionAccount} required value={collectionAccount} /><TextInput label="Payer name" onChange={setPayerName} required value={payerName} /><TextInput label="Payer account" onChange={setPayerAccount} value={payerAccount} /><TextInput label="Bank reference" onChange={setBankReference} value={bankReference} /><TextInput label="Bank payment reference" onChange={setBankPaymentReference} value={bankPaymentReference} /><TextInput label="Evidence reference" onChange={setEvidenceReference} value={evidenceReference} /><Field label="Revised full CSV"><input accept=".csv,text/csv" onChange={(event) => void chooseCsv(event.target.files?.[0])} required type="file" /></Field></FieldGrid>
          <TextAreaInput label="Admin notes" onChange={setNotes} value={notes} />
          <OperationConfirmButton confirmLabel="Record repayment" description="This posts borrower cash, distributes investor entitlements, accrues the unsold Loan Originator share, reduces holdings, reprices open secondary listings, and replaces the current schedule revision atomically." details={[{ label: "Loan", value: loan.title }, { label: "Payment reference", value: paymentReference || "Required" }, { label: "CSV", value: sourceFilename || "Required" }, { label: "Value date", value: valueDate }]} disabled={!csvContent || !paymentReference || !payerName || repaymentMutation.isPending} onConfirm={repayment} title="Record originator-loan borrower repayment" variant="primary">Review repayment</OperationConfirmButton>
        </div>
      ) : null}
      {mutationError ? <Banner tone="bad" title="Originator claim action failed">{errorMessage(mutationError)}</Banner> : null}
      {detailQuery.error ? <Banner tone="bad" title="Could not load imported loan evidence">{errorMessage(detailQuery.error)}</Banner> : null}
      {preview ? <Banner tone="info" title="Preview action">{preview}</Banner> : null}
      {action === "menu" && detail ? <OriginatorLoanEvidenceReview detail={detail} /> : null}
    </Modal>
  );
}

function BorrowerCreateForm({ onCreated }: { onCreated?: () => void }) {
  const [legalName, setLegalName] = useState(adminFormDefaults.borrowerLegalName);
  const [yearFounded, setYearFounded] = useState("2016");
  const [entityType, setEntityType] = useState<BorrowerEntityType>(BorrowerEntityTypeEnum.swiss_company);
  const [kybStatus, setKybStatus] = useState<BorrowerKybStatus>(BorrowerKybStatusEnum.pending);
  const [country, setCountry] = useState("CH");
  const [registrationNumber, setRegistrationNumber] = useState("");
  const [businessClassification, setBusinessClassification] = useState("");
  const [businessClassificationPublic, setBusinessClassificationPublic] = useState(false);
  const [registeredAddress, setRegisteredAddress] = useState("");
  const [registeredAddressPublic, setRegisteredAddressPublic] = useState(false);
  const [contactInfo, setContactInfo] = useState("");
  const [contactInfoPublic, setContactInfoPublic] = useState(false);
  const [ownershipStructure, setOwnershipStructure] = useState("");
  const [bankAccounts, setBankAccounts] = useState("");
  const [kybAmlObservations, setKybAmlObservations] = useState("");
  const [financialRisk, setFinancialRisk] = useState("");
  const [financialsCurrency, setFinancialsCurrency] = useState("CHF");
  const [assets, setAssets] = useState("");
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1EntitiesAdminBorrowersCreate({
    mutation: {
      onSuccess: () => {
        setSuccess("Borrower entity was created.");
        onCreated?.();
      }
    }
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: BorrowerEntityCreateRequest = {
      legal_name: legalName,
      year_founded: intValue(yearFounded, 2000),
      entity_type: entityType,
      kyb_status: kybStatus,
      country,
      registration_number: registrationNumber,
      business_classification: businessClassification,
      business_classification_public: businessClassificationPublic,
      registered_address: registeredAddress,
      registered_address_public: registeredAddressPublic,
      contact_info: contactInfo,
      contact_info_public: contactInfoPublic,
      ownership_structure: ownershipStructure,
      bank_account_details: bankAccountDetailsPayload(bankAccounts),
      kyb_aml_observations: kybAmlObservations,
      financial_risk: financialRisk,
      financials_currency: financialsCurrency,
      assets_minor: assets ? intValue(assets) : null,
      note
    };
    if (isFixturePreview) {
      setPreview(`${legalName} borrower record would be created.`);
      return;
    }
    mutation.mutate({ data });
  }

  return (
    <div className="admin-form-panel">
      <h2>Create borrower</h2>
      <form className="admin-action-form" onSubmit={submit}>
        <FieldGrid>
          <TextInput label="Legal name" onChange={setLegalName} required value={legalName} />
          <TextInput label="Year founded" onChange={setYearFounded} required value={yearFounded} />
          <SelectInput label="Entity type" onChange={setEntityType} options={Object.values(BorrowerEntityTypeEnum)} value={entityType} />
          <SelectInput label="KYB status" onChange={setKybStatus} options={Object.values(BorrowerKybStatusEnum)} value={kybStatus} />
          <TextInput label="Country" onChange={setCountry} value={country} />
          <TextInput label="Registration number" onChange={setRegistrationNumber} value={registrationNumber} />
          <TextInput label="Business classification" onChange={setBusinessClassification} value={businessClassification} />
          <TextInput label="Financials currency" onChange={setFinancialsCurrency} value={financialsCurrency} />
          <MoneyMinorInput currency={financialsCurrency} label="Assets minor units" onChange={setAssets} value={assets} />
        </FieldGrid>
        <label className="check-row">
          <input checked={businessClassificationPublic} onChange={(event) => setBusinessClassificationPublic(event.target.checked)} type="checkbox" />
          Show business classification to lenders.
        </label>
        <TextAreaInput label="Registered address" onChange={setRegisteredAddress} value={registeredAddress} />
        <label className="check-row">
          <input checked={registeredAddressPublic} onChange={(event) => setRegisteredAddressPublic(event.target.checked)} type="checkbox" />
          Show registered address to lenders.
        </label>
        <TextAreaInput label="Contact info" onChange={setContactInfo} value={contactInfo} />
        <label className="check-row">
          <input checked={contactInfoPublic} onChange={(event) => setContactInfoPublic(event.target.checked)} type="checkbox" />
          Show contact info to lenders.
        </label>
        <TextAreaInput hint="Internal only." label="Ownership" onChange={setOwnershipStructure} value={ownershipStructure} />
        <TextAreaInput hint="Internal only. Plain notes are stored under bank_account_details.notes; JSON objects are accepted for structured details." label="Bank accounts" onChange={setBankAccounts} value={bankAccounts} />
        <TextAreaInput hint="Internal only." label="KYB/AML observations" onChange={setKybAmlObservations} value={kybAmlObservations} />
        <TextAreaInput hint="Internal only." label="Financial risk" onChange={setFinancialRisk} value={financialRisk} />
        <TextAreaInput label="Admin note" onChange={setNote} value={note} />
        <ActionFooter mutation={mutation} previewMessage={preview} successMessage={success} submitLabel="Create borrower" />
      </form>
    </div>
  );
}

function BorrowerEditForm({ borrower, onSaved }: { borrower: BorrowerEntity; onSaved?: () => void }) {
  const [legalName, setLegalName] = useState(borrower.legal_name);
  const [yearFounded, setYearFounded] = useState(String(borrower.year_founded));
  const [entityType, setEntityType] = useState<BorrowerEntityType>(borrower.entity_type as BorrowerEntityType);
  const [kybStatus, setKybStatus] = useState<BorrowerKybStatus>(borrower.kyb_status as BorrowerKybStatus);
  const [complianceHold, setComplianceHold] = useState(borrower.compliance_hold);
  const [country, setCountry] = useState(borrower.country || "CH");
  const [registrationNumber, setRegistrationNumber] = useState(borrower.registration_number || "");
  const [businessClassification, setBusinessClassification] = useState(borrower.business_classification || "");
  const [businessClassificationPublic, setBusinessClassificationPublic] = useState(borrower.business_classification_public);
  const [registeredAddress, setRegisteredAddress] = useState(borrower.registered_address || "");
  const [registeredAddressPublic, setRegisteredAddressPublic] = useState(borrower.registered_address_public);
  const [contactInfo, setContactInfo] = useState(borrower.contact_info || "");
  const [contactInfoPublic, setContactInfoPublic] = useState(borrower.contact_info_public);
  const [ownershipStructure, setOwnershipStructure] = useState(borrower.ownership_structure || "");
  const [bankAccounts, setBankAccounts] = useState(bankAccountDetailsText(borrower.bank_account_details));
  const [kybAmlObservations, setKybAmlObservations] = useState(borrower.kyb_aml_observations || "");
  const [financialRisk, setFinancialRisk] = useState(borrower.financial_risk || "");
  const [financialsCurrency, setFinancialsCurrency] = useState(borrower.financials_currency || "CHF");
  const [assets, setAssets] = useState(borrower.assets_minor === null ? "" : String(borrower.assets_minor));
  const [liabilities, setLiabilities] = useState(borrower.liabilities_minor === null ? "" : String(borrower.liabilities_minor));
  const [revenue, setRevenue] = useState(borrower.revenue_last_year_minor === null ? "" : String(borrower.revenue_last_year_minor));
  const [profit, setProfit] = useState(borrower.profit_last_year_minor === null ? "" : String(borrower.profit_last_year_minor));
  const [note, setNote] = useState("");
  const [evidenceSummary, setEvidenceSummary] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1EntitiesAdminBorrowersPartialUpdate({
    mutation: {
      onSuccess: () => {
        setSuccess("Borrower entity was updated.");
        onSaved?.();
      }
    }
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: PatchedBorrowerEntityUpdateRequest = {
      legal_name: legalName,
      year_founded: intValue(yearFounded, borrower.year_founded),
      entity_type: entityType,
      kyb_status: kybStatus,
      compliance_hold: complianceHold,
      country,
      registration_number: registrationNumber,
      business_classification: businessClassification,
      business_classification_public: businessClassificationPublic,
      registered_address: registeredAddress,
      registered_address_public: registeredAddressPublic,
      contact_info: contactInfo,
      contact_info_public: contactInfoPublic,
      ownership_structure: ownershipStructure,
      bank_account_details: bankAccountDetailsPayload(bankAccounts),
      kyb_aml_observations: kybAmlObservations,
      financial_risk: financialRisk,
      financials_currency: financialsCurrency,
      assets_minor: assets ? intValue(assets) : null,
      liabilities_minor: liabilities ? intValue(liabilities) : null,
      revenue_last_year_minor: revenue ? intValue(revenue) : null,
      profit_last_year_minor: profit ? intValue(profit) : null,
      clear_assets: !assets,
      clear_liabilities: !liabilities,
      clear_revenue_last_year: !revenue,
      clear_profit_last_year: !profit,
      note,
      evidence_summary: evidenceSummary
    };
    if (isFixturePreview) {
      setPreview(`${legalName} borrower record would be updated.`);
      return;
    }
    mutation.mutate({ borrowerId: borrower.id, data });
  }

  return (
    <div className="admin-form-panel">
      <form className="admin-action-form" onSubmit={submit}>
        <div className="admin-context-bar">
          <span>Borrower ID</span>
          <code>{borrower.id}</code>
          <Chip tone={statusTone(borrower.kyb_status)}>{labelize(borrower.kyb_status)}</Chip>
        </div>
        <FieldGrid>
          <TextInput label="Legal name" onChange={setLegalName} required value={legalName} />
          <TextInput label="Year founded" onChange={setYearFounded} required value={yearFounded} />
          <SelectInput label="Entity type" onChange={setEntityType} options={Object.values(BorrowerEntityTypeEnum)} value={entityType} />
          <SelectInput label="KYB status" onChange={setKybStatus} options={Object.values(BorrowerKybStatusEnum)} value={kybStatus} />
          <TextInput label="Country" onChange={setCountry} value={country} />
          <TextInput label="Registration number" onChange={setRegistrationNumber} value={registrationNumber} />
          <TextInput label="Business classification" onChange={setBusinessClassification} value={businessClassification} />
          <TextInput label="Financials currency" onChange={setFinancialsCurrency} value={financialsCurrency} />
          <MoneyMinorInput currency={financialsCurrency} label="Assets minor units" onChange={setAssets} value={assets} />
          <MoneyMinorInput currency={financialsCurrency} label="Liabilities minor units" onChange={setLiabilities} value={liabilities} />
          <MoneyMinorInput currency={financialsCurrency} label="Revenue last year minor" onChange={setRevenue} value={revenue} />
          <MoneyMinorInput currency={financialsCurrency} label="Profit last year minor" onChange={setProfit} value={profit} />
        </FieldGrid>
        <label className="check-row">
          <input checked={businessClassificationPublic} onChange={(event) => setBusinessClassificationPublic(event.target.checked)} type="checkbox" />
          Show business classification to lenders.
        </label>
        <TextAreaInput label="Registered address" onChange={setRegisteredAddress} value={registeredAddress} />
        <label className="check-row">
          <input checked={registeredAddressPublic} onChange={(event) => setRegisteredAddressPublic(event.target.checked)} type="checkbox" />
          Show registered address to lenders.
        </label>
        <TextAreaInput label="Contact info" onChange={setContactInfo} value={contactInfo} />
        <label className="check-row">
          <input checked={contactInfoPublic} onChange={(event) => setContactInfoPublic(event.target.checked)} type="checkbox" />
          Show contact info to lenders.
        </label>
        <TextAreaInput hint="Internal only." label="Ownership" onChange={setOwnershipStructure} value={ownershipStructure} />
        <TextAreaInput hint="Internal only. Plain notes are stored under bank_account_details.notes; JSON objects are accepted for structured details." label="Bank accounts" onChange={setBankAccounts} value={bankAccounts} />
        <TextAreaInput hint="Internal only." label="KYB/AML observations" onChange={setKybAmlObservations} value={kybAmlObservations} />
        <TextAreaInput hint="Internal only." label="Financial risk" onChange={setFinancialRisk} value={financialRisk} />
        <label className="check-row">
          <input checked={complianceHold} onChange={(event) => setComplianceHold(event.target.checked)} type="checkbox" />
          Compliance hold is active.
        </label>
        <TextAreaInput label="Admin note" onChange={setNote} value={note} />
        <TextAreaInput label="Evidence summary" onChange={setEvidenceSummary} value={evidenceSummary} />
        <ActionFooter mutation={mutation} previewMessage={preview} successMessage={success} submitLabel="Save borrower changes" />
      </form>
    </div>
  );
}

function OriginalScheduleInformationalViewer({
  currency,
  principalMinor,
  interestRateBps,
  termMonths,
  startDate,
  repaymentType,
  interestOnlyMonths
}: {
  currency: string;
  principalMinor: number;
  interestRateBps: number;
  termMonths: number;
  startDate: string;
  repaymentType: LoanRepaymentType;
  interestOnlyMonths: number;
}) {
  const rows = useMemo(
    () => originalPreviewScheduleRows(
      principalMinor,
      interestRateBps,
      termMonths,
      startDate,
      repaymentType,
      interestOnlyMonths
    ),
    [interestOnlyMonths, interestRateBps, principalMinor, repaymentType, startDate, termMonths]
  );
  const totals = rows.reduce(
    (acc, row) => {
      acc.principal += row.principal_minor;
      acc.interest += row.interest_minor;
      acc.total += row.total_minor;
      return acc;
    },
    { principal: 0, interest: 0, total: 0 }
  );
  if (!rows.length) return null;
  return (
    <div className="admin-schedule-review">
      <div className="admin-subsection-header">
        <div>
          <h4>Original loan schedule (informational)</h4>
          <p className="muted">
            Client-side preview of the original loan contract. The backend computes the authoritative original
            schedule from the original payment type; installments due before today are tagged.
          </p>
        </div>
        <div className="admin-schedule-summary">
          <Chip tone="neutral">{termMonths} instalments</Chip>
          <Chip tone="neutral">{formatRateBps(interestRateBps)}</Chip>
          <Chip tone="neutral">{labelize(repaymentType)}</Chip>
          {interestOnlyMonths > 0 ? <Chip tone="neutral">{interestOnlyMonths} IO months</Chip> : null}
        </div>
      </div>
      <div className="table-wrap admin-table-wrap">
        <table className="admin-table admin-schedule-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Due date</th>
              <th className="num">Principal</th>
              <th className="num">Interest</th>
              <th className="num">Instalment</th>
              <th className="num">Outstanding after</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.installment_number}>
                <td>
                  {row.installment_number}
                  {isPastBusinessDate(row.due_date) ? <> <Chip tone="warn">Due</Chip></> : null}
                </td>
                <td>{formatDate(row.due_date)}</td>
                <td className="num"><Money amountMinor={row.principal_minor} currency={currency} /></td>
                <td className="num"><Money amountMinor={row.interest_minor} currency={currency} /></td>
                <td className="num"><Money amountMinor={row.total_minor} currency={currency} /></td>
                <td className="num"><Money amountMinor={row.outstanding_after_minor} currency={currency} /></td>
              </tr>
            ))}
          </tbody>
          <tfoot className="schedule-totals">
            <tr>
              <th colSpan={2}>Totals</th>
              <th className="num"><Money amountMinor={totals.principal} currency={currency} /></th>
              <th className="num"><Money amountMinor={totals.interest} currency={currency} /></th>
              <th className="num"><Money amountMinor={totals.total} currency={currency} /></th>
              <th className="num">-</th>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

function RefinancingFields({
  currency,
  isRefinancing,
  onIsRefinancingChange,
  originalPrincipal,
  onOriginalPrincipalChange,
  originalRateBps,
  onOriginalRateBpsChange,
  originalTermMonths,
  onOriginalTermMonthsChange,
  originalRepaymentType,
  onOriginalRepaymentTypeChange,
  originalInterestOnlyMonths,
  onOriginalInterestOnlyMonthsChange,
  originalStartDate,
  onOriginalStartDateChange
}: {
  currency: string;
  isRefinancing: boolean;
  onIsRefinancingChange: (value: boolean) => void;
  originalPrincipal: string;
  onOriginalPrincipalChange: (value: string) => void;
  originalRateBps: string;
  onOriginalRateBpsChange: (value: string) => void;
  originalTermMonths: string;
  onOriginalTermMonthsChange: (value: string) => void;
  originalRepaymentType: LoanRepaymentType;
  onOriginalRepaymentTypeChange: (value: LoanRepaymentType) => void;
  originalInterestOnlyMonths: string;
  onOriginalInterestOnlyMonthsChange: (value: string) => void;
  originalStartDate: string;
  onOriginalStartDateChange: (value: string) => void;
}) {
  const originalInputsComplete =
    isRefinancing &&
    intValue(originalPrincipal) > 0 &&
    intValue(originalTermMonths) > 0 &&
    Boolean(originalStartDate);
  return (
    <>
      <label className="check-row">
        <input checked={isRefinancing} onChange={(event) => onIsRefinancingChange(event.target.checked)} type="checkbox" />
        Refinancing loan (takes over an ongoing loan contract).
      </label>
      {isRefinancing ? (
        <>
          <FieldGrid>
            <MoneyMinorInput
              currency={currency}
              label="Original contractual principal minor units"
              onChange={onOriginalPrincipalChange}
              required
              value={originalPrincipal}
            />
            <TextInput label="Original interest bps" onChange={onOriginalRateBpsChange} required value={originalRateBps} />
            <TextInput label="Original term months" onChange={onOriginalTermMonthsChange} required value={originalTermMonths} />
            <SelectInput
              label="Original repayment type"
              onChange={onOriginalRepaymentTypeChange}
              options={Object.values(RepaymentTypeEnum)}
              value={originalRepaymentType}
            />
            <TextInput
              hint="Use 0 except for interest-only then amortizing. Bullet interest-only months are inferred from term."
              label="Original interest-only months"
              onChange={onOriginalInterestOnlyMonthsChange}
              required
              value={originalInterestOnlyMonths}
            />
            <TextInput label="Original loan start date" onChange={onOriginalStartDateChange} required type="date" value={originalStartDate} />
          </FieldGrid>
          {originalInputsComplete ? (
            <OriginalScheduleInformationalViewer
              currency={currency}
              interestRateBps={intValue(originalRateBps)}
              principalMinor={intValue(originalPrincipal)}
              repaymentType={originalRepaymentType}
              startDate={originalStartDate}
              interestOnlyMonths={intValue(originalInterestOnlyMonths)}
              termMonths={intValue(originalTermMonths)}
            />
          ) : null}
        </>
      ) : null}
    </>
  );
}

function LoanCreateForm({ defaultBorrowerId, onCreated }: { defaultBorrowerId: string; onCreated?: () => void }) {
  const [borrowerId, setBorrowerId] = useState(defaultBorrowerId);
  const [borrowerQuery, setBorrowerQuery] = useState(defaultBorrowerId);
  const [title, setTitle] = useState("New real-estate backed facility");
  const [summary, setSummary] = useState("Admin-entered investor summary for the loan.");
  const [principal, setPrincipal] = useState(isFixturePreview ? "100000000" : "");
  const [currency, setCurrency] = useState("CHF");
  const [rateBps, setRateBps] = useState("950");
  const [termMonths, setTermMonths] = useState("12");
  const [purpose, setPurpose] = useState<LoanPurpose>(PurposeEnum.bridge_financing);
  const [repaymentType, setRepaymentType] = useState<LoanRepaymentType>(RepaymentTypeEnum.equal_installments);
  const [collateralType, setCollateralType] = useState<LoanCollateralType>(CollateralTypeEnum.real_estate);
  const [collateralValue, setCollateralValue] = useState(isFixturePreview ? "160000000" : "");
  const [riskRating, setRiskRating] = useState<LoanRiskRating>(RiskRatingEnum.BBB);
  const [loanStartDate, setLoanStartDate] = useState("");
  const [fundingDeadline, setFundingDeadline] = useState("");
  const [minimumSubscriptionBps, setMinimumSubscriptionBps] = useState("5000");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1LoansAdminLoansCreate({
    mutation: {
      onSuccess: () => {
        setSuccess("Loan draft was created and schedule validations ran server-side.");
        onCreated?.();
      }
    }
  });

  useEffect(() => {
    setBorrowerId(defaultBorrowerId);
    setBorrowerQuery(defaultBorrowerId);
  }, [defaultBorrowerId]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: LoanCreateRequest = {
      borrower_id: borrowerId,
      title,
      investor_summary: summary,
      purpose,
      is_refinancing: false,
      principal_minor: intValue(principal),
      currency,
      interest_rate_bps: intValue(rateBps),
      term_months: intValue(termMonths),
      repayment_type: repaymentType,
      loan_start_date: loanStartDate || undefined,
      funding_deadline: fundingDeadline || undefined,
      collateral_type: collateralType,
      collateral_value_minor: intValue(collateralValue),
      risk_rating: riskRating,
      minimum_subscription_bps: minimumSubscriptionBps ? intValue(minimumSubscriptionBps) : 5000
    };
    if (isFixturePreview) {
      setPreview(`${title} loan draft would be created for ${borrowerId}.`);
      return;
    }
    mutation.mutate({ data });
  }

  return (
    <div className="admin-form-panel">
      <h2>Create loan draft</h2>
      <div className="admin-context-bar">
        <span>Selected borrower</span>
        <strong className="mono">{borrowerId || "No borrower selected"}</strong>
      </div>
      <form className="admin-action-form" onSubmit={submit}>
        <FieldGrid>
          <BorrowerLookupInput
            onChange={setBorrowerId}
            onQueryChange={setBorrowerQuery}
            query={borrowerQuery}
            required
            value={borrowerId}
          />
          <TextInput label="Title" onChange={setTitle} required value={title} />
          <MoneyMinorInput currency={currency} label="Financeable principal minor units" onChange={setPrincipal} required value={principal} />
          <TextInput label="Currency" onChange={setCurrency} required value={currency} />
          <TextInput label="Interest bps" onChange={setRateBps} required value={rateBps} />
          <TextInput label="Term months" onChange={setTermMonths} required value={termMonths} />
          <SelectInput label="Purpose" onChange={setPurpose} options={Object.values(PurposeEnum)} value={purpose} />
          <SelectInput label="Repayment type" onChange={setRepaymentType} options={Object.values(RepaymentTypeEnum)} value={repaymentType} />
          <SelectInput label="Collateral type" onChange={setCollateralType} options={Object.values(CollateralTypeEnum)} value={collateralType} />
          <MoneyMinorInput currency={currency} label="Collateral value minor" onChange={setCollateralValue} required value={collateralValue} />
          <SelectInput label="Risk rating" onChange={setRiskRating} options={Object.values(RiskRatingEnum)} value={riskRating} />
          <TextInput
            hint="First installment: one month after loan start date."
            label="Loan start date"
            onChange={setLoanStartDate}
            type="date"
            value={loanStartDate}
          />
          <TextInput label="Funding deadline" onChange={setFundingDeadline} type="date" value={fundingDeadline} />
          <TextInput
            hint="If subscriptions reach this share of the principal by the deadline, the loan closes at the subscribed amount; below it, the campaign is cancelled and refunded."
            label="Minimum subscription bps"
            onChange={setMinimumSubscriptionBps}
            value={minimumSubscriptionBps}
          />
        </FieldGrid>
        <Banner tone="neutral" title="Existing-loan acquisitions use Loan Originator claims">
          New refinancing products are disabled. Import an existing performing final-borrower claim through the Loan Originator workflow instead.
        </Banner>
        <TextAreaInput label="Investor summary" onChange={setSummary} required value={summary} />
        <ActionFooter mutation={mutation} previewMessage={preview} successMessage={success} submitLabel="Create loan draft" />
      </form>
    </div>
  );
}

function LoanEditForm({ loan, onSaved }: { loan: Loan; onSaved?: () => void }) {
  const [title, setTitle] = useState(loan.title);
  const [summary, setSummary] = useState(loan.investor_summary);
  const [principal, setPrincipal] = useState(String(loan.principal_minor));
  const [isRefinancing, setIsRefinancing] = useState(loan.is_refinancing);
  const [originalPrincipal, setOriginalPrincipal] = useState(
    loan.is_refinancing ? String(loan.original_principal_minor) : ""
  );
  const [originalRateBps, setOriginalRateBps] = useState(
    loan.original_interest_rate_bps === null ? "" : String(loan.original_interest_rate_bps)
  );
  const [originalTermMonths, setOriginalTermMonths] = useState(
    loan.original_term_months === null ? "" : String(loan.original_term_months)
  );
  const [originalRepaymentType, setOriginalRepaymentType] = useState<LoanRepaymentType>(
    (loan.original_repayment_type ?? RepaymentTypeEnum.equal_installments) as LoanRepaymentType
  );
  const [originalInterestOnlyMonths, setOriginalInterestOnlyMonths] = useState(
    loan.original_interest_only_months === null ? "0" : String(loan.original_interest_only_months)
  );
  const [originalStartDate, setOriginalStartDate] = useState(loan.original_loan_start_date ?? "");
  const [rateBps, setRateBps] = useState(String(loan.interest_rate_bps));
  const [termMonths, setTermMonths] = useState(String(loan.term_months));
  const [purpose, setPurpose] = useState<LoanPurpose>(loan.purpose as LoanPurpose);
  const [repaymentType, setRepaymentType] = useState<LoanRepaymentType>(loan.repayment_type as LoanRepaymentType);
  const [collateralType, setCollateralType] = useState<LoanCollateralType>(loan.collateral_type as LoanCollateralType);
  const [collateralValue, setCollateralValue] = useState(String(loan.collateral_value_minor));
  const [riskRating, setRiskRating] = useState<LoanRiskRating>(loan.risk_rating as LoanRiskRating);
  const [loanStartDate, setLoanStartDate] = useState(loan.loan_start_date);
  const [fundingDeadline, setFundingDeadline] = useState(loan.funding_deadline);
  const [minimumSubscriptionBps, setMinimumSubscriptionBps] = useState(
    String(loan.minimum_subscription_bps ?? 5000)
  );
  const [investorMessage, setInvestorMessage] = useState("");
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1LoansAdminLoansPartialUpdate({
    mutation: {
      onSuccess: () => {
        setSuccess("Loan changes were saved.");
        onSaved?.();
      }
    }
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: PatchedLoanUpdateRequest = {
      title,
      investor_summary: summary,
      purpose,
      is_refinancing: isRefinancing,
      ...(isRefinancing
        ? {
            original_principal_minor: intValue(originalPrincipal),
            original_interest_rate_bps: intValue(originalRateBps),
            original_term_months: intValue(originalTermMonths),
            original_repayment_type: originalRepaymentType,
            original_interest_only_months: intValue(originalInterestOnlyMonths),
            original_loan_start_date: originalStartDate
          }
        : {}),
      principal_minor: intValue(principal),
      interest_rate_bps: intValue(rateBps),
      term_months: intValue(termMonths),
      repayment_type: repaymentType,
      loan_start_date: loanStartDate,
      funding_deadline: fundingDeadline || undefined,
      ...(loan.status === "draft"
        ? { minimum_subscription_bps: intValue(minimumSubscriptionBps) }
        : {}),
      collateral_type: collateralType,
      collateral_value_minor: intValue(collateralValue),
      risk_rating: riskRating,
      investor_message: investorMessage,
      note
    };
    if (isFixturePreview) {
      setPreview(`${title} loan record would be updated.`);
      return;
    }
    mutation.mutate({ loanId: loan.id, data });
  }

  return (
    <div className="admin-form-panel">
      <form className="admin-action-form" onSubmit={submit}>
        <div className="admin-context-bar">
          <span>Loan ID</span>
          <code>{loan.id}</code>
          <Chip tone={statusTone(loan.status)}>{labelize(loan.status)}</Chip>
          <span>Committed <Money amountMinor={loan.committed_principal_minor} currency={loan.currency} /></span>
        </div>
        {loan.committed_principal_minor > 0 ? (
          <Banner tone="warn" title="Committed investments exist">
            Published principal and minimum subscription are frozen. Use Resolve funding deadline
            after expiry; the deterministic resolver alone may reduce principal to the subscribed
            amount when the disclosed threshold is met.
          </Banner>
        ) : null}
        <FieldGrid>
          <TextInput label="Title" onChange={setTitle} required value={title} />
          <MoneyMinorInput
            currency={loan.currency}
            hint={
              loan.status === "draft"
                ? "Editable until publication."
                : "Frozen at publication. Only deterministic funding close may reduce it to the subscribed amount."
            }
            label="Financeable principal minor units"
            onChange={setPrincipal}
            readOnly={loan.status !== "draft"}
            required
            value={principal}
          />
          <TextInput label="Interest bps" onChange={setRateBps} required value={rateBps} />
          <TextInput label="Term months" onChange={setTermMonths} required value={termMonths} />
          <SelectInput label="Purpose" onChange={setPurpose} options={Object.values(PurposeEnum)} value={purpose} />
          <SelectInput label="Repayment type" onChange={setRepaymentType} options={Object.values(RepaymentTypeEnum)} value={repaymentType} />
          <SelectInput label="Collateral type" onChange={setCollateralType} options={Object.values(CollateralTypeEnum)} value={collateralType} />
          <MoneyMinorInput currency={loan.currency} label="Collateral value minor" onChange={setCollateralValue} required value={collateralValue} />
          <SelectInput label="Risk rating" onChange={setRiskRating} options={Object.values(RiskRatingEnum)} value={riskRating} />
          <TextInput
            hint="First installment: one month after loan start date."
            label="Loan start date"
            onChange={setLoanStartDate}
            type="date"
            value={loanStartDate}
          />
          <TextInput label="Funding deadline" onChange={setFundingDeadline} type="date" value={fundingDeadline ?? ""} />
          <TextInput
            hint={
              loan.status === "draft"
                ? "Editable until publication. Publishing discloses and permanently freezes this threshold. At the deadline, it automatically decides whether the loan closes or is cancelled and refunded."
                : "Frozen at publication. At the deadline, this disclosed percentage automatically decides whether the loan closes or is cancelled and refunded."
            }
            label="Minimum subscription bps"
            onChange={setMinimumSubscriptionBps}
            readOnly={loan.status !== "draft"}
            value={minimumSubscriptionBps}
          />
        </FieldGrid>
        <RefinancingFields
          currency={loan.currency}
          isRefinancing={isRefinancing}
          onIsRefinancingChange={setIsRefinancing}
          onOriginalPrincipalChange={setOriginalPrincipal}
          onOriginalRateBpsChange={setOriginalRateBps}
          onOriginalRepaymentTypeChange={setOriginalRepaymentType}
          onOriginalInterestOnlyMonthsChange={setOriginalInterestOnlyMonths}
          onOriginalStartDateChange={setOriginalStartDate}
          onOriginalTermMonthsChange={setOriginalTermMonths}
          originalInterestOnlyMonths={originalInterestOnlyMonths}
          originalPrincipal={originalPrincipal}
          originalRateBps={originalRateBps}
          originalRepaymentType={originalRepaymentType}
          originalStartDate={originalStartDate}
          originalTermMonths={originalTermMonths}
        />
        <TextAreaInput label="Investor summary" onChange={setSummary} required value={summary} />
        <TextAreaInput
          hint="Required when lowering principal after committed investments exist."
          label="Investor message"
          onChange={setInvestorMessage}
          value={investorMessage}
        />
        <TextAreaInput label="Admin note" onChange={setNote} value={note} />
        <ActionFooter mutation={mutation} previewMessage={preview} successMessage={success} submitLabel="Save loan changes" />
      </form>
    </div>
  );
}

type ManageLoanActionId = "publish" | "cancel" | "expiry" | "release" | "disburse" | "servicing" | "recovery";

const MANAGE_LOAN_ACTIONS: Array<{
  id: ManageLoanActionId;
  title: string;
  description: string;
  statuses: string[];
  danger?: boolean;
}> = [
  {
    id: "publish",
    title: "Publish loan",
    description: "Put this draft live on the primary market so investors can place orders.",
    statuses: ["draft"]
  },
  {
    id: "cancel",
    title: "Cancel funding",
    description:
      "Stop the campaign before close: reserved balances are released and pending orders close as not invested.",
    statuses: ["published", "funding_close_failed"],
    danger: true
  },
  {
    id: "expiry",
    title: "Resolve funding deadline",
    description:
      "Apply the stored minimum automatically: close at the subscribed amount, or cancel and refund below the minimum. Failed resolutions can be retried after the cause is fixed.",
    statuses: ["published", "funding_close_failed"]
  },
  {
    id: "release",
    title: "Release an order's balance",
    description:
      "Return one allocated order's reserved balance to its investor without touching the rest of the campaign.",
    statuses: ["published", "funding_close_failed"],
    danger: true
  },
  {
    id: "disburse",
    title: "Borrower disbursement",
    description:
      "Record the external payout of the funded principal, less the BANXUM success fee, to the borrower.",
    statuses: ["funded"]
  },
  {
    id: "servicing",
    title: "Record borrower repayment",
    description:
      "Declare a matched incoming borrower payment against the next due installment, or record a repayment in advance with a schedule preview.",
    statuses: ["active", "late"]
  },
  {
    id: "recovery",
    title: "Record a recovery payment",
    description:
      "For a defaulted loan: record recovered funds and distribute them to lenders through the recovery waterfall.",
    statuses: ["defaulted"],
    danger: true
  }
];

function LoanScheduleReadonlyReview({
  loan,
  rows,
  loading,
  error
}: {
  loan: Loan;
  rows: LoanInstallment[];
  loading: boolean;
  error: unknown;
}) {
  let cumulativePrincipal = 0;
  const totals = rows.reduce(
    (acc, row) => {
      acc.principal += row.principal_minor;
      acc.interest += row.interest_minor;
      acc.total += row.total_minor;
      return acc;
    },
    { principal: 0, interest: 0, total: 0 }
  );
  const scheduleMatchesFinanceable = totals.principal === loan.principal_minor;

  return (
    <div className="admin-schedule-review">
      <div className="admin-subsection-header">
        <div>
          <h4>Repayment schedule review</h4>
          <p className="muted">
            Review the server-generated repayment schedule before publishing. The schedule is derived from the
            financeable principal.
          </p>
        </div>
        <div className="admin-schedule-summary">
          <Chip tone="neutral">Version {loan.schedule_version}</Chip>
          <Chip tone="neutral">{labelize(loan.repayment_type)}</Chip>
          <Chip tone="neutral">{loan.term_months} instalments</Chip>
        </div>
      </div>

      <div className="admin-schedule-metrics">
        <div className="admin-schedule-metric emphasis">
          <span>Financeable principal</span>
          <strong><Money amountMinor={loan.principal_minor} currency={loan.currency} /></strong>
        </div>
        <div className="admin-schedule-metric">
          <span>Scheduled principal</span>
          <strong><Money amountMinor={totals.principal} currency={loan.currency} /></strong>
        </div>
        <div className="admin-schedule-metric">
          <span>Scheduled interest</span>
          <strong><Money amountMinor={totals.interest} currency={loan.currency} /></strong>
        </div>
        <div className="admin-schedule-metric">
          <span>Total payments</span>
          <strong><Money amountMinor={totals.total} currency={loan.currency} /></strong>
        </div>
      </div>

      {loading ? <Banner tone="info" title="Loading schedule">Fetching the current server-generated schedule.</Banner> : null}
      {error ? <Banner tone="bad" title="Schedule unavailable">{errorMessage(error)}</Banner> : null}
      {!loading && !error && rows.length === 0 ? (
        <Banner tone="bad" title="No schedule rows">The loan has no current schedule rows. Publishing is blocked until a schedule exists.</Banner>
      ) : null}
      {!loading && !error && rows.length > 0 && !scheduleMatchesFinanceable ? (
        <Banner tone="bad" title="Schedule principal mismatch">
          The scheduled principal must equal the financeable principal before publishing.
        </Banner>
      ) : null}
      {!loading && !error && rows.length > 0 && scheduleMatchesFinanceable ? (
        <Banner tone="ok" title="Schedule reconciles">
          The scheduled principal equals the financeable principal.
        </Banner>
      ) : null}

      {rows.length ? (
        <div className="table-wrap admin-table-wrap">
          <table className="admin-table admin-schedule-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Due date</th>
                <th className="num">Instalment</th>
                <th className="num">Principal</th>
                <th className="num">Interest</th>
                <th className="num">Outstanding after</th>
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                cumulativePrincipal += row.principal_minor;
                const outstandingAfter = Math.max(0, totals.principal - cumulativePrincipal);
                return (
                  <tr key={row.id}>
                    <td>{row.installment_number}</td>
                    <td>{formatDate(row.due_date)}</td>
                    <td className="num"><Money amountMinor={row.total_minor} currency={loan.currency} /></td>
                    <td className="num"><Money amountMinor={row.principal_minor} currency={loan.currency} /></td>
                    <td className="num"><Money amountMinor={row.interest_minor} currency={loan.currency} /></td>
                    <td className="num"><Money amountMinor={outstandingAfter} currency={loan.currency} /></td>
                    <td>{row.admin_overridden ? <Chip tone="warn">Manual</Chip> : <Chip tone="neutral">Generated</Chip>}</td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot className="schedule-totals">
              <tr>
                <th colSpan={2}>Totals</th>
                <th className="num"><Money amountMinor={totals.total} currency={loan.currency} /></th>
                <th className="num"><Money amountMinor={totals.principal} currency={loan.currency} /></th>
                <th className="num"><Money amountMinor={totals.interest} currency={loan.currency} /></th>
                <th />
                <th />
              </tr>
            </tfoot>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function OriginalScheduleReview({
  loan,
  rows,
  loading,
  error,
  paidInstallmentNumbers,
  onTogglePaidInstallment
}: {
  loan: Loan;
  rows: OriginalLoanScheduleRow[];
  loading: boolean;
  error: unknown;
  paidInstallmentNumbers: number[];
  onTogglePaidInstallment: (installmentNumber: number) => void;
}) {
  const paidSet = new Set(paidInstallmentNumbers);
  const totals = rows.reduce(
    (acc, row) => {
      acc.principal += row.principal_minor;
      acc.interest += row.interest_minor;
      acc.total += row.total_minor;
      if (paidSet.has(row.installment_number)) {
        acc.paidPrincipal += row.principal_minor;
        acc.paidInterest += row.interest_minor;
      }
      return acc;
    },
    { principal: 0, interest: 0, total: 0, paidPrincipal: 0, paidInterest: 0 }
  );
  const remainingOutstanding = loan.original_principal_minor - totals.paidPrincipal;
  const overFinanced = loan.principal_minor > remainingOutstanding;
  const underFinanced = loan.principal_minor < remainingOutstanding;
  const selectedPaidCount = paidInstallmentNumbers.length;

  return (
    <div className="admin-schedule-review">
      <div className="admin-subsection-header">
        <div>
          <h4>Original loan schedule review</h4>
          <p className="muted">
            This refinancing loan takes over an ongoing contract. Mark the original installments the borrower has
            already paid to the original lender; they reduce the remaining outstanding that BANXUM finances.
          </p>
        </div>
        <div className="admin-schedule-summary">
          <Chip tone="neutral">{rows.length || loan.original_term_months || 0} instalments</Chip>
          <Chip tone="neutral">{formatRateBps(loan.original_interest_rate_bps ?? 0)}</Chip>
          {loan.original_repayment_type ? <Chip tone="neutral">{labelize(loan.original_repayment_type)}</Chip> : null}
          {loan.original_interest_only_months ? <Chip tone="neutral">{loan.original_interest_only_months} IO months</Chip> : null}
          {loan.original_loan_start_date ? <Chip tone="neutral">Started {formatDate(loan.original_loan_start_date)}</Chip> : null}
        </div>
      </div>

      <div className="admin-schedule-metrics">
        <div className="admin-schedule-metric">
          <span>Original principal</span>
          <strong><Money amountMinor={loan.original_principal_minor} currency={loan.currency} /></strong>
        </div>
        <div className="admin-schedule-metric">
          <span>Paid before publication</span>
          <strong><Money amountMinor={totals.paidPrincipal} currency={loan.currency} /></strong>
          <small>
            {selectedPaidCount} instalment{selectedPaidCount === 1 ? "" : "s"} selected
            {totals.paidInterest > 0 ? `, ${formatMoneyMinor(totals.paidInterest, loan.currency)} interest` : ""}
          </small>
        </div>
        <div className="admin-schedule-metric emphasis">
          <span>Remaining outstanding</span>
          <strong><Money amountMinor={remainingOutstanding} currency={loan.currency} /></strong>
        </div>
        <div className="admin-schedule-metric emphasis">
          <span>Financeable principal</span>
          <strong><Money amountMinor={loan.principal_minor} currency={loan.currency} /></strong>
        </div>
      </div>

      {loading ? <Banner tone="info" title="Loading original schedule">Fetching the computed original loan schedule.</Banner> : null}
      {error ? <Banner tone="bad" title="Original schedule unavailable">{errorMessage(error)}</Banner> : null}
      {!loading && !error && rows.length === 0 ? (
        <Banner tone="bad" title="No original schedule rows">
          The original loan schedule could not be computed. Check the original principal, interest, term and start
          date on the loan before publishing.
        </Banner>
      ) : null}
      {!loading && !error && rows.length > 0 && overFinanced ? (
        <Banner tone="bad" title="Financeable principal exceeds remaining outstanding">
          The financeable principal is larger than the remaining outstanding of the original schedule. Reduce the
          financeable amount or adjust the paid installment selections before publishing.
        </Banner>
      ) : null}
      {!loading && !error && rows.length > 0 && underFinanced ? (
        <Banner tone="info" title="Financing less than the remaining outstanding">
          The financeable principal is below the remaining outstanding of the original schedule. This is allowed;
          the difference stays with the original lender and is not financed on BANXUM.
        </Banner>
      ) : null}
      {!loading && !error && rows.length > 0 && !overFinanced && !underFinanced ? (
        <Banner tone="ok" title="Schedule reconciles">
          The financeable principal equals the remaining outstanding of the original schedule.
        </Banner>
      ) : null}

      {rows.length ? (
        <div className="table-wrap admin-table-wrap">
          <table className="admin-table admin-schedule-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Due date</th>
                <th>Paid</th>
                <th className="num">Instalment</th>
                <th className="num">Principal</th>
                <th className="num">Interest</th>
                <th className="num">Outstanding after</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const canMarkPaid = isPastBusinessDate(row.due_date);
                return (
                  <tr key={row.installment_number}>
                    <td>{row.installment_number}</td>
                    <td>{formatDate(row.due_date)}</td>
                    <td>
                      <label className="admin-checkbox-line compact">
                        <input
                          aria-label={`Mark original installment ${row.installment_number} paid before publication`}
                          checked={paidSet.has(row.installment_number)}
                          disabled={!canMarkPaid}
                          onChange={() => onTogglePaidInstallment(row.installment_number)}
                          type="checkbox"
                        />
                        <span>{canMarkPaid ? "Paid" : "Future"}</span>
                      </label>
                    </td>
                    <td className="num"><Money amountMinor={row.total_minor} currency={loan.currency} /></td>
                    <td className="num"><Money amountMinor={row.principal_minor} currency={loan.currency} /></td>
                    <td className="num"><Money amountMinor={row.interest_minor} currency={loan.currency} /></td>
                    <td className="num"><Money amountMinor={row.outstanding_after_minor} currency={loan.currency} /></td>
                  </tr>
                );
              })}
            </tbody>
            <tfoot className="schedule-totals">
              <tr>
                <th colSpan={2}>Totals</th>
                <th>{selectedPaidCount} selected</th>
                <th className="num"><Money amountMinor={totals.total} currency={loan.currency} /></th>
                <th className="num"><Money amountMinor={totals.principal} currency={loan.currency} /></th>
                <th className="num"><Money amountMinor={totals.interest} currency={loan.currency} /></th>
                <th />
              </tr>
            </tfoot>
          </table>
        </div>
      ) : null}
    </div>
  );
}

function ManageLoanModal({
  loan,
  onChanged,
  onClose
}: {
  loan: Loan;
  onChanged: () => void;
  onClose: () => void;
}) {
  const [action, setAction] = useState<ManageLoanActionId | null>(null);
  const [note, setNote] = useState("");
  const [cancelReason, setCancelReason] = useState("Campaign cancelled before funding close.");
  const [cancelInvestorMessage, setCancelInvestorMessage] = useState(
    "The campaign was cancelled before funding close. Any reserved balance has been released to your BANXUM account."
  );
  const [expiryAsOfDate, setExpiryAsOfDate] = useState(today);
  const [expiryReason, setExpiryReason] = useState("");
  const [expiryInvestorMessage, setExpiryInvestorMessage] = useState("");
  const [scanSelectedOnly, setScanSelectedOnly] = useState(true);
  const [orderId, setOrderId] = useState("");
  const [orderQuery, setOrderQuery] = useState("");
  const [releaseReason, setReleaseReason] = useState("Campaign closed or order not funded.");
  const [recGross, setRecGross] = useState("1000000");
  const [recExternalCosts, setRecExternalCosts] = useState("0");
  const [recThirdPartyCosts, setRecThirdPartyCosts] = useState("0");
  const [recFeeApplied, setRecFeeApplied] = useState(false);
  const [recFeeBps, setRecFeeBps] = useState("0");
  const [recContractualInterestDue, setRecContractualInterestDue] = useState("0");
  const [recDefaultInterestDue, setRecDefaultInterestDue] = useState("0");
  const [recPenaltiesDue, setRecPenaltiesDue] = useState("0");
  const [recBookingDate, setRecBookingDate] = useState(today);
  const [recValueDate, setRecValueDate] = useState(today);
  const [recPayerName, setRecPayerName] = useState(loan.title);
  const [prePublicationPaidNumbers, setPrePublicationPaidNumbers] = useState<number[]>(
    loan.pre_publication_paid_installments ?? []
  );
  const [publishStep, setPublishStep] = useState<"original" | "loan">("original");
  const [originalPaidInitializedFor, setOriginalPaidInitializedFor] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const loanId = loan.id;
  const scheduleQuery = useV1LoansAdminLoansScheduleList(loanId, {
    query: { enabled: !isFixturePreview && action === "publish", staleTime: 0 }
  });
  const originalScheduleQuery = useV1LoansAdminLoansOriginalScheduleList(loanId, {
    query: { enabled: !isFixturePreview && action === "publish" && loan.is_refinancing, staleTime: 0 }
  });
  const fixtureScheduleRows = useMemo(() => previewScheduleRows(loan), [loan]);
  const scheduleRows = useMemo(
    () => (isFixturePreview ? fixtureScheduleRows : scheduleQuery.data ?? []),
    [fixtureScheduleRows, scheduleQuery.data]
  );
  const fixtureOriginalScheduleRows = useMemo(() => previewOriginalScheduleRows(loan), [loan]);
  const originalScheduleRows = useMemo(
    () => (isFixturePreview ? fixtureOriginalScheduleRows : originalScheduleQuery.data ?? []),
    [fixtureOriginalScheduleRows, originalScheduleQuery.data]
  );
  const scheduledPrincipal = scheduleRows.reduce((sum, row) => sum + row.principal_minor, 0);
  const loanScheduleLoading = !isFixturePreview && scheduleQuery.isFetching && scheduleRows.length === 0;
  const loanScheduleBlocks =
    (!isFixturePreview && (scheduleQuery.isFetching || Boolean(scheduleQuery.error))) ||
    scheduleRows.length === 0 ||
    scheduledPrincipal !== loan.principal_minor;
  const originalPaidPrincipal = originalScheduleRows.reduce(
    (sum, row) => sum + (prePublicationPaidNumbers.includes(row.installment_number) ? row.principal_minor : 0),
    0
  );
  const originalRemainingOutstanding = loan.original_principal_minor - originalPaidPrincipal;
  const originalScheduleLoading =
    !isFixturePreview && originalScheduleQuery.isFetching && originalScheduleRows.length === 0;
  const originalScheduleBlocks =
    loan.is_refinancing &&
    ((!isFixturePreview && (originalScheduleQuery.isFetching || Boolean(originalScheduleQuery.error))) ||
      originalScheduleRows.length === 0 ||
      loan.principal_minor > originalRemainingOutstanding);
  const scheduleBlocksPublish = loanScheduleBlocks || originalScheduleBlocks;
  const succeed = (message: string) => {
    setSuccess(message);
    onChanged();
  };
  const publish = useV1LoansAdminLoansPublishCreate({
    mutation: { onSuccess: () => succeed("The loan is now published on the primary market.") }
  });
  const cancelFunding = useV1MarketplacePrimaryAdminLoansCancelFundingCreate({
    mutation: { onSuccess: () => succeed("Funding cancellation was submitted.") }
  });
  const expiryScan = useV1MarketplacePrimaryAdminLoansExpiryScanCreate({
    mutation: {
      onSuccess: (data) => {
        succeed(
          `Funding resolution closed ${data.closed_count ?? 0}, cancelled ${data.cancelled_count}, failed ${data.failed_count ?? 0}, and skipped ${data.skipped_count}.`
        );
      }
    }
  });
  const releaseOrder = useV1MarketplacePrimaryAdminOrdersReleaseBalanceCreate({
    mutation: { onSuccess: () => succeed("The order's reserved balance was released.") }
  });
  const recordRecovery = useV1ServicingAdminRecoveriesCreate({
    mutation: { onSuccess: () => succeed("The recovery payment was distributed to lenders.") }
  });

  useEffect(() => {
    if (action !== "publish" || !loan.is_refinancing || originalScheduleRows.length === 0) return;
    const scheduleKey = `${loan.id}:${originalScheduleRows
      .map((row) => `${row.installment_number}:${row.due_date}:${row.paid_before_publication ? 1 : 0}`)
      .join("|")}`;
    if (originalPaidInitializedFor === scheduleKey) return;
    setPrePublicationPaidNumbers(
      originalScheduleRows.filter((row) => row.paid_before_publication).map((row) => row.installment_number)
    );
    setOriginalPaidInitializedFor(scheduleKey);
  }, [action, loan.id, loan.is_refinancing, originalPaidInitializedFor, originalScheduleRows]);

  // The backend owns the allocation. The UI previews the same fixed order after
  // external costs, third-party costs, and Garanta's recovery fee are deducted.
  const recGrossMinor = intValue(recGross);
  const recExternalMinor = intValue(recExternalCosts);
  const recThirdPartyMinor = intValue(recThirdPartyCosts);
  const recNetReceivedMinor = recGrossMinor - recExternalMinor;
  const recFeeBaseMinor = recNetReceivedMinor - recThirdPartyMinor;
  const recFeeMinor = recFeeApplied ? Math.round((recFeeBaseMinor * intValue(recFeeBps)) / 10000) : 0;
  const recNetAvailableMinor = recFeeBaseMinor - recFeeMinor;
  const recPenaltyDueMinor = intValue(recDefaultInterestDue) + intValue(recPenaltiesDue);
  const recPenaltyAppliedMinor = Math.min(Math.max(recNetAvailableMinor, 0), recPenaltyDueMinor);
  const recAfterPenaltyMinor = Math.max(recNetAvailableMinor - recPenaltyAppliedMinor, 0);
  const recInterestAppliedMinor = Math.min(
    recAfterPenaltyMinor,
    intValue(recContractualInterestDue)
  );
  const recProjectedPrincipalMinor = Math.max(recAfterPenaltyMinor - recInterestAppliedMinor, 0);
  const recCanSubmit = recNetAvailableMinor > 0;

  const available = MANAGE_LOAN_ACTIONS.filter((item) => item.statuses.includes(loan.status));
  const active = MANAGE_LOAN_ACTIONS.find((item) => item.id === action) ?? null;
  const anyError =
    publish.error || cancelFunding.error || expiryScan.error || releaseOrder.error || recordRecovery.error;

  function choose(id: ManageLoanActionId) {
    setPreview(null);
    setSuccess(undefined);
    setPublishStep("original");
    setAction(id);
  }

  function togglePrePublicationPaidInstallment(installmentNumber: number) {
    const pastNumbers = originalScheduleRows
      .filter((row) => isPastBusinessDate(row.due_date))
      .map((row) => row.installment_number)
      .sort((a, b) => a - b);
    setPrePublicationPaidNumbers((current) => {
      if (current.includes(installmentNumber)) {
        return pastNumbers.filter((number) => number < installmentNumber);
      }
      return pastNumbers.filter((number) => number <= installmentNumber);
    });
  }

  function publishLoan() {
    if (isFixturePreview) {
      setPreview(`Loan ${loanId} would be published.`);
      return;
    }
    publish.mutate({
      loanId,
      data: loan.is_refinancing
        ? { note, pre_publication_paid_installment_numbers: prePublicationPaidNumbers }
        : { note }
    });
  }

  function cancelLoan() {
    const data: PrimaryLoanCancellationRequest = {
      reason: cancelReason,
      investor_message: cancelInvestorMessage,
      idempotency_key: idempotencyKey("cancel-funding")
    };
    if (isFixturePreview) {
      setPreview(`Funding cancellation would run for ${loanId}.`);
      return;
    }
    cancelFunding.mutate({ loanId, data });
  }

  function scanExpiredCampaigns() {
    const data: PrimaryLoanExpiryScanRequest = {
      as_of_date: expiryAsOfDate,
      loan_ids: scanSelectedOnly ? [loanId] : undefined,
      reason: expiryReason || undefined,
      investor_message: expiryInvestorMessage || undefined,
      idempotency_key: idempotencyKey("expiry-scan")
    };
    if (isFixturePreview) {
      setPreview(
        scanSelectedOnly
          ? `Expiry scan would evaluate selected loan ${loanId}.`
          : "Expiry scan would evaluate all expired published campaigns."
      );
      return;
    }
    expiryScan.mutate({ data });
  }

  function recordRecoveryPayment() {
    const data: LoanRecoveryPaymentRecordRequest = {
      loan_id: loanId,
      gross_recovered_minor: recGrossMinor,
      externally_deducted_costs_minor: recExternalMinor,
      third_party_costs_from_received_minor: recThirdPartyMinor,
      recovery_fee_applied: recFeeApplied,
      recovery_fee_bps: recFeeApplied ? intValue(recFeeBps) : 0,
      contractual_interest_due_minor: intValue(recContractualInterestDue),
      default_interest_due_minor: intValue(recDefaultInterestDue),
      penalties_due_minor: intValue(recPenaltiesDue),
      booking_date: recBookingDate,
      value_date: recValueDate,
      collection_account_identifier: defaultCollectionAccount,
      payer_name: recPayerName,
      idempotency_key: idempotencyKey("recovery")
    };
    if (isFixturePreview) {
      setPreview(`Recovery payment of ${recGrossMinor} minor units would be distributed for ${loanId}.`);
      return;
    }
    recordRecovery.mutate({ data });
  }

  function releaseBalance() {
    const data: PrimaryInvestmentOrderReleaseRequest = {
      reason: releaseReason,
      idempotency_key: idempotencyKey("release-order")
    };
    if (isFixturePreview) {
      setPreview(`Order ${orderId || "selected order"} balance would be released.`);
      return;
    }
    releaseOrder.mutate({ orderId, data });
  }

  return (
    <Modal title={`Manage loan - ${loan.title}`} wide xwide={action === "publish"} onClose={onClose}>
      <div className="admin-action-form">
        <div className="admin-context-bar">
          <Chip tone={statusTone(loan.status)}>{labelize(loan.status)}</Chip>
          <span>Funding deadline {loan.funding_deadline ? formatDate(loan.funding_deadline) : "-"}</span>
          <span>
            Committed <Money amountMinor={loan.committed_principal_minor} currency={loan.currency} /> /{" "}
            financeable <Money amountMinor={loan.principal_minor} currency={loan.currency} />
          </span>
          {loan.is_refinancing ? (
            <span>Original <Money amountMinor={loan.original_principal_minor} currency={loan.currency} /></span>
          ) : null}
          <code>{loanId}</code>
        </div>

        {active === null ? (
          available.length > 0 ? (
            <div className="admin-manage-menu">
              <p className="muted admin-manage-hint">
                Choose the action to apply to this loan. Only actions valid for its current status are listed.
              </p>
              {available.map((item) => (
                <button className="admin-manage-option" key={item.id} onClick={() => choose(item.id)} type="button">
                  <span className="admin-manage-option-title">
                    {item.title}
                    {item.danger ? <Chip tone="warn">Confirmation required</Chip> : null}
                  </span>
                  <span className="admin-manage-option-desc">{item.description}</span>
                </button>
              ))}
            </div>
          ) : (
            <Empty icon="docs" title="No manage actions for this status">
              {labelize(loan.status)} loans have no manage operations. Status scans and risk notes live in the
              Servicing operations panel below the loan table.
            </Empty>
          )
        ) : (
          <>
            <div className="admin-manage-step">
              <Button onClick={() => setAction(null)} size="sm" variant="ghost">
                &#8592; All actions
              </Button>
              <strong>{active.title}</strong>
            </div>

            {action === "publish" && !loan.is_refinancing ? (
              <>
                <LoanScheduleReadonlyReview
                  error={scheduleQuery.error}
                  loading={loanScheduleLoading}
                  loan={loan}
                  rows={scheduleRows}
                />
                <TextAreaInput label="Publish note" onChange={setNote} value={note} />
                <Button disabled={publish.isPending || scheduleBlocksPublish} onClick={publishLoan} variant="primary">
                  Publish loan after schedule review
                </Button>
              </>
            ) : null}

            {action === "publish" && loan.is_refinancing ? (
              <>
                <div className="row gap-8 wrap" role="tablist">
                  <Button
                    aria-selected={publishStep === "original"}
                    onClick={() => setPublishStep("original")}
                    role="tab"
                    size="sm"
                    variant={publishStep === "original" ? "primary" : "ghost"}
                  >
                    1. Original loan schedule
                  </Button>
                  <Button
                    aria-selected={publishStep === "loan"}
                    onClick={() => setPublishStep("loan")}
                    role="tab"
                    size="sm"
                    variant={publishStep === "loan" ? "primary" : "ghost"}
                  >
                    2. Loan schedule
                  </Button>
                </div>
                {publishStep === "original" ? (
                  <>
                    <OriginalScheduleReview
                      error={originalScheduleQuery.error}
                      loading={originalScheduleLoading}
                      loan={loan}
                      onTogglePaidInstallment={togglePrePublicationPaidInstallment}
                      paidInstallmentNumbers={prePublicationPaidNumbers}
                      rows={originalScheduleRows}
                    />
                    <Button onClick={() => setPublishStep("loan")} variant="primary">
                      Continue to loan schedule
                    </Button>
                  </>
                ) : (
                  <>
                    <LoanScheduleReadonlyReview
                      error={scheduleQuery.error}
                      loading={loanScheduleLoading}
                      loan={loan}
                      rows={scheduleRows}
                    />
                    <TextAreaInput label="Publish note" onChange={setNote} value={note} />
                    <Button disabled={publish.isPending || scheduleBlocksPublish} onClick={publishLoan} variant="primary">
                      Publish loan after schedule review
                    </Button>
                  </>
                )}
              </>
            ) : null}

            {action === "cancel" ? (
              <>
                <TextAreaInput label="Cancellation reason" onChange={setCancelReason} required value={cancelReason} />
                <TextAreaInput
                  hint="Required when investors have pending or allocated orders. This is the operator-facing source for later notifications."
                  label="Cancellation investor message"
                  onChange={setCancelInvestorMessage}
                  value={cancelInvestorMessage}
                />
                <OperationConfirmButton
                  confirmLabel="Cancel funding"
                  description="Cancelling funding releases allocated reservations, closes pending intents as not invested, moves the loan to cancelled, and records immutable evidence. This is only valid before funding close."
                  details={[
                    { label: "Loan", value: loanId },
                    { label: "Status", value: labelize(loan.status) },
                    { label: "Reason", value: cancelReason },
                    { label: "Investor message", value: cancelInvestorMessage || "-" }
                  ]}
                  disabled={cancelFunding.isPending}
                  onConfirm={cancelLoan}
                  title="Confirm primary funding cancellation"
                  variant="danger"
                >
                  Cancel funding
                </OperationConfirmButton>
              </>
            ) : null}

            {action === "expiry" ? (
              <>
                <FieldGrid>
                  <TextInput label="Funding resolution as-of date" onChange={setExpiryAsOfDate} type="date" value={expiryAsOfDate} />
                  <Field hint="When enabled, only this loan is resolved. Disable to process every expired published campaign. Failed campaigns are retried only when selected explicitly.">
                    <label className="check-row">
                      <input checked={scanSelectedOnly} onChange={(event) => setScanSelectedOnly(event.target.checked)} type="checkbox" />
                      Scan this loan only
                    </label>
                  </Field>
                </FieldGrid>
                <TextAreaInput
                  hint="Optional. Used only if the campaign is below its minimum and must be cancelled."
                  label="Below-minimum cancellation reason"
                  onChange={setExpiryReason}
                  value={expiryReason}
                />
                <TextAreaInput
                  hint="Optional. Sent only if the campaign is below its minimum and investor reservations are refunded."
                  label="Below-minimum investor message"
                  onChange={setExpiryInvestorMessage}
                  value={expiryInvestorMessage}
                />
                <OperationConfirmButton
                  confirmLabel="Resolve funding deadline"
                  description="Under the loan lock, the server compares committed principal with the stored minimum. It closes at the subscribed amount when the minimum is met, cancels and refunds below it, or preserves reservations and opens an urgent task if resolution fails."
                  details={[
                    { label: "As-of date", value: expiryAsOfDate },
                    { label: "Scope", value: scanSelectedOnly ? `Selected loan ${loanId}` : "All expired published campaigns" }
                  ]}
                  disabled={expiryScan.isPending}
                  onConfirm={scanExpiredCampaigns}
                  title="Confirm funding deadline resolution"
                  variant="primary"
                >
                  Resolve funding deadline
                </OperationConfirmButton>
              </>
            ) : null}

            {action === "release" ? (
              <>
                <FieldGrid>
                  <PrimaryOrderLookupInput
                    onChange={setOrderId}
                    onQueryChange={setOrderQuery}
                    query={orderQuery}
                    value={orderId}
                  />
                  <TextInput label="Release reason" onChange={setReleaseReason} value={releaseReason} />
                </FieldGrid>
                <OperationConfirmButton
                  confirmLabel="Release balance"
                  description="Releasing an allocated order restores the original investor balance lots and reverses the loan-funding escrow reservation."
                  details={[
                    { label: "Order", value: orderId || "-" },
                    { label: "Reason", value: releaseReason }
                  ]}
                  disabled={releaseOrder.isPending || !orderId}
                  onConfirm={releaseBalance}
                  title="Confirm order balance release"
                  variant="danger"
                >
                  Release order balance
                </OperationConfirmButton>
              </>
            ) : null}

            {action === "disburse" ? <ManageDisbursementForm loan={loan} onDone={onChanged} /> : null}

            {action === "servicing" ? <ManageBorrowerRepaymentForm loan={loan} onDone={onChanged} /> : null}

            {action === "recovery" ? (
              <>
                <p className="muted admin-manage-hint">
                  Record funds recovered on this defaulted loan. The recovered amount, minus external and
                  third-party costs and the optional Garanta recovery fee, is allocated by the server in one
                  non-overridable order: penalty, contractual interest, then principal.
                </p>
                <FieldGrid>
                  <MoneyMinorInput currency={loan.currency} label="Gross recovered" onChange={setRecGross} value={recGross} />
                  <MoneyMinorInput currency={loan.currency} label="Externally deducted costs" onChange={setRecExternalCosts} value={recExternalCosts} />
                </FieldGrid>
                <FieldGrid>
                  <MoneyMinorInput currency={loan.currency} label="Third-party costs (from received)" onChange={setRecThirdPartyCosts} value={recThirdPartyCosts} />
                  <Field hint="Applies the configured Garanta recovery fee on the net-of-third-party base.">
                    <label className="check-row">
                      <input checked={recFeeApplied} onChange={(event) => setRecFeeApplied(event.target.checked)} type="checkbox" />
                      Apply Garanta recovery fee
                    </label>
                  </Field>
                </FieldGrid>
                {recFeeApplied ? (
                  <TextInput hint="Basis points, e.g. 500 = 5%." label="Recovery fee bps" onChange={setRecFeeBps} value={recFeeBps} />
                ) : null}
                <div className="admin-context-bar admin-recovery-summary">
                  <span>Net received <Money amountMinor={recNetReceivedMinor} currency={loan.currency} /></span>
                  <span>Fee <Money amountMinor={recFeeMinor} currency={loan.currency} /></span>
                  <span>
                    Net to distribute <strong><Money amountMinor={recNetAvailableMinor} currency={loan.currency} /></strong>
                  </span>
                </div>
                <FieldGrid>
                  <MoneyMinorInput currency={loan.currency} label="Outstanding default/penalty interest" onChange={setRecDefaultInterestDue} value={recDefaultInterestDue} />
                  <MoneyMinorInput currency={loan.currency} label="Outstanding other penalties" onChange={setRecPenaltiesDue} value={recPenaltiesDue} />
                </FieldGrid>
                <MoneyMinorInput currency={loan.currency} label="Outstanding contractual interest" onChange={setRecContractualInterestDue} value={recContractualInterestDue} />
                <div className="admin-context-bar admin-recovery-summary">
                  <span>1. Costs and recovery fee <Money amountMinor={Math.max(recGrossMinor - recNetAvailableMinor, 0)} currency={loan.currency} /></span>
                  <span>2. Penalty <Money amountMinor={recPenaltyAppliedMinor} currency={loan.currency} /></span>
                  <span>3. Interest <Money amountMinor={recInterestAppliedMinor} currency={loan.currency} /></span>
                  <span>4. Principal <strong><Money amountMinor={recProjectedPrincipalMinor} currency={loan.currency} /></strong></span>
                </div>
                <p className="muted admin-manage-hint">
                  Enter evidence-backed amounts currently due. Principal is derived from active holdings and
                  receives only the remainder after every higher tier is satisfied. The backend rejects any
                  recovery larger than the total outstanding obligations.
                </p>
                <FieldGrid>
                  <TextInput label="Booking date" onChange={setRecBookingDate} type="date" value={recBookingDate} />
                  <TextInput label="Value date" onChange={setRecValueDate} type="date" value={recValueDate} />
                </FieldGrid>
                <TextInput label="Payer name" onChange={setRecPayerName} value={recPayerName} />
                <OperationConfirmButton
                  confirmLabel="Record recovery"
                  description="Recording a recovery credits affected investor balance lots via the recovery waterfall, reduces current holding principal, and posts Garanta recovery-fee revenue. Recovery is only valid on a defaulted loan."
                  details={[
                    { label: "Loan", value: loanId },
                    { label: "Gross recovered", value: `${recGrossMinor} minor units` },
                    { label: "Net to distribute", value: `${recNetAvailableMinor} minor units` },
                    { label: "Penalty applied first", value: `${recPenaltyAppliedMinor} minor units` },
                    { label: "Interest applied next", value: `${recInterestAppliedMinor} minor units` },
                    { label: "Projected principal", value: `${recProjectedPrincipalMinor} minor units` },
                    { label: "Fee applied", value: recFeeApplied ? `Yes (${intValue(recFeeBps)} bps)` : "No" }
                  ]}
                  disabled={recordRecovery.isPending || !recCanSubmit}
                  onConfirm={recordRecoveryPayment}
                  title="Confirm recovery payment"
                  variant="danger"
                >
                  Record recovery
                </OperationConfirmButton>
              </>
            ) : null}
          </>
        )}

        {anyError ? <Banner tone="bad" title="Marketplace operation failed">{errorMessage(anyError)}</Banner> : null}
        {preview ? <Banner tone="info" title="Preview action recorded">{preview}</Banner> : null}
        {success ? <Banner tone="ok" title="Marketplace operation submitted">{success}</Banner> : null}
      </div>
    </Modal>
  );
}

function ManageDisbursementForm({ loan, onDone }: { loan: Loan; onDone: () => void }) {
  const defaultFeeMinor = Math.round((loan.principal_minor * loan.borrower_success_fee_bps) / 10000);
  const defaultAmountMinor = loan.principal_minor - defaultFeeMinor;
  const [override, setOverride] = useState(false);
  const [amountMinor, setAmountMinor] = useState(String(defaultAmountMinor));
  const [feeMinor, setFeeMinor] = useState(String(defaultFeeMinor));
  const [overrideNote, setOverrideNote] = useState("");
  const [payeeName, setPayeeName] = useState(adminFormDefaults.borrowerName);
  const [payeeAccount, setPayeeAccount] = useState(adminFormDefaults.borrowerPayeeAccount);
  const [bookingDate, setBookingDate] = useState(today);
  const [valueDate, setValueDate] = useState(today);
  const [bankReference, setBankReference] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const [evidenceReference, setEvidenceReference] = useState("");
  const [notes, setNotes] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1LedgerAdminBorrowerDisbursementsCreate({
    mutation: {
      onSuccess: () => {
        setSuccess("Borrower disbursement payable was cleared against collection cash.");
        onDone();
      }
    }
  });

  const amount = intValue(amountMinor);
  const fee = intValue(feeMinor);
  const feeOutOfRange = fee < 0 || fee * 10 > loan.principal_minor;
  const amountAndFeeTotal = amount + fee;
  const amountFeeMismatch = amountAndFeeTotal !== loan.principal_minor;
  const overrideNoteMissing = override && !overrideNote.trim();
  const blocked = feeOutOfRange || amountFeeMismatch || overrideNoteMissing || !payeeName.trim() || !payeeAccount.trim();

  function toggleOverride(checked: boolean) {
    setOverride(checked);
    if (!checked) {
      setAmountMinor(String(defaultAmountMinor));
      setFeeMinor(String(defaultFeeMinor));
      setOverrideNote("");
    }
  }

  function submit() {
    const data: BorrowerDisbursementFinalizeRequest = {
      loan_id: loan.id,
      borrower_id: loan.borrower_id ?? "",
      amount_minor: amount,
      fee_minor: fee,
      currency: loan.currency,
      booking_date: bookingDate,
      value_date: valueDate,
      collection_account_identifier: defaultCollectionAccount,
      payee_name: payeeName,
      payee_account_identifier: payeeAccount,
      override_note: override ? overrideNote : undefined,
      bank_reference: bankReference || undefined,
      payment_reference: paymentReference || undefined,
      evidence_reference: evidenceReference || undefined,
      admin_notes: notes || undefined,
      idempotency_key: idempotencyKey("borrower-disbursement")
    };
    if (isFixturePreview) {
      setPreview(
        `Borrower disbursement ${formatMoneyMinor(amount, loan.currency)} ${loan.currency} with fee ${formatMoneyMinor(fee, loan.currency)} ${loan.currency} would be finalized for ${loan.id}.`
      );
      return;
    }
    mutation.mutate({ data });
  }

  return (
    <>
      <p className="muted admin-manage-hint">
        Record the external payout of this funded loan to the borrower. Amount and BANXUM fee default to the
        contractual values (fee = principal &times; success fee bps; amount = principal &minus; fee) and can only be
        changed with an override note.
      </p>
      <div className="admin-context-bar">
        <span>Financeable <Money amountMinor={loan.principal_minor} currency={loan.currency} /></span>
        <span>Success fee {formatRateBps(loan.borrower_success_fee_bps)}</span>
        <span>Default fee <Money amountMinor={defaultFeeMinor} currency={loan.currency} /></span>
        <span>Default payout <Money amountMinor={defaultAmountMinor} currency={loan.currency} /></span>
      </div>
      <FieldGrid>
        <MoneyMinorInput
          currency={loan.currency}
          label="Disbursement amount minor units"
          onChange={setAmountMinor}
          readOnly={!override}
          required
          value={amountMinor}
        />
        <MoneyMinorInput
          currency={loan.currency}
          label="BANXUM fee minor units"
          onChange={setFeeMinor}
          readOnly={!override}
          required
          value={feeMinor}
        />
        <TextInput label="Booking date" onChange={setBookingDate} required type="date" value={bookingDate} />
        <TextInput label="Value date" onChange={setValueDate} required type="date" value={valueDate} />
        <TextInput label="Payee name" onChange={setPayeeName} required value={payeeName} />
        <TextInput label="Payee account" onChange={setPayeeAccount} required value={payeeAccount} />
        <TextInput label="Bank reference" onChange={setBankReference} value={bankReference} />
        <TextInput label="Payment reference" onChange={setPaymentReference} value={paymentReference} />
        <TextInput label="Evidence reference" onChange={setEvidenceReference} value={evidenceReference} />
      </FieldGrid>
      <label className="check-row">
        <input checked={override} onChange={(event) => toggleOverride(event.target.checked)} type="checkbox" />
        Override amounts (requires note).
      </label>
      {override ? (
        <TextAreaInput
          hint="Required when the amount or fee differs from the contractual defaults."
          label="Override explanation note"
          onChange={setOverrideNote}
          required
          value={overrideNote}
        />
      ) : null}
      <TextAreaInput label="Admin notes" onChange={setNotes} value={notes} />
      {feeOutOfRange ? (
        <Banner tone="bad" title="Fee out of range">
          The BANXUM fee must be between 0 and 10% of the financeable principal.
        </Banner>
      ) : null}
      {!feeOutOfRange && amountFeeMismatch ? (
        <Banner tone="bad" title="Amount plus fee must clear payable">
          The disbursement amount plus the BANXUM fee must equal the financeable principal. Adjust one of the
          values so the borrower payable clears with no residual balance.
        </Banner>
      ) : null}
      {overrideNoteMissing ? (
        <Banner tone="warn" title="Override note required">
          Explain why the disbursement amount or fee differs from the contractual defaults.
        </Banner>
      ) : null}
      <OperationConfirmButton
        confirmLabel="Finalize disbursement"
        description="Finalizing the disbursement clears the borrower payable against collection cash and records the BANXUM success fee. This declares an already-executed external bank payout."
        details={[
          { label: "Loan", value: loan.id },
          { label: "Amount", value: <Money amountMinor={amount} currency={loan.currency} /> },
          { label: "BANXUM fee", value: <Money amountMinor={fee} currency={loan.currency} /> },
          { label: "Payee", value: payeeName || "-" },
          { label: "Override", value: override ? overrideNote || "-" : "No" }
        ]}
        disabled={mutation.isPending || blocked}
        onConfirm={submit}
        title="Confirm borrower disbursement"
        variant="primary"
      >
        Finalize disbursement
      </OperationConfirmButton>
      {mutation.error ? <Banner tone="bad" title="Disbursement failed">{errorMessage(mutation.error)}</Banner> : null}
      {preview ? <Banner tone="info" title="Preview action recorded">{preview}</Banner> : null}
      {success ? <Banner tone="ok" title="Disbursement submitted">{success}</Banner> : null}
    </>
  );
}

function AdvanceScheduleTable({ rows, currency }: { rows: AdvanceRepaymentScheduleRow[]; currency: string }) {
  const totals = rows.reduce(
    (acc, row) => {
      acc.principal += row.principal_minor;
      acc.interest += row.interest_minor;
      acc.total += row.total_minor;
      return acc;
    },
    { principal: 0, interest: 0, total: 0 }
  );
  return (
    <div className="table-wrap admin-table-wrap">
      <table className="admin-table admin-schedule-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Due date</th>
            <th className="num">Principal</th>
            <th className="num">Interest</th>
            <th className="num">Instalment</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.installment_number}>
              <td>{row.installment_number}</td>
              <td>{formatDate(row.due_date)}</td>
              <td className="num"><Money amountMinor={row.principal_minor} currency={currency} /></td>
              <td className="num"><Money amountMinor={row.interest_minor} currency={currency} /></td>
              <td className="num"><Money amountMinor={row.total_minor} currency={currency} /></td>
            </tr>
          ))}
        </tbody>
        <tfoot className="schedule-totals">
          <tr>
            <th colSpan={2}>Totals</th>
            <th className="num"><Money amountMinor={totals.principal} currency={currency} /></th>
            <th className="num"><Money amountMinor={totals.interest} currency={currency} /></th>
            <th className="num"><Money amountMinor={totals.total} currency={currency} /></th>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

function ManageBorrowerRepaymentForm({ loan, onDone }: { loan: Loan; onDone: () => void }) {
  const scheduleQuery = useV1LoansAdminLoansScheduleList(loan.id, {
    query: { enabled: !isFixturePreview, staleTime: 0 }
  });
  const fixtureRows = useMemo(() => previewScheduleRows(loan), [loan]);
  const scheduleRows = useMemo(
    () => (isFixturePreview ? fixtureRows : scheduleQuery.data ?? []),
    [fixtureRows, scheduleQuery.data]
  );
  const nextInstallment = scheduleRows.find((row) => (row.outstanding_total_minor ?? row.total_minor) > 0);
  const defaultAmountMinor = nextInstallment?.outstanding_total_minor ?? nextInstallment?.total_minor ?? 0;
  const [advance, setAdvance] = useState(false);
  const [advanceAmountMinor, setAdvanceAmountMinor] = useState("");
  const [bankDate, setBankDate] = useState(today);
  const [payerName, setPayerName] = useState(adminFormDefaults.borrowerName);
  const [payerAccount, setPayerAccount] = useState("");
  const [bookingDate, setBookingDate] = useState(today);
  const [valueDate, setValueDate] = useState(today);
  const [bankReference, setBankReference] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const [evidenceReference, setEvidenceReference] = useState("");
  const [notes, setNotes] = useState("");
  const [earlyRegularAcknowledged, setEarlyRegularAcknowledged] = useState(false);
  const [advancePlan, setAdvancePlan] = useState<BorrowerRepaymentAdvancePreviewResponse | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const repayment = useV1ServicingAdminBorrowerRepaymentsCreate({
    mutation: {
      onSuccess: () => {
        setAdvancePlan(null);
        setSuccess("Borrower repayment was recorded and distributed to lenders.");
        refetchLive(scheduleQuery.refetch);
        onDone();
      }
    }
  });
  const advancePreview = useV1ServicingAdminBorrowerRepaymentsAdvancePreviewCreate({
    mutation: { onSuccess: (plan) => setAdvancePlan(plan) }
  });

  const amountMinorValue = advance ? intValue(advanceAmountMinor) : defaultAmountMinor;
  const regularPaymentDaysEarly = nextInstallment
    ? dateDifferenceDays(nextInstallment.due_date, valueDate)
    : 0;
  const requiresEarlyRegularAcknowledgement = !advance && regularPaymentDaysEarly > 1;
  let cumulativePrincipal = 0;
  const scheduleTotals = scheduleRows.reduce(
    (acc, row) => {
      acc.principal += row.principal_minor;
      acc.interest += row.interest_minor;
      acc.total += row.total_minor;
      acc.remainingDue += row.outstanding_total_minor ?? row.total_minor;
      return acc;
    },
    { principal: 0, interest: 0, total: 0, remainingDue: 0 }
  );
  const scheduledPrincipal = scheduleTotals.principal;

  function toggleAdvance(checked: boolean) {
    setAdvance(checked);
    setAdvancePlan(null);
    if (checked) setAdvanceAmountMinor(String(defaultAmountMinor));
  }

  function buildRecordRequest(inAdvance: boolean): BorrowerRepaymentRecordRequest {
    return {
      loan_id: loan.id,
      amount_minor: amountMinorValue,
      booking_date: bookingDate,
      value_date: valueDate,
      payer_name: payerName,
      payer_account_identifier: payerAccount || undefined,
      bank_reference: bankReference || undefined,
      payment_reference: paymentReference || undefined,
      evidence_reference: evidenceReference || undefined,
      admin_notes: notes || undefined,
      repayment_in_advance: inAdvance,
      borrower_repayment_bank_date: inAdvance ? bankDate : undefined,
      early_regular_payment_acknowledged:
        !inAdvance && requiresEarlyRegularAcknowledgement
          ? earlyRegularAcknowledged
          : false,
      idempotency_key: idempotencyKey("borrower-repayment")
    };
  }

  function recordRegular() {
    if (isFixturePreview) {
      setPreview(
        `Borrower repayment of ${formatMoneyMinor(amountMinorValue, loan.currency)} ${loan.currency} would be recorded against the next due installment of ${loan.id}.`
      );
      return;
    }
    repayment.mutate({ data: buildRecordRequest(false) });
  }

  function requestAdvancePreview() {
    if (isFixturePreview) {
      setPreview(
        `Advance repayment of ${formatMoneyMinor(amountMinorValue, loan.currency)} ${loan.currency} with bank date ${bankDate} would be previewed for ${loan.id}.`
      );
      return;
    }
    advancePreview.mutate({
      data: { loan_id: loan.id, amount_minor: amountMinorValue, borrower_repayment_bank_date: bankDate }
    });
  }

  function confirmAdvance() {
    repayment.mutate({ data: buildRecordRequest(true) });
  }

  return (
    <>
      <p className="muted admin-manage-hint">
        Regular repayments must equal the next outstanding installment exactly; the amount is fixed from the
        current schedule and recorded repayment history. Use repayment in advance for a different amount - the
        backend recomputes interest to the bank date and reamortizes the remaining schedule.
      </p>
      <div className="admin-schedule-review">
        <div className="admin-subsection-header">
          <div>
            <h4>Current repayment schedule</h4>
            <p className="muted">Server-generated schedule, version {loan.schedule_version}.</p>
          </div>
          <Button icon="refresh" onClick={() => refetchLive(scheduleQuery.refetch)} size="sm">Refresh</Button>
        </div>
        {!isFixturePreview && scheduleQuery.isFetching && scheduleRows.length === 0 ? (
          <Banner tone="info" title="Loading schedule">Fetching the current server-generated schedule.</Banner>
        ) : null}
        {scheduleQuery.error ? <Banner tone="bad" title="Schedule unavailable">{errorMessage(scheduleQuery.error)}</Banner> : null}
        {scheduleRows.length ? (
          <div className="table-wrap admin-table-wrap">
            <table className="admin-table admin-schedule-table">
              <thead>
	                <tr>
	                  <th>Entry</th>
	                  <th>Date</th>
	                  <th className="num">Principal</th>
	                  <th className="num">Interest</th>
	                  <th className="num">Instalment</th>
	                  <th className="num">Remaining due</th>
	                  <th className="num">Outstanding after</th>
	                </tr>
              </thead>
              <tbody>
                {scheduleRows.map((row) => {
                  cumulativePrincipal += row.principal_minor;
                  const outstandingAfter = Math.max(0, scheduledPrincipal - cumulativePrincipal);
	                  const isPayment = row.row_type === "repayment_event";
	                  return (
	                    <tr key={row.id}>
	                      <td>
	                        {row.label}
	                        {row.is_paid ? <> <Chip tone="ok">{row.status === "paid_in_advance" ? "Paid in advance" : "Paid"}</Chip></> : null}
	                        {!row.is_paid && isPastBusinessDate(row.due_date) ? <> <Chip tone="warn">Due</Chip></> : null}
	                      </td>
	                      <td>{formatDate(isPayment && row.payment_date ? row.payment_date : row.due_date)}</td>
	                      <td className="num"><Money amountMinor={row.principal_minor} currency={loan.currency} /></td>
	                      <td className="num"><Money amountMinor={row.interest_minor} currency={loan.currency} /></td>
	                      <td className="num"><Money amountMinor={row.total_minor} currency={loan.currency} /></td>
	                      <td className="num">
	                        <Money amountMinor={row.outstanding_total_minor ?? row.total_minor} currency={loan.currency} />
	                      </td>
	                      <td className="num"><Money amountMinor={outstandingAfter} currency={loan.currency} /></td>
	                    </tr>
	                  );
                })}
              </tbody>
              <tfoot className="schedule-totals">
                <tr>
                  <th colSpan={2}>Totals</th>
                  <th className="num"><Money amountMinor={scheduleTotals.principal} currency={loan.currency} /></th>
                  <th className="num"><Money amountMinor={scheduleTotals.interest} currency={loan.currency} /></th>
                  <th className="num"><Money amountMinor={scheduleTotals.total} currency={loan.currency} /></th>
                  <th className="num"><Money amountMinor={scheduleTotals.remainingDue} currency={loan.currency} /></th>
                  <th className="num">-</th>
                </tr>
              </tfoot>
            </table>
          </div>
        ) : null}
      </div>
      <FieldGrid>
        <MoneyMinorInput
	          currency={loan.currency}
	          hint={advance ? undefined : "Fixed to the next outstanding installment total from the current schedule."}
          label="Amount minor units"
          onChange={setAdvanceAmountMinor}
          readOnly={!advance}
          required
          value={advance ? advanceAmountMinor : String(defaultAmountMinor)}
        />
        <TextInput label="Payer name" onChange={setPayerName} required value={payerName} />
        <TextInput label="Payer account" onChange={setPayerAccount} value={payerAccount} />
        <TextInput label="Booking date" onChange={setBookingDate} required type="date" value={bookingDate} />
        <TextInput label="Value date" onChange={setValueDate} required type="date" value={valueDate} />
        <TextInput label="Bank reference" onChange={setBankReference} value={bankReference} />
        <TextInput label="Payment reference" onChange={setPaymentReference} value={paymentReference} />
        <TextInput label="Evidence reference" onChange={setEvidenceReference} value={evidenceReference} />
      </FieldGrid>
      <TextAreaInput label="Admin notes" onChange={setNotes} value={notes} />
      <label className="check-row">
        <input checked={advance} onChange={(event) => toggleAdvance(event.target.checked)} type="checkbox" />
        Repayment in advance (different amount).
      </label>
      {requiresEarlyRegularAcknowledgement ? (
        <Banner tone="warn" title={`Regular installment is ${regularPaymentDaysEarly} days early`}>
          A regular repayment collects the installment's full contractual interest. If this is a principal
          repayment in advance, select "Repayment in advance" so interest is limited to the exact elapsed days.
          <label className="check-row" style={{ marginTop: 10 }}>
            <input
              checked={earlyRegularAcknowledged}
              onChange={(event) => setEarlyRegularAcknowledged(event.target.checked)}
              type="checkbox"
            />
            I confirm this is the full timely installment and the full scheduled interest should be applied.
          </label>
        </Banner>
      ) : null}
      {advance ? (
        <FieldGrid>
          <TextInput
            hint="Date the borrower's payment reached the bank. Interest is recomputed to this date."
            label="Borrower repayment bank date"
            onChange={setBankDate}
            required
            type="date"
            value={bankDate}
          />
        </FieldGrid>
      ) : null}
      <div className="row gap-8 wrap">
        {advance ? (
          <Button
            disabled={advancePreview.isPending || amountMinorValue <= 0 || !bankDate || !payerName.trim()}
            onClick={requestAdvancePreview}
            variant="primary"
          >
            Preview new schedule
          </Button>
        ) : (
          <Button
            disabled={repayment.isPending || amountMinorValue <= 0 || !payerName.trim() || (requiresEarlyRegularAcknowledgement && !earlyRegularAcknowledged)}
            onClick={recordRegular}
            variant="primary"
          >
            Record repayment
          </Button>
        )}
      </div>
      {repayment.error ? <Banner tone="bad" title="Repayment failed">{errorMessage(repayment.error)}</Banner> : null}
      {advancePreview.error ? <Banner tone="bad" title="Advance preview failed">{errorMessage(advancePreview.error)}</Banner> : null}
      {preview ? <Banner tone="info" title="Preview action recorded">{preview}</Banner> : null}
      {success ? <Banner tone="ok" title="Repayment submitted">{success}</Banner> : null}
      {advancePlan ? (
        <Modal title="Confirm repayment in advance" wide onClose={() => setAdvancePlan(null)}>
          <div className="admin-action-form">
            <Banner tone="warn" title="Review before recording">
              Recording this advance repayment applies the interest breakdown below and replaces the remaining
              schedule with the reamortized version.
            </Banner>
            <div className="admin-detail-grid">
              <div className="admin-review-row">
                <span>Amount</span>
                <strong><Money amountMinor={advancePlan.amount_minor} currency={advancePlan.currency} /></strong>
              </div>
              <div className="admin-review-row">
                <span>Bank date</span>
                <strong>{formatDate(advancePlan.bank_date)}</strong>
              </div>
              <div className="admin-review-row">
                <span>Scheduled interest due</span>
                <strong><Money amountMinor={advancePlan.scheduled_interest_due_minor} currency={advancePlan.currency} /></strong>
              </div>
              <div className="admin-review-row">
                <span>Accrued interest</span>
                <strong><Money amountMinor={advancePlan.accrued_interest_minor} currency={advancePlan.currency} /></strong>
              </div>
              <div className="admin-review-row">
                <span>Interest accrual period</span>
                <strong>{formatDate(advancePlan.interest_accrual_start_date)} to {formatDate(advancePlan.interest_accrual_end_date)}</strong>
              </div>
              <div className="admin-review-row">
                <span>Accrued days (ACT/365)</span>
                <strong>{advancePlan.accrued_interest_days}</strong>
              </div>
              <div className="admin-review-row">
                <span>Interest applied</span>
                <strong><Money amountMinor={advancePlan.interest_applied_minor} currency={advancePlan.currency} /></strong>
              </div>
              <div className="admin-review-row">
                <span>Principal applied</span>
                <strong><Money amountMinor={advancePlan.principal_applied_minor} currency={advancePlan.currency} /></strong>
              </div>
              <div className="admin-review-row">
                <span>Outstanding before</span>
                <strong><Money amountMinor={advancePlan.outstanding_principal_before_minor} currency={advancePlan.currency} /></strong>
              </div>
              <div className="admin-review-row">
                <span>Outstanding after</span>
                <strong><Money amountMinor={advancePlan.outstanding_principal_after_minor} currency={advancePlan.currency} /></strong>
              </div>
            </div>
            <h4>Current schedule</h4>
            <AdvanceScheduleTable currency={advancePlan.currency} rows={advancePlan.old_schedule_rows} />
            <h4>New schedule after this payment</h4>
            <AdvanceScheduleTable currency={advancePlan.currency} rows={advancePlan.new_schedule_rows} />
            {repayment.error ? <Banner tone="bad" title="Repayment failed">{errorMessage(repayment.error)}</Banner> : null}
            <div className="modal-foot inline-foot">
              <Button onClick={() => setAdvancePlan(null)}>Cancel</Button>
              <Button disabled={repayment.isPending} onClick={confirmAdvance} variant="primary">
                Confirm and record payment
              </Button>
            </div>
          </div>
        </Modal>
      ) : null}
    </>
  );
}

function ServicingOpsForm({
  defaultLoanId,
  defaultLoanTitle
}: {
  defaultLoanId: string;
  defaultLoanTitle: string;
}) {
  const [loanId, setLoanId] = useState(defaultLoanId);
  const [loanQuery, setLoanQuery] = useState(defaultLoanId);
  const [asOfDate, setAsOfDate] = useState(today);
  const [riskBody, setRiskBody] = useState("Public servicing update for affected investors.");
  const [preview, setPreview] = useState<string | null>(null);
  const scan = useV1ServicingAdminStatusScanCreate();
  const riskNote = useV1ServicingAdminRiskNotesCreate();

  useEffect(() => {
    setLoanId(defaultLoanId);
    setLoanQuery(defaultLoanId);
  }, [defaultLoanId]);

  function submitScan() {
    const data: LoanServicingStatusScanRequest = { as_of_date: asOfDate, loan_ids: loanId ? [loanId] : undefined };
    if (isFixturePreview) {
      setPreview(`Servicing status scan would run for ${loanId || "all repayable loans"}.`);
      return;
    }
    scan.mutate({ data });
  }

  function submitRiskNote() {
    const data: LoanRiskNoteCreateRequest = {
      loan_id: loanId,
      visibility: VisibilityEnum.public,
      note_type: NoteTypeEnum.public_update,
      title: "Investor update",
      body: riskBody,
      idempotency_key: idempotencyKey("risk-note")
    };
    if (isFixturePreview) {
      setPreview(`Public risk note would be recorded for ${loanId}.`);
      return;
    }
    riskNote.mutate({ data });
  }

  return (
    <Card padded className="admin-wide-card">
      <h2>Servicing operations</h2>
      <div className="admin-action-form">
        <div className="admin-context-bar">
          <span>Selected loan</span>
          <strong>{defaultLoanTitle || "No loan selected"}</strong>
          <code>{loanId || "-"}</code>
        </div>
        <FieldGrid>
          <LoanLookupInput
            onChange={setLoanId}
            onQueryChange={setLoanQuery}
            query={loanQuery}
            required
            value={loanId}
          />
          <TextInput label="Status scan as-of date" onChange={setAsOfDate} type="date" value={asOfDate} />
        </FieldGrid>
        <div className="row gap-8 wrap">
          <Button disabled={scan.isPending} onClick={submitScan}>Run status scan</Button>
        </div>
        <TextAreaInput label="Risk note body" onChange={setRiskBody} value={riskBody} />
        <div className="row gap-8 wrap">
          <Button disabled={riskNote.isPending} onClick={submitRiskNote}>Publish public note</Button>
        </div>
        <p className="muted" style={{ fontSize: 11.5 }}>
          Borrower repayments are declared from the loan row: use <strong>Manage &rarr; Record borrower repayment</strong>.
          Recording a recovery payment for a defaulted loan is done via <strong>Manage &rarr; Record a recovery payment</strong>.
        </p>
        {scan.error || riskNote.error ? (
          <Banner tone="bad" title="Servicing action failed">
            {errorMessage(scan.error || riskNote.error)}
          </Banner>
        ) : null}
        {preview ? <Banner tone="info" title="Preview action recorded">{preview}</Banner> : null}
      </div>
    </Card>
  );
}

type ListingDecision = "approve" | "reject" | "remove";

function listingStatusTone(status: string): Tone {
  if (status === "active") return "ok";
  if (status === "approval_requested") return "warn";
  if (status === "sold") return "info";
  return "neutral";
}

function listingPriceLabel(row: AdminSecondaryMarketListingRow) {
  const bps = row.discount_premium_bps;
  if (bps === 0) return "At par";
  const pct = (Math.abs(bps) / 100).toFixed(2).replace(/\.?0+$/, "");
  return bps > 0 ? `+${pct}% premium` : `-${pct}% discount`;
}

function ListingDecisionModal({
  decision,
  listing,
  onClose,
  onDone
}: {
  decision: ListingDecision;
  listing: AdminSecondaryMarketListingRow;
  onClose: () => void;
  onDone: () => void;
}) {
  const [reason, setReason] = useState(
    decision === "approve"
      ? "Admin-reviewed non-standard listing disclosure."
      : decision === "reject"
        ? "Listing rejected after admin review."
        : "Listing removed for operational reasons."
  );
  const [disclosure, setDisclosure] = useState(
    "Loan is non-performing. Review public note and days-past-due before purchase."
  );
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const done = (message: string) => {
    setSuccess(message);
    onDone();
  };
  const approve = useV1MarketplaceSecondaryAdminListingsApproveCreate({
    mutation: { onSuccess: () => done("The listing is approved and visible to buyers with the disclosure note.") }
  });
  const reject = useV1MarketplaceSecondaryAdminListingsRejectCreate({
    mutation: { onSuccess: () => done("The listing was rejected and stays hidden from buyers.") }
  });
  const remove = useV1MarketplaceSecondaryAdminListingsRemoveCreate({
    mutation: { onSuccess: () => done("The listing was removed from buyer visibility.") }
  });
  const anyError = approve.error || reject.error || remove.error;
  const titles: Record<ListingDecision, string> = {
    approve: "Approve listing",
    reject: "Reject listing",
    remove: "Remove listing"
  };

  function submit() {
    if (isFixturePreview) {
      setPreview(`Listing ${listing.id} would be ${decision}d.`);
      return;
    }
    if (decision === "approve") {
      approve.mutate({
        listingId: listing.id,
        data: { reason, disclosure_note: disclosure, idempotency_key: idempotencyKey("sm-approve") }
      });
    } else if (decision === "reject") {
      reject.mutate({ listingId: listing.id, data: { reason, idempotency_key: idempotencyKey("sm-reject") } });
    } else {
      remove.mutate({ listingId: listing.id, data: { reason, idempotency_key: idempotencyKey("sm-remove") } });
    }
  }

  return (
    <Modal title={`${titles[decision]} - ${listing.loan_title}`} onClose={onClose}>
      <div className="admin-action-form">
        <div className="admin-context-bar">
          <Chip tone={listingStatusTone(listing.status)}>{labelize(listing.status)}</Chip>
          <span>{listing.seller_full_name || listing.seller_email}</span>
          <span>
            <Money amountMinor={listing.transfer_price_minor} currency={listing.currency} /> ({listingPriceLabel(listing)})
          </span>
          {listing.days_past_due > 0 ? <span>{listing.days_past_due} days past due</span> : null}
          <code>{listing.id}</code>
        </div>
        <TextAreaInput label="Reason" onChange={setReason} required value={reason} />
        {decision === "approve" ? (
          <TextAreaInput
            hint="Shown to buyers as the public disclosure for this non-standard listing."
            label="Buyer disclosure note"
            onChange={setDisclosure}
            required
            value={disclosure}
          />
        ) : null}
        <OperationConfirmButton
          confirmLabel={titles[decision]}
          description={
            decision === "approve"
              ? "Approving a non-standard listing makes it visible to eligible buyers with the provided disclosure note and additional acknowledgement."
              : decision === "reject"
                ? "Rejecting a listing keeps it hidden and records the admin decision in the audit trail."
                : "Removing a listing takes it out of buyer visibility and records the operational reason."
          }
          details={[
            { label: "Listing", value: listing.id },
            { label: "Loan", value: listing.loan_title },
            { label: "Reason", value: reason },
            ...(decision === "approve" ? [{ label: "Disclosure", value: disclosure }] : [])
          ]}
          disabled={approve.isPending || reject.isPending || remove.isPending}
          onConfirm={submit}
          title={`Confirm secondary listing ${decision}`}
          variant={decision === "approve" ? "primary" : "danger"}
        >
          {titles[decision]}
        </OperationConfirmButton>
        {anyError ? <Banner tone="bad" title="Listing action failed">{errorMessage(anyError)}</Banner> : null}
        {preview ? <Banner tone="info" title="Preview action recorded">{preview}</Banner> : null}
        {success ? <Banner tone="ok" title="Listing action submitted">{success}</Banner> : null}
      </div>
    </Modal>
  );
}

function SecondaryMarketApprovalsTable() {
  const [statusFilter, setStatusFilter] = useState("");
  const [decision, setDecision] = useState<{ listing: AdminSecondaryMarketListingRow; decision: ListingDecision } | null>(null);
  const listingsQuery = useAdminSecondaryListingsData({
    status: statusFilter || undefined,
    limit: 100
  });
  const listings = listingsQuery.data ?? [];

  return (
    <Card padded>
      <EntityTableHeader
        description="Every secondary-market listing, newest first. Non-standard listings wait here as 'Approval requested' until an admin approves them with a buyer disclosure note."
        title="Secondary-market approvals"
        filters={
          <select
            aria-label="Filter listings by status"
            className="select"
            onChange={(event) => setStatusFilter(event.target.value)}
            value={statusFilter}
          >
            <option value="">All statuses</option>
            <option value="approval_requested">Approval requested</option>
            <option value="active">Active</option>
            <option value="sold">Sold</option>
            <option value="rejected">Rejected</option>
            <option value="removed">Removed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        }
        action={<Button size="sm" onClick={() => refetchLive(listingsQuery.refetch)}>Refresh</Button>}
      />
      {listings.length > 0 ? (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Loan / listing</th>
                <th>Seller</th>
                <th>Price</th>
                <th>Loan status</th>
                <th>DPD</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {listings.map((row) => (
                <tr key={row.id}>
                  <td><strong>{row.loan_title}</strong><span className="mono muted">{row.id}</span></td>
                  <td>{row.seller_full_name || "-"}<span className="mono muted">{row.seller_email}</span></td>
                  <td>
                    <Money amountMinor={row.transfer_price_minor} currency={row.currency} />
                    <span className="muted" style={{ display: "block", fontSize: 11.5 }}>{listingPriceLabel(row)}</span>
                  </td>
                  <td><Chip tone={statusTone(row.loan_status)}>{labelize(row.loan_status)}</Chip></td>
                  <td>{row.days_past_due > 0 ? row.days_past_due : "-"}</td>
                  <td><Chip tone={listingStatusTone(row.status)}>{labelize(row.status)}</Chip></td>
                  <td>{formatDate(row.created_at)}</td>
                  <td>
                    <div className="row gap-8 wrap">
                      {row.status === "approval_requested" ? (
                        <>
                          <Button size="sm" variant="primary" onClick={() => setDecision({ listing: row, decision: "approve" })}>Approve</Button>
                          <Button size="sm" variant="danger" onClick={() => setDecision({ listing: row, decision: "reject" })}>Reject</Button>
                        </>
                      ) : row.status === "active" ? (
                        <Button size="sm" variant="danger" onClick={() => setDecision({ listing: row, decision: "remove" })}>Remove</Button>
                      ) : (
                        <span className="muted" style={{ fontSize: 12 }}>No actions</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty icon="docs" title="No listings">
          {statusFilter ? "No listings match this status filter." : "Secondary-market listings will appear here once investors list holdings."}
        </Empty>
      )}
      {decision ? (
        <ListingDecisionModal
          decision={decision.decision}
          listing={decision.listing}
          onClose={() => setDecision(null)}
          onDone={() => refetchLive(listingsQuery.refetch)}
        />
      ) : null}
    </Card>
  );
}

export function ReportsPanel() {
  const [reportType, setReportType] = useState<AdminReportType>(ReportTypeEnum.operational_subledger);
  const [outputFormat, setOutputFormat] = useState<ReportOutputFormat>(
    ReportGenerateRequestOutputFormatEnum.csv
  );
  const [redactionMode, setRedactionMode] = useState<ReportRedactionMode>(RedactionModeEnum.redacted);
  const [periodPreset, setPeriodPreset] = useState<ReportPeriodPreset>(PeriodPresetEnum.custom);
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(today);
  const [destinationNote, setDestinationNote] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const mutation = useV1ReportingAdminReportsCreate();
  const auditQuery = useAuditEventsData({ limit: 100 });
  const reportResponse = mutation.data;
  const reportPreview = useMemo(() => {
    if (!reportResponse) return "";
    if (reportResponse.content_encoding.toLowerCase().includes("base64")) {
      return `${reportResponse.content_type} artifact is base64 encoded. Use Download artifact to save the generated file.`;
    }
    return reportResponse.content.slice(0, 2000);
  }, [reportResponse]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: ReportGenerateRequest = {
      report_type: reportType,
      output_format: outputFormat,
      redaction_mode: redactionMode,
      period_preset: periodPreset,
      start_date: periodPreset === PeriodPresetEnum.custom ? startDate : undefined,
      end_date: periodPreset === PeriodPresetEnum.custom ? endDate : undefined,
      period_anchor_date: periodPreset === PeriodPresetEnum.custom ? undefined : endDate,
      destination_note: destinationNote
    };
    if (isFixturePreview) {
      setPreview(`${labelize(reportType)} ${outputFormat.toUpperCase()} would be generated in ${labelize(redactionMode)} mode.`);
      return;
    }
    mutation.mutate({ data });
  }

  return (
    <div className="admin-content">
      <PreviewNotice>Report output is not generated in preview. Live mode returns base64 CSV, PDF or ZIP content from the backend.</PreviewNotice>
      <section className="admin-two-col">
        <Card padded>
          <SectionHeader description="Generate accounting, tax, regulatory and operational exports on demand." title="Report generation" />
          <form className="admin-action-form" onSubmit={submit}>
            <FieldGrid>
              <SelectInput label="Report type" onChange={setReportType} options={Object.values(ReportTypeEnum)} value={reportType} />
              <SelectInput
                label="Output format"
                onChange={setOutputFormat}
                options={Object.values(ReportGenerateRequestOutputFormatEnum)}
                value={outputFormat}
              />
              <SelectInput label="Redaction mode" onChange={setRedactionMode} options={Object.values(RedactionModeEnum)} value={redactionMode} />
              <SelectInput label="Period preset" onChange={setPeriodPreset} options={Object.values(PeriodPresetEnum)} value={periodPreset} />
              <TextInput label="Start date" onChange={setStartDate} type="date" value={startDate} />
              <TextInput label="End / anchor date" onChange={setEndDate} type="date" value={endDate} />
            </FieldGrid>
            <TextAreaInput label="Destination note" onChange={setDestinationNote} value={destinationNote} />
            <ActionFooter
              mutation={mutation}
              previewMessage={preview}
              successMessage={mutation.data ? `${mutation.data.filename} generated with checksum ${mutation.data.report_run.content_sha256.slice(0, 12)}...` : undefined}
              submitLabel="Generate report"
            />
          </form>
          {reportResponse ? (
            <div className="admin-artifact-panel">
              <div className="admin-artifact-head">
                <div>
                  <h3>{reportResponse.filename}</h3>
                  <p>
                    {labelize(reportResponse.report_run.report_type)} · {reportResponse.report_run.row_count} rows · {reportResponse.content_type}
                  </p>
                </div>
                <Button icon="download" onClick={() => downloadReportArtifact(reportResponse)} variant="primary">
                  Download artifact
                </Button>
              </div>
              <div className="admin-detail-grid">
                <div className="admin-review-row">
                  <span>Checksum</span>
                  <strong className="mono">{reportResponse.report_run.content_sha256}</strong>
                </div>
                <div className="admin-review-row">
                  <span>Generated</span>
                  <strong>{formatDateTime(reportResponse.report_run.generated_at)}</strong>
                </div>
                <div className="admin-review-row">
                  <span>Encoding</span>
                  <strong>{reportResponse.content_encoding}</strong>
                </div>
              </div>
              <h3>Content preview</h3>
              <pre className="admin-json">{reportPreview}</pre>
              <h3>Manifest</h3>
              <JsonPreview value={reportResponse.manifest} />
            </div>
          ) : null}
        </Card>
        <Card padded>
          <SectionHeader
            action={<Button icon="refresh" onClick={() => refetchLive(auditQuery.refetch)} size="sm">Refresh</Button>}
            description="Recent platform audit reads for operational review."
            title="Audit event search"
          />
          {auditQuery.data?.length ? (
            <div className="table-wrap admin-table-wrap">
              <table className="admin-table admin-audit-table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Action</th>
                    <th>Actor</th>
                    <th>Target</th>
                  </tr>
                </thead>
                <tbody>
                  {auditQuery.data.map((event) => (
                    <tr key={event.id}>
                      <td>{formatDateTime(event.occurred_at)}</td>
                      <td>{event.action}</td>
                      <td><span className="mono">{event.actor_type}:{event.actor_id}</span></td>
                      <td><span className="mono">{event.target_type}:{event.target_id}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty icon="docs" title="No audit events returned">
              Use filters once the backend audit-log endpoint is live with production data.
            </Empty>
          )}
        </Card>
      </section>
    </div>
  );
}

export function SettingsPanel() {
  const [category, setCategory] = useState<DocumentCategory>(CategoryEnum.registration);
  const [templateSearch, setTemplateSearch] = useState("");
  const [showTemplateForm, setShowTemplateForm] = useState(false);
  const [defaultTemplateVersionId, setDefaultTemplateVersionId] = useState("");
  const debouncedTemplateSearch = useDebouncedValue(templateSearch);
  const versionsQuery = useDocumentTemplateVersionsData({
    category,
    q: debouncedTemplateSearch || undefined,
    limit: 100
  });
  const versions = versionsQuery.data ?? [];

  return (
    <div className="admin-content">
      <PreviewNotice>Superadmin settings use dummy templates in preview. Live template changes create immutable document versions.</PreviewNotice>
      <section className="admin-section">
        <Card padded>
          <EntityTableHeader
            action={
              <div className="row gap-8 wrap">
                <Button icon="refresh" onClick={() => refetchLive(versionsQuery.refetch)} size="sm">Refresh</Button>
                <Button
                  icon="plus"
                  onClick={() => {
                    setDefaultTemplateVersionId("");
                    setShowTemplateForm(true);
                  }}
                  size="sm"
                  variant="primary"
                >
                  Create version
                </Button>
              </div>
            }
            description="Versioned clickwrap templates by category. Published versions are immutable evidence anchors."
            filters={<SelectInput label="Category" onChange={setCategory} options={Object.values(CategoryEnum)} value={category} />}
            onSearch={setTemplateSearch}
            search={templateSearch}
            searchPlaceholder="Search title, key, legal ref, hash, UUID"
            title="Document templates"
          />
          {versionsQuery.error ? <Banner tone="bad" title="Could not load document templates">{errorMessage(versionsQuery.error)}</Banner> : null}
          {versions.length ? (
            <div className="table-wrap admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Template</th>
                    <th>Status</th>
                    <th>Version</th>
                    <th>Published</th>
                    <th>Hash</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {versions.map((version) => (
                    <tr key={version.id}>
                      <td><strong>{version.template.name}</strong><span className="mono muted">{version.id}</span></td>
                      <td>
                        <Chip tone={version.template.current_published_version_id === version.id ? "ok" : statusTone(version.status)}>
                          {version.template.current_published_version_id === version.id ? "Current" : labelize(version.status)}
                        </Chip>
                      </td>
                      <td>v{version.version_number}</td>
                      <td>{formatDateTime(version.published_at)}</td>
                      <td className="mono">{version.content_hash}</td>
                      <td>
                        <div className="row gap-8 wrap">
                          <Button
                            onClick={() => {
                              setDefaultTemplateVersionId(version.id);
                              setShowTemplateForm(true);
                            }}
                            size="sm"
                          >
                            Publish / clone
                          </Button>
                          <UnsupportedRemoveNote label="Template version" />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty icon="doc" title="No template versions">
              Create a draft or publish an initial version for this category.
            </Empty>
          )}
        </Card>
      </section>
      <section className="admin-section">
        <Card padded>
          <SectionHeader
            description="Admin users and user account access controls now live in the Users module so account-level actions are reviewed from one place."
            title="User account administration"
          />
          <p className="muted">
            Open the Users module to search platform users, create admin accounts, restrict or reactivate accounts, and start superadmin read-only views.
          </p>
        </Card>
      </section>
      {showTemplateForm ? (
        <Modal title="Document template version" onClose={() => setShowTemplateForm(false)}>
          <DocumentTemplateForm
            category={category}
            defaultVersionId={defaultTemplateVersionId || versions[0]?.id || ""}
            onDone={() => {
              setShowTemplateForm(false);
              refetchLive(versionsQuery.refetch);
            }}
          />
        </Modal>
      ) : null}
    </div>
  );
}

const qaDevModePreviewState: QaDevModeState = {
  allowed: true,
  is_enabled: false,
  current_time: new Date().toISOString(),
  entered_at: null,
  entered_by_user_id: null,
  snapshot_created_at: null,
  has_snapshot: false,
  note: "",
  last_advanced_at: null,
  last_advance_summary: {},
  max_advance_days: 120,
  environment: "preview"
};

function qaSummaryBatches(state: QaDevModeState | undefined) {
  const summary = state?.last_advance_summary;
  if (!summary || typeof summary !== "object" || Array.isArray(summary)) return [];
  const batches = (summary as Record<string, unknown>).batches;
  return Array.isArray(batches) ? batches.slice(-8) : [];
}

function qaFailedCount(state: QaDevModeState | undefined) {
  const summary = state?.last_advance_summary;
  if (!summary || typeof summary !== "object" || Array.isArray(summary)) return 0;
  const failed = (summary as Record<string, unknown>).failed_count;
  return typeof failed === "number" ? failed : 0;
}

export function QaDevModePanel() {
  const [note, setNote] = useState("QA session");
  const [days, setDays] = useState("1");
  const [confirmation, setConfirmation] = useState("");
  const [notice, setNotice] = useState("");
  const stateQuery = useV1QaDevModeRetrieve({
    query: {
      enabled: !isFixturePreview,
      placeholderData: isFixturePreview ? qaDevModePreviewState : undefined,
      retry: false,
      staleTime: 0
    }
  });
  const enable = useV1QaDevModeEnableCreate();
  const advance = useV1QaDevModeAdvanceCreate();
  const revert = useV1QaDevModeRevertCreate();
  const state = stateQuery.data ?? qaDevModePreviewState;
  const failedCount = qaFailedCount(state);
  const batches = qaSummaryBatches(state);

  function refresh() {
    refetchLive(stateQuery.refetch);
  }

  function enableMode() {
    if (isFixturePreview) {
      setNotice("Preview mode: enabling QA would create a database snapshot and pin simulated time.");
      return;
    }
    enable.mutate(
      { data: { note } },
      {
        onSuccess: () => {
          setNotice("QA mode enabled. A database snapshot was captured at entry.");
          refresh();
        }
      }
    );
  }

  function advanceTime() {
    const parsedDays = intValue(days, 1);
    if (isFixturePreview) {
      setNotice(`Preview mode: advancing ${parsedDays} day(s) would run daily scheduled jobs.`);
      return;
    }
    advance.mutate(
      { data: { days: parsedDays } },
      {
        onSuccess: () => {
          setNotice(`QA clock advanced by ${parsedDays} day(s). Scheduled jobs were run for crossed business dates.`);
          refresh();
        }
      }
    );
  }

  function revertMode() {
    if (isFixturePreview) {
      setNotice("Preview mode: revert would restore the entry database snapshot and sign the operator out.");
      return;
    }
    revert.mutate(
      { data: { confirmation } },
      {
        onSuccess: () => {
          setNotice("Database revert was requested and completed. Sign in again if your session is reset.");
          setConfirmation("");
          refresh();
        }
      }
    );
  }

  return (
    <div className="admin-content">
      <PreviewNotice>QA mode is dummy-only in preview. Live mode requires QA_DEV_MODE_ALLOWED and an active superadmin session.</PreviewNotice>
      <section className="admin-section">
        <Card padded>
          <SectionHeader
            description="Temporary staging/local controls for deterministic QA. This must never be enabled in production."
            title="QA development mode"
          />
          {stateQuery.error ? (
            <Banner tone="bad" title="Could not load QA mode">
              {errorMessage(stateQuery.error)}
            </Banner>
          ) : null}
          {!state.allowed ? (
            <Banner tone="warn" title="Disabled by deployment config">
              Set QA_DEV_MODE_ALLOWED=true in a non-production environment to use this panel.
            </Banner>
          ) : null}
          {notice ? (
            <Banner tone="info" title="QA action">
              {notice}
            </Banner>
          ) : null}
          <div className="admin-detail-grid">
            <div className="admin-review-row">
              <span>Environment</span>
              <strong>{state.environment}</strong>
            </div>
            <div className="admin-review-row">
              <span>Mode</span>
              <strong>
                <Chip tone={state.is_enabled ? "warn" : "neutral"}>{state.is_enabled ? "Enabled" : "Disabled"}</Chip>
              </strong>
            </div>
            <div className="admin-review-row">
              <span>Simulated time</span>
              <strong>{state.current_time ? formatDateTime(state.current_time) : "-"}</strong>
            </div>
            <div className="admin-review-row">
              <span>Entered at</span>
              <strong>{state.entered_at ? formatDateTime(state.entered_at) : "-"}</strong>
            </div>
            <div className="admin-review-row">
              <span>Snapshot</span>
              <strong>{state.has_snapshot ? "Captured" : "-"}</strong>
            </div>
            <div className="admin-review-row">
              <span>Max advance</span>
              <strong>{state.max_advance_days} days per action</strong>
            </div>
          </div>
        </Card>
      </section>

      <section className="admin-module-grid">
        <Card padded>
          <SectionHeader
            description="Creates a database snapshot and pins now_utc() to the QA clock."
            title="Enable mode"
          />
          <Field label="QA session note">
            <textarea
              onChange={(event) => setNote(event.target.value)}
              rows={3}
              value={note}
            />
          </Field>
          {enable.error ? <Banner tone="bad" title="Could not enable QA mode">{errorMessage(enable.error)}</Banner> : null}
          <OperationConfirmButton
            confirmLabel="Enable QA mode"
            description="A database snapshot is created before mode is enabled. Use only on staging/local data."
            details={[
              { label: "Environment", value: state.environment },
              { label: "Snapshot", value: "Captured before enabling" }
            ]}
            disabled={!state.allowed || state.is_enabled || enable.isPending}
            onConfirm={enableMode}
            title="Enable QA development mode"
            variant="danger"
          >
            Enable QA mode
          </OperationConfirmButton>
        </Card>

        <Card padded>
          <SectionHeader
            description="Advances the simulated clock by whole days and runs the daily scheduled jobs for each crossed Zurich business date."
            title="Advance time"
          />
          <Field hint="Use small increments when testing irreversible transitions." label="Days to advance">
            <input
              max={state.max_advance_days}
              min={1}
              onChange={(event) => setDays(event.target.value)}
              type="number"
              value={days}
            />
          </Field>
          {advance.error ? <Banner tone="bad" title="Could not advance time">{errorMessage(advance.error)}</Banner> : null}
          <OperationConfirmButton
            confirmLabel="Advance and run jobs"
            description="This runs balance ageing, servicing status, funding expiry, reconciliation sync and due-email dispatch for crossed business dates."
            details={[
              { label: "Current simulated time", value: state.current_time ? formatDateTime(state.current_time) : "-" },
              { label: "Days", value: days || "0" }
            ]}
            disabled={!state.allowed || !state.is_enabled || advance.isPending}
            onConfirm={advanceTime}
            title="Advance QA time"
            variant="danger"
          >
            Advance time
          </OperationConfirmButton>
        </Card>

        <Card padded>
          <SectionHeader
            description="Restores the entry snapshot and exits QA mode. Sessions and all data changes made since entry are reset."
            title="Revert database"
          />
          <Banner tone="bad" title="Destructive QA reset">
            This restores the database to the moment QA mode was enabled. You should expect to sign in again.
          </Banner>
          <Field hint='Type "REVERT QA DB" exactly.' label="Confirmation">
            <input
              onChange={(event) => setConfirmation(event.target.value)}
              value={confirmation}
            />
          </Field>
          {revert.error ? <Banner tone="bad" title="Could not revert QA mode">{errorMessage(revert.error)}</Banner> : null}
          <OperationConfirmButton
            confirmLabel="Restore snapshot"
            description="This reverts the database snapshot captured when QA mode was enabled. File/object storage is not rolled back."
            details={[
              { label: "Snapshot", value: state.has_snapshot ? "Captured" : "Missing" },
              { label: "Confirmation", value: confirmation || "-" }
            ]}
            disabled={!state.allowed || !state.is_enabled || confirmation !== "REVERT QA DB" || revert.isPending}
            onConfirm={revertMode}
            title="Revert QA database"
            variant="danger"
          >
            Revert database
          </OperationConfirmButton>
        </Card>
      </section>

      <section className="admin-section">
        <Card padded>
          <SectionHeader
            description="Last advance result. Failed scheduled jobs should be investigated before continuing QA."
            title="Scheduled-job replay"
          />
          {failedCount ? (
            <Banner tone="bad" title="Scheduled jobs failed">
              {failedCount} job run(s) failed during the last advancement.
            </Banner>
          ) : state.last_advanced_at ? (
            <Banner tone="ok" title="Last advancement completed">
              No scheduled-job failures were reported.
            </Banner>
          ) : null}
          {batches.length ? (
            <div className="table-wrap admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>As of</th>
                    <th>Business date</th>
                    <th>Results</th>
                  </tr>
                </thead>
                <tbody>
                  {batches.map((batch, index) => {
                    const row = batch as Record<string, unknown>;
                    const results = Array.isArray(row.results) ? row.results : [];
                    return (
                      <tr key={`${row.as_of}-${index}`}>
                        <td>{typeof row.as_of === "string" ? formatDateTime(row.as_of) : "-"}</td>
                        <td>{typeof row.business_date === "string" ? row.business_date : "-"}</td>
                        <td>
                          <div className="row gap-8 wrap">
                            {results.map((result, resultIndex) => {
                              const job = result as Record<string, unknown>;
                              const status = String(job.status ?? "");
                              return (
                                <Chip key={`${job.job_name}-${resultIndex}`} tone={status === "failed" ? "bad" : status === "skipped" ? "neutral" : "ok"}>
                                  {String(job.job_name ?? "job")}: {labelize(status)}
                                </Chip>
                              );
                            })}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty icon="clock" title="No replay history">
              Advance QA time to see which scheduled jobs ran.
            </Empty>
          )}
        </Card>
      </section>
    </div>
  );
}

function DocumentTemplateForm({
  category,
  defaultVersionId,
  onDone
}: {
  category: DocumentCategory;
  defaultVersionId: string;
  onDone?: () => void;
}) {
  const [name, setName] = useState("BANXUM Terms Template");
  const [title, setTitle] = useState("BANXUM Terms");
  const [body, setBody] = useState("Advisor-approved body will be inserted here.");
  const [checkboxes, setCheckboxes] = useState("I accept these terms.\nI understand the platform risks.");
  const [publishNow, setPublishNow] = useState(false);
  const [versionId, setVersionId] = useState(defaultVersionId);
  const [versionQuery, setVersionQuery] = useState(defaultVersionId);
  const [legalRef, setLegalRef] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const create = useV1DocumentsAdminTemplatesVersionsCreate({
    mutation: { onSuccess: () => onDone?.() }
  });
  const publish = useV1DocumentsAdminTemplatesVersionsPublishCreate({
    mutation: { onSuccess: () => onDone?.() }
  });

  useEffect(() => {
    setVersionId(defaultVersionId);
    setVersionQuery(defaultVersionId);
  }, [defaultVersionId]);

  function createVersion(event: FormEvent) {
    event.preventDefault();
    const data: DocumentTemplateVersionCreateRequest = {
      category,
      name,
      title,
      body,
      checkbox_labels: checkboxes.split("\n").map((line) => line.trim()).filter(Boolean),
      publish_now: publishNow,
      legal_review_reference: legalRef || undefined
    };
    if (isFixturePreview) {
      setPreview(`${name} version would be created for ${labelize(category)}.`);
      return;
    }
    create.mutate({ data });
  }

  function publishVersion() {
    if (isFixturePreview) {
      setPreview(`Template version ${versionId || defaultVersionId} would be published.`);
      return;
    }
    publish.mutate({ templateVersionId: versionId || defaultVersionId, data: { legal_review_reference: legalRef } });
  }

  return (
    <div className="admin-form-panel">
      <h2>Create or publish template</h2>
      <form className="admin-action-form" onSubmit={createVersion}>
        <FieldGrid>
          <TextInput label="Name" onChange={setName} required value={name} />
          <TextInput label="Title" onChange={setTitle} required value={title} />
          <TextInput label="Legal review reference" onChange={setLegalRef} value={legalRef} />
        </FieldGrid>
        <TextAreaInput label="Body" onChange={setBody} required rows={5} value={body} />
        <TextAreaInput hint="One checkbox label per line." label="Checkbox labels" onChange={setCheckboxes} rows={3} value={checkboxes} />
        <label className="check-row">
          <input checked={publishNow} onChange={(event) => setPublishNow(event.target.checked)} type="checkbox" />
          Publish immediately after creation.
        </label>
        {create.error || publish.error ? <Banner tone="bad" title="Template action failed">{errorMessage(create.error || publish.error)}</Banner> : null}
        {preview ? <Banner tone="info" title="Preview action recorded">{preview}</Banner> : null}
        <Button disabled={create.isPending} type="submit" variant="primary">Create version</Button>
      </form>
      <div className="admin-action-form">
        <TemplateVersionLookupInput
          category={category}
          onChange={setVersionId}
          onQueryChange={setVersionQuery}
          query={versionQuery}
          value={versionId || defaultVersionId}
        />
        <OperationConfirmButton
          confirmLabel="Publish template"
          description="Publishing makes this immutable template version current for future clickwrap evidence. Existing accepted versions remain preserved."
          details={[
            { label: "Category", value: labelize(category) },
            { label: "Template version", value: versionId || defaultVersionId || "-" },
            { label: "Legal review reference", value: legalRef || "Not provided" }
          ]}
          disabled={publish.isPending || !(versionId || defaultVersionId)}
          onConfirm={publishVersion}
          title="Confirm template publication"
          variant="primary"
        >
          Publish selected version
        </OperationConfirmButton>
      </div>
    </div>
  );
}

export function UserAccountsPanel() {
  const [search, setSearch] = useState("");
  const [accountType, setAccountType] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [showCreate, setShowCreate] = useState(false);
  const [accessUser, setAccessUser] = useState<AdminUserDirectoryRow | null>(null);
  const [documentsUser, setDocumentsUser] = useState<AdminUserDirectoryRow | null>(null);
  const [impersonationNotice, setImpersonationNotice] = useState("");
  const debouncedSearch = useDebouncedValue(search);
  const pageSize = 25;
  const usersQuery = useAdminUsersDirectoryData({
    q: debouncedSearch,
    account_type: accountType || undefined,
    status: status || undefined,
    limit: pageSize,
    offset: page * pageSize
  });
  const users = usersQuery.data?.results ?? [];
  const total = usersQuery.data?.count ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const impersonationMutation = useV1AdminOpsUsersReadonlyImpersonationCreate();

  useEffect(() => {
    setPage(0);
  }, [accountType, debouncedSearch, status]);

  function userDisplay(user: AdminUserDirectoryRow) {
    return user.full_name || user.email || user.id;
  }

  function startReadOnlyImpersonation(user: AdminUserDirectoryRow) {
    if (isFixturePreview) {
      setImpersonationNotice(`Preview would open a read-only view as ${userDisplay(user)}.`);
      return;
    }
    impersonationMutation.mutate(
      { userId: user.id },
      {
        onSuccess: (response) => {
          writeReadonlyImpersonation(
            response.token,
            `${response.target_full_name || response.target_email} (${response.target_email})`,
            response.expires_in_seconds
          );
          window.open("/", "_blank", "noopener,noreferrer");
          setImpersonationNotice(`Read-only portal opened for ${response.target_email}.`);
        }
      }
    );
  }

  return (
    <div className="admin-content">
      <PreviewNotice>User records are dummy data in preview. Live mode queries users server-side with pagination.</PreviewNotice>
      <Card padded>
        <EntityTableHeader
          action={<Button icon="plus" onClick={() => setShowCreate(true)} size="sm" variant="primary">Create admin</Button>}
          description="Search every platform account by name, email, investor reference or UUID. Account-level actions are audited here."
          onSearch={setSearch}
          search={search}
          searchPlaceholder="Search name, email, reference, UUID"
          title="User accounts"
        />
        <FieldGrid>
          <SelectInput
            label="Account type"
            onChange={setAccountType}
            options={["", "natural_person_lender", "legal_entity_lender_representative", "admin", "superadmin"]}
            value={accountType}
          />
          <SelectInput
            label="Account status"
            onChange={setStatus}
            options={["", "pending_kyc", "active", "restricted", "locked", "closed"]}
            value={status}
          />
        </FieldGrid>
        {usersQuery.error ? <Banner tone="bad" title="Could not load users">{errorMessage(usersQuery.error)}</Banner> : null}
        {impersonationMutation.error ? <Banner tone="bad" title="Could not start read-only view">{errorMessage(impersonationMutation.error)}</Banner> : null}
        {impersonationNotice ? <Banner tone="info" title="Read-only view">{impersonationNotice}</Banner> : null}
        {users.length ? (
          <>
            <div className="table-wrap admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>User ID</th>
                    <th>Reference</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Phone verification</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td className="admin-user-name-cell">
                        <strong>{user.full_name || "-"}</strong>
                      </td>
                      <td>
                        <span className="admin-email-cell">{user.email}</span>
                      </td>
                      <td>
                        <span className="admin-id-cell mono muted">{user.id}</span>
                      </td>
                      <td className="mono">{user.investor_reference || "-"}</td>
                      <td><Chip tone="neutral">{labelize(user.account_type)}</Chip></td>
                      <td><Chip tone={statusTone(user.status)}>{labelize(user.status)}</Chip></td>
                      <td>{user.phone_verified ? <Chip tone="ok">Phone verified</Chip> : <Chip tone="neutral">Phone unverified</Chip>}</td>
                      <td>{formatDateTime(user.date_joined)}</td>
                      <td>
                        <div className="row gap-8 wrap">
                          <Button onClick={() => setAccessUser(user)} size="sm">Access controls</Button>
                          <Button onClick={() => setDocumentsUser(user)} size="sm" variant="ghost">Documents</Button>
                          <Button
                            disabled={!user.can_impersonate_readonly || impersonationMutation.isPending}
                            onClick={() => startReadOnlyImpersonation(user)}
                            size="sm"
                            variant="ghost"
                          >
                            Read-only view
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="admin-pager">
              <span className="muted">
                Showing {total === 0 ? 0 : page * pageSize + 1}&ndash;{Math.min(total, (page + 1) * pageSize)} of {total}
              </span>
              <div className="row gap-8">
                <Button disabled={page === 0} onClick={() => setPage((current) => Math.max(0, current - 1))} size="sm">Previous</Button>
                <span className="muted">Page {page + 1} of {pageCount}</span>
                <Button disabled={page >= pageCount - 1} onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))} size="sm">Next</Button>
              </div>
            </div>
          </>
        ) : (
          <Empty icon="search" title="No users found">
            Adjust the search or filters.
          </Empty>
        )}
      </Card>
      {showCreate ? (
        <Modal title="Create admin user" onClose={() => setShowCreate(false)}>
          <AdminUserCreateForm
            onCreated={() => {
              setShowCreate(false);
              refetchLive(usersQuery.refetch);
            }}
          />
        </Modal>
      ) : null}
      {accessUser ? (
        <Modal title={`Account access - ${userDisplay(accessUser)}`} onClose={() => setAccessUser(null)}>
          <AccountAccessForm
            defaultUserId={accessUser.id}
            defaultUserQuery={`${userDisplay(accessUser)} ${accessUser.email}`}
          />
        </Modal>
      ) : null}
      {documentsUser ? (
        <UserDocumentsModal
          onClose={() => setDocumentsUser(null)}
          user={documentsUser}
        />
      ) : null}
    </div>
  );
}

function UserDocumentsModal({
  onClose,
  user
}: {
  onClose: () => void;
  user: AdminUserDirectoryRow;
}) {
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const documentsQuery = useV1AdminOpsUsersDocumentsRetrieve(user.id, {
    query: {
      enabled: !isFixturePreview && Boolean(user.id),
      placeholderData: isFixturePreview
        ? {
            user: {
              id: user.id,
              email: user.email,
              full_name: user.full_name,
              investor_reference: user.investor_reference,
              account_type: user.account_type,
              status: user.status
            },
            documents: [],
            disclaimer:
              "Preview mode does not include accepted-document evidence. Live mode fetches this user-specific history from the backend."
          }
        : undefined
    }
  });
  const artifactMutation = useV1AdminOpsUsersDocumentsArtifactCreate();
  const documents = documentsQuery.data?.documents ?? [];

  function generate(documentRow: AdminUserDocument, outputFormat: "pdf" | "csv") {
    setError("");
    setSuccess("");
    if (isFixturePreview) {
      setSuccess(`${documentRow.title} would be generated as ${outputFormat.toUpperCase()}.`);
      return;
    }
    artifactMutation.mutate(
      {
        userId: user.id,
        acceptanceId: documentRow.id,
        data: {
          output_format:
            outputFormat === "csv"
              ? AdminUserDocumentArtifactRequestOutputFormatEnum.csv
              : AdminUserDocumentArtifactRequestOutputFormatEnum.pdf
        }
      },
      {
        onSuccess: (artifact) => {
          downloadArtifact(artifact);
          setSuccess(`Generated ${artifact.filename}.`);
        },
        onError: (mutationError) => setError(errorMessage(mutationError))
      }
    );
  }

  return (
    <Modal title={`Accepted documents - ${user.full_name || user.email}`} onClose={onClose}>
      <div className="col gap-16">
        <Banner tone="neutral" title="Accepted-document history">
          {documentsQuery.data?.disclaimer ?? "Each document is generated on demand from immutable clickwrap evidence."}
        </Banner>
        {documentsQuery.error ? <Banner tone="bad" title="Could not load documents">{errorMessage(documentsQuery.error)}</Banner> : null}
        {error ? <Banner tone="bad" title="Could not generate document">{error}</Banner> : null}
        {success ? <Banner tone="ok" title="Document generated">{success}</Banner> : null}
        <div className="admin-form-grid">
          <div className="admin-readonly-field"><span>Name</span><strong>{user.full_name || "-"}</strong></div>
          <div className="admin-readonly-field"><span>Email</span><strong>{user.email}</strong></div>
          <div className="admin-readonly-field"><span>Reference</span><strong className="mono">{user.investor_reference || "-"}</strong></div>
          <div className="admin-readonly-field"><span>Status</span><strong>{labelize(user.status)}</strong></div>
        </div>
        {documentsQuery.isLoading ? (
          <div className="muted">Loading accepted documents...</div>
        ) : documents.length ? (
          <div className="table-wrap admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Type</th>
                  <th>Accepted</th>
                  <th>Context</th>
                  <th>Hash</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((documentRow) => (
                  <tr key={documentRow.id}>
                    <td>
                      <strong>{documentRow.title}</strong>
                      <div className="muted small">{documentRow.template_title}</div>
                    </td>
                    <td><Chip tone="neutral">{documentRow.document_type}</Chip></td>
                    <td>{formatDateTime(documentRow.date)}</td>
                    <td>{documentRow.context_label}</td>
                    <td className="mono muted">{documentRow.content_hash.slice(0, 12)}...</td>
                    <td>
                      <div className="row gap-8 wrap">
                        <Button
                          disabled={artifactMutation.isPending}
                          icon="download"
                          onClick={() => generate(documentRow, "pdf")}
                          size="sm"
                          variant="ghost"
                        >
                          PDF
                        </Button>
                        {documentRow.output_formats.includes("csv") ? (
                          <Button
                            disabled={artifactMutation.isPending}
                            onClick={() => generate(documentRow, "csv")}
                            size="sm"
                            variant="ghost"
                          >
                            CSV
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty icon="doc" title="No accepted documents">
            This user has no accepted document evidence yet.
          </Empty>
        )}
      </div>
    </Modal>
  );
}

function AdminUserCreateForm({ onCreated }: { onCreated?: () => void }) {
  const [email, setEmail] = useState(adminFormDefaults.adminEmail);
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState(adminFormDefaults.adminFullName);
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1AuthAdminUsersCreate({
    mutation: {
      onSuccess: () => {
        setSuccess("Admin user was created. Password reset remains superadmin-managed.");
        onCreated?.();
      }
    }
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: AdminUserCreateRequest = { email, password, full_name: fullName };
    if (isFixturePreview) {
      setPreview(`${fullName} (${email}) would be created as an admin user.`);
      return;
    }
    mutation.mutate({ data });
  }

  return (
    <div className="admin-form-panel">
      <h2>Create admin user</h2>
      <p>Superadmin-created admins use email, password and email-code login. There is no forgot-password flow.</p>
      <form className="admin-action-form" onSubmit={submit}>
        <FieldGrid>
          <TextInput label="Email" onChange={setEmail} required type="email" value={email} />
          <TextInput label="Full name" onChange={setFullName} required value={fullName} />
          <TextInput label="Initial password" onChange={setPassword} required type="password" value={password} />
        </FieldGrid>
        <ActionFooter mutation={mutation} previewMessage={preview} successMessage={success} submitLabel="Create admin" />
      </form>
    </div>
  );
}

function StatLike({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <Card padded className="admin-stat-like">
      <span>{label}</span>
      <strong>{value}</strong>
      {sub ? <small>{sub}</small> : null}
    </Card>
  );
}
