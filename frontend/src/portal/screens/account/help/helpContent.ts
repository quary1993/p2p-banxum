// IP of Webby-Soft SRL.
// The questions of the portal Help page (design: hpQuestions of the U33 prototype, same ids, topics
// and tone). Every answer is written for today's platform, not the prototype: magic-link sign-in and
// PIN + email code (Phase 17.3 brings password + second factor, U33-DEC-01); repayments credited to the
// Banxum balance (U33-DEC-02); the holding time from the balances API; the minimum shown per
// opportunity; resale at par or a discount with the seller fee shown before confirming (U33-DEC-06/07
// come with Phase 17.2); late/default status as the servicing process sets it today (U33-DEC-09 comes
// with Phase 17.2); no ratings (U33-DEC-16); support by email (U33-DEC-35).
import type { RouteName } from "../../../../investorPortal/types";
import type { t as translate } from "../../../../i18n";

export type HelpTopic = "investing" | "money" | "documents" | "security";
export type HelpLink = { label: string; to: RouteName; params?: Record<string, string> };
export type HelpQuestion = {
  id: string;
  topic: HelpTopic;
  question: string;
  answer: string;
  more?: { title: string; text: string };
  links: HelpLink[];
  /** Topic preset of the Contact support dialog, when the answer offers it. */
  contact?: string;
};

export const HELP_TOPICS: Array<["all" | HelpTopic, string]> = [
  ["all", "All"],
  ["investing", "Investing"],
  ["money", "Money & payments"],
  ["documents", "Documents"],
  ["security", "Account & security"]
];

export function helpQuestions(t: typeof translate, { days, brand, fxEnabled }: { days: number; brand: string; fxEnabled: boolean }): HelpQuestion[] {
  const questions: HelpQuestion[] = [
    {
      id: "add-funds",
      topic: "money",
      question: t("How do I add money and pay for an investment?"),
      answer: t("Open Account and choose Add funds. Send a bank transfer from your own bank account in the same currency, with your personal payment reference exactly as shown. Your balance is credited once our team has matched the payment. Investments are paid from your available balance in the loan's currency; you cannot invest more than that balance."),
      links: [{ label: t("Account"), to: "balances" }]
    },
    {
      id: "minimum",
      topic: "investing",
      question: t("How much can I invest?"),
      answer: t("Each opportunity page shows the minimum investment and the amount still available. Your amount must be at least the minimum, no more than the amount still available, and within your available balance in the loan's currency."),
      more: {
        title: t("Why can the minimum be higher?"),
        text: t("Loans to Swiss borrowers can have a limited number of investors. The opportunity page then shows the places left, and the minimum can be higher so that the loan can still be fully funded.")
      },
      links: [{ label: t("Investment opportunities"), to: "market" }]
    },
    {
      id: "funding",
      topic: "investing",
      question: t("When does my investment begin?"),
      answer: t("Your amount is reserved when you confirm the investment. If the minimum funding is reached when funding closes, your investment starts and appears in My investments. If it is not reached, the reservation is released and the money is available again in your {brand} account.", { brand }),
      more: {
        title: t("What documents do I receive?"),
        text: t("The documents you accept when you invest are kept in Documents, with the version you accepted and the time. The payment schedule of each investment is on its page in My investments.")
      },
      links: [
        { label: t("My investments"), to: "portfolio" },
        { label: t("Documents"), to: "documents" }
      ]
    },
    {
      id: "schedule",
      topic: "money",
      question: t("Where can I see my payment schedule?"),
      answer: t("Open an investment in My investments to see its payment schedule, with the payments already received and the ones still to come. EUR and CHF are shown separately."),
      links: [{ label: t("My investments"), to: "portfolio" }]
    },
    {
      id: "repayments",
      topic: "money",
      question: t("Where are my repayments paid?"),
      answer: t("Repayments of principal and interest are credited to your {brand} balance in the loan's currency once the borrower's payment has been received and matched. From there you can invest the money again, each time with your confirmation, or withdraw it to your verified bank account.", { brand }),
      links: [
        { label: t("Account"), to: "balances" },
        { label: t("Transactions"), to: "transactions" }
      ]
    },
    {
      id: "smart",
      topic: "investing",
      question: t("Does Smart Invest invest automatically?"),
      answer: t("No. Smart Invest shows the opportunities that match your preferences. You review each investment, accept its documents and confirm it with your PIN and an email code before any money is reserved."),
      links: [{ label: t("Smart Invest"), to: "smartInvest" }]
    },
    {
      id: "late",
      topic: "investing",
      question: t("What happens if a payment is late?"),
      answer: t("The investment is marked Late and you are informed. {brand} contacts the borrower and, when needed, takes steps to recover the money, including through the security provided. Amounts recovered are credited to the investors' {brand} balances in proportion to their share. Recovery is not guaranteed.", { brand }),
      more: {
        title: t("Late payment, default and recovery"),
        text: t("The investment page shows the overdue amount and the days overdue. If the delay continues, the loan can be marked Default. Updates about the loan are published as loan notes on the investment page.")
      },
      links: [
        { label: t("My investments"), to: "portfolio" },
        { label: t("Notifications"), to: "notifications" }
      ]
    },
    {
      id: "security",
      topic: "investing",
      question: t("Is my investment guaranteed?"),
      answer: t("No. Collateral and guarantees can help recover money if a borrower does not repay, but they do not guarantee full or timely repayment. You can lose part or all of the money you invest. The opportunity page explains the security of each loan."),
      links: [{ label: t("Investment opportunities"), to: "market" }]
    },
    {
      id: "sell",
      topic: "investing",
      question: t("Can I sell an investment before it ends?"),
      answer: t("If the loan's payments are on time, open the investment in My investments and offer it on the Resale market. You sell your whole position. A sale needs a buyer and is not guaranteed."),
      more: {
        title: t("Price, interest and selling fees"),
        text: t("You set the price as a percentage of the outstanding principal, at most 100%. The buyer also pays the interest accrued since the last payment. The seller fee and the amount you receive are shown before you confirm. A listing ends if the loan becomes late.")
      },
      links: [
        { label: t("My investments"), to: "portfolio" },
        { label: t("Resale market"), to: "secondary" }
      ]
    },
    {
      id: "fees",
      topic: "investing",
      question: t("What fees do I pay?"),
      answer: t("Investing in an opportunity has no {brand} fee. If you sell an investment on the Resale market, a seller fee applies. Every fee is shown with its amount before you confirm, and nothing is charged without being shown first. Your bank may charge for transfers.", { brand }),
      links: [{ label: t("Documents"), to: "documents" }]
    },
    {
      id: "transfer",
      topic: "money",
      question: t("My bank transfer has not arrived. What should I check?"),
      answer: t("Check the bank details, currency and personal payment reference against the instructions in Add funds. The transfer must come from a bank account in your name. Our team matches payments by hand, so it can take some time after your bank has sent the money. If it is still missing, contact support with the transfer date, amount, currency and reference."),
      links: [{ label: t("Account"), to: "balances" }],
      contact: "My Banxum account"
    },
    {
      id: "unused",
      topic: "money",
      question: t("What happens to money I do not invest?"),
      answer: t("Money in your {brand} account earns no interest. Money you do not invest goes back to your bank automatically after {days} days, to your verified bank account in the same currency. Account shows the date for each amount.", { brand, days }),
      more: {
        title: t("After {days} days", { days }),
        text: t("Day {days} is the last day: you can still withdraw the money until the end of that day (Europe/Zurich), but you can no longer invest it. The next day we send it back automatically to your verified bank account. Without a verified bank account the money stays in your account and we ask you to add one. Money may not stay longer than 60 days, the legal limit: after day 60 it enters penalty mode and money-moving actions are blocked until a verified bank account is on file.", { days })
      },
      links: [
        { label: t("Account"), to: "balances" },
        { label: t("Bank accounts"), to: "settings", params: { tab: "bank-accounts" } }
      ]
    },
    {
      id: "interest",
      topic: "money",
      question: t("How is my interest calculated?"),
      answer: t("Interest is calculated on the principal still owed to you, at the loan's annual interest rate, and paid on the dates of your payment schedule. As principal is repaid, the amount earning interest goes down."),
      more: {
        title: t("Interest when an investment is sold"),
        text: t("If you sell on the Resale market, the buyer pays you the interest accrued since the last payment, on top of the price.")
      },
      links: [{ label: t("My investments"), to: "portfolio" }]
    },
    {
      id: "ownership",
      topic: "investing",
      question: t("What do I own when I invest?"),
      answer: t("You acquire a share of a company's loan: the right to receive your share of its repayments. {brand} administers the loan and collects the payments.", { brand }),
      more: {
        title: t("How is this recorded?"),
        text: t("The documents you accept when you invest describe the loan and your share. They are kept in Documents with the version you accepted and the time.")
      },
      links: [{ label: t("Documents"), to: "documents" }]
    },
    {
      id: "documents",
      topic: "documents",
      question: t("Where can I find my agreements and reports?"),
      answer: t("Documents lists the agreements you have accepted, with their version and date. Reports has your account statements and annual tax information. Information and documents about a project are on its opportunity page."),
      links: [
        { label: t("Documents"), to: "documents" },
        { label: t("Reports"), to: "reports" }
      ]
    },
    {
      id: "bank",
      topic: "security",
      question: t("How do I change my bank account?"),
      answer: t("Open Bank accounts in Profile & Settings and choose Add a bank account. The account must be in your name. You confirm with an email code and your PIN. Our team checks the new account: it shows Pending verification until then and cannot be used for withdrawals before. Your verified accounts stay usable meanwhile."),
      links: [{ label: t("Bank accounts"), to: "settings", params: { tab: "bank-accounts" } }]
    },
    {
      id: "pin",
      topic: "security",
      question: t("What if I forget my PIN?"),
      answer: t("Choose Forgot PIN in Security settings, or next to the PIN field when you confirm an action. You confirm with a code sent to your email and a code sent by SMS to your verified phone, then choose a new PIN."),
      links: [{ label: t("Security settings"), to: "settings", params: { tab: "security" } }]
    },
    {
      id: "access",
      topic: "security",
      question: t("What if I lose access to my email or phone?"),
      answer: t("You sign in with a link sent to your email, and some changes need an SMS code to your verified phone. If you lose access to either, contact support. We verify your identity before we change anything. Never include your PIN or a code in a message."),
      links: [{ label: t("Security settings"), to: "settings", params: { tab: "security" } }],
      contact: "Security"
    },
    {
      id: "emails",
      topic: "security",
      question: t("How do I change my notifications?"),
      answer: t("Emails about your investments, repayments, documents, money going back to your bank and security are always sent. In Notification settings you choose whether you also receive News from {brand}. Your notification history is in Notifications.", { brand }),
      links: [
        { label: t("Notification settings"), to: "settings", params: { tab: "notifications" } },
        { label: t("Notifications"), to: "notifications" }
      ]
    }
  ];
  if (fxEnabled) {
    questions.splice(12, 0, {
      id: "fx",
      topic: "money",
      question: t("Does exchanging currency reset the holding time?"),
      answer: t("No. Exchanged money keeps the holding time of the money you exchanged; it never gets a new {days}-day period.", { days }),
      links: [{ label: t("Account"), to: "balances" }]
    });
  }
  return questions;
}

/** Search as the design does it: case and accents ignored, every word of the question and answer. */
export function normaliseHelpText(value: string) {
  return value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function matchesHelpQuestion(item: HelpQuestion, topic: "all" | HelpTopic, search: string) {
  if (topic !== "all" && item.topic !== topic) return false;
  const needle = normaliseHelpText(search).trim();
  if (!needle) return true;
  const haystack = normaliseHelpText([item.question, item.answer, item.more?.title ?? "", item.more?.text ?? "", ...item.links.map((link) => link.label)].join(" "));
  return haystack.includes(needle);
}
