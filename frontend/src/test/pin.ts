// IP of Webby-Soft SRL.
// Enter a PIN (ACC-DEC-009): into the old six PIN boxes, one digit per box like typing, or into the
// one masked input of the U33 screens (labelled with the field name).
import { fireEvent, screen, within } from "@testing-library/react";

/** The PIN the tests type; not weak (no repeated digit, no straight run). */
export const TEST_PIN = "482916";

export function enterPin(pin = TEST_PIN, label = "PIN", container?: HTMLElement) {
  const scope = container ? within(container) : screen;
  const single = scope.queryByLabelText(label, { exact: true, selector: "input" });
  if (single) {
    fireEvent.change(single, { target: { value: pin } });
    return;
  }
  for (let index = 0; index < pin.length; index += 1) {
    fireEvent.change(scope.getByRole("textbox", { name: `${label} digit ${index + 1} of 6` }), {
      target: { value: pin[index] }
    });
  }
}
