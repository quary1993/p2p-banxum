// IP of Webby-Soft SRL.
/*
 * Content of the public site, word for word from the design (content.js): company details,
 * questions, guides and legal pages. The wording rules of the design apply (no "guaranteed",
 * "deposit", "savings" or "passive income"; rates are what the borrower owes, not a promise).
 *
 * Answers and bodies are trusted static HTML written here (never user or API data): render them
 * with <SiteHtml> (components.tsx), which rewrites the design's "#/x" links to "/x" and opens
 * them in the app. Placeholders stay as in the design until the owner provides the values.
 */

export type SiteCompany = {
  name: string;
  brand: string;
  city: string;
  street: string;
  uid: string;
  lei: string;
  bank: { name: string; CHF: string; EUR: string; swift: string };
  email: string;
  partners: string;
  phone: string;
  capital: string;
  vqf: string;
  auditor: string;
  hours: string;
};

export type FaqItem = { q: string; a: string; top?: boolean };
export type FaqGroup = { id: string; title: string; items: FaqItem[] };
export type SiteGuide = {
  id: string;
  kind: "Guide" | "News";
  date: string;
  icon: string;
  title: string;
  summary: string;
  body: string;
};
export type SiteLegalDoc = {
  id: string;
  title: string;
  version?: string;
  date?: string;
  body?: string;
  outline?: string[];
  imprint?: boolean;
};

/** Company details shown on the site. The owner changes them here, in one place. */
export const siteCompany: SiteCompany = {
  name: "Garanta Finanzgruppe AG",
  brand: "Banxum",
  city: "CH-3011 Bern, Switzerland",
  street: "Schauplatzgasse 26",
  uid: "CHE-302.757.239",
  lei: "984500N09O5DEDEK2085",
  bank: {
    name: "UBS Switzerland AG",
    CHF: "CH83 0020 6206 9567 6601 M",
    EUR: "CH84 0020 6206 9567 6660 L",
    swift: "UBSWCHZH80A"
  },
  email: "support@banxum.com",
  partners: "partners@banxum.com",
  phone: "+41 31 000 00 00 (sample)",
  capital: "CHF 1,100,000.00",
  vqf: "Member number to be added",
  auditor: "Independent auditor, name to be added",
  hours: "Monday to Friday, 9:00 to 17:00 (Swiss time)"
};

/** Help page, grouped by topic. The home page shows the questions marked "top". */
export const siteFaq: FaqGroup[] = [
  {
    id: "start",
    title: "Getting started",
    items: [
      {
        top: true,
        q: "Is Banxum regulated?",
        a: "<p>Yes. Banxum® is a registered trademark; the platform is owned and operated by Garanta Finanzgruppe AG, a Swiss financial company affiliated to VQF, a self-regulatory organisation recognised by FINMA, for its financial activities, and to FINOS, the Swiss financial ombudsman. Its accounts are audited by an independent auditor and its share capital is CHF 1,100,000.00. Garanta is not a bank.</p>"
      },
      {
        q: "Who can invest?",
        a: "<p>Adults and companies resident in Switzerland or in a country of the EU or the EEA, with a bank account in their own name in CHF or EUR. We check your identity online before you can invest. US persons cannot open an account.</p>"
      },
      {
        q: "How long does it take to open an account?",
        a: "<p>A few minutes: your details and the agreements, a password and a second factor (an SMS code or an authenticator app), then an online identity check with your ID document and a selfie. Before your first investment you give a few declarations (beneficial owner, source of funds) and add a verified bank account in your name.</p>"
      },
      {
        top: true,
        q: "How much do I need to start?",
        a: "<p><strong>CHF 1,000.00 or EUR 1,000.00</strong>, in the currency of the loan.</p><p>For some loans the minimum is higher, and loans from loan originators can have their own minimum. The project page always shows the current minimum.</p>"
      },
      {
        top: true,
        q: "Does Banxum charge investors fees?",
        a: "<p>No: <strong>0% fees for investors</strong>. Nothing to open or keep your wallet, to add or withdraw money, to invest, or on the interest and repayments you receive. Only if you sell early on the secondary market, the seller pays 2% of the price, at most 2% of the outstanding principal. Your bank may charge for its transfers.</p>"
      }
    ]
  },
  {
    id: "investing",
    title: "Investing",
    items: [
      {
        top: true,
        q: "How is interest calculated?",
        a: "<p>Every day, on the principal still outstanding: principal × rate ÷ 365 for each day, from the day the loan is paid out. It is paid on the dates of the repayment schedule (monthly, quarterly, half-yearly, yearly or at the end). If you sell early on the secondary market, the buyer pays you the interest accrued up to the sale.</p>"
      },
      {
        top: true,
        q: "What do I buy when I invest?",
        a: "<p>A share of a claim against a company: the company's obligation to repay a loan with interest. For a <strong>new loan</strong>, Garanta lends to the company and assigns part of the claim to you. For an <strong>existing claim</strong>, a loan originator (a leasing, factoring or lending company) has already lent the money, and you buy a share of its claim.</p><p>Before you confirm, you accept the investment and assignment terms of that loan; they name the loan, the amount and your share, and they stay in your Documents.</p>"
      },
      {
        q: "How are projects selected?",
        a: "<p>Each company is analysed before it is listed: financial statements of at least two years, credit reports, the value of the security, the owners and the management. Loan originators are checked the same way, and so are the claims they offer. Only projects that pass are listed.</p>"
      },
      {
        q: "When is my investment final?",
        a: "<p>When you confirm, the amount is reserved from your available balance. When the funding period ends and the loan has reached its minimum funding, the funding closes: you hold your share of the claim and you get your repayment schedule. If the loan does not reach its minimum funding, the reservation is released and the money is available again. An offer of a loan originator closes as soon as it is fully subscribed, or at its funding deadline.</p>"
      },
      {
        q: "Can Banxum choose loans for me?",
        a: "<p>You choose every loan yourself. Smart Invest shows the open loans that match your preferences and tells you when a new one is published. It never invests for you: you review and confirm each investment.</p>"
      }
    ]
  },
  {
    id: "money",
    title: "Money and payments",
    items: [
      {
        q: "What is my Banxum wallet?",
        a: "<p>Every investor has a segregated electronic wallet with a CHF and a EUR balance. The money is held on Garanta's collection account, apart from Garanta's own money, and recorded investor by investor. The wallet is not a bank account: it earns no interest, and money you do not invest can stay until day 56; then it goes back to your bank.</p>"
      },
      {
        q: "How do I pay for an investment?",
        a: "<p>From the available balance of your wallet, in the loan's currency. You add funds by bank transfer from your own account, with your personal reference. You cannot invest more than your available balance, and there is no second transfer after you confirm.</p>"
      },
      {
        q: "What happens to money I do not invest?",
        a: "<p>It stays in your wallet without interest until day 56 after it arrives. Then we return it automatically to your verified bank account in the same currency: the return starts on day 57, or earlier when the bank is closed that day. Banxum is not a bank and cannot keep money longer than 60 days.</p>"
      },
      {
        q: "Where are repayments paid?",
        a: "<p>Into your Banxum balance, in the loan's currency, when the borrower pays. From there you invest them again or withdraw them to your verified bank account.</p>"
      },
      {
        q: "Which currencies can I use?",
        a: "<p>CHF and EUR, each with its own balance in your wallet. Each loan is in one currency and there is no conversion on Banxum. If your bank account is in another currency, your bank converts the transfers.</p>"
      }
    ]
  },
  {
    id: "risks",
    title: "Risks and defaults",
    items: [
      {
        top: true,
        q: "Can I lose money?",
        a: "<p>Yes. A company can pay late or stop paying. The security can be worth less than expected or take long to sell. You can lose part or all of the money you lend. Spread your money across several loans and only invest money you can do without for the whole term.</p>"
      },
      {
        q: "What happens if a borrower pays late?",
        a: "<p>Garanta, as collection agent for all investors, reminds the borrower. For two business days after the due date the payment is shown as pending; then it is shown as due, with the number of days. From day 15 the investment is marked as late and you are informed. From day 60 Banxum can declare the loan in default (calendar days, Swiss time); a loan contract can set other days. Default does not end the contract by itself: the end of the contract, the enforcement of the security and the recovery are separate steps, shown on the investment page. Garanta shares what it recovers in proportion to each share. Recovery can take months or years.</p>"
      },
      {
        q: "What if Garanta stops operating?",
        a: "<p>The claims you bought are assigned to you. Garanta collects them as your agent; the agreements provide for the collection to pass to another agent or to the investors if Garanta could no longer do it. Money in Banxum wallets is kept apart from Garanta's own money and recorded investor by investor.</p>"
      }
    ]
  },
  {
    id: "selling",
    title: "Selling early",
    items: [
      {
        q: "Can I sell an investment before it ends?",
        a: "<p>Yes, on the secondary market, if the loan is paid on time and no instalment is due. You sell your whole share at a price from 0% to 102% of the outstanding principal (a discount, or at most a 2% premium); the buyer also pays the interest accrued since the last payment. The seller pays 2% of the price, at most 2% of the outstanding principal; the buyer pays no fee. A sale is not guaranteed: someone has to buy.</p>"
      }
    ]
  },
  {
    id: "tax",
    title: "Tax and documents",
    items: [
      {
        q: "How is interest taxed?",
        a: "<p>Interest is income. You declare it where you are tax resident. In Reports you can create a tax report for a year that has ended, as PDF or CSV. It is information for your tax return, not an official tax certificate.</p>"
      },
      {
        q: "Which documents do I receive?",
        a: "<p>For each investment: the terms you accepted and the repayment schedule, in Documents and on the investment page. In Reports: account statements, portfolio reports, interest and repayment reports and tax reports for a period you choose, as PDF or CSV, and a monthly statement.</p>"
      }
    ]
  },
  {
    id: "security",
    title: "Account and security",
    items: [
      {
        q: "How is my account protected?",
        a: "<p>You sign in with your password and a second factor: an SMS code or an authenticator app. Investments, withdrawals and changes of bank account ask for a code we email you and your PIN, or your authenticator code if you use the app.</p>"
      },
      {
        q: "How do you use my personal data?",
        a: "<p>Only to run your account and to meet our legal duties, under the Swiss Federal Act on Data Protection and, for residents of the EU, the GDPR. The <a href=\"#/legal/privacy\">privacy notice</a> has the details.</p>"
      }
    ]
  }
];

/** Questions of the For companies page. */
export const siteCompanyFaq: FaqItem[] = [
  {
    q: "Which companies can apply?",
    a: "<p>Companies (AG, GmbH, SA, Sàrl and their equivalents in the EU) registered in Switzerland or in a country of the EU, with at least two years of financial statements and a clear use for the money. We do not lend to private persons or to start-ups without revenue.</p>"
  },
  {
    q: "How much can we borrow, and for how long?",
    a: "<p>No loan size limits: the amount and the term follow your project. Repayment in monthly instalments, monthly interest with the principal at the end, or everything at the end for short terms.</p>"
  },
  {
    q: "Is our company name public?",
    a: "<p>No. The public project page shows the sector, the region and the terms. The company name, the financial figures and the documents are shown only to investors who have opened an account and passed the identity check.</p>"
  },
  {
    q: "How long does it take?",
    a: "<p>A first answer within two business days, an offer within about ten business days after we have all documents, and a funding period of up to 50 days. You receive the money when the loan is fully funded.</p>"
  }
];

export const siteGuides: SiteGuide[] = [
  {
    id: "read-a-project-page",
    kind: "Guide",
    date: "2026-09-12",
    icon: "ni-file-text",
    title: "How to read a project page",
    summary: "Rate, term, security and the minimum: what each figure means and what to check before you invest.",
    body: `<p>Every project on Banxum has the same page, so you can compare loans on the same points. Here is what to look at, in the order we would.</p>
        <h2>1. The company and the purpose</h2>
        <p>Who borrows, since when the company exists, what it does and what the money is for. A clear purpose (a machine, a building, invoices from named customers) is easier to follow than "working capital".</p>
        <h2>2. The security</h2>
        <p>What investors can enforce if the company stops paying: a mortgage note, a pledge on equipment, a personal guarantee, assigned receivables. Look at the loan-to-value ratio when there is one: the lower it is, the more room there is if the asset sells for less than its value.</p>
        <h2>3. The rate</h2>
        <p>The rate is what the borrower owes you each year on the principal. A higher rate is payment for a higher risk, not a better deal.</p>
        <h2>4. The term and the repayment</h2>
        <p>Regular instalments (monthly, quarterly, half-yearly or yearly) give your money back step by step. With interest only and the principal at the end, or everything at the end, more of your money depends on the last payment.</p>
        <h2>5. The minimum</h2>
        <p>CHF 1,000.00 or EUR 1,000.00. For some loans it is higher, and loans from loan originators can have their own minimum; the project page shows the current minimum.</p>
        <div class="site-callout">Spread your money: several smaller amounts in different companies, sectors and terms are safer than one large amount.</div>`
  },
  {
    id: "claim-assignment",
    kind: "Guide",
    date: "2026-09-02",
    icon: "ni-swap",
    title: "What claim assignment means for you",
    summary: "You do not lend through a pool: you receive your own share of a claim against a named company, under terms you accept for each investment.",
    body: `<p>On Banxum you invest by buying a share of a claim. A claim is the right to be repaid: the company owes the principal and the interest in the loan agreement.</p>
        <h2>New loans</h2>
        <p>Garanta Finanzgruppe AG lends to the company. When investors have funded the loan, Garanta assigns to each of them a share of the claim, in proportion to the amount they invested.</p>
        <h2>Existing claims</h2>
        <p>A loan originator, such as a leasing or factoring company, has already lent the money. Investors buy shares of its claim, at the outstanding principal plus the interest accrued so far.</p>
        <h2>What you receive</h2>
        <p>Before you confirm, you accept the investment and assignment terms of the loan. They name the loan, the amount and your share, and they stay in your Documents with your repayment schedule. The repayments for your share are credited to your Banxum balance.</p>
        <h2>How interest is calculated</h2>
        <p>Every day, on the principal still outstanding: principal × rate ÷ 365 for each day, from the day the loan is paid out. It is paid on the dates of your schedule.</p>
        <h2>Who collects</h2>
        <p>Garanta collects the repayments for all investors and, if a borrower does not pay, enforces the security on their behalf. What it recovers is shared in proportion to each share.</p>`
  },
  {
    id: "spread-your-money",
    kind: "Guide",
    date: "2026-08-14",
    icon: "ni-pie",
    title: "Spreading your money across loans",
    summary: "Why several smaller amounts in different companies, sectors and countries protect you better than one large amount.",
    body: `<p>Every loan can go wrong, whatever its rate. What you can control is how much depends on a single company.</p>
        <h2>Different companies</h2>
        <p>If one borrower stops paying, the others keep paying. With ten loans of equal size, one default touches a tenth of your money.</p>
        <h2>Different sectors and countries</h2>
        <p>A crisis in one sector or region hits several companies at once. Mixing construction, manufacturing, food and services spreads that risk.</p>
        <h2>Different terms</h2>
        <p>Loans that end at different times give your money back step by step and let you decide again with each repayment.</p>
        <div class="site-callout">Only invest money you can do without for the whole term. Lending to companies is not a savings account.</div>`
  },
  {
    id: "late-payments",
    kind: "Guide",
    date: "2026-07-30",
    icon: "ni-clock",
    title: "What happens when a borrower pays late",
    summary: "From the first reminder to the enforcement of the security: the steps, who takes them and how you are kept informed.",
    body: `<p>Most late payments are a few days late and are paid after a reminder. Some are the start of real difficulties. Here is what happens in each case.</p>
        <h2>Day 1 to 14</h2>
        <p>For two business days the payment is shown as pending; then it is shown as due in your account, with the number of days. Garanta reminds the borrower. Many payments arrive in these days.</p>
        <h2>Day 15 to 59</h2>
        <p>The payment is marked as late in your account, in red, with the number of days. Garanta talks to the company and its owners. Investors are informed of every step on the investment page.</p>
        <h2>From day 60</h2>
        <p>Banxum can declare the loan in default (calendar days, Swiss time); a loan contract can set other days. Default does not end the contract by itself. The end of the contract and the enforcement of the security (sale of the pledged asset, call of the guarantee) on behalf of all investors are separate steps, each shown with its date.</p>
        <h2>Recovery</h2>
        <p>What is recovered, after real external costs (lawyers, courts, enforcement), is shared in proportion to each share and credited to your Banxum balance. Banxum takes no recovery fee, and the investment page shows the gross amount, the costs and the net. Recovery can take months or years and may not cover the full amount.</p>`
  }
];

/**
 * Legal pages: outlines until the lawyers provide the texts. The risk page is complete because
 * the home page and every call to invest link to it.
 */
export const siteLegal: SiteLegalDoc[] = [
  {
    id: "risk",
    title: "Risk information",
    version: "1.0",
    date: "2026-09-01",
    body: `<p>Lending to companies can earn interest, and it can lose money. Read this page before you invest.</p>
        <h2>Credit risk</h2>
        <p>A borrower can pay late, pay only part or stop paying. You can lose part or all of the money you lend, and the interest you expected.</p>
        <h2>Security</h2>
        <p>Security (a mortgage note, a pledge, a guarantee) can be worth less than expected, be hard to sell or take long to enforce. Enforcement has costs, paid from what is recovered.</p>
        <h2>Liquidity</h2>
        <p>Your money is committed for the whole term. You can offer your share on the secondary market, but a sale is not guaranteed and may be at a price below the principal.</p>
        <h2>Concentration</h2>
        <p>If much of your money is in one loan, one sector or one country, a single problem can hit a large part of it. Spread your money across several loans.</p>
        <h2>The platform</h2>
        <p>Garanta collects repayments as agent for investors. If it could no longer do so, collection would pass to another agent, which can cause delays.</p>
        <h2>Currency</h2>
        <p>Loans are in CHF or EUR. If you think in another currency, exchange rates change the value of what you receive.</p>
        <h2>No deposit protection</h2>
        <p>Garanta is not a bank. Money in your Banxum wallet is not a deposit and is not protected by the Swiss deposit insurance or by any EU scheme. Loans are not covered by any investor compensation scheme.</p>
        <h2>Past results</h2>
        <p>Statistics of past loans do not predict how future loans will perform.</p>`
  },
  {
    id: "terms",
    title: "Terms of use",
    version: "2.1",
    date: "2026-09-01",
    outline: [
      "Scope and parties",
      "Opening and closing an account",
      "Identification and anti-money-laundering duties",
      "The Banxum wallet: payments in, reservations and the return of money not invested",
      "Interest: daily calculation (actual/365) and payment dates",
      "Investing: reservation, funding period, assignment",
      "Repayments and collection by Garanta",
      "Late payments, termination and enforcement",
      "Secondary market",
      "Fees",
      "Liability",
      "Changes to the terms",
      "Governing law and place of jurisdiction"
    ]
  },
  {
    id: "privacy",
    title: "Privacy notice",
    version: "2.1",
    date: "2026-11-20",
    body: `<p>This notice tells you which personal data Banxum uses, why, who receives it, how long we keep it and what your rights are. It follows the Swiss Federal Act on Data Protection (FADP) and, for people in the European Economic Area, the EU General Data Protection Regulation (GDPR). [Draft of 20 November 2026: the points marked "to confirm" are completed before launch.]</p>
        <h2>Who is responsible</h2>
        <p>Banxum is a brand of Garanta Finanzgruppe AG, Schauplatzgasse 26, CH-3011 Bern, Switzerland (UID CHE-302.757.239). Garanta is responsible for your data. For every question about your data, write to <a href="mailto:support@banxum.com">support@banxum.com</a> or by post to the address above.</p>
        <h2>Which data we use</h2>
        <ul>
          <li><strong>Account:</strong> name, email address, phone number, password (stored only as a hash), your PIN or authenticator app (stored only as a hash or an encrypted secret), recovery codes (hashed), language, number format and your choice about news emails.</li>
          <li><strong>Identity check:</strong> our identity provider checks your identity document and takes a live photo. We receive the result and, when the provider gives them, your verified address, date of birth and nationality.</li>
          <li><strong>Declarations:</strong> beneficial owner of the funds, sources of funds, whether you or a close person are politically exposed, your expected yearly investment volume, and for companies the company, its representative and its controlling persons.</li>
          <li><strong>Money and investments:</strong> your bank accounts (IBAN, holder, bank), deposits, reservations, investments, repayments, resale offers and withdrawals, and the documents you accept (with the time, the version, the amount and the technical data of the confirmation: the IP address and the browser).</li>
          <li><strong>Security:</strong> signed-in devices and sign-ins (date, device and browser, approximate place, method and result), and the codes we send you. In these account records we keep your IP address only as a keyed hash, not in clear. The approximate place (city and country) comes from an IP database kept on our server; no IP address goes to an outside service for this.</li>
          <li><strong>IP address in clear:</strong> we keep the IP address itself in two places only. (1) The record of each document you accept (for example an investment confirmation or an assignment), as evidence that the contract was concluded; it is kept with the contract records (see "How long we keep it") and only authorised staff can see it. (2) The technical logs of our web server, for security and error analysis. [To confirm: how long the server logs are kept.]</li>
          <li><strong>Messages:</strong> emails and notices we send you, and what you send to support (help messages, complaints, account closure requests).</li>
          <li><strong>Website:</strong> messages sent with the contact forms, newsletter subscriptions (with the confirmation of your consent) and your cookie choice.</li>
        </ul>
        <h2>Why we use it</h2>
        <ul>
          <li>To open and run your account and your investments under the terms of use (contract).</li>
          <li>To meet our legal duties: identification and anti-money-laundering checks, accounting, tax and reports to authorities (legal obligation).</li>
          <li>To protect your account and the platform: sign-in checks, alerts for new devices, prevention of fraud and abuse (legitimate interest).</li>
          <li>To send news about Banxum, only when you agree; you can stop it at any time (consent).</li>
          <li>To measure the use of the public website, only when you agree in the cookie settings (consent). This measurement is planned and not active today (see the cookie policy).</li>
        </ul>
        <p>We do not sell your data and we do not use it for advertising profiles. We do not make automated decisions that have legal effects on you; a compliance review is always done by a person.</p>
        <h2>Who receives it</h2>
        <ul>
          <li>Our identity provider (Didit) for the identity check. [To confirm: place of processing and contract terms.]</li>
          <li>Twilio (Twilio Verify) to send sign-in codes by SMS, and SendGrid (part of Twilio) to send emails. [To confirm: SendGrid region and the data processing terms.]</li>
          <li>Our hosting provider, which runs our server. [To confirm: provider and country.] Backups are stored with Amazon Web Services in Zurich, Switzerland.</li>
          <li>Banks that execute deposits, payments and returns.</li>
          <li>Authorities when the law requires it (for example the Money Laundering Reporting Office Switzerland, FINMA, tax authorities, courts), and our auditors and lawyers under professional secrecy.</li>
          <li>No analytics provider receives data today. If we add one for the public website (for example Google Analytics), it will start only after your consent, and we will name it here first.</li>
        </ul>
        <p>To check new passwords against known data breaches, we send only the first five characters of a one-way hash of the password to the "Have I Been Pwned" service; the password itself never leaves our server.</p>
        <h2>Transfers abroad</h2>
        <p>Some providers process data outside Switzerland, for example in the European Union or in the United States (Twilio, SendGrid). We send data to a country without an adequate level of protection only with suitable safeguards, such as the standard contractual clauses recognised by the Federal Data Protection and Information Commissioner, or a certification under the Swiss-U.S. Data Privacy Framework. [To confirm per provider.]</p>
        <h2>How long we keep it</h2>
        <p>Some data is deleted automatically:</p>
        <ul>
          <li>Sign-in history and ended sessions: after 365 days (our current setting).</li>
          <li>Contact form messages: after 24 months.</li>
          <li>Newsletter: as long as you are subscribed; the personal data of a subscription that was cancelled or never confirmed is deleted after 30 days.</li>
        </ul>
        <p>The other platform records (account, identity checks, declarations and compliance reviews, money, investments and ledger records, accepted documents and contracts, reports, messages and support requests, and the logs of important actions) have no automatic deletion yet. At launch we keep them at least for the periods the law requires, and in any case until our detailed retention schedule is approved:</p>
        <ul>
          <li>Identification and anti-money-laundering files: at least 10 years after the end of the business relationship (AMLA art. 7).</li>
          <li>Accounting, payment and ledger records: at least 10 years (CO art. 958f).</li>
          <li>Contracts, signed assignments and the evidence of their acceptance: at least 10 years after they end (CO art. 127).</li>
        </ul>
        <p>[To confirm: the detailed retention schedule per type of record, with the periods after which data is deleted or anonymised, and the exceptions for legal holds. It will replace this section before launch.]</p>
        <h2>Your rights</h2>
        <p>You can ask for a copy of your data, its correction, its deletion (where no legal duty requires us to keep it), a copy in a common electronic format, and you can object to processing based on our legitimate interest. You can withdraw a consent at any time, without effect on processing done before. Write to <a href="mailto:support@banxum.com">support@banxum.com</a>; we check your identity before we answer.</p>
        <p>You can complain to the Federal Data Protection and Information Commissioner (FDPIC, www.edoeb.admin.ch) or, in the European Economic Area, to the data protection authority of your country.</p>
        <h2>Security</h2>
        <p>We protect your data with technical and organisational measures: encrypted connections, sign-in with a password and a second factor, confirmation of sensitive operations, access only for authorised staff, and logs of important actions.</p>
        <h2>Credits and changes</h2>
        <p>IP geolocation by <a href="https://db-ip.com" rel="noopener noreferrer" target="_blank">DB-IP</a>, licensed under Creative Commons Attribution 4.0. We may update this notice; the date and version at the top show the current one, and we tell you about important changes.</p>`
  },
  {
    id: "cookies",
    title: "Cookie policy",
    version: "2.1",
    date: "2026-11-20",
    body: `<p>Cookies are small files that a website stores in your browser. Banxum also stores some data in your browser's local storage (kept until you clear it) and session storage (deleted when you close the tab). This page lists all of them.</p>
        <h2>Necessary cookies</h2>
        <p>These are needed for the site and the platform to work and to keep your account safe. They are always on.</p>
        <ul>
          <li><strong>sessionid</strong>: keeps you signed in. The session ends when you sign out, and at the latest 2 hours after you signed in.</li>
          <li><strong>csrftoken</strong>: protects forms against requests from other sites. 1 year.</li>
          <li><strong>banxum_device</strong>: recognises your browser so that we can show your signed-in devices and warn you about a sign-in from a new device. Stored on our side only as a hash. 2 years.</li>
          <li><strong>banxum_trusted</strong>: only when you choose "Trust this device" at sign-in; the second factor is then not asked on this device. 30 days.</li>
        </ul>
        <h2>Local storage (until you clear it)</h2>
        <ul>
          <li><strong>bxm-site-cookies</strong>: your cookie choice and its date.</li>
          <li><strong>banxum.appearance</strong>, <strong>banxum.sidebarCompact</strong>, <strong>banxum.numberFormat</strong>, <strong>banxum-investor-language</strong> (and <strong>banxum-investor-language-unsaved</strong>): appearance, sidebar width, number format and language.</li>
          <li><strong>banxum:app-route:v1</strong>: the last page you opened in the app, to open it again after a reload. No personal data.</li>
          <li><strong>banxum:marketplace-layout:v1</strong>, <strong>banxum.overview.returnNotice</strong>, <strong>banxum.overview.paymentUpdates</strong>: the Cards or List view of the opportunities and the notices you closed.</li>
          <li><strong>banxum:readonly-impersonation-…</strong>: only for Banxum staff who open a read-only support view of an account; removed when the view ends or expires.</li>
        </ul>
        <h2>Session storage (deleted when you close the tab)</h2>
        <ul>
          <li><strong>banxum:register-flow:v3</strong> and <strong>banxum:login-flow:v1</strong>: the steps of registration and sign-in, with the name, email address, phone number and country you typed, so that a reload does not lose them. Also deleted when you finish registration or sign out.</li>
          <li><strong>bxm-site-newsletter</strong>: the email address you subscribed with, for the confirmation message.</li>
          <li><strong>bxm-site-project-filters</strong>: the filters of the projects page.</li>
          <li><strong>banxum:session-expired:v1</strong> and <strong>banxum:u33-payment-updates-dismissed</strong>: a notice after your session expired, and a notice you closed.</li>
        </ul>
        <h2>Measurement (not active)</h2>
        <p>Banxum does not measure visits today: no analytics script is loaded and no analytics cookie is set. The cookie settings already let you agree to measurement in advance. If we start measuring visits to the public website (for example with Google Analytics), it will run only after your consent, and we will update this page first with the provider and its cookies.</p>
        <h2>No advertising cookies</h2>
        <p>Banxum does not use advertising or social media tracking cookies.</p>
        <h2>How to change your choice</h2>
        <p>Use "Cookie settings" at the bottom of every page of the website. You can also delete the cookies and site data of Banxum in your browser settings: deleting cookies signs you out; deleting site data (local storage) also removes your cookie choice, and we then ask for it again.</p>
        <p>More about how we use your data: <a href="/legal/privacy">Privacy notice</a>.</p>`
  },
  {
    id: "imprint",
    title: "Imprint",
    imprint: true
  },
  {
    id: "complaints",
    title: "Complaints",
    version: "1.0",
    date: "2026-09-01",
    body: `<p>If something went wrong, tell us. We answer every complaint in writing.</p>
        <h2>How to complain</h2>
        <p>Write to <a href="mailto:support@banxum.com">support@banxum.com</a> or by post to Garanta Finanzgruppe AG, Complaints, Schauplatzgasse 26, CH-3011 Bern, Switzerland. Tell us your investor number, what happened and what you expect.</p>
        <h2>What happens next</h2>
        <p>We confirm receipt within two business days and answer within fourteen days. If we need longer, we tell you why and when you will hear from us.</p>
        <h2>If you are not satisfied</h2>
        <p>You can turn, free of charge, to FINOS, the Swiss financial ombudsman (Finanzombudsstelle Schweiz), to which Garanta is affiliated. The ombudsman mediates between you and Garanta; you keep the right to go to court.</p>`
  }
];

/** The questions marked "top" (Home shows the first six, the first one open). */
export function topFaqItems() {
  return siteFaq.flatMap((group) => group.items).filter((item) => item.top);
}
