// IP of Webby-Soft SRL.
// Enter a PIN into the six PIN boxes (ACC-DEC-009), one digit per box like typing.
import { fireEvent, screen, within } from "@testing-library/react";

/** The PIN the tests type; not weak (no repeated digit, no straight run). */
export const TEST_PIN = "482916";

export function enterPin(pin = TEST_PIN, label = "PIN", container?: HTMLElement) {
  const scope = container ? within(container) : screen;
  for (let index = 0; index < pin.length; index += 1) {
    fireEvent.change(scope.getByRole("textbox", { name: `${label} digit ${index + 1} of 6` }), {
      target: { value: pin[index] }
    });
  }
}
