// IP of Webby-Soft SRL.
// Listing price rules of the Sell investment dialog (U33-DEC-06/07): the price of the principal is 0-102%
// of the outstanding principal (a premium of at most 2%), in whole basis points; the seller fee is
// min(2% x price, 2% x outstanding principal), with no minimum and no fee on accrued interest.

/** Par: 100% of the outstanding principal (backend PAR_PRICE_BPS). */
export const PAR_PRICE_BPS = 10_000;
/** The highest listing price: a 2% premium (backend MAX_PRICE_BPS). */
export const MAX_PRICE_BPS = 10_200;
/** A principal price of zero is allowed; the buyer still pays the accrued interest. */
export const MIN_PRICE_BPS = 0;
/** The slider moves in 0.5-point steps; a typed amount can be any whole basis point. */
export const SLIDER_STEP_BPS = 50;
/** Preview mode only (no server quote): the default seller fee rate of 2%. */
export const PREVIEW_FEE_BPS = 200;

/** The price of the principal in minor units, rounded like the backend (half up). */
export function priceMinorForBps(principalMinor: number, priceBps: number) {
  return Math.round((principalMinor * priceBps) / 10_000);
}

/** Price in whole basis points for a typed amount (the backend prices listings in basis points). */
export function priceBpsForAmount(amountMinor: number, principalMinor: number) {
  if (principalMinor <= 0) return MIN_PRICE_BPS;
  return Math.min(MAX_PRICE_BPS, Math.max(MIN_PRICE_BPS, Math.round((amountMinor * 10_000) / principalMinor)));
}

/** Preview mode only: the capped seller fee, min(rate x price, rate x outstanding principal). */
export function previewSellerFee(transferMinor: number, principalMinor: number, feeBps = PREVIEW_FEE_BPS) {
  return Math.min(Math.round((transferMinor * feeBps) / 10_000), Math.round((principalMinor * feeBps) / 10_000));
}

export function discountTone(priceBps: number): "none" | "caution" | "high" {
  const discountBps = PAR_PRICE_BPS - priceBps;
  if (discountBps >= 2_000) return "high";
  if (discountBps > 1_000) return "caution";
  return "none";
}
