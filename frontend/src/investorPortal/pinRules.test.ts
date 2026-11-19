// IP of Webby-Soft SRL.
// The PIN rules the portal checks before it asks the server (ACC-DEC-009; same rules as
// accounts_auth.pin_services). The old-skin six-box PIN input was removed in the S7 clean-up.
import { expect, test } from "vitest";

import { pinWeakness } from "./pinRules";

test("weak PINs follow the server rules", () => {
  for (const pin of ["000000", "111111", "123456", "654321", "012345", "987654"]) {
    expect(pinWeakness(pin)).not.toBeNull();
  }
  for (const pin of ["482916", "246810", "112233", "123465"]) {
    expect(pinWeakness(pin)).toBeNull();
  }
  expect(pinWeakness("12345")).toBe("Your PIN must be exactly 6 digits.");
});
