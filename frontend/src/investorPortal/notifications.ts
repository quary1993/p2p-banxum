import type { InvestorNotification, InvestorNotifications } from "../api/generated/banxumApi";
import type { AppRoute } from "./types";

type NotificationNavigation = Pick<InvestorNotification, "navigation_target" | "navigation_target_id"> &
  Partial<Pick<InvestorNotification, "topic">>;

/** Portal page a notification opens; without a usable target it opens the Notifications page. */
export function notificationRoute(notification: NotificationNavigation): AppRoute {
  const targetId = notification.navigation_target_id;
  switch (notification.navigation_target) {
    case "loan":
      return targetId ? { name: "loan", params: { loanId: targetId } } : { name: "notifications" };
    case "holding":
      return targetId
        ? {
            name: "investment",
            params: {
              holdingId: targetId,
              ...(notification.topic === "email.loan_risk_note_published"
                ? { section: "loan-notes" }
                : {})
            }
          }
        : { name: "portfolio" };
    case "portfolio":
      return { name: "portfolio" };
    case "balances":
      return { name: "balances" };
    case "secondary_market":
      return { name: "secondary" };
    case "fx":
      return { name: "fx" };
    // 18.3: movements, reports and documents.
    case "transactions":
      return { name: "transactions" };
    case "reports":
      return { name: "reports" };
    case "documents":
      return { name: "documents" };
    default:
      // The design's "View transactions" for money that left the account (withdrawals, automatic returns).
      if (notification.topic === "email.withdrawal_status" || notification.topic === "email.balance_forced_return") return { name: "transactions" };
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

function isFailedDelivery(item: Pick<InvestorNotification, "status">) {
  return item.status === "failed" || item.status === "dead_letter";
}

/**
 * 18.3: the design's tone of a notification row (.nd-row.is-positive / is-late / is-attention) from the
 * API's category; a failed email reads as late. Neutral rows have no tone class.
 */
export function notificationTone(item: Pick<InvestorNotification, "status" | "category">) {
  if (isFailedDelivery(item)) return "late";
  if (item.category === "positive") return "positive";
  if (item.category === "late") return "late";
  if (item.category === "default") return "attention";
  return "";
}

/** The design's icon of a notification: by its tone, then by what it opens. */
export function notificationIcon(item: Pick<InvestorNotification, "status" | "category" | "navigation_target">) {
  if (isFailedDelivery(item) || item.category === "late") return "alert";
  if (item.category === "default") return "alert-fill";
  switch (item.navigation_target) {
    case "balances":
      return "arrow-down-left";
    case "loan":
    case "holding":
      return "briefcase";
    case "portfolio":
      return "growth";
    case "secondary_market":
      return "exchange";
    case "transactions":
      return "tranx";
    case "reports":
    case "documents":
      return "file-text";
    default:
      return "bell";
  }
}
