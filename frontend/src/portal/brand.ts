// IP of Webby-Soft SRL.
// Brand and operator names of the investor area: configurable (AGENTS.md branding rule), same env
// values as App.tsx. U33-DEC-34: the interface says "Banxum"; the operator line names Garanta.
export const platformName: string = import.meta.env.VITE_PLATFORM_BRAND_NAME ?? "BANXUM";
export const operatorName: string = import.meta.env.VITE_LEGAL_OPERATOR_NAME ?? "Garanta Finanzgruppe AG";

/** The brand as the U33 interface writes it: "Banxum" (the configured name when it is another brand). */
export function brandDisplayName() {
  return platformName.toUpperCase() === "BANXUM" ? "Banxum" : platformName;
}

/** True when the Banxum logo files apply (another configured brand shows its name as text). */
export function isBanxumBrand() {
  return platformName.toUpperCase() === "BANXUM";
}
