// IP of Webby-Soft SRL.
// The line under the amount on the invest page of a Swiss-borrower loan (MKT-DEC-028).
import { swissInvestorLimitMessage, swissLoanFullForViewer, type InvestorLimitFields } from "./investorLimit";
import { Banner } from "./ui";

/** "Swiss borrower: at most 20 investors. N places left." Nothing for other loans. */
export function SwissInvestorLimitNote({ loan }: { loan: InvestorLimitFields }) {
  const maxInvestors = loan.max_investors;
  if (typeof maxInvestors !== "number") return null;
  if (swissLoanFullForViewer(loan)) {
    return (
      <Banner tone="bad" title="No place left for a new investor">
        {swissInvestorLimitMessage(maxInvestors)} Choose another loan on the primary market.
      </Banner>
    );
  }
  const placesLeft = loan.places_left ?? 0;
  const places =
    placesLeft === 0
      ? "No places left for new investors. You already invest in this loan, so you can add to it."
      : `${placesLeft} ${placesLeft === 1 ? "place" : "places"} left.`;
  return (
    <p className="iv-note">
      Swiss borrower: at most {maxInvestors} investors. {places}
    </p>
  );
}
