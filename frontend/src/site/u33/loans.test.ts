// IP of Webby-Soft SRL.
// 18.3: the public asset name of a project (the admin's anonymous name, else the type).
import { expect, test } from "vitest";

import { projectAssetName } from "./loans";

test("the public site names the main asset as entered, else by its type", () => {
  expect(projectAssetName({ collateral_type: "real_estate", security_public_name: "Residential building in Biel" })).toBe("Residential building in Biel");
  expect(projectAssetName({ collateral_type: "real_estate", security_public_name: "  " })).toBe("Property");
  expect(projectAssetName({ collateral_type: "equipment" })).toBe("Equipment");
});
