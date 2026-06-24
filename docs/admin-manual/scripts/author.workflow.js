export const meta = {
  name: 'banxum-admin-manual-author',
  description: 'Author the BANXUM admin training manual content (domain primer, glossary, per-screen annotated explanations, end-to-end flows) grounded in real code',
  phases: [
    { title: 'Domain' },
    { title: 'Screens' },
    { title: 'Flows' },
    { title: 'Verify' },
  ],
}

const ROOT = '/Volumes/quary-mac/Projects/p2p-BANXUM'
const OUT = `${ROOT}/docs/admin-manual/content`
const MANIFEST = `${ROOT}/docs/admin-manual/figures/manifest.json`

const SHARED = `
PROJECT: BANXUM is a peer-to-peer (P2P) lending marketplace operated by Garanta Finanzgruppe AG (a Swiss financial group).
Individual investors ("lenders") deposit money, then fund loans to vetted business "borrowers"; borrowers repay with interest; lenders withdraw.
You are documenting the INTERNAL ADMIN CONSOLE (the "ops console") served at /admin, used by Garanta staff — NOT the investor app.

AUDIENCE: a brand-new operations admin who may have ZERO knowledge of P2P lending or of this product. Explain plainly, define every piece of jargon the first time it appears, never assume prior knowledge. Be concrete and specific. Use short sentences. Prefer "what it does / why it matters / what to watch out for".

ACCURACY IS CRITICAL: read the actual source files listed before writing. Do not invent fields, buttons, statuses, or behaviors that are not in the code. If the code enforces a rule (a gate, a validation, a status transition), state it precisely.

SCREENSHOT MANIFEST: ${MANIFEST} is JSON: an array of screens; each screen has {key, figures:[{id, title, cssWidth, cssHeight, items:[{role, text, x, y, w, h}]}]}.
"items" are the real UI elements captured on that figure (role is one of heading/eyebrow/column/field/input/button/status/banner; text is the visible label; x/y/w/h are pixel coordinates inside the figure). When you annotate a figure, reference an element by its 0-based INDEX into that figure's items array. Only annotate items that genuinely need explaining; skip decorative duplicates.

OUTPUT RULES: Write ONLY raw, valid JSON (UTF-8) to the exact path given. No markdown code fences, no commentary, no trailing commas. Your final chat message must be a single short status line (e.g. "wrote screen-finance.json: 8 figures, 47 annotations"). Read files with your tools first; write the file; then report.
`

phase('Domain')

const domainPrimerPrompt = `${SHARED}

TASK: Write the plain-language P2P PRIMER that opens the manual — the conceptual foundation a new admin needs before touching any screen.
READ FIRST (ground every claim in these):
- ${ROOT}/backend/apps/accounts_auth/models.py (AccountType, AccountStatus, can_login, phone_verified)
- ${ROOT}/backend/apps/ledger/services.py and ${ROOT}/backend/apps/ledger/models.py (balance lots, available/investable/withdraw-only/overdue/frozen/penalty buckets, deposits, withdrawals, the 30/60-day ageing windows, forced withdrawals)
- ${ROOT}/backend/apps/investor_portal/services.py (deposit instructions, BX-{currency}-{investor_reference} payment reference, financial-access gating)
- ${ROOT}/backend/apps/loans/models.py and services.py (loan statuses & lifecycle)
- ${ROOT}/backend/apps/marketplace_primary (primary market: investment orders, allocation, funding)
- ${ROOT}/backend/apps/secondary_market (reselling holdings)
- ${ROOT}/backend/apps/kyc_compliance/models.py and services.py (KYC for people, KYB for companies, Didit provider, manual review, sanctions/PEP)
- ${ROOT}/backend/apps/fx (currency exchange / settlement)
- ${ROOT}/backend/apps/servicing (repayments, late/default/recovery)

COVER, as clearly-separated sections (heading + body paragraphs + optional bullets):
1. "What BANXUM is" — the marketplace in 4-5 sentences; who the operator is.
2. "The four people in the story" — Investor/lender, Borrower (a company, no portal login — admin-entered), Garanta operator (you), Didit (external identity provider). Define each.
3. "How money moves" — the full cycle: bank deposit -> matched & ledgered -> investable balance -> invest in a loan (primary market) -> borrower disbursement -> repayments -> returns -> withdrawal to bank. Mention the BX-currency-reference payment reference.
4. "Money is not a bank account" — balances are non-interest-bearing operational funds, segregated, and subject to regulatory AGEING. Explain the 30/60-day windows and what "forced withdrawal" / "frozen" / "penalty" mean in plain words.
5. "The balance buckets" — available, investable, withdraw-only, overdue, frozen, penalty: what each means for what the investor can do.
6. "The life of a loan" — draft -> published -> funded -> performing/late -> repaid OR defaulted -> recovery/written-off; primary vs secondary market in one paragraph each.
7. "Gates that protect everyone" — KYC (people) and KYB (companies) must pass; phone verification; account statuses (active/restricted/locked/closed/pending_kyc); why actions are blocked server-side and cannot be overridden in the UI.
8. "What the admin console is for" — the 7 areas at a glance (Daily dashboard, Tasks, Compliance, Finance ops, Loans, Reports, Superadmin settings) — one sentence each.

SCHEMA (write to ${OUT}/primer.json):
{ "title": string, "sections": [ { "heading": string, "body": [string,...], "bullets": [string,...] } ] }
Aim for 8 rich sections. bullets optional per section.`

const glossaryPrompt = `${SHARED}

TASK: Write the GLOSSARY / quick-reference. Three groups: domain TERMS, account/loan/case STATUSES, and dashboard QUEUES.
READ FIRST:
- ${ROOT}/backend/apps/accounts_auth/models.py (AccountStatus, AccountType)
- ${ROOT}/backend/apps/loans/models.py (loan statuses), ${ROOT}/backend/apps/kyc_compliance/models.py (KycStatus, manual-review reasons)
- ${ROOT}/frontend/src/adminConsole/AdminApp.tsx (the queueDefinitions array near the top lists all 13 dashboard queues with descriptions — reproduce each in plainer language)
- ${ROOT}/backend/apps/ledger/models.py (balance bucket / lot terms), ${ROOT}/backend/apps/secondary_market, ${ROOT}/backend/apps/fx
TERMS to define (at least): lender/investor, borrower, KYC, KYB, Didit, primary market, secondary market, balance lot, minor units, investor reference, payment reference, collection account, payout instruction (IBAN), withdrawal vs forced withdrawal, ageing, disbursement, servicing, recovery, default, reconciliation break, outbox/dead-letter email, FX settlement, audit event, manual review, sanctions/PEP/adverse-media. Add any other term that appears on screen.

SCHEMA (write to ${OUT}/glossary.json):
{ "terms": [ {"term": string, "definition": string} ],
  "statuses": [ {"name": string, "meaning": string} ],
  "queues": [ {"name": string, "meaning": string} ] }`

const domain = await parallel([
  () => agent(domainPrimerPrompt, { label: 'primer', phase: 'Domain' }),
  () => agent(glossaryPrompt, { label: 'glossary', phase: 'Domain' }),
])

phase('Screens')

const SCREENS = [
  {
    key: 'dashboard', title: 'Daily Dashboard',
    figures: ['dashboard-1-daily-dashboard-queues', 'dashboard-4-card'],
    kpiFigure: 'dashboard-0-key-metrics',
    files: [
      '${ROOT}/frontend/src/adminConsole/AdminApp.tsx (AdminDashboard component + queueDefinitions array — 13 queues, the queue tabs rail, the selected-queue table, the item detail drawer)',
      '${ROOT}/backend/apps/admin_ops/services.py (get_admin_operations_dashboard — how each queue is populated)',
    ],
    focus: 'The landing screen and daily triage tool. A left rail of 13 work QUEUES (each with a live count + group), a table of items for the selected queue, and a platform-wide multi-currency balance summary table. Explain what each queue means, how to read counts/priority/overdue, and that the dashboard is read/triage only — actual actions happen in the module screens. The figure "dashboard-4-card" is the platform balance summary by currency (Available/Investable/Withdraw-only/Overdue/Frozen/Penalty/Pending withdrawals/Pending bank ops).',
  },
  {
    key: 'tasks', title: 'Tasks',
    figures: ['tasks-1-operational-task-queue', 'tasks-2-card', 'tasks-3-card'],
    files: [
      '${ROOT}/frontend/src/adminConsole/AdminTasksPanel.tsx (toolbar, filters, table, create-task form, status transitions, related-object lookup)',
      '${ROOT}/backend/apps/admin_ops/models.py (AdminTask: task_type, priority, status, related_object_type/id, due) and services.py (create_admin_task/update_admin_task, allowed transitions)',
    ],
    focus: 'Internal operational to-do list: create tasks, assign, set priority/due date, link a task to a real object (loan/user/withdrawal/etc.) via autocomplete, move a task through its statuses, and read its event history. Distinguish manually-created tasks from auto-generated ones (e.g. reconciliation breaks).',
  },
  {
    key: 'compliance', title: 'Compliance',
    figures: ['compliance-5-kyc-manual-review', 'compliance-6-record-aml-decision', 'compliance-7-account-access-controls'],
    kpiFigure: 'compliance-0-key-metrics',
    files: [
      '${ROOT}/frontend/src/adminConsole/AdminModulePanels.tsx (CompliancePanel ~line 932; the KYC manual-review table, the Record AML decision form, and AccountAccessForm)',
      '${ROOT}/backend/apps/kyc_compliance/services.py and models.py (KycVerificationCase, manual review decisions, reasons, sanctions/PEP non-overridable blocks)',
      '${ROOT}/backend/apps/accounts_auth/services.py (change_account_access: statuses, reason codes, clean-account confirmation)',
    ],
    focus: 'Where Garanta makes identity/AML decisions Didit routed to manual review, and where an admin changes a user account status (restrict/lock/close/reactivate). Stress: sanctions/fraud blocks are non-overridable server-side; closing an account needs clean-account confirmation; superadmin needed to change admin accounts.',
  },
  {
    key: 'finance', title: 'Finance Operations',
    figures: ['finance-0-lender-deposit', 'finance-1-payout-instruction', 'finance-2-investor-balance-lookup', 'finance-3-balance-ageing-scan', 'finance-4-reconciliation-snapshot', 'finance-5-withdrawal-execution', 'finance-6-borrower-disbursement', 'finance-7-fx-settlement'],
    files: [
      '${ROOT}/frontend/src/adminConsole/AdminModulePanels.tsx (FinanceOpsPanel ~line 1139 and its 8 forms: DepositForm, PayoutInstructionForm, BalanceSummaryLookup, BalanceAgeingScanForm, ReconciliationSnapshotForm, WithdrawalOpsForm, BorrowerDisbursementForm, FxAdminOps)',
      '${ROOT}/backend/apps/ledger/services.py (lender deposit declaration, payout instruction registration, balance summary, ageing scan + forced withdrawals, withdrawal execution/finalization, borrower disbursement, reconciliation snapshot)',
      '${ROOT}/backend/apps/fx (FX settlement)',
    ],
    focus: 'The money-movement cockpit. Explain each of the 8 forms: what real-world action it records, the key inputs (especially the investor autocomplete that searches by name/email/reference/IBAN and stores a hidden ID; the BX-currency-reference matching for deposits; amount in MINOR UNITS i.e. cents), and the safety rules (e.g. borrower must match the loan; ageing scan can be a dry run; IBAN collision warning). Define "minor units", "collection account", "payout instruction", "disbursement", "reconciliation snapshot".',
  },
  {
    key: 'loans', title: 'Loans & Marketplace',
    figures: ['loans-5-borrowers', 'loans-6-loans', 'loans-7-primary-marketplace-operations', 'loans-8-secondary-market-approvals', 'loans-9-servicing-and-recovery'],
    kpiFigure: 'loans-0-key-metrics',
    files: [
      '${ROOT}/frontend/src/adminConsole/AdminModulePanels.tsx (LoansPanel ~line 1680: Borrowers table, Loans table, Create borrower/loan, LoanPublishCloseForm/Primary marketplace operations, ServicingOpsForm, SecondaryMarketAdminForm)',
      '${ROOT}/backend/apps/entities (BorrowerEntity, KYB, can_transact, compliance_hold)',
      '${ROOT}/backend/apps/loans/services.py (draft/publish/close/cancel gates), ${ROOT}/backend/apps/marketplace_primary (orders, allocate, release), ${ROOT}/backend/apps/secondary_market (listing approvals), ${ROOT}/backend/apps/servicing (repayments, ageing scan, recovery)',
    ],
    focus: 'The lending engine. Borrowers are companies admins enter by hand (no borrower login). Explain: the Borrowers table & KYB gate; the Loans table (status/amount/rate/LTV/funding deadline) and that loans only publish when fields+schedule+funding window+borrower KYB pass; Primary marketplace operations (publish/close/cancel a loan, release a stuck investor order); Servicing and recovery (record a repayment, run a servicing scan, add notes, recovery); Secondary-market approvals (approve/reject reselling of holdings). Define LTV, funding deadline, allocation, primary vs secondary.',
  },
  {
    key: 'reports', title: 'Reports & Audit',
    figures: ['reports-0-report-generation', 'reports-1-audit-event-search'],
    files: [
      '${ROOT}/frontend/src/adminConsole/AdminModulePanels.tsx (ReportsPanel ~line 2787: report generation form + audit event search)',
      '${ROOT}/backend/apps/reporting (report types, output formats, redaction modes)',
      '${ROOT}/backend/apps/platform_core (AuditEvent: actor/action/target, immutable log)',
    ],
    focus: 'Generate accounting/tax/regulatory/operational exports (choose report type, output format CSV/PDF/ZIP, redaction mode, date range) and search the immutable AUDIT log (who did what to which target, when). Explain redaction modes and that the audit log is append-only evidence.',
  },
  {
    key: 'settings', title: 'Superadmin Settings',
    figures: ['settings-0-document-templates'],
    files: [
      '${ROOT}/frontend/src/adminConsole/AdminModulePanels.tsx (SettingsPanel: document templates list + create/publish template)',
      '${ROOT}/backend/apps/documents (DocumentTemplate/Version, publish, versioning, legal review reference)',
    ],
    focus: 'Superadmin-only governance: manage versioned legal/document TEMPLATES (create a new version, publish the current one). User directory, admin-user creation, account access controls, and read-only impersonation now live in the Users module.',
  },
  {
    key: 'users', title: 'Users',
    figures: ['users-0-user-accounts', 'users-1-account-access-controls', 'users-2-read-only-impersonation'],
    files: [
      '${ROOT}/frontend/src/adminConsole/AdminModulePanels.tsx (UserAccountsPanel: paginated user directory, admin-user creation, account-access controls, superadmin read-only impersonation)',
      '${ROOT}/backend/apps/admin_ops/api/views.py (AdminUserDirectoryView, ReadOnlyImpersonationStartView)',
      '${ROOT}/backend/apps/platform_core/services/impersonation.py (signed short-lived read-only impersonation token)',
      '${ROOT}/backend/apps/accounts_auth/services.py (create_admin_user requires active superadmin; change_account_access)',
    ],
    focus: 'Account-level operations: backend-searchable user table, creating admins, restricting/locking/closing/reactivating users, and superadmin-only read-only investor portal view. Stress that impersonation never changes the user session, cannot impersonate admins/superadmins, disables investor mutations, and generated/downloaded evidence is audited to the superadmin only.',
  },
]

const screenPrompt = (s) => `${SHARED}

TASK: Author the manual section for the admin screen "${s.title}" (manifest key "${s.key}").
READ FIRST: ${s.files.map((f) => '- ' + f).join('\n')}
ALSO READ the manifest (${MANIFEST}); use only the figures for key "${s.key}".

WHAT THIS SCREEN IS FOR: ${s.focus}

ANNOTATE these figures (by id), in this order: ${s.figures.map((f) => '"' + f + '"').join(', ')}.
${s.kpiFigure ? `Also include the KPI figure "${s.kpiFigure}": it has no clickable items, so instead of "annotations" provide "kpiTiles" — one entry per metric tile shown (left to right), each explaining what the number means and why an admin watches it.` : ''}
For each figure: read its items[] in the manifest and produce annotations for the elements that matter (buttons, key fields, status chips, column headers, filters, autocompletes). Each annotation references the item by 0-based index. Write the explanation for a total beginner: what the element is, what happens when you use it, and any rule/gotcha. It is fine to annotate 5-15 items on dense figures.

SCHEMA (write to ${OUT}/screen-${s.key}.json):
{
  "key": "${s.key}",
  "title": "${s.title}",
  "intro": [string,...],            // 2-4 short paragraphs introducing the screen to a newcomer
  "whatYouDoHere": [string,...],    // 3-6 bullets of the concrete jobs done here
  "figures": [
    {
      "id": string,                 // must equal a manifest figure id from the list above
      "caption": string,            // one-line figure caption
      "summary": string,            // 1-2 sentences: what this panel/table/form is
      "annotations": [ { "item": number, "label": string, "text": string } ],
      "kpiTiles": [ { "label": string, "text": string } ],   // ONLY for the kpi figure; omit otherwise
      "notes": [string,...]         // optional: options, rules, gotchas for this figure
    }
  ]
}
Include every figure id listed above (plus the kpi figure if given). Be exhaustive and accurate.`

const screens = await parallel(
  SCREENS.map((s) => () => agent(screenPrompt(s), { label: 'screen:' + s.key, phase: 'Screens' }))
)

phase('Flows')

const flowsPrompt = `${SHARED}

TASK: Write END-TO-END WORKFLOWS — numbered, click-by-click walkthroughs that stitch the screens together for real jobs. These teach a newcomer "to do X, go here, then here".
READ FIRST (to get the gates/order right): ${ROOT}/frontend/src/adminConsole/AdminModulePanels.tsx, ${ROOT}/frontend/src/adminConsole/AdminApp.tsx, ${ROOT}/backend/apps/ledger/services.py, ${ROOT}/backend/apps/loans/services.py, ${ROOT}/backend/apps/kyc_compliance/services.py, ${ROOT}/backend/apps/entities. Also skim the manifest for the exact screen/figure names to reference.

WRITE these flows (each as ordered steps that name the screen and the control to use):
1. Onboard a borrower and publish their first loan (Borrowers -> KYB -> Create loan draft -> Primary marketplace operations: publish; note the publish gates).
2. Match an incoming bank deposit to a lender (Finance ops -> Lender deposit; using the BX-currency-reference or payer name; minor units).
3. Resolve a KYC case routed to manual review (Compliance -> KYC manual review -> Record AML decision; note sanctions/PEP are non-overridable).
4. Register a payout IBAN and execute an investor withdrawal (Finance ops -> Payout instruction, then Withdrawal execution; IBAN collision warning).
5. Handle a day-60 forced withdrawal (Finance ops -> Balance ageing scan -> forced withdrawal queue -> execute).
6. Record a borrower repayment / run servicing, and handle a late loan (Loans -> Servicing and recovery).
7. Approve a secondary-market resale listing (Loans -> Secondary-market approvals).
8. Disburse a funded loan to the borrower (Finance ops -> Borrower disbursement; borrower must match the loan).
9. Generate a regulatory report and find an action in the audit log (Reports).
10. Create a new admin user and restrict an investor account (Users module / Account access controls).
11. Work the daily dashboard from open to empty (Daily dashboard: read queues, triage, jump to the right module).

SCHEMA (write to ${OUT}/flows.json):
{ "flows": [ {
  "title": string, "goal": string, "actor": string,
  "preconditions": [string,...],
  "steps": [ { "n": number, "screen": string, "action": string, "detail": string } ],
  "outcome": string, "pitfalls": [string,...]
} ] }
Be precise about ORDER and GATES (what must be true before each step). 11 flows.`

const flows = await agent(flowsPrompt, { label: 'flows', phase: 'Flows' })

phase('Verify')

const verifyPrompt = (target, file, checkFiles) => `${SHARED}

TASK: ADVERSARIALLY FACT-CHECK the already-written manual content in ${file} against the real code. You are a skeptical reviewer; assume there are errors and find them.
READ: ${file} (the content to check) AND the authoritative code: ${checkFiles}.
For every claim about a status name, a gate/rule, a field, a button, a flow order, or a P2P concept, verify it against the code. Flag anything wrong, missing a critical caveat, or misleading to a newcomer. Do not nitpick style.

SCHEMA (write to ${OUT}/verify-${target}.json):
{ "corrections": [ { "location": string, "problem": string, "fix": string, "severity": "high"|"medium"|"low" } ],
  "confirmedAccurate": [string,...] }
If a claim is correct, you may list it briefly in confirmedAccurate. Be specific in fixes (quote the correct value).`

const verify = await parallel([
  () => agent(
    verifyPrompt('domain', `${OUT}/primer.json`,
      `${ROOT}/backend/apps/accounts_auth/models.py, ${ROOT}/backend/apps/ledger/services.py, ${ROOT}/backend/apps/ledger/models.py, ${ROOT}/backend/apps/investor_portal/services.py, ${ROOT}/backend/apps/kyc_compliance/models.py, ${ROOT}/backend/apps/loans/models.py`),
    { label: 'verify:domain', phase: 'Verify' }
  ),
  () => agent(
    verifyPrompt('flows', `${OUT}/flows.json`,
      `${ROOT}/backend/apps/ledger/services.py, ${ROOT}/backend/apps/loans/services.py, ${ROOT}/backend/apps/kyc_compliance/services.py, ${ROOT}/backend/apps/entities, ${ROOT}/frontend/src/adminConsole/AdminModulePanels.tsx`),
    { label: 'verify:flows', phase: 'Verify' }
  ),
])

return {
  domain: domain.map((d) => (d || '').slice(0, 200)),
  screens: screens.map((s) => (s || '').slice(0, 200)),
  flows: (flows || '').slice(0, 200),
  verify: verify.map((v) => (v || '').slice(0, 200)),
  note: 'content written to docs/admin-manual/content/*.json',
}
