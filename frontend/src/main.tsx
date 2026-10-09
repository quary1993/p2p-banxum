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
import { captureMagicLinkTokenFromLocation } from "./magicLinkToken";
import "./styles.css";
import "./banxumSkin.css";
import "./skin/projects.css";
import "./skin/loans.css";
import "./skin/investments.css";
import "./skin/account.css";
import "./skin/auth.css";
import "./skin/site.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false
    }
  }
});

// Take a login-link token out of the address bar before the first request (audit A-49).
captureMagicLinkTokenFromLocation();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
);
