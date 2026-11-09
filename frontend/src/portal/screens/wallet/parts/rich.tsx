// IP of Webby-Soft SRL.
// Puts React nodes into a translated sentence: rich(t("{amount} returns on {date}."), { amount: <strong/>, ... }).
// The sentence stays one catalog key (i18n rule: no sentences built from fragments).
import { Fragment, type ReactNode } from "react";

export function rich(template: string, nodes: Record<string, ReactNode>): ReactNode {
  const parts = template.split(/\{(\w+)\}/g);
  return parts.map((part, index) => {
    if (index % 2 === 0) return part ? <Fragment key={index}>{part}</Fragment> : null;
    return Object.prototype.hasOwnProperty.call(nodes, part) ? <Fragment key={index}>{nodes[part]}</Fragment> : `{${part}}`;
  });
}
