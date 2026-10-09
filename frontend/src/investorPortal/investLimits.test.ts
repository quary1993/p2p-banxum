import { describe, expect, test } from "vitest";

import type { BalanceLot } from "../api/generated/banxumApi";
import { currencyBalanceMinor, investAmountLimitMessage, noEligibleFundsReason, sourceAgeRuleText } from "./investLimits";

const money = (amountMinor: number) => `CHF ${(amountMinor / 100).toFixed(2)}`;

describe("invest limits", () => {
  test("one unit over the remaining capacity names the capacity, not the wallet (QA E11)", () => {
    const message = investAmountLimitMessage({
      amountMinor: 250_001_00,
      capacityMinor: 250_000_00,
      currency: "CHF",
      funds: { balanceMinor: 5_000_000_00, eligibleMinor: 5_000_000_00 },
      money
    });

    expect(message).toBe("This opportunity has only CHF 250000.00 left, so that is the most you can invest here.");
  });

  test("the balance message is used only when the balance is the smaller limit", () => {
    expect(
      investAmountLimitMessage({
        amountMinor: 50_000_00,
        capacityMinor: 250_000_00,
        currency: "CHF",
        funds: { balanceMinor: 20_000_00, eligibleMinor: 20_000_00 },
        money
      })
    ).toBe("Only CHF 20000.00 is not lent — today's maximum here.");
    expect(
      investAmountLimitMessage({
        amountMinor: 10_000_00,
        capacityMinor: 250_000_00,
        currency: "CHF",
        funds: { balanceMinor: 20_000_00, eligibleMinor: 20_000_00 },
        money
      })
    ).toBeNull();
  });

  test("old funds that cannot cover the funding window are named as the limit", () => {
    expect(
      investAmountLimitMessage({
        amountMinor: 50_000_00,
        capacityMinor: 250_000_00,
        currency: "CHF",
        funds: { balanceMinor: 900_000_00, eligibleMinor: 30_000_00 },
        money
      })
    ).toMatch(/Only CHF 30000\.00 of your CHF balance has enough holding time left/);
  });

  test("no eligible funds: no balance at all differs from a balance that is too old", () => {
    expect(noEligibleFundsReason("EUR", { balanceMinor: 0, eligibleMinor: 0 })?.title).toBe(
      "No investable balance is available in this currency."
    );
    const aged = noEligibleFundsReason("EUR", { balanceMinor: 3_000_000_00, eligibleMinor: 0 });
    expect(aged?.title).toBe("Your EUR balance does not have enough holding time left for this loan's funding period.");
    expect(aged?.detail).toBe(sourceAgeRuleText);
    expect(noEligibleFundsReason("EUR", { balanceMinor: 100, eligibleMinor: 100 })).toBeNull();
  });

  test("the currency balance counts available lots of any age but not frozen or penalty lots", () => {
    const lot = (overrides: Partial<BalanceLot>) => ({ currency: "CHF", status: "available", available_amount_minor: 100, ...overrides }) as BalanceLot;

    expect(
      currencyBalanceMinor(
        [
          lot({ bucket: "investable" }),
          lot({ bucket: "overdue" }),
          lot({ status: "penalty_mode" }),
          lot({ currency: "EUR" })
        ],
        "CHF"
      )
    ).toBe(200);
  });
});
