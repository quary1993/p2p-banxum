// IP of Webby-Soft SRL.
// Copy button of the Add funds bank data (design: button.p73-copy with the copy glyph). The label
// says what is copied ("Copy IBAN") and turns into "Copied" for a moment.
import { useEffect, useState } from "react";

import { useT } from "../../../../i18n";
import { NiIcon } from "../../../components";

function copyWithTextarea(text: string) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

function copyText(text: string): Promise<void> {
  const write = navigator.clipboard?.writeText?.bind(navigator.clipboard);
  if (!write) {
    copyWithTextarea(text);
    return Promise.resolve();
  }
  return write(text).catch(() => copyWithTextarea(text));
}

export function CopyButton({ value, label }: { value: string; label: string }) {
  const t = useT();
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return undefined;
    const timer = window.setTimeout(() => setCopied(false), 1400);
    return () => window.clearTimeout(timer);
  }, [copied]);
  const name = copied ? t("Copied") : t("Copy {label}", { label });
  return (
    <button
      aria-label={name}
      className="p73-copy"
      onClick={() => void copyText(value).then(() => setCopied(true))}
      title={name}
      type="button"
    >
      <NiIcon name={copied ? "check" : "copy"} />
    </button>
  );
}
