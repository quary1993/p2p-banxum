// IP of Webby-Soft SRL.
/*
 * The U33 design's country flags (svg.r35-flag, 19x14): Switzerland's cross and the stripe flags of
 * the design's countries, a neutral grey box for any other country. Shared by the investor area
 * (opportunity cards, design: r35-location) and the public site (site/u33/ui.tsx Flag).
 * label: the country name for an image with a name; null for a decorative flag (hidden from screen
 * readers, next to a country name).
 */
type Stripe = [fill: string, x: number, y: number, width: number, height: number];

/** Flag shapes in the design's 19x14 box: [fill, x, y, width, height]. */
const FLAG_STRIPES: Record<string, Stripe[]> = {
  RO: [
    ["#003f91", 0, 0, 6.34, 14],
    ["#f6d63e", 6.33, 0, 6.34, 14],
    ["#cc2734", 12.66, 0, 6.34, 14]
  ],
  IT: [
    ["#159366", 0, 0, 6.34, 14],
    ["white", 6.33, 0, 6.34, 14],
    ["#cd3442", 12.66, 0, 6.34, 14]
  ],
  FR: [
    ["#0055a4", 0, 0, 6.34, 14],
    ["white", 6.33, 0, 6.34, 14],
    ["#ef4135", 12.66, 0, 6.34, 14]
  ],
  BE: [
    ["#1d1d1b", 0, 0, 6.34, 14],
    ["#fdda24", 6.33, 0, 6.34, 14],
    ["#ef3340", 12.66, 0, 6.34, 14]
  ],
  DE: [
    ["#1d1d1b", 0, 0, 19, 4.67],
    ["#dd0000", 0, 4.66, 19, 4.68],
    ["#ffce00", 0, 9.33, 19, 4.67]
  ],
  AT: [
    ["#c8102e", 0, 0, 19, 4.67],
    ["white", 0, 4.66, 19, 4.68],
    ["#c8102e", 0, 9.33, 19, 4.67]
  ],
  NL: [
    ["#ae1c28", 0, 0, 19, 4.67],
    ["white", 0, 4.66, 19, 4.68],
    ["#21468b", 0, 9.33, 19, 4.67]
  ],
  LU: [
    ["#ea141d", 0, 0, 19, 4.67],
    ["white", 0, 4.66, 19, 4.68],
    ["#51adda", 0, 9.33, 19, 4.67]
  ],
  LI: [
    ["#002b7f", 0, 0, 19, 7],
    ["#ce1126", 0, 7, 19, 7]
  ],
  ES: [
    ["#aa151b", 0, 0, 19, 3.5],
    ["#f1bf00", 0, 3.5, 19, 7],
    ["#aa151b", 0, 10.5, 19, 3.5]
  ],
  PT: [
    ["#046a38", 0, 0, 7.6, 14],
    ["#da291c", 7.6, 0, 11.4, 14]
  ]
};

export function CountryFlag({ code, label = null, className = "r35-flag" }: { code: string; label?: string | null; className?: string }) {
  const iso = (code || "").trim().toUpperCase();
  const a11y = label ? { role: "img", "aria-label": label } : { "aria-hidden": true as const };
  return (
    <svg className={className} focusable="false" viewBox="0 0 19 14" {...a11y}>
      {label ? <title>{label}</title> : null}
      {iso === "CH" ? (
        <>
          <rect fill="#dc272f" height="14" width="19" />
          <path d="M8 3h3v2.5h2.5v3H11V11H8V8.5H5.5v-3H8Z" fill="white" />
        </>
      ) : FLAG_STRIPES[iso] ? (
        FLAG_STRIPES[iso].map(([fill, x, y, width, height]) => <rect fill={fill} height={height} key={`${x}-${y}`} width={width} x={x} y={y} />)
      ) : (
        <rect fill="#d7dce0" height="14" width="19" />
      )}
    </svg>
  );
}
