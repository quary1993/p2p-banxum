// IP of Webby-Soft SRL.
// Production stand-in for siteFixtures.ts (aliased in vite.config.ts): no design sample data
// reaches the production bundle. Keep the exports in sync with siteFixtures.ts.
import type { PublicOriginator, PublicProject, PublicStatistics } from "./data";

export const siteFixtureToday = "";

export const siteDesignProjectIds: Record<string, string> = {};

export const siteProjectsFixture: PublicProject[] = [];

export const siteStatisticsFixture: PublicStatistics = {
  as_of: "",
  loans_funded: 0,
  loans_repaid: 0,
  loans_late: 0,
  loans_defaulted: 0,
  average_interest_rate_bps: null,
  originators_count: 0,
  countries_count: 0,
  by_currency: []
};

export const siteOriginatorsFixture: PublicOriginator[] = [];
