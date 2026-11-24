// IP of Webby-Soft SRL.
const names: Record<string, string> = {
  AT: "Austria", BE: "Belgium", CH: "Switzerland", DE: "Germany", ES: "Spain",
  FR: "France", IT: "Italy", LI: "Liechtenstein", LU: "Luxembourg",
  NL: "Netherlands", PL: "Poland", PT: "Portugal", RO: "Romania"
};
const codes = new Map(Object.entries(names).map(([code, name]) => [name.toUpperCase(), code]));

export function countryKey(raw: string | null | undefined) {
  const value = raw?.trim().toUpperCase() ?? "";
  return codes.get(value) ?? value;
}

export function countryLabel(raw: string | null | undefined) {
  const key = countryKey(raw);
  if (names[key]) return names[key];
  if (/^[A-Z]{2}$/.test(key) && typeof Intl.DisplayNames === "function") {
    return new Intl.DisplayNames(["en"], { type: "region" }).of(key) ?? key;
  }
  return raw?.trim() ?? "";
}
