# Cross-Module Consistency Review

Status: Current Q/A resolved. Initial consistency pass completed on 2026-05-22; Bexio accounting-export and KYC/KYB/AML evidence storage updates applied on 2026-05-29; recovery allocation and closure pseudonymization updates applied on 2026-05-30; manual bank-operation reconciliation and configurable recovery waterfall updates applied on 2026-06-01; remaining launch inputs are tracked as Admin TODO items.

## Purpose

Capture the cross-module consistency review after the module-by-module Q/A sessions and identify the remaining launch decisions that still need Garanta input.

## Review Result

The platform plan is broadly consistent after the balance, FX, auth, security, integration, and infrastructure updates.

No unresolved contradiction was found around the major operating model:

- Borrowers do not have a portal or login.
- Natural-person lenders self-register, complete mandatory phone verification, accept registration-time terms, and complete Didit KYC/AML before dashboard, balance, deposit, FX, or investing access. Offline support recovery is available for lost/bouncing email access after identity re-verification.
- Didit performs natural-person KYC capture/checks, while Garanta stores the full required local KYC/KYB/AML evidence boundary on Swiss-controlled infrastructure, including provider reports and raw webhook payloads where legally and technically possible.
- Legal-entity lenders and borrowers are onboarded off-platform and admin-created; KYB/AML approval is required before platform transactions.
- Legal-entity lender accounts behave like regular lender accounts once KYB/AML-approved and active, but launch supports one representative/login and no legal-entity internal roles.
- Investor balances are in scope, with CHF/EUR launch currencies, source-level ageing, 30-day invest/reinvest eligibility, withdraw-only handling after day 30, 60-day withdrawal deadline, forced-withdrawal/penalty/freeze handling, and FIFO source consumption. Primary-market balance-funded orders are blocked if the loan funding deadline exceeds the consumed source entries' remaining 30-day investment window.
- Day-60 balance penalty mechanics are env/deployment-configurable. Launch default is 1% simple daily penalty on the overdue source balance, applied by Europe/Zurich calendar day, capped at the remaining overdue source balance, never creating a negative balance, with terminal `penalty_exhausted` status if fully consumed.
- Repayments, recovery payments, and secondary-market seller proceeds are credited to investor balances, not automatically paid to bank accounts.
- Default recovery uses configurable project-level waterfall settings. Unless overridden per project, the waterfall is external recovery/legal costs, platform-approved recovery costs including applied Garanta recovery fee, principal, contractual interest accrued until default, default/penalty interest, and other penalties/costs.
- Default/penalty interest starts from default time instead of regular contractual interest only where configured, and defaulted-loan recovery payments require admin to declare third-party recovery costs and whether Garanta's percentage recovery fee applies.
- All external bank movements are declared manually by admin at launch using lender deposit, lender withdrawal, borrower loan disbursement, borrower repayment, Garanta out, Garanta in, and currency-exchange external settlement operation types.
- Bank reconciliation compares bank-stated balances by currency with investor balances, Garanta accrued commissions/revenue held in collection accounts, suspense/unmatched cash, and pending/exception balances.
- Garanta accrued revenue reports are available for arbitrary periods, and `garanta_out` transfers move Garanta-owned amounts to operating accounts without affecting investor balances.
- Recovery payments are allocated pro rata to current lender holdings based on current principal balance at recovery event time, with gross-to-net recovery reporting, contractual-interest cutoff at default, separate default/penalty interest where applicable, and explicit recovery rounding differences.
- FX is in scope as an auxiliary settlement function, not trading/speculation. Launch pairs are CHF/EUR and EUR/CHF, with no minimum exchange amount, a CHF 100,000 per-investor daily maximum or equivalent configurable by admin, Yahoo Finance rates, live executable quotes fixed for 1 minute, display-only background polling, same-provider sanity checks, configurable fee, admin FX delta settlement, and realized FX gain/loss calculation after admin declares external execution. FX conversion does not reset balance-ageing timers or restore investment eligibility; target-currency entries inherit deadlines from consumed source entries, using the earliest consumed investment and withdrawal deadlines when multiple source entries are consumed in one exchange.
- Admin role model is superadmin for parametrization/template/configuration and admin for operational execution.
- Account closure requires a clean/empty account. Optional closure-time privacy anonymization is reversible pseudonymization of direct identifiers, with financial records, documents, KYC/KYB/AML evidence, and audit trail preserved intact.
- No launch maker-checker, admin step-up auth, admin impersonation, borrower portal, e-signature, support tickets, BI layer, bank-feed automation, or public API. Investor sensitive/financial actions require fresh email-code confirmation.
- Launch architecture is a modular monolith with append-only event table and background jobs.
- Launch infrastructure is AWS-oriented and cost-optimized, using AWS `eu-central-2` Zurich for the full stack. Staging and production are logically isolated but share one EC2 Docker Compose host at launch. PostgreSQL and Redis are self-hosted/containerized at launch, private S3 Zurich buckets store documents/evidence/backups, and the scale path is EC2 resize, RDS, ElastiCache, separate hosts, then ECS/Fargate if needed.
- Europe/Zurich is the authoritative business timezone for day-counting, reminders, penalties, funding deadlines, late/default status, report day buckets, and scheduler cutoffs. Timestamps are stored in UTC.

## Fixes Applied During Review

- Updated the planning index status from initial-Q/A state to consistency-review state.
- Marked the first Q/A in the workflow module as historical/completed.
- Removed stale wording that implied legal-entity lender multi-user/signatory permissions in v1.
- Removed duplicate/stale "lender payment notification" wording where lender balance-credit notification is the correct v1 behavior.
- Marked several Q/A backlog items as answered by later decisions, including KYC exception authority, auto-invest future scope, borrower multi-loan handling, no structured borrower post-funding reporting, no fixed partial-funding threshold, no in-platform external credit data source, admin loan approval authority, document retention baseline, and event retention baseline.

## Module-by-Module Consistency Notes

1. Operating Model and Compliance: consistent. Remaining work is legal/compliance validation and jurisdiction-specific policy.
2. Identity, KYC, KYB, and AML: consistent. Didit boundary is now clear: provider performs checks, while Garanta stores the required local evidence boundary in Swiss-controlled infrastructure, including reports, metadata, raw webhook payloads where possible, manual decisions, and audit trail.
3. Accounts, Authentication, and Access Control: consistent. Investor sessions are long-lived with sensitive-action email-code confirmation; codes expire after 10 minutes, allow 3 attempts, and require resend throttling. Offline support recovery covers lost/bouncing email access after identity re-verification using account/KYC and verified phone/account evidence.
4. Investor Portal: consistent. Minimum/maximum investment amounts are now defined for launch. V1 uses generic P2P lending risk acknowledgements and exposure metrics, with no hard suitability questionnaire or concentration-limit enforcement.
5. Borrower and Entity Records: consistent. Borrowers have no portal, and Garanta admins enter borrower opportunities directly in v1.
6. Admin and Operations Portal: consistent. Launch work uses simple task queues/queries, daily reports are defined, legal-entity lender fields are defined, and SLA tracking applies to all daily operational actions/queues.
7. Loan Product Catalog and Configuration: consistent. Exact term sanity bounds and collateral-warning policy can be finalized later. Launch schedule defaults are calendar-day status checks, annual nominal interest, monthly installment default, currency minor-unit rounding, and final-installment rounding-residue absorption.
8. Origination, Credit Review, and Underwriting: consistent. Offline credit review, manual risk rating, calculated LTV, and no incomplete loan persistence align with later modules.
9. Marketplace, Investments, and Allocations: consistent. Listing visibility/editing, secondary-market bulletin-board full-holding transfer flow, discount/premium pricing, accrued-interest split, launch secondary-market fees, non-standard listing admin approval, pending-order intent behavior, required funding deadline, balance-lot deadline eligibility for commitments, and partial-funding principal treatment are now defined; exact legal confirmations/templates remain open.
10. Payments, Ledger, Custody, and Reconciliation: consistent. Bank/payment partner remains open; launch payment-reference direction is lender ID or derived lender code, with final bank-compatible format pending. Manual bank-operation declaration, ledger-bank reconciliation equation, Garanta out/in, accrued revenue reporting, external FX settlement result handling, env-configured capped balance penalties, and Europe/Zurich day-counting are defined. Bank-specific statement formats, external FX settlement evidence fields, and final accounting/tax labels remain open. No unhedged/exposure alerts are required for launch FX.
11. Loan Servicing and Repayments: consistent. Repayment events can materially alter schedules, but only through declared payment/operational events. Borrower-side penalties are configurable but 0/inactive at launch. Default recovery handling uses project waterfall configuration and default/penalty interest replaces regular interest only after default where configured.
12. Risk Monitoring, Collections, and Recoveries: consistent. Garanta owns offline collections; platform tracks default status, notes, documents, recovery events, investor updates, gross-to-net recovery details, third-party recovery costs, Garanta recovery fee decisions, waterfall allocations, lender allocations, and recovery rounding differences. Operational v1 does not use write-off as a loan state; defaulted loans remain defaulted until recovery/resolution policy is finalized.
13. Documents, Contracting, and E-Signature: consistent. Legal templates and final wording remain open; e-signature is out of v1.
14. Communications and Notifications: consistent. Sender domain, support email, and SendGrid/Twilio production details are TBD/admin TODO; template wording and retry intervals remain open.
15. Accounting, Tax, and Finance Operations: consistent. Bexio is the selected accounting software; annual tax information statements now cover lenders, borrowers, and Garanta internal finance from the same transaction-level ledger; accrued revenue, Garanta out/in, bank reconciliation, and realized FX gain/loss reporting are defined; final Bexio chart mapping, import layout, tax-code/VAT/reverse-charge mapping, and final statement wording/examples remain Garanta/accountant/legal TODOs; launch report/export formats are PDF/CSV/ZIP as applicable.
16. Reporting, Analytics, and Regulatory Exports: consistent. Export-first model aligns with accounting, security, and admin modules.
17. Security, Privacy, and Auditability: consistent. Investor long-lived sessions, sensitive-action email-code confirmation, reversible closure pseudonymization, and production-to-staging anonymization policy are defined. Production access procedure, private-key custody, and detailed global rate limits remain implementation/security configuration.
18. Integrations, APIs, and Event Architecture: consistent. Manual banking, append-only events/background jobs, simple Didit onboarding integration, no in-platform Didit ongoing-monitoring automation, no public API, and no extra launch integrations align with infrastructure.
19. Infrastructure, DevOps, and Platform Operations: consistent. Launch uses AWS `eu-central-2` Zurich, one EC2 Docker Compose host shared by logically isolated staging and production, self-hosted/containerized PostgreSQL and Redis, AWS Zurich S3 for documents/evidence/backups, GitHub Actions plus ECR for deployment, daily encrypted backups with 62-day retention, JSON structured logs, and tech-team alerts. Real AWS/GitHub/DNS access remains an accounts TODO, not an architecture blocker.
20. Q/A Workflow: consistent after marking the first Q/A as historical.

## Resolved Q/A and Transferred Admin TODOs

1. Answered: natural-person lenders may self-register from Switzerland + EU/EEA; legal-entity lenders and borrowers are admin/offline onboarded rather than governed by a self-service country matrix.
2. Answered: primary-market minimum investment is 1,000 CHF/EUR and configurable by superadmin; maximum is remaining loan capacity.
3. Answered: borrower opportunities are entered directly by Garanta admins in v1; no broker/introducer submitter flow.
4. Answered: admin work is organized as simple task queues and filtered task queries in v1.
5. Answered: SLA tracking applies to all daily operational actions/queues and means storing task/event created time, optional due time, status, completion time, owner/role, overdue state, and audit trail.
6. Answered: no separate restricted support view or support role in v1; launch admin model is superadmin/admin, with normal email support outside the platform.
7. Answered: legal-entity lender mandatory fields are legal name, registration number, jurisdiction, registered address, representative name/email/phone, bank IBAN, onboarding/KYB status and date, risk rating, and tax residency. Uploads are optional.
8. Answered: no private, invitation-only, or segmented listings in v1; listings are visible to all eligible investors.
9. Answered: before committed investments, all fields can be edited; after committed investments, only total amount can be lowered, with custom investor message/reason and notification only.
10. Answered for product scope: keep generic checkbox/clickwrap confirmations; exact labels/acknowledgements are legal/template TODOs.
11. Answered: secondary-market is a bulletin-board claim/participation transfer mechanism. Current/performing listings can be purchased directly after system checks and document acceptance; non-performing/non-standard listings require admin approval before publication and additional buyer acknowledgement before purchase.
12. Answered: launch secondary-market fees are 0.25% maker/seller and 0.75% taker/buyer, calculated on transfer price excluding accrued interest, rounded half-up to the nearest cent/minor unit, and charged at settlement. Minimum fee support is configurable.
13. Answered: borrower-side penalties remain configurable but 0/inactive at launch until business/legal policy is finalized.
14. Partly answered: bank/payment partner remains TODO. Payment reference may use lender ID or a stable code derived from part of lender ID, pending final bank-compatible format.
15. Answered for planning: sender domain and support email remain TBD and are tracked in `admin_todo_accounts.md`.
16. Answered for planning: Bexio is the selected Swiss accounting software; exports are configurable monthly Bexio debit/credit outputs generated from the immutable transaction-level platform ledger. Final chart mapping, import layout, and tax-code mapping remain Garanta/accountant TODOs.
17. Answered: annual tax information statements are generated for lenders, borrowers, and Garanta internal finance from the same complete annual account statements and immutable transaction-level ledger. They separate tax-relevant income/cost items from information-only principal/balance movements and are informational only, not tax advice.
18. Answered: investors remain logged in through long-lived sessions, with fresh email-code confirmation for sensitive/financial actions. Investor sensitive-action codes expire after 10 minutes, allow 3 attempts, and require resend throttling. Admin defaults remain 10-minute email code, 15-minute idle timeout, and 8-hour maximum session unless changed later.
19. Answered: Didit registration flow sends relevant information to Didit and sends the user to Didit for KYC/selfie/ID scan. If KYC passes, the account opens for financial use; if not, it remains blocked. Garanta stores local KYC/KYB/AML evidence for regulatory/audit/compliance access. The platform does not consume ongoing-monitoring webhooks in v1; Didit handles provider-side monitoring and Garanta handles follow-up manually/off-platform.
20. Answered: launch infrastructure uses AWS `eu-central-2` Zurich for the full stack. IAM/access details are now narrowed to account access/provisioning in `admin_todo_accounts.md`.
21. Answered: production data copied to staging must replace direct identifiers with deterministic fake values while preserving operational/ledger structure, removing provider secrets/tokens, disabling real external sends/calls, and keeping re-identification mapping out of staging.
22. Answered: manual bank-operation declaration is the launch reconciliation model. Operation types are lender deposit, lender withdrawal, borrower loan disbursement, borrower repayment, Garanta out, Garanta in, and currency-exchange external settlement.
23. Answered: when no pending/suspense/exception items exist, bank balance by currency should equal investor balances plus Garanta accrued commissions/revenue held in the collection account. Reconciliation reports must show the full bridge and create work items for breaks.
24. Answered: after external FX settlement is declared with actual rate and fees, the platform calculates Garanta-owned realized FX gain/loss or surplus/deficit by currency without retroactively changing investor balances.
25. Answered: default/recovery projects support configurable recovery waterfall settings, default/penalty interest percentage, Garanta percentage recovery fee, and admin-declared third-party recovery costs at recovery-payment time.
