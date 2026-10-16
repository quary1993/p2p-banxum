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
- Smart-Invest newly published opportunity match.
- Primary investment document package generated and sent.
- Pending order created.
- Payment received pending validation.
- Deposit credited to balance.
- Withdrawal requested/processed.
- Balance ageing reminder day 25.
- Balance ageing reminder day 46.
- Balance ageing reminder day 53.
- Balance ageing reminders day 56 and 57 (2026-10-16, replacing day 59).
- Balance ageing last-day reminder day 58: tomorrow the money goes back to the bank, or without a usable IBAN "add a bank account today".
- Without a usable IBAN only: day-59 urgent notice (add a verified bank account so we can return your money) and day-60 notice that penalty mode starts tomorrow (2026-10-16, replacing the day-60 penalty notice).
- Automatic return started (forced return, from day 59).
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
- Recovery distribution credited notification showing loan/project, recovery event date, currency, credited amount, and the available recovery category split in waterfall order: disclosed recovery costs/fees, default/penalty interest and other penalties, contractual interest, principal, and rounding difference.
- Admin-published public loan note for affected investors.
- Bulk investor email for material loan status, arrears, default, recovery, or final-resolution changes.
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

The investor portal includes an in-app notification center backed by transactional email outbox and delivery evidence. Balance-ageing reminders belong in that notification center rather than as a persistent dashboard warning. Blocking account states, such as a day-60 freeze caused by a missing usable payout IBAN, remain visible as contextual banners because they directly change which actions are available.

Notification read state (QA 2026-10): each notice is unread until the investor opens it or marks it read; "mark all as read" covers the listed notices. Read state is an append-only receipt per investor and outbox message (`communications.NotificationReadReceipt`), so a notice stays read after it moves from queued to delivered. Each notice carries a typed navigation target (loan, holding, portfolio, balances, secondary market, FX, or none) derived from its own message metadata; the portal opens that page and still authorizes it as usual.

Notification centre content (audit 2026-10, A-46): sign-in link and confirmation-code emails (investor and admin) are not notices. The centre does not list them and does not count them as unread, so they cannot push real notices off the page. Each notice shows a short human label (for example "Deposit" or "Withdrawal"), never the raw topic key. The investor API does not return delivery internals (provider ids, attempts, errors).

The launch email provider is Twilio Email API. The sender domain for the current private-test deployment is `nxnarena.com`; the final production domain remains a go-live configuration decision.

Rationale:
Email covers the launch communication surface through Twilio Email API, while Twilio Verify remains the separate phone-verification channel.

Impacted modules:
- Integrations, APIs, and Event Architecture.
- Accounts, Authentication, and Access Control.
- Admin and Operations Portal.

Follow-ups:
Provide separate Twilio Email API-key credentials, verified sender/domain and DNS records, plus Twilio Verify credentials/service configuration. Decide the final production sender domain.

Implementation status:
Twilio Email API, legacy SendGrid and Twilio Verify are implemented behind provider settings and bounded provider calls. Non-local deploy checks reject mock/local email delivery and validate the credentials required by the selected provider. Twilio Email uses Basic authentication with a dedicated API-key SID/secret, while Twilio Verify retains separate credentials and preserves BANXUM's local user ownership, expiry, attempts, audit, and verified-state controls. Business-event email outbox mapping is implemented for the events listed under Implementation Status below. Final sender-domain validation, bounce/suppression integration and advisor-approved wording/templates remain launch setup tasks.

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

Updated 2026-10-15: the public site "New projects by email" newsletter is live as its own double opt-in list, independent of the account consent captured here; see COMMS-DEC-009.

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
- Late, default, recovery, recovery distribution, final-resolution, and operational loan-change emails.
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
For material loan status, arrears, default, recovery, final-resolution, or operational updates, admin can choose:

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

### COMMS-DEC-008: Smart-Invest Match Alerts Are Transactional And First-Publication-Only

Status: Accepted.
Date: 2026-08-06.
Owner: Garanta product / compliance / technology.

Decision:
When a loan first becomes public and investable, the platform evaluates every active Smart-Invest rule owned by an investor who still has financial access. A matching investor receives one transactional email and one portal notification for that investor/loan pair, regardless of marketing consent.

Activating or changing a rule does not backfill alerts for opportunities that were already open. Ordinary changes to an open loan do not resend the match alert. The rule and alert contain discovery information only: they do not reserve a balance, create an order, buy a claim, rank credit quality, or invest automatically.

The Smart-Invest setup wizard contains collateral, currency, optional minimum yield, optional maximum term, and review. It intentionally has no repayment/reinvestment preference and no originator-concentration step.

Rationale:
This gives investors timely notice without presenting Smart-Invest as discretionary management, suitability advice, or an automated investment mandate. Per-investor/per-loan deduplication prevents repeated promotional pressure and creates a clear notification audit boundary.

Follow-ups:
Final legal/compliance review should approve the match-email wording and confirm whether later material loan changes require a separate event-driven notice rather than another Smart-Invest match alert.

### COMMS-DEC-009: Public Site Newsletter and Public Forms

Status: Accepted.
Date: 2026-10-15.
Owner: Garanta product / marketing / compliance / technology.

Decision:
The public site has three forms (For companies, For loan originators, Contact) and a "New projects by email" newsletter. All of it lives in `communications` and uses the normal outbox, so retries, delivery records and evidence work as for every other email.

Public forms (`POST /api/v1/public/enquiries/`, anonymous, no session or CSRF):

- An accepted form is stored as `PublicEnquiry` (kind, reference, cleaned field values, sender email, IP as a keyed SHA-256 hash with a pepper derived from `SECRET_KEY`, user agent cut to 255 characters, delivery status) and sends ONE email (`email.public_enquiry`) to `PUBLIC_ENQUIRY_EMAIL` (default `hq@banxum.com`). Nothing is ever sent to the person who filled the form.
- References are `APP` (company), `PAR` (loan originator) or `MSG` (contact), the Europe/Zurich year and a 4-digit sequence, for example `APP-2026-0143`. The number comes from one counter row per prefix and year, raised with a single row-locking UPDATE inside the submit transaction, so two submissions never share a number; deleting old enquiries never reuses one.
- The subject is fixed text plus the reference only ("New company application APP-2026-0143", "New loan originator request PAR-…", "New contact message MSG-…"). The body uses the shared BANXUM layout with a table of every field, HTML-escaped and never turned into links, plus a plain-text part. Reply-To is set to the sender's address only on a provider that supports it (SendGrid) and only after re-validating it as a single address without CR/LF; the Twilio Email API has no reply-to field, so nothing is set there. The address is always in the body.
- Validation per form with DRF serializers: required fields, short fields 200 characters, email 254, phone 40, free text 4000; select values exactly as the site lists them; amounts are positive decimals with at most 2 decimals and at most 1,000,000,000,000, written plain or grouped by threes ("250000", "250,000.00", "250'000"; "250,50" is refused, not read as 25050) and stored normalised ("250000.00"); founded is a year from 1800 to the current year. Free text keeps line breaks and loses every other control character and bidi override; one-line fields turn them into spaces. Field errors are returned under `fields`.
- Abuse guards: a filled honeypot (`website`) or `elapsed_ms` under 3000 gets a 201 with a believable reference, stores and sends nothing and is logged at info level; a body over 32 KB is a 400; more than 5 links (`http://`, `https://`, `www.`) across the free-text fields is a 400 on that field ("Please remove some links."); `consent` must be true.
- Throttles (fixed cache windows, the pattern of the auth throttles through the shared `platform_core.services.rate_limits` helper; values in settings): per client IP 3 per 10 minutes and 10 per day, per sender email 3 per day, 200 per day in total. They count accepted submissions (including refused bots), so a visitor correcting validation errors does not use up the budget. A throttled request gets 429 `{detail: "Too many messages. Please try again later or write to us by email.", code: "throttled"}` with Retry-After.

Newsletter (double opt-in):

- `POST /api/v1/public/newsletter/subscribe/` always answers 202 "Check your inbox to confirm." for a well-formed address (no enumeration); a malformed address is a 400 on `email`; a filled honeypot gets the same 202 and nothing is stored. New address: a pending `NewsletterSubscription` and a confirmation email. Pending: the confirmation again, at most once an hour and three times in 24 hours. Confirmed: nothing. Unsubscribed: a new double opt-in with new links.
- `POST …/confirm/` with the token from `{PUBLIC_APP_BASE_URL}/newsletter/confirm?token=…` (7 days) and `POST …/unsubscribe/` with the token from `{PUBLIC_APP_BASE_URL}/newsletter/unsubscribe?token=…`. Both answer 400 `invalid_token` for an unknown, malformed or expired link; confirming twice and unsubscribing twice are fine. The unsubscribe endpoint also accepts the RFC 8058 one-click POST (token in the query string, form body `List-Unsubscribe=One-Click`); GET never unsubscribes.
- Link tokens are an HMAC of a random per-subscription nonce under a key derived from `SECRET_KEY`. The database stores the nonce and the SHA-256 hash of the token only, so a database copy alone cannot confirm or unsubscribe anyone. The live token is rebuilt only when the email is rendered for the provider; the stored copy in the delivery record carries "[redacted]". A still-valid confirmation link is kept on a re-send, so the first email keeps working. After a `SECRET_KEY` rotation the next email renews the stored hash for the new key (logged as a warning), so sending keeps working; links in emails sent before the rotation then stop working.
- Throttles: subscribe per IP 5 per hour and 20 per day (every request counts); confirmation emails 500 per day in total, checked on every subscribe request so a 429 never reveals whether an address is already subscribed; confirm and unsubscribe 30 per hour per IP each. Newsletter 429 bodies are `{detail: "Too many requests. Please try again later.", code: "throttled"}`.
- These are marketing emails to people who may have no account. They use their own `marketing_email.` topics, so they never appear in the investor notification centre (which lists `email.` deliveries by address), are not tied to an account and are separate from investor notices and from Smart-Invest alerts (transactional, COMMS-DEC-008). The account marketing consent of COMMS-DEC-002 is a different consent and is not used for this list; an investor who wants these emails subscribes on the site like anyone else. The emails use the shared layout with a footer that says why the person gets them and links to unsubscribe, instead of the account-holder footer.
- New-projects email: the scheduled job `newsletter_new_projects` runs daily in the default `run_scheduled_jobs` set (Europe/Zurich business-date run key, `ScheduledJobRun` evidence, monitored by `check_scheduled_jobs`, runs as the system without the admin actor). It lists loans first published after the end of the previous run's window and still open (the investor marketplace's open-loan selector `list_open_marketplace_loans`: published, capacity left, funding deadline not passed; Direct loans and Loan Originator claims) and queues ONE email per confirmed subscriber with title, interest a year, term, currency and a link to `{PUBLIC_APP_BASE_URL}/projects/<loan_id>`. No new projects, no email. The borrower's name is never used. What was sent is recorded per run (`NewsletterDigestRun`: window and the projects snapshot) and per subscriber (`NewsletterDigestDelivery`, unique per run and subscriber, append-only), so a repeat run sends nothing and a run interrupted on an earlier day is finished first. A loan announced in the last 180 days is not announced again. The first run ever looks back one day only. Every email has the unsubscribe link; on a provider that supports custom headers (SendGrid) it also carries `List-Unsubscribe: <{PUBLIC_APP_BASE_URL}/api/v1/public/newsletter/unsubscribe/?token=…>` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click`. An email queued for someone who unsubscribes before it goes out is closed unsent. There is at most one email a day and only when projects open; "once or twice a month" in the confirmation text describes the expected pace of new projects.

Retention:

- The scheduled job `public_site_retention` runs daily in the same set. Enquiries are deleted 24 months after they were received. Unsubscribed newsletter rows are anonymised 30 days after unsubscribing (address, IP hash and link nonces cleared; the unsubscribe hash is kept, so a late click on an old link still answers "unsubscribed", and the address can subscribe again from scratch). Rows never confirmed are anonymised 30 days after their link expired.
- Email evidence is append-only. The stored copy of an enquiry email has the field values redacted (the details live only in the enquiry row and go with it after 24 months); the outbox payload holds only the enquiry id and reference. Newsletter delivery records keep the recipient address and the email content without tokens, as for every email the platform sends.

Rationale:
One path for every email keeps retries and evidence uniform. Answering every newsletter request the same way, counting confirmation emails globally and storing only token hashes keeps the anonymous endpoints from being used to probe or flood addresses. Separate marketing topics keep the newsletter out of investor notices.

Impacted modules:
- Communications (endpoints, models, emails, jobs).
- Platform core (shared rate-limit helper, scheduled-job registration).
- Public site frontend (forms, newsletter confirm and unsubscribe pages).

Follow-ups:
Legal/compliance to approve the consent text, the privacy notice for forms and newsletter, and the retention periods. Decide the marketing sender identity and domain authentication before real sending. Bounce/suppression handling for the newsletter. Admin views of enquiries and subscribers. Failed `marketing_email.` sends do not appear in the admin failed-email queue (it lists `email.` topics); add them when that queue is next changed. One-click unsubscribe headers for Twilio Email once its API supports custom headers.

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

This balance can fund only loans whose remaining funding window fits within its remaining holding time. Currency exchange does not reset the ageing deadline. If the balance remains after day 60, it will be subject to the configured penalty policy: {{penalty.description}}.

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
Last day: your {{platform.name}} balance reaches the 60-day limit today

Day-60 body (sent on the deadline date, the last day the money may stay; enforcement starts the next day):

Hello {{investor_name}},

Your {{amount}} {{currency}} balance from {{received_date}} reaches the 60-day holding limit today.

Swiss regulatory requirements mean {{operator.legal_name}} must avoid keeping user funds for more than 60 days. This deadline cannot be extended.

Please withdraw the balance by the end of today. From tomorrow, {{operator.legal_name}} returns it to your verified IBAN; without a usable IBAN it becomes subject to the configured penalty policy: {{penalty.description}}.

If {{operator.legal_name}} does not have a usable IBAN for you, financial actions on your account will be frozen until you provide one so we can return the due funds. You will still have read-only access to your portfolio, documents, tax information statements, notices, and messages.

Regards,
{{platform.name}}
{{operator.legal_name}}

## Implementation Status

The current backend queues idempotent transactional email outbox messages for:

- Authentication magic links and sensitive-action confirmation codes, with the plaintext secret stored only in the short-lived encrypted auth record and rendered at dispatch time.
- Balance-ageing reminder thresholds on days 25, 46, 53, 56, 57, and 58 (2026-10-16; before: 25, 46, 53, 58, 59, 60), plus day 59 and 60 notices only without a usable IBAN.
- Borrower repayment distributions credited to lender balances.
- Recovery distributions credited to lender balances.
- Secondary-market listing lifecycle updates for sellers.
- Secondary-market buyer and seller purchase/sale confirmations, without exposing counterparty identity.
- Smart-Invest first-publication matches for active, financially eligible investors, deduplicated per investor and loan.
- Balance events (audit 2026-10, A-18): deposit credited; withdrawal requested, sent and cancelled; day-61 forced return started; penalty mode entered; payout IBAN added (also when added again after a rejection), verified, not verified (the admin rejects the request) or no longer usable (the admin revokes it). The IBAN verification task cannot be closed while the request is pending; the reject action closes it.
- Currency exchange completed, with amounts, rate, fee and date.
- Primary market: order placed with the amount actually reserved (also a partial reservation); funding closed (holding active) or partly closed (new loan amount); funding cancelled, with the admin's investor message; order released by an admin.
- Loan status: Direct and Loan Originator loans turned Late (day 5) or Defaulted (day 16), sent to current holders.
- Public site (COMMS-DEC-009): one email per accepted public form to `PUBLIC_ENQUIRY_EMAIL` (`email.public_enquiry`); newsletter confirmation and daily new-projects emails (`marketing_email.newsletter_confirmation`, `marketing_email.newsletter_new_projects`, scheduled job `newsletter_new_projects`); retention clean-up in the scheduled job `public_site_retention`.

Each business event creates one email and one portal notice through `platform_core.services.investor_notices` (idempotency key per event, Europe/Zurich business dates from the platform clock, amounts in the currency's minor units, masked IBANs, no secrets). Penalty mode sends one notice per investor, currency and entry day; daily penalty charges send no notice, and no weekly summary is sent. Internal admin reasons (withdrawal cancellation, order release, IBAN rejection or revocation) are not sent to investors; the investor message of a partial close or a funding cancellation is. A test renders every email topic produced in the backend through the real renderer. All emails share one layout in the site's design (October 2026 re-skin) with the Banxum wordmark in the header and the footer. The logo is a hosted PNG on the app domain (`/brand/banxum-email-logo.png`, or `EMAIL_ASSET_BASE_URL`), because email clients do not show SVG; its alt text keeps the name visible when images are blocked.

Local development uses the mock email provider. Staging and production use `COMMUNICATIONS_EMAIL_PROVIDER=twilio_email`, `TWILIO_EMAIL_API_KEY_SID`, `TWILIO_EMAIL_API_KEY_SECRET`, `TWILIO_EMAIL_FROM_EMAIL`, and authenticated sender-domain DNS before sending real notices. The legacy `sendgrid` provider remains available for rollback. Final advisor-approved template wording, template versioning UI, attachments/secure document links, bounce/suppression handling, and admin dead-letter task creation remain provider/content follow-ups before launch.

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
- Balance ageing reminders must be sent on days 25, 46, 53, 56, 57, and 58 for remaining unconsumed balance source entries (2026-10-16: money not invested goes back to the bank automatically after 58 days; day 59 and 60 notices only without a usable IBAN).
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
7. Answered by COMMS-DEC-001: Twilio Email API is the launch email provider; Twilio Verify is used separately for phone verification.
8. Answered by COMMS-DEC-006: no support tickets at launch; normal email support is enough and support email should be exposed on the site/FAQ.
9. Answered by COMMS-DEC-004: failed emails retry a few times, then create an admin notification/task; full sent email content is stored.
10. Answered by COMMS-DEC-005: admin can choose public loan note only, bulk email only, or both.
11. Answered by COMMS-DEC-007: email templates are superadmin-editable with variable scopes, examples, validation, versioning, and audit logs.
12. Updated by ACC-DEC-001/ACC-DEC-002/ACC-DEC-008: investor magic-link login emails, investor sensitive-action email-code emails, and admin email-code emails are transactional authentication messages.
