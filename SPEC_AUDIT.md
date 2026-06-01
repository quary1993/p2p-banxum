# Spec Audit — Findings Report

Status: Review report. No spec files were modified; these are findings and suggestions.
Reviewer pass date: 2026-06-01.
Scope reviewed: `IMPLEMENTATION_PLAN.md`, `plan/00`–`plan/21`, `ADMIN_TODO.md`, `admin_todo_garanta.md`, `admin_todo_accounts.md`, `admin_todo_tech.md`.

## 0. Overall Assessment

The specification is in strong shape and close to implementation-ready. The latest revisions resolved the great majority of issues a first read would surface. Cross-module consistency is high, decisions carry IDs/dates/owners, and the IMPLEMENTATION_PLAN tracks the module decisions closely.

This report lists what is still **vital and undocumented**, what is **documented but under-specified**, and **minor inconsistencies/nits**. It ends with items already resolved (so they are not re-raised) and two naming/definition questions that need a product answer.

Severity legend:
- **P1 — Vital**: affects money correctness, fund safety, account access, or legal identity. Close before or early in the relevant build.
- **P2 — Important**: a real gap that should be closed before the owning module is "done."
- **P3 — Minor / nit / consistency**: cleanup, wording, or low-risk edge cases.

---

## 1. P1 — Vital gaps

All P1 items from the 2026-06-01 audit have been resolved in the planning docs:

- Brand and legal naming is now explicit: BANXUM is the platform brand and Garanta Finanzgruppe AG is the legal operator. Templates and generated documents must use configurable platform and operator variables rather than hardcoded literals.
- The previously separate originator terminology has been collapsed into borrower everywhere. Borrower is the only borrower-side party type for v1.
- Day-60 balance penalty mechanics are defined as env/deployment-configurable, with a 1% simple daily launch default, Europe/Zurich cadence, cap at remaining overdue source balance, no negative balances, and terminal penalty_exhausted status if fully consumed.
- Balance-funded primary-market commitments are blocked when the loan funding deadline exceeds the selected source lots remaining 30-day investment window.
- Investor email-login recovery is documented as an offline support process with identity re-verification using account/KYC evidence and verified phone/account data.
- Europe/Zurich is the authoritative business timezone for business day-counting; timestamps remain stored in UTC.

## 2. P2 — Important gaps

No P2 items were closed in this pass.

## 3. P3 — Minor / nit / consistency

- **P3-1. "Minimum close amount" listing field contradicts "no minimum funding threshold."** Listing Data in [plan/09_marketplace_investments.md](plan/09_marketplace_investments.md) lists "Minimum close amount," but PAY-DEC-014 sets no fixed minimum partial-funding threshold. Remove the field or reconcile it as an optional admin-set soft target.
- **P3-2. Secondary-market "60-day maximum operational settlement period" is a pre-balance-model leftover.** With balance-funded instant settlement (MKT-DEC-016/PAY-DEC-009) the 60-day max only applies to a deposit-then-buy path. Scope the wording to that path or drop it to avoid implying delayed settlement.
- **P3-3. Loan state "Grace period" is listed without a crisp transition.** [plan/11_loan_servicing_repayments.md](plan/11_loan_servicing_repayments.md) Loan States includes "Grace period"; the arrears lifecycle says grace = days 1–4. Either bind the state to days 1–4 explicitly or drop it (status can go Current → Late at day 5).
- **P3-4. Withdrawal minimum amount and bank-fee bearer are undefined.** No minimum withdrawal; who absorbs the outgoing transfer fee. Tiny residual balances (e.g., after penalties) could cost more to remit than their value. Consider a configurable minimum and a stance on fees.
- **P3-5. Investor-facing fee VAT stance.** Displayed fees (1.5% FX, 0.25%/0.75% SM, borrower success fee) — inclusive or exclusive of Swiss VAT? FIN-DEC-005 defers VAT to the accountant, but the *display* needs a position. Minor but real for disclosure.
- **P3-6. Idempotency-key generation ownership for investor command endpoints.** §5 says admin financial ops get a server-side key; investor command-endpoint key generation/dedupe window isn't stated. Specify client-generated key (e.g., ULID) + server dedupe window.
- **P3-7. Indefinite retention of full email content (PII).** COMMS-DEC-004 + SEC-DEC-003 store full email bodies indefinitely; these contain PII. Flag as a conscious privacy decision and a candidate for the future granular retention schedule.
- **P3-8. DSAR / right-of-access has no v1 operational path.** Privacy lists it "where applicable" with no design. A one-line runbook (admin generates a per-subject export on email request) is enough for launch.
- **P3-9. [plan/10_payments_ledger_custody.md](plan/10_payments_ledger_custody.md) Q/A numbering bug.** The trailing Q/A items run 24, 25, 26, then a second 25 — duplicate/misordered numbers. Cosmetic.
- **P3-10. Resolved.** Product/platform naming is now canonicalized as BANXUM, with Garanta Finanzgruppe AG as legal operator.
- **P3-11. Public marketplace preview "status" field is not enumerated.** [plan/09_marketplace_investments.md](plan/09_marketplace_investments.md) exposes "status" pre-login but never lists allowed public values; confirm late/defaulted are never shown publicly (defaulted loans aren't on primary market anyway, but the enumeration should be explicit).
- **P3-12. "Affected investors / affected lenders" audience for public notes and bulk emails is undefined.** RISK-DEC-004 / COMMS-DEC-005 don't define the recipient set (current holders only vs. anyone who ever held the claim). Recommend: current holders at notification time.

---

## 4. Already resolved since the prior review pass (not re-raised)

These were natural first-read concerns and are now addressed in-document:
- FX no longer resets ageing; target lot inherits the newest consumed source deadline (PAY-DEC-017/021).
- Full recovery waterfall with Garanta recovery fee, default/penalty interest, interest cutoff at default, and explicit recovery rounding difference (PROD-DEC-009, RISK-DEC-005/006, SERV-DEC-013).
- Bank-operation taxonomy + ledger-bank reconciliation equation + accrued-revenue reporting (PAY-DEC-026, FIN-DEC-007).
- Realized FX gain/loss from declared external settlement (PAY-DEC-027, FIN-DEC-008).
- Secondary market scoped to whole-holding bulletin-board transfers, discount/premium pricing, accrued-interest split, non-standard-listing admin approval (MKT-DEC-007/009/016/017/020).
- AWS `eu-central-2` Zurich for the full stack; self-hosted Postgres/Redis in Docker on one EC2 host; WeasyPrint; ClamAV quarantine with 50 MB limit; webhook retry schedule; auth/rate-limit defaults; expected 50–100 concurrent users (admin_todo_tech, INFRA-DEC-009/011/012). The earlier IMPLEMENTATION_PLAN Frankfurt/RDS wording is now consistent with Zurich/self-hosted.
- Bexio selected as the accounting system; FX provider confirmed as Yahoo Finance (CHF/EUR only) with CHF 100k/day cap and 6-dp storage / 2-dp display / 4-dp confirmation, half-up rounding.
- Swiss-resident KYC/KYB/AML evidence storage with ≥10-year retention and full provider-report/webhook retention where possible (KYC-DEC-005, SEC-DEC-001/003/006).
- Reversible closure pseudonymization via offline-key asymmetric encryption (SEC-DEC-004).
- KYB-approval-before-transactions gate for legal-entity lenders and borrowers (KYC-DEC-008).

---

## 5. Open questions for product/Garanta

No P1 product questions remain open from this audit pass.

---

## 6. Suggested doc-hygiene additions (not blockers)

- A short **glossary** (in `plan/00_index.md`) defining holding, lot, source entry, claim, project, "affected" audience, and bank-operation types — several terms are load-bearing and used slightly differently across modules.
- A worked **module README example** (e.g., for `ledger`) so every later module follows one concrete template.
- A named **day-1 runbook list** under `docs/runbooks/`: deposit reconciliation, withdrawal execution, refund-to-sender, forced withdrawal, FX delta settlement, suspense escalation, deposit-reversal/clawback, ledger-imbalance triage, backup restore, KYC manual override.
- A one-paragraph **financial maintenance-mode / kill-switch** note (how to put money movement read-only if a ledger-imbalance alert fires), referenced from the ledger integrity checker in Phase 15.
