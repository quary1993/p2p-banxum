// IP of Webby-Soft SRL.
// Reports (design #/reports), interim version: U33 page head over today's account statements and
// annual tax information (passed in by App.tsx as the legacy body). Slice S4 rebuilds the body
// (period, report type, create report) on the platform's reporting service.
import type { ReactNode } from "react";

import { useT } from "../../../i18n";
import { PageHead } from "../../components";
import { LegacyBody } from "../../shell/LegacyBody";

export function ReportsScreen({ children }: { children: ReactNode }) {
  const t = useT();
  return (
    <main className="tr-page tr-reports-page rr-page r31m-reports">
      <PageHead subtitle={t("Statements and reports for your records and your tax return.")} title={t("Reports")} />
      <LegacyBody>{children}</LegacyBody>
    </main>
  );
}
