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
  useV1LoansAdminLoansPartialUpdate,
  useV1LoansAdminLoansPublishCreate,
  useV1MarketplacePrimaryAdminLoansCancelFundingCreate,
  useV1MarketplacePrimaryAdminLoansCloseFundingCreate,
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
  useV1ServicingAdminBorrowerRepaymentsCreate,
  useV1ServicingAdminRecoveriesCreate,
  useV1ServicingAdminRiskNotesCreate,
  useV1ServicingAdminStatusScanCreate,
  type AccountAccessChangeRequest,
  type AccountAccessChangeRequestReasonCodeEnum as AccountAccessReasonCode,
  type AdminLookupResult,
  type AdminUserDocument,
  type AdminUserDocumentArtifactResponse,
  type AdminUserDirectoryRow,
  type AdminUserCreateRequest,
  type BalanceAgeingScanRequest,
  type BorrowerEntity,
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
  type KycAdminCase,
  type KycManualReviewDecisionRequest,
  type KycManualReviewDecisionRequestReasonCodeEnum as KycReasonCode,
  type LenderDepositDeclareRequest,
  type Loan,
  type LoanCreateRequest,
  type LoanRecoveryPaymentRecordRequest,
  type LoanRiskNoteCreateRequest,
  type LoanServicingStatusScanRequest,
  type NewStatusEnum as AccountNewStatus,
  type PatchedBorrowerEntityUpdateRequest,
  type PatchedLoanUpdateRequest,
  type PeriodPresetEnum as ReportPeriodPreset,
  type PurposeEnum as LoanPurpose,
  type QaDevModeState,
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
  type SecondaryMarketListingRemoveRequest,
  type V1EntitiesAdminBorrowersListKybStatus as BorrowerListKybStatus,
  type V1LoansAdminLoansListStatus as LoanListStatus
} from "../api/generated/banxumApi";
import { writeReadonlyImpersonation } from "../api/client/impersonation";
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
  return (
    <span className="admin-action-note" title={`${label} records are retained for audit evidence.`}>
      No delete
    </span>
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
  const [borrowerSearch, setBorrowerSearch] = useState("");
  const [borrowerKybStatus, setBorrowerKybStatus] = useState<BorrowerListKybStatus | "">("");
  const [loanSearch, setLoanSearch] = useState("");
  const [loanStatus, setLoanStatus] = useState<LoanListStatus | "">("");
  const debouncedBorrowerSearch = useDebouncedValue(borrowerSearch);
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
  const borrowers = useMemo(() => borrowersQuery.data ?? [], [borrowersQuery.data]);
  const loans = useMemo(() => loansQuery.data ?? [], [loansQuery.data]);
  const [selectedBorrowerId, setSelectedBorrowerId] = useState("");
  const [selectedLoanId, setSelectedLoanId] = useState("");
  const [showBorrowerCreate, setShowBorrowerCreate] = useState(false);
  const [showLoanCreate, setShowLoanCreate] = useState(false);
  const [editingBorrower, setEditingBorrower] = useState<BorrowerEntity | null>(null);
  const [editingLoan, setEditingLoan] = useState<Loan | null>(null);
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

      <section className="admin-stack">
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
            searchPlaceholder="Search legal name, registration, country, UUID"
            title="Borrowers"
          />
          {borrowersQuery.error ? <Banner tone="bad" title="Could not load borrowers">{errorMessage(borrowersQuery.error)}</Banner> : null}
          {borrowers.length ? (
            <div className="table-wrap admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Entity</th>
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
                <Button icon="plus" onClick={() => setShowLoanCreate(true)} size="sm" variant="primary">Create loan</Button>
              </div>
            }
            description="Loans can only publish when required fields, schedule, funding-window and borrower KYB gates pass."
            filters={
              <select
                aria-label="Filter loans by status"
                onChange={(event) => setLoanStatus(event.target.value as LoanListStatus | "")}
                value={loanStatus}
              >
                <option value="">All loan statuses</option>
                {["draft", "published", "funded", "late", "defaulted", "repaid", "written_off", "cancelled"].map((status) => (
                  <option key={status} value={status}>{labelize(status)}</option>
                ))}
              </select>
            }
            onSearch={setLoanSearch}
            search={loanSearch}
            searchPlaceholder="Search title, borrower, status, UUID"
            title="Loans"
          />
          {loansQuery.error ? <Banner tone="bad" title="Could not load loans">{errorMessage(loansQuery.error)}</Banner> : null}
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
                        setSelectedBorrowerId(loan.borrower_id);
                      }}
                    >
                      <td><strong>{loan.title}</strong><span className="mono muted">{loan.id}</span></td>
                      <td><Chip tone={statusTone(loan.status)}>{labelize(loan.status)}</Chip></td>
                      <td><Money amountMinor={loan.principal_minor} currency={loan.currency} /></td>
                      <td>{formatRateBps(loan.interest_rate_bps)}</td>
                      <td>{loan.ltv_bps === null ? "-" : formatRateBps(loan.ltv_bps)}</td>
                      <td>{formatDate(loan.funding_deadline)}</td>
                      <td>
                        <div className="row gap-8 wrap" onClick={(event) => event.stopPropagation()}>
                          <Button onClick={() => setEditingLoan(loan)} size="sm">Edit</Button>
                          <Button onClick={() => setSelectedLoanId(loan.id)} size="sm">Manage</Button>
                          {loan.status === "published" ? <span className="admin-action-note">Cancel via operations</span> : <UnsupportedRemoveNote label="Loan" />}
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

      <section className="admin-module-grid">
        <LoanPublishCloseForm
          defaultCommittedPrincipalMinor={selectedLoan?.committed_principal_minor ?? 0}
          defaultFundingDeadline={selectedLoan?.funding_deadline ?? ""}
          defaultLoanCurrency={selectedLoan?.currency ?? "CHF"}
          defaultLoanId={selectedLoan?.id ?? ""}
          defaultLoanPrincipalMinor={selectedLoan?.principal_minor ?? 0}
          defaultLoanStatus={selectedLoan?.status ?? ""}
          defaultLoanTitle={selectedLoan?.title ?? ""}
        />
        <SecondaryMarketAdminForm />
        <ServicingOpsForm
          defaultLoanCurrency={selectedLoan?.currency ?? "CHF"}
          defaultLoanId={selectedLoan?.id ?? ""}
          defaultLoanTitle={selectedLoan?.title ?? ""}
        />
      </section>
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

function BorrowerCreateForm({ onCreated }: { onCreated?: () => void }) {
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
          <TextInput label="Financials currency" onChange={setFinancialsCurrency} value={financialsCurrency} />
          <MoneyMinorInput currency={financialsCurrency} label="Assets minor units" onChange={setAssets} value={assets} />
        </FieldGrid>
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
          <TextInput label="Financials currency" onChange={setFinancialsCurrency} value={financialsCurrency} />
          <MoneyMinorInput currency={financialsCurrency} label="Assets minor units" onChange={setAssets} value={assets} />
          <MoneyMinorInput currency={financialsCurrency} label="Liabilities minor units" onChange={setLiabilities} value={liabilities} />
          <MoneyMinorInput currency={financialsCurrency} label="Revenue last year minor" onChange={setRevenue} value={revenue} />
          <MoneyMinorInput currency={financialsCurrency} label="Profit last year minor" onChange={setProfit} value={profit} />
        </FieldGrid>
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
  const [fundingDeadline, setFundingDeadline] = useState("");
  const [firstPaymentDate, setFirstPaymentDate] = useState("");
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
    </div>
  );
}

function LoanEditForm({ loan, onSaved }: { loan: Loan; onSaved?: () => void }) {
  const [title, setTitle] = useState(loan.title);
  const [summary, setSummary] = useState(loan.investor_summary);
  const [principal, setPrincipal] = useState(String(loan.principal_minor));
  const [rateBps, setRateBps] = useState(String(loan.interest_rate_bps));
  const [termMonths, setTermMonths] = useState(String(loan.term_months));
  const [purpose, setPurpose] = useState<LoanPurpose>(loan.purpose as LoanPurpose);
  const [repaymentType, setRepaymentType] = useState<LoanRepaymentType>(loan.repayment_type as LoanRepaymentType);
  const [collateralType, setCollateralType] = useState<LoanCollateralType>(loan.collateral_type as LoanCollateralType);
  const [collateralValue, setCollateralValue] = useState(String(loan.collateral_value_minor));
  const [riskRating, setRiskRating] = useState<LoanRiskRating>(loan.risk_rating as LoanRiskRating);
  const [fundingDeadline, setFundingDeadline] = useState(loan.funding_deadline);
  const [firstPaymentDate, setFirstPaymentDate] = useState(loan.first_payment_date);
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
      principal_minor: intValue(principal),
      interest_rate_bps: intValue(rateBps),
      term_months: intValue(termMonths),
      repayment_type: repaymentType,
      funding_deadline: fundingDeadline,
      first_payment_date: firstPaymentDate,
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
            Backend policy allows only a principal reduction with an investor message once committed investments exist.
          </Banner>
        ) : null}
        <FieldGrid>
          <TextInput label="Title" onChange={setTitle} required value={title} />
          <MoneyMinorInput currency={loan.currency} label="Principal minor units" onChange={setPrincipal} required value={principal} />
          <TextInput label="Interest bps" onChange={setRateBps} required value={rateBps} />
          <TextInput label="Term months" onChange={setTermMonths} required value={termMonths} />
          <SelectInput label="Purpose" onChange={setPurpose} options={Object.values(PurposeEnum)} value={purpose} />
          <SelectInput label="Repayment type" onChange={setRepaymentType} options={Object.values(RepaymentTypeEnum)} value={repaymentType} />
          <SelectInput label="Collateral type" onChange={setCollateralType} options={Object.values(CollateralTypeEnum)} value={collateralType} />
          <MoneyMinorInput currency={loan.currency} label="Collateral value minor" onChange={setCollateralValue} required value={collateralValue} />
          <SelectInput label="Risk rating" onChange={setRiskRating} options={Object.values(RiskRatingEnum)} value={riskRating} />
          <TextInput label="Funding deadline" onChange={setFundingDeadline} type="date" value={fundingDeadline} />
          <TextInput label="First payment date" onChange={setFirstPaymentDate} type="date" value={firstPaymentDate} />
        </FieldGrid>
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
