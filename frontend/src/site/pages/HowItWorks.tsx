// IP of Webby-Soft SRL.
/*
 * The marketplace diagram of the retired How it works page (October design: pages_more.js
 * diagram, diagramWide, diagramTall, icon, arrows, node, legend), shown in Help under How it works
 * (Q24), and the redirect of the retired /how-it-works address. The SVG keeps the October
 * coordinates, icons, colours and texts; the logo in the disc is the white lockup file. The wide
 * diagram shows on desktop and tablet, the tall one on phones (u33/public-overrides.css).
 */
import { Fragment, useEffect, type ReactNode } from "react";

import { useSiteNav } from "../context";

// ---------------------------------------------------------------------------------------------
// Marketplace diagram: the marketplace as an Ink disc with the white logo, Ink lines for the
// investments, Success green for the repayments and the three advantages.

const INK = "#0a0a0a";
const STEEL = "#6e6e6e";
const GREEN = "#1e7a46";
const ON_INK = "#8a8a8a";
// White lockup (with ®) on the Ink marketplace.
const LOGO = "/brand/banxum-logo-white.svg";

const DESCRIPTION =
  "Investors fund loans through the Banxum marketplace: business loans granted by Garanta, and real estate loans, equipment leasing, invoice financing and SME loans from loan originators. The companies repay with interest, back to the investors. 0% fees, CHF and EUR, daily interest.";

type IconName =
  | "investor"
  | "company"
  | "business"
  | "estate"
  | "equipment"
  | "invoice"
  | "lender"
  | "fees"
  | "currencies"
  | "daily";

// Line icons on a 48 x 48 grid, drawn for the diagram.
const ICONS: Record<IconName, ReactNode> = {
  investor: (
    <>
      <circle cx="24" cy="17" r="7" />
      <path d="M10 40c0-8 6.3-13 14-13s14 5 14 13" />
    </>
  ),
  company: <path d="M12 40V10h24v30M8 40h32M18 16h4M26 16h4M18 23h4M26 23h4M18 30h4M26 30h4" />,
  business: (
    <>
      <rect height="22" width="32" x="8" y="16" />
      <path d="M18 16v-5h12v5M8 26h32" />
    </>
  ),
  estate: <path d="M7 22 24 9l17 13M12 19v19h24V19M21 38v-9h6v9" />,
  equipment: (
    <>
      <circle cx="24" cy="24" r="7" />
      <path d="M24 10v5M24 33v5M10 24h5M33 24h5M14.1 14.1l3.5 3.5M30.4 30.4l3.5 3.5M14.1 33.9l3.5-3.5M30.4 17.6l3.5-3.5" />
    </>
  ),
  invoice: <path d="M14 8h14l8 8v24H14zM28 8v8h8M19 22h12M19 28h12M19 34h8" />,
  lender: <path d="M8 18 24 9l16 9M9 19h30M13 21v13M20 21v13M28 21v13M35 21v13M8 38h32" />,
  fees: (
    <>
      <circle cx="18" cy="17" r="4" />
      <circle cx="30" cy="31" r="4" />
      <path d="M32 14 16 34" />
    </>
  ),
  currencies: (
    <>
      <circle cx="19" cy="24" r="10" />
      <circle cx="29" cy="24" r="10" />
    </>
  ),
  daily: (
    <>
      <rect height="27" width="30" x="9" y="12" />
      <path d="M9 20h30M17 8v8M31 8v8M20 29l3 3 6-6" />
    </>
  )
};

function DiagramIcon({ name, x, y, size, color }: { name: IconName; x: number; y: number; size: number; color?: string }) {
  const k = size / 48;
  return (
    <g
      fill="none"
      stroke={color || INK}
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={(1.6 / k).toFixed(2)}
      transform={`translate(${x} ${y}) scale(${k})`}
    >
      {ICONS[name]}
    </g>
  );
}

// A pair of arrows: investment towards the companies (Ink), repayments back (green).
function Arrows({ x1, y1, x2, y2, gap }: { x1: number; y1: number; x2: number; y2: number; gap: number }) {
  const vertical = x1 === x2;
  const dx = vertical ? gap / 2 : 0;
  const dy = vertical ? 0 : gap / 2;
  return (
    <>
      <line markerEnd="url(#bx-dg-ink)" stroke={INK} strokeWidth="1.5" x1={x1 - dx} x2={x2 - dx} y1={y1 - dy} y2={y2 - dy} />
      <line markerEnd="url(#bx-dg-green)" stroke={GREEN} strokeWidth="1.5" x1={x2 + dx} x2={x1 + dx} y1={y2 + dy} y2={y1 + dy} />
    </>
  );
}

function Node({ kind, x, y, r, label, labelSize }: { kind: IconName; x: number; y: number; r: number; label: string; labelSize: number }) {
  return (
    <>
      <circle cx={x} cy={y} fill="#fff" r={r} stroke={INK} strokeWidth="1.5" />
      <DiagramIcon name={kind} size={r * 1.1} x={x - r * 0.55} y={y - r * 0.55} />
      {label ? (
        <text fill={INK} fontSize={labelSize} fontWeight="600" textAnchor="middle" x={x} y={y + r + labelSize + 10}>
          {label}
        </text>
      ) : null}
    </>
  );
}

const LOANS: [IconName, string, string][] = [
  ["business", "Business loans", "New loans by Garanta"],
  ["estate", "Real estate loans", "Secured by a mortgage"],
  ["equipment", "Equipment leasing", "Leasing companies"],
  ["invoice", "Invoice financing", "Factoring companies"],
  ["lender", "SME loans", "Non-bank lenders"]
];

const ADVANTAGES: [IconName, string][] = [
  ["fees", "0% fees"],
  ["currencies", "CHF and EUR"],
  ["daily", "Daily interest"]
];

function Legend({ x, y, size }: { x: number; y: number; size: number }) {
  return (
    <g fill={STEEL} fontSize={size}>
      <line markerEnd="url(#bx-dg-ink)" stroke={INK} strokeWidth="1.5" x1={x} x2={x + 36} y1={y - size / 3} y2={y - size / 3} />
      <text x={x + 46} y={y}>
        Investments and loans
      </text>
      <line
        markerEnd="url(#bx-dg-green)"
        stroke={GREEN}
        strokeWidth="1.5"
        x1={x}
        x2={x + 36}
        y1={y + size * 1.3}
        y2={y + size * 1.3}
      />
      <text x={x + 46} y={y + size * 1.3 + size / 3}>
        Repayments with interest
      </text>
    </g>
  );
}

function DiagramWide() {
  const cx = 500;
  const cy = 300;
  const r = 250;
  const pt = (deg: number, rad: number) =>
    [cx + rad * Math.cos((deg * Math.PI) / 180), cy + rad * Math.sin((deg * Math.PI) / 180)].map((v) => v.toFixed(1));
  const [t1x, t1y] = pt(242, 264);
  const [t2x, t2y] = pt(298, 264);
  const [b1x, b1y] = pt(121, 282);
  const [b2x, b2y] = pt(59, 282);
  // Where the disc is at a given height.
  const half = (y: number) => Math.sqrt(r * r - (y - cy) * (y - cy));
  const rows = [160, 300, 440];
  const cols: [number, [IconName, string, string][]][] = [
    [318, LOANS.slice(0, 3)],
    [516, LOANS.slice(3)]
  ];
  return (
    <svg aria-labelledby="dg-wide-t dg-wide-d" className="site-diagram-wide" role="img" viewBox="0 0 1000 690">
      <title id="dg-wide-t">How Banxum works</title>
      <desc id="dg-wide-d">{DESCRIPTION}</desc>
      <defs>
        <path d={`M${t1x} ${t1y} A264 264 0 0 1 ${t2x} ${t2y}`} id="dg-arc-top" />
        <path d={`M${b1x} ${b1y} A282 282 0 0 0 ${b2x} ${b2y}`} id="dg-arc-bottom" />
      </defs>
      <Legend size={14} x={0} y={18} />
      <circle cx={cx} cy={cy} fill={INK} r={r} />
      <text fill={INK} fontSize="13" fontWeight="600" letterSpacing="3">
        <textPath href="#dg-arc-top" startOffset="50%" textAnchor="middle">
          LOAN ORIGINATORS
        </textPath>
      </text>
      <text fill={INK} fontSize="13" fontWeight="600" letterSpacing="3">
        <textPath href="#dg-arc-bottom" startOffset="50%" textAnchor="middle">
          NEW LOANS BY GARANTA
        </textPath>
      </text>
      <image height="54" href={LOGO} width="300" x="350" y="122" />
      <text fill={ON_INK} fontSize="18" textAnchor="middle" x={cx} y="214">
        Marketplace
      </text>
      <line stroke="#333" strokeWidth="1" x1="330" x2="670" y1="240" y2="240" />
      {cols.map(([x, items]) =>
        items.map(([k, label, sub], i) => {
          const y = 286 + i * 62;
          return (
            <Fragment key={label}>
              <DiagramIcon color="#fff" name={k} size={32} x={x} y={y - 18} />
              <text fill="#fff" fontSize="17" fontWeight="600" x={x + 44} y={y - 1}>
                {label}
              </text>
              <text fill={ON_INK} fontSize="14" x={x + 44} y={y + 17}>
                {sub}
              </text>
            </Fragment>
          );
        })
      )}
      {rows.map((y) => (
        <Fragment key={`investors-${y}`}>
          <Node kind="investor" label="Investors" labelSize={17} r={30} x={70} y={y} />
          <Arrows gap={10} x1={112} x2={Math.round(cx - half(y)) - 14} y1={y} y2={y} />
        </Fragment>
      ))}
      {rows.map((y) => (
        <Fragment key={`companies-${y}`}>
          <Arrows gap={10} x1={Math.round(cx + half(y)) + 14} x2={888} y1={y} y2={y} />
          <Node kind="company" label="Companies" labelSize={17} r={30} x={930} y={y} />
        </Fragment>
      ))}
      {ADVANTAGES.map(([k, label], i) => {
        const x = 320 + i * 180;
        return (
          <Fragment key={label}>
            <circle cx={x} cy="628" fill="#edf5f0" r="21" stroke={GREEN} strokeWidth="1.5" />
            <DiagramIcon color={GREEN} name={k} size={24} x={x - 12} y={616} />
            <text fill={INK} fontSize="17" fontWeight="600" textAnchor="middle" x={x} y="676">
              {label}
            </text>
          </Fragment>
        );
      })}
    </svg>
  );
}

function TallRow({ y, label }: { y: number; label: "Investors" | "Companies" }) {
  return (
    <>
      {[90, 180, 270].map((x) => (
        <Node key={x} kind={label === "Investors" ? "investor" : "company"} label="" labelSize={0} r={28} x={x} y={y} />
      ))}
      <text fill={INK} fontSize="16" fontWeight="600" textAnchor="middle" x="180" y={y + 56}>
        {label}
      </text>
    </>
  );
}

function DiagramTall() {
  return (
    <svg aria-labelledby="dg-tall-t dg-tall-d" className="site-diagram-tall" role="img" viewBox="0 0 360 1010">
      <title id="dg-tall-t">How Banxum works</title>
      <desc id="dg-tall-d">{DESCRIPTION}</desc>
      <Legend size={13} x={8} y={22} />
      <TallRow label="Investors" y={110} />
      <Arrows gap={14} x1={180} x2={180} y1={186} y2={244} />
      <rect fill={INK} height="424" width="344" x="8" y="258" />
      <image height="41" href={LOGO} width="230" x="65" y="290" />
      <text fill={ON_INK} fontSize="15" textAnchor="middle" x="180" y="360">
        Marketplace
      </text>
      <line stroke="#333" strokeWidth="1" x1="28" x2="332" y1="380" y2="380" />
      <text fill={ON_INK} fontSize="10" fontWeight="600" letterSpacing="1.5" x="28" y="406">
        LOAN ORIGINATORS · NEW LOANS BY GARANTA
      </text>
      {LOANS.map(([k, label, sub], i) => {
        const y = 448 + i * 50;
        return (
          <Fragment key={label}>
            <DiagramIcon color="#fff" name={k} size={30} x={28} y={y - 17} />
            <text fill="#fff" fontSize="15" fontWeight="600" x="72" y={y - 1}>
              {label}
            </text>
            <text fill={ON_INK} fontSize="12" x="72" y={y + 15}>
              {sub}
            </text>
          </Fragment>
        );
      })}
      <Arrows gap={14} x1={180} x2={180} y1={696} y2={754} />
      <TallRow label="Companies" y={800} />
      {ADVANTAGES.map(([k, label], i) => {
        const x = 64 + i * 116;
        return (
          <Fragment key={label}>
            <circle cx={x} cy="920" fill="#edf5f0" r="22" stroke={GREEN} strokeWidth="1.5" />
            <DiagramIcon color={GREEN} name={k} size={26} x={x - 13} y={907} />
            <text fill={INK} fontSize="14" fontWeight="600" textAnchor="middle" x={x} y="970">
              {label}
            </text>
          </Fragment>
        );
      })}
    </svg>
  );
}

function Marker({ id, color }: { id: string; color: string }) {
  return (
    <marker
      id={id}
      markerHeight="9"
      markerUnits="userSpaceOnUse"
      markerWidth="9"
      orient="auto"
      refX="9"
      refY="5"
      viewBox="0 0 10 10"
    >
      <path d="M0 0 10 5 0 10z" fill={color} />
    </marker>
  );
}

export function MarketplaceDiagram() {
  return (
    <figure className="site-diagram">
      <svg aria-hidden="true" className="site-diagram-defs" focusable="false">
        <defs>
          <Marker color={INK} id="bx-dg-ink" />
          <Marker color={GREEN} id="bx-dg-green" />
        </defs>
      </svg>
      <DiagramWide />
      <DiagramTall />
    </figure>
  );
}

/** The retired /how-it-works address: Help, at its How it works part. */
export function HowItWorksMoved() {
  const { navigate } = useSiteNav();
  useEffect(() => {
    navigate("/help#how-it-works", { replace: true });
  }, [navigate]);
  return null;
}
