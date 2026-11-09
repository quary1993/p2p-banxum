// IP of Webby-Soft SRL.
/*
 * The backend's published legal templates on the public site (/legal/registration,
 * /legal/risk-disclosure...): the current version of a category, its body split into numbered
 * sections and the PDF download. The investor flows link to these addresses (App.tsx
 * legalDocumentPath and LegalDocLink); site/u33/pages/Legal.tsx shows them in the U33 legal
 * layout. Tables keep the class site-table.
 */
import type { ReactNode } from "react";

import {
  useV1DocumentsTemplatesCurrentRetrieve,
  v1DocumentsTemplatesCurrentArtifactRetrieve,
  type CategoryEnum
} from "../api/generated/banxumApi";
import { isFixturePreview } from "../investorPortal/data";

const platformName = import.meta.env.VITE_PLATFORM_BRAND_NAME ?? "BANXUM";
const operatorName = import.meta.env.VITE_LEGAL_OPERATOR_NAME ?? "Garanta Finanzgruppe AG";
export const legalSupportEmail = import.meta.env.VITE_SUPPORT_EMAIL ?? "support@banxum.com";

/** Backend categories and the names shown before the published title is known. */
export const legalTemplateTitles: Record<CategoryEnum, string> = {
  registration: "Lender user agreement",
  primary_market_investment: "Investment terms and loan claim assignment",
  secondary_market_listing: "Secondary-market seller/listing terms",
  secondary_market_purchase: "Secondary-market buyer terms",
  risk_disclosure: "Generic P2P lending risk disclosure"
};

/** "/legal/<slug>" of a backend category (risk_disclosure -> risk-disclosure). */
export function legalTemplateCategory(slug: string): CategoryEnum | null {
  const category = slug.replace(/-/g, "_");
  return category in legalTemplateTitles ? (category as CategoryEnum) : null;
}

/**
 * The current published version of a category. Preview mode (fixtures) never asks the backend:
 * the site shows the design's texts instead. A 404 means "not published yet".
 */
export function useLegalTemplate(category: CategoryEnum | null) {
  return useV1DocumentsTemplatesCurrentRetrieve(
    { category: category ?? "registration", template_key: "default", language: "en" },
    { query: { enabled: !isFixturePreview && category !== null, retry: false, staleTime: 60_000 } }
  );
}

/** Whether the backend document query runs at all (false in preview mode). */
export const legalTemplatesLive = !isFixturePreview;

/** Downloads the PDF of the current published version (the old LegalDocumentPage download). */
export async function downloadLegalTemplatePdf(category: CategoryEnum) {
  const payload = await v1DocumentsTemplatesCurrentArtifactRetrieve({ category, template_key: "default", language: "en" });
  const bytes = Uint8Array.from(atob(payload.content), (char) => char.charCodeAt(0));
  const blob = new Blob([bytes], { type: payload.content_type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = payload.filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

/** Known template variables filled in; the others show as [x] (filled when a document is accepted). */
export function resolveLegalBody(body: string) {
  return body
    .replace(/\{\{\s*platform\.name\s*\}\}/g, platformName)
    .replace(/\{\{\s*operator\.name\s*\}\}/g, operatorName)
    .replace(/\{\{\s*platform\.support_email\s*\}\}/g, legalSupportEmail)
    .replace(/\{\{\s*([\w.]+)\s*\}\}/g, "[$1]");
}

export type LegalBlock =
  | { type: "p"; text: string }
  | { type: "h3"; text: string }
  | { type: "ul"; items: string[] }
  | { type: "table"; head: string[]; rows: string[][] };

export type LegalSection = { heading: string; blocks: LegalBlock[] };

/**
 * A template body (headings "#", "##", paragraphs, "-" lists, pipe tables; plain text, never
 * HTML) as numbered sections: the highest heading level of the body starts a section, deeper
 * headings become sub-headings. Text before the first heading is the introduction.
 */
export function legalDocumentSections(body: string): { intro: LegalBlock[]; sections: LegalSection[] } {
  const raw = resolveLegalBody(body)
    .split(/\n\n+/)
    .map((block) => block.trim())
    .filter(Boolean);
  const levels = raw.map((block) => block.match(/^(#{1,3})\s+/)?.[1].length ?? 0).filter(Boolean);
  const sectionLevel = levels.length ? Math.min(...levels) : 0;
  const intro: LegalBlock[] = [];
  const sections: LegalSection[] = [];
  for (const block of raw) {
    const heading = block.match(/^(#{1,3})\s+([\s\S]*)$/);
    if (heading) {
      const text = heading[2].trim();
      if (heading[1].length === sectionLevel) sections.push({ heading: text, blocks: [] });
      else (sections.length ? sections[sections.length - 1].blocks : intro).push({ type: "h3", text });
      continue;
    }
    (sections.length ? sections[sections.length - 1].blocks : intro).push(parseLegalBlock(block));
  }
  return { intro, sections };
}

function parseLegalBlock(block: string): LegalBlock {
  const lines = block
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length > 1 && lines.every((line) => line.startsWith("|"))) {
    const rows = lines.map((line) =>
      line
        .replace(/^\||\|$/g, "")
        .split("|")
        .map((cell) => cell.trim())
    );
    const [head, ...rest] = rows;
    return { type: "table", head, rows: rest.filter((cells) => !cells.every((cell) => /^[-\s:]*$/.test(cell))) };
  }
  if (lines.length > 0 && lines.every((line) => /^[-*]\s+/.test(line))) {
    return { type: "ul", items: lines.map((line) => line.replace(/^[-*]\s+/, "")) };
  }
  return { type: "p", text: block };
}

/** The blocks of a section as React nodes (plain text only). */
export function renderLegalBlocks(blocks: LegalBlock[]): ReactNode {
  return blocks.map((block, index) => {
    if (block.type === "h3") return <h3 key={index}>{block.text}</h3>;
    if (block.type === "ul")
      return (
        <ul key={index}>
          {block.items.map((item, itemIndex) => (
            <li key={itemIndex}>{item}</li>
          ))}
        </ul>
      );
    if (block.type === "table")
      return (
        <div className="site-table-scroll" key={index}>
          <table className="site-table">
            <thead>
              <tr>
                {block.head.map((cell, cellIndex) => (
                  <th key={cellIndex}>{cell}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((cells, rowIndex) => (
                <tr key={rowIndex}>
                  {cells.map((cell, cellIndex) => (
                    <td key={cellIndex}>{cell}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    return <p key={index}>{block.text}</p>;
  });
}
