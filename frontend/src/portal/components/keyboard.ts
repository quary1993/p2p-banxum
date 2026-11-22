// IP of Webby-Soft SRL.
import type { KeyboardEvent } from "react";

/**
 * Space for the design's link-buttons (<a href="#" role="button">): a link reacts to Enter only, and
 * Space would scroll the page. On Space the element is clicked, so its onClick runs, as for a button.
 */
export function clickOnSpace(event: KeyboardEvent<HTMLElement>) {
  if (event.key !== " " && event.key !== "Spacebar") return;
  event.preventDefault();
  event.currentTarget.click();
}
