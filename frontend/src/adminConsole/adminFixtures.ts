import type {
  AdminDashboardQueueItem,
  AdminDashboardQueues,
  AdminOperationsDashboard,
  AdminTask,
  AdminTaskEvent,
  AuditEvent,
  BorrowerEntity,
  DocumentTemplateVersion,
  KycAdminCase,
  Loan
} from "../api/generated/banxumApi";

function queueItem(
  overrides: Partial<AdminDashboardQueueItem> & Pick<AdminDashboardQueueItem, "kind" | "id" | "title" | "status">
): AdminDashboardQueueItem {
  return {
    priority: "normal",
    due_at: null,
    due_date: null,
    currency: "CHF",
    amount_minor: null,
    object_type: overrides.kind,
    object_id: overrides.id,
    metadata: {},
    ...overrides
  };
}

const emptyQueues: AdminDashboardQueues = {
  admin_tasks: [],
  kyc_reviews: [],
  bank_operations_pending: [],
  withdrawals_requested: [],
  forced_withdrawals_requested: [],
  balance_ageing_actions: [],
  funding_loans: [],
  servicing_due: [],
  loan_risk: [],
  secondary_listing_approvals: [],
  fx_settlement_deltas: [],
  failed_emails: [],
  reconciliation_breaks: []
};

export const adminDashboardFixture: AdminOperationsDashboard = {
  as_of: "2026-06-05T09:45:00+02:00",
  as_of_date: "2026-06-05",
  due_window_days: 7,
  queue_limit: 12,
  summary: {
    open_items: 34,
    high_priority_items: 7,
    failed_email_count: 2,
    reconciliation_break_count: 3,
    pending_withdrawal_count: 5,
    kyc_manual_review_count: 4
  },
  currency_summaries: [
    {
      currency: "CHF",
      available_balance_minor: 98422000,
      investable_available_minor: 51450000,
      withdraw_only_available_minor: 23900000,
      overdue_available_minor: 8710000,
      frozen_available_minor: 3150000,
      penalty_mode_available_minor: 2700000,
      pending_withdrawal_minor: 12150000,
      forced_withdrawal_minor: 3150000,
      pending_bank_operation_minor: 50600000,
      fx_unsettled_sold_minor: 44000000,
      fx_unsettled_bought_minor: 0,
      fx_unsettled_fee_minor: 61000
    },
    {
      currency: "EUR",
      available_balance_minor: 64180000,
      investable_available_minor: 38940000,
      withdraw_only_available_minor: 14500000,
      overdue_available_minor: 4700000,
      frozen_available_minor: 2040000,
      penalty_mode_available_minor: 0,
      pending_withdrawal_minor: 6400000,
      forced_withdrawal_minor: 2040000,
      pending_bank_operation_minor: 27800000,
      fx_unsettled_sold_minor: 0,
      fx_unsettled_bought_minor: 46190000,
      fx_unsettled_fee_minor: 47500
    }
  ],
  queues: {
    ...emptyQueues,
    admin_tasks: [
      queueItem({
        kind: "admin_task",
        id: "task-kyc-refresh-001",
        title: "Review updated KYC evidence retention checklist",
        status: "open",
        priority: "high",
        due_at: "2026-06-05T13:00:00+02:00",
        object_type: "kyc_case",
        object_id: "kyc-case-483",
        metadata: { owner: "Compliance", sla_hours_remaining: 3 }
      }),
      queueItem({
        kind: "admin_task",
        id: "task-bank-ref-002",
        title: "Resolve unmatched CHF lender deposit reference",
        status: "open",
        priority: "urgent",
        due_at: "2026-06-05T11:30:00+02:00",
        amount_minor: 2500000,
        object_type: "bank_operation",
        object_id: "bank-op-774",
        metadata: { sender_name: "A. Keller", reference_seen: "BX-81??" }
      })
    ],
    kyc_reviews: [
      queueItem({
        kind: "kyc_review",
        id: "kyc-case-483",
        title: "PEP flag requires Garanta AML officer decision",
        status: "manual_review",
        priority: "urgent",
        due_at: "2026-06-05T12:00:00+02:00",
        object_type: "kyc_case",
        object_id: "kyc-case-483",
        metadata: { provider: "Didit", flags: ["pep_hit"], country: "CH" }
      }),
      queueItem({
        kind: "kyc_review",
        id: "kyc-case-501",
        title: "Adverse media flag awaiting compliance note",
        status: "manual_review",
        priority: "high",
        due_at: "2026-06-06T10:00:00+02:00",
        object_type: "kyc_case",
        object_id: "kyc-case-501",
        metadata: { provider: "Didit", flags: ["adverse_media_hit"], country: "DE" }
      })
    ],
    bank_operations_pending: [
      queueItem({
        kind: "bank_operation",
        id: "bank-op-774",
        title: "Unmatched lender deposit needs reference review",
        status: "pending_review",
        priority: "urgent",
        due_at: "2026-06-05T10:30:00+02:00",
        currency: "CHF",
        amount_minor: 2500000,
        object_type: "bank_operation",
        object_id: "bank-op-774",
        metadata: { value_date: "2026-06-05", sender_iban: "CH93 **** 0173" }
      })
    ],
    withdrawals_requested: [
      queueItem({
        kind: "withdrawal",
        id: "wd-1002",
        title: "Investor withdrawal awaiting bank execution",
        status: "requested",
        priority: "normal",
        due_date: "2026-06-06",
        currency: "EUR",
        amount_minor: 6400000,
        object_type: "withdrawal_request",
        object_id: "wd-1002",
        metadata: { iban_verified: true, investor_reference: "INV-3021" }
      })
    ],
    forced_withdrawals_requested: [
      queueItem({
        kind: "forced_withdrawal",
        id: "wd-forced-301",
        title: "Day-60 forced withdrawal generated from ageing scan",
        status: "requested",
        priority: "high",
        due_date: "2026-06-05",
        currency: "CHF",
        amount_minor: 3150000,
        object_type: "withdrawal_request",
        object_id: "wd-forced-301",
        metadata: { scan_date: "2026-06-05", reason: "usable_iban_available" }
      })
    ],
    balance_ageing_actions: [
      queueItem({
        kind: "balance_ageing",
        id: "lot-883",
        title: "Lot enters withdraw-only window today",
        status: "withdraw_only",
        priority: "normal",
        due_date: "2026-06-05",
        currency: "CHF",
        amount_minor: 9800000,
        object_type: "investor_balance_lot",
        object_id: "lot-883",
        metadata: { investor_reference: "INV-2204", investment_deadline: "2026-06-05" }
      }),
      queueItem({
        kind: "balance_ageing",
        id: "lot-884",
        title: "No verified IBAN for day-60 lot",
        status: "penalty_mode",
        priority: "urgent",
        due_date: "2026-06-05",
        currency: "CHF",
        amount_minor: 2700000,
        object_type: "investor_balance_lot",
        object_id: "lot-884",
        metadata: { investor_reference: "INV-1458", action: "freeze_until_iban" }
      })
    ],
    funding_loans: [
      queueItem({
        kind: "funding_loan",
        id: "loan-zug-park-ii",
        title: "Zug Park II closes in 2 days with committed funds",
        status: "published",
        priority: "high",
        due_date: "2026-06-07",
        currency: "CHF",
        amount_minor: 84000000,
        object_type: "loan",
        object_id: "loan-zug-park-ii",
        metadata: { committed_percent: 92, pending_orders: 6 }
      })
    ],
    servicing_due: [
      queueItem({
        kind: "servicing_due",
        id: "installment-771",
        title: "Borrower repayment due in servicing window",
        status: "due",
        priority: "normal",
        due_date: "2026-06-08",
        currency: "CHF",
        amount_minor: 1845000,
        object_type: "loan_installment",
        object_id: "installment-771",
        metadata: { loan_reference: "L-2026-018", borrower: "Helvetic Wohnbau AG" }
      })
    ],
    loan_risk: [
      queueItem({
        kind: "loan_risk",
        id: "loan-basel-riverside",
        title: "Loan moved to late status, public note recommended",
        status: "late",
        priority: "high",
        due_date: "2026-06-05",
        currency: "CHF",
        amount_minor: 42000000,
        object_type: "loan",
        object_id: "loan-basel-riverside",
        metadata: { days_past_due: 7, last_payment_date: "2026-05-12" }
      }),
      queueItem({
        kind: "loan_risk",
        id: "loan-ticino-recovery",
        title: "Defaulted loan recovery note is stale",
        status: "defaulted",
        priority: "urgent",
        due_date: "2026-06-05",
        currency: "EUR",
        amount_minor: 12900000,
        object_type: "loan",
        object_id: "loan-ticino-recovery",
        metadata: { days_past_due: 24, public_note_age_days: 12 }
      })
    ],
    secondary_listing_approvals: [
      queueItem({
        kind: "secondary_listing",
        id: "sm-listing-711",
        title: "Non-standard secondary listing awaiting risk disclosure approval",
        status: "approval_requested",
        priority: "high",
        due_at: "2026-06-05T15:00:00+02:00",
        currency: "CHF",
        amount_minor: 1120000,
        object_type: "secondary_listing",
        object_id: "sm-listing-711",
        metadata: { loan_status: "late", days_past_due: 7 }
      })
    ],
    fx_settlement_deltas: [
      queueItem({
        kind: "fx_settlement",
        id: "fx-delta-2026-06-05",
        title: "CHF/EUR external FX settlement delta to declare",
        status: "unsettled",
        priority: "high",
        due_date: "2026-06-05",
        currency: "CHF",
        amount_minor: 44000000,
        object_type: "fx_settlement_window",
        object_id: "2026-06-05:CHF-EUR",
        metadata: { pair: "CHF/EUR", expected_sold: "CHF 440,000.00", expected_bought: "EUR 461,900.00" }
      })
    ],
    failed_emails: [
      queueItem({
        kind: "failed_email",
        id: "outbox-771",
        title: "Installment notification email dead-lettered",
        status: "dead_letter",
        priority: "normal",
        due_at: "2026-06-05T09:20:00+02:00",
        object_type: "outbox_message",
        object_id: "outbox-771",
        metadata: { topic: "email.installment_received", attempts: 8 }
      })
    ],
    reconciliation_breaks: [
      queueItem({
        kind: "reconciliation_break",
        id: "recon-chf-2026-06-05",
        title: "CHF reconciliation difference and sign anomaly",
        status: "break",
        priority: "urgent",
        due_date: "2026-06-05",
        currency: "CHF",
        amount_minor: 72000,
        object_type: "reconciliation_snapshot",
        object_id: "recon-chf-2026-06-05",
        metadata: {
          reconciliation_difference_minor: 72000,
          account_sign_anomalies: 1,
          investor_balance_integrity_breaks: 0
        }
      }),
      queueItem({
        kind: "reconciliation_break",
        id: "recon-eur-2026-06-05",
        title: "EUR investor liability mismatch in one account",
        status: "integrity_break",
        priority: "urgent",
        due_date: "2026-06-05",
        currency: "EUR",
        amount_minor: 0,
        object_type: "reconciliation_snapshot",
        object_id: "recon-eur-2026-06-05",
        metadata: {
          reconciliation_difference_minor: 0,
          account_sign_anomalies: 0,
          investor_balance_integrity_breaks: 1
        }
      })
    ]
  }
};

export const adminTasksFixture: AdminTask[] = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    task_type: "payment_reconciliation",
    title: "Resolve unmatched CHF lender deposit reference",
    priority: "urgent",
    status: "open",
    assigned_admin_id: null,
    created_by_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    due_at: "2026-06-05T11:30:00+02:00",
    notes:
      "Incoming CHF 25,000.00 deposit contains an incomplete lender reference. Check sender name, sender IBAN and bank description before crediting any investor balance.",
    related_object_type: "bank_operation",
    related_object_id: "bank-op-774",
    completed_at: null,
    completion_note: "",
    is_terminal: false,
    created_at: "2026-06-05T09:15:00+02:00",
    updated_at: "2026-06-05T09:15:00+02:00"
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    task_type: "kyc_manual_review",
    title: "PEP flag requires Garanta AML officer decision",
    priority: "urgent",
    status: "in_progress",
    assigned_admin_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    created_by_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    due_at: "2026-06-05T12:00:00+02:00",
    notes:
      "Didit routed this person to manual review. Review provider report, local evidence metadata and AML officer note before approving or declining.",
    related_object_type: "kyc_case",
    related_object_id: "kyc-case-483",
    completed_at: null,
    completion_note: "",
    is_terminal: false,
    created_at: "2026-06-05T08:42:00+02:00",
    updated_at: "2026-06-05T09:05:00+02:00"
  },
  {
    id: "33333333-3333-4333-8333-333333333333",
    task_type: "fx_settlement",
    title: "Declare CHF/EUR external FX settlement",
    priority: "high",
    status: "waiting",
    assigned_admin_id: null,
    created_by_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    due_at: "2026-06-05T17:00:00+02:00",
    notes:
      "Use the end-of-day bank report to declare the actual CHF sold and EUR bought. The platform will leave any realized surplus/deficit in FX clearing for reporting.",
    related_object_type: "fx_settlement_window",
    related_object_id: "2026-06-05:CHF-EUR",
    completed_at: null,
    completion_note: "",
    is_terminal: false,
    created_at: "2026-06-05T10:00:00+02:00",
    updated_at: "2026-06-05T10:00:00+02:00"
  },
  {
    id: "44444444-4444-4444-8444-444444444444",
    task_type: "document_review",
    title: "Review revised primary-market risk acknowledgement template",
    priority: "normal",
    status: "open",
    assigned_admin_id: null,
    created_by_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    due_at: "2026-06-07T15:00:00+02:00",
    notes:
      "Compare template variables and checkbox labels with the latest advisor text before publication.",
    related_object_type: "document_template",
    related_object_id: "primary-market-investment:v3",
    completed_at: null,
    completion_note: "",
    is_terminal: false,
    created_at: "2026-06-05T10:30:00+02:00",
    updated_at: "2026-06-05T10:30:00+02:00"
  },
  {
    id: "55555555-5555-4555-8555-555555555555",
    task_type: "email_delivery_failure",
    title: "Dead-lettered installment notification",
    priority: "normal",
    status: "resolved",
    assigned_admin_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    created_by_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    due_at: "2026-06-05T10:00:00+02:00",
    notes: "SendGrid rejected an installment email after retry exhaustion.",
    related_object_type: "outbox_message",
    related_object_id: "outbox-771",
    completed_at: "2026-06-05T10:21:00+02:00",
    completion_note: "Delivery issue recorded. Investor notification queued for manual support follow-up.",
    is_terminal: true,
    created_at: "2026-06-05T09:20:00+02:00",
    updated_at: "2026-06-05T10:21:00+02:00"
  }
];

export const adminTaskEventsFixture: Record<string, AdminTaskEvent[]> = {
  "11111111-1111-4111-8111-111111111111": [
    {
      id: "task-event-111-created",
      task_id: "11111111-1111-4111-8111-111111111111",
      event_type: "created",
      actor_user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      actor_account_type: "admin",
      previous_status: "",
      new_status: "open",
      note: "Task created from pending bank operation queue.",
      metadata: { source: "dashboard", related_object_type: "bank_operation" },
      occurred_at: "2026-06-05T09:15:00+02:00"
    }
  ],
  "22222222-2222-4222-8222-222222222222": [
    {
      id: "task-event-222-created",
      task_id: "22222222-2222-4222-8222-222222222222",
      event_type: "created",
      actor_user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      actor_account_type: "admin",
      previous_status: "",
      new_status: "open",
      note: "Manual review task opened from Didit webhook status mapping.",
      metadata: { provider: "Didit", flags: ["pep_hit"] },
      occurred_at: "2026-06-05T08:42:00+02:00"
    },
    {
      id: "task-event-222-status",
      task_id: "22222222-2222-4222-8222-222222222222",
      event_type: "status_changed",
      actor_user_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      actor_account_type: "admin",
      previous_status: "open",
      new_status: "in_progress",
      note: "Compliance review started.",
      metadata: {},
      occurred_at: "2026-06-05T09:05:00+02:00"
    }
  ],
  "33333333-3333-4333-8333-333333333333": [
    {
      id: "task-event-333-created",
      task_id: "33333333-3333-4333-8333-333333333333",
      event_type: "created",
      actor_user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      actor_account_type: "admin",
      previous_status: "",
      new_status: "waiting",
      note: "Waiting for end-of-day bank FX execution report.",
      metadata: { pair: "CHF/EUR" },
      occurred_at: "2026-06-05T10:00:00+02:00"
    }
  ],
  "44444444-4444-4444-8444-444444444444": [
    {
      id: "task-event-444-created",
      task_id: "44444444-4444-4444-8444-444444444444",
      event_type: "created",
      actor_user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      actor_account_type: "superadmin",
      previous_status: "",
      new_status: "open",
      note: "Document review requested before publication.",
      metadata: { template_category: "primary_market_investment" },
      occurred_at: "2026-06-05T10:30:00+02:00"
    }
  ],
  "55555555-5555-4555-8555-555555555555": [
    {
      id: "task-event-555-created",
      task_id: "55555555-5555-4555-8555-555555555555",
      event_type: "created",
      actor_user_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      actor_account_type: "admin",
      previous_status: "",
      new_status: "open",
      note: "Task created from dead-lettered email outbox message.",
      metadata: { topic: "email.installment_received", attempts: 8 },
      occurred_at: "2026-06-05T09:20:00+02:00"
    },
    {
      id: "task-event-555-resolved",
      task_id: "55555555-5555-4555-8555-555555555555",
      event_type: "status_changed",
      actor_user_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      actor_account_type: "admin",
      previous_status: "open",
      new_status: "resolved",
      note: "Delivery issue recorded. Investor notification queued for manual support follow-up.",
      metadata: {},
      occurred_at: "2026-06-05T10:21:00+02:00"
    }
  ]
};

export const kycManualReviewFixture: KycAdminCase[] = [
  {
    id: "kyc-case-483",
    subject_type: "natural_person",
    subject_reference: "INV-2048",
    user_id: "00000000-0000-4000-8000-000000002048",
    provider: "Didit",
    provider_environment: "sandbox",
    workflow_id: "didit-workflow-ch-person",
    status: "pep_hit",
    manual_review_required: true,
    blocking_reason: "PEP match requires AML officer decision before account activation.",
    risk_classification: "high",
    detected_flags: ["pep_hit", "high_risk"],
    provider_session_id: "didit-sess-483",
    provider_verification_id: "didit-ver-483",
    provider_report_id: "didit-report-483",
    aml_screening_id: "didit-aml-483",
    provider_subject_id: "didit-subject-483",
    decision_at: null,
    created_at: "2026-06-05T08:42:00+02:00",
    updated_at: "2026-06-05T09:05:00+02:00"
  },
  {
    id: "kyc-case-501",
    subject_type: "natural_person",
    subject_reference: "INV-2177",
    user_id: "00000000-0000-4000-8000-000000002177",
    provider: "Didit",
    provider_environment: "sandbox",
    workflow_id: "didit-workflow-eu-person",
    status: "adverse_media_hit",
    manual_review_required: true,
    blocking_reason: "Adverse media match routed to manual review.",
    risk_classification: "medium",
    detected_flags: ["adverse_media_hit"],
    provider_session_id: "didit-sess-501",
    provider_verification_id: "didit-ver-501",
    provider_report_id: "didit-report-501",
    aml_screening_id: "didit-aml-501",
    provider_subject_id: "didit-subject-501",
    decision_at: null,
    created_at: "2026-06-05T09:20:00+02:00",
    updated_at: "2026-06-05T09:55:00+02:00"
  }
];

export const borrowersFixture: BorrowerEntity[] = [
  {
    id: "borrower-helvetic-wohnbau",
    legal_name: "Helvetic Wohnbau AG",
    year_founded: 2011,
    entity_type: "swiss_company",
    kyb_status: "approved",
    compliance_hold: false,
    can_transact: true,
    country: "CH",
    registration_number: "CHE-123.456.789",
    registered_address: "Zugerstrasse 18, 6300 Zug",
    operating_address: "Zugerstrasse 18, 6300 Zug",
    industry_activity: "Residential real-estate development",
    ownership_structure: "Privately held Swiss company",
    beneficial_owners: [{ name: "Redacted in preview", share_percent: 100 }],
    directors_officers: [{ name: "Preview Director", role: "Director" }],
    authorized_signatories: [{ name: "Preview Signatory", authority: "single signature" }],
    bank_account_details: { iban_status: "verified_off_platform" },
    financials_currency: "CHF",
    assets_minor: 1820000000,
    liabilities_minor: 960000000,
    revenue_last_year_minor: 440000000,
    profit_last_year_minor: 31000000,
    created_by_admin_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    updated_by_admin_id: null,
    created_at: "2026-06-01T10:00:00+02:00",
    updated_at: "2026-06-04T16:20:00+02:00"
  },
  {
    id: "borrower-ticino-projects",
    legal_name: "Ticino Projects SA",
    year_founded: 2018,
    entity_type: "special_purpose_vehicle",
    kyb_status: "manual_review",
    compliance_hold: true,
    can_transact: false,
    country: "CH",
    registration_number: "CHE-987.654.321",
    registered_address: "Via Cantonale 7, 6900 Lugano",
    operating_address: "",
    industry_activity: "Real-estate backed project finance",
    ownership_structure: "",
    beneficial_owners: [],
    directors_officers: [],
    authorized_signatories: [],
    bank_account_details: {},
    financials_currency: "CHF",
    assets_minor: null,
    liabilities_minor: null,
    revenue_last_year_minor: null,
    profit_last_year_minor: null,
    created_by_admin_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    updated_by_admin_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    created_at: "2026-06-02T11:40:00+02:00",
    updated_at: "2026-06-05T08:30:00+02:00"
  }
];

export const loansFixture: Loan[] = [
  {
    id: "loan-zug-park-ii",
    borrower_id: "borrower-helvetic-wohnbau",
    status: "published",
    title: "Zug Park II bridge facility",
    investor_summary: "Real-estate backed bridge facility secured by a first-ranking pledge over the Zug Park II project.",
    purpose: "bridge_financing",
    purpose_description: "Bridge financing while the borrower completes senior bank refinancing.",
    principal_minor: 120000000,
    currency: "CHF",
    interest_rate_bps: 950,
    term_months: 12,
    repayment_type: "equal_installments",
    interest_only_months: 0,
    funding_deadline: "2026-06-30",
    first_payment_date: "2026-07-31",
    collateral_type: "real_estate",
    collateral_value_minor: 184000000,
    collateral_description: "Independent valuation of the pledged real-estate collateral.",
    risk_rating: "BBB",
    borrower_success_fee_bps: 250,
    lender_payment_fee_minor: 0,
    default_penalty_interest_bps: 0,
    recovery_fee_bps: 0,
    recovery_waterfall_version: "v1",
    schedule_version: 1,
    total_scheduled_principal_minor: 120000000,
    total_scheduled_interest_minor: 6264000,
    committed_principal_minor: 84000000,
    ltv_bps: 6522,
    ltv_warnings: [],
    published_at: "2026-06-03T10:30:00+02:00",
    created_by_admin_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    updated_by_admin_id: null,
    created_at: "2026-06-01T15:00:00+02:00",
    updated_at: "2026-06-03T10:30:00+02:00"
  },
  {
    id: "loan-basel-riverside",
    borrower_id: "borrower-helvetic-wohnbau",
    status: "late",
    title: "Basel Riverside refurbishment",
    investor_summary: "Refurbishment facility backed by mixed real-estate collateral.",
    purpose: "development",
    purpose_description: "Refurbishment and working-capital bridge for a residential development.",
    principal_minor: 42000000,
    currency: "CHF",
    interest_rate_bps: 1025,
    term_months: 10,
    repayment_type: "bullet_periodic_interest",
    interest_only_months: 0,
    funding_deadline: "2026-04-15",
    first_payment_date: "2026-05-15",
    collateral_type: "mixed_collateral",
    collateral_value_minor: 69000000,
    collateral_description: "Real-estate pledge plus corporate guarantee.",
    risk_rating: "BB+",
    borrower_success_fee_bps: 300,
    lender_payment_fee_minor: 0,
    default_penalty_interest_bps: 0,
    recovery_fee_bps: 0,
    recovery_waterfall_version: "v1",
    schedule_version: 1,
    total_scheduled_principal_minor: 42000000,
    total_scheduled_interest_minor: 3587500,
    committed_principal_minor: 42000000,
    ltv_bps: 6087,
    ltv_warnings: [],
    published_at: "2026-03-20T09:00:00+01:00",
    created_by_admin_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    updated_by_admin_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    created_at: "2026-03-18T12:00:00+01:00",
    updated_at: "2026-06-05T09:00:00+02:00"
  }
];

export const documentVersionsFixture: DocumentTemplateVersion[] = [
  {
    id: "doc-version-registration-v1",
    template: {
      id: "doc-template-registration",
      category: "registration",
      template_key: "registration-default",
      language: "en",
      name: "Registration terms",
      description: "Registration-time platform terms and privacy acknowledgement.",
      current_published_version_id: "doc-version-registration-v1",
      created_by_superadmin_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      updated_by_superadmin_id: null,
      created_at: "2026-06-01T09:30:00+02:00",
      updated_at: "2026-06-01T10:00:00+02:00"
    },
    version_number: 1,
    status: "published",
    title: "BANXUM Registration Terms",
    body: "Placeholder registration terms for preview. Advisor-approved text will be uploaded before launch.",
    checkbox_labels: ["I accept the BANXUM registration terms.", "I confirm the information I provide is accurate."],
    variable_schema: { variables: ["platform_name", "operator_name", "support_email"] },
    content_hash: "sha256-preview-registration",
    created_by_superadmin_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    source_version_id: null,
    published_at: "2026-06-01T10:00:00+02:00",
    legal_review_reference: "preview-legal-ref",
    metadata: { preview: true },
    created_at: "2026-06-01T09:30:00+02:00",
    updated_at: "2026-06-01T10:00:00+02:00"
  },
  {
    id: "doc-version-primary-v3",
    template: {
      id: "doc-template-primary",
      category: "primary_market_investment",
      template_key: "primary-market-default",
      language: "en",
      name: "Primary-market investment acknowledgement",
      description: "Clickwrap text for primary investment order submission.",
      current_published_version_id: "doc-version-primary-v2",
      created_by_superadmin_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      updated_by_superadmin_id: null,
      created_at: "2026-05-01T10:00:00+02:00",
      updated_at: "2026-06-05T10:30:00+02:00"
    },
    version_number: 3,
    status: "draft",
    title: "Primary-Market Investment Acknowledgement",
    body: "Draft placeholder risk acknowledgement for primary-market investments.",
    checkbox_labels: ["I understand this is not a bank deposit.", "I accept the loan assignment terms."],
    variable_schema: { variables: ["loan.title", "loan.currency", "loan.principal_minor"] },
    content_hash: "sha256-preview-primary-v3",
    created_by_superadmin_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    source_version_id: "doc-version-primary-v2",
    published_at: null,
    legal_review_reference: "",
    metadata: { preview: true },
    created_at: "2026-06-05T10:30:00+02:00",
    updated_at: "2026-06-05T10:30:00+02:00"
  }
];

export const auditEventsFixture: AuditEvent[] = [
  {
    id: "audit-001",
    occurred_at: "2026-06-05T10:21:00+02:00",
    actor_type: "admin",
    actor_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    action: "admin_task.status_changed",
    target_type: "admin_task",
    target_id: "55555555-5555-4555-8555-555555555555",
    request_id: "req-preview-001",
    metadata: { previous_status: "open", new_status: "resolved" }
  },
  {
    id: "audit-002",
    occurred_at: "2026-06-05T09:05:00+02:00",
    actor_type: "admin",
    actor_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    action: "kyc.manual_review_started",
    target_type: "kyc_case",
    target_id: "kyc-case-483",
    request_id: "req-preview-002",
    metadata: { provider: "Didit", flags: ["pep_hit"] }
  }
];

export const adminFormDefaults = {
  investorUserId: "00000000-0000-4000-8000-000000002048",
  borrowerId: "borrower-helvetic-wohnbau",
  loanId: "loan-zug-park-ii",
  kycCaseId: "kyc-case-483",
  withdrawalId: "wd-1002",
  secondaryListingId: "sm-listing-711",
  collectionAccount: "BANXUM-CHF-COLLECTION",
  payoutIban: "CH9300762011623852957",
  payoutAccountName: "Preview Investor",
  borrowerName: "Helvetic Wohnbau AG",
  borrowerPayeeAccount: "CH3900762011623852957",
  borrowerLegalName: "Preview Borrower AG",
  adminEmail: "ops-admin@banxum.local",
  adminFullName: "Operations Admin"
};
