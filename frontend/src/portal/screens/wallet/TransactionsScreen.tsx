// IP of Webby-Soft SRL.
// Transactions (design #/transactions), interim version: U33 page head over today's activity list
// (passed in by App.tsx as the legacy body). Slice S4 rebuilds the body (period, currency, type,
// search, detail, export) on the API.
import type { ReactNode } from "react";

import { useT } from "../../../i18n";
import { PageHead } from "../../components";
import { LegacyBody } from "../../shell/LegacyBody";

export function TransactionsScreen({ children }: { children: ReactNode }) {
  const t = useT();
  return (
    <main className="tr-page r30-transactions">
      {/* U33-DEC-02: repayments go to the Banxum balance, not directly to the bank account. */}
      <PageHead subtitle={t("Movements on your Banxum account: deposits, investments, repayments and withdrawals.")} title={t("Transactions")} />
      <LegacyBody>{children}</LegacyBody>
    </main>
  );
}
