export const meta = {
  name: 'banxum-admin-manual-fill',
  description: 'Re-run the 4 manual-authoring agents that hit transient socket errors (glossary, compliance, loans, settings) and apply verified accuracy corrections to primer.json and flows.json',
  phases: [
    { title: 'Fill' },
    { title: 'Fix' },
  ],
}

const ROOT = '/Volumes/quary-mac/Projects/p2p-BANXUM'
const OUT = `${ROOT}/docs/admin-manual/content`
const MANIFEST = `${ROOT}/docs/admin-manual/figures/manifest.json`

const SHARED = `
PROJECT: BANXUM is a peer-to-peer (P2P) lending marketplace operated by Garanta Finanzgruppe AG (a Swiss financial group).
Individual investors ("lenders") deposit money, then fund loans to vetted business "borrowers"; borrowers repay with interest; lenders withdraw.
You are documenting the INTERNAL ADMIN CONSOLE served at /admin, used by Garanta staff.
AUDIENCE: a brand-new operations admin with ZERO knowledge of P2P lending or this product. Explain plainly, define jargon, never assume prior knowledge. Short sentences. Concrete.
ACCURACY IS CRITICAL: read the actual source files before writing; do not invent fields/buttons/statuses/behaviors.
SCREENSHOT MANIFEST: ${MANIFEST} is JSON: array of screens; each {key, figures:[{id,title,cssWidth,cssHeight,items:[{role,text,x,y,w,h}]}]}. Annotate a figure element by its 0-based INDEX into that figure's items array. Only annotate items worth explaining.
OUTPUT RULES: Write ONLY raw valid JSON to the exact path. No code fences, no commentary. Final chat message = one short status line. Read files first, write file, then report.
`

const SCREENS = [
  {
    key: 'compliance', title: 'Compliance',
    figures: ['compliance-5-kyc-manual-review', 'compliance-6-record-aml-decision', 'compliance-7-account-access-controls'],
    kpiFigure: 'compliance-0-key-metrics',
    files: [
      `${ROOT}/frontend/src/adminConsole/AdminModulePanels.tsx (CompliancePanel ~line 932; KYC manual-review table, Record AML decision form, AccountAccessForm)`,
      `${ROOT}/backend/apps/kyc_compliance/services.py and models.py (KycVerificationCase, manual review decisions, reasons, sanctions/PEP non-overridable blocks)`,
      `${ROOT}/backend/apps/accounts_auth/services.py (change_account_access: statuses, reason codes, clean-account confirmation)`,
    ],
    focus: 'Where Garanta makes identity/AML decisions Didit routed to manual review, and where an admin changes a user account status (restrict/lock/close/reactivate). Stress: sanctions/fraud blocks are non-overridable server-side; closing an account needs clean-account confirmation; superadmin needed to change admin accounts.',
  },
  {
    key: 'loans', title: 'Loans & Marketplace',
    figures: ['loans-5-borrowers', 'loans-6-loans', 'loans-7-primary-marketplace-operations', 'loans-8-secondary-market-approvals', 'loans-9-servicing-and-recovery'],
    kpiFigure: 'loans-0-key-metrics',
    files: [
      `${ROOT}/frontend/src/adminConsole/AdminModulePanels.tsx (LoansPanel ~line 1680: Borrowers table, Loans table, Create borrower/loan, LoanPublishCloseForm/Primary marketplace operations, ServicingOpsForm, SecondaryMarketAdminForm)`,
      `${ROOT}/backend/apps/entities (BorrowerEntity, BorrowerKybStatus enum -> not_started/pending/approved/declined/manual_review/expired/reverification_required, can_transact, compliance_hold)`,
      `${ROOT}/backend/apps/loans/services.py (draft/publish/close/cancel gates), ${ROOT}/backend/apps/marketplace_primary (orders, allocate, release), ${ROOT}/backend/apps/secondary_market (listing approvals), ${ROOT}/backend/apps/servicing/services.py (repayment warning-acknowledged gate fires when amount != next due in EITHER direction; over-amount only allowed when loan status funded; recovery)`,
    ],
    focus: 'The lending engine. Borrowers are companies admins enter by hand (no borrower login). Explain: Borrowers table & KYB gate (valid KYB values: not_started, pending, approved, declined, manual_review, expired, reverification_required; only approved + no compliance hold lets a loan publish); Loans table (status/amount/rate/LTV/funding deadline) and that loans only publish when fields+schedule+funding window+borrower KYB pass; Primary marketplace operations (publish/close/cancel a loan, release a stuck investor order); Servicing and recovery (record a repayment, run a servicing scan, add notes, recovery); Secondary-market approvals. Define LTV, funding deadline, allocation, primary vs secondary.',
  },
  {
    key: 'settings', title: 'Superadmin Settings',
    figures: ['settings-0-document-templates'],
    files: [
      `${ROOT}/frontend/src/adminConsole/AdminModulePanels.tsx (SettingsPanel: document templates list + create/publish template)`,
      `${ROOT}/backend/apps/documents (DocumentTemplate/Version, publish, versioning, legal review reference)`,
    ],
    focus: 'Superadmin-only governance: manage versioned legal/document TEMPLATES (create a new version, publish the current one). User directory, admin-user creation, account access controls, and read-only impersonation now live in the Users module.',
  },
  {
    key: 'users', title: 'Users',
    figures: ['users-0-user-accounts', 'users-1-account-access-controls', 'users-2-read-only-impersonation'],
    files: [
      `${ROOT}/frontend/src/adminConsole/AdminModulePanels.tsx (UserAccountsPanel: paginated user directory, admin-user creation, account-access controls, superadmin read-only impersonation)`,
      `${ROOT}/backend/apps/admin_ops/api/views.py (AdminUserDirectoryView, ReadOnlyImpersonationStartView)`,
      `${ROOT}/backend/apps/platform_core/services/impersonation.py (signed short-lived read-only impersonation token)`,
      `${ROOT}/backend/apps/accounts_auth/services.py (create_admin_user requires active superadmin; change_account_access)`,
    ],
    focus: 'Account-level operations: backend-searchable user table, creating admins, restricting/locking/closing/reactivating users, and superadmin-only read-only investor portal view. Stress that impersonation never changes the user session, cannot impersonate admins/superadmins, disables investor mutations, and generated/downloaded evidence is audited to the superadmin only.',
  },
]

const screenPrompt = (s) => `${SHARED}

TASK: Author the manual section for the admin screen "${s.title}" (manifest key "${s.key}").
READ FIRST:
${s.files.map((f) => '- ' + f).join('\n')}
ALSO READ the manifest (${MANIFEST}); use only the figures for key "${s.key}".
WHAT THIS SCREEN IS FOR: ${s.focus}
ANNOTATE these figures (by id), in order: ${s.figures.map((f) => '"' + f + '"').join(', ')}.
Also include the KPI figure "${s.kpiFigure || ''}" if non-empty: it has no clickable items, so instead of "annotations" provide "kpiTiles" (one per metric tile left-to-right, each explaining the number and why an admin watches it).
For each figure, read its items[] and annotate the elements that matter (buttons, key fields, status chips, column headers, filters, autocompletes); reference each by 0-based index; explain for a total beginner (what it is, what happens when used, any rule/gotcha). 5-15 annotations on dense figures is fine.

SCHEMA (write to ${OUT}/screen-${s.key}.json):
{ "key":"${s.key}", "title":"${s.title}",
  "intro":[string,...], "whatYouDoHere":[string,...],
  "figures":[ { "id":string, "caption":string, "summary":string,
    "annotations":[{"item":number,"label":string,"text":string}],
    "kpiTiles":[{"label":string,"text":string}], "notes":[string,...] } ] }
Include every figure id listed (plus the kpi figure if given). Be exhaustive and accurate.`

const glossaryPrompt = `${SHARED}

TASK: Write the GLOSSARY / quick-reference: domain TERMS, account/loan/case STATUSES, and dashboard QUEUES.
READ FIRST:
- ${ROOT}/backend/apps/accounts_auth/models.py (AccountStatus, AccountType)
- ${ROOT}/backend/apps/loans/models.py (loan statuses), ${ROOT}/backend/apps/kyc_compliance/models.py (KycStatus, manual-review reasons), ${ROOT}/backend/apps/entities/models.py (BorrowerKybStatus)
- ${ROOT}/frontend/src/adminConsole/AdminApp.tsx (queueDefinitions array near the top lists all 13 dashboard queues with descriptions — reproduce each in plainer language)
- ${ROOT}/backend/apps/ledger/models.py (balance bucket/lot terms), ${ROOT}/backend/apps/secondary_market, ${ROOT}/backend/apps/fx
Define (at least): lender/investor, borrower, KYC, KYB, Didit, primary market, secondary market, balance lot, minor units, investor reference, payment reference, collection account, payout instruction (IBAN), withdrawal vs forced withdrawal, ageing, disbursement, servicing, recovery, default, reconciliation break, outbox/dead-letter email, FX settlement, audit event, manual review, sanctions/PEP/adverse-media. Add any other on-screen term.

SCHEMA (write to ${OUT}/glossary.json):
{ "terms":[{"term":string,"definition":string}],
  "statuses":[{"name":string,"meaning":string}],
  "queues":[{"name":string,"meaning":string}] }`

phase('Fill')
const fill = await parallel([
  () => agent(glossaryPrompt, { label: 'glossary', phase: 'Fill' }),
  ...SCREENS.map((s) => () => agent(screenPrompt(s), { label: 'screen:' + s.key, phase: 'Fill' })),
])

phase('Fix')
const fixPrompt = (name, file, verifyFile, codeFiles) => `${SHARED}

TASK: Apply verified accuracy CORRECTIONS to the already-written manual file ${file}.
1. Read ${verifyFile} — it lists corrections (location, problem, fix, severity) found by an adversarial fact-check against the code.
2. Read the authoritative code to confirm each fix: ${codeFiles}.
3. For EVERY correction with severity high or medium (and low ones where the fix is a simple wording change), edit ${file} IN PLACE using your Edit tool to incorporate the fix. Make SURGICAL edits to the offending strings only — preserve the JSON schema and ALL other content. Keep the file valid JSON (no code fences). Do not rewrite unrelated sections.
4. After editing, verify the file still parses as JSON.
Report a one-line status of how many corrections you applied.`

await parallel([
  () => agent(
    fixPrompt('primer', `${OUT}/primer.json`, `${OUT}/verify-domain.json`,
      `${ROOT}/backend/apps/platform_core/domain/access.py, ${ROOT}/backend/apps/ledger/services.py, ${ROOT}/backend/apps/marketplace_primary/services.py, ${ROOT}/backend/apps/investor_portal/services.py`),
    { label: 'fix:primer', phase: 'Fix' }
  ),
  () => agent(
    fixPrompt('flows', `${OUT}/flows.json`, `${OUT}/verify-flows.json`,
      `${ROOT}/backend/apps/entities/models.py, ${ROOT}/backend/apps/servicing/services.py, ${ROOT}/backend/apps/ledger/services.py, ${ROOT}/backend/apps/loans/services.py`),
    { label: 'fix:flows', phase: 'Fix' }
  ),
])

return { fill: fill.map((f) => (f || 'NULL').slice(0, 120)), note: 'glossary + 3 screens written; primer/flows corrected in place' }
