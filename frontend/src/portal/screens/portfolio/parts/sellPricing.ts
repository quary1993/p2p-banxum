// IP of Webby-Soft SRL.
// Listing price rules of the Sell investment dialog (today's platform rules, MKT-DEC-007; U33-DEC-06 in Phase 17.2).

/** Today's highest listing price: par, 100% of the outstanding principal (backend PAR_PRICE_BPS). */
export const MAX_PRICE_BPS = 10_000;
/** The slider moves in 0.5-point steps; a typed amount can be any whole basis point from 0.01%. */
export const SLIDER_STEP_BPS = 50;
export const MIN_PRICE_BPS = 1;
/** Preview mode only (no server quote): the default seller fee of 2% of the price. */
export const PREVIEW_FEE_BPS = 200;

/** Price in whole basis points for a typed amount (the backend prices listings in basis points). */
export function priceBpsForAmount(amountMinor: number, principalMinor: number) {
  if (principalMinor <= 0) return MIN_PRICE_BPS;
  return Math.max(MIN_PRICE_BPS, Math.round((amountMinor * 10_000) / principalMinor));
}

export function discountTone(priceBps: number): "none" | "caution" | "high" {
  const discountBps = MAX_PRICE_BPS - priceBps;
  if (discountBps >= 2_000) return "high";
  if (discountBps > 1_000) return "caution";
  return "none";
}

