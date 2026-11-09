// IP of Webby-Soft SRL.
// U33 card/panel (design: section.card.card-bordered > .card-inner); `className` adds the screen's own class.
import type { ReactNode } from "react";

export function Card({
  title,
  footer,
  className = "",
  innerClassName = "",
  children
}: {
  /** Card label, as the design's h6.subtitle. */
  title?: ReactNode;
  /** Bottom row, e.g. a <LinkArrow>. */
  footer?: ReactNode;
  className?: string;
  innerClassName?: string;
  children?: ReactNode;
}) {
  return (
    <section className={`card card-bordered ${className}`.trim()}>
      <div className={`card-inner ${innerClassName}`.trim()}>
        {title ? <h6 className="subtitle">{title}</h6> : null}
        {children}
        {footer ? <div className="u33-card-footer">{footer}</div> : null}
      </div>
    </section>
  );
}
