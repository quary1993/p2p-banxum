// IP of Webby-Soft SRL.
// U33 buttons (design: .btn.btn-primary, .btn.btn-outline-light, .btn.btn-trigger) and the link with an arrow.
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from "react";

import type { RouteName } from "../../investorPortal/types";
import { NiIcon } from "./Icon";
import { PortalLink } from "./navigation";

export type ButtonVariant = "primary" | "secondary" | "ghost";
const variantClass: Record<ButtonVariant, string> = {
  primary: "btn-primary",
  secondary: "btn-outline-light",
  ghost: "btn-trigger"
};

type CommonProps = {
  variant?: ButtonVariant;
  size?: "sm" | "lg";
  /** Nioicon name shown before the label. */
  icon?: string;
  /** Icon-only button: the label becomes the accessible name. */
  iconOnly?: boolean;
  children: ReactNode;
};

function buttonClass({ variant = "secondary", size, iconOnly }: CommonProps, extra = "") {
  return ["btn", size ? `btn-${size}` : "", iconOnly ? "btn-icon" : "", variantClass[variant], extra].filter(Boolean).join(" ");
}

function ButtonContent({ icon, iconOnly, children }: CommonProps) {
  return (
    <>
      {icon ? <NiIcon name={icon} /> : null}
      {iconOnly ? <span className="visually-hidden">{children}</span> : <span>{children}</span>}
    </>
  );
}

/** A U33 <button>; secondary (outlined) by default. */
export function Button({ variant, size, icon, iconOnly, children, className = "", type = "button", ...rest }: CommonProps & ButtonHTMLAttributes<HTMLButtonElement>) {
  const props = { variant, size, icon, iconOnly, children };
  return (
    <button {...rest} className={buttonClass(props, className)} type={type}>
      <ButtonContent {...props} />
    </button>
  );
}

/** A U33 button-styled link to a portal route. */
export function ButtonLink({ to, params, variant, size, icon, iconOnly, children, className = "", ...rest }: CommonProps & { to: RouteName; params?: Record<string, string> } & Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href">) {
  const props = { variant, size, icon, iconOnly, children };
  return (
    <PortalLink {...rest} className={buttonClass(props, className)} params={params} to={to}>
      <ButtonContent {...props} />
    </PortalLink>
  );
}

/** Text link followed by an arrow in a circle (design: "View account →" on Overview cards). */
export function LinkArrow({ to, params, onClick, children, className = "" }: { to?: RouteName; params?: Record<string, string>; onClick?: () => void; children: ReactNode; className?: string }) {
  const content = (
    <>
      <span>{children}</span>
      <NiIcon name="arrow-right" />
    </>
  );
  if (to) {
    return <PortalLink className={`u33-link-arrow ${className}`.trim()} params={params} to={to}>{content}</PortalLink>;
  }
  return <button className={`u33-link-arrow ${className}`.trim()} onClick={onClick} type="button">{content}</button>;
}
