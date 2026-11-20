import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";

import { getBanxumApiMock } from "../generated/banxumApi";

// Anonymous endpoints of the public site (site/data.ts): calm empty answers by default, so live
// tests that pass through a site page need no handlers of their own. Tests override them with
// server.use(...). First in the list wins over the generated mocks.
const publicSiteHandlers = [
  http.get("*/api/v1/marketplace/primary/public/projects/", () => HttpResponse.json([])),
  http.get("*/api/v1/marketplace/primary/public/statistics/", () =>
    HttpResponse.json({
      as_of: "2026-09-23T06:00:00Z",
      loans_funded: 0,
      loans_repaid: 0,
      loans_late: 0,
      loans_defaulted: 0,
      average_interest_rate_bps: null,
      originators_count: 0,
      countries_count: 0,
      by_currency: []
    })
  ),
  http.get("*/api/v1/marketplace/primary/public/originators/", () => HttpResponse.json([])),
  // Investor app feature switches (anonymous-safe): the production default, FX off.
  http.get("*/api/v1/investor/portal/features/", () => HttpResponse.json({ fx_enabled: false })),
  // 18.10: no compliance block by default. Audit S7-7: an unknown reason now blocks, so the
  // generated random value must not reach the investment screens.
  http.get("*/api/v1/kyc/declarations/", () =>
    HttpResponse.json({
      declaration: null,
      review_open: false,
      review_status: null,
      review_message: "",
      reverification_due_date: null,
      declaration_subject: "person",
      investment_block: null,
      investment_block_message: ""
    })
  )
];

export const server = setupServer(...publicSiteHandlers, ...getBanxumApiMock());
