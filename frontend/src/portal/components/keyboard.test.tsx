// IP of Webby-Soft SRL.
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { Dropdown } from "./Dropdown";
import { Tabs } from "./Tabs";

test("Space activates a tab link-button and does not scroll the page", () => {
  const onChange = vi.fn();
  render(<Tabs items={[{ value: "a", label: "First" }, { value: "b", label: "Second" }]} label="Views" onChange={onChange} value="a" />);
  const second = screen.getByRole("button", { name: "Second" });
  const notPrevented = fireEvent.keyDown(second, { key: " " });
  expect(notPrevented).toBe(false);
  expect(onChange).toHaveBeenCalledWith("b");
});

test("Space opens and closes the dropdown toggle", () => {
  render(
    <ul>
      <Dropdown toggle={<span>Menu</span>} toggleLabel="Account menu">
        <a href="/x">Item</a>
      </Dropdown>
    </ul>
  );
  const toggle = screen.getByRole("button", { name: "Account menu" });
  fireEvent.keyDown(toggle, { key: " " });
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  fireEvent.keyDown(toggle, { key: " " });
  expect(toggle).toHaveAttribute("aria-expanded", "false");
});
