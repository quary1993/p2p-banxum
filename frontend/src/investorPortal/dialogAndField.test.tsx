// Accessibility of the shared Field and Modal (audit 2026-10-09, A-61/A-62): labels and hints are
// linked to their controls; dialogs take focus, trap Tab, give focus back, ignore Escape while a
// money action runs, and only the top-most of two stacked dialogs closes on Escape.
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { expect, test } from "vitest";

import { Button, Field, Modal } from "./ui";

test("Field links its label, hint and error to the control", () => {
  render(
    <>
      <Field hint="Whole francs only." label="Amount">
        <input />
      </Field>
      <Field error="Enter a number." label="Mobile phone number">
        <div className="phone-number-row">
          <select aria-label="Phone country prefix"><option>+41</option></select>
          <input />
        </div>
      </Field>
    </>
  );

  const amount = screen.getByLabelText("Amount");
  expect(amount.tagName).toBe("INPUT");
  expect(amount).toHaveAccessibleDescription("Whole francs only.");
  // The nested number input, not the prefix select that has its own name.
  const phone = screen.getByLabelText("Mobile phone number");
  expect(phone.tagName).toBe("INPUT");
  expect(phone).toHaveAccessibleDescription("Enter a number.");
  expect(phone).toHaveAttribute("aria-invalid", "true");
  expect(screen.getByLabelText("Phone country prefix").tagName).toBe("SELECT");
});

function DialogHarness({ busy = false }: { busy?: boolean }) {
  const [open, setOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)} type="button">Open task</button>
      {open ? (
        <Modal
          busy={busy}
          footer={<Button onClick={() => setConfirmOpen(true)}>Resolve</Button>}
          onClose={() => setOpen(false)}
          title="Task"
        >
          <Field label="Note"><input /></Field>
        </Modal>
      ) : null}
      {confirmOpen ? (
        <Modal footer={<Button onClick={() => setConfirmOpen(false)}>Cancel</Button>} onClose={() => setConfirmOpen(false)} title="Resolve this task?">
          <p>Resolving only closes the task.</p>
        </Modal>
      ) : null}
    </>
  );
}

test("a dialog takes focus, traps Tab and gives focus back to its opener", () => {
  render(<DialogHarness />);
  const opener = screen.getByRole("button", { name: "Open task" });
  opener.focus();
  fireEvent.click(opener);

  const dialog = screen.getByRole("dialog", { name: "Task" });
  const note = screen.getByLabelText("Note");
  expect(document.activeElement).toBe(note);

  // Tab from the last control wraps to the first; Shift+Tab from the first wraps to the last.
  const resolve = screen.getByRole("button", { name: "Resolve" });
  resolve.focus();
  fireEvent.keyDown(document.activeElement as Element, { key: "Tab" });
  expect(dialog.contains(document.activeElement)).toBe(true);
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "Close" }));
  fireEvent.keyDown(document.activeElement as Element, { key: "Tab", shiftKey: true });
  expect(document.activeElement).toBe(resolve);

  fireEvent.keyDown(document.activeElement as Element, { key: "Escape" });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(document.activeElement).toBe(opener);
});

test("Escape on a stacked confirmation closes only the confirmation", () => {
  render(<DialogHarness />);
  fireEvent.click(screen.getByRole("button", { name: "Open task" }));
  screen.getByRole("button", { name: "Resolve" }).focus();
  fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
  expect(screen.getByRole("dialog", { name: "Resolve this task?" })).toBeInTheDocument();
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "Cancel" }));

  fireEvent.keyDown(document.activeElement as Element, { key: "Escape" });
  expect(screen.queryByRole("dialog", { name: "Resolve this task?" })).not.toBeInTheDocument();
  expect(screen.getByRole("dialog", { name: "Task" })).toBeInTheDocument();
  expect(document.activeElement).toBe(screen.getByRole("button", { name: "Resolve" }));
});

test("while a money action runs, Escape, the backdrop and the close button do not close the dialog", () => {
  render(<DialogHarness busy />);
  fireEvent.click(screen.getByRole("button", { name: "Open task" }));
  const dialog = screen.getByRole("dialog", { name: "Task" });

  fireEvent.keyDown(document.activeElement as Element, { key: "Escape" });
  fireEvent.mouseDown(dialog.parentElement as Element);
  expect(screen.getByRole("dialog", { name: "Task" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Close" })).toBeDisabled();
  expect(dialog).toHaveAttribute("aria-busy", "true");
});
