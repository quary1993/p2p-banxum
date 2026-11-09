// IP of Webby-Soft SRL.
// IBAN display as the design writes it: groups of four ("CH93 0076 2011 6238 5295 7") or masked
// ("CH93 •••• 5295 7" -> first four and last four characters).

export function groupIban(value: string) {
  return value.replace(/\s+/g, "").replace(/(.{4})/g, "$1 ").trim();
}

export function maskIban(value: string) {
  const compact = value.replace(/\s+/g, "");
  if (compact.length <= 8) return groupIban(compact);
  return `${compact.slice(0, 4)} •••• ${compact.slice(-4)}`;
}
