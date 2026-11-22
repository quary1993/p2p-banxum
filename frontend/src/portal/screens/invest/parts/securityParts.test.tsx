// IP of Webby-Soft SRL.
// C06 / F16: the main security, the assets in the loan-to-value and a valuation in another currency.
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import type { MarketplaceSecurity } from "../../../../api/generated/banxumApi";
import { LtvAssets, SecurityFacts } from "./SecurityDetails";
import { splitSecurities } from "./securityParts";

const base: MarketplaceSecurity = {
  id: "s1",
  position: 0,
  security_type: "real_estate",
  is_guarantee: false,
  description: "",
  holder_name: "",
  rank: null,
  status: "in_place",
  value_minor: 200_000_00,
  valuation_date: "2026-03-12",
  valuation_source: "",
  appraiser: "",
  prior_ranking_debt_minor: null,
  insurance: "",
  undertaking_scope: "",
  undertaking_limit_minor: null,
  is_main: false,
  counts_in_ltv: true,
  valuation_currency: "",
  valuation_amount_minor: null,
  valuation_fx_rate: null,
  valuation_fx_rate_date: null,
  documents: []
};

test("the main security is the chosen one; guarantees, released and excluded values do not count", () => {
  const securities: MarketplaceSecurity[] = [
    base,
    { ...base, id: "s2", position: 1, security_type: "equipment", is_main: true, value_minor: 50_000_00 },
    { ...base, id: "s3", position: 2, security_type: "personal_guarantee", is_guarantee: true, value_minor: null, counts_in_ltv: false },
    { ...base, id: "s4", position: 3, security_type: "inventory", status: "released" },
    { ...base, id: "s5", position: 4, security_type: "receivables", counts_in_ltv: false }
  ];
  const parts = splitSecurities(securities);
  expect(parts.main?.id).toBe("s2");
  expect(parts.others.map((item) => item.id)).toEqual(["s1", "s3", "s4", "s5"]);
  expect(parts.counted.map((item) => item.id)).toEqual(["s1", "s2"]);

  render(<LtvAssets counted={parts.counted} currency="CHF" main={parts.main} />);
  expect(screen.getByText("The loan-to-value uses the sum of these values:")).toBeInTheDocument();
  expect(screen.getAllByRole("listitem")).toHaveLength(2);
});

test("one counted main security needs no list; a valuation in another currency shows its amount and rate", () => {
  const main = { ...base, is_main: true };
  const { container } = render(<LtvAssets counted={[main]} currency="CHF" main={main} />);
  expect(container).toBeEmptyDOMElement();

  render(
    <SecurityFacts
      currency="CHF"
      loanMinor={100_000_00}
      security={{ ...base, valuation_currency: "EUR", valuation_amount_minor: 100_000_00, valuation_fx_rate: "0.95000000", valuation_fx_rate_date: "2026-11-02", value_minor: 95_000_00 }}
    />
  );
  expect(screen.getByText("Valuation in EUR").nextElementSibling?.textContent).toMatch(/EUR 100.000.00 at a rate of 0.95/);
  expect(screen.getByText("In the loan-to-value").nextElementSibling).toHaveTextContent("Yes");
});
