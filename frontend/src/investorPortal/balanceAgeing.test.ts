// IP of Webby-Soft SRL.
import { describe, expect, test } from "vitest";

import { AUTO_RETURN_AFTER_DAYS, autoReturnDays, autoReturnRuleText, lotAgeLines } from "./balanceAgeing";

describe("balance ageing texts (18.4: day 56 last day, return on day 57)", () => {
  test("the day count comes from the API, with 56 as the default", () => {
    expect(AUTO_RETURN_AFTER_DAYS).toBe(56);
    expect(autoReturnDays(55)).toBe(55);
    for (const value of [undefined, null, 0, -1, 1.5]) expect(autoReturnDays(value)).toBe(56);
    expect(autoReturnRuleText()).toBe("Money that is not invested can stay until day 56. Then it goes back to your bank automatically.");
  });

  test("a lot shows its time left, its last day and when the return is due", () => {
    expect(lotAgeLines({ days_until_last_day: 3, return_date: "2026-03-01", return_failed: false })).toEqual({
      status: "3d holding time left",
      detail: "Goes back to your bank on 1 Mar 2026"
    });
    expect(lotAgeLines({ days_until_last_day: 0, return_date: "2026-03-01", return_failed: false })).toEqual({
      status: "Last day",
      detail: "Goes back to your bank on 1 Mar 2026"
    });
    expect(lotAgeLines({ days_until_last_day: -1, return_date: "2026-03-01", return_failed: false })).toEqual({
      status: "Due back to your bank",
      detail: "Return due since 1 Mar 2026"
    });
    expect(lotAgeLines({ days_until_last_day: -3, return_date: "2026-03-01", return_failed: true })).toEqual({
      status: "Return failed",
      detail: "Your bank sent the money back"
    });
  });
});
