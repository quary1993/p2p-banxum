//IP of Webby-Soft SRL.
// source-seal: SVAgQkVMT05HUyBUTyBXRUJCWS1TT0ZUIFNSTC4=
import {
  cloneElement,
  isValidElement,
  useCallback,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactElement,
  type ReactNode
} from "react";
import { createPortal } from "react-dom";

import { handleTabListKeyDown, useDialog } from "./dialog";
import { formatMoneyMinor, humanizeEnum } from "./format";

type IconName =
  | "dashboard"
  | "market"
  | "portfolio"
  | "swap"
  | "balance"
  | "secondary"
  | "docs"
  | "settings"
  | "bell"
  | "search"
  | "arrowR"
  | "arrowL"
  | "chevR"
  | "chevD"
  | "check"
  | "checkCircle"
  | "x"
  | "alert"
  | "info"
  | "clock"
  | "lock"
  | "download"
  | "plus"
  | "filter"
  | "copy"
  | "phone"
  | "shield"
  | "doc"
  | "logout"
  | "menu"
  | "wallet"
  | "trend"
  | "refresh"
  | "briefcase"
  | "user"
  | "help"
  | "grid"
  | "list"
  | "building"
  | "more"
  | "arrowUpRight"
  | "arrowDownLeft"
  | "eye"
  | "calendar"
  | "globe"
  | "mail"
  | "external"
  | "home"
  | "pin"
  | "percent"
  | "chart"
  | "upload"
  | "star"
  | "minus";

const icons: Record<IconName, string> = {
  dashboard: "M3 3h7v7H3zM14 3h7v4h-7zM14 10h7v11h-7zM3 13h7v8H3z",
  market: "M3 21h18M5 21V8l7-5 7 5v13M9 21v-6h6v6",
  portfolio: "M4 19V5m0 14h16M8 16V9m4 7V6m4 10v-4",
  swap: "M7 7h11l-3-3M17 17H6l3 3",
  balance: "M3 7h18v12H3zM3 7l2-3h14l2 3M16 13h2",
  secondary: "M4 7h16M4 12h10M4 17h13M18 14l3 3-3 3",
  docs: "M6 2h8l4 4v16H6zM14 2v4h4",
  settings:
    "M12 15a3 3 0 100-6 3 3 0 000 6zM19.4 13.5a7.9 7.9 0 000-3l2-1.5-2-3.5-2.4 1a8 8 0 00-2.6-1.5L14 2h-4l-.4 2.5a8 8 0 00-2.6 1.5l-2.4-1-2 3.5 2 1.5a7.9 7.9 0 000 3l-2 1.5 2 3.5 2.4-1a8 8 0 002.6 1.5L10 22h4l.4-2.5a8 8 0 002.6-1.5l2.4 1 2-3.5z",
  bell: "M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 01-3.4 0",
  search: "M11 11m-7 0a7 7 0 1014 0 7 7 0 10-14 0M21 21l-4.3-4.3",
  arrowR: "M5 12h14M13 6l6 6-6 6",
  arrowL: "M19 12H5M11 18l-6-6 6-6",
  chevR: "M9 6l6 6-6 6",
  chevD: "M6 9l6 6 6-6",
  check: "M20 6L9 17l-5-5",
  checkCircle: "M22 11.1V12a10 10 0 11-5.9-9.1M22 4L12 14.1l-3-3",
  x: "M18 6L6 18M6 6l12 12",
  alert: "M12 9v4m0 4h.01M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L14.7 3.9a2 2 0 00-3.4 0z",
  info: "M12 16v-4m0-4h.01M12 22a10 10 0 100-20 10 10 0 000 20z",
  clock: "M12 22a10 10 0 100-20 10 10 0 000 20zM12 6v6l4 2",
  lock: "M5 11h14v10H5zM8 11V7a4 4 0 018 0v4",
  download: "M12 3v12m0 0l-4-4m4 4l4-4M5 21h14",
  plus: "M12 5v14M5 12h14",
  filter: "M3 5h18l-7 8v6l-4 2v-8z",
  copy: "M9 9h11v11H9zM5 15H4V4h11v1",
  phone:
    "M22 16.9v3a2 2 0 01-2.2 2 19.8 19.8 0 01-8.6-3 19.5 19.5 0 01-6-6 19.8 19.8 0 01-3-8.6A2 2 0 014.1 2h3a2 2 0 012 1.7c.1.9.3 1.8.6 2.6a2 2 0 01-.5 2.1L8.1 9.9a16 16 0 006 6l1.5-1.1a2 2 0 012.1-.5c.8.3 1.7.5 2.6.6a2 2 0 011.7 2z",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  doc: "M6 2h8l4 4v16H6zM14 2v4h4",
  logout: "M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9",
  menu: "M3 6h18M3 12h18M3 18h18",
  wallet: "M3 7h18v12H3zM3 7l2-3h14l2 3M16 13h2",
  trend: "M3 17l6-6 4 4 7-7M14 8h7v7",
  refresh: "M21 12a9 9 0 11-2.6-6.4M21 4v6h-6",
  briefcase: "M3 8h18v12H3zM8 8V5h8v3M3 13h18",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 21a8 8 0 0116 0",
  help: "M12 22a10 10 0 100-20 10 10 0 000 20zM9.1 9a3 3 0 015.8 1c0 2-3 3-3 3M12 17h.01",
  grid: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
  list: "M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01",
  building: "M4 21V5l8-3v19M12 8l8 3v10M2 21h20M8 9h.01M8 13h.01M8 17h.01M16 14h.01M16 18h.01",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  arrowUpRight: "M7 17L17 7M8 7h9v9",
  arrowDownLeft: "M17 7L7 17M16 17H7V8",
  eye: "M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12zM12 15a3 3 0 100-6 3 3 0 000 6z",
  calendar: "M4 5h16v16H4zM4 10h16M8 3v4M16 3v4",
  globe: "M12 22a10 10 0 100-20 10 10 0 000 20zM2 12h20M12 2a15 15 0 010 20M12 2a15 15 0 000 20",
  mail: "M3 5h18v14H3zM3 6l9 7 9-7",
  external: "M14 4h6v6M20 4l-9 9M18 14v6H4V6h6",
  home: "M3 11l9-8 9 8M5 9.5V21h14V9.5",
  pin: "M12 22s7-7.2 7-12.5a7 7 0 10-14 0C5 14.8 12 22 12 22zM12 12a2.5 2.5 0 100-5 2.5 2.5 0 000 5z",
  percent: "M19 5L5 19M7 9a2 2 0 100-4 2 2 0 000 4zM17 19a2 2 0 100-4 2 2 0 000 4z",
  chart: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  upload: "M12 21V9m0 0l-4 4m4-4l4 4M5 3h14",
  star: "M12 3l2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2l1.1-6.2L3 9.6l6.2-.9z",
  minus: "M5 12h14"
};

export type { IconName };

// The user-facing skin is scoped by a class on <html>, so portal content such as
// tooltips gets it as well. The admin console never mounts this wrapper.
let userSkinMounts = 0;

export function UserSkin({ children }: { children: ReactNode }) {
  useLayoutEffect(() => {
    userSkinMounts += 1;
    document.documentElement.classList.add("bxm");
    return () => {
      userSkinMounts -= 1;
      if (userSkinMounts <= 0) {
        userSkinMounts = 0;
        document.documentElement.classList.remove("bxm");
      }
    };
  }, []);
  return <>{children}</>;
}

export function PageHead({
  title,
  description,
  eyebrow,
  back,
  actions,
  className = ""
}: {
  title: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  back?: { label: string; onClick: () => void };
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`page-head ${className}`}>
      <div className="page-head-main">
        {back ? (
          <button className="page-back" onClick={back.onClick} type="button">
            <Icon name="arrowL" size={18} />
            <span>{back.label}</span>
          </button>
        ) : null}
        {eyebrow ? <div className="eyebrow page-eyebrow">{eyebrow}</div> : null}
        <h1>{title}</h1>
        {description ? <div className="ph-sub">{description}</div> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </div>
  );
}

export function Icon({
  name,
  size = 16,
  className = "",
  strokeWidth = 1.7
}: {
  name: IconName;
  size?: number;
  className?: string;
  strokeWidth?: number;
}) {
  const filled = name === "dashboard";
  return (
    <svg
      aria-hidden="true"
      className={className}
      fill={filled ? "currentColor" : "none"}
      height={size}
      stroke={filled ? "none" : "currentColor"}
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={strokeWidth}
      viewBox="0 0 24 24"
      width={size}
    >
      <path d={icons[name]} />
    </svg>
  );
}

export function Tooltip({
  children,
  content,
  focusable = true,
  label,
  className = ""
}: {
  children: ReactNode;
  content: ReactNode;
  focusable?: boolean;
  label?: string;
  className?: string;
}) {
  const anchorRef = useRef<HTMLSpanElement>(null);
  const tooltipId = useId();
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ left: 0, placement: "top" as "top" | "bottom", top: 0 });
  const hasContent = content !== null && content !== undefined && content !== "";

  const updatePosition = useCallback(() => {
    const anchor = anchorRef.current;
    if (!anchor) return;
    const rect = anchor.getBoundingClientRect();
    const viewportWidth = document.documentElement.clientWidth;
    const estimatedHalfWidth = Math.min(160, Math.max(90, (viewportWidth - 24) / 2));
    const left = Math.max(
      12 + estimatedHalfWidth,
      Math.min(viewportWidth - 12 - estimatedHalfWidth, rect.left + rect.width / 2)
    );
    const placement = rect.top >= 88 ? "top" : "bottom";
    setPosition({
      left,
      placement,
      top: placement === "top" ? rect.top : rect.bottom
    });
  }, []);

  useLayoutEffect(() => {
    if (!open || !hasContent) return undefined;
    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [hasContent, open, updatePosition]);

  if (!hasContent) return <>{children}</>;

  return (
    <span
      aria-describedby={open ? tooltipId : undefined}
      aria-label={label}
      className={`ui-tooltip-anchor ${focusable ? "is-focusable" : ""} ${className}`}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
      onFocus={() => setOpen(true)}
      onKeyDown={(event) => {
        if (event.key === "Escape") {
          setOpen(false);
          anchorRef.current?.blur();
        }
      }}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onPointerDown={(event) => {
        if (event.pointerType === "touch" && focusable) event.currentTarget.focus();
      }}
      ref={anchorRef}
      tabIndex={focusable ? 0 : undefined}
    >
      {children}
      {open
        ? createPortal(
            <span
              className={`ui-tooltip-popup ${position.placement}`}
              id={tooltipId}
              role="tooltip"
              style={{ left: position.left, top: position.top }}
            >
              {content}
            </span>,
            document.body
          )
        : null}
    </span>
  );
}

export function Money({
  amountMinor,
  currency,
  sign = false,
  decimals = 2,
  showCurrency = true
}: {
  amountMinor: number | null | undefined;
  currency: string;
  sign?: boolean;
  decimals?: number;
  showCurrency?: boolean;
}) {
  const value = amountMinor ?? 0;
  const className = sign ? (value > 0 ? "pos" : value < 0 ? "neg" : "") : "";
  return (
    <span className={`money ${className}`}>
      {showCurrency ? <span className="muted">{currency} </span> : null}
      {sign && value > 0 ? "+" : ""}
      {formatMoneyMinor(amountMinor, currency, decimals)}
    </span>
  );
}

export function Button({
  children,
  variant = "default",
  size,
  icon,
  block,
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "primary" | "danger" | "ghost" | "link";
  size?: "sm" | "lg";
  icon?: IconName;
  block?: boolean;
}) {
  const variantClass =
    variant === "primary"
      ? "btn-primary"
      : variant === "danger"
        ? "btn-danger"
        : variant === "ghost"
          ? "btn-ghost"
          : variant === "link"
            ? "btn-link"
            : "";
  return (
    <button
      className={`btn ${variantClass} ${size === "sm" ? "btn-sm" : ""} ${
        size === "lg" ? "btn-lg" : ""
      } ${block ? "btn-block" : ""} ${className}`}
      type={rest.type ?? "button"}
      {...rest}
    >
      {icon ? <Icon name={icon} size={15} /> : null}
      {children}
    </button>
  );
}

const statusMap: Record<string, { tone: Tone; label: string }> = {
  active: { tone: "ok", label: "Active" },
  approved: { tone: "ok", label: "Approved" },
  available: { tone: "ok", label: "Available" },
  funded: { tone: "neutral", label: "Funded" },
  open: { tone: "accent", label: "Open" },
  published: { tone: "accent", label: "Open" },
  performing: { tone: "ok", label: "Performing" },
  late: { tone: "warn", label: "Late" },
  defaulted: { tone: "bad", label: "Default" },
  default: { tone: "bad", label: "Default" },
  recovery: { tone: "neutral", label: "Recovery" },
  written_off: { tone: "bad", label: "Default" },
  pending: { tone: "neutral", label: "Pending" },
  pending_allocation: { tone: "neutral", label: "Pending allocation" },
  partially_allocated: { tone: "info", label: "Partially allocated" },
  balance_allocated: { tone: "info", label: "Balance allocated" },
  balance_released: { tone: "neutral", label: "Balance released" },
  closed_invested: { tone: "ok", label: "Invested" },
  closed_not_invested: { tone: "neutral", label: "Not invested" },
  allocated: { tone: "ok", label: "Allocated" },
  settled: { tone: "ok", label: "Settled" },
  verified: { tone: "ok", label: "Verified" },
  investable: { tone: "ok", label: "Investable" },
  withdraw_only: { tone: "warn", label: "Withdraw-only" },
  overdue: { tone: "warn", label: "Overdue" },
  penalty: { tone: "bad", label: "Frozen, penalty charged" },
  penalty_mode: { tone: "bad", label: "Frozen, penalty charged" },
  penalty_exhausted: { tone: "bad", label: "Used up by penalty" },
  frozen: { tone: "bad", label: "Frozen" },
  consumed: { tone: "neutral", label: "Used" },
  requested: { tone: "warn", label: "Pending" },
  finalized: { tone: "ok", label: "Paid out" },
  cancelled: { tone: "neutral", label: "Cancelled" },
  pending_verification: { tone: "warn", label: "Pending verification" },
  revoked: { tone: "bad", label: "Revoked" },
  rejected: { tone: "bad", label: "Rejected" },
  disabled: { tone: "neutral", label: "Not in use" }
};

export type Tone = "ok" | "warn" | "bad" | "info" | "neutral" | "accent";

export function Chip({
  status,
  tone,
  children,
  dot = true,
  square = false,
  tooltip
}: {
  status?: string;
  tone?: Tone;
  children?: ReactNode;
  dot?: boolean;
  square?: boolean;
  tooltip?: string;
}) {
  const mapped = status ? statusMap[status] : undefined;
  const finalTone = tone ?? mapped?.tone ?? "neutral";
  // Unknown API values are shown as readable words, never as raw enum keys.
  const label = children ?? mapped?.label ?? humanizeEnum(status);
  const accessibleLabel = tooltip && typeof label === "string" ? `${label}. ${tooltip}` : undefined;
  const chip = (
    <span
      className={`chip chip-${finalTone} ${square ? "chip-square" : ""} ${status ? `chip-status-${status}` : ""}`}
    >
      {dot ? <span className="dot" /> : null}
      {label}
    </span>
  );
  return tooltip ? <Tooltip content={tooltip} label={accessibleLabel}>{chip}</Tooltip> : chip;
}

export function Rating({ value }: { value: string }) {
  const rating = value.slice(0, 1).toLowerCase();
  return <span className={`rating rating-${rating}`}>{value}</span>;
}

export function Country({ code }: { code: string }) {
  return <span className="tag">{code}</span>;
}

export function Card({
  children,
  padded = false,
  className = "",
  id
}: {
  children: ReactNode;
  padded?: boolean;
  className?: string;
  id?: string;
}) {
  return <div className={`card ${padded ? "card-pad" : ""} ${className}`} id={id}>{children}</div>;
}

export function Stat({
  label,
  amountMinor,
  currency,
  raw,
  sub
}: {
  label: string;
  amountMinor?: number;
  currency?: string;
  raw?: string;
  sub?: string;
}) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {currency ? <span className="ccy">{currency}</span> : null}
        {raw ?? formatMoneyMinor(amountMinor ?? 0, currency)}
      </div>
      {sub ? <div className="stat-sub">{sub}</div> : null}
    </div>
  );
}

export function Banner({
  tone = "info",
  icon,
  title,
  children,
  actions
}: {
  tone?: Tone;
  icon?: IconName;
  title?: string;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  const iconName = icon ?? (tone === "bad" || tone === "warn" ? "alert" : tone === "ok" ? "checkCircle" : "info");
  return (
    <div className={`banner banner-${tone}`} role={tone === "bad" ? "alert" : "status"}>
      <Icon className="b-ico" name={iconName} size={18} />
      <div className="grow">
        {title ? <h4>{title}</h4> : null}
        {children ? <p>{children}</p> : null}
        {actions ? <div className="row gap-8 wrap" style={{ marginTop: 10 }}>{actions}</div> : null}
      </div>
    </div>
  );
}

const fieldControlSelector = "input:not([type=hidden]), select, textarea";

function mergeIdList(existing: string | null | undefined, add: string | undefined, remove?: string) {
  const ids = (existing ?? "").split(/\s+/).filter((item) => item && item !== remove && item !== add);
  if (add) ids.push(add);
  return ids.length > 0 ? ids.join(" ") : undefined;
}

// A labelled form field. The label is linked to its control (htmlFor/id) and the hint or error is
// linked with aria-describedby, so assistive technology and getByLabelText find the control. A
// direct <input>/<select>/<textarea> child gets the id at once; a control nested in a wrapper is
// found after render (the first one without its own aria-label, e.g. the number next to a prefix).
export function Field({
  label,
  hint,
  error,
  children,
  id
}: {
  label?: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  id?: string;
}) {
  const autoId = useId();
  const containerRef = useRef<HTMLDivElement>(null);
  const [controlId, setControlId] = useState(id ?? `${autoId}control`);
  const descriptionId = `${autoId}description`;
  const description = error || hint ? descriptionId : undefined;
  let content = children;
  if (isValidElement(children) && typeof children.type === "string" && ["input", "select", "textarea"].includes(children.type)) {
    const props = children.props as { id?: string; "aria-describedby"?: string; "aria-invalid"?: boolean | "true" | "false" };
    content = cloneElement(children as ReactElement<Record<string, unknown>>, {
      id: props.id ?? controlId,
      "aria-describedby": mergeIdList(props["aria-describedby"], description, descriptionId),
      "aria-invalid": error ? true : props["aria-invalid"]
    });
  }
  useLayoutEffect(() => {
    const controls = Array.from(containerRef.current?.querySelectorAll<HTMLElement>(fieldControlSelector) ?? []);
    const control = controls.find((item) => item.id === controlId)
      ?? controls.find((item) => !item.hasAttribute("aria-label") && !item.hasAttribute("aria-labelledby"))
      ?? controls[0];
    if (!control) return;
    if (!control.id) control.id = controlId;
    if (control.id !== controlId) {
      setControlId(control.id);
      return;
    }
    const describedBy = mergeIdList(control.getAttribute("aria-describedby"), description, descriptionId);
    if (describedBy) control.setAttribute("aria-describedby", describedBy);
    else control.removeAttribute("aria-describedby");
    if (error) control.setAttribute("aria-invalid", "true");
    else if (control.dataset.fieldInvalid === "true") control.removeAttribute("aria-invalid");
    control.dataset.fieldInvalid = error ? "true" : "false";
  }, [children, controlId, description, descriptionId, error]);
  return (
    <div className="field" ref={containerRef}>
      {label ? <label htmlFor={controlId}>{label}</label> : null}
      {content}
      {error ? <span className="err" id={descriptionId}>{error}</span> : hint ? <span className="hint" id={descriptionId}>{hint}</span> : null}
    </div>
  );
}

export function Check({
  checked,
  onChange,
  children,
  disabled = false,
  id
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: ReactNode;
  disabled?: boolean;
  id: string;
}) {
  return (
    <label className={`check${disabled ? " disabled" : ""}`} htmlFor={id}>
      <input checked={checked} disabled={disabled} id={id} onChange={(event) => onChange(event.target.checked)} type="checkbox" />
      <span className="box">
        <Icon name="check" size={12} strokeWidth={2.6} />
      </span>
      <span className="ctext">{children}</span>
    </label>
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label
}: {
  options: Array<{ value: T; label: string }>;
  value: T;
  onChange: (value: T) => void;
  label?: string;
}) {
  return (
    <div aria-label={label} className="seg" onKeyDown={handleTabListKeyDown} role="tablist">
      {options.map((option) => (
        <button
          aria-selected={value === option.value}
          className={value === option.value ? "on" : ""}
          key={option.value}
          onClick={() => onChange(option.value)}
          role="tab"
          tabIndex={value === option.value ? 0 : -1}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
  label,
  idPrefix
}: {
  tabs: Array<{ value: T; label: string }>;
  value: T;
  onChange: (value: T) => void;
  label?: string;
  /** When set, tab i controls the panel `${idPrefix}-panel-${value}` (see tabPanelProps). */
  idPrefix?: string;
}) {
  return (
    <div aria-label={label} className="tabs" onKeyDown={handleTabListKeyDown} role="tablist">
      {tabs.map((tab) => (
        <button
          aria-controls={idPrefix ? `${idPrefix}-panel-${tab.value}` : undefined}
          aria-selected={value === tab.value}
          className={value === tab.value ? "on" : ""}
          id={idPrefix ? `${idPrefix}-tab-${tab.value}` : undefined}
          key={tab.value}
          onClick={() => onChange(tab.value)}
          role="tab"
          tabIndex={value === tab.value ? 0 : -1}
          type="button"
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
  footer,
  wide = false,
  xwide = false,
  drawer = false,
  busy = false
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
  xwide?: boolean;
  drawer?: boolean;
  /** A money action is running: Escape, the backdrop and the close button do nothing. */
  busy?: boolean;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const { blocked, dismissFromBackdrop } = useDialog({ dialogRef, onDismiss: onClose, busy });

  return (
    <div className="scrim" onMouseDown={(event) => event.target === event.currentTarget && dismissFromBackdrop()}>
      <div aria-busy={blocked || undefined} aria-labelledby={titleId} aria-modal="true" className={`modal ${wide ? "wide" : ""} ${xwide ? "xwide" : ""} ${drawer ? "drawer" : ""}`} ref={dialogRef} role="dialog">
        <div className="modal-head">
          <h3 id={titleId}>{title}</h3>
          <button aria-label="Close" className="x-btn" disabled={blocked} onClick={onClose} type="button">
            <Icon name="x" size={17} />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer ? <div className="modal-foot">{footer}</div> : null}
      </div>
    </div>
  );
}

export function Review({ rows }: { rows: Array<{ label: string; value: ReactNode; total?: boolean; tone?: Tone }> }) {
  return (
    <div className="review">
      {rows.map((row) => (
        <div className={`rrow ${row.total ? "total" : ""}`} key={row.label}>
          <span className="rk">{row.label}</span>
          <span className={`rv ${row.tone === "bad" ? "neg" : row.tone === "ok" ? "pos" : ""}`}>{row.value}</span>
        </div>
      ))}
    </div>
  );
}

export function Progress({ percent, tone }: { percent: number; tone?: "warn" | "bad" }) {
  const color = tone === "bad" ? "var(--bad)" : tone === "warn" ? "var(--warn)" : "var(--accent)";
  return (
    <div className="bar">
      <span style={{ background: color, width: `${Math.max(0, Math.min(100, percent))}%` }} />
    </div>
  );
}

export function DeadlineMeter({ daysUntilWithdrawal }: { daysUntilWithdrawal: number }) {
  const daysHeld = Math.max(0, 60 - daysUntilWithdrawal);
  const percent = Math.min(100, (daysHeld / 60) * 100);
  const color = daysUntilWithdrawal <= 7 ? "var(--bad)" : daysUntilWithdrawal <= 30 ? "var(--warn)" : "var(--ok)";
  return (
    <div className="dmeter">
      <span style={{ background: color, width: `${percent}%` }} />
    </div>
  );
}

export function Empty({
  icon = "info",
  title,
  children
}: {
  icon?: IconName;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <Icon className="faint" name={icon} size={30} />
      <h4>{title}</h4>
      {children ? <p>{children}</p> : null}
    </div>
  );
}

export function BarBreakdown({
  data
}: {
  data: Array<{ label: string; value: number; color?: string }>;
}) {
  const total = data.reduce((sum, item) => sum + item.value, 0) || 1;
  return (
    <div className="col gap-10">
      {data.map((item, index) => {
        const percent = Math.round((item.value / total) * 100);
        return (
          <div className="col gap-4" key={`${item.label}-${index}`}>
            <div className="row spread" style={{ fontSize: 12.5 }}>
              <span>{item.label}</span>
              <span className="mono muted">{percent}%</span>
            </div>
            <div className="bar">
              <span style={{ background: item.color ?? "var(--accent)", width: `${percent}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
