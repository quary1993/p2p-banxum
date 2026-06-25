import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";

import { formatMoneyMinor } from "./format";

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
  | "refresh";

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
  refresh: "M21 12a9 9 0 11-2.6-6.4M21 4v6h-6"
};

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
  penalty: { tone: "bad", label: "Penalty mode" }
};

export type Tone = "ok" | "warn" | "bad" | "info" | "neutral" | "accent";

export function Chip({
  status,
  tone,
  children,
  dot = true,
  square = false
}: {
  status?: string;
  tone?: Tone;
  children?: ReactNode;
  dot?: boolean;
  square?: boolean;
}) {
  const mapped = status ? statusMap[status] : undefined;
  const finalTone = tone ?? mapped?.tone ?? "neutral";
  const label = children ?? mapped?.label ?? status;
  return (
    <span className={`chip chip-${finalTone} ${square ? "chip-square" : ""}`}>
      {dot ? <span className="dot" /> : null}
      {label}
    </span>
  );
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
  className = ""
}: {
  children: ReactNode;
  padded?: boolean;
  className?: string;
}) {
  return <div className={`card ${padded ? "card-pad" : ""} ${className}`}>{children}</div>;
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

export function Field({
  label,
  hint,
  error,
  children
}: {
  label?: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div className="field">
      {label ? <label>{label}</label> : null}
      {children}
      {error ? <span className="err">{error}</span> : hint ? <span className="hint">{hint}</span> : null}
    </div>
  );
}

export function Check({
  checked,
  onChange,
  children,
  id
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: ReactNode;
  id: string;
}) {
  return (
    <label className="check" htmlFor={id}>
      <input checked={checked} id={id} onChange={(event) => onChange(event.target.checked)} type="checkbox" />
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
  onChange
}: {
  options: Array<{ value: T; label: string }>;
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="seg" role="tablist">
      {options.map((option) => (
        <button
          aria-selected={value === option.value}
          className={value === option.value ? "on" : ""}
          key={option.value}
          onClick={() => onChange(option.value)}
          role="tab"
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
  onChange
}: {
  tabs: Array<{ value: T; label: string }>;
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((tab) => (
        <button
          aria-selected={value === tab.value}
          className={value === tab.value ? "on" : ""}
          key={tab.value}
          onClick={() => onChange(tab.value)}
          role="tab"
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
  drawer = false
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
  drawer?: boolean;
}) {
  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", listener);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", listener);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  return (
    <div className="scrim" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div aria-label={title} aria-modal="true" className={`modal ${wide ? "wide" : ""} ${drawer ? "drawer" : ""}`} role="dialog">
        <div className="modal-head">
          <h3>{title}</h3>
          <button aria-label="Close" className="x-btn" onClick={onClose} type="button">
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
