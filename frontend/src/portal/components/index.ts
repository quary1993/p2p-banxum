// IP of Webby-Soft SRL.
/*
 * Shared U33 building blocks for the investor area (slices S2-S5 use these instead of making their own).
 *
 * Conventions of the U33 investor area (Phase 17.1):
 * - Styles: portal/u33/u33.css is GENERATED from the design (never edit it; run tools/u33-design/investor/build.sh), fixes go to
 *   portal/u33/u33-overrides.css. Both are scoped to html.bxu, which <U33Skin> sets while the investor
 *   area is mounted. Use the design's DOM and class names; do not invent a parallel class system.
 * - Screens: one folder per area, frontend/src/portal/screens/<area>/<Name>Screen.tsx (areas: invest,
 *   portfolio, wallet, account). A screen gets its data from the generated API client hooks
 *   (src/api/generated) or the existing investorPortal/data.ts hooks, and renders U33 markup with these
 *   components. App.tsx only maps routes to screens (InvestorShell's switch); no screen code in App.tsx.
 * - The shell (portal/shell) is shared: sidebar, header, menus, mobile menu. Screens render their own
 *   <main className="..."> with a <PageHead> first.
 * - Every investor screen is U33 (S7 of audit step 4 removed the old skin, <LegacyBody> and html.bxm).
 * - Texts: every user-facing string through t()/useT() (src/i18n), English keys. Amounts, rates and
 *   numbers through investorPortal/format.ts (MoneyAmount here), never toFixed/toLocaleString.
 * - Light/Dark: the design's [data-theme] rules apply automatically; do not branch on the theme in code.
 */
export { Button, ButtonLink, LinkArrow, type ButtonVariant } from "./Button";
export { Card } from "./Card";
export { CurrencySwitch } from "./CurrencySwitch";
export { Dialog, InfoTip } from "./Dialog";
export { PdfReader, type PdfFile } from "./PdfReader";
export { bytesOfArtifact } from "./pdf/bytes";
export { Dropdown } from "./Dropdown";
export { useDismissable } from "./useDismissable";
export { EmptyState } from "./EmptyState";
export { NiIcon } from "./Icon";
export { clickOnSpace } from "./keyboard";
export { KeyValueList, type KeyValueItem } from "./KeyValueList";
export { MoneyAmount } from "./MoneyAmount";
export { PortalLink, PortalNavProvider } from "./navigation";
export { isPlainLeftClick, PORTAL_ADDRESS_EVENT, usePortalNav, type PortalNav } from "./portalNav";
export { PageHead } from "./PageHead";
export { StatusTag, type TagStatus, type TagTone } from "./StatusTag";
export { Tabs, type TabItem } from "./Tabs";
