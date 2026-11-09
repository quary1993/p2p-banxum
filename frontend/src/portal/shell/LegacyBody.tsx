// IP of Webby-Soft SRL.
/*
 * Migration wrapper for a screen body that has not been rebuilt in U33 yet (slices S2-S5).
 * The body keeps the old skin: the old CSS reaches it through html.bxm and the ".app" context it was
 * written for, and the generated U33 rules skip everything inside .bxu-legacy (their
 * :where(:not(.bxu-legacy *)) guard). u33-overrides.css resets the inherited U33 text styles here.
 * A rebuilt screen renders without this wrapper; when the last one is gone, the final slice removes
 * this file, the guard (build tool --no-legacy-guard) and the old skin files.
 */
import type { ReactNode } from "react";

export function LegacyBody({ children }: { children: ReactNode }) {
  return <div className="bxu-legacy app">{children}</div>;
}
