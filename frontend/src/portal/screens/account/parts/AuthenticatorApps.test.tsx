// IP of Webby-Soft SRL.
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AuthenticatorApps, AuthenticatorStep } from "./AuthenticatorApps";

const OFFICIAL_LISTINGS: Record<string, [string, string]> = {
  "Google Authenticator": [
    "https://apps.apple.com/app/google-authenticator/id388497605",
    "https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2"
  ],
  "Microsoft Authenticator": [
    "https://apps.apple.com/app/microsoft-authenticator/id983156458",
    "https://play.google.com/store/apps/details?id=com.azure.authenticator"
  ],
  "1Password": [
    "https://apps.apple.com/app/1password-password-manager/id1511601750",
    "https://play.google.com/store/apps/details?id=com.onepassword.android"
  ]
};

describe("AuthenticatorApps", () => {
  it("lists the three apps with their official App Store and Google Play links, opened in a new tab", () => {
    render(<AuthenticatorApps />);

    expect(screen.getByRole("heading", { name: "Install an authenticator app on your phone" })).toBeInTheDocument();
    const rows = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(rows.map((row) => row.querySelector("strong")?.textContent)).toEqual(Object.keys(OFFICIAL_LISTINGS));

    for (const [app, [appStore, googlePlay]] of Object.entries(OFFICIAL_LISTINGS)) {
      const ios = screen.getByRole("link", { name: `${app} on App Store (opens in a new tab)` });
      const android = screen.getByRole("link", { name: `${app} on Google Play (opens in a new tab)` });
      expect(ios).toHaveAttribute("href", appStore);
      expect(android).toHaveAttribute("href", googlePlay);
      for (const link of [ios, android]) {
        expect(link).toHaveAttribute("target", "_blank");
        expect(link).toHaveAttribute("rel", "noopener noreferrer");
      }
    }
  });

  it("shows the official icon from assets/app-icons, or a neutral initials tile when the file is not there", () => {
    render(<AuthenticatorApps />);

    const tiles = [...document.querySelectorAll(".aa-icon")];
    expect(tiles).toHaveLength(3);
    tiles.forEach((tile, index) => {
      if (tile.classList.contains("has-image")) expect(tile.querySelector("img")).not.toBeNull();
      else expect(tile.textContent).toBe(["GA", "MA", "1P"][index]);
    });
  });

  it("tells the user that the QR code is new for each set-up", () => {
    render(<AuthenticatorStep number={2} title="Scan this code with the app" />);

    expect(screen.getByRole("heading", { name: "Scan this code with the app" })).toBeInTheDocument();
    expect(screen.getByText(/This code is new each time you start the set-up/)).toBeInTheDocument();
  });
});
