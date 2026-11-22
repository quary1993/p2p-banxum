// IP of Webby-Soft SRL.
// Which document a /legal/<slug> address shows (u33/pages/Legal.tsx): a content.ts document,
// a backend template category, or both (terms -> registration, risk -> risk_disclosure).
import type { CategoryEnum } from "../../api/generated/banxumApi";
import { siteLegal, type SiteLegalDoc } from "../content";
import { legalTemplateCategory } from "../legalDocuments";

/** Documents whose text is a published backend template once there is one. */
const DESIGN_TEMPLATES: Record<string, CategoryEnum> = { terms: "registration", risk: "risk_disclosure" };
const TEMPLATE_DESIGNS: Partial<Record<CategoryEnum, string>> = { registration: "terms", risk_disclosure: "risk" };

export type LegalRoute = { design: SiteLegalDoc | null; category: CategoryEnum | null };

export function legalRoute(slug: string): LegalRoute | null {
  const design = siteLegal.find((item) => item.id === slug);
  if (design) return { design, category: DESIGN_TEMPLATES[design.id] ?? null };
  const category = legalTemplateCategory(slug);
  if (!category) return null;
  const designId = TEMPLATE_DESIGNS[category];
  return { design: siteLegal.find((item) => item.id === designId) ?? null, category };
}

/** Whether /legal/<slug> has a page (else the 404). */
export function isPublicLegalDocument(slug: string) {
  return legalRoute(slug) !== null;
}
