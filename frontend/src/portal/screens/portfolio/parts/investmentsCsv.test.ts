// IP of Webby-Soft SRL.
// "Download schedule" of the investment page (design data-action="export-schedule").
import { describe, expect, test } from "vitest";

import type { Holding } from "../../../../api/generated/banxumApi";
import { portfolioFixture } from "../../../../investorPortal/fixtures";
import { hasScheduleRows, scheduleCsv } from "./investmentsCsv";

function fixture(id: string): Holding {
  const holding = portfolioFixture.holdings.find((candidate) => candidate.id === id);
  if (!holding) throw new Error(`Missing fixture holding ${id}`);
  return holding;
}

describe("scheduleCsv", () => {
  test("has the design's columns, the received total and the remaining payments", () => {
    const lines = scheduleCsv(fixture("H-2410"), "european", (text) => text).split("\r\n");
    expect(lines[0]).toBe("#;Due;Principal;Interest;Total;Principal left;Status");
    // Older records without per-payment rows: one "Received to date" line (as on the page).
    expect(lines[1]).toBe(";Received to date;337,00;83,00;420,00;;Paid");
    expect(lines[2]).toMatch(/^\d+;2026-11-26;170,40;39,66;210,06;[\d,]+;Scheduled$/);
    expect(lines.length).toBeGreaterThan(3);
  });

  test("uses the Swiss separators and keeps only received rows for a sold investment", () => {
    const sold = fixture("H-2199");
    const csv = scheduleCsv(sold, "swiss", (text) => text);
    expect(csv.split("\r\n")[0]).toBe("#,Due,Principal,Interest,Total,Principal left,Status");
    expect(csv).not.toMatch(/Scheduled/);
    expect(hasScheduleRows(sold)).toBe(true);
  });
});
