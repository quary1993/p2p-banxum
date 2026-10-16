// IP of Webby-Soft SRL.
// Public site: Projects (filters, list, calculator), Project page and Statistics, with the
// preview fixtures (the design's sample data, TODAY 2026-09-23).
import { fireEvent, render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, test, vi } from "vitest";

import { App } from "../../App";
import { siteQueryKeys, type PublicProject } from "../data";
import { siteDesignProjectIds, siteProjectsFixture } from "../siteFixtures";
import { projectView } from "../projects";
import {
  calcAmount,
  expectedInterest,
  filterProjects,
  filtersFromQuery,
  ltvText,
  planRepaymentOf,
  purposeItems,
  securityText,
  simulate
} from "./projectHelpers";

const ID = (designId: string) => siteDesignProjectIds[designId];
const fixture = (designId: string) => siteProjectsFixture.find((p) => p.loan_id === ID(designId)) as PublicProject;

function renderSite(path: string, seed?: (client: QueryClient) => void) {
  window.history.pushState({}, "", path);
  const queryClient = new QueryClient();
  seed?.(queryClient);
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

const projectList = () => document.getElementById("site-project-list") as HTMLElement;
const cardTitles = () => Array.from(projectList().querySelectorAll(".site-project-title")).map((el) => el.textContent);
const chip = (name: RegExp) => within(screen.getByRole("group", { name: "Status" })).getByRole("button", { name });

describe("Projects page", () => {
  test("filters by status and currency, with the design's counts and order", () => {
    renderSite("/projects");
    expect(screen.getByRole("heading", { level: 1, name: "Companies looking for a loan" })).toBeInTheDocument();
    expect(chip(/^Open/)).toHaveTextContent("Open7");
    expect(chip(/^Open/)).toHaveAttribute("aria-pressed", "true");
    expect(chip(/^Coming soon/)).toHaveTextContent("Coming soon2");
    expect(chip(/^Funded/)).toHaveTextContent("Funded7");
    expect(chip(/^All/)).toHaveTextContent("All16");
    // Open projects, newest published first.
    expect(cardTitles()).toEqual([
      "Residential building completion",
      "Invoice financing, automotive supplier",
      "Machining centre purchase",
      "Solar roof for a logistics centre",
      "Dental practice equipment",
      "Packaging factory extension",
      "Wine cellar expansion"
    ]);

    fireEvent.click(chip(/^Coming soon/));
    expect(chip(/^Coming soon/)).toHaveClass("active");
    expect(chip(/^Open/)).not.toHaveClass("active");
    expect(cardTitles()).toEqual(["Co-working space fit-out", "Truck fleet renewal"]);

    fireEvent.click(chip(/^All/));
    fireEvent.change(screen.getByRole("combobox", { name: "Currency" }), { target: { value: "EUR" } });
    // Open first, then the rest (coming soon and funded) by newest publication.
    expect(cardTitles()).toEqual([
      "Invoice financing, automotive supplier",
      "Machining centre purchase",
      "Wine cellar expansion",
      "Truck fleet renewal",
      "Invoice financing, food wholesaler",
      "Hotel renovation Brașov",
      "Furniture production line",
      "Agricultural machinery",
      "Trade receivables financing"
    ]);
    expect(within(projectList()).getByText("Truck fleet renewal").closest("a")).toHaveAttribute(
      "href",
      `/projects/${ID("bx-1052")}`
    );
  });

  test("the address query sets the filters once and leaves the address; the choice is kept", () => {
    const first = renderSite("/projects?status=funded&currency=CHF");
    expect(window.location.pathname).toBe("/projects");
    expect(window.location.search).toBe("");
    expect(chip(/^Funded/)).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("combobox", { name: "Currency" })).toHaveValue("CHF");
    expect(cardTitles()).toEqual(["Bakery chain working capital", "Cold storage warehouse"]);

    // Back from a project page: the same list.
    fireEvent.click(within(projectList()).getByText("Bakery chain working capital"));
    expect(window.location.pathname).toBe(`/projects/${ID("bx-1027")}`);
    first.unmount();
    const second = renderSite("/projects");
    expect(chip(/^Funded/)).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("combobox", { name: "Currency" })).toHaveValue("CHF");
    fireEvent.click(chip(/^Open/));
    second.unmount();

    // Unknown values are ignored (and leave the address too).
    renderSite("/projects?status=nothing&currency=USD");
    expect(window.location.search).toBe("");
    expect(chip(/^Open/)).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("combobox", { name: "Currency" })).toHaveValue("CHF");
  });

  test("no match shows the design's empty box, and 'Show all projects' resets the filters", () => {
    const funded = siteProjectsFixture.filter((p) => p.public_status !== "open");
    renderSite("/projects", (client) => client.setQueryData(siteQueryKeys.projects(250), funded));
    expect(chip(/^Open/)).toHaveTextContent("Open0");
    expect(chip(/^Coming soon/)).toHaveTextContent("Coming soon0");
    expect(within(projectList()).getByText(/No projects match\./)).toBeInTheDocument();
    fireEvent.click(within(projectList()).getByRole("link", { name: "Show all projects" }));
    expect(chip(/^All/)).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("combobox", { name: "Currency" })).toHaveValue("all");
    expect(cardTitles()).toHaveLength(7);
  });

  test("the locked block, the newsletter and the risk line", () => {
    renderSite("/projects");
    expect(screen.getByRole("heading", { name: "See the full project pages" })).toBeInTheDocument();
    const locked = screen.getByRole("heading", { name: "See the full project pages" }).parentElement as HTMLElement;
    expect(within(locked).getByRole("link", { name: "Open account" })).toHaveAttribute("href", "/register");
    expect(within(locked).getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("heading", { name: "Get new projects by email" })).toBeInTheDocument();
    expect(document.getElementById("site-sub-projects")).toBeInTheDocument();
    expect(screen.getAllByText(/Lending to companies puts your capital at risk\. Read the/).length).toBeGreaterThan(0);
  });

  test("the calculator follows the amount, currency, rate, term and repayment", () => {
    renderSite("/projects");
    const calc = document.getElementById("site-calc") as HTMLElement;
    const figure = (label: string) => within(calc).getByText(label).nextElementSibling;
    expect(within(calc).getByLabelText("Amount")).toHaveValue("5,000.00");
    expect(figure("Interest before tax")).toHaveTextContent("EUR 399.76");
    expect(figure("First month")).toHaveTextContent("EUR 225.00");
    expect(figure("Total repaid")).toHaveTextContent("EUR 5,399.76");
    expect(within(calc).getByText("7.5%")).toBeInTheDocument();
    expect(within(calc).getByText("24 months")).toBeInTheDocument();
    expect(within(calc).getByText("Month 1 to 24")).toBeInTheDocument();
    expect(calc.querySelectorAll(".site-calc-bars > span")).toHaveLength(24);

    fireEvent.click(within(calc).getByRole("radio", { name: /CHF$/ }));
    fireEvent.click(within(calc).getByRole("radio", { name: "At the end" }));
    fireEvent.change(within(calc).getByLabelText("Term"), { target: { value: "6" } });
    fireEvent.change(within(calc).getByLabelText("Interest rate a year"), { target: { value: "10.2" } });
    expect(within(calc).getByText("10.2%")).toBeInTheDocument();
    expect(within(calc).getByText("6 months")).toBeInTheDocument();
    // Paid at the end: one bar per month, the last one carries everything.
    expect(calc.querySelectorAll(".site-calc-bars > span")).toHaveLength(6);
    const sim = simulate(5000, 10.2, 6, "bullet");
    expect(figure("Paid at the end")).toHaveTextContent(`CHF ${sim.total.toLocaleString("en-US", { minimumFractionDigits: 2 })}`);

    fireEvent.change(within(calc).getByLabelText("Amount"), { target: { value: "100" } });
    expect(within(calc).getByText("The minimum is CHF 1,000.00.")).toBeInTheDocument();
    fireEvent.change(within(calc).getByLabelText("Amount"), { target: { value: "12x000" } });
    expect(within(calc).getByLabelText("Amount")).toHaveValue("12000");
    fireEvent.blur(within(calc).getByLabelText("Amount"));
    expect(within(calc).getByLabelText("Amount")).toHaveValue("12,000.00");
    fireEvent.change(within(calc).getByLabelText("Amount"), { target: { value: "" } });
    expect(within(calc).getByText("Enter an amount.")).toBeInTheDocument();
  });

  test("'See open projects in <currency>' sets the filters and scrolls to them", () => {
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView");
    renderSite("/projects");
    fireEvent.click(chip(/^Funded/));
    const calc = document.getElementById("site-calc") as HTMLElement;
    fireEvent.click(within(calc).getByRole("radio", { name: /CHF$/ }));
    const link = within(calc).getByRole("link", { name: "See open projects in CHF" });
    fireEvent.click(link);
    expect(chip(/^Open/)).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("combobox", { name: "Currency" })).toHaveValue("CHF");
    expect(cardTitles()).toEqual([
      "Residential building completion",
      "Solar roof for a logistics centre",
      "Dental practice equipment",
      "Packaging factory extension"
    ]);
    expect(scroll).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });
    expect(window.location.pathname).toBe("/projects");
    scroll.mockRestore();
  });
});

describe("Project page", () => {
  test("an open project: head, facts, security, company, invest box and other projects", () => {
    renderSite(`/projects/${ID("bx-1048")}`);
    expect(document.title).toBe("Residential building completion · Banxum");
    const crumbs = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(crumbs).getByRole("link", { name: "Projects" })).toHaveAttribute("href", "/projects");
    expect(crumbs).toHaveTextContent("Projects/B0000000");
    const head = screen.getByRole("heading", { level: 1, name: "Residential building completion" }).parentElement as HTMLElement;
    expect(head.querySelector(".site-project-tags")).toHaveTextContent("Open New loan Risk B");
    expect(within(head).getByText("Switzerland · Real estate")).toBeInTheDocument();

    const facts = document.querySelector(".site-facts-grid") as HTMLElement;
    expect(facts).toHaveTextContent("Interest a year7.5%Term18 monthsAmountCHF 800kRepaymentAt the end");
    expect(screen.getByText("Interior works and façade: CHF 520,000").tagName).toBe("LI");
    expect(screen.getByText("First-rank mortgage note (Schuldbrief) on the building")).toBeInTheDocument();
    expect(screen.getByText("62%")).toBeInTheDocument();
    expect(screen.getByText("(AAA lowest, D highest)")).toBeInTheDocument();
    expect(screen.getByText("Founded").nextElementSibling).toHaveTextContent("2008");
    expect(screen.getByText("Employees").nextElementSibling).toHaveTextContent("–");
    expect(screen.getByText("Region").nextElementSibling).toHaveTextContent("Switzerland");
    expect(screen.getByText("Shown after you open an account")).toHaveClass("visually-hidden");
    expect(
      screen.getByText(
        "Garanta Finanzgruppe AG lends to the company and assigns shares of the claim to investors when the loan is funded."
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Repayment so far" })).not.toBeInTheDocument();

    const box = document.querySelector(".site-sticky") as HTMLElement;
    expect(box).toHaveTextContent("23 days left");
    expect(box).toHaveTextContent("CHF 380,000.00 funded48%");
    expect(within(box).getByText("Still to fund").nextElementSibling).toHaveTextContent("CHF 420,000.00");
    expect(within(box).getByText("Minimum now").nextElementSibling).toHaveTextContent("CHF 32,308.00");
    expect(within(box).getByRole("link", { name: "Open account to invest" })).toHaveAttribute("href", "/register");
    expect(within(box).getByRole("link", { name: "I have an account" })).toHaveAttribute("href", `/marketplace/${ID("bx-1048")}`);

    const others = screen.getByRole("heading", { name: "Other projects" }).closest("section") as HTMLElement;
    expect(Array.from(others.querySelectorAll(".site-project-title")).map((el) => el.textContent)).toEqual([
      "Packaging factory extension",
      "Wine cellar expansion",
      "Dental practice equipment"
    ]);
  });

  test("the mini calculator shows the interest and the minimum and capacity notes", () => {
    renderSite(`/projects/${ID("bx-1048")}`);
    const input = screen.getByLabelText("Your amount");
    const out = () => (document.getElementById("site-mini-calc") as HTMLElement).querySelector("p") as HTMLElement;
    expect(input).toHaveValue("32,308.00");
    expect(out()).toHaveTextContent(
      "Interest before tax over 18 months: CHF 3,637.97, counted every day, if every payment is on time. No fees."
    );
    fireEvent.change(input, { target: { value: "100" } });
    expect(out()).toHaveTextContent("The minimum now is CHF 32,308.00.");
    fireEvent.change(input, { target: { value: "500000" } });
    expect(out()).toHaveTextContent("Only CHF 420,000.00 is left.");
    fireEvent.change(input, { target: { value: "" } });
    expect(out()).toHaveTextContent(/^Enter an amount\.$/);
    fireEvent.change(input, { target: { value: "40000.5" } });
    fireEvent.blur(input);
    expect(input).toHaveValue("40,000.50");
  });

  test("a late claim: record tag, originator, repayment so far and the late notice", () => {
    renderSite(`/projects/${ID("bx-1031")}`);
    const head = screen.getByRole("heading", { level: 1, name: "Hotel renovation Brașov" }).parentElement as HTMLElement;
    expect(head.querySelector(".site-project-tags")).toHaveTextContent("Late 12 days Existing claim Risk C");
    expect(screen.getByText("Poiana Credit IFN SA").tagName).toBe("STRONG");
    expect(screen.getByText("Poiana Credit IFN SA").parentElement).toHaveTextContent(
      "The loan originator Poiana Credit IFN SA, Romania, assigns the claim to Garanta Finanzgruppe AG, which assigns shares to investors."
    );
    expect(screen.getByRole("heading", { name: "Repayment so far" })).toBeInTheDocument();
    expect(document.querySelector(".alert-warning")).toHaveTextContent(
      "One payment is late 12 days. Garanta has reminded the borrower; investors are informed of each step."
    );
    const box = document.querySelector(".site-sticky") as HTMLElement;
    expect(box).toHaveTextContent("Funding closed");
    expect(within(box).getByText("Payments made").nextElementSibling).toHaveTextContent("5 of 18");
    expect(within(box).queryByText("Still to fund")).not.toBeInTheDocument();
    expect(box).toHaveTextContent("This project is no longer open. See the open projects.");
    expect(screen.queryByLabelText("Your amount")).not.toBeInTheDocument();
  });

  test("a defaulted loan shows the default date and the public note", () => {
    renderSite(`/projects/${ID("bx-1024")}`);
    const alert = document.querySelector(".alert-danger") as HTMLElement;
    expect(within(alert).getByText("In default since 15 Jul 2026.").tagName).toBe("STRONG");
    expect(alert).toHaveTextContent(fixture("bx-1024").record?.public_note ?? "");
  });

  test("a project opening soon and a fully funded one", () => {
    const soon = renderSite(`/projects/${ID("bx-1052")}`);
    let box = document.querySelector(".site-sticky") as HTMLElement;
    expect(box).toHaveTextContent("Coming soon");
    expect(box).toHaveTextContent("Opens 28 Sep");
    expect(box).toHaveTextContent("This project opens on 28 Sep 2026. Open an account now so you can invest from the first day.");
    expect(within(box).queryByText("Still to fund")).not.toBeInTheDocument();
    // The project's own minimum from the API (design sample data).
    expect(within(box).getByText("Minimum").nextElementSibling).toHaveTextContent("EUR 500.00");
    expect(within(box).getByRole("link", { name: "I have an account" })).toBeInTheDocument();
    soon.unmount();

    const full: PublicProject = {
      ...fixture("bx-1046"),
      public_status: "fully_funded",
      committed_principal_minor: fixture("bx-1046").principal_minor,
      remaining_capacity_minor: 0,
      minimum_investment_minor: null
    };
    renderSite(`/projects/${ID("bx-1046")}`, (client) => client.setQueryData(siteQueryKeys.project(full.loan_id), full));
    box = document.querySelector(".site-sticky") as HTMLElement;
    expect(box).toHaveTextContent("Fully funded");
    expect(within(box).getByText("Minimum").nextElementSibling).toHaveTextContent("CHF 1,000.00");
    expect(box).toHaveTextContent("This project is no longer open.");
    expect(screen.queryByLabelText("Your amount")).not.toBeInTheDocument();
  });

  test("an unknown project shows the 404", async () => {
    renderSite("/projects/not-a-project");
    expect(await screen.findByRole("heading", { level: 1, name: "This page does not exist" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/projects/not-a-project");
  });
});

describe("Statistics page", () => {
  test("figures, amounts by currency and every funded loan", () => {
    renderSite("/statistics");
    expect(screen.getByRole("heading", { level: 1, name: "Every loan, including the ones that went wrong" })).toBeInTheDocument();
    expect(screen.queryByText(/This prototype shows its sample data/)).not.toBeInTheDocument();
    const figures = document.querySelector(".site-figures") as HTMLElement;
    expect(figures).toHaveTextContent("7loans funded1repaid in full1with a late payment now1in default");

    const amounts = screen.getByRole("heading", { name: "Amounts" }).closest("section") as HTMLElement;
    const rows = within(amounts).getAllByRole("row");
    expect(rows[1]).toHaveTextContent("CHF2300,000.0032,470.098,382.45267,529.910.00");
    expect(rows[2]).toHaveTextContent("EUR5735,000.00170,572.4423,118.19416,761.03147,666.53");
    expect(within(rows[2]).getByText("147,666.53")).toHaveClass("bxm-signal-text");
    expect(amounts).toHaveTextContent("Average interest rate, weighted by amount: 8.1%.");

    const record = screen.getByRole("heading", { name: "All funded loans" }).closest("section") as HTMLElement;
    const loanRows = within(record).getAllByRole("row").slice(1);
    expect(loanRows).toHaveLength(7);
    expect(loanRows[0]).toHaveTextContent("Invoice financing, food wholesalerFunded 20 Jul 2026 · risk B");
    expect(loanRows[2]).toHaveTextContent("Late 12 days");
    expect(loanRows[6]).toHaveTextContent("Trade receivables financing");
    fireEvent.click(within(loanRows[4]).getByRole("link", { name: "Furniture production line" }));
    expect(window.location.pathname).toBe(`/projects/${ID("bx-1024")}`);
  });
});

describe("project page helpers", () => {
  test("repayment, security, purpose and loan-to-value texts", () => {
    expect(planRepaymentOf("equal_installments")).toBe("annuity");
    expect(planRepaymentOf("bullet_periodic_interest")).toBe("interest-only");
    expect(planRepaymentOf("interest_only_then_bullet")).toBe("bullet");
    expect(securityText({ collateral_description: " ", collateral_type: "real_estate" })).toBe("Real estate");
    expect(purposeItems({ purpose_description: "A\n\n B \n", purpose: "capex" })).toEqual(["A", "B"]);
    expect(purposeItems({ purpose_description: "", purpose: "capex" })).toEqual(["Capex / business expansion"]);
    expect(ltvText(6250)).toBe("62.5%");
    expect(ltvText(null)).toBe("Not applicable");
    expect(calcAmount("1'234.5")).toBe(1234.5);
    expect(calcAmount("-")).toBe(0);
    expect(calcAmount("99999999")).toBe(10000000);
  });

  test("filters and the expected interest", () => {
    const views = siteProjectsFixture.map((p) => projectView(p, "2026-09-23"));
    expect(filterProjects(views, { status: "soon", currency: "CHF" }).map((v) => v.p.title)).toEqual(["Co-working space fit-out"]);
    expect(filtersFromQuery(new URLSearchParams("status=all"), { status: "open", currency: "EUR" })).toEqual({
      status: "all",
      currency: "EUR"
    });
    expect(expectedInterest(fixture("bx-1048"), 32308)).toBe(3637.97);
  });
});
