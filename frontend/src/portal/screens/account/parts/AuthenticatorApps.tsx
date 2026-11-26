// IP of Webby-Soft SRL.
// "Install an authenticator app": the three apps the setup text names, each with its official
// App Store and Google Play listing (checked 26/11/2026: Google LLC, Microsoft Corporation,
// AgileBits). Shown in every authenticator setup: registration, the second-factor gate,
// Settings → Security and the admin sign-in.
//
// App icons: the official icons are the vendors' trademarks, so they are not drawn here. Put the
// files from each vendor's press or brand page in src/portal/assets/app-icons/ with these names:
// google-authenticator.png, microsoft-authenticator.png, 1password.png (.svg or .webp also work).
// The build picks them up; without a file the row shows a neutral tile with the app's initials.
import { useId } from "react";

import { useT } from "../../../../i18n";
import "./authenticatorApps.css";

const ICON_FILES = import.meta.glob<string>("../../../assets/app-icons/*.{png,svg,webp}", { eager: true, query: "?url", import: "default" });

function iconFor(slug: string) {
  const match = Object.entries(ICON_FILES).find(([path]) => /\/([^/]+)\.(png|svg|webp)$/.exec(path)?.[1] === slug);
  return match?.[1] ?? null;
}

type AuthenticatorApp = {
  slug: string;
  name: string;
  initials: string;
  publisher: string;
  price: "Free" | "Subscription";
  appStore: string;
  googlePlay: string;
};

const AUTHENTICATOR_APPS: AuthenticatorApp[] = [
  {
    slug: "google-authenticator",
    name: "Google Authenticator",
    initials: "GA",
    publisher: "Google",
    price: "Free",
    appStore: "https://apps.apple.com/app/google-authenticator/id388497605",
    googlePlay: "https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2"
  },
  {
    slug: "microsoft-authenticator",
    name: "Microsoft Authenticator",
    initials: "MA",
    publisher: "Microsoft",
    price: "Free",
    appStore: "https://apps.apple.com/app/microsoft-authenticator/id983156458",
    googlePlay: "https://play.google.com/store/apps/details?id=com.azure.authenticator"
  },
  {
    slug: "1password",
    name: "1Password",
    initials: "1P",
    publisher: "AgileBits",
    price: "Subscription",
    appStore: "https://apps.apple.com/app/1password-password-manager/id1511601750",
    googlePlay: "https://play.google.com/store/apps/details?id=com.onepassword.android"
  }
];

function StoreLink({ href, store, app }: { href: string; store: "App Store" | "Google Play"; app: string }) {
  const t = useT();
  return (
    <a
      aria-label={t("{app} on {store} (opens in a new tab)", { app, store })}
      className="aa-store"
      href={href}
      rel="noopener noreferrer"
      target="_blank"
    >
      <span className="aa-store-text">
        <small>{store === "App Store" ? t("iPhone and iPad") : t("Android")}</small>
        <strong>{store}</strong>
      </span>
      {/* An arrow drawn inline: the admin console has no icon font. */}
      <svg aria-hidden="true" fill="none" height="14" viewBox="0 0 16 16" width="14">
        <path d="M5 11 11 5M6 5h5v5" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6" />
      </svg>
    </a>
  );
}

export function AuthenticatorApps() {
  const t = useT();
  const titleId = useId();
  return (
    <section aria-labelledby={titleId} className="aa-apps">
      <div className="aa-head">
        <span aria-hidden="true" className="aa-step">1</span>
        <div>
          <h3 id={titleId}>{t("Install an authenticator app on your phone")}</h3>
          <p>{t("Already have one? Go to step 2 and scan the code.")}</p>
        </div>
      </div>
      <ul className="aa-list">
        {AUTHENTICATOR_APPS.map((app) => {
          const icon = iconFor(app.slug);
          return (
            <li className="aa-app" key={app.slug}>
              <span aria-hidden="true" className={`aa-icon${icon ? " has-image" : ""}`}>
                {icon ? <img alt="" height={40} src={icon} width={40} /> : app.initials}
              </span>
              <span className="aa-name">
                <strong>{app.name}</strong>
                <small>
                  {app.publisher} · {t(app.price)}
                </small>
              </span>
              <span className="aa-stores">
                <StoreLink app={app.name} href={app.appStore} store="App Store" />
                <StoreLink app={app.name} href={app.googlePlay} store="Google Play" />
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** The step heading before the QR code and before the code field ("2 Scan the code", "3 ..."). */
/**
 * "2 Scan this code with the app". Every start of a set-up makes a new secret (the backend deletes
 * the unconfirmed one), so an app entry from an earlier QR code shows codes that are refused. The
 * hint says so. All three apps use the same codes as the backend: SHA-1, 6 digits, 30 seconds
 * (RFC 6238, accounts_auth/totp.py).
 */
export function AuthenticatorStep({ number, title }: { number: number; title: string }) {
  const t = useT();
  return (
    <div className="aa-head aa-head-step">
      <span aria-hidden="true" className="aa-step">{number}</span>
      <div>
        <h3>{title}</h3>
        <p>{t("This code is new each time you start the set-up. If you scanned an older code, delete that entry in your app, then scan this code.")}</p>
      </div>
    </div>
  );
}
