// IP of Webby-Soft SRL.
// EUR/CHF segmented control (design: .bxm-seg[role=group] with aria-pressed buttons). CHF and EUR
// stay separate: switching changes the view only, never converts (U33-DEC-33).
import { useT } from "../../i18n";

export function CurrencySwitch<C extends string>({
  value,
  options,
  onChange,
  label,
  className = ""
}: {
  value: C;
  options: readonly C[];
  onChange: (currency: C) => void;
  /** Accessible group name; "Currency" by default. */
  label?: string;
  className?: string;
}) {
  const t = useT();
  return (
    <div aria-label={label ?? t("Currency")} className={`bxm-seg ${className}`.trim()} role="group">
      {options.map((option) => (
        <button
          aria-pressed={option === value}
          className={option === value ? "active" : ""}
          key={option}
          onClick={() => onChange(option)}
          type="button"
        >
          {option}
        </button>
      ))}
    </div>
  );
}
