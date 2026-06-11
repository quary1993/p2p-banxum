const currencyMinorUnitDecimals: Record<string, number> = {
  BHD: 3,
  CHF: 2,
  EUR: 2,
  GBP: 2,
  JPY: 0,
  KWD: 3,
  USD: 2
};

export function minorUnitDecimalsForCurrency(currency: string | null | undefined) {
  if (!currency) return 2;
  return currencyMinorUnitDecimals[currency.toUpperCase()] ?? 2;
}

export function formatMoneyMinor(
  amountMinor: number | null | undefined,
  currencyOrDecimals: string | number = 2,
  displayDecimals?: number
) {
  if (amountMinor === null || amountMinor === undefined || Number.isNaN(amountMinor)) {
    return "-";
  }
  const minorUnitDecimals =
    typeof currencyOrDecimals === "string" ? minorUnitDecimalsForCurrency(currencyOrDecimals) : 2;
  const decimals =
    typeof currencyOrDecimals === "number"
      ? currencyOrDecimals
      : (displayDecimals ?? minorUnitDecimals);

  return (amountMinor / 10 ** minorUnitDecimals)
    .toLocaleString("en-CH", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    })
    .replace(/,/g, "\u2009");
}

export function formatRateBps(bps: number) {
  return `${(bps / 100).toFixed(1)}%`;
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "Europe/Zurich"
  });
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return "-";
  return new Date(value).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Zurich"
  });
}

export function safeMetadataCategory(metadata: unknown) {
  if (metadata && typeof metadata === "object" && "category" in metadata) {
    const value = (metadata as { category?: unknown }).category;
    return typeof value === "string" ? value : "principal";
  }
  return "principal";
}

export function parseMoneyInputToMinorUnits(input: string, currency: string) {
  const normalized = input.trim().replace(",", ".");
  const minorUnitDecimals = minorUnitDecimalsForCurrency(currency);

  if (normalized === "") {
    return { amountMinor: 0, error: undefined };
  }

  if (!/^\d+(?:\.\d*)?$/.test(normalized) && !/^\.\d+$/.test(normalized)) {
    return { amountMinor: 0, error: "Enter a valid amount." };
  }

  const [rawInteger, rawFraction = ""] = normalized.split(".");
  if (rawFraction.length > minorUnitDecimals) {
    return {
      amountMinor: 0,
      error:
        minorUnitDecimals === 0
          ? `${currency} amounts must be whole units.`
          : `${currency} amounts support at most ${minorUnitDecimals} decimal places.`
    };
  }

  const integerPart = rawInteger === "" ? "0" : rawInteger;
  const fractionPart = rawFraction.padEnd(minorUnitDecimals, "0");
  const minorString = `${integerPart}${fractionPart}`.replace(/^0+(?=\d)/, "") || "0";
  const amountMinor = Number(minorString);

  if (!Number.isSafeInteger(amountMinor)) {
    return { amountMinor: 0, error: "Amount is too large." };
  }

  return { amountMinor, error: undefined };
}
