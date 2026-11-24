import { expect, test } from "vitest";
import { countryKey, countryLabel } from "./countries";

test("imported country names and codes share one filter key and label", () => {
  const countries = [" Switzerland ", "ch", "Germany", " de "];
  expect([...new Set(countries.map(countryKey))]).toEqual(["CH", "DE"]);
  expect(countries.map(countryLabel)).toEqual(["Switzerland", "Switzerland", "Germany", "Germany"]);
  expect(countryLabel(null)).toBe("");
});
