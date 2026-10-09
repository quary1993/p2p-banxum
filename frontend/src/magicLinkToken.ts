//IP of Webby-Soft SRL.
// Login-link token handling (audit 2026-10-09, A-49).
//
// Login emails put the token in the URL fragment (/login#token=...), which browsers
// never send to a server. Older emails used /login?token=..., which stays valid for its
// 15 minutes. Either way the token is taken out of the address bar before the app makes
// any request, so it cannot leak into access logs or a Referer header.

let pendingToken: string | null = null;

function isLoginPath(pathname: string) {
  return pathname === "/login" || pathname === "/login/";
}

/** Move a login token from the URL into memory. Safe to call more than once. */
export function captureMagicLinkTokenFromLocation(): void {
  if (typeof window === "undefined" || !isLoginPath(window.location.pathname)) return;
  const url = new URL(window.location.href);
  const hashParams = new URLSearchParams(url.hash.replace(/^#/, ""));
  const fromHash = hashParams.get("token");
  const fromQuery = url.searchParams.get("token");
  const token = fromHash || fromQuery;
  if (!token) return;
  hashParams.delete("token");
  url.searchParams.delete("token");
  const remainingHash = hashParams.toString();
  window.history.replaceState(
    window.history.state,
    "",
    `${url.pathname}${url.search}${remainingHash ? `#${remainingHash}` : ""}`
  );
  pendingToken = token;
}

/** The captured token, once. Later calls return null. */
export function takePendingMagicLinkToken(): string | null {
  captureMagicLinkTokenFromLocation();
  const token = pendingToken;
  pendingToken = null;
  return token;
}

export function hasPendingMagicLinkToken(): boolean {
  captureMagicLinkTokenFromLocation();
  return pendingToken !== null;
}
