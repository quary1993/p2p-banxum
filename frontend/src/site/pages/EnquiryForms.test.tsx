// IP of Webby-Soft SRL.
// The three U33 public forms (For borrowers, For loan originators, Contact): the check before
// sending, the request body (field mapping, consent, honeypot, elapsed time), API errors, 429
// and the "sent" state with the reference.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import { ApiClientError } from "../../api/client/httpClient";
import { SiteNavContext } from "../context";
import type { EnquiryBody, EnquiryResponse } from "../data";
import { Companies, Originators } from "../u33/pages/Business";
import { Contact } from "../u33/pages/Contact";
import {
  buildEnquiryBody,
  checkEnquiry,
  COMPANY_FORM,
  CONTACT_FORM,
  ENQUIRY_FALLBACK_ERROR,
  ORIGINATOR_FORM,
  readEnquiryErrors
} from "./enquiry";

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

/** The error line of an invalid field (aria-describedby). */
function errorOf(element: HTMLElement) {
  const id = element.getAttribute("aria-describedby");
  return id ? document.getElementById(id)?.textContent : undefined;
}

function consent() {
  return screen.getByRole("checkbox") as HTMLInputElement;
}

function fillCompanyForm() {
  type("Company name", "  Alpenbau AG ");
  type("Country of registration", "Switzerland");
  fireEvent.change(field("Loan currency"), { target: { value: "CHF" } });
  type("Amount requested", "250000");
  fireEvent.blur(field("Amount requested"));
  type("Purpose of financing", "A new machining centre");
  type("Available collateral", "Pledge on the machine.\nPersonal guarantee.");
  type("Your name", "Anna Muster");
  type("Email", "anna@example.com ");
  fireEvent.click(consent());
}

function submit(name: string) {
  fireEvent.click(screen.getByRole("button", { name }));
}

describe("For borrowers", () => {
  test("an empty form marks every required field and focuses the first one", () => {
    renderPage(Companies, "/companies");
    submit("Send financing request");

    ["Company name", "Country of registration", "Amount requested", "Purpose of financing", "Available collateral", "Your name", "Email"].forEach(
      (label) => expect(field(label)).toHaveAttribute("aria-invalid", "true")
    );
    expect(errorOf(field("Company name"))).toBe("Please fill in this field.");
    expect(errorOf(field("Amount requested"))).toBe("Enter the amount you would like to borrow.");
    expect(errorOf(field("Email"))).toBe("Enter a valid email address.");
    // The currency has a value from the start (EUR).
    expect(field("Loan currency")).toHaveValue("EUR");
    expect(field("Loan currency")).not.toHaveAttribute("aria-invalid");
    expect(consent()).toHaveAttribute("aria-invalid", "true");
    expect(errorOf(consent())).toBe("Please confirm.");
    expect(document.activeElement).toBe(field("Company name"));
    expect(enquiry.submit).not.toHaveBeenCalled();

    // An edit clears the field's mark.
    type("Company name", "A");
    expect(field("Company name")).not.toHaveAttribute("aria-invalid");
    fireEvent.click(consent());
    expect(consent()).not.toHaveAttribute("aria-invalid");
  });

  test("a badly written email is invalid; a project choice fills the purpose", () => {
    renderPage(Companies, "/companies");
    fireEvent.click(screen.getByRole("link", { name: /Machinery & equipment/ }));
    expect(field("Purpose of financing")).toHaveValue("Machinery and equipment");

    fillCompanyForm();
    type("Email", "anna@example");
    submit("Send financing request");
    expect(field("Email")).toHaveAttribute("aria-invalid", "true");
    expect(field("Company name")).not.toHaveAttribute("aria-invalid");
    expect(document.activeElement).toBe(field("Email"));
    expect(enquiry.submit).not.toHaveBeenCalled();
  });

  test("the amount keeps only amount characters and shows 1,234.56 when left", () => {
    renderPage(Companies, "/companies");
    type("Amount requested", "CHF 1'250'000.5");
    expect(field("Amount requested").value).toBe(" 1'250'000.5");
    fireEvent.blur(field("Amount requested"));
    expect(field("Amount requested").value).toBe("1,250,000.50");
  });

  test("sends the U33 fields under the contract names, with consent, the honeypot and the elapsed time", async () => {
    enquiry.submit.mockResolvedValue({ reference: "APP-2026-0143" });
    renderPage(Companies, "/companies");
    fillCompanyForm();
    vi.mocked(Date.now).mockReturnValue(SHOWN_AT + 7_500);
    submit("Send financing request");

    await waitFor(() => expect(enquiry.submit).toHaveBeenCalledTimes(1));
    expect(enquiry.submit.mock.calls[0][0]).toEqual({
      kind: "company",
      fields: {
        company_name: "Alpenbau AG",
        country: "Switzerland",
        currency: "CHF",
        amount: "250,000.00",
        purpose: "A new machining centre",
        collateral: "Pledge on the machine.\nPersonal guarantee.",
        contact_name: "Anna Muster",
        email: "anna@example.com"
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
    expect(honeypot?.closest("[aria-hidden=true]")).toHaveClass("bxp-honeypot");

    fillCompanyForm();
    fireEvent.change(honeypot as HTMLInputElement, { target: { value: "https://spam.example" } });
    vi.mocked(Date.now).mockReturnValue(SHOWN_AT + 900);
    submit("Send financing request");
    await waitFor(() => expect(enquiry.submit).toHaveBeenCalledTimes(1));
    expect(enquiry.submit.mock.calls[0][0]).toMatchObject({ website: "https://spam.example", elapsed_ms: 900 });
  });

  test("shows the API field errors on their inputs and focuses the first one", async () => {
    enquiry.submit.mockRejectedValue(
      new ApiClientError(400, "Bad request", {
        fields: {
          amount: ["Enter an amount like 250000 or 250,000.00."],
          email: ["Enter a valid email address."],
          collateral: ["Please remove some links."]
        },
        consent: ["Please agree before you send the form."]
      })
    );
    renderPage(Companies, "/companies");
    fillCompanyForm();
    submit("Send financing request");

    await waitFor(() => expect(field("Amount requested")).toHaveAttribute("aria-invalid", "true"));
    expect(errorOf(field("Amount requested"))).toBe("Enter an amount like 250000 or 250,000.00.");
    expect(field("Email")).toHaveAttribute("aria-invalid", "true");
    expect(errorOf(field("Available collateral"))).toBe("Please remove some links.");
    expect(errorOf(consent())).toBe("Please agree before you send the form.");
    expect(field("Company name")).not.toHaveAttribute("aria-invalid");
    expect(document.activeElement).toBe(field("Amount requested"));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    // Editing the field clears the server's message with the mark.
    type("Amount requested", "250000");
    expect(field("Amount requested")).not.toHaveAttribute("aria-invalid");
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
    submit("Send financing request");

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Too many messages. Please try again later or write to us by email.");
    expect(alert).toHaveClass("bxp-form-alert");
    const button = screen.getByRole("button", { name: "Send financing request" });
    expect(alert.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(consent()).toBeChecked();
    expect(field("Company name").value).toBe("  Alpenbau AG ");

    // A new attempt clears the alert.
    enquiry.submit.mockResolvedValue({ reference: "APP-2026-0144" });
    submit("Send financing request");
    await screen.findByRole("status");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  test("on success the form shows the API reference, without a reply deadline; Send another starts again", async () => {
    enquiry.submit.mockResolvedValue({ reference: "APP-2026-0143" });
    renderPage(Companies, "/companies");
    fillCompanyForm();
    submit("Send financing request");

    const sent = await screen.findByRole("status");
    expect(sent).toHaveClass("bxp-form-sent");
    expect(within(sent).getByRole("heading", { name: "Thank you. Your financing request has been sent." })).toBeInTheDocument();
    // U33-DEC-35: no "shortly" or business-day promise.
    expect(sent).toHaveTextContent("Reference APP-2026-0143. A member of our team will reply by email to anna@example.com.");
    expect(sent).not.toHaveTextContent(/shortly|business day/);

    fireEvent.click(within(sent).getByRole("button", { name: "Send another request" }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(field("Company name").value).toBe("");
    expect(consent()).not.toBeChecked();
  });
});

describe("For loan originators", () => {
  test("a route's action fills the proposal; the request goes as kind originator", async () => {
    enquiry.submit.mockResolvedValue({ reference: "PAR-2026-0007" });
    renderPage(Originators, "/originators");

    submit("Propose a partnership");
    expect(document.activeElement).toBe(field("Company name"));
    expect(field("What would you like to propose?")).toHaveAttribute("aria-invalid", "true");
    expect(errorOf(field("What would you like to propose?"))).toBe("Choose the type of opportunity.");
    expect(field(/^A short introduction/)).not.toHaveAttribute("aria-invalid");

    fireEvent.click(screen.getByRole("link", { name: /Propose an existing loan/ }));
    expect(field("What would you like to propose?")).toHaveValue("Refinancing of existing loans");

    type("Company name", "Leasing Partner GmbH");
    type("Country of registration", "Germany");
    type("Your name", "Max Muster");
    type("Email", "max@example.com");
    type(/^A short introduction/, "Equipment leasing.\nSmall companies.");
    fireEvent.click(consent());
    vi.mocked(Date.now).mockReturnValue(SHOWN_AT + 12_000);
    submit("Propose a partnership");

    const sent = await screen.findByRole("status");
    expect(enquiry.submit.mock.calls[0][0]).toEqual({
      kind: "originator",
      fields: {
        company_name: "Leasing Partner GmbH",
        country: "Germany",
        contact_name: "Max Muster",
        email: "max@example.com",
        proposal: "Refinancing of existing loans",
        about: "Equipment leasing.\nSmall companies."
      },
      consent: true,
      website: "",
      elapsed_ms: 12_000
    });
    expect(within(sent).getByRole("heading", { name: "Thank you. Your partnership request has been sent." })).toBeInTheDocument();
    expect(sent).toHaveTextContent("Reference PAR-2026-0007.");
    fireEvent.click(within(sent).getByRole("button", { name: "Send another request" }));
    expect(screen.getByRole("heading", { name: "Your partnership request", level: 2 })).toBeInTheDocument();
  });
});

describe("Contact", () => {
  function fillContactForm() {
    type("Full name", "Anna Muster");
    type("Email address", "anna@example.com");
    fireEvent.click(consent());
  }

  test("only the name, email and consent are required; topic and message are optional", async () => {
    enquiry.submit.mockResolvedValue({ reference: "MSG-2026-0412" });
    renderPage(Contact, "/contact");
    // Today's configured address (U33-DEC-36), not the design's investors@banxum.ch.
    expect(screen.getByRole("link", { name: "support@banxum.com" })).toHaveAttribute("href", "mailto:support@banxum.com");
    expect(screen.queryByText(/investors@banxum\.ch/)).not.toBeInTheDocument();
    expect(screen.getByText("A member of our team will reply by email.")).toBeInTheDocument();

    submit("Request a conversation");
    ["Full name", "Email address"].forEach((label) => expect(field(label)).toHaveAttribute("aria-invalid", "true"));
    expect(field(/^Message/)).not.toHaveAttribute("aria-invalid");
    expect(document.activeElement).toBe(field("Full name"));

    fillContactForm();
    vi.mocked(Date.now).mockReturnValue(SHOWN_AT + 30_000);
    submit("Request a conversation");
    const sent = await screen.findByRole("status");
    expect(enquiry.submit.mock.calls[0][0]).toEqual({
      kind: "contact",
      fields: { name: "Anna Muster", email: "anna@example.com" },
      consent: true,
      website: "",
      elapsed_ms: 30_000
    });
    expect(within(sent).getByRole("heading", { name: "Thank you. Your request has been sent." })).toBeInTheDocument();
    expect(sent).toHaveTextContent("Reference MSG-2026-0412. A member of our team will reply by email to anna@example.com.");
  });

  test("the topic is a toggle and goes with the message", async () => {
    enquiry.submit.mockResolvedValue({ reference: "MSG-2026-0413" });
    renderPage(Contact, "/contact");
    const topic = screen.getByRole("button", { name: "An opportunity" });
    fireEvent.click(topic);
    expect(topic).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "How investing works" }));
    expect(topic).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(screen.getByRole("button", { name: "How investing works" }));
    expect(screen.getByRole("button", { name: "How investing works" })).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(topic);
    type(/^Message/, "How do I add EUR to my account?");
    fillContactForm();
    submit("Request a conversation");
    await screen.findByRole("status");
    expect(enquiry.submit.mock.calls[0][0].fields).toEqual({
      name: "Anna Muster",
      email: "anna@example.com",
      topic: "An opportunity",
      message: "How do I add EUR to my account?"
    });
  });

  test("an error without a field (or a server error) goes to the alert", async () => {
    enquiry.submit.mockRejectedValueOnce(new ApiClientError(400, "Too large", { detail: "The form is too large.", code: "too_large" }));
    renderPage(Contact, "/contact");
    fillContactForm();
    submit("Request a conversation");
    expect(await screen.findByRole("alert")).toHaveTextContent("The form is too large.");

    enquiry.submit.mockRejectedValueOnce(new ApiClientError(500, "Server error", null));
    await act(async () => submit("Request a conversation"));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(ENQUIRY_FALLBACK_ERROR));
  });

  test("double clicks send once", async () => {
    let resolve: (value: EnquiryResponse) => void = () => undefined;
    enquiry.submit.mockReturnValue(new Promise((done) => (resolve = done)));
    renderPage(Contact, "/contact");
    fillContactForm();
    submit("Request a conversation");
    await waitFor(() => expect(screen.getByRole("button", { name: /Sending/ })).toBeDisabled());
    fireEvent.submit(screen.getByRole("button", { name: /Sending/ }).closest("form") as HTMLFormElement);
    expect(enquiry.submit).toHaveBeenCalledTimes(1);
    await act(async () => resolve({ reference: "MSG-2026-0414" }));
    expect(await screen.findByRole("status")).toHaveTextContent("MSG-2026-0414");
  });
});

describe("enquiry helpers", () => {
  test("checkEnquiry checks the required fields in form order and the email rule", () => {
    const values = { "contact-name": " ", "contact-email": "a@b", "contact-topic": "", "contact-message": "" };
    expect(checkEnquiry(CONTACT_FORM, values, false)).toEqual(["contact-name", "contact-email", "contact-consent"]);
    expect(checkEnquiry(CONTACT_FORM, { ...values, "contact-name": "A", "contact-email": "a@b.ch" }, true)).toEqual([]);
  });

  test("buildEnquiryBody leaves out empty optional fields and never sends a negative time", () => {
    const values = Object.fromEntries(ORIGINATOR_FORM.fields.map((spec) => [spec.id, spec.required ? "x" : " "]));
    const body = buildEnquiryBody(ORIGINATOR_FORM, values, { website: "", elapsedMs: -5 });
    expect(body.fields).not.toHaveProperty("about");
    expect(body.elapsed_ms).toBe(0);
    expect(Object.keys(body.fields)).toEqual(["company_name", "country", "contact_name", "email", "proposal"]);
  });

  test("readEnquiryErrors maps contract names to the form ids", () => {
    const error = new ApiClientError(400, "Bad", { fields: { collateral: ["Required."], proposal: ["x"] } });
    expect(readEnquiryErrors(COMPANY_FORM, error)).toEqual({ fields: { "company-collateral": "Required." }, alert: null });
    expect(readEnquiryErrors(ORIGINATOR_FORM, error)).toEqual({ fields: { "originator-loan-type": "x" }, alert: null });
    const throttled = new ApiClientError(429, "Throttled", { detail: "Slow down.", code: "throttled" });
    expect(readEnquiryErrors(CONTACT_FORM, throttled)).toEqual({ fields: {}, alert: "Slow down." });
  });
});
