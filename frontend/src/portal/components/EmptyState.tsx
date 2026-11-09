// IP of Webby-Soft SRL.
// Empty or no-result state (design: .r75-empty with icon, h3, text and actions).
import type { ReactNode } from "react";

import { NiIcon } from "./Icon";

export function EmptyState({ icon = "search", title, children, actions, className = "" }: { icon?: string; title: ReactNode; children?: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <div className={`r75-empty ${className}`.trim()}>
      <NiIcon name={icon} />
      <h3>{title}</h3>
      {children ? <p>{children}</p> : null}
      {actions ? <div>{actions}</div> : null}
    </div>
  );
}
