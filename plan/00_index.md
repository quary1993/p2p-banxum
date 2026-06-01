# BANXUM Planning Index

Status: Module-by-module Q/A completed for current scope; remaining launch inputs are tracked in the split admin TODO files.

BANXUM is planned as a peer-to-peer lending platform operated by Garanta Finanzgruppe AG, a FINMA-regulated Swiss entity. The planning approach is to split the business and technology platform into modules, document each module, then review each module through a Q/A session before marking it as requirements-ready.

Canonical naming:

- Platform/brand name: BANXUM.
- Legal operator: Garanta Finanzgruppe AG.
- Implementation must treat platform/brand name, legal operator name, support email, domains, and document footer identities as configuration/template variables, not hardcoded literals in email templates, legal PDFs, generated statements, or user-facing notices.

This folder is the source of truth for product, operations, compliance, and technical planning until the implementation repository exists.

## Core Assumptions

- The platform brand/name is BANXUM, and the legal operator is Garanta Finanzgruppe AG.
- The platform will support investor/client users, admin-managed borrower/requesting entity records, internal administrators, compliance staff, finance staff, and auditors.
- Natural-person lender KYC/AML will use Didit during registration before dashboard, deposit, balance, FX, or investment access. The platform sends relevant registration/KYC metadata to Didit and sends the user to Didit for KYC, selfie/liveness, and ID scan. Legal-entity lender and borrower KYC/KYB/AML are handled off-platform or through external providers and recorded by admin.
- Garanta stores the full required local KYC/KYB/AML evidence boundary for regulatory, VQF/SRO, audit, bank/payment partner, and internal compliance purposes on Garanta-controlled infrastructure located in Switzerland, with minimum 10-year retention subject to final legal/compliance confirmation.
- Natural-person self-service lenders may register from Switzerland and EU/EEA at launch, subject to compliance and operational restrictions. Legal-entity lenders are admin-created after offline onboarding; borrowers have no self-service accounts.
- Investor/client portal login uses email magic links. Natural-person lender phone verification is mandatory through Twilio. Offline support recovery is available for lost/bouncing email access after identity re-verification using account/KYC evidence and verified phone/account data. Investor sessions are long-lived, with fresh email-code confirmation required for sensitive/financial actions such as withdrawals, FX, investments, and secondary-market actions; those codes expire after 10 minutes, allow 3 attempts, and require resend throttling. Admin users authenticate with email/password plus email code. The initial superadmin account is configured through environment/deployment configuration.
- The platform now includes investor multi-currency balances, starting with CHF and EUR, with enabled currencies configurable by superadmin.
- Deposits, repayment/installment proceeds, secondary-market proceeds, refunds credited to balance, and FX proceeds are subject to source-level balance ageing controls, including a 30-day investment/reinvestment deadline and a 60-day withdrawal deadline under the launch interpretation.
- Balance source entries older than 30 days become withdraw-only and cannot be invested/reinvested. Balance-funded primary-market orders are blocked if the loan funding deadline exceeds the consumed source entries' remaining 30-day investment window. Day-60 balances trigger forced withdrawal if a usable IBAN is known or penalty/freeze mode if it is not.
- Day-60 balance penalty mechanics are env/deployment-configurable. Launch default is 1% simple daily penalty on the overdue source balance, applied by Europe/Zurich calendar day, capped at the remaining overdue source balance, never creating a negative balance, with terminal `penalty_exhausted` status if fully consumed.
- Currency exchange is in scope as an auxiliary settlement function, not trading/speculation. Launch uses Yahoo Finance rates, CHF/EUR and EUR/CHF pairs, no minimum exchange amount, a CHF 100,000 per-investor daily maximum or equivalent configurable by admin, a configurable platform FX fee, and admin FX delta reporting. FX conversion does not reset 30/60-day balance-ageing timers or restore investment eligibility; target-currency balances inherit deadlines from consumed source balances, using the newest/latest consumed expiry timestamp when multiple source entries are consumed in one exchange.
- FX executable quotes are fetched live, fixed for 1 minute for investor approval, and protected by same-provider sanity checks; background-polled FX rates are display-only. FX calculation values are stored with at least 6 decimals, ordinary website amounts show 2 decimals, FX confirmation may show 4 decimals, and half-up rounding applies.
- Primary-market minimum investment is 1,000 CHF/EUR at launch, configurable by superadmin. Maximum investment is the remaining loan capacity available for the order.
- V1 uses generic P2P lending risk acknowledgements and exposure metrics; no detailed suitability questionnaire or hard concentration limits are enforced at launch.
- Every primary-market loan has an admin-set funding deadline. Default funding deadline is 30 days and maximum funding deadline is 60 days. If admin accepts partial funding, the accepted funded amount becomes final loan principal and the repayment schedule is based on that amount.
- The authoritative business timezone is Europe/Zurich for 30/60-day balance deadlines, reminders, penalties, funding deadlines, day-5 late status, day-16 default status, report day buckets, and scheduler cutoffs. Timestamps are stored in UTC.
- Launch marketplace listings are visible to all eligible investors, with no private, invitation-only, or segmented listings in v1.
- Published loans can be fully edited until committed investments exist. After committed investments exist, admin can only lower the total loan amount, with required investor notification and a custom reason.
- Secondary-market is a bulletin-board claim/participation transfer mechanism. Sellers may list only full holdings, priced as a discount or premium to current principal balance; accrued interest to settlement belongs to the seller and future interest belongs to the buyer. Current/performing listings can settle directly after buyer eligibility, balance/funds, fees, and document checks; non-performing/non-standard listings require admin approval, disclosure, and additional buyer acknowledgement before purchase.
- Recovery payments for defaulted/recovery loans use configurable project recovery waterfalls. Default waterfall: external recovery/legal costs, platform-approved recovery costs including applied Garanta recovery fee, principal, contractual interest accrued until default, default/penalty interest, and other penalties/costs. Lender-facing buckets are allocated pro rata to current lender holdings based on current principal balance unless project-specific terms override this. Recovery reports separately show gross recovered amount, third-party costs, recovery fee, net amount received by Garanta, contractual-interest cutoff at default, default/penalty interest where applicable, lender distributions, and rounding differences.
- Swiss accounting uses CHF as base reporting currency and Bexio as the selected accounting software. The platform ledger is the immutable transaction-level operational subledger/source of truth and exports configurable monthly Bexio debit/credit accounting data; currency-specific ledgers are reported, while accounting FX revaluation is handled by the accountant/accounting system.
- Annual tax information statements are generated for lenders, borrowers, and Garanta internal finance from the same complete annual account statements and immutable transaction-level ledger. Tax summaries separate income/cost items from information-only principal and balance movements and are informational only, not tax advice.
- Reporting is export-first at launch: admin-only on-demand PDF/CSV reports and ZIP evidence packages, with redacted and full export modes. Dashboards and BI/data warehouse are future-ready but not required for v1.
- Communications are email-first at launch using SendGrid. Twilio is used only for phone verification. Marketing/newsletter consent is captured in v1 for future newsletters, transactional emails are mandatory, and email templates are superadmin-editable with variable scopes and examples.
- Account closure is admin-operated after email/support request and requires a clean/empty account. Admin may optionally apply reversible privacy pseudonymization at closure, encrypting direct identifiers while preserving financial records, documents, KYC/KYB/AML evidence, and audit trail intact.
- Security posture is good internal controls for v1, with EU hosting acceptable for general infrastructure, Swiss-controlled storage required for KYC/KYB/AML evidence, append-only ledger/financial audit events, no launch log deletion, financial record retention of at least 10 years, and tech-team email alerts for critical technical/security conditions.
- Architecture is a modular monolith at launch, with an append-only event table and background jobs rather than a dedicated event bus. No public API is required for v1.
- Infrastructure is AWS-oriented and cost-optimized at launch, using AWS `eu-central-2` Zurich for the full stack. Hosted environments are staging and production on the same EC2 Docker Compose host with logical isolation. PostgreSQL and Redis are self-hosted/containerized at launch, private S3 Zurich buckets store documents/evidence/backups, GitHub Actions handles CI/CD, AWS ECR stores container images, secrets use restricted environment files/environment variables, and backups run daily to encrypted S3 with two-month retention.
- The platform must be designed for Swiss regulated operations and must support auditability, segregation of duties, traceable approvals, and regulatory reporting.
- Legal and compliance conclusions in these plans are requirements prompts, not legal advice. Final interpretation must be validated by Swiss counsel, the responsible compliance officer, and any applicable supervisory or audit stakeholders.
- Money movement, safeguarding, custody, and payment account setup are intentionally treated as first-class modules because they drive licensing, risk, and operating complexity.

## Module Files

1. [Operating Model and Compliance](01_operating_model_compliance.md)
2. [Identity, KYC, KYB, and AML](02_identity_kyc_kyb_aml.md)
3. [Accounts, Authentication, and Access Control](03_accounts_auth_access.md)
4. [Investor Portal](04_investor_portal.md)
5. [Borrower and Entity Records](05_borrower_entity_portal.md)
6. [Admin and Operations Portal](06_admin_operations_portal.md)
7. [Loan Product Catalog and Configuration](07_loan_product_catalog.md)
8. [Origination, Credit Review, and Underwriting](08_origination_underwriting.md)
9. [Marketplace, Investments, and Allocations](09_marketplace_investments.md)
10. [Payments, Ledger, Custody, and Reconciliation](10_payments_ledger_custody.md)
11. [Loan Servicing and Repayments](11_loan_servicing_repayments.md)
12. [Risk Monitoring, Collections, and Recoveries](12_risk_collections_recoveries.md)
13. [Documents, Contracting, and E-Signature](13_documents_contracting_esign.md)
14. [Communications and Notifications](14_communications_notifications.md)
15. [Accounting, Tax, and Finance Operations](15_accounting_tax_finance.md)
16. [Reporting, Analytics, and Regulatory Exports](16_reporting_analytics.md)
17. [Security, Privacy, and Auditability](17_security_privacy_audit.md)
18. [Integrations, APIs, and Event Architecture](18_integrations_api_events.md)
19. [Infrastructure, DevOps, and Platform Operations](19_infrastructure_devops.md)
20. [Q/A Workflow](20_qna_workflow.md)
21. [Cross-Module Consistency Review](21_consistency_review.md)

## Suggested Q/A Order

The recommended review order follows business risk:

1. Operating Model and Compliance
2. Identity, KYC, KYB, and AML
3. Payments, Ledger, Custody, and Reconciliation
4. Loan Product Catalog and Configuration
5. Origination, Credit Review, and Underwriting
6. Marketplace, Investments, and Allocations
7. Loan Servicing and Repayments
8. Investor Portal
9. Borrower and Entity Records
10. Admin and Operations Portal
11. Risk Monitoring, Collections, and Recoveries
12. Documents, Contracting, and E-Signature
13. Accounting, Tax, and Finance Operations
14. Reporting, Analytics, and Regulatory Exports
15. Communications and Notifications
16. Accounts, Authentication, and Access Control
17. Security, Privacy, and Auditability
18. Integrations, APIs, and Event Architecture
19. Infrastructure, DevOps, and Platform Operations

## Documentation Status Legend

- Draft: Initial module definition exists, but Q/A is pending.
- Reviewed: Q/A completed and decisions recorded.
- Requirements-ready: Scope, rules, workflows, and open dependencies are stable enough for design and implementation.
- Deferred: Module intentionally postponed.

## Source Notes

The initial plans use current public documentation checked on 2026-05-15 from:

- Didit documentation: https://docs.didit.me/
- Didit API full flow: https://docs.didit.me/integration/api-full-flow
- Didit API overview: https://docs.didit.me/api-reference/overview
- Didit continuous AML monitoring: https://docs.didit.me/core-technology/aml-screening/continuous-monitoring-aml-screening
- Didit AML Screening API: https://docs.didit.me/standalone-apis/aml-screening
- Didit data retention: https://docs.didit.me/console/data-retention
- Didit pricing: https://docs.didit.me/getting-started/pricing
- FINMA FinTech information: https://www.finma.ch/en/authorisation/fintech/
- FINMA FinTech licence: https://www.finma.ch/en/authorisation/fintech/fintech-bewilligung
- FINMA AMLA legal basis: https://www.finma.ch/en/documentation/legal-basis/laws-and-ordinances/anti-money-laundering-act-%28amla%29/
- FINMA AML supervision overview: https://www.finma.ch/en/supervision/cross-sector-issues/combating-money-laundering/
- FINMA supervision of SROs: https://www.finma.ch/en/supervision/self-regulatory-organisations-sros/
- FINMA self-regulation overview: https://www.finma.ch/en/documentation/self-regulation/

Additional regulatory-sensitive balance/FX model check on 2026-05-20 used:

- FINMA FinTech information: https://www.finma.ch/en/authorisation/fintech/
- FINMA FinTech licence: https://www.finma.ch/en/authorisation/fintech/fintech-bewilligung/
- FINMA AML supervision overview: https://www.finma.ch/en/supervision/cross-sector-issues/combating-money-laundering/

Additional Swiss accounting/reporting source check on 2026-05-21 used:

- Swiss SME Portal compulsory accounting: https://www.kmu.admin.ch/kmu/en/home/concrete-know-how/finances/accounting-and-auditing/compulsory-accounting.html
- Swiss SME Portal electronic bookkeeping: https://www.kmu.admin.ch/kmu/en/home/concrete-know-how/finances/accounting-and-auditing/electronic-bookkeeping.html
- Swiss SME Portal profit and loss statement: https://www.kmu.admin.ch/kmu/en/home/concrete-know-how/finances/accounting-and-auditing/annual-financial-statements/profit-loss-statement.html
