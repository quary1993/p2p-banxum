// IP of Webby-Soft SRL.
/*
 * Notifications (design #/notifications: main.nd-page): All / Unread, Mark all as read, rows that
 * open the screen they are about (investorPortal/notifications.ts) and mark themselves read, and the
 * empty states. Rows use the design's .nd-row like the header menu (portal/shell/NotificationsMenu,
 * whose row is not exported: same markup and mapping here; the main session can merge them). Tone:
 * neutral, amber only for failed deliveries (the API has no category for other tones). Each row keeps
 * its human topic label (audit A-46).
 */
import { useState, type MouseEvent } from "react";

import type { InvestorNotification } from "../../../api/generated/banxumApi";
import { useT } from "../../../i18n";
import { useNotificationReadActions, useNotificationsData } from "../../../investorPortal/data";
import { formatDateTime } from "../../../investorPortal/format";
import { notificationRoute } from "../../../investorPortal/notifications";
import type { AppRoute } from "../../../investorPortal/types";
import { EmptyState, isPlainLeftClick, NiIcon, PageHead, PortalLink, usePortalNav } from "../../components";
import "./wallet.css";
import { clickOnSpace } from "../../components/keyboard";

function isFailed(item: InvestorNotification) {
  return item.status === "failed" || item.status === "dead_letter";
}

/** Design icon of a notification, by what it opens (same mapping as the header menu). */
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
    case "fx":
      return "View currency exchange";
    default:
      return "";
  }
}

function NotificationRow({ item, onOpen }: { item: InvestorNotification; onOpen: (item: InvestorNotification, route: AppRoute) => void }) {
  const t = useT();
  const nav = usePortalNav();
  const route = notificationRoute(item);
  const destination = destinationLabel(route);
  const className = `nd-row ${item.unread ? "is-unread" : ""} ${isFailed(item) ? "is-late" : ""}`.replace(/\s+/g, " ").trim();
  const content = (
    <>
      <span aria-hidden="true" className="nd-icon"><NiIcon name={notificationIcon(item)} /></span>
      <span className="nd-content">
        <span className="nd-title">
          {item.title}
          {item.unread ? <span aria-label={t("Unread")} className="nd-unread-dot" role="img" /> : null}
        </span>
        {item.body ? <span className="nd-description">{item.body}</span> : null}
        <span className="wl-nd-topic">
          {item.topic_label}
          {isFailed(item) ? <> · {t("Email not delivered")}</> : null}
        </span>
      </span>
      <span className="nd-row-meta">
        <time dateTime={item.created_at}>{formatDateTime(item.created_at)}</time>
        {destination ? <span className="nd-destination">{t(destination)} <NiIcon name="arrow-right" /></span> : null}
      </span>
    </>
  );
  if (!destination) {
    // Nothing to open: the row only marks itself read.
    return (
      <button aria-label={item.unread ? t("Mark as read: {title}", { title: item.title }) : undefined} className={`${className} wl-nd-static`} onClick={() => onOpen(item, route)} type="button">
        {content}
      </button>
    );
  }
  return (
    <a
      className={className}
      href={nav.hrefFor(route.name, route.params)}
      onClick={(event: MouseEvent<HTMLAnchorElement>) => {
        if (!isPlainLeftClick(event)) return;
        event.preventDefault();
        onOpen(item, route);
      }}
    >
      {content}
    </a>
  );
}

export function NotificationsScreen() {
  const t = useT();
  const nav = usePortalNav();
  const notificationsQuery = useNotificationsData(100);
  const readActions = useNotificationReadActions();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const payload = notificationsQuery.data;
  const all = payload?.notifications ?? [];
  const unread = payload?.unread_count ?? 0;
  const list = unreadOnly ? all.filter((item) => item.unread) : all;
  const open = (item: InvestorNotification, route: AppRoute) => {
    if (item.unread) void readActions.markRead(item.id).catch(() => undefined);
    if (route.name !== "notifications") nav.go(route.name, route.params);
  };
  const filter = (value: boolean, label: string, count: number) => (
    <a
      aria-pressed={unreadOnly === value}
      className={unreadOnly === value ? "active" : ""}
      href="#"
      onClick={(event) => {
        event.preventDefault();
        setUnreadOnly(value);
      }}
      onKeyDown={clickOnSpace}
      role="button"
    >
      {label}<span>{count}</span>
    </a>
  );

  return (
    <main className="nd-page">
      <PageHead
        actions={<PortalLink className="nd-settings-link" to="settings"><NiIcon name="setting" />{t("Notification settings")}</PortalLink>}
        title={t("Notifications")}
      />
      {!payload ? (
        notificationsQuery.isError ? (
          <EmptyState
            actions={<button className="btn btn-outline-light" onClick={() => void notificationsQuery.refetch()} type="button">{t("Try again")}</button>}
            icon="alert-circle"
            title={t("We could not load your notifications")}
          >
            {t("Your notifications are not available right now. Try again in a moment.")}
          </EmptyState>
        ) : (
          <div className="bxm-empty" role="status"><NiIcon name="loader" /><p>{t("Loading notifications...")}</p></div>
        )
      ) : (
        <>
          <div className="nd-toolbar">
            <nav aria-label={t("Notification view")} className="nd-filters">
              {filter(false, t("All"), all.length)}
              {filter(true, t("Unread"), unread)}
            </nav>
            <button className="nd-read-all" disabled={unread === 0} onClick={() => void readActions.markAllRead().catch(() => undefined)} type="button">
              <NiIcon name="check" />{t("Mark all as read")}
            </button>
          </div>
          <div className="nd-list">
            {list.length === 0 ? (
              <div className="nd-empty">
                <NiIcon name={unreadOnly ? "check-circle" : "bell"} />
                <h2>{unreadOnly ? t("No unread notifications") : t("No notifications yet")}</h2>
                <p>{unreadOnly ? t("You have read all your notifications.") : t("Updates about your investments and account will appear here.")}</p>
                {unreadOnly && all.length > 0 ? (
                  <a
                    className="nd-settings-link"
                    href="#"
                    onClick={(event) => {
                      event.preventDefault();
                      setUnreadOnly(false);
                    }}
                    onKeyDown={clickOnSpace}
                    role="button"
                  >
                    {t("View all notifications")} <NiIcon name="arrow-right" />
                  </a>
                ) : null}
              </div>
            ) : (
              list.map((item) => <NotificationRow item={item} key={item.id} onOpen={open} />)
            )}
          </div>
        </>
      )}
    </main>
  );
}
