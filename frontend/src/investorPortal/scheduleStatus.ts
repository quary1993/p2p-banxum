export type ScheduleStatusTone = "ok" | "bad" | "neutral";

/**
 * Chip tone for a repayment schedule row.
 *
 * The server marks an unpaid row "due" on its due date and during the grace
 * period (days 1-4), and "overdue" only from day 5, when the loan becomes Late.
 * "Due" stays neutral: it is not an alarm yet.
 */
export function scheduleStatusTone(status: string): ScheduleStatusTone {
  if (status === "paid" || status === "paid_in_advance") return "ok";
  if (status === "overdue") return "bad";
  return "neutral";
}
