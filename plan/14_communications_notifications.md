# Communications and Notifications

Status: Draft. Updated with payment, balance, FX, marketplace, servicing, recovery waterfall, document/tax, marketing-consent, SendGrid, Twilio, template, and authentication decisions on 2026-06-01.

## Purpose

Define transactional notifications, operational messaging, support communication, investor updates, arrears/default updates, and communication preferences.

## Scope

- Email notifications.
- SMS for phone confirmation only at launch.
- In-app banners and status messages for required actions.
- Future WhatsApp/push notifications.
- Transactional notification templates.
- Compliance and legal notices.
- Borrower reminders, if later supported; borrower contact is offline in v1.
- Investor marketplace and portfolio updates.
- Balance ageing, withdrawal, reinvestment, penalty, and FX notifications.
- Secondary-market transaction notifications for involved users.
- Marketing consent capture and future newsletter list handling.
- Admin task notifications.
- Support communication.
- Communication audit trail and preferences.

## Notification Types

- Account verification.
- Investor magic-link login.
- Investor sensitive-action email-code confirmation.
- Admin email-code verification.
- Phone verification.
- KYC/KYB session started/completed.
- Compliance information request.
- Investment order confirmation.
- Primary investment document package generated and sent.
- Pending order created.
- Payment received pending validation.
- Deposit credited to balance.
- Withdrawal requested/processed.
- Balance ageing reminder day 25.
- Balance ageing reminder day 46.
- Balance ageing reminder day 53.
- Balance ageing reminder day 58.
- Balance ageing reminder day 59.
- Balance day-60 penalty notice.
- Currency exchange quote accepted.
- Currency exchange completed/failed.
- Investment order validated.
- Funding status update.
- Loan closing confirmation.
- Document ready/acceptance request.
- Transfer instruction ready.
- Payment received.
- Borrower repayment received.
- Lender balance-credit notification.
- Internal distribution artifact generated for admin processing.
- Bank statement/evidence attachment reminder.
- Surplus refund initiated.
- Full excess refund required.
- Wrong payment reference follow-up.
- Partial funding close or refund decision.
- Secondary-market listing created.
- Secondary-market non-standard listing request submitted, approved, rejected, or removed.
- Secondary-market listing changed/cancelled/sold.
- Secondary-market buyer payment received.
- Secondary-market listing document package generated and sent.
- Secondary-market sale/purchase confirmation.
- Secondary-market document package generated and sent.
- Secondary-market seller proceeds credited to balance.
- Secondary-market transfer settled.
- Annual lender tax information statement available.
- Internal/admin borrower repayment reminder.
- Early repayment notification.
- Partial repayment notification.
- Late payment notice from day 5 after due date.
- Default/recovery update from day 16 after due date.
- Recovery distribution credited notification showing loan/project, recovery event date, currency, credited amount, and available recovery category split, including principal, contractual interest, default/penalty interest, recovery costs/fees where disclosed, other penalties/costs, and rounding difference.
- Admin-published public loan note for affected investors.
- Bulk investor email for material loan status, arrears, default, recovery, or write-off changes.
- Account/security alert.
- Terms update.
- Support email reference.

## Decisions

### COMMS-DEC-001: Launch Channels and Providers

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta product / operations / technology.

Decision:
Email is the only launch channel for transactional, regulatory, document, marketplace, balance, payment, servicing, recovery, and security messaging.

SMS is used only for phone confirmation at launch. Phone verification uses Twilio. Security messaging, account alerts, and other operational notices can be handled by email only in v1.

In-app notifications are limited to banners and status messages for required actions, warnings, and account states. There is no full in-app notification center in v1.

The launch email provider is SendGrid. The sender domain is TBD.

Rationale:
Email covers the launch communication surface, while Twilio is limited to phone verification to keep the first version simple.

Impacted modules:
- Integrations, APIs, and Event Architecture.
- Accounts, Authentication, and Access Control.
- Admin and Operations Portal.

Follow-ups:
Provide SendGrid account/API credentials, verified sender/domain, DNS records, and Twilio account/API credentials/Verify configuration. Decide sender domain.

### COMMS-DEC-002: Marketing Consent and Future Newsletter Lists

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta marketing / product / compliance.

Decision:
Marketing/newsletter sending is not required as an active launch workflow, but v1 must capture optional user approval for marketing communications.

The platform should create and maintain SendGrid contact lists/audiences for future newsletters, including marketing consent status and unsubscribe handling. Users do not manage notification preferences in the website in v1. Newsletter unsubscribe is handled through newsletter unsubscribe links/provider mechanics.

Transactional and regulatory emails are mandatory and are not controlled by newsletter unsubscribe preferences.

Rationale:
Capturing consent from v1 avoids rework later while keeping the active launch messaging surface transactional.

Follow-ups:
Define exact marketing consent wording, SendGrid list/audience names, consent audit fields, and unsubscribe/suppression-list synchronization behavior.

### COMMS-DEC-003: Mandatory Transactional Emails

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta legal / compliance / product.

Decision:
All transactional emails are mandatory to receive and cannot be opted out of where legally permitted.

Mandatory transactional categories include:

- Account and KYC/account-status emails.
- Investment order and primary-market investment emails.
- Document package emails.
- Balance ageing, withdrawal, forced withdrawal, penalty, and missing-IBAN emails.
- Repayment/balance-credit emails.
- Currency-exchange emails.
- Late, default, recovery, recovery distribution, write-off, and operational loan-change emails.
- Terms update emails.
- Any secondary-market transaction email where the user is buyer, seller, or otherwise directly involved.

Rationale:
These communications are tied to legal, operational, financial, or regulatory events and are part of the platform record.

Follow-ups:
Legal/compliance should confirm final mandatory notice list and wording before launch.

### COMMS-DEC-004: Failed Send Handling and Email Record Storage

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta operations / technology / security.

Decision:
Failed emails should retry automatically a few times. If delivery still fails after retry attempts, the platform creates an admin notification/task or visible admin portal notice.

Admin does not need a manual resend function at launch.

The platform stores full email content for sent emails, not only metadata/template version/data snapshot. Delivery metadata, provider message id, template version, dynamic data snapshot, recipient, timestamps, and delivery/failure status should also be stored where available.

Rationale:
Stored full content and delivery metadata create an operational and audit trail, while failed-send admin notices are enough for v1.

Follow-ups:
Define retry count, retry intervals, bounce/suppression handling, retention period for full email content, and sensitive-data minimization rules.

### COMMS-DEC-005: Public Loan Notes and Bulk Investor Emails

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta operations / servicing / product.

Decision:
For material loan status, arrears, default, recovery, write-off, or operational updates, admin can choose:

- Public loan note only.
- Bulk email only.
- Both public loan note and bulk email.

Public loan notes remain auditable and visibly distinct from internal notes.

Rationale:
Admin needs flexibility to decide the right communication method based on the operational context.

Follow-ups:
Define public-note visibility duration, affected-investor recipient rules, and whether public notes trigger optional email alerts by default.

### COMMS-DEC-006: Support Email Instead of Support Tickets

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta operations / product.

Decision:
In-platform support tickets are not required at launch. Normal email support is enough.

The site should expose a support email address, likely in a FAQ/help section and other appropriate footer/help locations.

Support also handles offline account-access recovery when an investor loses email access or transactional authentication emails repeatedly bounce. Recovery requires identity re-verification using account/KYC evidence and verified phone/account data before admin changes email/login access.

Rationale:
Email support keeps launch scope smaller while still giving users a clear support path.

Follow-ups:
Provide support email address, support mailbox/provider setup, response ownership, and any required footer/FAQ wording.

### COMMS-DEC-007: Superadmin-Editable Email Templates and Variable Scopes

Status: Accepted.
Date: 2026-05-21.
Owner: Garanta product / legal / operations / technology.

Decision:
Email templates are editable by superadmin in the platform, with versioning and audit logs. Regulated or legally sensitive template changes should support legal/compliance review evidence, even if no maker-checker approval is required at launch.

The template editor must show the variable scope available for the selected template. It should help the superadmin by listing available objects, fields, descriptions, and one or two examples of usage.

Example variable scopes:

- Account/KYC email: `user`, `kyc_session`, `support`, `platform`, `operator`.
- Investment order email: `user`, `lender`, `loan`, `borrower`, `order`, `documents`, `payment`, `platform`, `operator`.
- Installment/repayment credit email: `user`, `lender`, `loan`, `borrower`, `repayment`, `balance_credit`, `schedule`, `platform`, `operator`.
- Secondary-market transaction email: `user`, `buyer`, `seller`, `loan`, `holding`, `listing`, `secondary_market_transaction`, `fees`, `documents`, `platform`, `operator`.
- Balance ageing email: `user`, `balance_source`, `currency`, `deadlines`, `penalty`, `iban`, `platform`, `operator`.
- FX email: `user`, `fx_quote`, `source_balance`, `target_balance`, `fees`, `platform`, `operator`.

Brand/legal examples:

- `{{platform.name}}` renders the platform/brand name, initially BANXUM.
- `{{operator.legal_name}}` renders the legal operator, initially Garanta Finanzgruppe AG.
- Templates must use these variables rather than hardcoded platform or operator names.

Example usage for an installment received email:

- `Hello {{lender.display_name}}, your balance has been credited with {{balance_credit.amount}} {{balance_credit.currency}} for loan {{loan.reference}}.`
- `The payment relates to {{borrower.name}} and value date {{repayment.value_date}}.`

Example usage for a secondary-market purchase email:

- `You purchased {{secondary_market_transaction.claim_share}} of loan {{loan.reference}} for {{secondary_market_transaction.price}} {{secondary_market_transaction.currency}}.`
- `Fees applied: {{fees.total}} {{secondary_market_transaction.currency}}.`

Rationale:
Template editing needs guardrails so superadmin can safely use valid variables without breaking transactional communications.

Follow-ups:
Define the template variable registry, validation rules, preview/test-send behavior, legal review evidence fields, and template rollback process.

## Communication Channels

- Email: primary channel for documents, notices, and confirmations.
- SMS: phone confirmation only at launch through Twilio.
- In-app: banners and status messages for required actions and account states.
- Push: future mobile apps.
- Manual borrower outreach: handled offline and not structured in the platform in v1.

## Template Requirements

- Versioned templates.
- Superadmin-editable templates with audit trail.
- Localized templates if multiple languages are supported.
- Product/user-type-specific content.
- Legal/compliance approval for regulated templates.
- Balance reminder email bodies are configurable by superadmin.
- Template editor exposes available variable scopes, field descriptions, and usage examples.
- Template editor validates variables before save/publish.
- Dynamic data validation before send.
- Preview and test-send tools.

## Default Balance Reminder Email Body

Subject:
Action required: your {{platform.name}} balance must be invested or withdrawn

Day-25 body:

Hello {{investor_name}},

You have {{amount}} {{currency}} in your {{platform.name}} balance from {{received_date}}.

Swiss regulatory requirements mean {{operator.legal_name}} must avoid keeping user funds for more than 60 days. This deadline is not a term {{operator.legal_name}} can extend.

Please invest or reinvest this balance before {{deadline_date}} if it is still eligible under the balance-ageing and loan-funding-deadline rules. Otherwise, please withdraw it.

After day 30, this balance can no longer be invested or reinvested and becomes withdraw-only. Currency exchange does not reset the ageing deadline. If the balance remains after day 60, it will be subject to the configured penalty policy: {{penalty.description}}.

Regards,
{{platform.name}}
{{operator.legal_name}}

Day-46/53/58/59 subject:
Final reminder: your {{platform.name}} balance must be withdrawn

Day-46/53/58/59 body:

Hello {{investor_name}},

You have {{amount}} {{currency}} in your {{platform.name}} balance from {{received_date}}.

Swiss regulatory requirements mean {{operator.legal_name}} must avoid keeping user funds for more than 60 days. This deadline is not a term {{operator.legal_name}} can extend.

This balance can no longer be invested or reinvested. Please withdraw it before {{deadline_date}}.

If you have not already provided a usable IBAN, please add one immediately. {{operator.legal_name}} needs a usable IBAN to return funds if they are not withdrawn before the deadline.

If the balance remains after day 60, it will be subject to the configured penalty policy: {{penalty.description}}.

Regards,
{{platform.name}}
{{operator.legal_name}}

Day-60 subject:
Penalty notice: your {{platform.name}} balance has reached the 60-day limit

Day-60 body:

Hello {{investor_name}},

Your {{amount}} {{currency}} balance from {{received_date}} has reached the 60-day holding limit.

Swiss regulatory requirements mean {{operator.legal_name}} must avoid keeping user funds for more than 60 days. This deadline cannot be extended.

This balance is now subject to the configured penalty policy: {{penalty.description}}.

Please withdraw the balance immediately.

If {{operator.legal_name}} does not have a usable IBAN for you, financial actions on your account will be frozen until you provide one so we can return the due funds. You will still have read-only access to your portfolio, documents, tax information statements, notices, and messages.

Regards,
{{platform.name}}
{{operator.legal_name}}

## Controls

- Required regulatory notices cannot be opted out where legally permitted.
- Transactional emails are mandatory where legally permitted and are not controlled by newsletter unsubscribe preferences.
- Marketing communications require optional consent capture in v1 and SendGrid list/audience management for future newsletters.
- Sensitive data in notifications is minimized.
- Full sent email content is stored with delivery metadata, template version, dynamic data snapshot, recipient, timestamps, and provider message id where available.
- All material investor notices and platform-recorded borrower evidence are logged.
- Relevant monetary actions are communicated by email at launch.
- Any secondary-market transaction involving a user must generate relevant transactional email.
- Lender balance-credit emails state the credited amount and payment context, but internal distribution artifacts are not sent as files by default.
- Balance ageing reminders must be sent on days 25, 46, 53, 58, 59, and 60 for remaining unconsumed balance source entries.
- Reminder emails must state that the regulatory/compliance requirement to avoid holding user funds beyond 60 days cannot be extended.
- Final reminders must state that Garanta Finanzgruppe AG needs a usable IBAN to return funds if the investor does not withdraw before the deadline.
- Day-60 notifications must state that missing usable IBAN causes penalty mode and freezes financial actions until a usable IBAN is declared, while read-only access to portfolio, documents, tax information statements, notices, and messages remains available.
- Primary investment and secondary-market purchase documents are generated at transaction time and sent by email.
- Launch document communications are English-only.
- Arrears/default investor updates are event-driven: admin sends a bulk email and/or publishes a public loan note when something material changes.
- Public loan notes must be visibly distinct from internal notes and must be auditable.
- Failed sends retry automatically a few times and then create an admin notification/task or visible admin portal notice.
- Manual resend is not required at launch.
- Regulated communication template changes require legal/compliance review evidence where applicable; template editing/publishing is superadmin-owned.

## Dependencies

- Investor Portal.
- Borrower and Entity Records.
- Admin and Operations Portal.
- Documents, Contracting, and E-Signature.
- Loan Servicing and Repayments.

## Q/A Backlog

1. Partly answered by DOC-DEC-002: launch documents, document emails, and default reminder emails are English-only.
2. Answered by COMMS-DEC-001: launch channel is email only, with SMS through Twilio for phone confirmation only and in-app banners/status messages for required actions.
3. Answered by COMMS-DEC-002: marketing sending is future scope, but v1 captures optional marketing consent and maintains SendGrid lists/audiences for future newsletters.
4. Answered by COMMS-DEC-003: all transactional emails are mandatory where legally permitted, including account/KYC, investment, document, balance, repayment, withdrawal/FX, late/default/recovery, terms, and user-involved secondary-market transaction emails.
5. Partly answered by RISK-DEC-004: arrears/default investor updates may be sent by bulk email and/or public loan note when something material changes; borrower outreach remains offline and is not structured in v1.
6. Answered for planning: sender domain is TBD and tracked in `admin_todo_accounts.md`.
7. Answered by COMMS-DEC-001: SendGrid is the launch email provider; Twilio is used for phone verification.
8. Answered by COMMS-DEC-006: no support tickets at launch; normal email support is enough and support email should be exposed on the site/FAQ.
9. Answered by COMMS-DEC-004: failed emails retry a few times, then create an admin notification/task; full sent email content is stored.
10. Answered by COMMS-DEC-005: admin can choose public loan note only, bulk email only, or both.
11. Answered by COMMS-DEC-007: email templates are superadmin-editable with variable scopes, examples, validation, versioning, and audit logs.
12. Updated by ACC-DEC-001/ACC-DEC-002/ACC-DEC-008: investor magic-link login emails, investor sensitive-action email-code emails, and admin email-code emails are transactional authentication messages.
