import type { InvestorNotification, InvestorNotifications } from "../api/generated/banxumApi";
import type { AppRoute } from "./types";

/** Portal page a notification opens; without a usable target it opens the Notifications page. */
export function notificationRoute(notification: Pick<InvestorNotification, "navigation_target" | "navigation_target_id">): AppRoute {
  const targetId = notification.navigation_target_id;
  switch (notification.navigation_target) {
    case "loan":
      return targetId ? { name: "loan", params: { loanId: targetId } } : { name: "notifications" };
    case "holding":
      return targetId ? { name: "investment", params: { holdingId: targetId } } : { name: "portfolio" };
    case "portfolio":
      return { name: "portfolio" };
    case "balances":
      return { name: "balances" };
    case "secondary_market":
      return { name: "secondary" };
    case "fx":
      return { name: "fx" };
    default:
      return { name: "notifications" };
  }
}

/** Marks notifications read in a loaded payload (one or more ids, or all) and lowers the unread count to match. */
export function markNotificationsRead(payload: InvestorNotifications, ids: string[] | "all"): InvestorNotifications {
  if (ids === "all") {
    return {
      ...payload,
      notifications: payload.notifications.map((notification) => (notification.unread ? { ...notification, unread: false } : notification)),
      unread_count: 0
    };
  }
  const wanted = new Set(ids);
  let newlyRead = 0;
  const notifications = payload.notifications.map((notification) => {
    if (!wanted.has(notification.id) || !notification.unread) return notification;
    newlyRead += 1;
    return { ...notification, unread: false };
  });
  return { ...payload, notifications, unread_count: Math.max(0, payload.unread_count - newlyRead) };
}
