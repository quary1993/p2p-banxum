// IP of Webby-Soft SRL.
// 18.3: the Transactions page from GET /investor/portal/transactions/ (server filters, pages of
// movements with the available balance after each one, the summary of the movements in view) and
// the CSV of the whole filtered history from GET /investor/portal/transactions/export/. The review
// build computes the same page from the fixture activity (without the available balance).
import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";

import {
  getV1InvestorPortalTransactionsRetrieveQueryKey,
  v1InvestorPortalTransactionsExportRetrieve,
  v1InvestorPortalTransactionsRetrieve,
  type TransactionPage,
  type V1InvestorPortalTransactionsRetrieveParams
} from "../../../api/generated/banxumApi";
import { isFixturePreview } from "../../../investorPortal/data";
import { activityFixture } from "../../../investorPortal/fixtures";
import { previewTransactionPage, type TransactionQuery } from "./transactionsModel";

function queryParams(query: TransactionQuery): V1InvestorPortalTransactionsRetrieveParams {
  const params: V1InvestorPortalTransactionsRetrieveParams = {};
  if (query.currency) params.currency = query.currency;
  if (query.group) params.group = query.group;
  if (query.date_from) params.date_from = query.date_from;
  if (query.date_to) params.date_to = query.date_to;
  if (query.q.trim()) params.q = query.q.trim();
  return params;
}

/** Pages of movements that match the filters, newest first; the next page is fetched on demand. */
export function useTransactionsData(query: TransactionQuery, pageSize: number) {
  const params = queryParams(query);
  return useInfiniteQuery({
    queryKey: [...getV1InvestorPortalTransactionsRetrieveQueryKey(params), "pages", pageSize],
    queryFn: ({ pageParam, signal }): Promise<TransactionPage> =>
      isFixturePreview
        ? Promise.resolve(previewTransactionPage(activityFixture.entries, query, pageParam, pageSize))
        : v1InvestorPortalTransactionsRetrieve({ ...params, offset: pageParam, limit: pageSize }, { signal }),
    initialPageParam: 0,
    getNextPageParam: (last: TransactionPage) => last.next_offset ?? undefined,
    // Keep the rows of the last filters on screen while the new ones load.
    placeholderData: keepPreviousData,
    retry: false,
    staleTime: 0
  });
}

/** The server's CSV of every movement that matches the filters, in the investor's number format. */
export function fetchTransactionsCsv(query: TransactionQuery): Promise<string> {
  return v1InvestorPortalTransactionsExportRetrieve(queryParams(query));
}
