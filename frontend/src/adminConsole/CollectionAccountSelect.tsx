import { useEffect } from "react";
import { Field } from "../investorPortal/ui";
import { useCollectionAccountsData } from "./data";

/**
 * The receiving/paying collection account, chosen from the configured accounts of the
 * currency (one per currency at launch), with the currency's account selected by default.
 * Free text is only offered when no account is configured for the currency.
 */
export function CollectionAccountSelect({
  currency,
  value,
  onChange,
  label = "Collection account"
}: {
  currency: string;
  value: string;
  onChange: (value: string) => void;
  label?: string;
}) {
  const accountsQuery = useCollectionAccountsData();
  const code = currency.trim().toUpperCase();
  const accounts = (accountsQuery.data ?? []).filter(
    (account) => account.currency === code && account.collection_account_identifier
  );
  const defaultAccount = accounts[0]?.collection_account_identifier ?? "";
  const valueIsConfigured = accounts.some((account) => account.collection_account_identifier === value);

  useEffect(() => {
    if (defaultAccount && !valueIsConfigured) onChange(defaultAccount);
  }, [defaultAccount, valueIsConfigured, onChange]);

  if (!accounts.length) {
    return (
      <Field
        hint={
          accountsQuery.isLoading
            ? "Loading the configured collection accounts..."
            : `No ${code || "currency"} collection account is configured. Type the account.`
        }
        label={label}
      >
        <input aria-label={label} onChange={(event) => onChange(event.target.value)} required value={value} />
      </Field>
    );
  }
  const selected = accounts.find((account) => account.collection_account_identifier === value) ?? accounts[0];
  return (
    <Field hint={[selected.bank_name, selected.iban].filter(Boolean).join(" · ")} label={label}>
      <select aria-label={label} onChange={(event) => onChange(event.target.value)} required value={valueIsConfigured ? value : defaultAccount}>
        {accounts.map((account) => (
          <option key={account.collection_account_identifier} value={account.collection_account_identifier}>
            {account.collection_account_identifier} ({account.currency})
          </option>
        ))}
      </select>
    </Field>
  );
}
