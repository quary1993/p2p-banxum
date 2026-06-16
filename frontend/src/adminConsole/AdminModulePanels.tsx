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
  useV1AuthAdminUsersAccessCreate,
  useV1AuthAdminUsersCreate,
  useV1DocumentsAdminTemplatesVersionsCreate,
  useV1DocumentsAdminTemplatesVersionsPublishCreate,
  useV1EntitiesAdminBorrowersCreate,
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
  useV1LoansAdminLoansPublishCreate,
  useV1MarketplacePrimaryAdminLoansCancelFundingCreate,
  useV1MarketplacePrimaryAdminLoansCloseFundingCreate,
  useV1MarketplacePrimaryAdminLoansExpiryScanCreate,
  useV1MarketplacePrimaryAdminOrdersReleaseBalanceCreate,
  useV1MarketplaceSecondaryAdminListingsApproveCreate,
  useV1MarketplaceSecondaryAdminListingsRejectCreate,
  useV1MarketplaceSecondaryAdminListingsRemoveCreate,
  useV1ReportingAdminReportsCreate,
  useV1ServicingAdminBorrowerRepaymentsCreate,
  useV1ServicingAdminRecoveriesCreate,
  useV1ServicingAdminRiskNotesCreate,
  useV1ServicingAdminStatusScanCreate,
  type AccountAccessChangeRequest,
  type AccountAccessChangeRequestReasonCodeEnum as AccountAccessReasonCode,
  type AdminLookupResult,
  type AdminUserCreateRequest,
  type BalanceAgeingScanRequest,
  type BorrowerDisbursementFinalizeRequest,
  type BorrowerEntityCreateRequest,
  type BorrowerEntityTypeEnum as BorrowerEntityType,
  type BorrowerKybStatusEnum as BorrowerKybStatus,
  type BorrowerRepaymentRecordRequest,
  type CategoryEnum as DocumentCategory,
  type CollateralTypeEnum as LoanCollateralType,
  type DecisionEnum as KycDecision,
  type DocumentTemplateVersionCreateRequest,
  type FxExternalSettlementDeclareRequest,
  type InvestorPayoutInstructionRegisterRequest,
  type InvestorWithdrawalCancelRequest,
  type InvestorWithdrawalFinalizeRequest,
  type KycManualReviewDecisionRequest,
  type KycManualReviewDecisionRequestReasonCodeEnum as KycReasonCode,
  type LenderDepositDeclareRequest,
  type LoanCreateRequest,
  type LoanRecoveryPaymentRecordRequest,
  type LoanRiskNoteCreateRequest,
  type LoanServicingStatusScanRequest,
  type NewStatusEnum as AccountNewStatus,
  type PeriodPresetEnum as ReportPeriodPreset,
  type PurposeEnum as LoanPurpose,
  type RepaymentTypeEnum as LoanRepaymentType,
  type PrimaryInvestmentOrderReleaseRequest,
  type PrimaryLoanCancellationRequest,
  type PrimaryLoanCloseRequest,
  type PrimaryLoanExpiryScanRequest,
  type ReconciliationSnapshotCreateRequest,
  type RedactionModeEnum as ReportRedactionMode,
  type ReportGenerateRequest,
  type ReportGenerateRequestOutputFormatEnum as ReportOutputFormat,
  type ReportGenerateResponse,
  type ReportTypeEnum as AdminReportType,
  type RiskRatingEnum as LoanRiskRating,
  type SecondaryMarketListingApproveRequest,
  type SecondaryMarketListingRejectRequest,
  type SecondaryMarketListingRemoveRequest
} from "../api/generated/banxumApi";
import { isFixturePreview } from "../investorPortal/data";
import { formatDate, formatDateTime, formatMoneyMinor, formatRateBps } from "../investorPortal/format";
import { Banner, Button, Card, Chip, Empty, Field, Modal, Money, type Tone } from "../investorPortal/ui";
import { adminFormDefaults } from "./adminFixtures";
import {
  useAuditEventsData,
  useAdminBorrowerLookupData,
  useAdminDocumentTemplateVersionLookupData,
  useAdminInvestorLookupData,
  useAdminKycCaseLookupData,
  useAdminLoanLookupData,
  useAdminPrimaryOrderLookupData,
  useAdminSecondaryListingLookupData,
  useAdminUserLookupData,
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

const today = new Date().toLocaleDateString("en-CA", { timeZone: "Europe/Zurich" });
const defaultCollectionAccount = adminFormDefaults.collectionAccount;

function labelize(value: string | null | undefined) {
  if (!value) return "-";
  if (value === "written_off") return "Defaulted";
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

function reportContentBytes(response: ReportGenerateResponse) {
  if (response.content_encoding.toLowerCase().includes("base64")) {
    const binary = window.atob(response.content);
    return Uint8Array.from(binary, (char) => char.charCodeAt(0));
  }
  return new TextEncoder().encode(response.content);
}

function downloadReportArtifact(response: ReportGenerateResponse) {
  const blob = new Blob([reportContentBytes(response)], {
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

function statusTone(status: string): Tone {
  if (["approved", "active", "funded", "published", "repaid", "finalized", "current", "clean"].includes(status)) return "ok";
  if (["manual_review", "pending", "pending_review", "approval_requested", "late", "draft"].includes(status)) return "warn";
  if (["declined", "defaulted", "written_off", "locked", "closed", "restricted", "sanctions_hit"].includes(status)) return "bad";
  return "neutral";
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
  placeholder
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  type?: string;
  hint?: string;
  placeholder?: string;
}) {
  return (
    <Field hint={hint} label={label}>
      <input
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
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
  placeholder
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  currency: string;
  required?: boolean;
  hint?: string;
  placeholder?: string;
}) {
  const helper = [minorUnitPreview(value, currency), hint].filter(Boolean).join(" ");
  return (
    <Field hint={helper} label={label}>
      <input
        inputMode="numeric"
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        required={required}
        value={value}
      />
    </Field>
  );
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
  required = false
}: {
  value: string;
  onChange: (value: string) => void;
  query: string;
  onQueryChange: (value: string) => void;
  required?: boolean;
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

function SecondaryListingLookupInput({
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
  const lookup = useAdminSecondaryListingLookupData({ q: debouncedQuery, limit: 20 });
  return (
    <AdminLookupInput
      error={lookup.error}
      hint="Search by loan title, seller name/email/reference, or listing UUID."
      label="Secondary listing"
      loading={lookup.isFetching}
      onChange={onChange}
      onQueryChange={onQueryChange}
      options={lookup.data ?? []}
      placeholder="Loan, seller, or listing UUID"
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
  hint
}: {
  label: string;
  value: T;
  onChange: (value: T) => void;
  options: readonly T[];
  hint?: string;
}) {
  return (
    <Field hint={hint} label={label}>
      <select onChange={(event) => onChange(event.target.value as T)} value={value}>
        {options.map((option) => (
          <option key={option} value={option}>
            {labelize(option)}
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

export function CompliancePanel() {
  const kycQuery = useKycManualReviewsData();
  const cases = useMemo(() => kycQuery.data ?? [], [kycQuery.data]);
  const [selectedCaseId, setSelectedCaseId] = useState("");

  useEffect(() => {
    if (!selectedCaseId && cases[0]) setSelectedCaseId(cases[0].id);
  }, [cases, selectedCaseId]);

  return (
    <div className="admin-content">
      <PreviewNotice>Compliance cases are dummy Didit status mappings. Live mode reads only backend-owned KYC evidence.</PreviewNotice>
      <section className="admin-kpi-grid">
        <StatLike label="Manual review" value={cases.length} sub="Provider-routed cases" />
        <StatLike label="PEP/high risk" value={cases.filter((item) => item.detected_flags.some((flag) => flag.includes("pep") || flag.includes("high"))).length} sub="AML officer queue" />
        <StatLike label="Pending decision" value={cases.filter((item) => !item.decision_at).length} sub="No Garanta decision yet" />
        <StatLike label="Provider" value={cases[0]?.provider ?? "Didit"} sub="External KYC/KYB provider" />
      </section>

      <section className="admin-two-col">
        <Card padded>
          <SectionHeader
            action={<Button icon="refresh" onClick={() => refetchLive(kycQuery.refetch)} size="sm">Refresh</Button>}
            description="Review KYC/KYB cases routed to Garanta manual review. Sanctions and fraud blocks remain non-overridable server-side."
            title="KYC manual review"
          />
          {cases.length ? (
            <div className="table-wrap admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Subject</th>
                    <th>Status</th>
                    <th>Risk</th>
                    <th>Flags</th>
                    <th>Provider refs</th>
                    <th>Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {cases.map((item) => (
                    <tr
                      className={selectedCaseId === item.id ? "admin-selected-row" : ""}
                      key={item.id}
                      onClick={() => setSelectedCaseId(item.id)}
                    >
                      <td>
                        <strong>{item.subject_reference}</strong>
                        <span className="muted mono">{item.user_id ?? item.subject_type}</span>
                      </td>
                      <td><Chip tone={statusTone(item.status)}>{labelize(item.status)}</Chip></td>
                      <td>{labelize(item.risk_classification)}</td>
                      <td>{item.detected_flags.map((flag) => <Chip key={flag} tone="warn">{labelize(flag)}</Chip>)}</td>
                      <td>
                        <div className="col gap-4">
                          <span className="mono">{item.provider_report_id || "-"}</span>
                          <span className="mono muted">{item.aml_screening_id || "-"}</span>
                        </div>
                      </td>
                      <td>{formatDateTime(item.updated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty icon="shield" title="No manual-review cases">
              KYC/KYB review items will appear when Didit routes a case to Garanta.
            </Empty>
          )}
        </Card>
        <ManualKycDecisionForm defaultCaseId={selectedCaseId} />
      </section>

      <section className="admin-section">
        <AccountAccessForm />
      </section>
    </div>
  );
}

function ManualKycDecisionForm({ defaultCaseId }: { defaultCaseId: string }) {
  const [caseId, setCaseId] = useState(defaultCaseId);
  const [caseQuery, setCaseQuery] = useState(defaultCaseId);
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

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: KycManualReviewDecisionRequest = { decision, reason_code: reasonCode, note, evidence_summary: evidenceSummary };
    if (isFixturePreview) {
      setPreview(`${labelize(decision)} recorded for ${caseId || "selected case"}.`);
      return;
    }
    mutation.mutate({ caseId, data });
  }

  return (
    <Card padded>
      <h2>Record AML decision</h2>
      <p>Use only after provider evidence has been reviewed. The backend enforces allowed status transitions.</p>
      <form className="admin-action-form" onSubmit={submit}>
        <KycCaseLookupInput
          onChange={setCaseId}
          onQueryChange={setCaseQuery}
          query={caseQuery}
          required
          value={caseId}
        />
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

function AccountAccessForm() {
  const [userId, setUserId] = useState("");
  const [userQuery, setUserQuery] = useState("");
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

export function FinanceOpsPanel() {
  return (
    <div className="admin-content">
      <PreviewNotice>Finance forms use dummy IDs in preview. Live submissions post to the ledger, FX and reconciliation services.</PreviewNotice>
      <section className="admin-module-grid">
        <DepositForm />
        <PayoutInstructionForm />
        <BalanceSummaryLookup />
        <BalanceAgeingScanForm />
        <ReconciliationSnapshotForm />
        <WithdrawalOpsForm />
        <BorrowerDisbursementForm />
        <FxAdminOps />
      </section>
    </div>
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
  const [paymentReference, setPaymentReference] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1LedgerAdminLenderDepositsCreate({
    mutation: { onSuccess: () => setSuccess("Deposit was declared, ledgered, and added to investor balance lots.") }
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
      <p>Declare a matched incoming bank transfer and credit the investor liability ledger.</p>
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
    mutation: { onSuccess: () => setSuccess("Payout instruction was registered and superseded the prior active instruction.") }
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
      <p>Register a verified IBAN used for withdrawals and day-60 forced returns.</p>
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

function WithdrawalOpsForm() {
  const [withdrawalId, setWithdrawalId] = useState(adminFormDefaults.withdrawalId);
  const [withdrawalQuery, setWithdrawalQuery] = useState(adminFormDefaults.withdrawalId);
  const [bookingDate, setBookingDate] = useState(today);
  const [valueDate, setValueDate] = useState(today);
  const [collectionAccount, setCollectionAccount] = useState(defaultCollectionAccount);
  const [reason, setReason] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const finalize = useV1LedgerAdminWithdrawalRequestsFinalizeCreate();
  const cancel = useV1LedgerAdminWithdrawalRequestsCancelCreate();

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
    <Card padded>
      <h2>Withdrawal execution</h2>
      <p>Finalize executed withdrawals or cancel requested withdrawals before bank execution.</p>
      <form className="admin-action-form" onSubmit={finalizeSubmit}>
        <FieldGrid>
          <WithdrawalLookupInput
            onChange={setWithdrawalId}
            onQueryChange={setWithdrawalQuery}
            query={withdrawalQuery}
            required
            value={withdrawalId}
          />
          <TextInput label="Booking date" onChange={setBookingDate} required type="date" value={bookingDate} />
          <TextInput label="Value date" onChange={setValueDate} required type="date" value={valueDate} />
          <TextInput label="Collection account" onChange={setCollectionAccount} required value={collectionAccount} />
        </FieldGrid>
        <TextAreaInput label="Admin note / cancel reason" onChange={setReason} value={reason} />
        {finalize.error || cancel.error ? <Banner tone="bad" title="Withdrawal action failed">{errorMessage(finalize.error || cancel.error)}</Banner> : null}
        {preview ? <Banner tone="info" title="Preview action recorded">{preview}</Banner> : null}
        <div className="row gap-8 wrap">
          <Button disabled={finalize.isPending} type="submit" variant="primary">Finalize withdrawal</Button>
          <Button disabled={cancel.isPending} onClick={cancelSubmit} variant="danger">Cancel before execution</Button>
        </div>
      </form>
    </Card>
  );
}

function BorrowerDisbursementForm() {
  const [loanId, setLoanId] = useState(adminFormDefaults.loanId);
  const [loanQuery, setLoanQuery] = useState(adminFormDefaults.loanId);
  const [borrowerId, setBorrowerId] = useState(adminFormDefaults.borrowerId);
  const [borrowerQuery, setBorrowerQuery] = useState(adminFormDefaults.borrowerName);
  const [amountMinor, setAmountMinor] = useState(isFixturePreview ? "98000000" : "");
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
      currency,
      booking_date: bookingDate,
      value_date: valueDate,
      collection_account_identifier: defaultCollectionAccount,
      payee_name: payeeName,
      payee_account_identifier: payeeAccount,
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
          <TextInput label="Currency" onChange={setCurrency} required value={currency} />
          <TextInput label="Booking date" onChange={setBookingDate} required type="date" value={bookingDate} />
          <TextInput label="Value date" onChange={setValueDate} required type="date" value={valueDate} />
          <TextInput label="Payee name" onChange={setPayeeName} required value={payeeName} />
          <TextInput label="Payee account" onChange={setPayeeAccount} required value={payeeAccount} />
        </FieldGrid>
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
  const borrowersQuery = useBorrowersData({ limit: 100 });
  const loansQuery = useLoansData({ limit: 100 });
  const borrowers = useMemo(() => borrowersQuery.data ?? [], [borrowersQuery.data]);
  const loans = useMemo(() => loansQuery.data ?? [], [loansQuery.data]);
  const [selectedBorrowerId, setSelectedBorrowerId] = useState("");
  const [selectedLoanId, setSelectedLoanId] = useState("");
  const selectedLoan = loans.find((loan) => loan.id === selectedLoanId) ?? loans[0];

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
        <StatLike label="Loans" value={loans.length} sub={`${loans.filter((item) => item.status === "published").length} published`} />
        <StatLike label="Committed" value={loans.reduce((sum, loan) => sum + loan.committed_principal_minor, 0)} sub="Minor units across preview loans" />
        <StatLike label="Risk items" value={loans.filter((item) => ["late", "defaulted"].includes(item.status)).length} sub="Servicing attention" />
      </section>

      <section className="admin-two-col">
        <Card padded>
          <SectionHeader
            action={<Button icon="refresh" onClick={() => { refetchLive(borrowersQuery.refetch); refetchLive(loansQuery.refetch); }} size="sm">Refresh</Button>}
            description="Entity data is admin-entered. Borrower portal accounts do not exist."
            title="Borrowers"
          />
          {borrowers.length ? (
            <div className="table-wrap admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Entity</th>
                    <th>KYB</th>
                    <th>Country</th>
                    <th>Financials</th>
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
                      <td><Chip tone={statusTone(borrower.kyb_status)}>{labelize(borrower.kyb_status)}</Chip></td>
                      <td>{borrower.country || "-"}</td>
                      <td>
                        <div className="col gap-4">
                          <span>Assets <Money amountMinor={borrower.assets_minor} currency={borrower.financials_currency} /></span>
                          <span>Revenue <Money amountMinor={borrower.revenue_last_year_minor} currency={borrower.financials_currency} /></span>
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
          <SectionHeader description="Loans can only publish when required fields, schedule and borrower KYB gates pass." title="Loans" />
          {loans.length ? (
            <div className="table-wrap admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Loan</th>
                    <th>Status</th>
                    <th>Amount</th>
                    <th>Rate</th>
                    <th>LTV</th>
                    <th>Funding deadline</th>
                  </tr>
                </thead>
                <tbody>
                  {loans.map((loan) => (
                    <tr
                      className={selectedLoanId === loan.id ? "admin-selected-row" : ""}
                      key={loan.id}
                      onClick={() => {
                        setSelectedLoanId(loan.id);
                        setSelectedBorrowerId(loan.borrower_id);
                      }}
                    >
                      <td><strong>{loan.title}</strong><span className="mono muted">{loan.id}</span></td>
                      <td><Chip tone={statusTone(loan.status)}>{labelize(loan.status)}</Chip></td>
                      <td><Money amountMinor={loan.principal_minor} currency={loan.currency} /></td>
                      <td>{formatRateBps(loan.interest_rate_bps)}</td>
                      <td>{loan.ltv_bps === null ? "-" : formatRateBps(loan.ltv_bps)}</td>
                      <td>{formatDate(loan.funding_deadline)}</td>
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

      <section className="admin-module-grid">
        <BorrowerCreateForm />
        <LoanCreateForm defaultBorrowerId={selectedBorrowerId} />
        <LoanPublishCloseForm
          defaultCommittedPrincipalMinor={selectedLoan?.committed_principal_minor ?? 0}
          defaultFundingDeadline={selectedLoan?.funding_deadline ?? ""}
          defaultLoanCurrency={selectedLoan?.currency ?? "CHF"}
          defaultLoanId={selectedLoan?.id ?? ""}
          defaultLoanPrincipalMinor={selectedLoan?.principal_minor ?? 0}
          defaultLoanStatus={selectedLoan?.status ?? ""}
          defaultLoanTitle={selectedLoan?.title ?? ""}
        />
        <ServicingOpsForm
          defaultLoanCurrency={selectedLoan?.currency ?? "CHF"}
          defaultLoanId={selectedLoan?.id ?? ""}
          defaultLoanTitle={selectedLoan?.title ?? ""}
        />
        <SecondaryMarketAdminForm />
      </section>
    </div>
  );
}

function BorrowerCreateForm() {
  const [legalName, setLegalName] = useState(adminFormDefaults.borrowerLegalName);
  const [yearFounded, setYearFounded] = useState("2016");
  const [entityType, setEntityType] = useState<BorrowerEntityType>(BorrowerEntityTypeEnum.swiss_company);
  const [kybStatus, setKybStatus] = useState<BorrowerKybStatus>(BorrowerKybStatusEnum.pending);
  const [country, setCountry] = useState("CH");
  const [financialsCurrency, setFinancialsCurrency] = useState("CHF");
  const [assets, setAssets] = useState("");
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1EntitiesAdminBorrowersCreate({
    mutation: { onSuccess: () => setSuccess("Borrower entity was created.") }
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    const data: BorrowerEntityCreateRequest = {
      legal_name: legalName,
      year_founded: intValue(yearFounded, 2000),
      entity_type: entityType,
      kyb_status: kybStatus,
      country,
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
    <Card padded>
      <h2>Create borrower</h2>
      <form className="admin-action-form" onSubmit={submit}>
        <FieldGrid>
          <TextInput label="Legal name" onChange={setLegalName} required value={legalName} />
          <TextInput label="Year founded" onChange={setYearFounded} required value={yearFounded} />
          <SelectInput label="Entity type" onChange={setEntityType} options={Object.values(BorrowerEntityTypeEnum)} value={entityType} />
          <SelectInput label="KYB status" onChange={setKybStatus} options={Object.values(BorrowerKybStatusEnum)} value={kybStatus} />
          <TextInput label="Country" onChange={setCountry} value={country} />
          <TextInput label="Financials currency" onChange={setFinancialsCurrency} value={financialsCurrency} />
          <MoneyMinorInput currency={financialsCurrency} label="Assets minor units" onChange={setAssets} value={assets} />
        </FieldGrid>
        <TextAreaInput label="Admin note" onChange={setNote} value={note} />
        <ActionFooter mutation={mutation} previewMessage={preview} successMessage={success} submitLabel="Create borrower" />
      </form>
    </Card>
  );
}

function LoanCreateForm({ defaultBorrowerId }: { defaultBorrowerId: string }) {
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
  const [fundingDeadline, setFundingDeadline] = useState("");
  const [firstPaymentDate, setFirstPaymentDate] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1LoansAdminLoansCreate({
    mutation: { onSuccess: () => setSuccess("Loan draft was created and schedule validations ran server-side.") }
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
      principal_minor: intValue(principal),
      currency,
      interest_rate_bps: intValue(rateBps),
      term_months: intValue(termMonths),
      repayment_type: repaymentType,
      funding_deadline: fundingDeadline || undefined,
      first_payment_date: firstPaymentDate || undefined,
      collateral_type: collateralType,
      collateral_value_minor: intValue(collateralValue),
      risk_rating: riskRating
    };
    if (isFixturePreview) {
      setPreview(`${title} loan draft would be created for ${borrowerId}.`);
      return;
    }
    mutation.mutate({ data });
  }

  return (
    <Card padded className="admin-wide-card">
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
          <MoneyMinorInput currency={currency} label="Principal minor units" onChange={setPrincipal} required value={principal} />
          <TextInput label="Currency" onChange={setCurrency} required value={currency} />
          <TextInput label="Interest bps" onChange={setRateBps} required value={rateBps} />
          <TextInput label="Term months" onChange={setTermMonths} required value={termMonths} />
          <SelectInput label="Purpose" onChange={setPurpose} options={Object.values(PurposeEnum)} value={purpose} />
          <SelectInput label="Repayment type" onChange={setRepaymentType} options={Object.values(RepaymentTypeEnum)} value={repaymentType} />
          <SelectInput label="Collateral type" onChange={setCollateralType} options={Object.values(CollateralTypeEnum)} value={collateralType} />
          <MoneyMinorInput currency={currency} label="Collateral value minor" onChange={setCollateralValue} required value={collateralValue} />
          <SelectInput label="Risk rating" onChange={setRiskRating} options={Object.values(RiskRatingEnum)} value={riskRating} />
          <TextInput label="Funding deadline" onChange={setFundingDeadline} type="date" value={fundingDeadline} />
          <TextInput label="First payment date" onChange={setFirstPaymentDate} type="date" value={firstPaymentDate} />
        </FieldGrid>
        <TextAreaInput label="Investor summary" onChange={setSummary} required value={summary} />
        <ActionFooter mutation={mutation} previewMessage={preview} successMessage={success} submitLabel="Create loan draft" />
      </form>
    </Card>
  );
}

function LoanPublishCloseForm({
  defaultCommittedPrincipalMinor,
  defaultFundingDeadline,
  defaultLoanCurrency,
  defaultLoanId,
  defaultLoanPrincipalMinor,
  defaultLoanStatus,
  defaultLoanTitle
}: {
  defaultCommittedPrincipalMinor: number;
  defaultFundingDeadline: string;
  defaultLoanCurrency: string;
  defaultLoanId: string;
  defaultLoanPrincipalMinor: number;
  defaultLoanStatus: string;
  defaultLoanTitle: string;
}) {
  const [loanId, setLoanId] = useState(defaultLoanId);
  const [loanQuery, setLoanQuery] = useState(defaultLoanId);
  const [note, setNote] = useState("");
  const [closeReason, setCloseReason] = useState("Accepted funding close after admin review.");
  const [investorMessage, setInvestorMessage] = useState("Loan funding has closed. Your assigned claim is now active.");
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
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const publish = useV1LoansAdminLoansPublishCreate();
  const closeFunding = useV1MarketplacePrimaryAdminLoansCloseFundingCreate({
    mutation: { onSuccess: () => setSuccess("Funding close was submitted.") }
  });
  const cancelFunding = useV1MarketplacePrimaryAdminLoansCancelFundingCreate({
    mutation: { onSuccess: () => setSuccess("Funding cancellation was submitted.") }
  });
  const expiryScan = useV1MarketplacePrimaryAdminLoansExpiryScanCreate({
    mutation: {
      onSuccess: (data) => {
        setSuccess(
          `Expiry scan cancelled ${data.cancelled_count} campaign(s) and skipped ${data.skipped_count}.`
        );
      }
    }
  });
  const releaseOrder = useV1MarketplacePrimaryAdminOrdersReleaseBalanceCreate();

  useEffect(() => {
    setLoanId(defaultLoanId);
    setLoanQuery(defaultLoanId);
  }, [defaultLoanId]);

  function publishLoan() {
    if (isFixturePreview) {
      setPreview(`Loan ${loanId} would be published.`);
      return;
    }
    publish.mutate({ loanId, data: { note } });
  }

  function closeLoan() {
    const data: PrimaryLoanCloseRequest = {
      reason: closeReason,
      investor_message: investorMessage,
      idempotency_key: idempotencyKey("close-funding")
    };
    if (isFixturePreview) {
      setPreview(`Funding close would run for ${loanId}.`);
      return;
    }
    closeFunding.mutate({ loanId, data });
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
      loan_ids: scanSelectedOnly && loanId ? [loanId] : undefined,
      reason: expiryReason || undefined,
      investor_message: expiryInvestorMessage || undefined,
      idempotency_key: idempotencyKey("expiry-scan")
    };
    if (isFixturePreview) {
      setPreview(
        scanSelectedOnly && loanId
          ? `Expiry scan would evaluate selected loan ${loanId}.`
          : "Expiry scan would evaluate all expired published campaigns."
      );
      return;
    }
    expiryScan.mutate({ data });
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
    <Card padded>
      <h2>Primary marketplace operations</h2>
      <div className="admin-action-form">
        <div className="admin-context-bar">
          <span>Selected loan</span>
          <strong>{defaultLoanTitle || "No loan selected"}</strong>
          <code>{loanId || "-"}</code>
        </div>
        <div className="admin-context-bar">
          <span>Status</span>
          <Chip tone={statusTone(defaultLoanStatus || "draft")}>
            {labelize(defaultLoanStatus || "draft")}
          </Chip>
          <span>Funding deadline {defaultFundingDeadline ? formatDate(defaultFundingDeadline) : "-"}</span>
          <span>
            Committed{" "}
            <Money amountMinor={defaultCommittedPrincipalMinor} currency={defaultLoanCurrency} /> /{" "}
            <Money amountMinor={defaultLoanPrincipalMinor} currency={defaultLoanCurrency} />
          </span>
        </div>
        <LoanLookupInput
          onChange={setLoanId}
          onQueryChange={setLoanQuery}
          query={loanQuery}
          required
          value={loanId}
        />
        <TextAreaInput label="Publish note" onChange={setNote} value={note} />
        <Button disabled={publish.isPending} onClick={publishLoan} variant="primary">Publish loan</Button>
        <TextAreaInput label="Funding close reason" onChange={setCloseReason} value={closeReason} />
        <TextAreaInput label="Investor message" onChange={setInvestorMessage} value={investorMessage} />
        <OperationConfirmButton
          confirmLabel="Close funding"
          description="Closing funding creates holdings, moves escrow into borrower payable and Garanta fee revenue, and blocks later order releases for the closed loan."
          details={[
            { label: "Loan", value: loanId || "-" },
            { label: "Reason", value: closeReason },
            { label: "Investor message", value: investorMessage }
          ]}
          disabled={closeFunding.isPending || !loanId}
          onConfirm={closeLoan}
          title="Confirm primary funding close"
          variant="primary"
        >
          Close funding
        </OperationConfirmButton>
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
            { label: "Loan", value: loanId || "-" },
            { label: "Status", value: labelize(defaultLoanStatus || "-") },
            { label: "Committed principal", value: `${defaultCommittedPrincipalMinor} minor units` },
            { label: "Reason", value: cancelReason },
            { label: "Investor message", value: cancelInvestorMessage || "-" }
          ]}
          disabled={cancelFunding.isPending || !loanId}
          onConfirm={cancelLoan}
          title="Confirm primary funding cancellation"
          variant="danger"
        >
          Cancel funding
        </OperationConfirmButton>
        <FieldGrid>
          <TextInput label="Expiry scan as-of date" onChange={setExpiryAsOfDate} type="date" value={expiryAsOfDate} />
          <Field hint="When enabled, only the selected loan ID is scanned. Disable to scan all expired published campaigns.">
            <label className="check-row">
              <input checked={scanSelectedOnly} onChange={(event) => setScanSelectedOnly(event.target.checked)} type="checkbox" />
              Scan selected loan only
            </label>
          </Field>
        </FieldGrid>
        <TextAreaInput
          hint="Optional. If blank, the backend uses the standard expiry reason."
          label="Expiry scan reason override"
          onChange={setExpiryReason}
          value={expiryReason}
        />
        <TextAreaInput
          hint="Optional. If blank, the backend uses the standard investor message."
          label="Expiry scan investor message override"
          onChange={setExpiryInvestorMessage}
          value={expiryInvestorMessage}
        />
        <OperationConfirmButton
          confirmLabel="Run expiry scan"
          description="The scan cancels published campaigns whose funding deadline is before the as-of date by calling the same conservation-checked cancellation backend primitive."
          details={[
            { label: "As-of date", value: expiryAsOfDate },
            { label: "Scope", value: scanSelectedOnly && loanId ? `Selected loan ${loanId}` : "All expired published campaigns" }
          ]}
          disabled={expiryScan.isPending || (scanSelectedOnly && !loanId)}
          onConfirm={scanExpiredCampaigns}
          title="Confirm funding expiry scan"
          variant="danger"
        >
          Run expiry scan
        </OperationConfirmButton>
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
        {publish.error || closeFunding.error || cancelFunding.error || expiryScan.error || releaseOrder.error ? <Banner tone="bad" title="Marketplace operation failed">{errorMessage(publish.error || closeFunding.error || cancelFunding.error || expiryScan.error || releaseOrder.error)}</Banner> : null}
        {preview ? <Banner tone="info" title="Preview action recorded">{preview}</Banner> : null}
        {success ? <Banner tone="ok" title="Marketplace operation submitted">{success}</Banner> : null}
      </div>
    </Card>
  );
}

function ServicingOpsForm({
  defaultLoanCurrency,
  defaultLoanId,
  defaultLoanTitle
}: {
  defaultLoanCurrency: string;
  defaultLoanId: string;
  defaultLoanTitle: string;
}) {
  const [loanId, setLoanId] = useState(defaultLoanId);
  const [loanQuery, setLoanQuery] = useState(defaultLoanId);
  const [amountMinor, setAmountMinor] = useState("1845000");
  const [bookingDate, setBookingDate] = useState(today);
  const [valueDate, setValueDate] = useState(today);
  const [payerName, setPayerName] = useState(adminFormDefaults.borrowerName);
  const [warningAck, setWarningAck] = useState(true);
  const [riskBody, setRiskBody] = useState("Public servicing update for affected investors.");
  const [recoveryGross, setRecoveryGross] = useState("1000000");
  const [preview, setPreview] = useState<string | null>(null);
  const repayment = useV1ServicingAdminBorrowerRepaymentsCreate();
  const scan = useV1ServicingAdminStatusScanCreate();
  const riskNote = useV1ServicingAdminRiskNotesCreate();
  const recovery = useV1ServicingAdminRecoveriesCreate();

  useEffect(() => {
    setLoanId(defaultLoanId);
    setLoanQuery(defaultLoanId);
  }, [defaultLoanId]);

  function submitRepayment() {
    const data: BorrowerRepaymentRecordRequest = {
      loan_id: loanId,
      amount_minor: intValue(amountMinor),
      booking_date: bookingDate,
      value_date: valueDate,
      collection_account_identifier: defaultCollectionAccount,
      payer_name: payerName,
      warning_acknowledged: warningAck,
      idempotency_key: idempotencyKey("borrower-repayment")
    };
    if (isFixturePreview) {
      setPreview(`Borrower repayment would be recorded for ${loanId}.`);
      return;
    }
    repayment.mutate({ data });
  }

  function submitScan() {
    const data: LoanServicingStatusScanRequest = { as_of_date: valueDate, loan_ids: loanId ? [loanId] : undefined };
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

  function submitRecovery() {
    const gross = intValue(recoveryGross);
    const data: LoanRecoveryPaymentRecordRequest = {
      loan_id: loanId,
      gross_recovered_minor: gross,
      externally_deducted_costs_minor: 0,
      third_party_costs_from_received_minor: 0,
      recovery_fee_applied: false,
      principal_recovered_minor: gross,
      booking_date: bookingDate,
      value_date: valueDate,
      collection_account_identifier: defaultCollectionAccount,
      payer_name: payerName,
      idempotency_key: idempotencyKey("recovery")
    };
    if (isFixturePreview) {
      setPreview(`Recovery payment would be distributed for ${loanId}.`);
      return;
    }
    recovery.mutate({ data });
  }

  return (
    <Card padded className="admin-wide-card">
      <h2>Servicing and recovery</h2>
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
          <MoneyMinorInput currency={defaultLoanCurrency} label="Amount minor units" onChange={setAmountMinor} value={amountMinor} />
          <TextInput label="Booking date" onChange={setBookingDate} type="date" value={bookingDate} />
          <TextInput label="Value date" onChange={setValueDate} type="date" value={valueDate} />
          <TextInput label="Payer name" onChange={setPayerName} value={payerName} />
        </FieldGrid>
        <label className="check-row">
          <input checked={warningAck} onChange={(event) => setWarningAck(event.target.checked)} type="checkbox" />
          Warning acknowledged for partial/irregular borrower repayment.
        </label>
        <div className="row gap-8 wrap">
          <Button disabled={repayment.isPending} onClick={submitRepayment} variant="primary">Record repayment</Button>
          <Button disabled={scan.isPending} onClick={submitScan}>Run status scan</Button>
        </div>
        <TextAreaInput label="Risk note body" onChange={setRiskBody} value={riskBody} />
        <div className="row gap-8 wrap">
          <Button disabled={riskNote.isPending} onClick={submitRiskNote}>Publish public note</Button>
          <MoneyMinorInput currency={defaultLoanCurrency} label="Recovery gross minor" onChange={setRecoveryGross} value={recoveryGross} />
          <OperationConfirmButton
            confirmLabel="Record recovery"
            description="Recording a recovery credits affected investor balance lots, applies the recovery waterfall, and reduces current holding principal according to backend allocation rules."
            details={[
              { label: "Loan", value: loanId || "-" },
              { label: "Gross recovery", value: `${recoveryGross} minor units` },
              { label: "Value date", value: valueDate }
            ]}
            disabled={recovery.isPending || !loanId}
            onConfirm={submitRecovery}
            title="Confirm recovery payment"
            variant="primary"
          >
            Record recovery
          </OperationConfirmButton>
        </div>
        {repayment.error || scan.error || riskNote.error || recovery.error ? (
          <Banner tone="bad" title="Servicing action failed">
            {errorMessage(repayment.error || scan.error || riskNote.error || recovery.error)}
          </Banner>
        ) : null}
        {preview ? <Banner tone="info" title="Preview action recorded">{preview}</Banner> : null}
      </div>
    </Card>
  );
}

function SecondaryMarketAdminForm() {
  const [listingId, setListingId] = useState(adminFormDefaults.secondaryListingId);
  const [listingQuery, setListingQuery] = useState(adminFormDefaults.secondaryListingId);
  const [reason, setReason] = useState("Admin-reviewed non-standard listing disclosure.");
  const [disclosure, setDisclosure] = useState("Loan is non-performing. Review public note and days-past-due before purchase.");
  const [preview, setPreview] = useState<string | null>(null);
  const approve = useV1MarketplaceSecondaryAdminListingsApproveCreate();
  const reject = useV1MarketplaceSecondaryAdminListingsRejectCreate();
  const remove = useV1MarketplaceSecondaryAdminListingsRemoveCreate();

  function approveListing() {
    const data: SecondaryMarketListingApproveRequest = { reason, disclosure_note: disclosure, idempotency_key: idempotencyKey("sm-approve") };
    if (isFixturePreview) {
      setPreview(`Listing ${listingId} would be approved with disclosure.`);
      return;
    }
    approve.mutate({ listingId, data });
  }

  function rejectListing() {
    const data: SecondaryMarketListingRejectRequest = { reason, idempotency_key: idempotencyKey("sm-reject") };
    if (isFixturePreview) {
      setPreview(`Listing ${listingId} would be rejected.`);
      return;
    }
    reject.mutate({ listingId, data });
  }

  function removeListing() {
    const data: SecondaryMarketListingRemoveRequest = { reason, idempotency_key: idempotencyKey("sm-remove") };
    if (isFixturePreview) {
      setPreview(`Listing ${listingId} would be removed.`);
      return;
    }
    remove.mutate({ listingId, data });
  }

  return (
    <Card padded>
      <h2>Secondary-market approvals</h2>
      <div className="admin-action-form">
        <SecondaryListingLookupInput
          onChange={setListingId}
          onQueryChange={setListingQuery}
          query={listingQuery}
          required
          value={listingId}
        />
        <TextAreaInput label="Reason" onChange={setReason} value={reason} />
        <TextAreaInput label="Buyer disclosure note" onChange={setDisclosure} value={disclosure} />
        <div className="row gap-8 wrap">
          <OperationConfirmButton
            confirmLabel="Approve listing"
            description="Approving a non-standard listing makes it visible to eligible buyers with the provided disclosure note and additional acknowledgement."
            details={[
              { label: "Listing", value: listingId || "-" },
              { label: "Reason", value: reason },
              { label: "Disclosure", value: disclosure }
            ]}
            disabled={approve.isPending || !listingId}
            onConfirm={approveListing}
            title="Confirm secondary listing approval"
            variant="primary"
          >
            Approve listing
          </OperationConfirmButton>
          <OperationConfirmButton
            confirmLabel="Reject listing"
            description="Rejecting a listing keeps it hidden and records the admin decision in the audit trail."
            details={[
              { label: "Listing", value: listingId || "-" },
              { label: "Reason", value: reason }
            ]}
            disabled={reject.isPending || !listingId}
            onConfirm={rejectListing}
            title="Confirm listing rejection"
            variant="danger"
          >
            Reject
          </OperationConfirmButton>
          <OperationConfirmButton
            confirmLabel="Remove listing"
            description="Removing a listing takes it out of buyer visibility and records the operational reason."
            details={[
              { label: "Listing", value: listingId || "-" },
              { label: "Reason", value: reason }
            ]}
            disabled={remove.isPending || !listingId}
            onConfirm={removeListing}
            title="Confirm listing removal"
          >
            Remove
          </OperationConfirmButton>
        </div>
        {approve.error || reject.error || remove.error ? <Banner tone="bad" title="Secondary action failed">{errorMessage(approve.error || reject.error || remove.error)}</Banner> : null}
        {preview ? <Banner tone="info" title="Preview action recorded">{preview}</Banner> : null}
      </div>
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
              <table className="admin-table">
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
  const versionsQuery = useDocumentTemplateVersionsData({ category });
  const versions = versionsQuery.data ?? [];

  return (
    <div className="admin-content">
      <PreviewNotice>Superadmin settings use dummy templates in preview. Live template changes create immutable document versions.</PreviewNotice>
      <section className="admin-two-col">
        <Card padded>
          <SectionHeader
            action={<Button icon="refresh" onClick={() => refetchLive(versionsQuery.refetch)} size="sm">Refresh</Button>}
            description="Versioned clickwrap templates by category. Published versions are immutable evidence anchors."
            title="Document templates"
          />
          <SelectInput label="Category" onChange={setCategory} options={Object.values(CategoryEnum)} value={category} />
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
        <DocumentTemplateForm category={category} defaultVersionId={versions[0]?.id ?? ""} />
      </section>
      <section className="admin-two-col">
        <AdminUserCreateForm />
        <AccountAccessForm />
      </section>
    </div>
  );
}

function DocumentTemplateForm({ category, defaultVersionId }: { category: DocumentCategory; defaultVersionId: string }) {
  const [name, setName] = useState("BANXUM Terms Template");
  const [title, setTitle] = useState("BANXUM Terms");
  const [body, setBody] = useState("Advisor-approved body will be inserted here.");
  const [checkboxes, setCheckboxes] = useState("I accept these terms.\nI understand the platform risks.");
  const [publishNow, setPublishNow] = useState(false);
  const [versionId, setVersionId] = useState(defaultVersionId);
  const [versionQuery, setVersionQuery] = useState(defaultVersionId);
  const [legalRef, setLegalRef] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const create = useV1DocumentsAdminTemplatesVersionsCreate();
  const publish = useV1DocumentsAdminTemplatesVersionsPublishCreate();

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
    <Card padded>
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
    </Card>
  );
}

function AdminUserCreateForm() {
  const [email, setEmail] = useState(adminFormDefaults.adminEmail);
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState(adminFormDefaults.adminFullName);
  const [preview, setPreview] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | undefined>();
  const mutation = useV1AuthAdminUsersCreate({
    mutation: { onSuccess: () => setSuccess("Admin user was created. Password reset remains superadmin-managed.") }
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
    <Card padded>
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
    </Card>
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
