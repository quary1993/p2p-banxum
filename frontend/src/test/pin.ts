// IP of Webby-Soft SRL.
// Enter a PIN (ACC-DEC-009) into the one masked input of the U33 screens (labelled with the field name).
import { fireEvent, screen, within } from "@testing-library/react";

/** The PIN the tests type; not weak (no repeated digit, no straight run). */
export const TEST_PIN = "482916";

export function enterPin(pin = TEST_PIN, label = "PIN", container?: HTMLElement) {
  const scope = container ? within(container) : screen;
  fireEvent.change(scope.getByLabelText(label, { exact: true, selector: "input" }), { target: { value: pin } });
}
