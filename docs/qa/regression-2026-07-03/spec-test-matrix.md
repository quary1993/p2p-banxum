# BANXUM Consolidated Regression Test Plan

Sources: per-module extractions for plan/01–02 (Operating Model, KYC/AML), plan/03 (Accounts/Auth), plan/04 (Investor Portal), plan/05–06 (Borrower Records, Admin Portal), plan/07–08 (Product Catalog, Origination), plan/09 (Marketplace), plan/10 (Payments/Ledger — extraction truncated at ADM-OVERSUB-1; checks included as far as provided).

---

## 1. P0 End-to-End Money Path (dependency order)

Run as one continuous scenario using QA time-travel; all calendar-day transitions must flip at **Europe/Zurich midnight** (not UTC) — SYS-TZ-1.

### Step 0 — Admin fixture: borrower + published loan (prerequisite for Step 4)
Stories: BOR-CREATE-1, ADM-BORROWER-1/2, BOR-COMPLIANCE-GATE-1, BOR-LOAN-CREATE-1, PROD-SANITY-1, PROD-LTV-1, PROD-REPAY-1, PROD-RATE-1, PROD-FUNDDL-1, ORIG-INTAKE-1, ORIG-PUBLISH-1, ORIG-KYB-1, MKT-PUBLISH-1, MKT-DEADLINE-1
- Borrower entity mandatory fields exactly: **entity legal name + year founded** (save rejected if missing); legal entities only; borrowers never log in.
- With KYB/AML not approved OR a compliance hold: publish, funding close, disbursement, repayment processing all blocked; after approval + hold cleared they unlock.
- Loan save rejected until ALL mandatory fields complete: principal, currency, term, interest rate, repayment type, repayment schedule, purpose, collateral type, collateral value; no incomplete loan persisted; offline credit review recorded before save/publish.
- Principal sanity: reject **< 1,000** and **> 1,000,000,000** (loan currency); inside range accepted.
- LTV = principal / collateral value × 100, system-computed only (no manual input); collateral value 0 → warning AND LTV hidden; collateral value > principal → warning AND LTV still shown.
- Repayment picker: exactly 5 launch types, default **equal installment**, each with short description; no custom/manual schedule; interest rate admin-entered annual nominal, never derived from risk grade.
- Funding deadline mandatory: launch default **30 days**, draft max **60 days**; publish blocked if deadline in the past OR **> 29 calendar days** from Europe/Zurich business date (time-travel past deadline must flip publishable → blocked).
- Defaulted loans can never be published on primary market.

### Step 1 — Investor registration
Stories: INV-REG-1, INV-REG-2, INV-PHONE-1, INV-LOGIN-MAGIC-1
- Self-registration: natural persons only; Switzerland + EU/EEA only; other countries rejected; no borrower or legal-entity self-registration.
- Order enforced: register → clickwrap terms → Didit KYC → gated access; terms acceptance recorded (document/template version, data snapshot, timestamp, user, context); registration terms state the 60-day holding limit cannot be extended.
- Email verified; phone verification mandatory (local/mock provider; `PHONE_VERIFICATION_PROVIDER=twilio_verify` in staging/prod); in Twilio mode no local OTP digest stored, only challenge/audit evidence + Twilio verification SID; local expiry/attempt limits/throttles still enforced.
- Login = email magic link only; investors have NO password; no baseline MFA beyond the link; session long-lived (no idle expiry).

### Step 2 — KYC / gating
Stories: INV-KYC-1, INV-KYC-2, INV-KYC-GATE-1, SYS-KYC-MAP-1, SYS-KYC-MAP-2, SYS-WEBHOOK-1
- Backend creates KYC session (mock locally; `DIDIT_SESSION_PROVIDER=api` for real Didit) with vendor_data = internal user reference, workflow ID, callback URL; no new session if KYC already valid.
- Internal statuses exactly 10: Pending, Approved, Declined, Manual review, High risk, Sanctions hit, PEP hit, Adverse media hit, Expired, Re-verification required; mapping table verified (approved/verified/clear → approved ONLY if no unresolved blocking/manual-review flag; sanctions → blocks onboarding; PEP/high-risk/adverse-media → manual AML review, never auto-approved).
- Every non-approved status blocks: dashboard, deposit, balance, FX, investment completion, contract acceptance, withdrawal, primary investing, secondary listing/purchase — enforced **server-side**.
- Webhook: raw body + timestamp freshness + V3 signature verified before any status change; idempotent by vendor event/session ID; unsigned/stale/replayed/unmatched webhooks never grant verified; raw payload stored in restricted storage.
- Approved + no hold unlocks dashboard, deposits, balances, FX, investing.

### Step 3 — Deposit
Stories: INV-DEPOSIT-1 (plan/04 + plan/10), INV-BAL-1, INV-BALANCE-BREAKDOWN-1
- Payment reference format **BX-{currency}-{investor_reference}** (e.g. BX-CHF-L4F8K2Q9R); investor_reference short, immutable, platform-generated.
- One segregated collection account/IBAN per enabled currency (CHF, EUR); instructions warn against cross-currency bank transfers.
- Admin matching order: bank-statement reference → payer name/surname → email → sender IBAN → manual reconciliation; admin records `lender_deposit` bank operation.
- Ledger: 'in' movement, investor balance liability increased; source entry gets received timestamp = **bank value date**, **30-day** investment deadline, **60-day** withdrawal deadline, penalty status field.
- Balances non-interest-bearing; display 2 decimals; per-currency breakdown shows investable / must-withdraw / FX-eligible / penalty-frozen.

### Step 4 — Primary investment order
Stories: INV-INVEST-1, INV-INVEST-2, INV-ORDER-1…6, INV-NOCANCEL-1, INV-FUND-BALANCE-1, INV-INVEST-FIFO-1, INV-SENSITIVE-CODE-1
- Minimum **1,000 CHF/EUR** (superadmin-configurable) — below rejected; maximum = remaining loan amount/cap — above rejected; single-currency match required.
- Explicit risk acknowledgement + clickwrap investment terms before EVERY order; acceptance evidence recorded (version, snapshot, timestamp, user, context).
- Fresh email code required (expiry **exactly 10 minutes**, max **3 attempts** — 4th fails, resend throttled; used/stale code rejected).
- KYC/AML + no-hold re-confirmed at order time; fees/cash flows/risks shown pre-confirmation.
- Balance consumed **FIFO within currency**; only source entries inside their 30-day window at pledge time; loan funding deadline MAY be after the source's day-30 deadline (only pledge time matters); aggregate containing >30-day entries → explicit error + per-currency investable vs withdraw-only breakdown.
- No cancel action in UI or API, any state; max **50 pending orders** per investor (51st rejected); pending orders do NOT reserve capacity or move funded progress until allocated/validated.

### Step 5 — Funding, allocation, close/activation
Stories: SYS-ALLOC-FCFS-1, SYS-OVERSUB-1, SYS-ORDERSTATES-1, ADM-ORDER-VALIDATE-1, ADM-FUNDING-CLOSE-1, ADM-CLOSE-1, ADM-PARTIAL-1, SYS-FUNDS-1
- Allocation strictly first-come-first-served by balance reservation/allocation timestamp or bank value date of validated external funds; determines pro-rata claim share; all decisions audited.
- Oversubscription: system splits accepted portion vs excess ('Partially funded/validated' + 'Excess refund or balance release due'); zero capacity → order auto-closes 'Fully excess/refund or balance release due' → 'Closed not invested', admin alerted to return full amount; funded total never exceeds cap.
- All **11 order states** reachable: Pending; Payment received pending validation; Balance allocated pending validation; Funded/validated; Partially funded/validated; Excess refund or balance release due; Fully excess/refund or balance release due; Closed invested; Closed not invested; Refunded/balance released; Expired/closed unfunded.
- Close requires operational/compliance/credit/payment readiness; investor eligibility re-checked at **closing time**; settlement within the **60-day** max holding period; funds released to borrower, returned to balances, or withdrawn — never held past the funding period.
- One assignment document generated per investment order from template/data snapshot at closing.
- Partial funding path: accepted funded amount becomes final principal; schedule regenerated from it; success fee applies to it; lenders notified, NOT re-confirmed; non-proceeding campaigns → funds released back, orders 'Closed not invested'/'Refunded/balance released'.

### Step 6 — Disbursement
Stories: ADM-RELEASE-1, ADM-DISBURSE-1, PROD-FEES-1
- Release gates (all must pass): funding conditions reached, contractual documents effective/offline prerequisites confirmed, borrower KYB/AML still approved, no compliance hold, payment reconciliation passed, admin final approval.
- Borrower success fee **2%–4%** withheld from disbursement (CHF 100,000 loan → CHF 96,000–98,000 paid out); borrower still owes FULL principal (100,000) + interest; schedule unaffected; fee invisible to investors; stored for accounting.
- `borrower_loan_disbursement` bank operation with settlement evidence; ledger records full principal, success-fee revenue, net cash, settlement liability clearance; fee remains Garanta accrued revenue until `garanta_out`.

### Step 7 — Repayments (time-travel)
Stories: ADM-REPAY-1, ADM-REPAY-DIST-1, PROD-SCHEDULE-1, INV-PORT-2
- Schedule: calendar-day counts, monthly default frequency, each line rounded to currency minor unit, **final installment absorbs rounding residue** — totals reconcile exactly to principal + interest.
- Advance time to due date: installment becomes due; **day-5 late** and **day-16 default** status transitions (Europe/Zurich days) reflected in loan status, investor portfolio (days past due), and admin due/late/defaulted report.
- Admin records `borrower_repayment`; system correlates to next due installment, warns on lower/higher amount; classifies regular / partial / multi-installment (late loan) / early repayment (healthy loan).
- Allocation order: fees → penalties → current installment interest → current installment principal → future outstanding principal; schedule recalculated on timing changes.

### Step 8 — Interest/principal distribution to lenders
Stories: ADM-REPAY-DIST-1 (cont.), PROD-FEES-2, INV-PORT-3, INV-NOTIFY-1
- Pro-rata distribution per lender; `lender_payment_fee` applied per distribution — **launch value 0**.
- Lender credits: 'in' movements, received timestamp = borrower payment **bank value date**, **fresh 30/60-day clocks**; email notification on every balance credit.
- Admin sees distribution list (lenders, amounts, currencies, references); internal distribution artifacts never sent to lenders; history shows principal / contractual interest / default-penalty interest / recovery costs / other penalties / rounding-difference splits.

### Step 9 — Secondary market
Stories: INV-SEC-1…5, SEC-LIST-1, SEC-BUY-1, SEC-FEES-1, SEC-INTEREST-1, SEC-DISPLAY-1, SEC-SETTLE-1, SM-SETTLE-1, INV-SM-SELL-1, INV-SM-BUY-1
- Whole holding only — splitting/partial sale/partial transfer rejected; multiple holdings in same project listable separately; positive current principal required; no minimum holding period; no minimum transfer size.
- Price = discount/premium % of current principal balance; performing holdings publish automatically after checks + seller clickwrap; email code before listing AND purchase.
- Fees at settlement: maker/seller **0.25%**, taker/buyer **0.75%**, computed on transfer price **EXCLUDING accrued interest**, rounded **half-up** to minor unit; seller net = price + accrued interest − seller fee; buyer total = price + accrued interest + buyer fee; minimum fee configurable (no launch default).
- Accrued interest: daily, pro rata, to seller up to settlement date (performing loans); post-settlement interest to buyer; time-travel changes the accrued amount and both parties' totals.
- Display all 8 economics items: current principal, sale price, discount/premium, accrued interest, seller fee, seller net proceeds, buyer fee, buyer total cost.
- Buyer eligibility re-checked at **settlement time** (buyer who lost approval cannot settle); settlement never exceeds **60 days** from buyer-fund receipt/reservation.
- Seller proceeds credit as NEW source entry with fresh 30/60 clocks (internal transaction timestamp); reassignment document per purchase; servicing/pro-rata records updated.

### Step 10 — FX
Stories: INV-FX-1/2/3 (plan/01+04), INV-FX-QUOTE-1, INV-FX-SETTLE-1, SYS-FX-SANITY-1
- Pairs **CHF/EUR and EUR/CHF only**; fee **1.5%** launch default (superadmin-configurable); **no minimum**; max **CHF 100,000 per investor per day** (or equivalent, admin-configurable, resets daily) — above rejected.
- Executable quote: live Yahoo Finance fetch, fixed **exactly 1 minute** with countdown; expired quote must refresh; clickwrap FX terms + fresh email code before execution; background-polled rates display-only.
- Instant settlement: source debited FIFO, target credited immediately; ageing NEVER resets — target inherits **EARLIEST** consumed investment (day-30) and withdrawal (day-60) deadlines; full lineage retained; FX entries use internal transaction timestamp; fee revenue posted at exchange time.
- Display up to 4 decimals on FX quote/confirmation (2 elsewhere); rates/fees/intermediates stored with **≥ 6 decimal places**; half-up rounding on debit/credit/fees/posted amounts.
- Sanity: fail-closed on missing/zero/negative/non-numeric/infinite/malformed/stale/wrong-pair rates; **±5%** deviation vs previous-day average → alert, no auto-execute; **±2%** display-tick jump → invalidated/skipped; **300-second** freshness window; weekends and configured FX market holidays fail closed with explicit closure copy; ordinary stale/provider issues fail closed with a temporary availability message; production rejects mock rates.

### Step 11 — Balance ageing 30/60d (time-travel)
Stories: INV-BAL-2/3/4/5, INV-AGE-1…4, SYS-AGEING-REMINDERS-1, SYS-PENALTY-1, ADM-FORCED-WITHDRAWAL-1, ADM-FORCED-WD-1, ADM-PENALTY-FREEZE-1
- Reminders on days **25, 46, 53, 58, 59, 60** from received timestamp (remaining unconsumed amount; Europe/Zurich days); day-60 notice announces penalties and states Garanta needs a usable IBAN; templates superadmin-configurable and must state the 60-day rule is non-extendable; reminders audited + finance/compliance alerts.
- Day 30: source becomes withdraw-only; investment attempt → explicit error + breakdown; still withdrawable; FX cannot restore eligibility.
- Day 60 with usable verified IBAN: admin forced withdrawal (recorded as `lender_withdrawal`, appears in forced-withdrawal queue, audited high-risk, final once executed).
- Day 60 without IBAN: penalty mode — ALL financial actions frozen except declaring/updating a usable IBAN; blocking banner; read-only access preserved (portfolio, documents, tax statements, notices, messages); declaring IBAN unfreezes withdrawal path; freeze/unfreeze audited.
- After day 60: penalty **1% simple daily** on overdue source balance (env-configurable), once per Zurich calendar day, **capped at remaining overdue balance**, never negative; fully consumed source → terminal `penalty_exhausted` with zero remaining, fully ledgered.

### Step 12 — Withdrawal
Stories: INV-WD-1, INV-WITHDRAW-1
- Only to verified bank account; validates KYC/KYB, bank account, available balance, currency, compliance hold; fresh email code for withdrawal creation AND bank-account change.
- FIFO reserve/debit; admin records `lender_withdrawal` with evidence; 'out' movement finalized; once recorded executed it is **FINAL** in-platform (bank failures handled offline, never reopen); withdrawal confirmation in documents; pending withdrawals on dashboard; notification sent.

### Step 13 — Reconciliation close-out (assert after full run)
Stories: SYS-RECON-1, ADM-RECON-1, SYS-AUDIT-1
- With no pending/suspense/exception items: per currency, collection-account bank balances = sum of investor balances + Garanta accrued commissions/revenue.
- Reconciliation workspace breaks out per currency: bank-stated balance, ledger investor balances, Garanta accrued revenue/commission, suspense/unmatched cash, pending/exception balances, reconciliation difference.
- Every step above produced immutable audit entries (no edit/delete).

---

## 2. P0/P1 Admin-Side Stories by Console Section

### Dashboard
| ID | P | Checks |
|---|---|---|
| ADM-DAILY-REPORTS-1 | P1 | Exactly 7 daily reports: cash reconciliation, balance ageing, pending/forced withdrawals, FX delta, failed communications, due/late/defaulted loans, pending admin actions; each reachable, current data |
| ADM-BAL-AGEING-1 | P0 | Ageing workspace shows balance ages + deadline exposures; ages advance with time-travel; feeds daily report |

### Tasks / queues
| ID | P | Checks |
|---|---|---|
| ADM-QUEUE-1 | P1 | Work queues with assignment, filters, permission-checked status transitions, internal notes + attachments, age/SLA columns, reason codes for approvals/overrides/holds |
| ADM-SLA-1 | P1 | Task stores event/due/completion timestamps, status, responsible user, overdue state flips when now > due (time-travel); covers cash recon, ageing, withdrawals, FX delta, failed comms, loan review, pending actions |
| SYS-WEBHOOK-2 | P1 | Declined/suspicious/ambiguous KYC and manual-review statuses (PEP, high risk, adverse media) create visible compliance tasks |

### Users
| ID | P | Checks |
|---|---|---|
| ADM-LENDER-CREATE-1 | P0 | Legal-entity lender: all **12 mandatory fields** (legal name, reg number, jurisdiction, registered address, rep name/email/phone, bank IBAN, KYB status, KYB date, risk rating, tax residency); save rejected if any missing; audited high-risk |
| ADM-LENDER-EVIDENCE-1 / ADM-ENTITY-1/2 | P0 | Financial activation blocked until KYB/AML evidence recorded; approved entity behaves like regular lender; hold blocks even after approval |
| LE-LENDER-CREATE-1 / LE-REP-UNIQUE-1 | P0/P1 | Exactly one representative/login per entity (second rejected); no Didit for entities; one person cannot represent two accounts |
| LE-MANUAL-INVEST-1 / ADM-MANUAL-INVEST-1 | P0/P1 | Manual investment entry only for active KYB-approved entities; appears in order book; audited high-risk |
| ACC-CLOSE-1 / ACC-CLOSE-PSEUDO-1 | P0/P1 | Closure only for clean/empty accounts; optional reversible pseudonymization of direct identifiers; financial/audit/tax records retained; login restricted after |
| ACC-STATUS-GATE-1 | P0 | Restricted and locked both block login + financial actions; admin can lock/suspend/restrict/close |
| INV-EMAIL-RECOVERY-1 | P1 | No self-service email recovery; admin re-verifies identity offline; audit records actor, timestamp, reason, old/new email, evidence summary |
| ADM-SEARCH-1 | P1 | Search returns user/entity/legal-entity-lender/borrower profiles with KYC/KYB status |
| ADM-NO-IMPERSONATE-1 | P1 | No impersonation feature anywhere (admin portal or API) |
| BORROWER-NO-LOGIN-1 / BOR-NOLOGIN-1 | P0 | No borrower registration/login path exists; reps/UBOs stored as entity data only |

### Compliance
| ID | P | Checks |
|---|---|---|
| ADM-KYC-2 | P0 | Manual review: open → approve/reject; records decision, officer, date, reason; reflected in user KYC status and gates |
| ADM-KYC-1 / ADM-KYC-REVIEW-1 | P1 | 14-state verification list visible; approve/reject/reopen/update transitions, all audit-logged with reason; provider report import/attach |
| ADM-KYC-3 | P1 | Trigger re-verification (→ re-verification required, blocks financial actions); off-platform document notes |
| ADM-KYC-4 | P1 | Status override needs role + reason code, immutable audit, single-actor suffices |
| SYS-HOLD-1 | P0 | Compliance hold overrides all product flows regardless of KYC state |
| BOR-COMPLIANCE-GATE-1 | P0 | Borrower KYB gate on publish/close/disburse/repay; hold override admin-only with reason code + audit |
| SYS-EVIDENCE-1 / ADM-EVIDENCE-1 / ADM-EVIDENCE-EXPORT-1 | P1 | Full evidence record (provider/session/report/webhook metadata, checksums, decisions); ZIP export packages, redacted or full mode, admin-only, audited; retention ≥ **10 years**, launch default no deletion |
| BOR-EVIDENCE-1 | P1 | Uploads malware-scanned, access-controlled, in KYB evidence workspace |

### Finance
| ID | P | Checks |
|---|---|---|
| ADM-BANKOP-1 | P0 | All **7 bank operation types** declarable: lender_deposit, lender_withdrawal, borrower_loan_disbursement, borrower_repayment, garanta_out, garanta_in, external FX settlement; linked to ledger/statement/evidence/timestamp; reversible ONLY via correction records |
| ADM-RECON-1 / SYS-RECON-1 | P0 | Per-currency reconciliation identity + exception queue (see Step 13) |
| ADM-ORDER-VALIDATE-1 / ADM-OVERSUB-1 | P0 | Fund validation vs allocation; oversubscription/refund queue; excess computed, never silently retained; confirmations audited |
| ADM-FORCED-WD-1 / ADM-PENALTY-FREEZE-1 | P0 | Day-60 queues: forced-withdrawal (IBAN known) and missing-IBAN penalty-mode review |
| ADM-FX-DELTA-1 / ADM-FX-1 | P0/P1 | Net FX deltas by day/period (only unsettled exchanges); `currency_exchange_external_settlement` declaration with sold/bought amounts, dates, references; each exchange linked to exactly one settlement (no double-settling); realized FX gain/loss computed |
| ADM-FIN-CORRECT-1 | P0 | Correction workspace; admin AND superadmin can approve; only mechanism to reverse bank operations; audited |
| ADM-BEXIO-1 / ADM-REVENUE-1 | P1 | Operational subledger export; configurable monthly Bexio debit/credit export; arbitrary-period accrued revenue reports |
| ADM-BAL-REMINDER-1 | P1 | Reminder schedule/templates superadmin-only; fire relative to deadlines with time-travel |

### Loans / marketplace
| ID | P | Checks |
|---|---|---|
| BOR-CREATE-1 / BOR-LOAN-CREATE-1 / BOR-LOAN-PUBLISH-1 | P0/P1 | See Step 0 checks (mandatory fields, sanity 1,000–1,000,000,000, LTV rules, publish gates) |
| MKT-EDIT-1/2 | P1/P0 | Pre-commitment: any field editable (audited); post-commitment: ONLY lowering total amount, mandatory custom investor message + reason, investors notified, no re-acceptance |
| ADM-FUNDING-CLOSE-1 / ADM-RELEASE-1 | P0 | Close/release admin-only, blocked without borrower KYB + no hold; disbursement declared as bank operation |
| ADM-REPAY-1 / ADM-SCHED-OVERRIDE-1 / ADM-EARLY-REPAY-1 | P0/P1 | Repayment declaration + distribution workspace; received/corrected marks; schedule override with version history; early/partial/operational-change records audited |
| ADM-RECOVERY-1 (plan/06 + plan/10) | P0/P1 | Recovery event captures ALL: gross recovered, external legal/recovery costs, third-party costs, Garanta recovery fee decision+amount, net received, waterfall split, evidence, rounding difference; waterfall order: (1) external recovery/legal costs (2) platform-approved recovery costs incl. Garanta fee (3) principal (4) contractual interest accrued until default (5) default/penalty interest (6) other penalties/costs; contractual interest cut off at default declaration date; penalty interest replaces (not stacks) from that date; lender lines half-up rounded, residual recorded as rounding difference |
| PROD-RECOVERY-1/2, PROD-PENALTY-1 | P0/P1 | Per-loan recovery terms inert before default; per-payment Garanta-fee apply/skip toggle; deterministic waterfall |
| ADM-WRITEOFF-1 | P1 | Write-off admin-only, workflow rules, audited |
| ADM-SECMKT-1 | P1 | Transfer monitor; non-standard listing queue; approve/reject/remove each requires reason AND disclosure note + audit (date, admin) |
| SEC-LIST-NONSTD-1 / SEC-BUY-NONSTD-1 / INV-SM-SELL-2 | P0/P1 | Non-performing listings invisible until admin approval; buyer sees status, days past due, recovery status, last payment date, public note + extra risk acknowledgement; no second admin approval at purchase |
| ADM-MATCHANGE-1 | P1 | Material-change communication: exactly one of three modes (public note only / bulk email only / both), audited |
| BOR-DRAWDOWN-1 / BOR-BANKCHG-1 | P0/P1 | Drawdown confirmation, monitoring docs, servicing notes; bank-account changes need elevated verification + approval + audit; signatory authority verified before contract signature |
| ORIG-RATING-1 / BOR-INVESTOR-VIEW-1 / ORIG-DISCLOSURE-1 | P1 | 21-option grade picker (AAA…D, Unrated), manual only; undeclared optional borrower fields never render (no labels/placeholders) |
| ADM-CLOSE-1 / ADM-PARTIAL-1 | P0 | See Step 5 |

### Reports
| ID | P | Checks |
|---|---|---|
| ADM-EXPORT-1 | P1 | PDF/CSV/ZIP; redacted or full mode; targets accounting/audit/regulatory/board/bank/operational; admin-only |
| ADM-AUDIT-1 | P0 | Audit log explorer; every high-risk action logged; immutable |
| ADM-STATEMENTS-1 | P1 | Borrower account statement + borrower annual tax statement, each PDF AND CSV |
| ADM-REVENUE-1 | P1 | Arbitrary-period accrued revenue from ledger |
| AUDIT-AUTH-EVENTS-1 | P1 | Successful/failed logins + permission changes create audit events; access logs exportable |

### Settings
| ID | P | Checks |
|---|---|---|
| ADM-ROLES-1 / ADM-ROLE-1 | P0 | Exactly 2 roles: superadmin (parametrization) + admin (operations); admin blocked from superadmin functions (admin accounts, password resets, templates, currency/FX/reminder config, IBAN change); no maker-checker anywhere |
| ADM-SUPER-ACCOUNTS-1 / ADM-LOGIN-1 / ADM-NO-FORGOT-PW-1 | P0 | Admin auth = email + password + email code (all three); no forgot-password; only superadmin resets admin passwords; passwords hashed |
| SUPER-IBAN-1 / ADM-GARANTA-IBAN-1 | P0/P1 | Collection account/IBAN change superadmin-only, server-side enforced, audited high-risk |
| SA-CONFIG-1 / ADM-SUPER-CONFIG-1 / SA-CONFIG-MIN-1 | P1 | Superadmin owns: currencies, FX fee/pairs/quote/sanity thresholds, reminder templates, min investment (1,000 default), product params; brand (BANXUM), operator (Garanta Finanzgruppe AG), support email, domains, footers are template variables — never hardcoded |
| ADM-FX-CONFIG-1 | P1 | Superadmin-only FX settings vs admin-configurable per-investor daily conversion limit (with audit); admin blocked from superadmin FX settings |
| ADM-DOC-TPL-1 | P1 | Document template versioning + audit, superadmin publish only |
| SUPER-BOOTSTRAP-1 / ADM-SUPER-ENV-1 | P1 | Superadmin exists from env config at deploy; no UI to create/edit/remove superadmin |
| PROD-VERSION-1 / PROD-FEES-2 / PROD-CURRENCY-1 | P0/P1 | Product config versioned; loans pinned to approval-time version; lender_payment_fee = 0; single-currency loans; CHF+EUR only |
| ADM-NO-STEPUP-1 | P0 | No step-up prompts on admin sensitive actions; each fully logged (actor, timestamp, action, target, before/after, reason) |

### QA mode (time-travel harness)
| ID | P | Checks |
|---|---|---|
| SYS-TZ-1 | P0 | All calendar rules (30/60d, reminders, day-5/day-16, funding deadlines, report cutoffs, dashboard buckets) flip at Europe/Zurich midnight; UTC storage, Zurich rendering; no off-by-one |
| INV-SENSITIVE-CODE-EXPIRY-1 | P0 | Code at <10 min succeeds; >10 min rejected, action not executed |
| INV-SESSION-LONG-1 / TOKEN-LIFECYCLE-1 | P1 | Time advance does NOT log investor out; expired access token rejected while refresh works; revoked refresh mints nothing; admin sessions expire |
| ADM-SLA-1, ADM-BAL-AGEING-1, ADM-FORCED-WD-1, ADM-PENALTY-FREEZE-1, ADM-BAL-REMINDER-1 | P0/P1 | Covered above — all require time-travel |
| INV-ORDER-6 | P1 | Source pledged inside 30-day window funds a loan whose deadline is after the entry's day-30 |

---

## 3. Global Invariants (deduplicated — assert continuously during the run)

**Compliance & gating**
1. Client funds segregated from Garanta operating funds, non-interest-bearing, never used for Garanta's own account.
2. Compliance holds override ALL product flows for any party, regardless of KYC state.
3. Blocking KYC statuses (pending, declined, manual review, expired, high risk, sanctions hit, PEP hit, adverse media hit, re-verification required) block dashboard, deposit, balance, FX, investment completion, contract acceptance, withdrawal, loan publication, funding close, disbursement — server-side.
4. Sanctions hits and confirmed identity/document fraud always block onboarding; PEP/high-risk/adverse-media/unclear-ownership never auto-approved (manual AML review).
5. Verified status never granted from unsigned/stale/replayed/unmatched webhooks; idempotency by vendor event/session ID.
6. Borrowers are legal entities only, admin-created, never log in; legal-entity lenders never self-register, have exactly one representative/login, skip Didit; no financial activity before admin-recorded KYB/AML approval.
7. No funds release before: funding conditions met, contracts effective, borrower KYB/AML still approved, payment reconciliation passed.
8. Investor eligibility re-checked at BOTH order time and closing time; buyer eligibility re-checked at secondary settlement.

**Money, ledger, ageing**
9. Every source entry: 30-day investment deadline + 60-day absolute withdrawal deadline (non-extendable); Europe/Zurich calendar days.
10. Sources > 30 days old are withdraw-only; investment rejected with explicit error + per-currency investable vs withdraw-only breakdown.
11. Penalty: launch default 1% simple daily on overdue source, capped at remaining overdue balance, never negative, terminal penalty_exhausted.
12. FIFO source consumption within each currency for investments, withdrawals, FX, fees, penalties.
13. FX never resets ageing; target inherits EARLIEST consumed investment and withdrawal deadlines; lineage retained.
14. FX: pairs CHF/EUR + EUR/CHF only; fee 1.5%; no minimum; max CHF 100,000/investor/day; 1-minute quote lock; storage ≥ 6 decimals.
15. Reconciliation identity: bank balances = investor balances + Garanta accrued revenue, per currency, when no pending/suspense/exception items.
16. Bank operation declarations reversible ONLY via correction/reversal records — never edited/deleted in place.
17. Withdrawals recorded executed are final in-platform.

**Orders & marketplace**
18. Investors can never cancel orders (UI or API); max 50 pending orders; pending orders never reserve capacity or move funded progress.
19. Min investment 1,000 CHF/EUR; max = remaining cap; allocation strictly FCFS by allocation timestamp / bank value date; funded total never exceeds cap; excess always marked refund/release due.
20. Publish blocked when mandatory fields missing or deadline past / > 29 calendar days out; defaulted loans never on primary market.
21. After committed investments: total amount may only be lowered, with mandatory message + reason + notification.
22. Risk acknowledgement required before every investment order; every clickwrap records version, snapshot, timestamp, user, context.
23. Loan principal 1,000 ≤ P ≤ 1,000,000,000; LTV always system-computed (P / collateral × 100); collateral 0 → warn + hide LTV; collateral > P → warn + show LTV; incomplete loans never persisted.
24. Each installment line rounded to minor unit; final installment absorbs rounding residue; single-currency loans; borrower success fee 2%–4% withheld, never investor-visible, never alters schedule; lender_payment_fee = 0 at launch.
25. Penalty/default interest replaces contractual interest from the official default declaration date; recovery waterfall order fixed (6 steps); recovery terms inert before default.

**Secondary market**
26. Whole holdings only; positive principal required; fees 0.25%/0.75% at settlement on price EXCLUDING accrued interest, half-up rounding; accrued interest daily pro rata to seller up to settlement, future interest to buyer; settlement ≤ 60 days; seller proceeds = new source with fresh clocks; non-standard listings need admin approval + disclosure note + extra buyer acknowledgement; pro-rata economics preserved through all transfers.

**Auth & access**
27. Investors: passwordless magic-link only, long-lived revocable sessions, no idle expiry; mandatory phone verification; fresh email code (10 min / 3 attempts / throttled resend) for withdrawal creation, withdrawal bank-account change, FX, primary investment, secondary listing, secondary purchase.
28. Admin: email + password + email code; no forgot-password; superadmin-only password resets; exactly 2 roles; superadmin env-managed only; collection IBAN changes superadmin-only; no impersonation; no maker-checker at launch.
29. Restricted and locked statuses both block login + financial actions; closure only for clean/empty accounts; pseudonymization reversible, records retained.

**Audit, evidence, presentation**
30. Every lifecycle event → immutable audit entry; high-risk actions carry permission checks + reason codes; logins/permission changes audited.
31. KYC/KYB/AML evidence on Swiss-controlled storage, retained ≥ 10 years (launch: no deletion); exports admin-only PDF/CSV/ZIP, offline delivery.
32. All calendar-day rules use Europe/Zurich local dates; storage UTC timezone-aware.
33. BANXUM/Garanta Finanzgruppe AG/support email/domains/footers are template variables, never hardcoded.
34. Exposure always presented as pro-rata assigned loan claims — never securities, notes, bonds, fund units, deposits, or managed portfolios.
35. Undeclared optional borrower fields never render (no labels, no placeholders); amounts display 2 decimals (FX quote/confirm up to 4); legal/transaction PDFs never emailed by default; internal distribution artifacts and bank statements never exposed to lenders.

---

## 4. Stories Blocked by External Providers or User Input

**BLOCKED — live provider required (mock/local path exists; test the mock, defer live validation):**
- INV-AUTH-1 (P0) — magic-link email delivery: dev/mock capture sufficient for flow; live email provider needed for staging/prod.
- INV-AUTH-2 / TWILIO-LIVE-SMS-1 (P0/P1) — real SMS via Twilio Verify: needs staging/prod credentials + phone-number policies; local/mock provider testable now.
- INV-AUTH-3 (P0) — sensitive-action email codes: live delivery blocked; local capture testable.
- INV-KYC-1 (P0) — real Didit sessions/webhooks/report capture: need reachable staging/production domain; mock provider (`DIDIT_SESSION_PROVIDER`) testable now.
- INV-FX-1 / INV-FX-QUOTE-1 (P0/P1) — live Yahoo Finance quotes: mock rates allowed only in local/test; live sanity behavior deferred.
- INV-NOTIFY-1 (P1), ADM-FAILED-EMAIL-1 (P1), ADM-EMAIL-TPL-1 (P2) — real email delivery/failure queue/test-send need live email provider.

**BLOCKED — needs user/operator input:**
- INV-AUTH-4 (P2) — offline email-recovery flow requires human identity re-verification.
- ADM-SUPER-ENV-1 / SUPER-BOOTSTRAP-1 (P1) — superadmin bootstrap requires deployment env configuration (verify absence of UI path only).

---

## 5. Deferred / Not-v1 (DO NOT TEST; absence is not a bug)

**Compliance/KYC:** suitability/investor-classification questionnaire (DEC-004); in-platform ongoing AML monitoring automation (KYC-DEC-007); self-service KYB / UBO automation (KYC-DEC-002); KYC appeal/retry path; evidence export manifest/redaction rules; retention beyond 10 years; EU/EEA country block list; accepted legal-entity forms/SPVs; final legal wording (risk warnings DEC-009, bulletin board DEC-008, FX model, assignment templates DOC-DEC-005, recovery fee disclosures PROD-DEC-009); FINMA licence-fit confirmation.

**Auth/accounts:** maker-checker/dual approval (DEC-011) — only future enablement by config; admin step-up auth; admin impersonation; auditor/read-only portal; granular investor permissions (viewer/transaction/balance/approver); legal-entity multi-user/org model; self-service account closure; "log out all devices" (ACC-DEC-007); restricted-vs-locked semantic distinction; auto-locking inactive accounts; support role separation; undefined values (magic-link expiry/rate limits, Twilio retry limits, admin code expiry, resend cooldown seconds, password policy, closure reason codes, break-glass path DEC-010); system-verified closure prerequisites (attestation is acceptable interim behavior).

**Product/origination:** custom/manual repayment schedule; late fees (field exists, inactive); term sanity bounds (PROD-DEC-004); currency-specific amount limits; unsecured-exception reason code (PROD-DEC-002); collateral-type-specific data models (PROD-DEC-003); other day-count conventions/frequencies/interest components; rate auto-derivation from risk grade; platform credit memo (ORIG-DEC-002); draft-loan/rejection tracking (ORIG-DEC-007); collateral valuation policy/LTV constraints (DEC-006); LTV rounding rules; minimum funding threshold (none at launch — admin decides partial closes case-by-case, PAY-DEC-008/014).

**Marketplace/investor portal:** auto-invest/auto-reinvestment; hard concentration limits (warnings only, MKT-DEC-018); notification-preference management (only marketing consent capture); private/segmented listings (MKT-DEC-013); brokers/introducers (MKT-DEC-012); allocation methods beyond FCFS (pro-rata, manual, tiers, auctions); transfer restrictions by jurisdiction ("if enabled"); re-acceptance after amount reduction (notification suffices); tie-break for same bank value date (MKT-DEC-001); 50-order cap scope (global vs per-loan); non-zero secondary minimum fee; investor documents beyond English; 'Mark interest' feature (underspecified); pre-registration public preview scope (KYC-DEC-003).

**Admin/servicing:** structured borrower post-funding reporting (SERV-DEC-010/RISK-DEC-001/003); offline credit evidence area ("if needed later"); document template workspace ("if exposed"); day-60 penalty mechanics admin UI (env-config only at launch); deeper deployment-only product parameters (PROD-DEC-007); KYB evidence category naming (configurable); SLA contractual commitments (internal visibility only); manual legal-entity investment evidence fields (KYC-DEC-001); disclosure of internal distribution artifacts to lenders ("later disclosure policy").
