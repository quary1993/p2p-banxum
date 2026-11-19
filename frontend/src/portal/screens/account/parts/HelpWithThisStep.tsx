// IP of Webby-Soft SRL.
// "Help with this step" (design: .v107-help-row > button.v107-help, opening the explanation dialog
// .r34-explanation-modal > .r34-help-body with the project line and question/answer pairs). For the
// financial flows (amount, review, withdraw, sell, 18.3): the caller passes the step's questions with
// the live values (minimum, balance, available amount, price and fee from the API). Inside a dialog
// (withdraw, sell) it opens in place (`inline`), so no dialog opens over another.
import { useState, type ReactNode } from "react";

import { useT } from "../../../../i18n";
import { Dialog, NiIcon, PortalLink } from "../../../components";

export type StepHelpItem = { question: ReactNode; answer: ReactNode };

export function HelpWithThisStep({
  title,
  context,
  items,
  label,
  leading,
  inline = false
}: {
  /** Dialog heading, e.g. "Choosing your amount". */
  title: ReactNode;
  /** The project or position the step is about (design: .r34-help-project). */
  context?: ReactNode;
  items: StepHelpItem[];
  /** Button text; "Help with this step" by default. */
  label?: string;
  /** Content on the left of the row (design: the "How investing works" link). */
  leading?: ReactNode;
  /** Opens in place under the button (inside a dialog). */
  inline?: boolean;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const topics = (
    <dl className="r34-help-topics">
      {items.map((item, index) => (
        <div key={index}>
          <dt>{item.question}</dt>
          <dd>{item.answer}</dd>
        </div>
      ))}
    </dl>
  );
  if (inline) {
    return (
      <details className="v107-help-row u33-step-help" onToggle={(event) => setOpen(event.currentTarget.open)} open={open}>
        <summary className="v107-help">
          <NiIcon name="help" />
          {label ?? t("Help with this step")}
          <NiIcon name={open ? "chevron-up" : "chevron-down"} />
        </summary>
        <div className="r34-help-body">
          {context ? <p className="r34-help-project">{context}</p> : null}
          <h3 className="h6">{title}</h3>
          {topics}
        </div>
      </details>
    );
  }
  return (
    <div className="v107-help-row">
      {leading}
      <button aria-haspopup="dialog" className="v107-help" onClick={() => setOpen(true)} type="button">
        <NiIcon name="help" />
        {label ?? t("Help with this step")}
        <NiIcon name="arrow-right" />
      </button>
      {open ? (
        <Dialog bodyClassName="r34-help-body" className="r34-explanation-modal" onClose={() => setOpen(false)} size="md" title={title}>
          {context ? <p className="r34-help-project">{context}</p> : null}
          {topics}
          <p className="r34-general-help">
            <PortalLink onNavigate={() => setOpen(false)} to="faq">{t("More answers in Help")}</PortalLink>
          </p>
        </Dialog>
      ) : null}
    </div>
  );
}
