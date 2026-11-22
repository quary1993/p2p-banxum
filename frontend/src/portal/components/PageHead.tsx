// IP of Webby-Soft SRL.
// U33 page head (design: .nk-block-head > .nk-block-between): title, optional subtitle, actions on the right.
import { Children, type ReactNode } from "react";

export function PageHead({
  title,
  subtitle,
  actions,
  headingLevel = 1
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  /** One node per action; several are laid out as the design's .nk-block-tools list. */
  actions?: ReactNode;
  /** The design uses h3.page-title; the app keeps one h1 per page for screen readers. */
  headingLevel?: 1 | 2 | 3;
}) {
  const Heading = `h${headingLevel}` as "h1" | "h2" | "h3";
  const actionList = Children.toArray(actions);
  return (
    <div className="nk-block-head nk-block-head-sm">
      <div className="nk-block-between g-3">
        <div className="nk-block-head-content">
          <Heading className="nk-block-title page-title">{title}</Heading>
          {subtitle ? <div className="nk-block-des text-soft"><p>{subtitle}</p></div> : null}
        </div>
        {actionList.length === 1 ? <div className="nk-block-head-content">{actionList[0]}</div> : null}
        {actionList.length > 1 ? (
          <div className="nk-block-head-content">
            <ul className="nk-block-tools g-3">{actionList.map((action, index) => <li key={index}>{action}</li>)}</ul>
          </div>
        ) : null}
      </div>
    </div>
  );
}
