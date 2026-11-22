//IP of Webby-Soft SRL.
// source-seal: SVAgQkVMT05HUyBUTyBXRUJCWS1TT0ZUIFNSTC4=
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@fontsource-variable/archivo";
import "@fontsource-variable/archivo/wght-italic.css";
import "@fontsource-variable/instrument-sans";
// font-synthesis is off, so every family needs its real italic face for <em>/<i>.
import "@fontsource-variable/instrument-sans/standard-italic.css";
import "@fontsource-variable/newsreader";
import "@fontsource-variable/newsreader/wght-italic.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { preloadPreferredLanguage } from "./i18n/language";
import { captureMagicLinkTokenFromLocation, captureSecurityLinkTokenFromLocation } from "./magicLinkToken";
import "./base.css";
// Audit G-07: one stylesheet entry per area. The investor area (sign-in, registration, the portal)
// loads the U33 design CSS scoped to html.bxu (U33Skin) and its fixes here; the public site
// (site/siteStyles.ts) and the admin console (adminConsole/adminStyles.ts, styles.css) load theirs
// with their lazy bundles (lazyAreas.ts). base.css (tokens and element rules) is global.
import "./portal/u33/u33.css";
import "./portal/u33/u33-overrides.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false
    }
  }
});

// Take a login-link token out of the address bar before the first request (audit A-49).
captureMagicLinkTokenFromLocation();
captureSecurityLinkTokenFromLocation();

// U33-DEC-31: a visitor who chose German gets the German texts before the first render.
void preloadPreferredLanguage().then(() =>
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </StrictMode>
  )
);
