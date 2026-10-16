// IP of Webby-Soft SRL.
// The six-box PIN input and the PIN rules (ACC-DEC-009).
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, test } from "vitest";

import { PinInput, PinRules } from "./pin";
import { pinWeakness } from "./pinRules";

function Harness({ initial = "", label = "PIN" }: { initial?: string; label?: string }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <PinInput label={label} value={value} onChange={setValue} />
      <output data-testid="value">{value}</output>
    </>
  );
}

function box(index: number, label = "PIN") {
  return screen.getByRole("textbox", { name: `${label} digit ${index} of 6` });
}

test("six labelled boxes: numeric keypad, no autocomplete, masked digits", () => {
  render(<Harness initial="48" />);

  expect(screen.getByRole("group", { name: "PIN" })).toBeInTheDocument();
  for (let index = 1; index <= 6; index += 1) {
    expect(box(index)).toHaveAttribute("inputmode", "numeric");
    expect(box(index)).toHaveAttribute("autocomplete", "off");
  }
  expect(box(1)).toHaveValue("•");
  expect(box(2)).toHaveValue("•");
  expect(box(3)).toHaveValue("");

  fireEvent.click(screen.getByRole("button", { name: "Show PIN" }));
  expect(box(1)).toHaveValue("4");
  expect(box(2)).toHaveValue("8");
  expect(screen.getByRole("button", { name: "Hide PIN" })).toHaveAttribute("aria-pressed", "true");
});

test("typing fills one box at a time and moves the focus on; letters are ignored", () => {
  render(<Harness />);

  fireEvent.change(box(1), { target: { value: "4" } });
  expect(screen.getByTestId("value")).toHaveTextContent("4");
  expect(box(2)).toHaveFocus();
  fireEvent.change(box(2), { target: { value: "a" } });
  expect(screen.getByTestId("value")).toHaveTextContent(/^4$/);
  fireEvent.keyDown(box(2), { key: "x" });
  fireEvent.change(box(2), { target: { value: "8" } });
  fireEvent.change(box(3), { target: { value: "2" } });
  expect(screen.getByTestId("value")).toHaveTextContent("482");
  expect(box(4)).toHaveFocus();
});

test("a pasted 6-digit PIN fills every box", () => {
  render(<Harness />);

  fireEvent.paste(box(1), { clipboardData: { getData: () => "48 29 16" } });

  expect(screen.getByTestId("value")).toHaveTextContent("482916");
  expect(box(6)).toHaveFocus();
});

test("backspace clears the box and goes back to the previous one", () => {
  render(<Harness initial="482" />);

  fireEvent.keyDown(box(4), { key: "Backspace" });
  expect(screen.getByTestId("value")).toHaveTextContent(/^48$/);
  expect(box(3)).toHaveFocus();
  fireEvent.keyDown(box(3), { key: "Backspace" });
  expect(screen.getByTestId("value")).toHaveTextContent(/^4$/);
  expect(box(2)).toHaveFocus();
});

test("the error line sits under the boxes and marks them invalid", () => {
  render(<PinInput error="Wrong PIN. 4 attempts left before your PIN is locked." label="PIN" value="" onChange={() => undefined} />);

  expect(screen.getByRole("alert")).toHaveTextContent("Wrong PIN. 4 attempts left");
  expect(box(1)).toHaveAttribute("aria-invalid", "true");
});

test("weak PINs follow the server rules", () => {
  for (const pin of ["000000", "111111", "123456", "654321", "012345", "987654"]) {
    expect(pinWeakness(pin)).not.toBeNull();
  }
  for (const pin of ["482916", "246810", "112233", "123465"]) {
    expect(pinWeakness(pin)).toBeNull();
  }
  expect(pinWeakness("12345")).toBe("Your PIN must be exactly 6 digits.");
});

test("the checklist ticks each rule as it is met", () => {
  const { rerender } = render(<PinRules confirmation="" pin="123456" />);
  const list = screen.getByRole("list", { name: "PIN rules" });
  expect(list.querySelectorAll("li.is-met")).toHaveLength(2);
  expect(screen.getByText("Not a straight run, like 123456 or 654321").closest("li")).not.toHaveClass("is-met");

  rerender(<PinRules confirmation="482916" pin="482916" />);
  expect(list.querySelectorAll("li.is-met")).toHaveLength(4);
});
