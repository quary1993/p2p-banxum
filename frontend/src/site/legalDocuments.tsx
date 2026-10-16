// IP of Webby-Soft SRL.
/*
 * The backend's published legal templates on the public site (/legal/registration,
 * /legal/risk-disclosure...): the current version of a category, its body rendered as site prose
 * and the PDF download. The investor flows link to these addresses (App.tsx legalDocumentPath and
 * LegalDocLink); site/pages/Legal.tsx shows them in the design's legal layout.
 *
 * Moved from App.tsx (renderLegalBody, the PDF download of LegalDocumentPage) when the old public
 * shell was removed; the parsing is unchanged. Tables use the design's site-table classes.
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

/**
 * A template body (headings "#", "##", paragraphs, "-" lists, pipe tables) as React nodes. The
 * text stays plain text (never HTML). Known variables are filled in, other {{ x }} show as [x]:
 * they are filled with the transaction's data when a document is accepted.
 */
export function renderLegalBody(body: string): ReactNode {
  const resolved = body
    .replace(/\{\{\s*platform\.name\s*\}\}/g, platformName)
    .replace(/\{\{\s*operator\.name\s*\}\}/g, operatorName)
    .replace(/\{\{\s*platform\.support_email\s*\}\}/g, legalSupportEmail)
    .replace(/\{\{\s*([\w.]+)\s*\}\}/g, "[$1]");
  return resolved.split(/\n\n+/).map((rawBlock, index) => {
    const block = rawBlock.trim();
    if (!block) return null;
    const heading = block.match(/^(#{1,3})\s+([\s\S]*)$/);
    if (heading) {
      const text = heading[2].trim();
      return heading[1].length === 1 ? <h2 key={index}>{text}</h2> : <h3 key={index}>{text}</h3>;
    }
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
      return (
        <div className="site-table-scroll mt-4 mb-4" key={index}>
          <table className="site-table">
            <thead>
              <tr>
                {head.map((cell, cellIndex) => (
                  <th key={cellIndex}>{cell}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rest
                .filter((cells) => !cells.every((cell) => /^[-\s:]*$/.test(cell)))
                .map((cells, rowIndex) => (
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
    }
    if (lines.length > 0 && lines.every((line) => /^[-*]\s+/.test(line))) {
      return (
        <ul key={index}>
          {lines.map((line, lineIndex) => (
            <li key={lineIndex}>{line.replace(/^[-*]\s+/, "")}</li>
          ))}
        </ul>
      );
    }
    return <p key={index}>{block}</p>;
  });
}
