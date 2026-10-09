// Audit A-30: during the grace period (days 1-4 after a missed due date) the server
// sends "due" and the investor sees a neutral "Due". "Overdue" (red) starts on day 5,
// when the loan becomes Late.
import { expect, test } from "vitest";

import { scheduleStatusTone } from "./scheduleStatus";

test("schedule row tones: due is neutral, overdue is red, paid is green", () => {
  expect(scheduleStatusTone("due")).toBe("neutral");
  expect(scheduleStatusTone("upcoming")).toBe("neutral");
  expect(scheduleStatusTone("overdue")).toBe("bad");
  expect(scheduleStatusTone("paid")).toBe("ok");
  expect(scheduleStatusTone("paid_in_advance")).toBe("ok");
});
