// IP of Webby-Soft SRL.
// U33 dialog shell (design: Bootstrap .modal.fade.show > .modal-dialog > .modal-content, close "×" top
// right, .modal-backdrop) rendered into <body>. Focus moves in and is trapped, Escape and the
// backdrop close it, focus returns to the opener: investorPortal/dialog.ts (useDialog). While a
// money action runs (`busy`, or a pending mutation) it cannot be dismissed.
import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { useT } from "../../i18n";
import { useDialog } from "../../investorPortal/dialog";
import { NiIcon } from "./Icon";

export function Dialog({
  title,
  onClose,
  children,
  footer,
  size = "md",
  className = "",
  bodyClassName = "",
  busy = false
}: {
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  /** Buttons row under the body (.modal-footer). */
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
  /** The screen's own modal class (design: p73-modal, s106-modal...). */
  className?: string;
  bodyClassName?: string;
  busy?: boolean;
}) {
  const t = useT();
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const { blocked, dismissFromBackdrop } = useDialog({ dialogRef, onDismiss: onClose, busy });
  useEffect(() => {
    document.body.classList.add("modal-open");
    return () => document.body.classList.remove("modal-open");
  }, []);
  const close = () => {
    if (!blocked) onClose();
  };
  const onCloseKey = (event: KeyboardEvent<HTMLAnchorElement>) => {
    if (event.key === " ") {
      event.preventDefault();
      close();
    }
  };
  return createPortal(
    <>
      <div
        aria-busy={blocked || undefined}
        aria-labelledby={titleId}
        aria-modal="true"
        className={`modal fade show ${className}`.trim()}
        onMouseDown={(event) => event.target === event.currentTarget && dismissFromBackdrop()}
        ref={dialogRef}
        role="dialog"
        style={{ display: "block" }}
        tabIndex={-1}
      >
        <div className={`modal-dialog modal-${size} modal-dialog-centered`} role="document">
          <div className="modal-content">
            <a
              aria-disabled={blocked || undefined}
              aria-label={t("Close")}
              className="close"
              href="#"
              onClick={(event) => {
                event.preventDefault();
                close();
              }}
              onKeyDown={onCloseKey}
              role="button"
            >
              <NiIcon name="cross-sm" />
            </a>
            <div className={`modal-body modal-body-${size} ${bodyClassName}`.trim()}>
              <h5 className="title" id={titleId}>{title}</h5>
              {children}
            </div>
            {footer ? <div className="modal-footer">{footer}</div> : null}
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </>,
    document.body
  );
}

/** The "i" explanation button (design: .bxm-vocab-info) opening a short dialog (.bxm-vocab-dialog). */
export function InfoTip({ label, title, children }: { label: string; title: ReactNode; children: ReactNode }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button aria-haspopup="dialog" aria-label={t("About {label}", { label })} className="bxm-vocab-info" onClick={() => setOpen(true)} type="button">
        <NiIcon name="info" />
      </button>
      {open ? (
        <Dialog bodyClassName="bxm-vocab-dialog" onClose={() => setOpen(false)} title={title}>
          <p>{children}</p>
        </Dialog>
      ) : null}
    </>
  );
}
