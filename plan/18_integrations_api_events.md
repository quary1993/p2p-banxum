# Integrations, APIs, and Event Architecture

Status: Draft. Updated with identity, balance, FX, origination, marketplace, servicing, document, reporting, Bexio export, SendGrid, Twilio, authentication, and integration-architecture decisions on 2026-05-29.

## Purpose

Define internal APIs, external integrations, event contracts, idempotency, webhooks, and data exchange patterns across BANXUM.

## Scope

- Didit KYC/AML integration for natural-person lenders.
- Payment/banking provider integration.
- Future e-signature provider integration, not used in v1.
- SendGrid email integration.
- SendGrid contact/list integration for future marketing newsletters.
- Twilio phone verification integration.
- Accounting system integration/export.
- Future credit data providers, if later needed.
- Admin/reporting exports.
- Future BI/data warehouse export.
- Future internal event bus if scale or integration needs require it.
- Append-only event table and background jobs.
- Webhook ingestion and delivery.
- Future public or partner APIs if a concrete use case appears.

## Integration Principles

- Vendor integrations use adapters to isolate external API changes.
- Every external callback is authenticated, validated, idempotent, and logged.
- External commands use idempotency keys.
- Events are append-only and schema-versioned.
- Business workflows do not depend solely on provider UI state.
- Provider outages degrade gracefully and create operational work items.
- Sensitive payloads are minimized and encrypted where appropriate.

## Decisions

### INT-DEC-001: Modular Monolith Architecture

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology.

Decision:
The v1 platform should be implemented as a modular monolith.

Modules should have clear domain boundaries, internal APIs/services, and separate database ownership conventions where useful, but they do not need to be deployed as separate microservices at launch.

Rationale:
A modular monolith keeps deployment and operations simple while preserving the option to extract services later if load, team structure, or regulatory/vendor boundaries justify it.

### INT-DEC-002: Append-Only Event Table and Background Jobs

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology.

Decision:
A dedicated external event bus is not required at launch.

The platform should use an append-only event table plus background workers/jobs for asynchronous processing, retries, notifications, exports, reconciliation tasks, balance ageing reminders, FX polling, and webhook follow-up.

Events must be schema-versioned and append-only. Financial events must follow the immutability requirements in the security and payments modules.

Rationale:
An append-only event table fits the launch architecture and audit needs without adding unnecessary distributed-system complexity.

Follow-ups:
Define event schema versioning, job retry policy, dead-letter handling, and operational dashboards/alerts.

### INT-DEC-003: Didit Integration UX Remains Flexible

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / compliance / technology.

Decision:
The Didit user-facing integration method remains flexible at planning stage. Hosted redirect, embedded iframe, SDK/mobile flow, or a mixed approach may be selected during implementation based on Didit capabilities, UX, device coverage, and compliance needs.

Rationale:
Didit is the selected KYC/AML provider, but the exact presentation mode should be chosen with implementation constraints and provider configuration in view.

### INT-DEC-004: No Public API at Launch

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / technology.

Decision:
No public or partner API is required at launch.

The platform only needs internal APIs for the investor portal, admin portal, background workers, provider adapters, exports, and operational tooling.

Rationale:
Launch workflows are portal-operated and admin-operated. Public API design would add security, support, versioning, and documentation burden without a current use case.

### INT-DEC-005: Webhook Retry and Failure Handling

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta technology / operations.

Decision:
Webhook processing and outbound callback-style delivery, where used, must retry automatically after transient failure.

Repeated failures should move the item to a failed/dead-letter state and create an admin/tech alert or operational work item. Webhook processing must remain authenticated, idempotent, timestamp-validated where applicable, and fully logged.

Rationale:
Provider and network failures are expected operational cases. Retry plus visible failure handling prevents silent data loss.

### INT-DEC-006: Banking/Payment Integration Is Manual at Launch and Future-Ready

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta finance / operations / technology.

Decision:
Banking/payment integration is manual at launch. Admin declares external bank operations through manual entry and operational evidence uploads, then reconciles bank-stated balances against platform ledger balances by currency.

The architecture should be future-ready for bank statement import and bank/API-feed automation if the selected bank/payment partner later supports it. Automation must preserve the same matching, evidence, exception-handling, approval, and audit rules as the manual launch workflow.

Rationale:
Manual bank-operation declaration matches the first operating model, while adapter boundaries avoid rework when bank automation becomes available.

### INT-DEC-007: FX Rate Integration and Quote Sanity Controls

Status: Accepted.
Date: 2026-05-22. Updated 2026-06-01.
Owner: Garanta finance / product / technology.

Decision:
FX executable quotes are fetched live from Yahoo Finance when the investor requests a currency exchange quote, subject to final access-method and terms-of-use confirmation. The accepted executable quote is fixed for 1 minute. If the investor does not approve within that window, the quote expires and must be refreshed.

The platform also polls FX rates in the background for display-only indicative rates. Display-only ticks must not be used for execution unless converted into a fresh executable quote.

Launch sanity controls:

- Reject missing, zero, negative, non-numeric, infinite, malformed, or wrong-currency-pair rates.
- Reject stale provider responses outside the configured freshness window.
- Reject or hold executable quotes if the quote differs by more than a configured threshold from a recent trusted reference. Launch reference threshold: +/- 5% compared with the previous-day average from the same Yahoo Finance provider should trigger an alert and should not be auto-executed unless an admin/tech-reviewed fallback policy permits it.
- For display-only polling, if a new tick differs by more than +/- 2% from the last accepted display tick for the same pair, invalidate and skip that tick rather than showing it.
- Use configurable min/max allowed rate bounds per currency pair where available.
- If provider bid/ask or reverse-pair data is available, check inverse consistency within a small configurable tolerance.
- Optionally compare against a fallback provider/reference source in a later version if configured; not required at launch.
- Record provider, pair, raw rate, adjusted fee rate, quote timestamp, expiry timestamp, sanity-check result, and source payload reference for every executable quote.

Rationale:
FX quote errors can create direct financial loss and poor customer outcomes. A 1-minute quote lock gives the investor enough time to approve while limiting rate risk, and sanity checks reduce the risk of executing against broken provider data.

Follow-ups:
Validate Yahoo Finance API/access terms, define polling interval, previous-day-average calculation, min/max pair bounds, exact quote expiry behavior in the UI, and alert recipients.

### INT-DEC-008: No Additional Launch Integrations

Status: Accepted.
Date: 2026-05-22.
Owner: Garanta product / technology.

Decision:
No additional third-party integrations are currently required beyond Didit, SendGrid, Twilio, the FX rate provider, banking/payment partner/manual statement handling, and accounting/report exports.

Rationale:
The known integration set is enough for the launch scope.

## Core Events

- UserRegistered.
- InvestorMagicLinkRequested.
- InvestorMagicLinkSent.
- InvestorMagicLinkConsumed.
- InvestorMagicLinkExpired.
- AdminUserCreated.
- AdminUserDisabled.
- AdminPasswordResetBySuperadmin.
- AdminEmailCodeRequested.
- AdminEmailCodeSent.
- AdminEmailCodeVerified.
- AdminEmailCodeFailed.
- SuperadminCredentialConfigured.
- PhoneVerificationRequested.
- PhoneVerificationCompleted.
- MarketingConsentCaptured.
- MarketingConsentWithdrawn.
- SendGridContactSynced.
- KycSessionCreated.
- KycDecisionReceived.
- KycProviderReportDownloaded.
- KycRawWebhookPayloadStored.
- KycManualStatusUpdated.
- KycEvidencePackageGenerated.
- KybApprovalRecorded.
- EntityVerified.
- LoanRecordCreated.
- OfflineCreditApprovalRecorded.
- ListingPublished.
- InvestmentOrderCreated.
- PaymentReceivedPendingValidation.
- InvestorDepositCredited.
- InvestorBalanceCredited.
- InvestorBalanceDebited.
- BalanceAgeingReminderDue.
- BalanceAgeingReminderSent.
- BalancePenaltyApplied.
- PenaltyModeEnabled.
- PenaltyModeDisabled.
- ForcedWithdrawalAttempted.
- ForcedWithdrawalProcessed.
- WithdrawalFinalized.
- OfflineWithdrawalReturnNoted.
- WithdrawalRequested.
- WithdrawalProcessed.
- CurrencyExchangeQuoteRequested.
- FxExecutableQuoteIssued.
- FxExecutableQuoteExpired.
- FxDisplayRatePolled.
- FxDisplayRateRejected.
- FxQuoteSanityCheckFailed.
- CurrencyExchangeAccepted.
- CurrencyExchangeCompleted.
- CurrencyExchangeFailed.
- FxDeltaReportGenerated.
- ExternalFxExecutionRecorded.
- InvestmentOrderValidated.
- InvestmentOrderPartiallyValidated.
- InvestmentOrderClosedNotInvested.
- LegalEntityLenderInvestmentEntered.
- OversubscriptionRefundDue.
- PaymentReceived.
- LoanFunded.
- FundsReleased.
- RepaymentDue.
- BorrowerRepaymentReceived.
- RepaymentAmountWarningRaised.
- RepaymentScheduleRecalculated.
- InvestorDistributionCreated.
- InvestorDistributionCreditedToBalance.
- InternalPayoutArtifactGenerated.
- LenderPaymentNotificationSent.
- EarlyRepaymentRecorded.
- LoanOperationalChangeRecorded.
- LoanRepaid.
- SecondaryMarketListingCreated.
- SecondaryMarketBuyerPaymentReceived.
- SecondaryMarketPurchaseConfirmed.
- SecondaryMarketMakerTakerFeesCharged.
- SecondaryMarketTransferSettled.
- SecondaryMarketSellerProceedsCreditedToBalance.
- LoanLate.
- LoanDefaulted.
- DocumentAccepted.
- DocumentPackageGenerated.
- DocumentPackageSent.
- EmailTemplateCreated.
- EmailTemplateUpdated.
- EmailTemplatePublished.
- EmailQueued.
- EmailSent.
- EmailDeliveryFailed.
- EmailRetryScheduled.
- AdminEmailFailureNoticeCreated.
- WebhookReceived.
- WebhookProcessingRetried.
- WebhookProcessingFailed.
- BackgroundJobRetried.
- BackgroundJobFailed.
- PublicLoanNotePublished.
- BulkInvestorEmailQueued.
- SwissTaxStatementGenerated.
- ReportExportGenerated.
- EvidencePackageGenerated.
- RedactedExportGenerated.
- FullExportGenerated.
- ComplianceHoldPlaced.

## API Domains

- Identity and account API.
- Onboarding/compliance API.
- Borrower/entity API.
- Loan/origination API.
- Marketplace/investment API.
- Payments/ledger API.
- Servicing API.
- Documents API.
- Notifications API.
- Reporting API.
- Admin API.

## Dependency Notes

Didit integration method remains flexible for natural-person lender KYC/AML. Hosted redirect, embedded iframe, SDK/mobile flow, or a mixed approach may be selected during implementation. Didit webhooks must be verified before decisions affect internal statuses.

Legal-entity lender and borrower KYC/KYB/AML are off-platform at launch. The integration layer should still allow admin-entered external references and evidence metadata for those records.

Ongoing AML monitoring is handled by Didit on the provider side where enabled. The platform does not consume ongoing-monitoring webhooks or automate ongoing-monitoring workflows in v1. Garanta handles follow-up actions manually/off-platform and records account locks, restrictions, closures, notes, or status changes in the admin portal where needed.

Formal KYC/AML provider reports are generated by the KYC provider at launch. The platform stores provider references, statuses, decision metadata, downloadable-file metadata, downloaded provider reports where legally and technically possible, raw provider webhook payloads where legally and technically possible, required KYC/KYB data fields, supporting-document references/local copies where possible, and audit metadata required by the identity module. It does not recreate provider-native KYC report generation. Didit performs the launch natural-person KYC capture/check flow, while Garanta retains the local regulatory evidence boundary described in the identity and security modules.

SendGrid is the launch email provider for transactional emails and future newsletter lists/audiences. The platform must store full sent email content, template version, data snapshot, recipient, provider message id, and delivery/failure metadata where available. Failed sends retry a configured number of times and then create an admin notice/task. Sender domain remains TBD.

Twilio is used at launch only for phone verification. Other security and operational messaging is email-only in v1.

Investor login uses email magic links delivered through the launch email provider. Investor sensitive/financial actions require fresh email-code confirmation delivered through the launch email provider. Admin login uses email, password, and an email code delivered through the launch email provider. Initial superadmin credentials are configured through environment/deployment configuration rather than stored as ordinary database-created admin users.

Payment and ledger integration is manual at launch through admin-declared bank operations, optional statement/evidence upload, and ledger-bank reconciliation workspaces. Adapter boundaries should keep future bank-feed automation possible after the money model, regulated perimeter, and selected bank/payment partner are approved.

FX rate integration uses live executable quotes fixed for 1 minute, plus background polling for display-only indicative rates. Sanity checks must reject malformed/stale/broken rates, skip suspicious display ticks, and alert on material deviations.

Reporting should be designed as on-demand admin exports at launch, with report definitions, source-event lineage, and export events structured so a BI/data warehouse layer can be added later.

## Q/A Backlog

1. Answered by COMMS-DEC-001/002: selected launch communication vendors are SendGrid for email/contact lists and Twilio for phone verification, in addition to Didit for KYC/AML.
2. Answered by INT-DEC-001: v1 architecture is a modular monolith.
3. Answered by INT-DEC-002: no dedicated event bus is required at launch; append-only event table plus background jobs is enough.
4. Answered by INT-DEC-004: no public or partner API is required at launch.
5. Partly answered by INT-DEC-006/INT-DEC-008/FIN-DEC-002: no direct bank/payment/accounting API integration is required at launch beyond manual banking operations, evidence upload, and Bexio accounting exports. Final Bexio chart mapping, import layout, and tax-code mapping remain Garanta/accountant TODOs.
6. Answered by INT-DEC-005: webhook processing retries automatically and repeated failures create admin/tech alerts or operational work items.
7. Answered by SEC-DEC-002/SEC-DEC-003: launch events/logs are append-only and not deleted; financial records are retained for at least 10 years, and granular cleanup/archive policy is future scope.
8. Answered by KYC-DEC-007 and KYC-DEC-005: no Didit ongoing-monitoring webhook/status events are consumed by the platform in v1. Didit handles provider-side monitoring where enabled, and Garanta handles resulting account actions manually/off-platform. Launch onboarding webhooks, report downloads, raw payload retention where possible, provider references, and local evidence exports remain in scope.
9. Answered by RPT-DEC-004: no BI/data warehouse is required at launch, but events and reporting exports should be structured for later BI.
10. Answered for planning: sender domain and SendGrid/Twilio production account details are TBD and tracked in ADMIN_TODO.
11. Updated by ACC-DEC-001/ACC-DEC-002/ACC-DEC-008: investor authentication uses magic-link email events plus sensitive-action email-code events; admin authentication uses database admin users plus email-code events; initial superadmin credentials are environment-configured.
12. Answered by INT-DEC-003: Didit integration UX remains flexible.
13. Answered by INT-DEC-006: banking/payment integration is manual at launch and future-ready for automation.
14. Answered by INT-DEC-007: FX executable quotes are fetched live, fixed for 1 minute, and guarded by sanity checks; display rates are polled separately.
15. Answered by INT-DEC-008: no additional launch integrations are required beyond the known providers/export paths.
