// IP of Webby-Soft SRL.
import { expect, test } from "vitest";

import { ratio } from "./financialRatio";

test("C07: n/a for missing data or a divisor that is not positive; coverage uses the absolute expense", () => {
  expect(ratio(null, 100, "%")).toBe("n/a");
  expect(ratio(50, undefined, "×")).toBe("n/a");
  expect(ratio(50, 0, "×")).toBe("n/a");
  expect(ratio(50, -10, "×")).toBe("n/a");
  expect(ratio(1_050, -160, "×", { absolute: true })).toMatch(/^6.56×$/);
  expect(ratio(1_050, 160, "×", { absolute: true })).toMatch(/^6.56×$/);
  expect(ratio(-200, 160, "×", { absolute: true })).toMatch(/^-1.25×$/);
});
