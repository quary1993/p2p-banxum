// IP of Webby-Soft SRL.
// 18.10 (Q12): Profile & Settings -> Declarations. Without a declaration the investor sees why and
// fills the form; the answers are sent as one new version, and a review in progress is explained.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { emptyCalls, investorShellHandlers, renderLiveApp, type RecordedCalls } from "./test/liveInvestor";

vi.stubEnv("MODE", "development");
vi.stubEnv("VITE_PREVIEW", "false");

let App: ComponentType;
beforeAll(async () => {
  App = (await import("./App")).App;
});

let calls: RecordedCalls;
beforeEach(() => {
  calls = emptyCalls("declarations");
});

const EMPTY = {
  declaration: null,
  review_open: false,
  review_status: null,
  review_message: "",
  reverification_due_date: null,
  investment_block: "declaration_missing",
  investment_block_message: "Complete your declarations (Settings > Declarations) before your next investment."
};

test("an investor without declarations fills the form and the answers are sent as one version", async () => {
  let state: Record<string, unknown> = EMPTY;
  server.use(
    ...investorShellHandlers(calls),
    http.get("*/api/v1/kyc/declarations/", () => HttpResponse.json(state)),
    http.post("*/api/v1/kyc/declarations/", async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      calls.declarations.push(body);
      state = {
        ...EMPTY,
        declaration: {
          id: "d1",
          version: 1,
          subject_type: "person",
          beneficial_owner_is_self: true,
          beneficial_owner_name: "",
          sources_of_funds: body.sources_of_funds,
          savings_origin: body.savings_origin,
          source_other_text: "",
          pep_status: "not_sure",
          pep_person: "",
          pep_relation: "",
          pep_function: "",
          pep_country: "",
          yearly_volume_band: "10k_50k",
          company_details: {},
          review_triggers: ["pep"],
          submitted_at: "2026-11-20T08:00:00Z"
        },
        review_open: true,
        review_status: "open",
        investment_block: "compliance_review_open",
        investment_block_message: "Our compliance team is reviewing your declarations."
      };
      return HttpResponse.json(state, { status: 201 });
    })
  );
  renderLiveApp(App, "/settings/declarations");
  expect(await screen.findByText("Complete your declarations", {}, { timeout: 5000 })).toBeInTheDocument();
  const form = screen.getByRole("form", { name: "Declarations" });
  fireEvent.click(within(form).getByRole("checkbox", { name: "Salary" }));
  fireEvent.click(within(form).getByRole("checkbox", { name: "Savings" }));
  fireEvent.change(within(form).getByRole("textbox", { name: "Where do the savings come from?" }), { target: { value: "Salary saved since 2015" } });
  fireEvent.click(within(form).getByRole("radio", { name: "Not sure" }));
  fireEvent.change(within(form).getByRole("combobox", { name: "Expected yearly investment volume" }), { target: { value: "10k_50k" } });
  fireEvent.click(within(form).getByRole("button", { name: "Save declarations" }));

  await waitFor(() => expect(calls.declarations).toHaveLength(1));
  expect(calls.declarations[0]).toMatchObject({
    subject_type: "person",
    beneficial_owner_is_self: true,
    sources_of_funds: ["salary", "savings"],
    savings_origin: "Salary saved since 2015",
    pep_status: "not_sure",
    yearly_volume_band: "10k_50k"
  });
  expect(await screen.findByText("Compliance review in progress")).toBeInTheDocument();
  expect(screen.getByText("Version 1 · 20 Nov 2026")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Update declarations" })).toBeInTheDocument();
}, 30_000);
