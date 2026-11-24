// IP of Webby-Soft SRL.
// 18.10 (Q12): Profile & Settings -> Declarations. Without a declaration the investor sees why and
// fills the form; the answers are sent as one new version, and a review in progress is explained.
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ComponentType } from "react";
import { beforeAll, beforeEach, expect, test, vi } from "vitest";

import { server } from "./api/mocks/server";
import { getV1KycDeclarationsRetrieveQueryKey } from "./api/generated/banxumApi";
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
  declaration_subject: "person",
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
  const { queryClient } = renderLiveApp(App, "/settings/declarations");
  expect(await screen.findByText("Complete your declarations", {}, { timeout: 5000 })).toBeInTheDocument();
  const form = screen.getByRole("form", { name: "Declarations" });
  fireEvent.click(within(form).getByRole("checkbox", { name: "Salary" }));
  fireEvent.click(within(form).getByRole("checkbox", { name: "Savings" }));
  fireEvent.change(within(form).getByRole("textbox", { name: "Where do the savings come from?" }), { target: { value: "Salary saved since 2015" } });
  fireEvent.click(within(form).getByRole("radio", { name: "Not sure" }));
  fireEvent.change(within(form).getByRole("combobox", { name: "Expected yearly investment volume" }), { target: { value: "10k_50k" } });
  state = { ...EMPTY, reverification_due_date: "2026-12-15" };
  await act(async () => { await queryClient.refetchQueries({ queryKey: getV1KycDeclarationsRetrieveQueryKey() }); });
  expect(within(form).getByRole("textbox", { name: "Where do the savings come from?" })).toHaveValue("Salary saved since 2015");
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

test("audit S7-1: a company account gets the company declaration without a person choice", async () => {
  server.use(
    ...investorShellHandlers(calls),
    http.get("*/api/v1/kyc/declarations/", () => HttpResponse.json({ ...EMPTY, declaration_subject: "company" })),
    http.post("*/api/v1/kyc/declarations/", async ({ request }) => {
      calls.declarations.push((await request.json()) as Record<string, unknown>);
      return HttpResponse.json({ detail: "stop" }, { status: 400 });
    })
  );
  renderLiveApp(App, "/settings/declarations");
  const form = await screen.findByRole("form", { name: "Declarations" }, { timeout: 5000 });
  expect(within(form).getByText("A company invests (company account).")).toBeInTheDocument();
  expect(within(form).queryByRole("radio", { name: /private person/i })).not.toBeInTheDocument();
  fireEvent.change(within(form).getByRole("textbox", { name: "Company name" }), { target: { value: "Example Holding AG" } });
  fireEvent.click(within(form).getByRole("checkbox", { name: "Salary" }));
  fireEvent.click(within(form).getByRole("radio", { name: "Not sure" }));
  fireEvent.change(within(form).getByRole("combobox", { name: "Expected yearly investment volume" }), { target: { value: "10k_50k" } });
  fireEvent.click(within(form).getByRole("button", { name: "Save declarations" }));
  await waitFor(() => expect(calls.declarations).toHaveLength(1));
  expect(calls.declarations[0]).toMatchObject({
    subject_type: "company",
    company_details: expect.objectContaining({ company_name: "Example Holding AG" })
  });
}, 30_000);

test("18.11: the Overview shows a re-verification date and a review in progress", async () => {
  server.use(
    ...investorShellHandlers(calls),
    http.get("*/api/v1/kyc/declarations/", () =>
      HttpResponse.json({ ...EMPTY, declaration: null, investment_block: null, investment_block_message: "", reverification_due_date: "2026-12-15" })
    )
  );
  renderLiveApp(App, "/dashboard");
  expect(await screen.findByText("Re-verification due by 15 Dec 2026.", {}, { timeout: 5000 })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open declarations" })).toHaveAttribute("href", "/settings/declarations");
}, 30_000);
