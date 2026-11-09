// IP of Webby-Soft SRL.
// Per-browser conveniences of the investing screens (dismissed notices, Cards/List view). Storage can
// be blocked (private mode); the screens then keep the choice for this visit only.
export function readStored(key: string) {
  try {
    return window.localStorage.getItem(key) ?? "";
  } catch {
    return "";
  }
}

export function writeStored(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Kept for this visit only.
  }
}
