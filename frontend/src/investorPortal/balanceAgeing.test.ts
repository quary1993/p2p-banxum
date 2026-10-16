// IP of Webby-Soft SRL.
import { describe, expect, test } from "vitest";

import { AUTO_RETURN_AFTER_DAYS, autoReturnDays, autoReturnRuleText, lotAgeLines } from "./balanceAgeing";

describe("balance ageing texts (58-day automatic return)", () => {
  test("the day count comes from the API, with 58 as the default", () => {
    expect(AUTO_RETURN_AFTER_DAYS).toBe(58);
    expect(autoReturnDays(55)).toBe(55);
    for (const value of [undefined, null, 0, -1, 1.5]) expect(autoReturnDays(value)).toBe(58);
    expect(autoReturnRuleText()).toBe("Money that is not invested goes back to your bank automatically after 58 days.");
  });

  test("a lot shows its time left, its last day and when the return is due", () => {
    expect(lotAgeLines({ days_until_last_day: 3, return_date: "2026-03-01" }, 58)).toEqual({
      status: "3d holding time left",
      detail: "Goes back to your bank on 01 Mar 2026"
    });
    expect(lotAgeLines({ days_until_last_day: 0, return_date: "2026-03-01" }, 58)).toEqual({
      status: "Day 58: last day",
      detail: "Goes back to your bank on 01 Mar 2026"
    });
    expect(lotAgeLines({ days_until_last_day: -1, return_date: "2026-03-01" }, 58)).toEqual({
      status: "Due back to your bank",
      detail: "Return due since 01 Mar 2026"
    });
  });
});
