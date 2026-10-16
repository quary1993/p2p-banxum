// IP of Webby-Soft SRL.
// The three public forms (For companies, For loan originators, Contact): the design's check,
// the request body (field mapping, honeypot, elapsed time), API errors, 429 and the done boxes.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { ApiClientError } from "../../api/client/httpClient";
import { SiteNavContext } from "../context";
import type { EnquiryBody, EnquiryResponse } from "../data";
import { Companies } from "./Companies";
import { Contact } from "./Contact";
import {
  buildEnquiryBody,
  checkEnquiry,
  COMPANY_FORM,
  CONTACT_FORM,
  ENQUIRY_FALLBACK_ERROR,
  ORIGINATOR_FORM,
  readEnquiryErrors
} from "./enquiry";
import { Originators } from "./Originators";

// The preview hook answers with fixtures; here the submit goes to a mock the tests control.
const enquiry = vi.hoisted(() => ({
  submit: vi.fn<(body: EnquiryBody) => Promise<EnquiryResponse>>()
}));

vi.mock("../data", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../data")>();
  const { useMutation } = await import("@tanstack/react-query");
  return {
    ...actual,
    useEnquirySubmit: () => useMutation({ mutationFn: (body: EnquiryBody) => enquiry.submit(body) })
  };
});

const SHOWN_AT = 1_800_000_000_000;

beforeEach(() => {
  enquiry.submit.mockReset();
  vi.spyOn(Date, "now").mockReturnValue(SHOWN_AT);
});

afterEach(() => {
  vi.restoreAllMocks();
});

function renderPage(Page: ComponentType, path: string) {
  const nav = { path, search: "", query: new URLSearchParams(), navigate: vi.fn() };
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <SiteNavContext.Provider value={nav}>
        <Page />
      </SiteNavContext.Provider>
    </QueryClientProvider>
  );
}

function field(label: string | RegExp) {
  return screen.getByLabelText(label) as HTMLInputElement;
}

function type(label: string | RegExp, value: string) {
  fireEvent.change(field(label), { target: { value } });
}

function feedbackOf(element: HTMLElement) {
  return element.parentElement?.querySelector(".invalid-feedback")?.textContent;
}

function fillCompanyForm() {
  type("Company name", "  Alpenbau AG ");
  type("Country of registration", "Switzerland");
  type("Company number", "CHE-123.456.789");
  type("Amount", "250000");
  fireEvent.blur(field("Amount"));
  type("Term", "24 months");
  type("Purpose", "Machines and equipment");
  type("Security you can offer", "Pledge on equipment");
  type("Founded", "2015");
  type("Your name", "Anna Muster");
  type("Your role", "CFO");
  type("Email", "anna@example.com ");
  type("Phone", "+41 44 000 00 00");
  fireEvent.click(screen.getByRole("checkbox"));
}

function submit(name: string) {
  fireEvent.click(screen.getByRole("button", { name }));
}

describe("For companies", () => {
  test("an empty form marks every required field like the design and focuses the first one", () => {
    renderPage(Companies, "/companies");
    submit("Send application");

    const required = [
      "Company name",
      "Country of registration",
      "Company number",
      "Amount",
      "Term",
      "Purpose",
      "Security you can offer",
      "Founded",
      "Your name",
      "Your role",
      "Email",
      "Phone"
    ];
    required.forEach((label) => {
      expect(field(label)).toHaveClass("is-invalid");
      expect(field(label)).toHaveAttribute("aria-invalid", "true");
    });
    expect(feedbackOf(field("Company name"))).toBe("Required.");
    expect(feedbackOf(field("Email"))).toBe("Enter a valid email address.");
    // Optional fields stay valid.
    expect(field("Revenue last year")).not.toHaveClass("is-invalid");
    expect(field("What is the money for?")).not.toHaveClass("is-invalid");
    const consent = screen.getByRole("checkbox");
    expect(consent).toHaveClass("form-check-input is-invalid");
    expect(feedbackOf(consent)).toBe("Please confirm.");
    expect(document.activeElement).toBe(field("Company name"));
    expect(enquiry.submit).not.toHaveBeenCalled();

    // An edit clears the field's mark (design: input / change listeners).
    type("Company name", "A");
    expect(field("Company name")).not.toHaveClass("is-invalid");
    type("Term", "12 months");
    expect(field("Term")).not.toHaveClass("is-invalid");
    fireEvent.click(consent);
    expect(consent).not.toHaveClass("is-invalid");
  });

  test("a badly written email is invalid; the amount note follows the country", () => {
    renderPage(Companies, "/companies");
    expect(screen.getByText("No loan size limits")).toBeInTheDocument();
    type("Country of registration", "Switzerland");
    expect(screen.getByText("In CHF. No loan size limits")).toBeInTheDocument();
    type("Country of registration", "Germany");
    expect(screen.getByText("In EUR. No loan size limits")).toBeInTheDocument();

    fillCompanyForm();
    type("Email", "anna@example");
    submit("Send application");
    expect(field("Email")).toHaveClass("is-invalid");
    expect(field("Company name")).not.toHaveClass("is-invalid");
    expect(document.activeElement).toBe(field("Email"));
    expect(enquiry.submit).not.toHaveBeenCalled();
  });

  test("amount fields keep only amount characters and show 1,234.56 when left", () => {
    renderPage(Companies, "/companies");
    type("Amount", "CHF 1'250'000.5");
    // The design's filter keeps digits, separators and spaces.
    expect(field("Amount").value).toBe(" 1'250'000.5");
    fireEvent.blur(field("Amount"));
    expect(field("Amount").value).toBe("1,250,000.50");
  });

  test("sends the design fields under the contract names, with the honeypot and the elapsed time", async () => {
    enquiry.submit.mockResolvedValue({ reference: "APP-2026-0143" });
    renderPage(Companies, "/companies");
    fillCompanyForm();
    type("Revenue last year", "1200000");
    vi.mocked(Date.now).mockReturnValue(SHOWN_AT + 7_500);
    submit("Send application");

    await waitFor(() => expect(enquiry.submit).toHaveBeenCalledTimes(1));
    expect(enquiry.submit.mock.calls[0][0]).toEqual({
      kind: "company",
      fields: {
        company_name: "Alpenbau AG",
        country: "Switzerland",
        company_number: "CHE-123.456.789",
        amount: "250,000.00",
        term: "24 months",
        purpose: "Machines and equipment",
        security: "Pledge on equipment",
        revenue: "1200000",
        founded: "2015",
        contact_name: "Anna Muster",
        role: "CFO",
        email: "anna@example.com",
        phone: "+41 44 000 00 00"
      },
      consent: true,
      website: "",
      elapsed_ms: 7_500
    });
  });

  test("the honeypot is hidden from people and sent as filled", async () => {
    enquiry.submit.mockResolvedValue({ reference: "APP-2026-0143" });
    const { container } = renderPage(Companies, "/companies");
    const honeypot = container.querySelector<HTMLInputElement>("input[name=website]");
    expect(honeypot).not.toBeNull();
    expect(honeypot).toHaveAttribute("tabindex", "-1");
    expect(honeypot).toHaveAttribute("autocomplete", "off");
    expect(honeypot?.closest("[aria-hidden=true]")).toHaveClass("visually-hidden");

    fillCompanyForm();
    fireEvent.change(honeypot as HTMLInputElement, { target: { value: "https://spam.example" } });
    vi.mocked(Date.now).mockReturnValue(SHOWN_AT + 900);
    submit("Send application");
    await waitFor(() => expect(enquiry.submit).toHaveBeenCalledTimes(1));
    expect(enquiry.submit.mock.calls[0][0]).toMatchObject({ website: "https://spam.example", elapsed_ms: 900 });
  });

  test("shows the API field errors on their inputs and focuses the first one", async () => {
    enquiry.submit.mockRejectedValue(
      new ApiClientError(400, "Bad request", {
        fields: {
          founded: ["Enter a year between 1800 and 2026."],
          email: ["Enter a valid email address."],
          about: ["Please remove some links."]
        },
        consent: ["Please agree before you send the form."]
      })
    );
    renderPage(Companies, "/companies");
    fillCompanyForm();
    submit("Send application");

    await waitFor(() => expect(field("Founded")).toHaveClass("is-invalid"));
    expect(feedbackOf(field("Founded"))).toBe("Enter a year between 1800 and 2026.");
    expect(field("Email")).toHaveClass("is-invalid");
    expect(feedbackOf(field("What is the money for?"))).toBe("Please remove some links.");
    expect(feedbackOf(screen.getByRole("checkbox"))).toBe("Please agree before you send the form.");
    expect(field("Company name")).not.toHaveClass("is-invalid");
    expect(document.activeElement).toBe(field("Founded"));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    // Editing the field clears the server's message with the mark.
    type("Founded", "2016");
    expect(field("Founded")).not.toHaveClass("is-invalid");
  });

  test("a 429 shows the API message in an alert above the submit button", async () => {
    enquiry.submit.mockRejectedValue(
      new ApiClientError(429, "Throttled", {
        detail: "Too many messages. Please try again later or write to us by email.",
        code: "throttled"
      })
    );
    renderPage(Companies, "/companies");
    fillCompanyForm();
    submit("Send application");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Too many messages. Please try again later or write to us by email.");
    expect(alert).toHaveClass("alert alert-danger");
    const button = screen.getByRole("button", { name: "Send application" });
    expect(alert.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByRole("checkbox")).toBeChecked();
    expect(field("Company name").value).toBe("  Alpenbau AG ");

    // A new attempt clears the alert.
    enquiry.submit.mockResolvedValue({ reference: "APP-2026-0144" });
    submit("Send application");
    await screen.findByRole("status");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  test("on success the done box shows the API reference; Send another starts again", async () => {
    enquiry.submit.mockResolvedValue({ reference: "APP-2026-0143" });
    renderPage(Companies, "/companies");
    fillCompanyForm();
    submit("Send application");

    const done = await screen.findByRole("status");
    expect(done).toHaveClass("site-form site-form-done");
    expect(within(done).getByRole("heading", { name: "Thank you, we have your application" })).toBeInTheDocument();
    expect(done).toHaveTextContent("Reference APP-2026-0143. Your message was sent successfully.");
    expect(done).not.toHaveTextContent("anna@example.com");
    expect(within(done).getAllByRole("listitem").map((item) => item.querySelector("strong")?.textContent)).toEqual([
      "First answer",
      "Documents",
      "Offer"
    ]);
    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ block: "center" });

    fireEvent.click(within(done).getByRole("button", { name: "Send another" }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(field("Company name").value).toBe("");
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });

  test("Apply now scrolls to the form", () => {
    renderPage(Companies, "/companies");
    const scroll = vi.mocked(Element.prototype.scrollIntoView);
    scroll.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Apply now" }));
    expect(scroll).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });
    expect(scroll.mock.contexts[0]).toBe(document.getElementById("apply"));
  });
});

describe("For loan originators", () => {
  test("lists the partners from the API and sends the request as kind originator", async () => {
    enquiry.submit.mockResolvedValue({ reference: "PAR-2026-0007" });
    renderPage(Originators, "/originators");
    expect(screen.getByRole("heading", { name: "Lindmatt Leasing AG" })).toBeInTheDocument();
    expect(screen.getByText("Switzerland · partner since November 2025")).toBeInTheDocument();
    expect(screen.getByText("14 claims funded.")).toBeInTheDocument();

    submit("Send");
    expect(document.activeElement).toBe(field("Company name"));
    expect(field("Loan book")).toHaveClass("form-control bxm-amount is-invalid");

    type("Company name", "Leasing Partner GmbH");
    type("Country", "Germany");
    type("Licence or registration", "BaFin 123456");
    type("What you finance", "Invoices (factoring)");
    type("Loan book", "10000000");
    fireEvent.blur(field("Loan book"));
    type("Anything we should know?", "Equipment leasing.\nSmall companies.");
    type("Your name", "Max Muster");
    type("Email", "max@example.com");
    fireEvent.click(screen.getByRole("checkbox"));
    vi.mocked(Date.now).mockReturnValue(SHOWN_AT + 12_000);
    submit("Send");

    const done = await screen.findByRole("status");
    expect(enquiry.submit.mock.calls[0][0]).toEqual({
      kind: "originator",
      fields: {
        company_name: "Leasing Partner GmbH",
        country: "Germany",
        licence: "BaFin 123456",
        product: "Invoices (factoring)",
        loan_book: "10,000,000.00",
        about: "Equipment leasing.\nSmall companies.",
        contact_name: "Max Muster",
        email: "max@example.com"
      },
      consent: true,
      website: "",
      elapsed_ms: 12_000
    });
    expect(within(done).getByRole("heading", { name: "Thank you, we have your request" })).toBeInTheDocument();
    expect(done).toHaveTextContent("Reference PAR-2026-0007. Your message was sent successfully.");
    expect(within(done).getAllByRole("listitem")).toHaveLength(3);
    expect(done).toHaveTextContent("Introduction call");
    fireEvent.click(within(done).getByRole("button", { name: "Send another" }));
    expect(screen.getByRole("heading", { name: "Talk to us", level: 3 })).toBeInTheDocument();
  });
});

describe("Contact", () => {
  function fillContactForm() {
    type("Your name", "Anna Muster");
    type("Email", "anna@example.com");
    type("Topic", "Investing");
    type("Message", "How do I add EUR to my wallet?");
    fireEvent.click(screen.getByRole("checkbox"));
  }

  test("checks the form, sends kind contact and shows the contact done box", async () => {
    enquiry.submit.mockResolvedValue({ reference: "MSG-2026-0412" });
    renderPage(Contact, "/contact");
    submit("Send message");
    ["Your name", "Email", "Topic", "Message"].forEach((label) => expect(field(label)).toHaveClass("is-invalid"));
    expect(feedbackOf(field("Message"))).toBe("Required.");
    expect(document.activeElement).toBe(field("Your name"));

    fillContactForm();
    vi.mocked(Date.now).mockReturnValue(SHOWN_AT + 30_000);
    submit("Send message");
    const done = await screen.findByRole("status");
    expect(enquiry.submit.mock.calls[0][0]).toEqual({
      kind: "contact",
      fields: { name: "Anna Muster", email: "anna@example.com", topic: "Investing", message: "How do I add EUR to my wallet?" },
      consent: true,
      website: "",
      elapsed_ms: 30_000
    });
    expect(within(done).getByRole("heading", { name: "Thank you, we will answer soon" })).toBeInTheDocument();
    expect(done).toHaveTextContent(
      "Reference MSG-2026-0412. Your message was sent successfully. We usually answer within one business day, at anna@example.com."
    );
    fireEvent.click(within(done).getByRole("button", { name: "Send another message" }));
    expect(field("Message").value).toBe("");
  });

  test("an error without a field (or a network error) goes to the alert", async () => {
    enquiry.submit.mockRejectedValueOnce(new ApiClientError(400, "Too large", { detail: "The form is too large.", code: "too_large" }));
    renderPage(Contact, "/contact");
    fillContactForm();
    submit("Send message");
    expect(await screen.findByRole("alert")).toHaveTextContent("The form is too large.");

    enquiry.submit.mockRejectedValueOnce(new ApiClientError(500, "Server error", null));
    await act(async () => submit("Send message"));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(ENQUIRY_FALLBACK_ERROR));
  });

  test("double clicks send once", async () => {
    let resolve: (value: EnquiryResponse) => void = () => undefined;
    enquiry.submit.mockReturnValue(new Promise((done) => (resolve = done)));
    renderPage(Contact, "/contact");
    fillContactForm();
    submit("Send message");
    await waitFor(() => expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled());
    fireEvent.submit(screen.getByRole("button", { name: "Send message" }).closest("form") as HTMLFormElement);
    expect(enquiry.submit).toHaveBeenCalledTimes(1);
    await act(async () => resolve({ reference: "MSG-2026-0413" }));
    expect(await screen.findByRole("status")).toHaveTextContent("MSG-2026-0413");
  });
});

describe("enquiry helpers", () => {
  test("checkEnquiry follows the design's checkForm order and email rule", () => {
    const values = { "ct-name": " ", "ct-email": "a@b", "ct-topic": "Press", "ct-msg": "Hello" };
    expect(checkEnquiry(CONTACT_FORM, values, false)).toEqual(["ct-name", "ct-email", "ct-consent"]);
    expect(checkEnquiry(CONTACT_FORM, { ...values, "ct-name": "A", "ct-email": "a@b.ch" }, true)).toEqual([]);
  });

  test("buildEnquiryBody leaves out empty optional fields and never sends a negative time", () => {
    const values = Object.fromEntries(ORIGINATOR_FORM.fields.map((spec) => [spec.id, spec.required ? "x" : " "]));
    const body = buildEnquiryBody(ORIGINATOR_FORM, values, { website: "", elapsedMs: -5 });
    expect(body.fields).not.toHaveProperty("about");
    expect(body.elapsed_ms).toBe(0);
    expect(Object.keys(body.fields)).toEqual(["company_name", "country", "licence", "product", "loan_book", "contact_name", "email"]);
  });

  test("readEnquiryErrors maps contract names to the design ids", () => {
    const error = new ApiClientError(400, "Bad", { fields: { company_number: ["Required."], loan_book: ["x"] } });
    expect(readEnquiryErrors(COMPANY_FORM, error)).toEqual({ fields: { "co-reg": "Required." }, alert: null });
    expect(readEnquiryErrors(ORIGINATOR_FORM, error)).toEqual({ fields: { "or-book": "x" }, alert: null });
    const throttled = new ApiClientError(429, "Throttled", { detail: "Slow down.", code: "throttled" });
    expect(readEnquiryErrors(CONTACT_FORM, throttled)).toEqual({ fields: {}, alert: "Slow down." });
  });
});
