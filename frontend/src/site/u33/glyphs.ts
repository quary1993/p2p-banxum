// IP of Webby-Soft SRL.
// Nioicon glyphs of the U33 public site (the subset in assets/nioicon-public.woff2, family
// "Bxp Nioicon"). The design writes them as characters inside <span class="ni">.
export const GLYPHS = {
  arrow: "\ue93b",
  building: "\ue97d",
  check: "\ue9be",
  checkCircle: "\ue9b8",
  alert: "\ue90d",
  clock: "\ue9e9",
  cross: "\uea06",
  lock: "\uead5",
  gear: "\ueb75",
  file: "\uea50",
  user: "\uec33",
  shield: "\ueb7c",
  coins: "\ue9f4"
} as const;

export type GlyphName = keyof typeof GLYPHS;
