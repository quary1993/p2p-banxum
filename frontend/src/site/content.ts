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
        a: "<p>About 2 minutes: your details, the agreements, a few declarations (beneficial owner, source of funds) and an online identity check with your ID document and a selfie. Our compliance team usually confirms the account within one business day.</p>"
      },
      {
        top: true,
        q: "How much do I need to start?",
        a: "<p><strong>CHF 1,000.00 or EUR 1,000.00</strong>, in the currency of the loan.</p><p>For some loans the minimum is higher, and loans from loan originators can have their own minimum. The project page always shows the current minimum.</p>"
      },
      {
        top: true,
        q: "Does Banxum charge investors fees?",
        a: "<p>No: <strong>0% fees for investors</strong>. Nothing to open or keep your wallet, to add or withdraw money, to invest, or on the interest and repayments you receive. Only if you sell early on the secondary market, the seller pays 2% of the price. Your bank may charge for its transfers.</p>"
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
        a: "<p>Every day, on the principal still outstanding: principal × rate ÷ 365 for each day, from the day the loan is paid out. It is paid on the dates of the repayment schedule, monthly or at the end. If you sell early on the secondary market, the buyer pays you the interest up to the day of the sale.</p>"
      },
      {
        top: true,
        q: "What do I buy when I invest?",
        a: "<p>A share of a claim against a company: the company's obligation to repay a loan with interest. For a <strong>new loan</strong>, Garanta lends to the company and assigns part of the claim to you. For an <strong>existing claim</strong>, a loan originator (a leasing, factoring or lending company) first assigns the claim to Garanta, which then assigns part of it to you.</p><p>Your assignment declaration names the borrower, the loan agreement, the principal, the interest and your share.</p>"
      },
      {
        q: "How are projects selected?",
        a: "<p>Each company is analysed before it is listed: financial statements of at least two years, credit reports, the value of the security, the owners and the management. Loan originators are checked the same way, and so are the claims they offer. Only projects that pass are listed, with a rating from AAA to D.</p>"
      },
      {
        q: "What do the risk classes mean?",
        a: "<p>They are our opinion of the borrower's ability to repay and of the security, with ratings from AAA to D: AAA is the lowest risk, D the highest. Higher risk usually comes with a higher rate. A rating is not a guarantee: a loan rated AAA can also be repaid late or not at all.</p>"
      },
      {
        q: "When is my investment final?",
        a: "<p>When you confirm, the amount is reserved from your available balance. When the funding period ends and the loan is fully funded, Garanta signs the assignment with a qualified electronic signature and you receive the assignment declaration and your repayment schedule. If a loan is not fully funded, the reservation is released and the money is available again.</p>"
      },
      {
        q: "Can Banxum choose loans for me?",
        a: "<p>You choose every loan yourself. Smart-Invest is being prepared.</p>"
      }
    ]
  },
  {
    id: "money",
    title: "Money and payments",
    items: [
      {
        q: "What is my Banxum wallet?",
        a: "<p>Every investor has a segregated electronic wallet with a CHF and a EUR balance. The money is held on Garanta's collection account, apart from Garanta's own money, and recorded investor by investor. The wallet is not a bank account: it earns no interest, and money you do not invest goes back to your bank after 58 days.</p>"
      },
      {
        q: "How do I pay for an investment?",
        a: "<p>From the available balance of your wallet, in the loan's currency. You add funds by bank transfer from your own account, with your personal reference. You cannot invest more than your available balance, and there is no second transfer after you confirm.</p>"
      },
      {
        q: "What happens to money I do not invest?",
        a: "<p>It stays in your wallet without interest. After 58 days it goes back automatically to your verified bank account in the same currency. Banxum is not a bank and cannot keep money longer than 60 days.</p>"
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
        a: "<p>Garanta, as collection agent for all investors, reminds the borrower. From day 5 after the due date the investment is marked as late and you are informed. From day 16 the loan is in default (calendar days, Swiss time): Garanta enforces the security on behalf of the investors and shares what it recovers in proportion to each share. Recovery can take months or years.</p>"
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
        a: "<p>Yes, on the secondary market, if the loan is paid on time. You set the price at the principal (par) or at a discount, never above it; the buyer also pays the interest accrued since the last payment. Every share is sold whole. The seller pays 2% of the price. A sale is not guaranteed: someone has to buy.</p>"
      }
    ]
  },
  {
    id: "tax",
    title: "Tax and documents",
    items: [
      {
        q: "How is interest taxed?",
        a: "<p>Interest is income. You declare it where you are tax resident. The annual tax statement of interest and holdings is in your account, as PDF or CSV, when you need it for your tax return.</p>"
      },
      {
        q: "Which documents do I receive?",
        a: "<p>For each investment: the assignment declaration and the repayment schedule. For your account: an account statement for a period you choose and the annual tax statement, when you need them, as PDF or CSV.</p>"
      }
    ]
  },
  {
    id: "security",
    title: "Account and security",
    items: [
      {
        q: "How is my account protected?",
        a: "<p>You access your account with a magic link sent to your email. Investments, withdrawals and changes of bank account ask for an extra code and your PIN code.</p>"
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
    summary: "Rate, term, security, risk class and the minimum: what each figure means and what to check before you invest.",
    body: `<p>Every project on Banxum has the same page, so you can compare loans on the same points. Here is what to look at, in the order we would.</p>
        <h2>1. The company and the purpose</h2>
        <p>Who borrows, since when the company exists, what it does and what the money is for. A clear purpose (a machine, a building, invoices from named customers) is easier to follow than "working capital".</p>
        <h2>2. The security</h2>
        <p>What investors can enforce if the company stops paying: a mortgage note, a pledge on equipment, a personal guarantee, assigned receivables. Look at the loan-to-value ratio when there is one: the lower it is, the more room there is if the asset sells for less than its value.</p>
        <h2>3. The rate and the rating</h2>
        <p>The rate is what the borrower owes you each year on the principal. The rating, from AAA to D, is our opinion of the borrower and the security. A higher rate is payment for a higher risk, not a better deal.</p>
        <h2>4. The term and the repayment</h2>
        <p>Monthly instalments give your money back step by step. With monthly interest and the principal at the end, or everything at the end, more of your money depends on the last payment.</p>
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
    summary: "You do not lend through a pool: you receive your own share of a claim against a named company, with a signed assignment declaration.",
    body: `<p>On Banxum you invest by buying a share of a claim. A claim is the right to be repaid: the company owes the principal and the interest in the loan agreement.</p>
        <h2>New loans</h2>
        <p>Garanta Finanzgruppe AG lends to the company. When investors have funded the loan, Garanta assigns to each of them a share of the claim, in proportion to the amount they invested.</p>
        <h2>Existing claims</h2>
        <p>A loan originator, such as a leasing or factoring company, has already lent the money. It assigns the claim to Garanta, which then assigns shares to investors in the same way.</p>
        <h2>What you receive</h2>
        <p>An assignment declaration signed by Garanta with a qualified electronic signature. It names the borrower, the loan agreement, the principal, the interest and your share. The repayments for your share are credited to your Banxum balance.</p>
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
    body: `<p>Every loan can go wrong, whatever its rate or risk class. What you can control is how much depends on a single company.</p>
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
        <h2>Day 1 to 4</h2>
        <p>Garanta reminds the borrower. Many payments arrive in these first days.</p>
        <h2>Day 5 to 15</h2>
        <p>The payment is marked as late in your account, in red, with the number of days. Garanta talks to the company and its owners. Investors are informed of every step on the investment page.</p>
        <h2>From day 16</h2>
        <p>The loan is in default automatically (calendar days, Swiss time). Garanta then enforces the security (sells the pledged asset, calls the guarantee) on behalf of all investors.</p>
        <h2>Recovery</h2>
        <p>What is recovered, after the costs of enforcement, is shared in proportion to each share and credited to your Banxum balance. Recovery can take months or years and may not cover the full amount.</p>`
  },
  {
    id: "first-year",
    kind: "News",
    date: "2026-01-15",
    icon: "ni-growth",
    title: "Our first year in figures",
    summary: "Loans funded, repayments made, one late payment and what we learned. The same figures are on the statistics page, updated every month.",
    body: `<p>We publish the same figures every month on the <a href="#/statistics">statistics page</a>: loans funded, repaid, late and in default, per currency. Here are the main points of our first year.</p>
        <h2>What went well</h2>
        <p>Loans in Switzerland, Romania and Italy, from new loans and from three loan originators. Repayments were paid to investors' bank accounts on the business day after the borrowers paid.</p>
        <h2>What we watch</h2>
        <p>One late payment in the hospitality sector, paid after a reminder. We added the payment history of each borrower to the project page.</p>
        <div class="site-callout">Sample article of the prototype: the figures are the sample data of the statistics page.</div>`
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
      "The Banxum wallet: payments in, reservations, the 50-day return",
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
    version: "1.2",
    date: "2026-09-01",
    outline: [
      "Who is responsible",
      "Which data we collect (account, online identity check, transactions, website)",
      "Why we process it and on which legal basis (FADP, GDPR)",
      "Who receives it (identity provider, banks, authorities, service providers)",
      "Transfers abroad",
      "How long we keep it",
      "Your rights and how to use them",
      "Contact and supervisory authorities"
    ]
  },
  {
    id: "cookies",
    title: "Cookie policy",
    version: "1.0",
    date: "2026-09-01",
    outline: [
      "What cookies are",
      "Necessary cookies (sign-in, security, your cookie choice)",
      "Measurement cookies (only with your consent)",
      "No advertising cookies",
      "How to change your choice"
    ]
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
