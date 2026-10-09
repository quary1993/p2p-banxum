import { describe, expect, test } from "vitest";

import type { Holding, PortfolioInstallment } from "../api/generated/banxumApi";
import {
  completedHoldingLabel,
  completedHoldings,
  defaultSelectedPaymentKey,
  installmentProgress,
  scheduleRowStatus
} from "./holdingProgress";

function row(overrides: Partial<PortfolioInstallment>): PortfolioInstallment {
  return {
    id: "row",
    schedule_version: 1,
    installment_number: 1,
    due_date: "2026-11-19",
    principal_minor: 0,
    interest_minor: 0,
    total_minor: 0,
    paid_principal_minor: 0,
    paid_interest_minor: 0,
    outstanding_principal_minor: 0,
    outstanding_interest_minor: 0,
    outstanding_total_minor: 0,
    is_paid: false,
    days_past_due: 0,
    status: "upcoming",
    row_type: "scheduled_installment",
    label: "Installment",
    payment_date: null,
    ...overrides
  };
}

// A repaid LO loan: three recorded payments (no installment number) and three schedule rows.
const repaidLoanSchedule = [
  row({ id: "p1", installment_number: 0, row_type: "repayment_event", is_paid: true, status: "paid" }),
  row({ id: "s1", installment_number: 1, row_type: "originator_schedule", is_paid: true, status: "historical" }),
  row({ id: "p2", installment_number: 0, row_type: "repayment_event", is_paid: true, status: "paid" }),
  row({ id: "s2", installment_number: 2, row_type: "originator_schedule", is_paid: true, status: "historical" }),
  row({ id: "p3", installment_number: 0, row_type: "repayment_event", is_paid: true, status: "paid" }),
  row({ id: "s3", installment_number: 3, row_type: "originator_schedule", is_paid: true, status: "historical" })
];

describe("installment progress", () => {
  test("counts installments, not payment rows (3 of 3, not 6 of 6)", () => {
    expect(installmentProgress(repaidLoanSchedule)).toEqual({ paid: 3, total: 3 });
  });

  test("a part-paid installment is not paid", () => {
    const rows = [
      row({ id: "e1", installment_number: 1, row_type: "repayment_event", is_paid: true, status: "paid" }),
      row({ id: "r1", installment_number: 1, status: "overdue" }),
      row({ id: "i2", installment_number: 2 })
    ];
    expect(installmentProgress(rows)).toEqual({ paid: 0, total: 2 });
  });
});

describe("selected payment of a defaulted loan", () => {
  const schedule = [
    row({ id: "i1", installment_number: 1, due_date: "2026-11-11", status: "overdue" }),
    row({ id: "i2", installment_number: 2, due_date: "2026-12-11", status: "upcoming" }),
    row({ id: "i3", installment_number: 3, due_date: "2027-01-11", status: "upcoming" })
  ];

  test("opens on the overdue payment, not an upcoming one", () => {
    expect(defaultSelectedPaymentKey({ loan_status: "defaulted" }, schedule, null)).toBe("loan:i1");
    expect(defaultSelectedPaymentKey({ loan_status: "defaulted" }, schedule, "proj-2")).toBe("loan:i1");
  });

  test("a performing loan still opens on its next projected payment", () => {
    expect(defaultSelectedPaymentKey({ loan_status: "active" }, schedule, "proj-2")).toBe("projection:proj-2");
  });

  test("future rows of a loan in default are not expected", () => {
    expect(scheduleRowStatus({ status: "upcoming" }, { loan_status: "defaulted" })).toBe("not_expected");
    expect(scheduleRowStatus({ status: "overdue" }, { loan_status: "defaulted" })).toBe("overdue");
    expect(scheduleRowStatus({ status: "upcoming" }, { loan_status: "active" })).toBe("upcoming");
  });

  test("a repaid loan opens on its last payment", () => {
    expect(defaultSelectedPaymentKey({ loan_status: "repaid" }, repaidLoanSchedule, null)).toBe("loan:s3");
  });
});

describe("completed holdings", () => {
  const base = { current_principal_minor: 0, loan: { loan_status: "repaid" } };
  const holdings = [
    { ...base, id: "open", status: "active", current_principal_minor: 100 },
    { ...base, id: "repaid", status: "closed" },
    { ...base, id: "sold", status: "transferred", loan: { loan_status: "active" } }
  ] as unknown as Holding[];

  test("lists repaid and sold holdings only", () => {
    expect(completedHoldings(holdings).map((holding) => holding.id)).toEqual(["repaid", "sold"]);
    expect(completedHoldings(holdings).map(completedHoldingLabel)).toEqual(["Repaid", "Sold"]);
  });
});
