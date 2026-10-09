import { describe, expect, test } from "vitest";

import type { InvestorNotification, InvestorNotifications } from "../api/generated/banxumApi";
import { markNotificationsRead, notificationRoute } from "./notifications";

const notification = (id: string, unread: boolean): InvestorNotification => ({
  id,
  notification_source: "email_delivery",
  topic: "email.investor_notice",
  status: "sent",
  title: id,
  body: "",
  created_at: "2026-10-01T10:00:00Z",
  sent_at: "2026-10-01T10:00:00Z",
  unread,
  navigation_target: "none",
  navigation_target_id: "",
  metadata: {}
});

describe("notification helpers", () => {
  test("each target opens its portal page and falls back to the Notifications page", () => {
    expect(notificationRoute({ navigation_target: "loan", navigation_target_id: "L1" })).toEqual({ name: "loan", params: { loanId: "L1" } });
    expect(notificationRoute({ navigation_target: "holding", navigation_target_id: "H1" })).toEqual({ name: "investment", params: { holdingId: "H1" } });
    expect(notificationRoute({ navigation_target: "holding", navigation_target_id: "" })).toEqual({ name: "portfolio" });
    expect(notificationRoute({ navigation_target: "balances", navigation_target_id: "" })).toEqual({ name: "balances" });
    expect(notificationRoute({ navigation_target: "secondary_market", navigation_target_id: "" })).toEqual({ name: "secondary" });
    expect(notificationRoute({ navigation_target: "fx", navigation_target_id: "" })).toEqual({ name: "fx" });
    expect(notificationRoute({ navigation_target: "loan", navigation_target_id: "" })).toEqual({ name: "notifications" });
    expect(notificationRoute({ navigation_target: "none", navigation_target_id: "" })).toEqual({ name: "notifications" });
  });

  test("marking read lowers the unread count once per newly read notification", () => {
    // The server counts unread notices beyond the listed page, so the count is lowered, not recounted.
    const payload: InvestorNotifications = {
      notifications: [notification("a", true), notification("b", true), notification("c", false)],
      unread_count: 5
    };

    const one = markNotificationsRead(payload, ["a", "c", "missing"]);
    expect(one.unread_count).toBe(4);
    expect(one.notifications.map((item) => item.unread)).toEqual([false, true, false]);
    expect(markNotificationsRead(one, ["a"]).unread_count).toBe(4);

    const all = markNotificationsRead(payload, "all");
    expect(all.unread_count).toBe(0);
    expect(all.notifications.every((item) => !item.unread)).toBe(true);
  });
});
