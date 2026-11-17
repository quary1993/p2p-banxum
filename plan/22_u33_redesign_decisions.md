# U33 Redesign Reconciliation Decisions

Status: Approved product decisions, current at 2026-11-13 (group 2 approved 2026-11-04, group 3 completed 2026-11-08, final answers 2026-11-13 and round 2 of 2026-11-16 at the end of this file; they prevail where they say so).
Source: "Lot 113 - Register of reconciliation decisions with Vlad" (Romanian original, received 2026-11-09), answering the 39 items of `BANXUM_redesign_nov3_decisions` (design package `website_redesign_nov3`, edition "Banxum unified U33", 3 Nov 2026).
Owner: Banxum product (decisions); Vlad (implementation).

## How These Decisions Apply

- The decisions below replace the conflicting rules of the U33 design and the conflicting platform decisions listed under "Supersedes". The rest of the approved U33 design and behaviour stays.
- "Approved" means a product decision. It is not an implementation, a legal check or a backend audit. Open confirmations are listed in each decision.
- Item numbers 1-39 match the reconciliation file. Each decision is listed once.
- For items 29 and 39 the follow-up work is approved, not a visual result and not the removal of features.
- The implementation order is in `IMPLEMENTATION_PLAN.md`, "Phase 17: U33 Redesign and Reconciliation Decisions".

| Group | Topic | Items |
| --- | --- | --- |
| 1 | Access, security and profile | 1, 25, 26, 27, 28 |
| 2 | Money and bank accounts | 2, 3, 4, 5, 33 |
| 3 | Product and security (collateral) | 15, 16, 21, 38 |
| 4 | Minimum, interest and repayment | 8, 10, 11 |
| 5 | States and exceptions | 9, 22, 29 |
| 6 | Resale and fees | 6, 7, 12 |
| 7 | Credit file and contracts | 13, 14, 20, 23, 24 |
| 8 | Smart Invest, saved items and notifications | 17, 18, 19, 30 |
| 9 | Localization | 31, 32 |
| 10 | Public area, identity, texts and resources | 34, 35, 36, 37, 39 |

## Group 1 - Access, Security and Profile

### U33-DEC-01: Sign-In and Confirmation of Operations

Status: Approved (new solution). Open implementation confirmations below.

> Updated 2026-11-13 (Q05): password rules, Twilio SMS, trusted device 30 days, 10 recovery codes, migration at next sign-in, assisted recovery (Vlad validates first), admins with authenticator app. Details: "Final Answers Of 2026-11-13".

> Updated 2026-11-17 (Vlad, D1/D3): NIST password rules; no migration flow (no real investors; Eduard to confirm). Details: "Round 2 Answers Of 2026-11-16".

Supersedes: ACC-DEC-001 (magic-link login), ACC-DEC-008 (email code for sensitive actions), ACC-DEC-009 (email code + PIN).

Decision:

- Investor login uses a **password plus a second factor: an SMS code or an authenticator-app code**, chosen by the investor. Two-factor authentication is mandatory. The method is enrolled and verified once; the investor does not type a phone number at each login. Both methods are not required. No passkeys and no magic link as an alternative login.
- Investments, withdrawals, bank account changes and resale actions need a review step and **only the personal PIN**, inside the authenticated session. Each investment is confirmed separately. Agreement checkboxes are unchecked by default.
- The server authorization is bound to the exact operation, amount and destination; it expires and can be used once. Changed data needs a new confirmation. The PIN is reusable; the authorization is not.
- Attempt limits, audit logging and alerts stay.

Recovery:

| Case | Procedure |
| --- | --- |
| Forgotten password, second factor available | Expiring single-use link to the verified email **plus the configured second factor**, before the new password. The link alone does not authenticate. |
| Forgotten PIN | Password + configured second factor, then a new PIN. PIN-only confirmation of operations does not remove the protection of recovery. |
| Forgotten password and PIN | Password recovery, then PIN recovery, as above. |
| Second factor not available / not enough access | Assisted recovery: identity verification, controlled enrolment and revocation of the old access. No bypass by email or by an unverified phone. |

- Changing the second-factor method or the verified phone needs access/identity control and a notification. Email alone cannot switch off the second factor. Every reset is notified.
- Password recovery or factor replacement revokes old sessions and tokens. A PIN reset invalidates unfinished authorizations. Recovery never executes transactions.

To clarify with Vlad: the operational procedure, migration of existing accounts, the SMS service and the recovery implementation. SMS is more exposed than an authenticator app (including number takeover). The PIN alone is not a new second factor. A security review stays necessary, without silently adding a code to each operation.

### U33-DEC-25: Sessions, Sign-In History and Security Alerts

Status: Approved (design).

> Updated 2026-11-13 (Q06): approximate city from a server-side IP database; 365 days kept, last 50 shown. Details: "Final Answers Of 2026-11-13".

Supersedes: ACC-DEC-007 (device list was "nice to have").

Decision:

- Security settings show the device/browser, approximate location, last activity and the current session. The investor can close one session or all other sessions, with real revocation of access.
- The sign-in history keeps date/time, device, approximate location, method and result, also after sessions end.
- Email alerts for a new device/browser and for important security changes, independent of marketing consent.
- The existing mechanisms are adapted to U33-DEC-01. IP location is not GPS; fields and history retention must match the real data and the privacy rules. Verification covers real revocation and alert triggering, not only the interface.

### U33-DEC-26: Changes to Personal Data

Status: Approved (Vlad's platform).
Confirms: ACC-DEC-006 support recovery, COMMS-DEC-006.

Decision:

- Verified personal data, including email, phone and address, cannot be edited freely. The platform shows the available information and a "Contact support to change" access.
- The team verifies the identity and makes the authorized change. An email request alone is not proof of identity.
- No invented missing fields. A change is never shown as done before it is confirmed. Corrections stay possible, and the procedure is aligned with access recovery (U33-DEC-01).

### U33-DEC-27: Self-Declaration and Periodic Review

Status: Approved (extension). Operational/compliance details open.

> Updated 2026-11-13 (Q12): declarations, review triggers, blocking of new investments, re-verification notices 30/7 days, company form. Details: "Final Answers Of 2026-11-13".

Supersedes in part: KYC-DEC-007 (no platform monitoring).

Decision:

- Didit stays. The relevant declarations are added to onboarding and to the profile: beneficial owner of the funds, source of funds, PEP status and expected yearly volume. A "yes" to PEP leads to a review; the platform does not force a "I am not a PEP" declaration.
- The admin keeps the declaration, its date, changes, review result and any requested additions.
- A re-verification date can be set per investor, with notification and update of the required data/verification. Handling can be manual. A full continuous-monitoring system is not required.

To define (operations/compliance): exact fields, responsibilities, escalation and periodicity. Automatic yearly re-verification is not approved. The Didit result does not automatically approve the declarations or count as compliance approval.

### U33-DEC-28: Account Closure

Status: Approved (Vlad's platform).
Confirms: ACC-DEC-006.

Decision:

- The "Close account" button sends a **request** to the team. The team checks balances, investments and open obligations before closing. The confirmation that the request was received is separate from the confirmation of the actual closure.
- No promise of instant closure or of deleting all records. Records and operations needed to settle obligations are kept.

## Group 2 - Money and Bank Accounts (approved 2026-11-04)

### U33-DEC-02: Where Repayments Are Paid

Status: Approved (Vlad's platform).
Confirms: PAY-DEC-005.

Decision:

- Principal, interest and recoveries go to the **Banxum balance**, not directly to the investor's IBAN. The investor reinvests by explicit confirmation or asks for a withdrawal. Money not invested follows U33-DEC-03.
- CHF/EUR and the principal/interest components stay separate.
- All functional effects and texts in the platform, public site, schedules, reports and notifications that say "paid directly to the bank account" are adapted. This is not only a wording change.

### U33-DEC-03: Return Deadline and Return Notices

Status: Approved (mixed variant).

> Updated 2026-11-13 (Q01): day 56 last day, request on day 57, previous settlement day for holidays, debit of the Garanta account within 60 days, notices 14/10/3 days before. Details: "Final Answers Of 2026-11-13".

Supersedes: the 58-day return of PAY-DEC-017 (2026-10-16) and the reminder days 25/46/53/56/57/58.

Decision:

- Money not invested is returned after **56 days**, with notices **10 days and 3 days before** the return, then a confirmation of the return. The concrete date is shown. Urgent notices about the IBAN stay separate.
- A reservation does not reset or silently extend the period. The project for which money is reserved must close before the last allowed holding day; reservation eligibility follows the 56-day deadline.
- Vlad must specify the day counting, the moment the return starts and the handling of non-business days, so that the buffer before day 60 is real. The change is not a number swap in the interface with the old behaviour kept. The legal framing of holding money is confirmed separately.

### U33-DEC-04: Impossible Return and Penalty

Status: Approved (adapted solution).

> Updated 2026-11-13 (Q02): state "Return failed", daily notices, compliance after 5 days or at once when the 60-day limit is threatened. Details: "Final Answers Of 2026-11-13".

Supersedes: the 1% daily penalty and penalty mode of PAY-DEC-017 / PAY-DEC-022.

Decision:

- The **1% daily penalty is removed**.
- A bank account is verified before the first investment. The last valid IBAN needed for the return cannot be removed while there is money to return.
- If a return fails or the IBAN becomes invalid: a clear message, correction/verification of the data and intervention by the team. Money past its deadline does not become available for reinvestment again. Support and the documents needed to fix the situation stay accessible.
- States and procedure follow the 56 days and are validated operationally and legally: a simple block or a fee does not solve an exceeded deadline.

### U33-DEC-05: Bank Accounts and Deposits

Status: Approved (Vlad's platform, with adaptations).

> Updated 2026-11-13 (Q02.5): returns only to a verified account; the deposit transfer can serve as proof of the holder. Details: "Final Answers Of 2026-11-13".

Updates: PAY-DEC-022 payout-IBAN controls.

Decision:

- Several verified bank accounts in the investor's own name; one **default return account per currency**. "Verified" and "Pending verification" are shown separately.
- Adding or changing an account is confirmed with the PIN (U33-DEC-01). The destination becomes usable after the holder is verified. The transfer reference, name or email does not replace that verification. Unidentified or unclear deposits are checked by hand before they become available.
- The general 48-hour block of the design is removed. Holder checks, confirmations and change notifications stay.

### U33-DEC-33: Currency Exchange

Status: Approved (the existing function stays switched off).

> Updated 2026-11-13 (Q25): the old exchange screen is removed from the investor area. Details: "Final Answers Of 2026-11-13".

Confirms: PAY-DEC-018 as switched off on 2026-10-16.

Decision: CHF and EUR are separate, with no implicit conversion. The FX code can stay, with no active FX offer or fee. Switching it on later needs a separate decision, the display of rate and costs, confirmation and verification.

## Group 3 - Product and Security (completed 2026-11-08)

### U33-DEC-15: Banxum Co-Investment

Status: Approved (new/adapted function).

> Updated 2026-11-13 (Q04): Garanta investor account; label "Banxum invests" without amount from the confirmed reservation; equal terms. Details: "Final Answers Of 2026-11-13".

Decision:

- Banxum may co-invest from its own funds **case by case, with no obligation and no minimum percentage**. No participation does not block publication.
- The actual participation is identified by entity, amount, status and operation reference, separate from an intention to participate and from the share kept by an originator.
- No priority, identical terms or guaranteed recovery are implied. Terms and timing are confirmed contractually/operationally. Public statements that promise participation in every loan are corrected.

### U33-DEC-16: Risk Ratings

Status: Approved (design).
Supersedes: ORIG-DEC-004 investor visibility; rating criteria of MKT-DEC-026.

Decision:

- No risk ratings or risk classes in the investor experience: public site, platform, filters, Smart Invest, reports and generated documents. Financial data, securities, late payments and Default stay.
- Existing ratings may stay passively in the admin **only if this costs nothing extra**; their use, completion or development is not planned. They never influence filtering or matching in a hidden way. Migration of existing preferences removes the rating criteria explicitly, without investing automatically.

### U33-DEC-21: Several Securities and Structured Details

Status: Approved (design).

> **Changed 2026-11-13** (Q15, C06): vehicles type, invoices closed for new securities; main security chosen explicitly; LTV on the sum of the distinct relevant assets. Details: "Final Answers Of 2026-11-13".

Supersedes: PROD-DEC-002 / PROD-DEC-003 (one collateral item per loan).

Decision:

- A loan can have several securities, managed separately: type of asset/right, holder/guarantor, rank, status, value, valuation date/source and appraiser, insurance and relevant documents, only where they apply. For personal/corporate undertakings: scope and limit of the undertaking.
- The opportunity, the credit file and the filters use the same data. Asset value, loan and prior-ranking debt are kept separate; a cumulative ratio is labelled as such. The guarantor's wealth is never added to the property value, and the same asset is never counted twice.
- The existing taxonomy is reconciled, including vehicles, inventory, pledged securities and cash where they really exist. "Mixed" is split into its securities, "Other" needs a description, and "asset-backed" does not replace the identification of the right. No invented data at migration; this does not approve new products. Mandatory eligibility is in U33-DEC-38.

Implemented 2026-11-10 (Phase 17.4): `plan/07_loan_product_catalog.md` PROD-DEC-003 note. A vehicle type is not added (no vehicle loans exist today); existing "mixed" records stay until an admin splits them.

### U33-DEC-38: Public Wording and Security Eligibility

Status: Approved (final).

> Updated 2026-11-13 (Q13): publication blocked until all required documents and a named verification exist; a dedicated verifier role. Details: "Final Answers Of 2026-11-13".

Supersedes: the "unsecured exception" collateral type for new loans (PROD-DEC-002).

Decision:

- Every loan must have **collateral or guarantees, with no unsecured exceptions**; the requirement is not limited to physical assets. The admin does not allow publication of a new ineligible loan. Rights and documents must be verified; a label alone is not proof. History stays factual, with no guarantees invented retroactively.
- The approved wording "Every loan is secured by collateral or guarantees" is published in line with real eligibility. Universal statements about "real assets" are replaced and "Your investment is protected" is removed. This does not mean guaranteed repayment or a risk-free investment.
- Classification follows the concrete right: an invoice is a document; a receivable against a third party can be collateral if validly pledged. The assignment of the financed claim alone does not create an extra security. The debtor's promissory note does not automatically become extra collateral or a third-party guarantee; a third party's aval/undertaking is examined separately. Documents and applicable law are checked, without reopening the product choice.

## Group 4 - Minimum, Interest and Repayment

### U33-DEC-08: Cap for Swiss Borrowers and Minimum Investment

Status: Approved product rule; legal framing to confirm.

> **Changed 2026-11-13** (Q03): three creditor regimes (none / 20 / 10+20) replace "strictly below CHF 500,000"; external debts count; a dynamic minimum to the success threshold returns where a limit applies. WW validation pending. Details: "Final Answers Of 2026-11-13".

> Updated 2026-11-16 (round 2: F06-F09): sandbox checkbox per project, off by default; counts per borrower UID; WW notice with explicit confirmation; F07 counting rules; F09 external-debt record with creditor identification. Details: "Round 2 Answers Of 2026-11-16".

Supersedes: MKT-DEC-028 (20 investors per Swiss-borrower loan and the raised "minimum now").

Decision:

- For each **Swiss borrower**, the total of its loans must be **strictly below CHF 500,000**, with no maximum number of lenders in this model. Exactly CHF 500,000 is not eligible. It is not a separate cap per project, and it does not depend on the loan currency or the investor's nationality.
- The places rule and the minimum calculated from the amount to the threshold divided by the places left are removed. The usual minimum of **EUR/CHF 1,000** stays, limited to the amount still available in the project, and the minimum success threshold stays. Reaching the threshold does not mean full funding or immediate closing. The minimum is not a recommendation or a pre-filled amount.
- Admin, checks, displays and resale are adapted. Incompatible Swiss examples are reconciled explicitly, without silent changes.

Before the real implementation: confirm the basis of the total (external loans, repaid principal, undisbursed commitments, assigned claims), the moment of the check, the technical conversion to CHF and the control of simultaneous operations. The control conversion does not switch on FX for investors. Summing Banxum projects alone is not assumed to be enough. The ESTV 46/47 tax reference and FINMA conditions are separate; this rule alone does not prove legal compliance.

### U33-DEC-10: Interest Calculation and Start Date

Status: Approved (final): Actual/365 Fixed.

> **Changed 2026-11-13** (Q07): interest from the payout; base interest stops before the adjusted due date even when unpaid; daily penalty X to the payment day included; previous-business-day rule; fractional cents carried. Details: "Final Answers Of 2026-11-13".

> Updated 2026-11-16 (round 2: F10-F13, F17): due dates from the payout day; per-loan payment order; early payment keeps the final maturity; exited investors keep cent fractions until the final distribution; CHF/EUR calendars. Details: "Round 2 Answers Of 2026-11-16".

Supersedes: the monthly rate (annual rate / 12) of PROD-DEC-008 and the schedule engine.

Decision: interest accrues on actual days, on the outstanding principal, with a fixed denominator of **365**, also in leap years:

`Interest = sum(outstanding principal in the interval x annual rate as a decimal x actual days / 365)`

- Intervals are split when principal or rate changes. Principal due but unpaid is not deducted as if repaid; contractual rules apply.
- First/last broken periods, early repayment and mid-period changes use the same formula. 29 February counts; the basis does not become 366.
- Daily calculation is not daily payment, daily capitalization or equal monthly interest. Frequencies are in U33-DEC-11; annual rate / 12 is not used as a general rule.
- Assignment/resale splits rights at the effective date, with no doubled or missing days; the originator's share is separate (U33-DEC-24). Existing/imported contracts keep their convention; an assignment does not change it retroactively.
- Penalties have separate rules: rate, base, start, beneficiaries, cumulation/replacement and day convention per contract. They are not derived from the Due/Late labels, and interest is not capitalized automatically.

Example, constant principal 10,000 at 12%: **15 days = 49.32; 30 days = 98.63; 31 days = 101.92**. For 366 days the unrounded value is 1,203.287671...; 1,203.29 after one final rounding. Rounding individual installments can need a separate adjustment.

To clarify with Vlad: the contractual start date (not the reservation date), inclusion/exclusion of boundary days, the effective date of a balance change, non-business days, intermediate precision, rounding and allocation/adjustment between investors. Tests cover leap years, broken periods, amortization, early/late repayments and assignments; contracts, projections, schedules, transactions and resale must agree.

### U33-DEC-11: Repayment Types and Frequencies

Status: Approved (extension as designed).

> Updated 2026-11-13 (Q08): four frequencies from the start, equal total installments, custom schedules by import, filter groups confirmed. Details: "Final Answers Of 2026-11-13".

Supersedes: PROD-DEC-005 / SERV-DEC-001 (monthly-only launch types).

Decision:

- Base frequencies: **monthly, quarterly, half-yearly, annual**, each with interest-only and principal at the end, or with principal and interest. Separately: full repayment of principal and interest at the end.
- Custom schedules and initial interest-only phases are allowed; relevant existing structures stay, with no artificial limit to three simplified formulas. Configuration belongs to the admin and the contract, not to the investor, who only filters offers. The interface keeps the grouping **Periodic repayments / Payment at maturity**, with the principal structure and real phases explicit.
- Imports keep the real data and phases; an irregular schedule does not get an invented frequency. Admin, calculator, contracts, calendar, opportunities and Smart Invest follow U33-DEC-10; incompatible monthly formulas are not reused. The editor/import and validations for custom schedules are defined with Vlad. Existing contracts are respected.

## Group 5 - States and Exceptions

### U33-DEC-09: Late, Default and Termination

Status: Approved (mixed variant).

> **Changed 2026-11-13** (C01-C03): Late 15 / Default 60 for all records, demo records included; real contracts with other terms differ case by case. Details: "Final Answers Of 2026-11-13".

> Updated 2026-11-16 (round 2: C01, C03): demo records may keep 5/16; claim purchases blocked at Due. Details: "Round 2 Answers Of 2026-11-16".

Supersedes: SERV-DEC-008 (Late day 5, Default day 16).

Decision:

- Base scenario: **Due** on the due date and during the first 14 days overdue, **Late from day 15**, **Default at 60 days**, with thresholds adaptable to the actual contract. Due does not mean paid or "On schedule"; the real number of overdue days stays correct before Late.
- Default, termination and recovery stages are separate, manageable and visible states/events, with real dates and history. A loan is not terminated automatically just because the label becomes Default. Existing contracts keep their terms; penalties follow the contract, not the visual thresholds.
- Vlad specifies the day boundaries in Europe/Zurich and the link with notifications, reports, resale and U33-DEC-22.

### U33-DEC-22: Late Payment and Recovery Information

Status: Approved (mixed variant).

> Updated 2026-11-13 (Q16, C08): eight standard English stage names, own titles allowed, EN/DE variants. Details: "Final Answers Of 2026-11-13".

Updates: RISK-DEC-003 / RISK-DEC-007.

Decision:

- Vlad's existing data, notes and updates are reused, with the **stage-by-stage presentation** of the design. Extra manual administration per case is accepted.
- The admin records the arrears, recovery amounts/dates, events and real stages, including termination, plus the note for investors. The next step/date shows only when known. The investor sees what was done, the current stage and what really comes next; no fictitious automatic progress or invented universal calendar.
- The history stays accessible on request, and updates are still published, including the existing email to the relevant investors. Messages explain Banxum's actions and do not ask the investor to manage the recovery. Recoveries go to the Banxum balance (U33-DEC-02). Stage names and fields follow the real process, with no promises about a team or procedures that do not exist.

Implemented 2026-11-10 (Phase 17.4): `plan/12_risk_collections_recoveries.md` RISK-DEC-003 note. Stage titles are free text with suggested examples; the list of real stage names is in the open questions of Phase 17.

### U33-DEC-29: Missing States and Screens, Including Company Accounts

Status: Approved as later design work. Not declared done and not visually approved.

> Updated 2026-11-13 (Q23): Vlad builds first versions with maximum care; Vlad chooses the order. Details: "Final Answers Of 2026-11-13".

Decision: the following are prepared later on the existing mechanisms:

| Case | Distinction to keep |
| --- | --- |
| Funding closed, payout to the borrower pending | Separate from Repaying; the interest date follows the contract, not the label. No resale before real eligibility. |
| Funding failed/cancelled | The reservation is released to the Banxum balance, not returned directly to the bank; the holding deadline is checked, and expired funds are not reinvested. |
| Written-off claim | Written off is separate from Default and Repaid and does not mean automatic waiver of rights; later recoveries stay recordable. |
| Restricted/locked/closed account | Reason and remedy that fit the state; access to support/documents as appropriate. Messages before login do not reveal that the account exists. |
| Re-verification in progress | Requirement, stage and any limits follow the U33-DEC-27 process. |
| Security for existing accounts | Migration to password + chosen second factor + PIN, not only PIN setup. |
| Company investor and representative | Team-managed path with verification of the company/representative; no automatic self-service onboarding is implied. |

These are cases/states, not a request for seven new pages. Existing components are reused. The design's `src/create-account.js` already has verification/PIN/company-contact states, and the profile has desktop/mobile verification states; they are completed, not declared missing and not rebuilt by default.

## Group 6 - Resale and Fees

### U33-DEC-06: Resale Price and Premium

Status: Approved (design adjusted on 2026-11-08).
Supersedes: MKT-DEC-007 "par or discount only" (2026-10-16).

Decision:

- The seller sells **the investor's whole position**, without splitting, not the whole loan. The principal price can be **0-102% of the outstanding principal**: discount allowed, premium at most **2%**. Accrued unpaid interest is added separately.
- The slider keeps 0.5 percentage-point steps and the manual amount to the cent, with the real percentage in sync. Discount over 10% -> warning; 20% or more -> stronger warning, with no automatic block. A principal price of zero stays allowed, with no new minimum; the total can include accrued interest.
- Active listings are reconciled explicitly with U33-DEC-06/07; closed trades are not recalculated. The old Help text with 95-105% is corrected.

### U33-DEC-07: Seller Fee

Status: Approved: 2%, with a cap (replaces the old 1% of the design).
Updates: MKT-DEC-017.

Decision:

`Seller fee = min(2% x sale price of the principal, 2% x outstanding principal)`

- **Accrued unpaid interest: "No fees"**, shown next to that component, not only in a tooltip. It is not part of the fee base, and the sale as a whole is not presented as fee-free.
- The buyer pays no fee. The seller fee is charged only when the sale completes. Principal price zero -> fee zero.
- Example: outstanding principal 10,000, principal price 10,200, accrued interest 100 -> the buyer pays 10,300; the capped fee is 200; the seller receives 10,100.
- Fee and net are shown before confirmation. Open listings take the new rule after edit/refresh; these listings and any needed reconfirmation are reconciled explicitly, without recalculating closed trades or silently changing accepted terms.
- Base, cap and interest exclusion are checked even though the current percentage is already 2%. Premium and fee are two separate rules, both 2%.

### U33-DEC-12: Fees and Platform Wording

Status: Approved (own variant).

> **Changed 2026-11-13** (Q24.2): the Help text "0% fees for investors" stays word for word. Recovery-cost clause from lawyers (Q11.2). Details: "Final Answers Of 2026-11-13".

Updates: PAY-DEC-006 (lender payment fee), PROD-DEC-009 / RISK-DEC-005 (recovery fee).

Decision:

- Investing, holding the account and ordinary repayments/administration are free at launch; the configurable fee on repayments stays zero. **No Banxum recovery fee for the investor.**
- Real, documented external costs (lawyer, court, enforcement) are claimed from the borrower under the contract/law. If they are not covered separately, they may be deducted from recovered amounts. Costs already paid are not deducted twice, and internal Banxum costs are not reclassified as external costs. Distribution order and shared costs follow the applicable rights/documents.
- The platform shows the gross recovered amount, the deducted costs and the net distributed to the Banxum balance. No promise of zero costs, and no separate debit of other investor money. A possible Banxum fee owed by the borrower needs its own basis and decision; no new fee is approved here.
- Resale follows U33-DEC-07; the daily penalty is removed (U33-DEC-04); FX is off (U33-DEC-33). No universal "0 fees" wording. A future repayment fee needs a decision and new terms, shown before agreement and reflected in projections, never retroactively. The contractual transposition of recovery stays to be checked, including cross-border.

## Group 7 - Credit File and Contracts

### U33-DEC-13: Acceptance of the Investment and the Assignment Document

Status: Approved (design with the new authentication). Validation open.

> **Changed 2026-11-13** (Q10): the QES is a condition of settlement; chain originator -> Garanta -> investors; resale assignment signed by Garanta for the seller; one managing-director signature; EN/DE templates. Details: "Final Answers Of 2026-11-13".

> Updated 2026-11-16 (round 2: F05, Q10.2): first assignment upload required; authorized deputy signer. Details: "Round 2 Answers Of 2026-11-16".

Supersedes: DOC-DEC-003 (no e-signature) for the post-closing assignment declaration; updates DOC-DEC-005.

Decision:

- The investor reviews, accepts and confirms **with the PIN only**; this **is not a QES**.
- At successful closing, one assignment declaration per investment is issued, signed with a **Swiss QES (ZertES)** by the authorized representative of the assigning entity, and stored in **Documents**, accessible to the investor.
- Banxum is the brand; for the Banxum -> investor assignment the legal entity is **Garanta Finanzgruppe AG**. The document identifies the exact parties and signatories. The accepted version, the operation and the confirmation time are recorded. The signed document must be real and downloadable; it is never shown as "signed" before the signature succeeds.

To validate: the contractual and signature chain (including resale), templates, QES integration, archiving and errors. A Banxum QES is not assumed to replace the consent/signature of the previous assignor, and QES is not introduced for the investor's simple confirmation.

### U33-DEC-14: Documents and Acceptance Checkboxes

Status: Approved (Vlad's platform, adapted).

> Updated 2026-11-13 (Q11): templates reused and adapted to Q09-Q10 in EN/DE; thresholds corrected before the first new loan. Details: "Final Answers Of 2026-11-13".

Confirms: MKT-DEC-015, DOC-DEC-001.

Decision:

- Two clear acceptances, unchecked by default: **investment/assignment terms** and **risks**. Resale uses the seller-specific and buyer-specific agreements.
- Documents open before confirmation, with an identifiable version and later access. Vlad's materials are reused if they cover the rights, terms, costs, risks and required information, including confidentiality where it applies. No redundant checkboxes/PDFs just to copy the prototype, and no removal of required content to get two physical documents. The legal set and names are validated; QES stays separate (U33-DEC-13).

### U33-DEC-20: Credit File Content and Administration

Status: Approved (mixed administration, keeping the full approved depth and presentation).

> Updated 2026-11-13 (C07): ratio formulas confirmed; "n/a" for missing data or a non-positive denominator. Details: "Final Answers Of 2026-11-13".

Updates: DOC-DEC-004 / DOC-DEC-006 and the borrower story model.

Decision: the seven chapters stay: Summary, Borrower & business, Financials, Security, Loan terms, Checks & updates, Documents. Navigation, depth and document access stay; simpler administration does not justify a smaller file.

- **Structured data:** historical P&L and balance sheet, the available years/periods, sub-items, the four approved ratios (calculated) and debts explained from the documents. One source for figures; no invented financial data and no business scenarios/projections to fill gaps.
- **Texts and media through templates:** business explanation, intended use of funds, representative, quote and images when they exist, without a separate field for each sentence.
- **Securities and progress:** the structure of U33-DEC-21, checks/updates with source, date and result, the recovery stages of U33-DEC-22.
- **Library:** real documents with metadata for category, period/date, issuer, version, status and access; references lead to the same document.

Content is factual, with no ratings, opinions on the business or subjective assessments. The 16 demo files and PDFs show the standard; 9-12 PDFs per file is not a quota. In production, demo data, images/quotes and documents are replaced with real material, never presented as originals received from companies.

Implemented 2026-11-10 (Phase 17.4): `plan/13_documents_contracting_esign.md` DOC-DEC-004 / DOC-DEC-006 notes. The four ratios are the design's (equity / total assets, financial debt / equity, operating margin, interest coverage).

### U33-DEC-23: Missing Descriptive Fields

Status: Approved (design).

Decision: the borrower's city and number of employees (with the relevant period) are added; for the originator: founding year, city and sector. The admin manages them and the interface shows them when available. Values are not derived automatically from other texts, a missing value is not shown as zero, and an unknown value does not block publication by default.

### U33-DEC-24: Refinancing and Economic Rights on Originator Claims

Status: Approved (Vlad's mechanism, explained in the design). Clarifications open.

> **Changed 2026-11-13** (Q09): no installment retained by the originator; price = principal at settlement + accrued unpaid interest; rights from settlement. Details: "Final Answers Of 2026-11-13".

> **Changed 2026-11-16** (round 2: F02-F04, C03): price fixed for the planned settlement day (1 business day after the funding end), originator bears delays; offer fails on any payment or due date before settlement; purchases blocked at Due. Details: "Round 2 Answers Of 2026-11-16".

Confirms: PROD-DEC-013, MKT-DEC-022, MKT-DEC-025.

Decision:

- The split of interest and, where the contract provides it, of penalty interest with the originator stays, with **percentages set case by case**, no universal percentage. The rate, projections, schedule and first payment shown to the investor reflect only the investor's rights, not automatically the interest paid by the borrower.
- Loan terms show the actual percentages for the investor and the originator, for interest and, where it applies, penalty interest. The split and its effect on the first receipt are explained briefly before confirmation. Old/new refinancing terms and the base schedule/contract stay accessible in Loan terms; Summary identifies the refinancing factually.

Implemented 2026-11-10 (Phase 17.4), display part: Loan terms show the investor's and the originator's shares of interest and, where recorded, of penalty interest; the review step states the split in one line before confirmation. The first installment is explained only with the existing sentence until the open point below is clarified.

To clarify with Vlad: the first installment assigned to the originator (principal, interest, period, rights and effect on the investment price); no generic loss for the investor is approved. Penalties and their beneficiaries are treated separately, not as projected profit or a recovery fee. For originator claims, the existing mechanism excludes investor interest during funding; the exact contractual start date and the split of rights follow U33-DEC-10.

## Group 8 - Smart Invest, Saved Items and Notifications

### U33-DEC-17: Coming Soon and the Opening Alert

Status: Approved (design).

> Updated 2026-11-13 (Q17, C04): Coming soon also for originator claims; email at the real opening. Details: "Final Answers Of 2026-11-13".

Decision:

- Projects can be visible before opening, with the planned date and an explicit request for an email notification. The admin manages the state and the opening; the alert fires at the real opening, not only when the date passes.
- No investments or reservations before opening, including in the backend. In Smart Invest, Coming soon is separate from available matches, and the open-investment counter does not include it. The opening alert is not duplicated with the Smart Invest alert. The public state stays consistent; opening does not reset the age of money (U33-DEC-03).

Implemented 2026-11-10 (Phase 17.4) for Direct loans: `plan/09_marketplace_investments.md` MKT-DEC-029. Loan Originator claims are an open point. Smart Invest does not list Coming soon matches yet (its matches are open loans only, so the counters already leave Coming soon out).

### U33-DEC-18: Save for Later

Status: Approved (design with automatic alerts).

> **Changed 2026-11-13** (Q18, C05): reminder rules confirmed; saved opportunities first, then Closing soonest. Details: "Final Answers Of 2026-11-13".

Decision:

- The opportunity and, optionally, an explicitly chosen amount are saved in the account, available across devices and from Overview. Saving does not reserve money or places, does not check agreements and does not guarantee later availability. The minimum is not selected silently, and the "Closing soonest" sort is not changed to put saved items first.
- On return the platform checks the project state, the minimum, the project's available amount and the personal balance. An incompatible amount is explained, never changed or confirmed silently; a closed project does not become investable through a saved item.
- Approved alerts: automatic **7, 3 and 1 day** before closing, as in-platform notifications and email, not SMS/push. They are independent of marketing and of the Smart Invest pause.

Proposed details, to define with Vlad (not yet approved decisions): only future milestones after saving, no retroactive alerts; de-duplication per event/channel; stop when the item is removed or the project closes/is cancelled, and reschedule when the date changes; time of day and simultaneous operations.

Implemented 2026-11-10 (Phase 17.4) with the proposed details: `plan/09_marketplace_investments.md` MKT-DEC-030. The time of day is the daily job run; it and the proposed details are in the open questions of Phase 17.

### U33-DEC-19: Smart Invest

Status: Approved (final, mixed variant).

> Updated 2026-11-13 (Q14.2): one-click "Stop these alerts" link in Smart Invest emails. Details: "Final Answers Of 2026-11-13".

Supersedes: MKT-DEC-027 (batch placement); updates MKT-DEC-026 and COMMS-DEC-008.

Decision:

- **Individual confirmation only** for each investment, with the PIN; no batch approval, no discretionary buying, no reservation and no auto-checked agreement.
- The existing matching mechanism and one set of preferences are reused. Criteria: currency, minimum interest, maximum term, several security types, maximum LTV, repayment, country and originator. No ratings and no new purpose/refinancing filters. Setup/editing follows the five approved steps; when editing, the existing preferences are pre-filled and saved at the end. EUR/CHF and "No preference" stay, with coherent selections and no contradictions.
- The usual amount is optional and chosen explicitly. If it is missing, the minimum is not pre-filled. If it exists, it can prepare the amount; it is never raised silently. The usual amount and the balance do not exclude opportunities from matching; the impossibility of investing that amount is explained separately.
- **Pause:** keeps the preferences, stops Smart Invest alerts and removes the marks, counters and recommendations from Overview, Opportunities and the Smart Invest page. Opportunities stay accessible manually; history is not deleted. **Resume:** recalculates the current matches. Coming soon, saved items and notification channels follow U33-DEC-17, U33-DEC-18 and U33-DEC-30.

### U33-DEC-30: Notification Preferences

Status: Approved (Vlad's platform, adapted).

> Updated 2026-11-13 (Q14): classification approved; stop links per alert; News from Banxum and the public newsletter are one preference. Details: "Final Answers Of 2026-11-13".

Updates: COMMS-DEC-002, COMMS-DEC-003, COMMS-DEC-008.

Decision:

- Service emails stay on: confirmations, repayments, documents, arrears/recoveries, returns and security. Controls that promise to switch them off individually are removed. No generic mandatory email for every new opportunity.
- Marketing is optional and unchecked at sign-up; the existing control is **Profile & Settings -> Notifications -> News from Banxum**. Marketing is separate from operational alerts and from the opportunity options the investor asked for. The legal classification and unsubscribe procedure are checked; not every message is assumed to be legally mandatory.
- Smart Invest has separate **in-platform / email** controls with real effects per channel, not a copy of one setting. Switching off a channel does not stop matching or service messages; Pause stops Smart Invest alerts on both channels. Financial/service history stays accessible; closing a banner does not delete the event.
- Syncing the marketing control and the email unsubscribe into one preference, and the alternative label "Marketing emails", are detail proposals, not approved renames.

## Group 9 - Localization

### U33-DEC-31: Languages of the Interface, Messages and Documents

Status: Approved (design).

> **Changed 2026-11-13** (Q19, Q10.6, C10): contract documents of the flow in EN and DE from launch; all communications in the account language; public DE/FR from the design translations. Details: "Final Answers Of 2026-11-13".

> **Changed 2026-11-16** (round 2): English first; all translations in a final phase before launch. Details: "Round 2 Answers Of 2026-11-16".

Supersedes: DOC-DEC-002 for the interface and emails (contracts may stay English at first).

Decision: investor platform **EN / Swiss Standard German (de-CH)**; public site **EN / DE / FR**. Desktop/mobile and Light/Dark. English by default on the first visit; the choice is saved in the account. Changing the language keeps the page, the state and the entered data.

- All pages and secondary states, validations, errors, notifications, confirmations and backend emails are translated, including those not in the prototype. German uses "Sie", no "ß", a simple, formal and welcoming tone, consistent across devices.
- Admin-managed content has reviewed language variants: EN/de-CH in the platform and EN/DE/FR where it is public. Figures have one source; a missing translation is flagged in the available language, with no invented content.
- Source documents stay in their original language, clearly marked. Contracts can stay in English at first, announced before acceptance; a German legal translation needs a separate review. Signed PDFs are never machine-translated, and no prevailing legal language is assumed. The English demo PDFs are not real contracts.
- Continuity from the public DE site into the DE platform. From the public FR site the investor chooses EN/DE, with no claim of a French platform. The interface language does not promise human support in the same language.

Implemented 2026-11-10 (Phase 17.8, investor interface): `User.language` (`en` by default, `de-CH`) saved with `PATCH /api/v1/auth/preferences/display/` (audit `account.language_changed`) and shown in `/auth/me/`. The investor area (sign-in, registration, portal) switches between English and Deutsch from Preferences, the account menu and the sign-in header; the page, its state and the entered data stay. English is the default on the first visit; a choice made before sign-in, or `?lang=de|en` from the public site, is kept in the browser and saved in the account after sign-in; afterwards the account's language applies on every device. German texts: the design's approved dictionary (about 830 texts) plus drafted texts for everything else in the investor area (about 1,280, "Sie", no "ß"), loaded as a separate file; dates follow the language ("4. Okt. 2026"); a test checks that every investor-area text has a German entry. The number format stays independent of the language (U33-DEC-32). Waiting for answers (last slice of Phase 17): native review of the drafted German texts, backend emails, notifications and server messages in German, the public site in DE/FR, and language variants of admin-managed content. The public site and the admin console stay English until then.

### U33-DEC-32: Number Format and Time Zone

Status: Approved (mixed variant).

> Updated 2026-11-13 (C09): the number format applies to all newly generated personal reports. Details: "Final Answers Of 2026-11-13".

Decision:

- **European `1.234,56` by default; Swiss `1'234.56` as an alternative**, independent of language, with a saved preference. It applies to amounts/percentages in the interface, data entry, notifications/emails and newly generated personal reports. Source documents, signed contracts and documents already issued are not rewritten.
- Input recognizes unambiguous forms; ambiguous values follow the displayed/selected convention or ask for clarification, never guessing the amount. Formatting never changes values or calculations. The same value is checked up to confirmation in both formats, languages and devices.
- One time reference, **Europe/Zurich**, with automatic summer/winter time, not a fixed UTC+1/CET and no personal time-zone selector. Contractual due dates never move by a day by accident. The time zone is mentioned when a cut-off time matters, not next to every date.

Implemented 2026-11-10 (Phase 17.8): `User.number_format` (`european` by default, `swiss`), `PATCH /api/v1/auth/preferences/display/` (audit `account.number_format_changed`), shown in `/auth/me/`. The portal applies the account's choice on sign-in and saves a new choice in the account. Emails and the notification centre convert the canonical amounts ("CHF 1'234.50") and percentages ("7.40%") of each message to the recipient's format when shown (`localize_number_text`); a new account statement of one investor is written in that investor's format (`number_format_context`). Stored messages and issued documents are not rewritten. Dates and times stay Europe/Zurich.

## Group 10 - Public Area, Identity, Texts and Resources

### U33-DEC-34: Brand and Operator Identity

Status: Approved (mixed variant).
Confirms: the BANXUM/Garanta naming rule in `plan/00_index.md` and `plan/01_operating_model_compliance.md`.

Decision:

- The interface uses **Banxum**. A discreet and accessible identification: **"Banxum is a brand of Garanta Finanzgruppe AG"**, with the official address, UID and other official data in the legal area/footer; "Bern, Switzerland" alone is not a complete identification.
- Contracts, signatures and the beneficiary of transfers use the exact legal entity. About/Legal keep company facts, without deriving a banking status, affiliation, licence or guarantee from the brand. Final official data are checked; the operator is not hidden only inside personal contracts.

### U33-DEC-35: Service Promises

Status: Principle approved; operational confirmations needed.

> Updated 2026-11-13 (Q20): withdrawal 1-3 business days, repayments within 2 business days, support hours, complaint times; public only after capacity is confirmed. Details: "Final Answers Of 2026-11-13".

Decision: texts describe the real service, not the prototype's promises at any cost. Bank payments are operated by hand by the team; deadlines are confirmed against that process.

| Area | Requirement / open confirmation |
| --- | --- |
| Withdrawals | Preference for **1-3 business days**, only after confirmation of operational capacity. Processing is separate from bank crediting. **No Banxum fee.** |
| Repayments | Go to the Banxum balance after receipt/reconciliation (U33-DEC-02). The real time is confirmed; "next business day" is not assumed. |
| Help | Form sent by email, with no new ticket system. Real confirmation of receipt, error/retry state, and page/project context without unnecessary sensitive data. No simulated sending. |
| Support | Hours, languages and owner to confirm; Europe/Zurich with summer time. No "shortly" or unassured deadline; receipt confirmation is separate from resolution. |
| Valuations/experts | Identify the author and the real document. No automatic claim that Banxum orders all valuations, that all are independent or externally checked. Use factual names such as "Valuation report". |

### U33-DEC-36: Contact Addresses

Status: Organization approved; actual addresses deferred.

> Updated 2026-11-13 (Q21): main domain + `app` subdomain; roles support / partnerships / notifications; replies to monitored addresses. Details: "Final Answers Of 2026-11-13".

Decision: few coherent channels for investors/support and partnerships. The domain and exact addresses are decided after they are created; the example addresses discussed earlier are not final. Interface, form recipients, senders and email replies are aligned.

### U33-DEC-37: Fonts, Icons and Demo Material

Status: Template purchased; licences to check.

> Updated 2026-11-13 (Q22): Vlad clarifies the licence with Eduard's father; buy if not expensive. Details: "Final Answers Of 2026-11-13".

Decision: check the proof of purchase, the licence and the resources actually included: fonts (including Archivo), Nioicon/other icons, images and portraits. It is assumed neither that all are licensed nor that all must be replaced. Material with sufficient rights is kept. Where rights are not confirmed or do not cover the real use/distribution, close visual alternatives with clear rights are chosen, keeping the approved identity. Demo images/quotes/documents do not automatically become production material; the origin and permissions of real ones are checked separately.

### U33-DEC-39: Public Functions That Already Exist in the Platform

Status: Preference for the current public area of the design; individual analysis deferred.

> **Changed 2026-11-13** (Q24): pages kept/merged; first-year article removed; privacy and cookie texts drafted by Vlad. Details: "Final Answers Of 2026-11-13".

Decision:

- To evaluate later: **Projects/project history, Statistics, How it works, Help/FAQ, Guides, legal pages, newsletter and cookies**. For each, keep, integrate elsewhere or retire; neither removing all nor keeping all of the initial recommendations is approved.
- U33 public shows three projects and access to opportunities, without Vlad's full public catalogue/history. How it works and FAQ are integrated in Home; some legal texts are still demo. Without the catalogue/statistics there is less public visibility of the history; this implication is recorded for the decision, with no pages added automatically.
- Unique content is inventoried before anything is retired. Keeping the public design does not exempt texts from U33-DEC-02, U33-DEC-15 and U33-DEC-34/35. Real legal documents and cookie handling (based on the technologies actually used) are finalized separately; placeholders are never reused as if valid. Extra design is created after the individual choices, not in this round.

## Design To Complete After Reconciliation

Later work, with no implied visual approval. Approved components are reused, covering desktop/mobile, languages and Light/Dark.

| Area | Items | Work |
| --- | --- | --- |
| Access and profile | 1, 25-28 | Authentication/recovery, sessions, verified data, declarations, closure by request |
| Money and accounts | 2-5, 8 | Destination of receipts, returns, IBANs, removal of the old places/dynamic minimum |
| States and recovery | 9, 22, 29 | The seven cases of item 29 and the real recovery stages |
| Resale and costs | 6-7, 12 | Percentage, breakdown, "No fees" on interest, Help correction |
| Contracts and files | 13-14, 20-24 | Separate PIN/QES, acceptances, originator rights, data/securities; mixed administration does not reduce the credit file design |
| Opportunities and alerts | 15-19, 30, 38 | Optional participation, eligibility, Coming soon/Save/Smart Invest states and real notification controls |
| Localization and identity | 31-32, 34-37 | Shared texts/formats, operator, promises, contacts and resources with confirmed rights |
| Extra public pages | 39 | Only after the individual decision for the eight items |

## Clarifications For Implementation

Still to clarify, without changing the approved choices:

| Items | Clarification / owner |
| --- | --- |
| 1, 25-28 | Vlad and the responsible team: recovery/migration, revocations, history retention, declarations and the re-verification calendar |
| 3-5 | Vlad/operations: deadline counting, non-business days, failed return, holder verification and unidentified deposits |
| 8, 21, 38 | Legal/operations + Vlad: basis of the Swiss total, classification and proof of securities, eligibility controls |
| 10-11 | Vlad + contract documents: boundary dates, effective balances, rounding/allocation, separate penalties, custom schedules |
| 6-7, 12-14, 24 | Vlad/legal: active resale listings, external costs, assignment/QES and agreements, first installment/originator rights |
| 17-18, 30 | Vlad/operations: alert events and de-duplication, the details still proposed, preferences and unsubscribe implementation |
| 31-32, 35-37 | Team + Vlad: content/legal translations, format coverage, real deadlines, contacts and licences |
| 29, 39 | Eduard + design: the missing screens and the individual choices on public functions |

## Final Answers Of 2026-11-13

Source: "Banxum - răspunsuri finale pentru implementarea U33", edition of 13 Nov 2026, revision 1 (Romanian original; issuer Eduard for the Banxum product decisions; addressee Vlad). It answers the questionnaire of 10 Nov 2026 (`Q01`-`Q27`, `C01`-`C10`, `A01`-`A04`). The questionnaire IDs are kept below.

How to read this section:

- These answers replace the text above **where they say so**. Elsewhere the decisions above stay.
- **Approved** = a product decision to implement. **To validate** = a technical, legal, bank or operational condition that is still open. "WW" is the external Swiss legal/tax validation named by the owner. An approved rule is not used with real money before its validation.
- Items "for Vlad" are delegated to the implementation (Vlad decides and confirms).
- There is no real money, no real loan and no real investor on the platform yet. Transition rules apply only to real pre-existing contracts that are imported later; those keep their own contract terms.
- A difficulty found in implementation is reported before an approved rule is changed.

### Rules That Changed (signalled)

| Item | Rule before | Rule now |
| --- | --- | --- |
| C01 (DEC-09) | Contracts that existed before U33-DEC-09 keep Late day 5 / Default day 16 (migration `loans` 0025, audit G-01, 2026-11-10). | **Changed:** every record, demo records included, uses Late from day 15 and Default from day 60. Only a real contract with other terms differs, case by case. |
| Q03 (DEC-08) | Total per Swiss borrower strictly below CHF 500,000; no lender limit; places rule and dynamic minimum removed. | **Changed:** three regimes with creditor limits (none / 20 per borrower / 10 per financing + 20 per borrower); CHF 500,000 and more is allowed in the 10/20 regime; debts outside Banxum count; a dynamic minimum based on the success threshold applies where a creditor limit applies. |
| Q07 (DEC-10) | Open details. | **Changed / new:** base interest on matured principal stops before the adjusted due date even when unpaid; a daily penalty rate X applies to every overdue amount from the next day to the payment day included, never on X; due dates on non-business days move to the previous business day; fractional cents are carried per investor and the last cents go by largest remainder at final settlement. |
| Q09 (DEC-24) | The first installment after the funding deadline belongs entirely to the originator; investors buy the principal after it, at par. | **Changed:** no retained installment. The investor pays the principal at the settlement of the assignment plus the accrued unpaid interest of the rights bought; the rights transfer at settlement; the originator keeps its contractual interest share. |
| Q10 (DEC-13) | One signed assignment document per investment after closing. | **Changed / extended:** the QES signature is a condition of the assignment. No transfer is settled before the signature. Originator claims use two assignments: originator -> Garanta -> investors. A resale is documented by a signed assignment, signed for the seller by Garanta as representative (mandate to validate). One signature: the Garanta managing director, personal QES, batch signing allowed. |
| Q10.6, Q19 (DEC-31) | Contracts may stay in English at first. | **Changed:** the assignment templates and the contract documents of the flow exist in English and German from launch. All communications follow the account language. |
| Q24.2 (DEC-12) | No universal "0 fees" wording. | **Changed for one text:** the Help text "0% fees for investors" stays word for word (owner choice). The economic rules stay. |
| Q24.2 (DEC-39) | The "Our first year in figures" article is kept word for word (2026-10-15). | **Changed:** the article is removed from the public launch version; the source is archived. |
| Q24.4, A04 (DEC-39) | Lawyers deliver the privacy and cookie texts. | **Changed:** Vlad drafts both texts from existing references (Swiss examples), adapted to the real application, in EN/DE/FR. The other legal documents keep their legal validation. |
| C05 (DEC-18) | Saved items do not change the "Closing soonest" order. | **Changed:** saved opportunities come first, visually marked; "Closing soonest" orders each group. |
| C06 (DEC-21) | The first security gives the summary and the loan-to-value. | **Changed:** the admin chooses the main security explicitly; the loan-to-value uses the sum of the values of the distinct relevant assets. |

### Group 1 - Access, Security and Profile

**U33-DEC-01 (Q05).**

- Password: at least 12 and at most 128 characters; very common passwords are refused; no forced change at fixed intervals. Composition rules (upper case, digits, symbols) are required in some form; Vlad sets the exact set. The rule "no composition rules" is not approved.
- SMS provider: Twilio preferred, subject to Vlad's confirmation. Account and contract in the name of Garanta Finanzgruppe AG, which pays. SMS must work in Switzerland, the EU and the rest of the EEA.
- Trusted device: optional, for 30 days, after a sign-in with both factors. On that device the second factor is not asked at sign-in during the 30 days; the password is still asked; PIN confirmations stay. It is separate from the new-device cookie `banxum_device`.
- Recovery codes: 10 single-use codes at enrolment. A code replaces the second factor, not the password. Assisted recovery stays for a lost factor with no code left.
- Migration: existing accounts use the email link one last time, then must set a password and enrol a second factor before normal access. The PIN stays. Asking for the existing PIN to authorize the migration is a recommendation; Vlad confirms the protection of the migration. New accounts use the new sign-in directly.
- Assisted recovery (lost factor and no recovery code): support takes the case; an authorized security/compliance person approves; a new Didit check compared with the existing identity; notice and 24 hours of waiting after verification/approval; a record of the request, check, approval and access changes; the old factor and the sessions are invalidated; the new factor is enrolled and verified under control. The 24 hours do not apply to a forgotten password or PIN when the factor is available. **Vlad must validate this procedure and its security measures before implementation** and report adjustments.
- Admins: password + authenticator app, no SMS.
- Security review: Vlad chooses an internal review or an external provider before launch.

**U33-DEC-25 (Q06).** Approximate city and country from an IP-range database kept on the Banxum server (for example MaxMind GeoLite2); no IP goes to an outside service. Shown as approximate; the country when the city is unknown. The IP stays stored only as a keyed hash. History kept 365 days; the last 50 sign-ins are shown (a display limit). The privacy text states the purpose and the retention.

**U33-DEC-27 (Q12).**

- Declarations in registration and profile: beneficial owner (Yes/No, name if No, opens a review); source of funds (several allowed: salary, savings with their origin, sale of property, inheritance, business income, dividends, investment income, rent, other with explanation); PEP status of the investor, a close family member or close associate (Yes / No / Not sure; Yes asks for person, relation, function and country); expected yearly volume (four bands: under 10,000; 10,000-50,000; 50,000-250,000; over 250,000; final bands without overlap; compliance sets the currency, CHF/EUR treatment and reinvestment).
- A review is opened by: PEP Yes or Not sure, beneficial owner is another person, source "Other", volume over 250,000, and other cases compliance defines. A review is an analysis, not a refusal.
- While a necessary review is open: no new investment, reservation or resale purchase. Account, documents and existing investments stay accessible.
- Owner: the Garanta compliance role with a deputy; support may collect documents. Target: first analysis of a complete file in 3 business days (operational proposal, not a promise).
- Re-verification: a date per investor set by compliance from the internal compliance risk (not a loan rating); notices 30 and 7 days before; after the date the investor cannot invest but can withdraw when the delay is the only problem. No automatic yearly re-verification.
- Existing accounts: asked at the next sign-in; mandatory before the next investment; compliance sets an update deadline for active accounts.
- Company investors: the same structure with company data (company, representative and authority, controlling persons, beneficial owners of the funds, source of funds, PEP of relevant persons, yearly volume). Compliance sets the documents.
- To validate (compliance): texts, forms, bands, currency, company set, intervals.

### Group 2 - Money and Bank Accounts

**U33-DEC-03 (Q01).**

- The value date of each lot is day 0; calendar days.
- Day 56 is the last day (withdraw only). The return request is created on day 57 to the default return account; the team makes the transfer by hand. Days 57-59 are the intended margin before day 60.
- If the return day is not a settlement day of the relevant Swiss interbank system, the return moves to the **previous** settlement day. Operations keep the yearly calendar in the admin and confirm it for the CHF/EUR transfers and the bank used. The request and the blocking of the amount are prepared early enough; the date shown to the investor includes the adjustment.
- Requirement (2026-11-11): the effective **debit of the Garanta account** happens within the 60 days. It is proven by the bank's debit confirmation, not by the request or the payment order. Day 57 is the normal start; it moves earlier when the calendar, cut-off times or the bank's processing time need it. To confirm before launch: the bank's processing time and cut-offs, and which bank event proves settlement (legal reading of BankV art. 5 para. 3 let. c and FINMA circular 2008/3 no. 16).
- Notices 14, 10 and 3 days before the scheduled (adjusted) return date; a confirmation when the request is created; a second confirmation after the team made the transfer (not a claim that the beneficiary bank credited it). The old reminders on days 25/46/53/56/57/58 stop. Urgent notices for a missing usable account stay separate.
- Transition: lots with a value date on or after the change follow 56 days; older lots, if any, keep 58 days and their announced dates.

**U33-DEC-04 (Q02).**

- New state "Return failed". The amount the bank sends back returns to the balance as "due back" (withdraw/return only), with its original age; no new 56/60-day period; no penalty. The request state and the reconciliation of the returned amount stay separate, so the balance is never credited twice.
- The cause shown follows the bank's answer; a technical error or a bank restriction is not blamed on the investor.
- Email and in-app notice at once; an admin task with the bank's reason; the team contacts the investor and follows the case. Support and documents stay accessible.
- No automatic retry. The team sends again, as fast as possible, after the account is corrected or a new account is verified; never again to the same invalid data.
- Urgent notices every day while unresolved (saying the real action needed). Compliance takes the case after 5 calendar days at the latest, and **at once** when the 60-day limit is threatened or passed (the age of the money is tracked, not only the age of the task).
- To validate before launch (Swiss lawyer and bank): the exception procedure when a return is impossible, and how settlement is proven after a rejected transfer. Keeping money after day 60 is not allowed only because the problem comes from the investor. Court deposit ("Hinterlegung", CO art. 91-92, 96) is an option to analyse, not an approved procedure.

**U33-DEC-05 (Q02.5).** Returns go only to a verified account of the investor. The team can verify the account that sent the deposit from the bank's data (holder and IBAN against the verified identity), keeping the proof, when the proof is sufficient; no automatic micro-transfer or extra statement. If the holder is unclear, the data differ or the transfer came through a collecting/intermediary account, the team asks for a statement or bank confirmation first. This does not allow sending to any IBAN that once sent money.

**U33-DEC-33 (Q25).** The old currency exchange screen is removed from the investor area; the function code can stay. Vlad checks shared style files before removing them.

### Group 3 - Product and Security

**U33-DEC-15 (Q04).** Garanta Finanzgruppe AG invests its own money through an ordinary investor account, with the same flow and controls; the interface says "Banxum". The decision is taken before publication or just after. The label **"Banxum invests"** (design component, position and style) shows as soon as a confirmed reservation exists, **without amount or percentage**; no new "Reserved/Invested" indicator. After closing the label stays for a real participation; a cancelled participation removes it. Same interest, rank and calendar as the other investors, pro-rata receipts, no priority, no obligation to cover losses. The participation counts in the Q03 creditor counts. Contract wording to validate with WW.

**U33-DEC-21 (Q15, C06).**

- Vehicles: a security type from the start (Vlad confirms the effort; a significant effort is reported for discussion, not assumed).
- Invoices: closed for new securities; use "Receivables" for the pledged claim and attach the invoice as a document.
- New records: each security separate with its concrete type; "Mixed collateral" and "asset backed" not available for new securities; "Other" needs a description; real verified data only. No migration project is needed (no real loans).
- Loan-to-value: the admin chooses the main security for the summary. `LTV = loan amount / sum of the values of the distinct assets included x 100`. The same asset never counts twice; a guarantor's wealth is never added; personal/corporate guarantees without an adequate valued basis do not produce an LTV. The investor sees the assets included, their values and valuation dates. Prior-ranking debt and the cumulative ratio are shown separately and labelled. A released security is recorded as "released" and leaves the summary and the calculation.

**U33-DEC-38 (Q13).** Publication of a new loan is blocked until each security has **all** the documents its type and situation need (the questionnaire's list per type is the working base; legal validates it per type and jurisdiction) and an authorized person records the verification with name and date. A change of an essential document, guarantor, asset or scope needs a new verification, with history. The right to verify is a specific role (credit and security analysis, with a deputy), not general admin access. A file present is not a legal verification.

### Group 4 - Minimum, Interest and Repayment

**U33-DEC-08 (Q03).** Approved 2026-11-11; WW validation pending; no real use of a regime before WW validation. Premise: no public solicitation.

- `T` = total in CHF per Swiss borrower (same UID): the **original amount** of each loan still active (also after partial repayments; fully repaid loans excluded); the whole published amount of projects in funding (one reservation of capacity, replaced by the active loan at funding, released only for the part not granted); originator claims on the borrower (the underlying loan counted once); active debts outside Banxum (banks and other platforms), from a verified borrower declaration. The outstanding-principal basis may be used case by case with a documented legal justification, never automatically.

| Total and regime | Creditor limit |
| --- | --- |
| T < CHF 500,000, sandbox applicable (approved working assumption) | No numerical limit. |
| T < CHF 500,000, sandbox not applicable (safety alternative) | At most 20 relevant creditors in total per borrower. |
| T >= CHF 500,000 (exactly 500,000 included) | At most 10 non-bank creditors for the same financing on identical terms, and at most 20 in total per borrower. |

- No new money cap in these regimes; the CHF 1 million limit belongs to the sandbox regime. A borrower that already has more than 20 relevant creditors cannot enter the 10/20 regime. The same financing is never split into projects to avoid the limit of 10.
- Check at publication with the whole new amount; again before closing and at relevant changes. Simultaneous operations are controlled per borrower UID in every path (direct investment, originator claims, resale).
- UID mandatory for Swiss borrowers (direct loans and originator claims).
- EUR -> CHF at the SNB reference rate of the day of the check (the last official rate when there is no new one; source and date kept). No FX for investors.
- Borrower declaration verified before publication and before closing; a contractual duty to notify new financing.
- Dynamic minimum where a creditor limit applies, for a participation that takes a new place: `minimum = min(R, max(1,000, round up to the currency unit of max(0, P - F) / N))` for `N > 0` and `R > 0`. `P` = minimum success threshold of the offer; `F` = amount validly allocated (confirmed reservations included); `R` = amount still available to the full target; `N` = places really available under all limits. An investor already in the same offer adds with the usual minimum, capped at `R`. After the threshold, or with no creditor limit, the usual minimum EUR/CHF 1,000 capped at `R`. No places left -> no new creditor. The minimum is checked again before confirmation and never raises a chosen amount silently. Resale stays a whole-position sale; creditor limits are checked, no fund-raising minimum.
- The old 20-investor rule is replaced at once (no real loans to migrate).
- To validate (WW): sandbox applicability and conditions (prior individual information, no interest-margin business), the total and creditor definitions, assignments, regime changes. Vlad/operations: SNB source, verified external debts, simultaneous controls, threshold monitoring.

**U33-DEC-10 (Q07).** Final 2026-11-12. Actual/365 Fixed: `outstanding principal x annual rate x actual days / 365` per interval of constant principal and rate, leap years included.

- New direct loans: interest starts on the value date of the payout to the borrower.
- Base interest: intervals include the start and exclude the end. For each principal component the end is its adjusted due date, or the receipt date that repays it early if earlier. No base interest on the due date or after on matured principal, even when unpaid. Principal not yet due keeps base interest. 1 Jan - 1 Feb = 31 days ("1-31 January", paid 1 February). Each day and each right counts once, also at assignment.
- Penalty X: for an amount unpaid at the adjusted due date, from the next calendar day to the receipt day **included**, weekends and holidays included; zero for an amount paid at or before the due date. `X amount = overdue base x X / 100 x calendar days` (X is a daily % rate set by the contract, not divided by 365); split by interval when base or rate changes. X applies to every overdue amount: principal, base interest and other contractual money obligations. Never X on X or on penalties; no capitalization; components recorded separately. The whole remaining principal is in the X base only if it became due under the contract (a Default label alone does not do this). Admin records rate, eligible components, start, day convention and beneficiaries (investors, originator, Banxum/legal entity).
- Early repayment: base interest on the repaid principal stops from the receipt value date (the receipt day is excluded). This also applies to principal paid on the adjusted due date; the old exception that kept interest to the original date ends.
- Non-business due date: the due date moves to the nearest **previous** business day of the currency's calendar; the interest period adapts; the first late day is the next calendar day. The original date and the adjusted date are both kept.
- Payment = effective receipt on the account at the relevant value date.
- Cents: precision kept; investors receive whole cents at each distribution and the fraction is carried to the next one; at final settlement the remaining cents of the distributable amount go by largest remainder with full reconciliation. Remainders are kept per investor, loan and currency; not passed to a resale buyer; an investor's exit is regularized without deleting fractions. Never more than the distributable amount. Vlad validates precision, reconciliation and ties.
- No real portfolio to migrate; imported pre-existing claims keep their source contract convention, never recalculated retroactively.
- To validate (WW): the complete clause (base interest stop when unpaid, X from the next day to the payment day included, the rate, the components; CO art. 102, 104-105). Until then the mechanism is an implementation requirement, not an obligation applied to borrowers.

**U33-DEC-11 (Q08).** All four frequencies (monthly, quarterly, half-yearly, annual) from the start, each with periodic interest and principal at the end, or periodic principal and interest; separately full payment of principal and interest at the end; initial interest-only phases and the relevant approved structures stay.

- Principal and interest: the **total installment stays equal**; interest on actual days and outstanding principal; principal = installment - interest; the last installment settles the difference. No "equal principal" type is added as a second standard type by this answer. No return to equal monthly interest or rate / 12.
- Custom schedules from the start through an import (one row per installment: due date and principal; the platform computes the interest), unless Vlad shows a significant effort; then only the custom schedules may be deferred. Checks: increasing dates; first due date after the interest start; principal total = loan amount; zero principal allowed (interest-only), never negative; remaining principal never negative; full calculated schedule and errors shown before confirmation; original and adjusted dates kept. Imported originator schedules stay.
- Filter groups: "Periodic repayments" (any frequency, interest-only or principal and interest) and "Payment at maturity" (all principal and all interest at the end). The offer shows frequency, principal structure and phases; irregular schedules keep the real calendar.

### Group 5 - States and Exceptions

**U33-DEC-09 (C01-C03).** Standard Late from day 15 and Default from day 60 for all records (see "Rules That Changed"). The due date is day 0; for new direct loans it is the adjusted due date (Q07); the next calendar day is late day 1; Due on days 0-14. Changes of the thresholds apply at the next daily check. Originator offers close at the loan's own Late threshold (standard day 15); the purchase is blocked when the threshold is reached, also between periodic checks.

**U33-DEC-22 (Q16, C08).** Standard English stage names: Reminder sent; Formal notice; Enforcement of the security; Debt collection proceedings; Claim filed in insolvency; Sale of the security; Recovery closed; Loan agreement terminated. The admin picks a standard name or types an own title; English and German variants (German names to be set later by the team); the investor note stays free text. Only real actions with dates; termination separate from Default; enforcement separate from sale; "Recovery closed" states the result (full, partial or no recovery); the next step only when known. Recording a stage sends no email; the admin can send a note separately.

**U33-DEC-29 (Q23).** Vlad builds first versions of the seven cases with the existing U33 components, with **maximum care**: coherent with the approved visual language, as beautiful as possible, finished already at the first review; desktop/mobile, EN/de-CH, Light/Dark; behaviour checked, not only looks. Vlad chooses the order.

### Group 6 - Resale and Fees

**U33-DEC-12 (Q11.2, Q24.2).** No Banxum recovery fee. Real documented external costs are claimed from the borrower; if not covered they may be deducted from recoveries under the applicable conditions and order; never twice; internal costs are not external. The investor sees gross, deducted costs and net. Lawyers provide the clause (eligible costs, proof, order, shared costs, cross-border). The Help text "0% fees for investors" stays (see "Rules That Changed").

### Group 7 - Credit File and Contracts

**U33-DEC-13 (Q10).**

- Provider not chosen; Vlad states technical preferences. Swiss QES (ZertES) with qualified time stamp.
- One signature for Garanta: the managing director (person to be named). To verify: the commercial-register signing authority allows a single signature; if not, report before implementation.
- Personal QES, not the company seal. Batch signing allowed; each investment keeps its own declaration and verifiable signature; the investor's PIN confirmation stays.
- Originator claims: first assignment originator -> Garanta (signatory and form validated separately; Garanta's QES does not replace it); second assignment Garanta -> investors by the normal procedure. No extra margin or own-funds financing between the steps is assumed.
- Resale: each resale documented by a signed assignment; seller and buyer keep their PIN confirmations; Garanta signs for the seller as authorized representative with its own QES (Swiss law allows representation, CO 32-33, 165, 14 para. 2bis). To validate (WW): governing law, mandate clause and form, limits, representation of both parties, revocation (CO 34). The PIN is not declared a sufficient mandate without legal check.
- Templates in English and German from launch, legally validated.
- Archive: PDF/A prepared before signing; the signed original and the verification data kept. Retention period and start to set legally.
- The signature is necessary for the assignment. On error: agreement and operation/reservation state kept; document "in preparation"; retries; team alert; escalation after 24 hours; never "signed" before success; the assignment is not declared done and not settled before the signature.

**U33-DEC-14 (Q11.1, Q11.3, A01).** Two unchecked acceptances (investment/assignment terms; risks) and the resale agreements stay; two acceptances do not mean exactly two PDFs. Existing templates are reused with legal review and adapted to Q09-Q10 (chain, accrued interest, transfer at settlement, QES, resale representation), in EN and DE. The terms use Due (days 0-14), Late from day 15, Default from day 60 or the contract's days, the Q07 interest and penalty rules; they are corrected and validated before the first new loan (A01). The questionnaire default (current templates unchanged) is not accepted for launch.

**U33-DEC-20 (C07).** Ratios: equity ratio = equity / total assets x 100 (%); financial debt / equity (multiple); operating margin = operating profit / revenue x 100 (%); interest coverage = operating profit / absolute interest expense (multiple). Figures in thousands with currency and unit; units aligned before division; missing data or a non-positive denominator shows "n/a", never an invented zero. The admin sets the reporting plan per loan; the design's standard plan is the start and stays "proposed" until agreed.

**U33-DEC-24 (Q09).** Final 2026-11-11 at product level.

- The investor buys the principal of the participation at the settlement of the assignment plus the accrued unpaid interest of the transferred rights; the investor receives the rights bought, including the next payment. A reservation or the funding close alone transfers nothing.
- No installment is retained by the originator; a shorter or longer first period does not justify it.
- The originator's contractual share of interest (and of penalty interest where the contract says so) stays per loan; the accrued interest in the price covers only the transferred share.
- `Total to pay = principal bought at settlement + accrued unpaid interest of the transferred rights`. Example: principal 10,000 + accrued 40 = 10,040; next payment 500 principal + 100 interest -> 600 to the investor; 40 recovers the bought interest, 60 is interest earned after the transfer. The resale analogy does not extend resale fees or premium/discount limits to originator sales.
- Before confirmation the investor sees: principal bought, accrued interest in the price, total, the receipts of the investor's rights (first estimated payment), and the actual percentages of investor and originator. The old message "the first installment belongs to the originator" is not used. Bought interest is never shown as new earnings.
- Direct loans: no retained first installment; interest from the payout value date.
- For Vlad to confirm: the event and date that prove settlement (with the payment to the originator), the accrued interest to settlement and the difference between reservation and payment (never a silent extra debit), reconciliation, arrears and penalties per transferred rights.

### Group 8 - Smart Invest, Saved Items and Notifications

**U33-DEC-17 (Q17, C04).** Coming soon also for originator claims, from the start (Vlad confirms the effort). The opening email is sent when the admin's publication really opens investing, before or after the planned date; not when the page shows or the date passes; only to active requests; never duplicated with the Smart Invest email. A temporarily withdrawn opportunity keeps its active requests ("Cancel the opening alert" stays); one email at the real opening; not moved to another project; a definitively cancelled project sends no alert.

**U33-DEC-18 (Q18, C05).** Reminders 7, 3 and 1 day before closing, in-app and email per active channel. A daily job, weekends included, no fixed hour; only milestones after the saving day (none on the saving day, none retroactive); one reminder per milestone, deadline and channel; after a missed run only the latest relevant reminder, with the real remaining time; stop on removal or closing/cancellation and on the Q14 unsubscribe; recalculated when the deadline changes. Saved opportunities come first, visually marked; "Closing soonest" inside each group. The amount stays optional; no balance check and no reservation at saving.

**U33-DEC-19 / U33-DEC-30 (Q14).** Vlad's classification is approved: service messages always on; alerts the investor asked for (Smart Invest matches, "Tell me when it opens", "Save for later" reminders) can be stopped; marketing ("News from Banxum", public newsletter) by explicit consent, unchecked at sign-up, double opt-in for the public form.

- Each alert email has a one-click "Stop these alerts" link, without sign-in: Smart Invest -> stops Smart Invest emails (in-app setting and matching stay); "Tell me when it opens" -> stops the request for that project; "Save for later" -> stops the reminder emails for that project (the saved item and in-app reminders stay). The confirmation says exactly what stopped. Pause of Smart Invest stays separate (both channels).
- "News from Banxum" and the public newsletter are one preference when they cover the same communications and the same verified address: unsubscribing from one updates the other; account creation never reactivates a stopped subscription; consent only for new-project news is not extended to other promotions; the confirmation of the public subscription and the proof of consent are kept. A request to stop all commercial communications is respected.
- To validate (legal): classification of each template, consent and unsubscribe texts (Swiss law, EU ePrivacy).

### Group 9 - Localization

**U33-DEC-31 (Q19, C10).**

- Investor platform EN / de-CH; public site EN / DE / FR (French uses "vous"); English by default; preference saved in the account.
- A professional reviewer for Swiss Standard German and financial terms reviews the ~1,280 draft texts (and consistency with the ~830 design texts) before the functional launch. Vlad exports a table: English, German, context.
- Emails, notifications, confirmations, server messages and errors in the account language only (German or English), not both.
- Public DE/FR: start from the translations in the design, updated to later decisions; owners for content, reviewers for de-CH and Swiss French, lawyers where legal validation applies (privacy/cookies: Q24.4).
- Admin content with reviewed language variants: loan title, summary and purpose; borrower and originator presentation; loan updates and recovery notes; security descriptions. EN/de-CH for investors, EN/DE/FR when public. The reviewer marks a translation as checked; the Banxum owner confirms the meaning; a substantial change of the original needs a new check. Figures come from one source.
- Temporary English for a missing translation of an individual admin content item, with a discreet note in the interface language ("Available in English only"). Not allowed for the interface, standard communications or mandatory contract documents.
- C10: after sign-in the account preference applies on all devices; an explicit choice before sign-in may become the saved preference; without one the account language stays; browser detection never overrides it.

**U33-DEC-32 (C09).** European `1.234,56` default, Swiss `1'234.56` alternative, independent of the language; emails use the preference at sending. The preference applies to **all newly generated personal reports** (the account statement included); Vlad lists the personal reports. Source documents, signed contracts and issued documents keep their form.

### Group 10 - Public Area, Identity, Texts and Resources

**U33-DEC-35 (Q20).** Operational proposals; shown as public promises only after the team confirms its capacity.

- Withdrawals: processing in 1-3 business days from a complete eligible request; processing is separate from the credit at the investor's bank (duration to confirm). No same-day cut-off promise yet. No Banxum fee.
- Repayments: credited to the balances within 2 business days of the effective receipt (identification and reconciliation included); the receipt date stays the date used in calculations.
- Support: Monday-Friday 10:00-12:00 and 13:00-17:00 Europe/Zurich; holidays to state; English confirmed; German wished, to confirm; only languages really available are published; a Garanta owner and a deputy before launch; no numeric answer time for ordinary support.
- Complaints: receipt confirmed within 2 business days; reasoned answer within 14 calendar days from receipt; an update with reason and new estimate before expiry if more time is needed. FINOS affiliation of Garanta Finanzgruppe AG stays (owner confirmed 2026-10-26). Final wording checked by lawyers.

**U33-DEC-36 (Q21, A03).** Main domain for the public site, subdomain `app` for the investor area; the exact domain is still to set. Three email roles (exact addresses later): `support` (investors: support, Help, closure, complaints), `partnerships` (borrowers, originators), `notifications` (automatic sender). The sender may be send-only, but the reply of an email must go to a monitored address (support or partnerships). The public contact form routes by subject. Operations alerts go to the designated internal recipients. Official data: Garanta Finanzgruppe AG, Schauplatzgasse 26, 3011 Bern, Switzerland, UID CHE-302.757.239 (checked in the UID register 2026-11-12); "Complaints" may stay in the postal address; lawyers check the final legal mentions.

**U33-DEC-37 (Q22).** Vlad clarifies the proof of purchase, licence type and holder and the coverage of the real use with Eduard's father (the template DashLite HTML 3.4.0 by Softnio, bought on ThemeForest; the certificate is not in the received material). Vlad lists exactly the template material used (Nioicon, the reduced icon font, template styles). "If it is not expensive, we buy. If it is expensive, we see how we adapt." No budget set; the Extended licence was listed at USD 899 on 2026-11-12, not confirmed as needed or sufficient. Replacing icons alone does not settle rights on template styles.

**U33-DEC-39 (Q24, A02, A04).**

- Keep All projects (open, funded, repaid, with filters), Statistics (correct data, coherent presentation; a larger redesign later; CHF/EUR separate), Help (full questions; Home has a selection), Guides (useful ones, updated), Newsletter (with Q14 rules), Cookies and the legal pages. Move the unique content of How it works into Help and retire the page; Home keeps the short version. Kept pages follow the U33 public design with the Q23 care. Unique content is listed before a page is retired. Catalogue and statistics show real activity, never demo figures as history.
- Texts: "0% fees for investors" stays; "Our first year in figures" is removed from the launch version; sign-in texts follow Q05 (with the last-link transition and the separate PIN role); return texts follow Q01 (day 56 last day, request normally on day 57, calendar advances, manual transfer described separately); the "50-day return" on the Terms outline is corrected.
- Privacy and Cookies: Vlad proposes the source and drafts the texts from the real application (data, purposes, recipients/providers, places, retention, transfers, cookies, settings), with Garanta's data and the final contacts; EN/DE/FR. The security cookie `banxum_device` is listed as necessary after checking its function and two-year duration (A02).

**Other answers.** Q26: a released reservation is an entry in Transactions (project, amount, currency, date, reason, link to the reservation), not duplicated in My investments. Q27: the two invalid selectors are removed; the visible U33 look stays.

## Round 2 Answers Of 2026-11-16 And Vlad's Decisions Of 2026-11-17

Source: "Banxum - Răspunsuri pentru Vlad, runda 2", 16 Nov 2026 (Eduard's decisions; Romanian original), answering the explained follow-up questions (F01-F17, D1-D11) and the explained radical changes of 13 Nov 2026. It completes "Final Answers Of 2026-11-13" and prevails where it corrects it. Vlad's decisions of 17 Nov 2026 (delegated items) are marked "Vlad".

Product approvals are not technical, legal (WW), bank or operational validations. Eduard's agreement to D1-D11 is "in principle": Vlad checks fitness, security and feasibility and reports any adjustment that would change an approved rule before applying it.

### Changes To The Answers Of 2026-11-13

| Item | Answer of 2026-11-13 | Now |
| --- | --- | --- |
| C01 | Every record, demo records included, moves to Late 15 / Default 60. | New loans use 15/60; real contracts with other terms keep them. Moving the demo records is no longer required. **Vlad:** the demo records keep the 5/16 days of migration `loans` 0025; no new migration; QA data can be re-seeded. |
| C03 | Originator offers close at the loan's Late day (15). | **Changed:** a claim purchase is blocked as soon as an amount is due and unpaid (status Due), the due date included. The team plans each offer by hand between two due dates (after the previous installment is paid on time, ending before the next due date, with time for signing and settlement). The purchase check runs live at each purchase, also between scheduled checks. |
| F04 / Q09 | Open (proposal: wait for the overdue installment). | **Changed:** if, during the offer and up to the effective settlement, the borrower pays anything on the offered claim (also partial or early) or an installment falls due, the offer fails and every participation is cancelled; reserved money goes back to the investors' available balances. A due date alone is enough. Participations are not reactivated if the borrower later catches up. Checked again before Garanta's account is debited, also after the price reference day. |
| F02 / Q09 | Open. | **Changed:** settlement = the day Garanta's account is debited for the payment to the originator, with the required assignments signed (F02.1). Price **fixed** for the planned settlement day (F02.2 B): one reference day for all investors; the investor's own confirmation day does not set the price and transfers no rights. If settlement is late, the accepted price stays and the originator bears the interest of the extra days, by an explicit rule in the transaction documents; no extra money is asked from investors; no reservation at a maximum price and no reconfirmation. **Vlad:** planned settlement day = 1 business day after the funding end (success day). |
| F06.1 / Q03 | Proposal: "sandbox applies" per borrower, default "applies". | **Changed:** a checkbox **per project**, **off by default**, set by the admin from a documented confirmation (person and date). Totals and creditor counts stay per borrower (UID), external debts included; the checkbox does not split them and does not remove the 10/20 limits when the total reaches CHF 500,000. **Vlad (2026-11-17, to confirm by Eduard):** the mode is per borrower, pre-selected "sandbox" for a Swiss borrower and confirmed by the admin; sandbox mode = total below CHF 500,000 with no creditor limit; 10/20 mode = 10 creditors per financing and 20 per borrower at any total; switching only when the target mode's limits are already met (no project in funding). |
| F06.2 / Q03 | Open. | Approved: the WW text before the investment, short on the offer page and separate in the confirmation step, with an explicit, unchecked confirmation and proof of the text and the confirmation; publication blocked until the WW text exists. The notice does not move the duty to check limits to the investor (FINMA circular 2008/3 no. 8.3: individual information, at the latest at commitment, before the deposit; a mention in general terms is not enough). |
| F07 / Q03 | Proposals. | Approved: (1) eligible banks do not count in the tax count, their amounts stay in the money total; the categories for the banking check are confirmed separately; (2) a non-bank originator counts as one creditor while it keeps part of the claim; Garanta's strictly temporary holding between the two assignments does not count (legal treatment to confirm by WW); (3) Garanta's remaining co-investment counts as one creditor; (4) an investor in two financings takes a place in each financing and is counted once in the borrower total (WW validates this per legal limit). |
| F08 / Q03 | Proposal. | Approved: a failed check before closing stops the automatic close; the admin decides to wait or to cancel and release the money. |
| F09 / Q03 | Proposal (8 fields). | Approved with additions: creditor identification, a unique financing ID and the link to the group on identical terms, and the signed declaration attached. An aggregated number of creditors alone is not enough. The same loan is never added twice (import, assignment). |
| F10 / Q07 | Open. | Approved A: due dates follow the effective payout day by frequency; short months use their last day, then the reference day returns (31 Jan -> 28 Feb -> 31 Mar). An estimated schedule before funding from the planned payout; the schedule is confirmed at the payout. |
| F11 / Q07 | Proposal: one universal order. | **Changed:** the order in the loan contract prevails, per loan (imported claims included). Standard: contractual recovery costs -> penalty X -> ordinary interest -> principal. No new costs are created by the order. Lawyers confirm the clause in the templates (CO art. 85-87). |
| F12 / Q07 | Proposal. | Approved: a regular installment paid early is recalculated at the receipt value date (receipt day excluded); the rest repays principal; future installments are recalculated, smaller, **keeping the final maturity date**. |
| F13 / Q07 | Recommendation A. | **Changed to B:** the exited investor keeps his recorded fraction until the final largest-remainder distribution of the loan (from the amount really distributable); not transferred to the buyer; not shown as an active investment after the sale. A cent may be credited long after the exit. |
| F14 / Q08 | Proposal. | Approved A: the equal-principal type is closed for new direct loans; existing/imported contracts keep their terms. |
| F15 / C09 | Recommendation C. | Approved C: the decimal sign follows the account's number format, no thousands separator (European `1234,56` with `;` columns; Swiss `1234.56` with `,` columns), independent of the language. Vlad checks the Excel import, also when the account preference differs from Excel's settings. |
| F16 / C06 | Proposal. | Approved: assets with a documented valuation count (real estate, equipment, inventory, vehicles, pledged securities, cash); personal/corporate guarantees add nothing (distinct assets given as security follow the rule, never the guarantor's wealth); pledged receivables only if valued (invoice nominal is not enough); the admin can exclude an asset (exclusion is not release); values in the loan currency (converted value, rate and rate date recorded; no FX). |
| F17 / Q01, Q07 | Proposal. | Approved: separate CHF/EUR calendars in the admin, shared by returns and due dates: SIC for CHF, TARGET/T2 for ordinary EUR payments. Vlad checks with the bank and operations that the calendars fit the real systems and transfer types (instant payments may differ); operations confirm them yearly. Linked with the bank's processing time and cut-offs (D9) and the F01 margin. |
| F01 / Q01 | Proposal A. | Approved A: money that funds a loan must reach the borrower by day 56 of its lot; the close is planned early enough, with an initial margin of 3 business days for signing and payment, confirmed with the bank (not a legal deadline). Order: close -> signatures (managing director or authorized deputy) -> payout; interest from the payout value date. |
| F03 / Q09 | Proposal A. | Approved A: required field, no default; the admin records the exact convention of the claim contract (for example Actual/365 Fixed, Actual/360, the exact 30/360 variant); an unknown or unsupported convention is clarified before it is used in a price; the originator's contract is never overwritten by the direct-loan standard. |
| F05 / Q10 | Proposal A. | Approved A: signing the assignments to investors and the settlement are blocked until the signed first assignment (originator -> Garanta) is uploaded. |
| Q10.2 | One signature: the managing director. | **Completed:** an authorized deputy with his own QES and confirmed single signing right signs when the director is absent. Each document keeps one signature (director or deputy); the person is still to be named. Without the required signature the operation waits (Q10.8). |
| Q19 / Q10.6 | Translations at launch. | **Work order changed:** the whole platform is finished and checked in English first (functions, interface, texts, communications, generated documents); only then, before launch, the other approved languages are translated, integrated and checked. Launch scope stays (EN/de-CH platform and communications; EN/DE contract documents; public EN/DE/FR; reviewed variants of published admin content, not the admin interface). **Vlad:** no multilanguage work until that final phase. |
| Q24.4 | Vlad drafts privacy and cookies. | Confirmed; English first; Vlad gathers the technical facts and contacts Eduard's father for the operational facts, with a precise list of gaps. A short later legal read is recommended, not required. |
| Q05.5 / D3 | Migration of existing accounts (last email link + PIN). | **Vlad (proposal to confirm by Eduard):** no migration flow, because there are no real investors; test accounts are reset or re-created at the release of the new sign-in. |
| D1 | Proposal with a mix rule. | **Vlad, after the NIST SP 800-63B-4 re-check:** 12-128 characters, no forced mix of character types, refusal of common passwords (server list) and of leaked passwords (Have I Been Pwned range API: only the first 5 characters of the SHA-1 hash leave the server); no forced periodic change. |
| D2-D11 | Proposals. | Accepted in principle with Eduard's precisions: D2 Twilio Verify (Garanta account; Vlad checks delivery CH/EU/EEA, cost, limits, abuse protection; SMS at sign-in never replaces the operation PIN); D4 assisted recovery with approval by another person, 24 h dispute window, single-use link; "closing operations" means invalidating unfinished authorizations (valid investments, reservations and contracts stay); 72 h without new bank accounts or a change of the default return account after a completed recovery; Vlad validates the limits and the flow; D5 internal OWASP ASVS level 2 review plus an independent external test before real money, scope including financial authorization, account isolation and recovery; D6 MaxMind GeoLite2 City with a Garanta account and licence key, used locally (licence, attribution, update/deletion terms checked); D7 evaluate Skribble, then compare Swisscom Trust Services (provider not chosen); D8 custom schedules, vehicles and Coming soon for originators all from the start; D9 1 business day and 12:00 cut-off only as configuration/test values; D10 all three service times (withdrawals included) need confirmed capacity before they are public promises; D11 inventory of Nioicon, DashLite-derived styles and images used. |

### Confirmed Without Change

C05 (saved first), C06 (LTV on the distinct assets), Q24.2 ("0% fees for investors" word for word; the "first year" article retired), the three Swiss regimes and the dynamic minimum to the success threshold, the penalty X rule (all overdue contractual amounts, never on penalties; a point legal check before real contracts is recommended, CO art. 105 and 163), Q01 (day 56 withdraw-only; initiation and debit are distinct), Q12 (blocking only for a necessary unresolved review, not for a reminder before a future date), Q14 (one News/newsletter preference only for the same category and the same verified address).

Correction (Eduard, 16 Nov): an example due date of Sunday 15 Nov 2026 moves to Friday 13 Nov; a payment on 18 Nov then has five penalty days (14-18 Nov), not three.

### Vlad's Answers Of 2026-11-17 (Questions E-01 To E-09)

| ID | Answer |
| --- | --- |
| E-01 | Confirmed: no migration flow for old accounts (no real investors); test accounts are reset or re-created at the release of the new sign-in. |
| E-02 | Confirmed: Vlad's Swiss model. One mode per borrower: "sandbox" (total below CHF 500,000, no lender limit) or "10/20" (10 lenders per project, 20 per borrower, any amount); "sandbox" pre-selected for a new Swiss borrower and confirmed by the admin; a change only when the target mode's limits are already met (repaid loans free lenders and amounts; no change while a project is in funding; no switch to sandbox while open loans total CHF 500,000 or more). Replaces the per-project checkbox of round 2. |
| E-03 | A placeholder text along Vlad's description until the legal text arrives (Vlad asks for it): the borrower operates under the Swiss sandbox exemption, is not supervised by FINMA, and the investment is not covered by the Swiss deposit protection. The investor's confirmation stays unchecked by default. |
| E-04 | The originator-agreement rule (the originator bears the extra days when settlement is late) is prepared by the team; a placeholder clause in the templates is optional. |
| E-05 | Confirmed: NIST rules (12-128 characters, no forced mix, common and leaked passwords refused, no forced periodic change). |
| E-06 | Confirmed: English only for now; no i18n work until the final phase (German and French deferred). |
| E-07 | The deliberate differences from the U33 HTML are explained to Vlad (IMPLEMENTATION_PLAN 18.1); no change. |
| E-08 | Yes, per U33-DEC-26 (verified personal data, address included, shown read-only with "Contact support to change"; no invented fields): the verified address, birth date and nationality are stored from the Didit result when Didit provides them. |
| E-09 | Confirmed: the "Tax report" is an information report for the investor's tax return, not an official tax certificate; its text says so. |

### Vlad's Decisions Of 2026-11-17 (Operations Facts And The Installment Rule)

**Changed (signalled to Eduard): presumed payment of installments.** It replaces, for new direct loans, the Q07 rules "base interest on matured principal stops at the adjusted due date even when unpaid" and "penalty X from the day after the due date", and the round-2 C03 rule "purchases blocked from the due date itself".

- On the (adjusted) due date a scheduled installment is **presumed paid on time**: the schedule continues as if it was paid (its principal no longer bears interest); investors see it as paid; the money reaches their balances only when the admin confirms it.
- Within **10 calendar days** the admin either confirms it as **paid in time**, with the bank statement uploaded (the installment is distributed as scheduled; everything is as if the borrower paid exactly on the due date; no penalty and no interest on its principal, also when the money arrived a few days later), or marks it **not received**. Without an action, it becomes "not received" automatically on day 11 and the admin is alerted.
- **Not received:** recalculated from the due date as if the installment never arrived: normal interest on the whole outstanding principal, the unpaid installment's principal included (no interest on unpaid interest); **no penalty X before Default**. Statuses count from the due date: Due (days 0-14), Late from day 15, **Default automatically on day 60** (or the contract's day). A later receipt is recorded with its value date: interest on the unpaid principal runs to the day before the receipt; the payment follows the loan's payment order and is distributed.
- **From the Default day:** penalty X (the contract's daily rate) on the unpaid amounts, **replacing** normal interest on those amounts (no retroactive X before the Default day); principal not yet due keeps normal interest; never X on X; no capitalization.
- **Purchases** (originator claims, resale) stay allowed during the 10-day window (risk accepted: a buyer can buy just before the admin marks "not received"); they are blocked once an installment is marked not received. The F04 rule for originator offers (a due date before settlement makes the offer fail) is unchanged. Early payments (F12) are unchanged.

**Operations facts:**

| Item | Decision |
| --- | --- |
| Hosting | The current server; snapshots on AWS from time to time, in AWS Europe (Zurich) `eu-central-2` (consistent with INFRA-DEC-009). |
| Email | The existing SendGrid account (Vlad's); the account region and the data processing terms are listed in the privacy inventory. |
| SMS | The existing Twilio account (Twilio Verify). |
| Retention | The legal limits: identity and anti-money-laundering files 10 years after the relationship ends (AMLA art. 7); accounting, payment and ledger records 10 years (CO art. 958f); contracts and signed assignments 10 years after they end (CO art. 127); sign-in history 365 days; other data as short as possible. |
| Privacy contact | The support address (the same as for everything else). |
| Analytics | Google Analytics on the public site (Vlad adds it); it loads only after the visitor's consent in the cookie settings, and the cookie text lists it. |
| Bank | Regular Swiss bank schedules: processing 1 business day, cut-off 12:00 Europe/Zurich (settings). The proof of the debit is the bank statement, outside the platform; the platform uses the date the team marks the transfer as made. |
| Calendars | Regular bank holidays: CHF (Swiss interbank) and EUR (TARGET) preloaded each year, editable by the admin. |
| Service times | Capacity confirmed: withdrawals processed in 1-3 business days; repayments credited within 2 business days of receipt (the 10-day confirmation window is the maximum). Support hours are not shown in the platform. |
| Signer | Until further notice, an admin user with the signer permission signs the assignments with his own QES (his authority to sign for Garanta to be confirmed by the lawyers). |
| Licence | Garanta has the template licence; nothing to do in the platform. |
| Lawyers | No validation blocks the work; Vlad reports any change from the lawyers. |
