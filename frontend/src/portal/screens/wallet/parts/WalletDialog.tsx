// IP of Webby-Soft SRL.
/*
 * Modal shell of the wallet dialogs whose body is not the shared Dialog's ".modal-body > h5.title":
 * the money dialogs (design .p73-modal: ".modal-body > h2") and the Create report dialog (design
 * .tr-report-modal: a form directly in .modal-content). Same behaviour as portal/components Dialog
 * (focus in and trapped, Escape and backdrop close, focus back to the opener, no dismiss while a
 * money action runs: investorPortal/dialog.ts). Candidate for portal/components after the merge.
 */
import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { useT } from "../../../../i18n";
import { useDialog } from "../../../../investorPortal/dialog";
import { NiIcon } from "../../../components";

export function WalletDialog({
  className,
  labelledBy,
  onClose,
  size = "md",
  busy = false,
  children
}: {
  /** The design's modal class (p73-modal, tr-report-modal). */
  className: string;
  /** Id of the heading that names the dialog. */
  labelledBy: string;
  onClose: () => void;
  size?: "sm" | "md" | "lg";
  busy?: boolean;
  children: ReactNode;
}) {
  const t = useT();
  const dialogRef = useRef<HTMLDivElement>(null);
  const { blocked, dismissFromBackdrop } = useDialog({ dialogRef, onDismiss: onClose, busy });
  useEffect(() => {
    document.body.classList.add("modal-open");
    return () => document.body.classList.remove("modal-open");
  }, []);
  const close = () => {
    if (!blocked) onClose();
  };
  return createPortal(
    <>
      <div
        aria-busy={blocked || undefined}
        aria-labelledby={labelledBy}
        aria-modal="true"
        className={`modal fade show ${className}`}
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
              onKeyDown={(event) => {
                if (event.key === " ") {
                  event.preventDefault();
                  close();
                }
              }}
              role="button"
            >
              <NiIcon name="cross-sm" />
            </a>
            {children}
          </div>
        </div>
      </div>
      <div className="modal-backdrop fade show" />
    </>,
    document.body
  );
}
