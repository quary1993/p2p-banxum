// IP of Webby-Soft SRL.
// "Help with this step" (design: .v107-help-row > button.v107-help, opening the explanation dialog
// .r34-explanation-modal > .r34-help-body with the project line and question/answer pairs). For the
// financial flows (amount, review, withdraw, sell): the caller passes the step's questions with
// today's values (minimum, balance, available amount from the API). Not wired to a flow yet; the flow
// slices use it from here (docs/claude-design/TODO.md, Phase 17.1 S5).
import { useState, type ReactNode } from "react";

import { useT } from "../../../../i18n";
import { Dialog, NiIcon, PortalLink } from "../../../components";

export type StepHelpItem = { question: ReactNode; answer: ReactNode };

export function HelpWithThisStep({
  title,
  context,
  items,
  label,
  leading
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
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
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
          <dl className="r34-help-topics">
            {items.map((item, index) => (
              <div key={index}>
                <dt>{item.question}</dt>
                <dd>{item.answer}</dd>
              </div>
            ))}
          </dl>
          <p className="r34-general-help">
            <PortalLink onNavigate={() => setOpen(false)} to="faq">{t("More answers in Help")}</PortalLink>
          </p>
        </Dialog>
      ) : null}
    </div>
  );
}
