// IP of Webby-Soft SRL.
// Notifications bell of the U33 header (design: #bxm-notification-dropdown .nd-dropdown): unread dot,
// latest items with their destination, "Mark all as read", "View all notifications".
import type { InvestorNotification, InvestorNotifications } from "../../api/generated/banxumApi";
import { useT } from "../../i18n";
import { formatDate, formatDateTime } from "../../investorPortal/format";
import { notificationRoute } from "../../investorPortal/notifications";
import type { AppRoute } from "../../investorPortal/types";
import { Dropdown, NiIcon, usePortalNav } from "../components";

const MAX_ITEMS = 5;

function isFailed(item: InvestorNotification) {
  return item.status === "failed" || item.status === "dead_letter";
}

/** Design icon of a notification, by what it opens. */
function notificationIcon(item: InvestorNotification) {
  if (isFailed(item)) return "alert";
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
    default:
      return "bell";
  }
}

/** The design's destination line ("View investment →"), by the route the notification opens. */
function destinationLabel(route: AppRoute) {
  switch (route.name) {
    case "loan":
      return "View opportunity";
    case "investment":
    case "portfolio":
      return "View investment";
    case "balances":
      return "View account";
    case "secondary":
      return "View resale market";
    default:
      return "View notification";
  }
}

export function NotificationsMenu({
  notifications,
  onMarkRead,
  onMarkAllRead
}: {
  notifications: InvestorNotifications | undefined;
  onMarkRead: (id: string) => void;
  onMarkAllRead: () => void;
}) {
  const t = useT();
  const nav = usePortalNav();
  const unread = notifications?.unread_count ?? 0;
  const items = (notifications?.notifications ?? []).slice(0, MAX_ITEMS);
  return (
    <Dropdown
      className="notification-dropdown me-n1"
      id="bxm-notification-dropdown"
      menuClassName="dropdown-menu-s1 nd-dropdown"
      menuSize="xl"
      toggle={<div className={`icon-status ${unread > 0 ? "icon-status-info" : ""}`.trim()}><NiIcon name="bell" /></div>}
      toggleClassName="nk-quick-nav-icon"
      toggleLabel={t("Notifications")}
    >
      {(close) => (
        <>
          <div className="nd-dropdown-head">
            <div>
              <strong>{t("Notifications")}</strong>
              <span>{unread > 0 ? t("{count} unread", { count: unread }) : t("All read")}</span>
            </div>
            <a
              aria-label={t("Notification settings")}
              className="nd-dropdown-settings"
              href={nav.hrefFor("settings")}
              onClick={(event) => {
                event.preventDefault();
                close();
                nav.go("settings");
              }}
              title={t("Notification settings")}
            >
              <NiIcon name="setting" />
            </a>
            <button aria-label={t("Close notifications")} className="ra-dismiss ra-close-notifications" onClick={close} type="button">
              <NiIcon name="cross" />
            </button>
          </div>
          <div className="nd-dropdown-tools">
            <span>{t("Most recent")}</span>
            {unread > 0 ? (
              <button className="nd-read-all" onClick={onMarkAllRead} type="button">{t("Mark all as read")}</button>
            ) : null}
          </div>
          <div className="nd-dropdown-list">
            {items.length === 0 ? (
              <p className="nd-empty">{t("No notifications yet.")}</p>
            ) : (
              items.map((item) => {
                const route = notificationRoute(item);
                return (
                  <a
                    className={`nd-row nd-row-compact ${item.unread ? "is-unread" : ""} ${isFailed(item) ? "is-late" : ""}`.replace(/\s+/g, " ").trim()}
                    href={nav.hrefFor(route.name, route.params)}
                    key={item.id}
                    onClick={(event) => {
                      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                      event.preventDefault();
                      if (item.unread) onMarkRead(item.id);
                      close();
                      nav.go(route.name, route.params);
                    }}
                  >
                    <span aria-hidden="true" className="nd-icon"><NiIcon name={notificationIcon(item)} /></span>
                    <span className="nd-content">
                      <span className="nd-title">
                        {item.title}
                        {item.unread ? <span aria-label={t("Unread")} className="nd-unread-dot" role="img" /> : null}
                      </span>
                      {item.body ? <span className="nd-description">{item.body}</span> : null}
                    </span>
                    <span className="nd-row-meta">
                      <time dateTime={item.created_at} title={formatDateTime(item.created_at)}>{formatDate(item.created_at)}</time>
                      <span className="nd-destination">{t(destinationLabel(route))} <NiIcon name="arrow-right" /></span>
                    </span>
                  </a>
                );
              })
            )}
          </div>
          <div className="nd-dropdown-foot">
            <a
              href={nav.hrefFor("notifications")}
              onClick={(event) => {
                event.preventDefault();
                close();
                nav.go("notifications");
              }}
            >
              {t("View all notifications")} <NiIcon name="arrow-right" />
            </a>
          </div>
        </>
      )}
    </Dropdown>
  );
}
