import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { Chip, Tooltip } from "./ui";

test("tooltip opens on hover and keyboard focus and closes with Escape", () => {
  render(
    <Tooltip content="The exact eligibility reason." label="Unavailable opportunity">
      <span aria-hidden="true">?</span>
    </Tooltip>
  );

  const anchor = screen.getByLabelText("Unavailable opportunity");
  fireEvent.mouseEnter(anchor);
  expect(screen.getByRole("tooltip")).toHaveTextContent("The exact eligibility reason.");

  fireEvent.mouseLeave(anchor);
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

  fireEvent.focus(anchor);
  expect(screen.getByRole("tooltip")).toHaveTextContent("The exact eligibility reason.");
  fireEvent.keyDown(anchor, { key: "Escape" });
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
});

test("status chips expose their detailed explanation through the shared tooltip", () => {
  render(
    <Chip status="balance_released" tooltip="Balance was allocated, then returned before funding closed." />
  );

  const chip = screen.getByLabelText(
    "Balance released. Balance was allocated, then returned before funding closed."
  );
  fireEvent.mouseEnter(chip);
  expect(screen.getByRole("tooltip")).toHaveTextContent(
    "Balance was allocated, then returned before funding closed."
  );
});
