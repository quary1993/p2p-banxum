// IP of Webby-Soft SRL.
// 18.5 (U33-DEC-01): the email code of an operation is requested with its details (amount,
// currency, IBAN, loan, listing, price) and confirms only them. When the details change after the
// code was sent (the investor went back and changed the amount), the old code no longer fits: the
// hooks forget it and ask for a new one.
import { useEffect, useRef } from "react";

import type { OperationDetails } from "../api/generated/banxumApi";

export type { OperationDetails };

/** A stable key of the details ("" when there are none yet). */
export function operationKey(operation: OperationDetails | null | undefined) {
  if (!operation) return "";
  const entries = Object.entries(operation)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .sort(([a], [b]) => a.localeCompare(b));
  return entries.length ? JSON.stringify(entries) : "";
}

/** Calls ``onChange`` when the details change after the first render with details. */
export function useOperationChange(operation: OperationDetails | null | undefined, onChange: () => void) {
  const key = operationKey(operation);
  const previous = useRef(key);
  const callback = useRef(onChange);
  useEffect(() => {
    callback.current = onChange;
  });
  useEffect(() => {
    if (previous.current !== key) {
      previous.current = key;
      callback.current();
    }
  }, [key]);
}

/** The request body of a code request: the action and, for an operation, its details. */
export function codeRequestBody<A extends string>(action: A, operation: OperationDetails | null | undefined) {
  const key = operationKey(operation);
  return key && operation ? { action, operation } : { action };
}
