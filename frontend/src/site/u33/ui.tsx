// IP of Webby-Soft SRL.
/*
 * Small blocks of the U33 public site, same markup and classes as the design: the Nioicon
 * glyph span, the 19x14 country flags (class r35-flag), the arrow link and the in-page links
 * to the home sections. Links are real paths opened in the app (SiteLink).
 */
import type { AnchorHTMLAttributes, MouseEvent, ReactNode } from "react";

import { SiteLink } from "../components";
import { useSiteNav } from "../context";
import { isPlainLeftClick } from "../links";
import { t } from "../../i18n";
import { CountryFlag } from "../../portal/components/CountryFlag";
import { countryName } from "../projects";
import { GLYPHS, type GlyphName } from "./glyphs";
import { scrollToSection } from "./hooks";
import { ltvText } from "./loans";

export { SiteLink as PublicLink };

/** <span class="ni"> with a Nioicon glyph (decorative). */
export function Ni({ glyph, className, id }: { glyph: GlyphName; className?: string; id?: string }) {
  return (
    <span aria-hidden="true" className={className ? `${className} ni` : "ni"} id={id}>
      {GLYPHS[glyph]}
    </span>
  );
}

/**
 * The design's country flag (svg.r35-flag, 19x14). Decorative flags (next to the country's name
 * or in a choice button) are hidden from screen readers; the others are an image with the name.
 * The drawing is shared with the investor area (portal/components/CountryFlag.tsx).
 */
export function Flag({ code, decorative = false, className = "r35-flag" }: { code: string; decorative?: boolean; className?: string }) {
  const iso = (code || "").trim().toUpperCase();
  return <CountryFlag className={className} code={iso} label={decorative ? null : countryName(iso) || iso} />;
}

type HashLinkProps = Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & {
  /** Section id on the home page ("opportunities", "how-it-works", "security"). */
  section: string;
  children: ReactNode;
};

/**
 * A link to a section of the home page ("/#opportunities"): on the home page it scrolls there
 * and puts the section in the address; elsewhere it opens the home page at that section.
 */
export function HomeSectionLink({ section, onClick, children, ...rest }: HashLinkProps) {
  const { path, navigate } = useSiteNav();
  const href = `/#${section}`;
  return (
    <a
      {...rest}
      href={href}
      onClick={(event: MouseEvent<HTMLAnchorElement>) => {
        onClick?.(event);
        if (event.defaultPrevented || !isPlainLeftClick(event)) return;
        event.preventDefault();
        if (path === "/") {
          if (window.location.hash !== `#${section}`) window.history.pushState(window.history.state, "", href);
          scrollToSection(section);
        } else {
          navigate(href);
        }
      }}
    >
      {children}
    </a>
  );
}

/** A section link inside the current page ("#request"): scrolls without changing the route. */
export function InPageLink({ section, onClick, children, ...rest }: HashLinkProps) {
  return (
    <a
      {...rest}
      href={`#${section}`}
      onClick={(event) => {
        onClick?.(event);
        if (event.defaultPrevented || !isPlainLeftClick(event)) return;
        event.preventDefault();
        scrollToSection(section);
      }}
    >
      {children}
    </a>
  );
}

/** The mobile edition's loan/asset bars in HTML (mobile-security-ltv). */
export function MobileLtv({
  figure,
  currency,
  loan,
  value,
  id = "mobile-security-ltv"
}: {
  figure: { ltv: number; valueLabel: string };
  currency: string;
  loan: string;
  value: string;
  id?: string;
}) {
  return (
    <div aria-hidden="true" className="mobile-ltv" id={id} style={{ ["--loan-ratio" as string]: `${figure.ltv}%` }}>
      <div className="mobile-ltv-label-row">
        <span className="mobile-ltv-label">{t("Loan amount")}</span>
        <strong className="mobile-ltv-value">
          <small>{currency}</small> <span className="mobile-ltv-loan-amount">{loan}</span>
        </strong>
      </div>
      <div className="mobile-ltv-bars">
        <div className="mobile-ltv-loan" />
        <div className="mobile-ltv-marker">
          <strong className="mobile-ltv-percent">{ltvText(figure.ltv)}</strong>
          <span>{t("Loan-to-value")}</span>
        </div>
        <div className="mobile-ltv-asset">
          <span>100%</span>
        </div>
      </div>
      <div className="mobile-ltv-label-row">
        <span className="mobile-ltv-label mobile-ltv-asset-label">{figure.valueLabel}</span>
        <strong className="mobile-ltv-value">
          <small>{currency}</small> <span className="mobile-ltv-asset-amount">{value}</span>
        </strong>
      </div>
    </div>
  );
}
