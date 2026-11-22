// IP of Webby-Soft SRL.
// Short confirmation at the bottom right (design: #bxm-toasts.bxm-toasts > .bxm-toast), e.g.
// "Report ready" after Create report. Announced politely; disappears after a few seconds.
import { useEffect } from "react";
import { createPortal } from "react-dom";

import { NiIcon } from "../../../components";

export function Toast({ icon, message, onDone, timeoutMs = 4500 }: { icon: string; message: string; onDone: () => void; timeoutMs?: number }) {
  useEffect(() => {
    const timer = window.setTimeout(onDone, timeoutMs);
    return () => window.clearTimeout(timer);
  }, [onDone, timeoutMs, message]);
  return createPortal(
    <div aria-live="polite" className="bxm-toasts" role="status">
      <div className="bxm-toast"><NiIcon name={icon} /><span>{message}</span></div>
    </div>,
    document.body
  );
}
